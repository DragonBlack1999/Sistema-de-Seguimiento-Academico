"""Reglas de la asistencia diaria tomada en la puerta."""

import datetime

from django.conf import settings

from apps.academico.models import Curso, Gestion, Horario, Matricula

from .models import Asistencia


def hora_limite():
    """Hora a partir de la cual una llegada cuenta como atraso."""
    texto = str(getattr(settings, 'HORA_ENTRADA', '13:50')).strip()
    try:
        horas, minutos = texto.split(':')
        return datetime.time(int(horas), int(minutos))
    except (ValueError, TypeError):
        # Un valor mal escrito en el .env no debe tumbar la pantalla de la puerta.
        return datetime.time(13, 50)


def estado_por_hora(hora):
    """Presente si llegó a tiempo, Atraso si pasó la hora límite."""
    return Asistencia.Estado.ATRASO if hora > hora_limite() else Asistencia.Estado.PRESENTE


def gestion_vigente():
    return Gestion.objects.filter(activa=True).order_by('-anio').first() or \
        Gestion.objects.order_by('-anio').first()


# Los lunes son 0 en datetime.weekday(). El sábado es día de clase; el domingo no.
DIA_POR_WEEKDAY = {
    0: Horario.Dia.LUNES,
    1: Horario.Dia.MARTES,
    2: Horario.Dia.MIERCOLES,
    3: Horario.Dia.JUEVES,
    4: Horario.Dia.VIERNES,
    5: Horario.Dia.SABADO,
}


def cursos_en_capacitacion(fecha):
    """Cursos que ese día no pasan por la puerta, porque están en capacitación."""
    dia = DIA_POR_WEEKDAY.get(fecha.weekday())
    if dia is None:
        return Curso.objects.none()
    return Curso.objects.filter(dias_capacitacion__dia=dia).distinct()


def matriculas_del_dia(gestion, fecha):
    """Estudiantes que deben pasar por la puerta ese día.

    Excluye a los cursos en capacitación: si no, "cerrar el día" les pondría
    falta a todos cada semana, porque nunca pasan por la puerta ese día.
    """
    return (
        Matricula.objects
        .filter(curso__gestion=gestion, activa=True)
        .exclude(curso__in=cursos_en_capacitacion(fecha))
        .select_related('estudiante__usuario', 'curso')
        .order_by('curso__nivel', 'curso__grado', 'curso__paralelo',
                  'estudiante__usuario__last_name', 'estudiante__usuario__first_name')
    )


def registrar_entrada(estudiante, gestion, fecha, usuario, hora=None):
    """Marca la entrada de un estudiante. Devuelve (asistencia, creada).

    La gestión no se guarda en el registro: es el año de la fecha. El parámetro
    se mantiene porque las vistas ya la tienen y sirve para no aceptar marcas de
    otro año escolar.
    """
    hora = hora or datetime.datetime.now().time().replace(microsecond=0)
    return Asistencia.objects.update_or_create(
        estudiante=estudiante, fecha=fecha,
        defaults={
            'hora_llegada': hora,
            'estado': estado_por_hora(hora),
            'registrado_por': usuario,
        },
    )


def cerrar_dia(gestion, fecha, usuario):
    """Marca como falta a quien no fue registrado ese día. Devuelve los estudiantes marcados.

    Es el paso que cierra la puerta: hasta entonces "sin registro" significa
    "todavía puede llegar", no "faltó".
    """
    ya_registrados = set(
        Asistencia.objects.filter(fecha=fecha).values_list('estudiante_id', flat=True)
    )
    faltantes = [
        m.estudiante for m in matriculas_del_dia(gestion, fecha)
        if m.estudiante_id not in ya_registrados
    ]
    Asistencia.objects.bulk_create([
        Asistencia(
            estudiante=estudiante, fecha=fecha,
            estado=Asistencia.Estado.FALTA, registrado_por=usuario,
        )
        for estudiante in faltantes
    ], batch_size=500)

    # Cada falta se le avisa a su familia. Va en el resumen del día: son muchas
    # a la vez y ninguna necesita interrumpir en ese momento.
    from apps.comunicaciones.alertas import avisar_falta

    for estudiante in faltantes:
        avisar_falta(estudiante, fecha)
    return faltantes


def de_la_gestion(registros, gestion):
    """Los registros de asistencia de ese año escolar, por su fecha."""
    return registros.filter(fecha__year=gestion.anio)


def resumen_por_estado(registros):
    """Conteo por estado, para la cabecera de las pantallas de consulta."""
    conteo = {}
    for registro in registros:
        conteo[registro.estado] = conteo.get(registro.estado, 0) + 1
    return {
        'presentes': conteo.get(Asistencia.Estado.PRESENTE, 0),
        'atrasos': conteo.get(Asistencia.Estado.ATRASO, 0),
        'faltas': conteo.get(Asistencia.Estado.FALTA, 0),
        'licencias': conteo.get(Asistencia.Estado.LICENCIA, 0),
    }
