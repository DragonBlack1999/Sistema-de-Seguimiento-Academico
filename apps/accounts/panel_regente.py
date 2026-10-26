"""Lo que el regente necesita ver al entrar.

Su panel decía cuántos entraron hoy, en total. Pero el regente no trabaja con
un total: trabaja por curso —«al 3° B todavía le faltan seis»— y con los
nombres de quienes acumulan faltas, que son los que terminan en una citación.
Las dos cosas estaban en el sistema y ninguna se veía sin abrir otra pantalla.
"""
from django.conf import settings
from django.db.models import Count
from django.utils import timezone

from apps.asistencia.models import Asistencia
from apps.asistencia.services import matriculas_del_dia


def por_curso(gestion, fecha):
    """Cuántos faltan por registrar en cada curso, de peor a mejor.

    Dos consultas para todo el colegio: las matrículas del día ya vienen con su
    curso, y los registros del día se piden una sola vez.
    """
    registrados = set(
        Asistencia.objects.filter(fecha=fecha).values_list('estudiante_id', flat=True)
    )

    cursos = {}
    for matricula in matriculas_del_dia(gestion, fecha):
        datos = cursos.setdefault(matricula.curso_id, {
            'curso': matricula.curso, 'total': 0, 'pendientes': 0,
        })
        datos['total'] += 1
        if matricula.estudiante_id not in registrados:
            datos['pendientes'] += 1

    # Primero los que más gente tienen sin registrar: es por donde hay que
    # empezar, y con dieciocho cursos la lista entera no se mira.
    return sorted(cursos.values(), key=lambda d: (-d['pendientes'], str(d['curso'])))


def acumulan_faltas(gestion, cuantos=6):
    """Quiénes están cerca del umbral de faltas, o ya lo pasaron.

    El umbral es el mismo que dispara la citación automática
    (`UMBRAL_FALTAS_ALERTA`): mostrar a quienes se le están acercando es lo que
    permite llamar a la familia **antes** de que el sistema cite solo.
    """
    umbral = settings.UMBRAL_FALTAS_ALERTA
    desde = max(1, umbral - 2)

    filas = (
        Asistencia.objects
        .filter(estado=Asistencia.Estado.FALTA, fecha__year=gestion.anio)
        .values('estudiante_id',
                'estudiante__usuario__first_name', 'estudiante__usuario__last_name')
        .annotate(faltas=Count('id'))
        .filter(faltas__gte=desde)
        .order_by('-faltas')[:cuantos]
    )
    # Si ya se le generó la citación automática, se mira; no se deduce del
    # número. Cruzar el umbral y estar citado no son lo mismo: la citación la
    # genera la puerta al marcar la falta, y una ya atendida no se repite.
    from apps.comunicaciones.models import Citacion

    citados = set(
        Citacion.objects.filter(
            es_automatica=True, estudiante_id__in=[f['estudiante_id'] for f in filas],
        ).values_list('estudiante_id', flat=True)
    )

    return [
        {
            'nombre': f"{f['estudiante__usuario__first_name']} "
                      f"{f['estudiante__usuario__last_name']}".strip(),
            'faltas': f['faltas'],
            'paso_el_umbral': f['faltas'] >= umbral,
            'citado': f['estudiante_id'] in citados,
        }
        for f in filas
    ]


def ultimos_dias(gestion, cuantos=5):
    """Cómo viene la semana: entraron / esperados por día.

    Sirve para ver si lo de hoy es raro o es lo de siempre. Un «faltan 40» no
    dice nada hasta que se sabe que ayer faltaban 12.
    """
    from apps.accounts.tablero import _dias_de_clase

    fechas = _dias_de_clase(timezone.localdate(), cuantos)
    presentes = {}
    for fila in (Asistencia.objects
                 .filter(fecha__in=fechas,
                         estado__in=[Asistencia.Estado.PRESENTE, Asistencia.Estado.ATRASO])
                 .values('fecha').annotate(cuantos=Count('id'))):
        presentes[fila['fecha']] = fila['cuantos']

    dias = []
    for fecha in fechas:
        esperados = matriculas_del_dia(gestion, fecha).count()
        entraron = presentes.get(fecha, 0)
        dias.append({
            'fecha': fecha,
            'esperados': esperados,
            'entraron': entraron,
            'porcentaje': round(entraron / esperados * 100) if esperados else None,
        })
    return dias
