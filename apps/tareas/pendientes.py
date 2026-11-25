from collections import defaultdict

from django.utils import timezone

from apps.calificaciones.models import Puntaje
from .models import EntregaTarea, Tarea


def tareas_vencidas_sin_entregar(gestion, matriculas):
    """Pares (matrícula, tarea) sin entrega ni puntaje, incluida la nota en papel."""
    vencidas = Tarea.objects.filter(asignacion__curso__gestion=gestion, fecha_entrega__lt=timezone.localdate())
    tareas = list(vencidas.select_related('asignacion__curso', 'asignacion__materia'))
    if not tareas:
        return

    resueltas = set(Puntaje.objects.filter(actividad__tarea__in=vencidas).order_by()
                    .values_list('actividad__tarea__id', 'estudiante_id'))
    resueltas.update(EntregaTarea.objects.filter(
        tarea__in=vencidas, estado__in=[EntregaTarea.Estado.ENTREGADA, EntregaTarea.Estado.ATRASADA],
    ).order_by().values_list('tarea_id', 'estudiante_id'))

    por_curso = defaultdict(list)
    for matricula in matriculas:
        por_curso[matricula.curso_id].append(matricula)
    for tarea in tareas:
        for matricula in por_curso[tarea.asignacion.curso_id]:
            if (tarea.pk, matricula.estudiante_id) not in resueltas:
                yield matricula, tarea
