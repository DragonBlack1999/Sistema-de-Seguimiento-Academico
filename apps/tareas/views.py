from decimal import Decimal, InvalidOperation
from pathlib import Path

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Count, Q
from django.http import FileResponse, Http404, HttpResponseForbidden, HttpResponseNotAllowed
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.clickjacking import xframe_options_sameorigin

from apps.academico.models import AsignacionDocente, Matricula
from apps.calificaciones.models import Trimestre

from .forms import EntregaEstudianteForm, TareaForm
from .models import EntregaTarea, Tarea
from .notas import (
    MAXIMO_TAREA, borrar_actividad, entero_valido, guardar_puntaje, puntajes_de, recalcular,
    sincronizar_actividad, sin_calificar,
)
from .validators import tipo_en_linea


def _puede_gestionar(user, asignacion):
    return user.es_admin() or (user.es_profesor() and asignacion.profesor_id == user.id)


def _trimestre_visible(request, tareas):
    """Qué trimestre mostrar en la lista de tareas.

    El de la URL si viene indicado; si no, el más avanzado que ya tenga tareas,
    que es donde el profesor está trabajando. Un año recién empezado abre en el
    primero.
    """
    pedido = request.GET.get('trimestre', '')
    if pedido.isdigit() and int(pedido) in Trimestre.values:
        return int(pedido)
    con_tareas = [t.trimestre for t in tareas]
    return max(con_tareas) if con_tareas else Trimestre.PRIMERO


def _url_lista(asignacion_id, trimestre):
    """Vuelve a la lista abriendo la pestaña del trimestre que se acaba de tocar."""
    return f"{reverse('tareas:lista_tareas', args=[asignacion_id])}?trimestre={trimestre}"


def _notificar_tarea_nueva(tarea, excluir=None):
    """Avisa a los estudiantes del curso y a sus tutores.

    Al tutor se le manda una notificación por hijo, porque cada una apunta a la
    pantalla de tareas de ese hijo en concreto.
    """
    from django.urls import reverse

    from apps.notificaciones.models import Notificacion
    from apps.notificaciones.services import crear_notificaciones

    matriculas = list(_matriculas_del_curso(tarea.asignacion))
    materia = tarea.asignacion.materia

    crear_notificaciones(
        [m.estudiante.usuario_id for m in matriculas],
        tipo=Notificacion.Tipo.TAREA,
        titulo=f'Nueva tarea de {materia}: {tarea.titulo}',
        mensaje=f'Entrega hasta el {tarea.fecha_entrega:%d/%m/%Y}.',
        url=reverse('tareas:mis_tareas'),
        excluir=excluir,
    )
    for matricula in matriculas:
        estudiante = matricula.estudiante
        if not estudiante.tutor_id:
            continue
        crear_notificaciones(
            [estudiante.tutor_id],
            tipo=Notificacion.Tipo.TAREA, estudiante=estudiante,
            titulo=f'Nueva tarea de {materia} para {estudiante.usuario.get_full_name()}',
            mensaje=f'{tarea.titulo} — entrega hasta el {tarea.fecha_entrega:%d/%m/%Y}.',
            url=reverse('padres:tareas_hijo', args=[estudiante.pk]),
            excluir=excluir,
        )


def _matriculas_del_curso(asignacion):
    return (
        Matricula.objects
        .filter(curso=asignacion.curso, activa=True)
        .select_related('estudiante__usuario')
        .order_by('estudiante__usuario__last_name')
    )


# --------------------------------------------------------------------------- profesor / admin

@login_required
def lista_tareas(request, asignacion_id):
    asignacion = get_object_or_404(
        AsignacionDocente.objects.select_related('curso__gestion', 'materia'), pk=asignacion_id
    )
    if not _puede_gestionar(request.user, asignacion):
        return HttpResponseForbidden('No tienes permiso para gestionar las tareas de esta materia.')

    tareas = (
        Tarea.objects.filter(asignacion=asignacion)
        .annotate(
            entregadas=Count(
                'entregas',
                filter=Q(entregas__estado__in=[EntregaTarea.Estado.ENTREGADA, EntregaTarea.Estado.ATRASADA]),
                distinct=True,
            ),
            calificadas=Count('actividad__puntajes', distinct=True),
        )
    )
    total_matriculados = _matriculas_del_curso(asignacion).count()

    # Un trimestre por vez: los tres seguidos obligaban a bajar por tareas de
    # meses atrás para llegar a las de esta semana.
    tareas = list(tareas)
    activo = _trimestre_visible(request, tareas)
    pestanas = [
        {
            'valor': valor,
            'etiqueta': etiqueta,
            'cuantas': sum(1 for t in tareas if t.trimestre == valor),
            'activa': valor == activo,
        }
        for valor, etiqueta in Trimestre.choices
    ]

    return render(request, 'tareas/lista_tareas.html', {
        'asignacion': asignacion,
        'pestanas': pestanas,
        'trimestre': activo,
        'etiqueta_trimestre': Trimestre(activo).label,
        'tareas': [t for t in tareas if t.trimestre == activo],
        'total_matriculados': total_matriculados,
    })


@login_required
def crear_tarea(request, asignacion_id):
    asignacion = get_object_or_404(AsignacionDocente, pk=asignacion_id)
    if not _puede_gestionar(request.user, asignacion):
        return HttpResponseForbidden('No tienes permiso para gestionar las tareas de esta materia.')

    if request.method == 'POST':
        form = TareaForm(request.POST, request.FILES)
        if form.is_valid():
            tarea = form.save(commit=False)
            tarea.asignacion = asignacion
            tarea.creado_por = request.user
            if request.FILES.get('archivo_adjunto'):
                tarea.archivo_nombre = request.FILES['archivo_adjunto'].name
            tarea.save()
            # Cada tarea es una columna de "hacer": se crea junto con ella.
            sincronizar_actividad(tarea, request.user)
            messages.success(
                request,
                f'Tarea creada. Ya aparece en la planilla de notas, sobre {MAXIMO_TAREA:.0f} puntos.',
            )
            _notificar_tarea_nueva(tarea, excluir=request.user)
            return redirect(_url_lista(asignacion.id, tarea.trimestre))
    else:
        form = TareaForm()

    return render(request, 'tareas/form_tarea.html', {
        'form': form, 'asignacion': asignacion, 'es_edicion': False,
    })


@login_required
def editar_tarea(request, tarea_id):
    tarea = get_object_or_404(Tarea.objects.select_related('asignacion'), pk=tarea_id)
    if not _puede_gestionar(request.user, tarea.asignacion):
        return HttpResponseForbidden('No tienes permiso para gestionar las tareas de esta materia.')

    if request.method == 'POST':
        form = TareaForm(request.POST, request.FILES, instance=tarea)
        if form.is_valid():
            tarea = form.save(commit=False)
            if request.FILES.get('archivo_adjunto'):
                tarea.archivo_nombre = request.FILES['archivo_adjunto'].name
            elif not tarea.archivo_adjunto:
                tarea.archivo_nombre = ''
            tarea.save()
            for trimestre in sincronizar_actividad(tarea, request.user):
                recalcular(tarea.asignacion_id, trimestre, usuario=request.user)
            messages.success(request, 'Tarea actualizada correctamente.')
            return redirect(_url_lista(tarea.asignacion_id, tarea.trimestre))
    else:
        form = TareaForm(instance=tarea)

    return render(request, 'tareas/form_tarea.html', {
        'form': form, 'asignacion': tarea.asignacion, 'tarea': tarea, 'es_edicion': True,
    })


@login_required
def eliminar_tarea(request, tarea_id):
    tarea = get_object_or_404(Tarea.objects.select_related('asignacion'), pk=tarea_id)
    if not _puede_gestionar(request.user, tarea.asignacion):
        return HttpResponseForbidden('No tienes permiso para gestionar las tareas de esta materia.')

    asignacion_id = tarea.asignacion_id
    trimestre = tarea.trimestre
    if request.method == 'POST':
        with transaction.atomic():
            estudiantes, trimestre_borrado = borrar_actividad(tarea)
            tarea.delete()
            recalcular(asignacion_id, trimestre_borrado, estudiantes, usuario=request.user)
        messages.warning(request, 'Tarea eliminada, también de la planilla de notas.')
        return redirect(_url_lista(asignacion_id, trimestre))

    return render(request, 'tareas/confirmar_eliminar_tarea.html', {
        'tarea': tarea,
        'total_entregas': tarea.entregas.count(),
        'total_notas': len(puntajes_de(tarea)),
    })


@login_required
def calificar_tarea(request, tarea_id):
    tarea = get_object_or_404(
        Tarea.objects.select_related('asignacion__curso', 'asignacion__materia'), pk=tarea_id
    )
    if not _puede_gestionar(request.user, tarea.asignacion):
        return HttpResponseForbidden('No tienes permiso para gestionar las tareas de esta materia.')

    matriculas = _matriculas_del_curso(tarea.asignacion)
    entregas = {e.estudiante_id: e for e in tarea.entregas.all()}
    # Las notas viven en la columna de la tarea; se traen todas de una vez.
    puntajes = puntajes_de(tarea)

    if request.method == 'POST':
        if request.POST.get('accion') == 'cero_no_entregados':
            sin_entregar = 0
            for matricula in matriculas:
                entrega = entregas.get(matricula.estudiante_id)
                ya_entrego = entrega and entrega.estado in (
                    EntregaTarea.Estado.ENTREGADA, EntregaTarea.Estado.ATRASADA
                )
                if ya_entrego or matricula.estudiante_id in puntajes:
                    continue
                EntregaTarea.objects.update_or_create(
                    tarea=tarea, estudiante=matricula.estudiante,
                    defaults={'estado': EntregaTarea.Estado.NO_ENTREGADA},
                )
                guardar_puntaje(tarea, matricula.estudiante_id, Decimal('0'), request.user)
                sin_entregar += 1
            messages.success(request, f'Se asignó 0 a {sin_entregar} estudiante(s) que no entregaron.')
            return redirect('tareas:calificar_tarea', tarea_id=tarea.id)

        for matricula in matriculas:
            valor = request.POST.get(f'nota_{matricula.estudiante_id}', '').strip()
            observacion = request.POST.get(f'obs_{matricula.estudiante_id}', '').strip()
            if valor == '' and observacion == '':
                continue

            nota_decimal, error = entero_valido(valor)
            if error:
                messages.error(request, f'{matricula.estudiante}: {error}')
                continue

            # La observación es de la entrega; la nota, de la planilla.
            # estado, archivo y fecha_entrega_real NO se tocan: son del estudiante.
            EntregaTarea.objects.update_or_create(
                tarea=tarea, estudiante=matricula.estudiante,
                defaults={'observacion': observacion},
                create_defaults={
                    'observacion': observacion, 'estado': EntregaTarea.Estado.NO_ENTREGADA,
                },
            )
            guardar_puntaje(tarea, matricula.estudiante_id, nota_decimal, request.user)

        messages.success(request, 'Notas guardadas. Ya están en la planilla del trimestre.')
        return redirect('tareas:calificar_tarea', tarea_id=tarea.id)

    filas = []
    for matricula in matriculas:
        entrega = entregas.get(matricula.estudiante_id)
        filas.append({
            'matricula': matricula,
            'entrega': entrega,
            'nota': puntajes.get(matricula.estudiante_id, ''),
            'observacion': entrega.observacion if entrega else '',
        })

    return render(request, 'tareas/calificar_tarea.html', {'tarea': tarea, 'filas': filas})


# --------------------------------------------------------------------------- estudiante

@login_required
def mis_tareas(request):
    estudiante = getattr(request.user, 'estudiante', None)
    if estudiante is None:
        return HttpResponseForbidden('Tu usuario no tiene un perfil de estudiante asociado.')

    matricula = (
        Matricula.objects.filter(estudiante=estudiante, activa=True)
        .select_related('curso__gestion').order_by('-curso__gestion__anio').first()
    )
    if matricula is None:
        return render(request, 'tareas/mis_tareas.html', {'estudiante': estudiante, 'grupos': []})

    tareas = list(
        Tarea.objects
        .filter(asignacion__curso=matricula.curso, asignacion__curso__gestion=matricula.gestion)
        .select_related('asignacion__materia')
        .order_by('trimestre', 'fecha_entrega')
    )
    mis_entregas = {
        e.tarea_id: e for e in EntregaTarea.objects.filter(estudiante=estudiante, tarea__in=tareas)
    }

    grupos = []
    for valor, etiqueta in Trimestre.choices:
        filas = [
            {'tarea': t, 'entrega': mis_entregas.get(t.id)}
            for t in tareas if t.trimestre == valor
        ]
        grupos.append({'etiqueta': etiqueta, 'filas': filas})

    return render(request, 'tareas/mis_tareas.html', {
        'estudiante': estudiante, 'matricula': matricula, 'grupos': grupos,
    })


def _estudiante_puede_ver(user, tarea):
    estudiante = getattr(user, 'estudiante', None)
    if estudiante is None:
        return None
    matriculado = Matricula.objects.filter(
        estudiante=estudiante, curso=tarea.asignacion.curso,
        activa=True,
    ).exists()
    return estudiante if matriculado else None


@login_required
def detalle_tarea(request, tarea_id):
    tarea = get_object_or_404(
        Tarea.objects.select_related('asignacion__curso', 'asignacion__materia', 'asignacion__curso__gestion'),
        pk=tarea_id,
    )
    estudiante = _estudiante_puede_ver(request.user, tarea)
    if estudiante is None:
        return HttpResponseForbidden('No tienes acceso a esta tarea.')

    entrega = EntregaTarea.objects.filter(tarea=tarea, estudiante=estudiante).first()

    if request.method == 'POST':
        if entrega and entrega.calificada:
            messages.error(request, 'La tarea ya fue calificada; no puedes modificar tu entrega.')
            return redirect('tareas:detalle_tarea', tarea_id=tarea.id)

        if request.POST.get('accion') == 'deshacer':
            if entrega:
                entrega.estado = EntregaTarea.Estado.PENDIENTE
                entrega.archivo = None
                entrega.archivo_nombre = ''
                entrega.fecha_entrega_real = None
                entrega.save()
                messages.info(request, 'Entrega deshecha. Puedes volver a entregarla.')
            return redirect('tareas:detalle_tarea', tarea_id=tarea.id)

        if tarea.vencida and not tarea.permite_atraso:
            messages.error(
                request,
                f'La fecha límite ({tarea.fecha_entrega}) ya pasó y esta tarea no admite entregas atrasadas.',
            )
            return redirect('tareas:detalle_tarea', tarea_id=tarea.id)

        form = EntregaEstudianteForm(request.POST, request.FILES, instance=entrega)
        if form.is_valid():
            nueva = form.save(commit=False)
            nueva.tarea = tarea
            nueva.estudiante = estudiante
            if request.FILES.get('archivo'):
                if not tarea.permite_archivo:
                    messages.error(request, 'Esta tarea no admite archivos adjuntos.')
                    return redirect('tareas:detalle_tarea', tarea_id=tarea.id)
                nueva.archivo_nombre = request.FILES['archivo'].name
            nueva.fecha_entrega_real = timezone.now()
            nueva.estado = (
                EntregaTarea.Estado.ATRASADA if tarea.vencida else EntregaTarea.Estado.ENTREGADA
            )
            nueva.save()
            messages.success(request, 'Tu entrega se registró correctamente.')
            return redirect('tareas:detalle_tarea', tarea_id=tarea.id)
    else:
        form = EntregaEstudianteForm(instance=entrega)

    return render(request, 'tareas/detalle_tarea.html', {
        'tarea': tarea, 'entrega': entrega, 'form': form,
    })


# --------------------------------------------------------------------------- descargas protegidas

def _servir(archivo, nombre, en_linea=False):
    """Entrega el archivo. Con `en_linea`, el navegador lo muestra en vez de bajarlo."""
    if not archivo:
        raise Http404('El archivo no existe.')

    nombre = nombre or Path(archivo.name).name
    tipo = tipo_en_linea(archivo.name) if en_linea else None
    if tipo is None:
        # Lo que el navegador no sabe mostrar (un .docx, un .zip) se descarga.
        return FileResponse(archivo.open('rb'), as_attachment=True, filename=nombre)

    respuesta = FileResponse(
        archivo.open('rb'), as_attachment=False, filename=nombre, content_type=tipo,
    )
    # Sin adivinanzas de tipo: un archivo subido por un estudiante no debe poder
    # reinterpretarse como algo que el navegador ejecute dentro de nuestro dominio.
    # Django ya lo pone de serie; aquí se repite porque es la única respuesta que
    # se muestra en línea y no debe depender de un ajuste general.
    respuesta['X-Content-Type-Options'] = 'nosniff'
    return respuesta


@login_required
def descargar_enunciado(request, tarea_id):
    tarea = get_object_or_404(Tarea.objects.select_related('asignacion'), pk=tarea_id)
    permitido = _puede_gestionar(request.user, tarea.asignacion) or _estudiante_puede_ver(request.user, tarea)
    if not permitido:
        return HttpResponseForbidden('No tienes permiso para descargar este archivo.')
    return _servir(tarea.archivo_adjunto, tarea.archivo_nombre)


@login_required
@xframe_options_sameorigin
def descargar_entrega(request, entrega_id):
    """Entrega del estudiante. Con ?ver=1 se muestra dentro del visor del profesor.

    El permiso de marco se abre **solo aquí y solo para el mismo dominio**: el
    resto del sistema sigue con la protección por defecto, que no admite ninguno.
    """
    entrega = get_object_or_404(
        EntregaTarea.objects.select_related('tarea__asignacion', 'estudiante'), pk=entrega_id
    )
    es_dueño = getattr(request.user, 'estudiante', None) == entrega.estudiante
    if not (_puede_gestionar(request.user, entrega.tarea.asignacion) or es_dueño):
        return HttpResponseForbidden('No tienes permiso para descargar este archivo.')
    return _servir(
        entrega.archivo, entrega.archivo_nombre, en_linea=request.GET.get('ver') == '1',
    )
