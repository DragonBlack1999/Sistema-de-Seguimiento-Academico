"""Qué clases toca hoy.

Lo preguntan dos paneles: el del docente («mis clases de hoy») y el del
estudiante («qué tengo hoy»). Vive aquí, y no en cada uno, para que la
respuesta a «qué día es hoy en el horario» sea una sola: el sábado es día de
clase en este colegio y el domingo no, y eso no puede quedar escrito dos veces.
"""
from .models import Horario

# Los lunes son 0 en datetime.weekday(). El sábado es día de clase; el domingo no.
DIA_POR_WEEKDAY = {
    0: Horario.Dia.LUNES,
    1: Horario.Dia.MARTES,
    2: Horario.Dia.MIERCOLES,
    3: Horario.Dia.JUEVES,
    4: Horario.Dia.VIERNES,
    5: Horario.Dia.SABADO,
}


def del_dia(fecha, *, profesor=None, curso=None):
    """Las clases de ese día, en el orden en que se dictan.

    Los períodos no guardan horas —cada curso empieza a una distinta y el
    colegio organiza el día por períodos, no por reloj— así que el orden es lo
    que se muestra, que es como lo nombran ahí.
    """
    dia = DIA_POR_WEEKDAY.get(fecha.weekday())
    if dia is None:
        return []

    clases = Horario.objects.filter(dia=dia)
    if profesor is not None:
        clases = clases.filter(asignacion__profesor=profesor)
    if curso is not None:
        clases = clases.filter(asignacion__curso=curso)

    return list(
        clases
        .select_related('asignacion__curso', 'asignacion__materia', 'asignacion__profesor',
                        'periodo')
        .order_by('periodo__orden')
    )
