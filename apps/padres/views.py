"""Portal del padre/tutor: solo lectura sobre los datos de sus hijos.

Regla de seguridad: la pertenencia se expresa SIEMPRE como filtro del queryset
(`tutor_id=user.id`), nunca como una comparación posterior a un get(pk=...).
Si el id de la URL no corresponde a un hijo suyo, la fila sencillamente no
existe para esa consulta. Además, "no existe" y "no es tu hijo" devuelven el
mismo mensaje, así que no hay forma de enumerar estudiantes ajenos.
"""

from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden
from django.shortcuts import render

from apps.academico.models import Estudiante, Matricula
from apps.accounts import resumenes
from apps.asistencia.models import Asistencia
from apps.asistencia.services import resumen_por_estado
from apps.calificaciones.services import gestion_actual, notas_de_gestion
from apps.calificaciones.services import pivotar_notas
from apps.tareas.models import EntregaTarea, Tarea
from apps.tareas.notas import sin_calificar

MENSAJE_SIN_PERMISO = 'No tienes permiso para ver la información de este estudiante.'


def _hijos(user):
    return (
        Estudiante.objects.filter(tutor_id=user.id)
        .select_related('usuario')
        .order_by('usuario__last_name', 'usuario__first_name')
    )


def _hijo_o_none(user, estudiante_id):
    if not user.is_authenticated or not user.es_padre():
        return None
    return _hijos(user).filter(pk=estudiante_id).first()


@login_required
def panel(request):
    if not request.user.es_padre():
        return HttpResponseForbidden('Esta sección es solo para padres o tutores.')

    hijos = list(_hijos(request.user))

    tarjetas = []
    for hijo in hijos:
        _, totales = pivotar_notas(notas_de_gestion(hijo, gestion_actual(hijo)))
        tarjetas.append({
            'hijo': hijo,
            'promedio': totales['promedio'] if totales and totales['promedio'] != '-' else None,
            'faltas': Asistencia.objects.filter(
                estudiante=hijo, estado=Asistencia.Estado.FALTA,
            ).count(),
            'citaciones_pendientes': hijo.citaciones.filter(estado='PENDIENTE').count(),
            'tareas_pendientes': sin_calificar(
                EntregaTarea.objects.filter(estudiante=hijo)
            ).count(),
        })

    return render(request, 'padres/panel.html', {
        'tarjetas': tarjetas, 'avisos': resumenes.para_padre(hijos),
    })


@login_required
def notas_hijo(request, estudiante_id):
    hijo = _hijo_o_none(request.user, estudiante_id)
    if hijo is None:
        return HttpResponseForbidden(MENSAJE_SIN_PERMISO)

    gestion = gestion_actual(hijo)
    filas, totales = pivotar_notas(notas_de_gestion(hijo, gestion))
    return render(request, 'padres/notas_hijo.html', {
        'hijo': hijo, 'filas': filas, 'totales': totales, 'gestion': gestion,
    })


@login_required
def asistencia_hijo(request, estudiante_id):
    hijo = _hijo_o_none(request.user, estudiante_id)
    if hijo is None:
        return HttpResponseForbidden(MENSAJE_SIN_PERMISO)

    registros = Asistencia.objects.filter(estudiante=hijo)
    return render(request, 'padres/asistencia_hijo.html', {
        'hijo': hijo, 'registros': registros, 'resumen': resumen_por_estado(registros),
    })


@login_required
def tareas_hijo(request, estudiante_id):
    hijo = _hijo_o_none(request.user, estudiante_id)
    if hijo is None:
        return HttpResponseForbidden(MENSAJE_SIN_PERMISO)

    matricula = (
        Matricula.objects.filter(estudiante=hijo, activa=True)
        .select_related('curso__gestion').order_by('-curso__gestion__anio').first()
    )
    filas = []
    if matricula is not None:
        tareas = list(
            Tarea.objects
            .filter(asignacion__curso=matricula.curso)
            .select_related('asignacion__materia')
            .order_by('trimestre', 'fecha_entrega')
        )
        entregas = {
            e.tarea_id: e
            for e in EntregaTarea.objects.filter(estudiante=hijo, tarea__in=tareas)
        }
        filas = [{'tarea': t, 'entrega': entregas.get(t.id)} for t in tareas]

    return render(request, 'padres/tareas_hijo.html', {
        'hijo': hijo, 'matricula': matricula, 'filas': filas,
    })


@login_required
def citaciones_hijo(request, estudiante_id):
    hijo = _hijo_o_none(request.user, estudiante_id)
    if hijo is None:
        return HttpResponseForbidden(MENSAJE_SIN_PERMISO)

    return render(request, 'padres/citaciones_hijo.html', {
        'hijo': hijo, 'citaciones': hijo.citaciones.all(),
    })
