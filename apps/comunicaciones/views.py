from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, HttpResponseForbidden, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render

from apps.academico.busqueda import buscar_estudiantes
from apps.academico.models import Estudiante

from .alertas import notificar_citacion
from .emails import destinatarios_estudiante, enviar_correo, enviar_notificacion_citacion
from .forms import CitacionForm
from .models import Citacion
from .reportes import generar_boletin_pdf


def _es_staff(user):
    return user.es_admin() or user.es_profesor()


# Cuántas sugerencias devuelve el buscador del formulario de citación. Con más
# de ocho la lista deja de ayudar: obliga a leer en vez de a reconocer.
LIMITE_SUGERENCIAS = 8


@login_required
def sugerencias_estudiantes(request):
    """Nombres aproximados para el buscador de la citación.

    Reutiliza el mismo buscador que la pantalla de boletines, así que tolera
    tildes y da igual escribir primero el nombre o el apellido.
    """
    if not _es_staff(request.user):
        return HttpResponseForbidden('No tienes permiso para buscar estudiantes.')

    consulta = request.GET.get('q', '').strip()
    if len(consulta) < 2:
        # Con una sola letra la lista sería medio colegio: no orienta a nadie.
        return JsonResponse({'resultados': []})

    encontrados = (
        buscar_estudiantes(consulta)
        .select_related('usuario')
        .order_by('usuario__last_name', 'usuario__first_name')[:LIMITE_SUGERENCIAS]
    )
    return JsonResponse({'resultados': [
        {
            'id': estudiante.pk,
            'nombre': estudiante.usuario.get_full_name(),
            'rude': estudiante.rude,
            'curso': str(estudiante.curso_actual) if estudiante.curso_actual else 'Sin curso',
        }
        for estudiante in encontrados
    ]})


@login_required
def lista_citaciones(request):
    if request.user.es_estudiante():
        estudiante = getattr(request.user, 'estudiante', None)
        citaciones = Citacion.objects.filter(estudiante=estudiante) if estudiante else []
    else:
        citaciones = Citacion.objects.select_related('estudiante__usuario')
    return render(request, 'comunicaciones/lista_citaciones.html', {'citaciones': citaciones})


@login_required
def crear_citacion(request):
    if not _es_staff(request.user):
        return HttpResponseForbidden('No tienes permiso para generar citaciones.')

    if request.method == 'POST':
        form = CitacionForm(request.POST)
        if form.is_valid():
            citacion = form.save(commit=False)
            citacion.generado_por = request.user
            citacion.save()
            messages.success(request, 'Citación generada correctamente.')
            notificar_citacion(citacion)

            destinatarios = destinatarios_estudiante(citacion.estudiante)
            if destinatarios:
                try:
                    enviar_notificacion_citacion(citacion)
                    messages.info(request, f'Correo de citación enviado a: {", ".join(destinatarios)}')
                except Exception as error:
                    messages.warning(request, f'La citación se guardó, pero el correo no pudo enviarse: {error}')
            else:
                messages.warning(request, 'La citación se guardó, pero el estudiante no tiene correos registrados.')

            return redirect('comunicaciones:lista_citaciones')
    else:
        form = CitacionForm(initial={'estudiante': request.GET.get('estudiante')})

    # El campo real guarda el id; el buscador de la pantalla necesita el nombre
    # para poder mostrarlo escrito, tanto al llegar desde un enlace como al
    # volver de un formulario con errores.
    pedido = (request.POST.get('estudiante') or request.GET.get('estudiante') or '').strip()
    elegido = None
    if pedido.isdigit():
        elegido = Estudiante.objects.filter(pk=pedido).select_related('usuario').first()

    return render(request, 'comunicaciones/crear_citacion.html', {
        'form': form,
        'elegido': elegido,
    })


@login_required
def cambiar_estado_citacion(request, citacion_id, estado):
    if not _es_staff(request.user):
        return HttpResponseForbidden('No tienes permiso para modificar citaciones.')

    citacion = get_object_or_404(Citacion, pk=citacion_id)
    if estado in Citacion.Estado.values:
        citacion.estado = estado
        citacion.save()
        messages.success(request, 'Estado de la citación actualizado.')
    return redirect('comunicaciones:lista_citaciones')


def _puede_ver_boletin(user, estudiante):
    if user.es_admin():
        return True
    if user.es_estudiante():
        return getattr(user, 'estudiante', None) == estudiante
    if user.es_padre():
        return estudiante.tutor_id == user.id
    return False


@login_required
def buscar_boletines(request):
    """Buscador de estudiantes desde el que el administrador descarga cualquier boletín."""
    if not request.user.es_admin():
        return HttpResponseForbidden('Solo el administrador puede generar boletines de otros estudiantes.')

    consulta = request.GET.get('q', '').strip()
    estudiantes = (
        buscar_estudiantes(consulta)
        .select_related('usuario')
        .prefetch_related('matriculas__curso__gestion')
    )

    return render(request, 'comunicaciones/buscar_boletines.html', {
        'consulta': consulta,
        'estudiantes': estudiantes,
    })


@login_required
def notas_por_curso_excel(request):
    """Todas las notas de la gestión en Excel: un resumen y una hoja por curso."""
    if not request.user.es_admin():
        return HttpResponseForbidden('Solo el administrador puede descargar las notas de todos los cursos.')

    # Importación local: openpyxl solo se carga si alguien descarga.
    from apps.asistencia.services import gestion_vigente

    from .planilla_notas import libro_de_notas

    gestion = gestion_vigente()
    if gestion is None:
        return HttpResponseForbidden('No hay ninguna gestión escolar registrada.')

    respuesta = HttpResponse(
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    )
    respuesta['Content-Disposition'] = f'attachment; filename="notas-por-curso-{gestion.anio}.xlsx"'
    libro_de_notas(gestion).save(respuesta)
    return respuesta


@login_required
def boletin_estudiante(request, estudiante_id):
    estudiante = get_object_or_404(Estudiante, pk=estudiante_id)
    if not _puede_ver_boletin(request.user, estudiante):
        return HttpResponseForbidden('No tienes permiso para ver este boletín.')

    pdf_bytes = generar_boletin_pdf(estudiante)
    response = HttpResponse(pdf_bytes, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="boletin_{estudiante.rude}.pdf"'
    return response


@login_required
def enviar_boletin_correo(request, estudiante_id):
    estudiante = get_object_or_404(Estudiante, pk=estudiante_id)
    if not (_es_staff(request.user) or _puede_ver_boletin(request.user, estudiante)):
        return HttpResponseForbidden('No tienes permiso para enviar este boletín.')

    destinatarios = destinatarios_estudiante(estudiante)
    if not destinatarios:
        messages.warning(request, 'El estudiante no tiene correos registrados (ni propio ni de su tutor).')
        return redirect(request.META.get('HTTP_REFERER', 'comunicaciones:lista_citaciones'))

    pdf_bytes = generar_boletin_pdf(estudiante)
    cuerpo = (
        f'Estimado(a) padre/madre/tutor y estudiante {estudiante.usuario.get_full_name()}:\n\n'
        f'Adjuntamos el boletín de calificaciones actualizado.\n\n'
        f'Unidad Educativa «Eduardo Abaroa Tarde» - Nivel Secundario'
    )
    try:
        enviar_correo(
            f'Boletín de calificaciones - {estudiante.usuario.get_full_name()}',
            cuerpo, destinatarios,
            adjunto_bytes=pdf_bytes, adjunto_nombre=f'boletin_{estudiante.rude}.pdf',
        )
        messages.success(request, f'Boletín enviado por correo a: {", ".join(destinatarios)}')
    except Exception as error:
        messages.error(request, f'No se pudo enviar el correo: {error}')

    return redirect(request.META.get('HTTP_REFERER', 'comunicaciones:lista_citaciones'))
