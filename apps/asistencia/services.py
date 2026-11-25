"""Reglas de la asistencia diaria tomada en la puerta."""

import datetime

from django.conf import settings
from django.utils import timezone

from apps.academico.clases import DIA_POR_WEEKDAY
from apps.academico.models import Curso, Gestion, Matricula

from .models import Asistencia


class RegistroNoValido(ValueError):
    """La fecha o el estudiante no corresponden a la jornada."""


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


# Qué día del horario es cada fecha. Vive en `academico.clases` porque también
# lo preguntan los paneles del docente y del estudiante, y «el sábado es día de
# clase y el domingo no» no puede estar escrito en dos sitios.


def cursos_en_capacitacion(fecha):
    """Cursos que ese día no pasan por la puerta, porque están en capacitación."""
    dia = DIA_POR_WEEKDAY.get(fecha.weekday())
    if dia is None:
        return Curso.objects.none()
    return Curso.objects.filter(dias_capacitacion__dia=dia).distinct()


def error_de_fecha(gestion, fecha, *, puerta=True):
    if gestion is None or not gestion.activa:
        return 'No hay una gestión activa para registrar asistencia.'
    if (fecha.year != gestion.anio
            or (gestion.fecha_inicio and fecha < gestion.fecha_inicio)
            or (gestion.fecha_fin and fecha > gestion.fecha_fin)):
        return f'La fecha está fuera de la gestión escolar {gestion.anio}.'
    if puerta and fecha.weekday() not in DIA_POR_WEEKDAY:
        return 'Ese día no hay ingreso por la puerta del colegio.'
    return ''


def matriculas_del_dia(gestion, fecha):
    """Estudiantes que deben pasar por la puerta ese día.

    Excluye a los cursos en capacitación: si no, "cerrar el día" les pondría
    falta a todos cada semana, porque nunca pasan por la puerta ese día.
    """
    if error_de_fecha(gestion, fecha):
        return Matricula.objects.none()
    # OJO con `fecha_matricula`: el corte es correcto —quien se inscribió el
    # martes no estaba el lunes— pero el campo es `auto_now_add`, así que
    # guarda cuándo se tecleó la matrícula, no cuándo se inscribió el alumno.
    # Las 402 del colegio se cargaron todas el 14/09/2026: para cualquier
    # fecha anterior a esa carga, esta lista sale vacía. Mientras el campo no
    # sea una fecha de inscripción de verdad (editable y rellenada hacia
    # atrás), no conviene mirar días previos a la carga de datos.
    return (
        Matricula.objects
        .filter(curso__gestion=gestion, activa=True, estudiante__usuario__is_active=True,
                fecha_matricula__lte=fecha)
        .exclude(curso__in=cursos_en_capacitacion(fecha))
        .select_related('estudiante__usuario', 'curso')
        .order_by('curso__nivel', 'curso__grado', 'curso__paralelo',
                  'estudiante__usuario__last_name', 'estudiante__usuario__first_name')
    )


def registrar_entrada(estudiante, gestion, fecha, usuario, hora=None, *, estado=None):
    """Marca la entrada de un estudiante. Devuelve (asistencia, creada).

    La gestión no se guarda en el registro: es el año de la fecha. El parámetro
    se mantiene porque las vistas ya la tienen y sirve para no aceptar marcas de
    otro año escolar.
    """
    error = error_de_fecha(gestion, fecha)
    if error:
        raise RegistroNoValido(error)
    if not matriculas_del_dia(gestion, fecha).filter(estudiante=estudiante).exists():
        raise RegistroNoValido('El estudiante no está en la lista de ingreso de ese día.')
    hora = hora or timezone.localtime().time().replace(microsecond=0)
    estado = estado or estado_por_hora(hora)
    return Asistencia.objects.update_or_create(
        estudiante=estudiante, fecha=fecha,
        defaults={
            'hora_llegada': hora if estado in (Asistencia.Estado.PRESENTE, Asistencia.Estado.ATRASO) else None,
            'estado': estado,
            'registrado_por': usuario,
        },
    )


def cerrar_dia(gestion, fecha, usuario):
    """Marca como falta a quien no fue registrado ese día. Devuelve los estudiantes marcados.

    Es el paso que cierra la puerta: hasta entonces "sin registro" significa
    "todavía puede llegar", no "faltó".
    """
    error = error_de_fecha(gestion, fecha)
    if error:
        raise RegistroNoValido(error)
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
