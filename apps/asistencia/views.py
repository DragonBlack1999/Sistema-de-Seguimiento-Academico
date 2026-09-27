import datetime
import io

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import Http404, HttpResponse, HttpResponseForbidden, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.text import slugify
from django.views.decorators.http import require_POST

from apps.academico.busqueda import buscar_estudiantes
from apps.academico.models import Curso, Estudiante, Matricula
from apps.comunicaciones.alertas import avisar_atraso, avisar_falta, verificar_alerta_faltas

from .models import Asistencia
from .services import (
    cerrar_dia,
    cursos_en_capacitacion,
    gestion_vigente,
    hora_limite,
    matriculas_del_dia,
    registrar_entrada,
    resumen_por_estado,
)

MENSAJE_SOLO_REGENTE = 'Solo el regente o un administrador pueden registrar la asistencia.'


def _puede_registrar(user):
    return user.es_regente() or user.es_admin()


def _fecha_pedida(request):
    texto = request.GET.get('fecha') or request.POST.get('fecha')
    if texto:
        try:
            return datetime.date.fromisoformat(texto)
        except ValueError:
            pass
    return timezone.localdate()


# --------------------------------------------------------------- puerta (regente)

@login_required
def puerta(request):
    """Pantalla de la puerta: la lista del día con buscador."""
    if not _puede_registrar(request.user):
        return HttpResponseForbidden(MENSAJE_SOLO_REGENTE)

    gestion = gestion_vigente()
    if gestion is None:
        return render(request, 'asistencia/puerta.html', {'sin_gestion': True})

    fecha = _fecha_pedida(request)
    consulta = request.GET.get('q', '').strip()

    matriculas = matriculas_del_dia(gestion, fecha)
    if consulta:
        permitidos = set(
            buscar_estudiantes(consulta).values_list('pk', flat=True)
        )
        matriculas = [m for m in matriculas if m.estudiante_id in permitidos]
    else:
        matriculas = list(matriculas)

    registros = {
        a.estudiante_id: a
        for a in Asistencia.objects.filter(fecha=fecha)
    }

    filas = [
        {'matricula': m, 'asistencia': registros.get(m.estudiante_id)}
        for m in matriculas
    ]

    total = matriculas_del_dia(gestion, fecha).count()
    presentes = sum(1 for a in registros.values() if a.estado == Asistencia.Estado.PRESENTE)
    atrasos = sum(1 for a in registros.values() if a.estado == Asistencia.Estado.ATRASO)
    faltas = sum(1 for a in registros.values() if a.estado == Asistencia.Estado.FALTA)
    licencias = sum(1 for a in registros.values() if a.estado == Asistencia.Estado.LICENCIA)

    return render(request, 'asistencia/puerta.html', {
        'gestion': gestion,
        'fecha': fecha,
        'consulta': consulta,
        'filas': filas,
        'estados': Asistencia.Estado.choices,
        'hora_limite': hora_limite(),
        'en_capacitacion': list(cursos_en_capacitacion(fecha)),
        'resumen': {
            'total': total,
            'presentes': presentes,
            'atrasos': atrasos,
            'faltas': faltas,
            'licencias': licencias,
            'sin_registrar': total - len(registros),
        },
    })


@login_required
@require_POST
def marcar(request, estudiante_id):
    """Registra la entrada de un estudiante. Responde JSON para no recargar la puerta."""
    if not _puede_registrar(request.user):
        return HttpResponseForbidden(MENSAJE_SOLO_REGENTE)

    gestion = gestion_vigente()
    estudiante = get_object_or_404(Estudiante.objects.select_related('usuario'), pk=estudiante_id)
    fecha = _fecha_pedida(request)
    estado_pedido = request.POST.get('estado', '')

    if estado_pedido in Asistencia.Estado.values:
        # El regente eligió el estado a mano (falta justificada, licencia, corrección).
        asistencia, _ = Asistencia.objects.update_or_create(
            estudiante=estudiante, fecha=fecha,
            defaults={
                'estado': estado_pedido,
                'hora_llegada': (
                    timezone.localtime().time().replace(microsecond=0)
                    if estado_pedido in (Asistencia.Estado.PRESENTE, Asistencia.Estado.ATRASO)
                    else None
                ),
                'registrado_por': request.user,
            },
        )
    else:
        asistencia, _ = registrar_entrada(
            estudiante, gestion, fecha, request.user,
            hora=timezone.localtime().time().replace(microsecond=0),
        )

    aviso = ''
    if asistencia.estado == Asistencia.Estado.FALTA:
        # A la familia se le avisa siempre; la citación solo si acumula faltas.
        avisar_falta(estudiante, fecha)
        try:
            citacion = verificar_alerta_faltas(estudiante, gestion, generado_por=request.user)
            if citacion:
                aviso = f'Se generó una citación automática para {estudiante} por inasistencias reiteradas.'
        except Exception as error:
            aviso = f'Asistencia guardada, pero la alerta automática falló: {error}'
    elif asistencia.estado == Asistencia.Estado.ATRASO and asistencia.hora_llegada:
        avisar_atraso(estudiante, fecha, asistencia.hora_llegada)

    return JsonResponse({
        'estado': asistencia.estado,
        'estado_texto': asistencia.get_estado_display(),
        'hora': asistencia.hora_llegada.strftime('%H:%M') if asistencia.hora_llegada else '',
        'aviso': aviso,
    })


@login_required
@require_POST
def cerrar(request):
    """Marca como falta a todos los que no pasaron por la puerta ese día."""
    if not _puede_registrar(request.user):
        return HttpResponseForbidden(MENSAJE_SOLO_REGENTE)

    gestion = gestion_vigente()
    fecha = _fecha_pedida(request)
    marcados = cerrar_dia(gestion, fecha, request.user)

    citaciones = 0
    for estudiante in marcados:
        try:
            if verificar_alerta_faltas(estudiante, gestion, generado_por=request.user):
                citaciones += 1
        except Exception as error:
            messages.warning(request, f'La alerta automática de {estudiante} falló: {error}')

    if marcados:
        texto = f'Día cerrado: {len(marcados)} estudiante(s) quedaron como falta.'
        if citaciones:
            texto += f' Se generaron {citaciones} citación(es) automática(s).'
        messages.success(request, texto)
    else:
        messages.info(request, 'Todos los estudiantes ya tenían su asistencia registrada.')

    return redirect(f"{reverse('asistencia:puerta')}?fecha={fecha.isoformat()}")


# --------------------------------------------------------------- capacitación (admin)

MENSAJE_SOLO_ADMIN = 'Solo el administrador puede registrar la asistencia de capacitación.'

# En capacitación el curso entra en grupo y a otra hora: solo interesa si vino o
# no. Por eso la pantalla ofrece dos botones y no guarda hora de llegada.
ESTADOS_CAPACITACION = (Asistencia.Estado.PRESENTE, Asistencia.Estado.FALTA)


def _cursos_con_capacitacion(gestion):
    """Cursos de la gestión que tienen días de capacitación asignados."""
    return list(
        Curso.objects.filter(gestion=gestion, dias_capacitacion__isnull=False)
        .distinct().order_by('nivel', 'grado', 'paralelo')
    )


@login_required
def capacitacion(request):
    """Asistencia de los cursos que ese día están en capacitación, curso por curso.

    Se guarda la lista entera de una vez (patrón de formulario masivo del
    proyecto), porque estos cursos llegan en grupo y a otra hora, no de uno en
    uno como en la puerta.
    """
    if not request.user.es_admin():
        return HttpResponseForbidden(MENSAJE_SOLO_ADMIN)

    gestion = gestion_vigente()
    if gestion is None:
        return render(request, 'asistencia/capacitacion.html', {'sin_gestion': True})

    fecha = _fecha_pedida(request)
    del_dia = list(cursos_en_capacitacion(fecha).filter(gestion=gestion))
    todos = _cursos_con_capacitacion(gestion)

    # Por defecto se propone el curso que toca ese día; si no toca ninguno, el
    # administrador puede elegir igual (una recuperación, un día repuesto).
    curso = None
    pedido = request.GET.get('curso') or request.POST.get('curso')
    if pedido:
        curso = next((c for c in todos if str(c.pk) == str(pedido)), None)
    elif del_dia:
        curso = del_dia[0]

    matriculas = []
    if curso is not None:
        matriculas = list(
            Matricula.objects.filter(curso=curso, activa=True)
            .select_related('estudiante__usuario')
            .order_by('estudiante__usuario__last_name', 'estudiante__usuario__first_name')
        )

    if request.method == 'POST' and curso is not None:
        guardados, citaciones = 0, 0
        for matricula in matriculas:
            estado = request.POST.get(f'estado_{matricula.estudiante_id}', '')
            if estado not in ESTADOS_CAPACITACION:
                # Sin botón elegido (o con un estado que esta pantalla ya no
                # ofrece) se deja el registro como estaba, sin pisarlo.
                continue

            Asistencia.objects.update_or_create(
                estudiante=matricula.estudiante, fecha=fecha,
                defaults={
                    'estado': estado, 'hora_llegada': None,
                    'observacion': 'Clase de capacitación',
                    'registrado_por': request.user,
                },
            )
            guardados += 1

            if estado == Asistencia.Estado.FALTA:
                avisar_falta(matricula.estudiante, fecha)
                try:
                    if verificar_alerta_faltas(matricula.estudiante, gestion, generado_por=request.user):
                        citaciones += 1
                except Exception as error:
                    messages.warning(request, f'La alerta automática de {matricula.estudiante} falló: {error}')

        texto = f'Asistencia de capacitación guardada: {guardados} estudiante(s).'
        if citaciones:
            texto += f' Se generaron {citaciones} citación(es) automática(s).'
        messages.success(request, texto)
        return redirect(f"{reverse('asistencia:capacitacion')}?fecha={fecha.isoformat()}&curso={curso.pk}")

    registros = {
        a.estudiante_id: a for a in Asistencia.objects.filter(
            fecha=fecha, estudiante__in=[m.estudiante_id for m in matriculas],
        )
    } if matriculas else {}

    filas = []
    for m in matriculas:
        registro = registros.get(m.estudiante_id)
        # Sin registro previo se propone Presente: así solo hay que marcar a los
        # que faltaron, que son los menos.
        estado = registro.estado if registro else Asistencia.Estado.PRESENTE
        filas.append({
            'matricula': m,
            'asistencia': registro,
            'estado': estado,
            # Un estado que esta pantalla ya no ofrece (una licencia cargada
            # desde el panel de datos): se muestra, y ningún botón sale marcado.
            'otro_estado': (
                registro.get_estado_display()
                if registro and estado not in ESTADOS_CAPACITACION else ''
            ),
        })

    return render(request, 'asistencia/capacitacion.html', {
        'gestion': gestion,
        'fecha': fecha,
        'curso': curso,
        'cursos': todos,
        'del_dia': del_dia,
        'filas': filas,
    })


# --------------------------------------------------- planilla del curso en Excel

@login_required
def capacitacion_excel(request):
    """Planilla del curso en Excel: una hoja de resumen y una hoja por mes.

    Cubre toda la gestión, no solo el día que se esté viendo en pantalla: lo que
    se pide para archivar o presentar es el acumulado del curso.
    """
    if not request.user.es_admin():
        return HttpResponseForbidden(MENSAJE_SOLO_ADMIN)

    gestion = gestion_vigente()
    if gestion is None:
        raise Http404('No hay ninguna gestión escolar registrada.')

    pedido = request.GET.get('curso', '')
    curso = next((c for c in _cursos_con_capacitacion(gestion) if str(c.pk) == pedido), None)
    if curso is None:
        raise Http404('Ese curso no tiene clases de capacitación.')

    matriculas = list(
        Matricula.objects.filter(curso=curso, activa=True)
        .select_related('estudiante__usuario')
        .order_by('estudiante__usuario__last_name', 'estudiante__usuario__first_name')
    )
    registros = Asistencia.objects.filter(
        fecha__year=gestion.anio, estudiante_id__in=[m.estudiante_id for m in matriculas],
    )

    fechas = sorted({a.fecha for a in registros})
    por_estudiante = {}
    for a in registros:
        por_estudiante.setdefault(a.estudiante_id, {})[a.fecha] = a

    # La importación es local: openpyxl solo se carga si alguien descarga.
    from .planillas import planilla_de_capacitacion

    libro = planilla_de_capacitacion(curso, gestion, matriculas, fechas, por_estudiante)

    memoria = io.BytesIO()
    libro.save(memoria)
    memoria.seek(0)

    nombre = f'asistencia-{slugify(str(curso))}.xlsx'
    respuesta = HttpResponse(
        memoria.read(),
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    )
    respuesta['Content-Disposition'] = f'attachment; filename="{nombre}"'
    return respuesta


# --------------------------------------------------------------- consulta

@login_required
def mi_asistencia(request):
    estudiante = getattr(request.user, 'estudiante', None)
    if estudiante is None:
        return HttpResponseForbidden('Tu usuario no tiene un perfil de estudiante asociado.')

    registros = Asistencia.objects.filter(estudiante=estudiante)
    resumen = resumen_por_estado(registros)
    return render(request, 'asistencia/mi_asistencia.html', {
        'registros': registros, 'estudiante': estudiante, 'resumen': resumen,
    })
