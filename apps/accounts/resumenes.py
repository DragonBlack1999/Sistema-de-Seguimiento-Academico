"""Avisos en frases normales para la cabecera de cada panel.

Cada función devuelve una lista de diccionarios `{tono, texto}`, donde `texto`
ya viene redactado como una frase y `tono` elige el color del ícono. La idea es
que el usuario lea lo que necesita saber sin tener que interpretar una tabla.

`texto` se marca como seguro porque lo componemos aquí con `format_html`,
escapando los datos que vienen de la base.
"""


from django.utils import timezone
from django.utils.formats import number_format
from django.utils.html import format_html

from apps.academico.models import Matricula
from apps.asistencia.models import Asistencia
from apps.comunicaciones.models import Citacion
from apps.tareas.models import EntregaTarea, Tarea

# Tonos disponibles: 'urgente' (rojo), 'atencion' (naranja), 'bien' (verde), 'dato' (azul)
DIAS = ['lunes', 'martes', 'miércoles', 'jueves', 'viernes', 'sábado', 'domingo']
MESES = ['enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio', 'julio',
         'agosto', 'septiembre', 'octubre', 'noviembre', 'diciembre']


def _fecha_legible(fecha):
    """'jueves 10' si es de esta semana, 'el 10 de septiembre' si está más lejos."""
    hoy = timezone.localdate()
    delta = (fecha - hoy).days
    if delta == 0:
        return 'hoy'
    if delta == 1:
        return 'mañana'
    if 0 < delta <= 6:
        return f'el {DIAS[fecha.weekday()]} {fecha.day}'
    return f'el {fecha.day} de {MESES[fecha.month - 1]}'


def _matricula_activa(estudiante):
    return (
        Matricula.objects.filter(estudiante=estudiante, activa=True)
        .select_related('curso__gestion').order_by('-curso__gestion__anio').first()
    )


def para_estudiante(estudiante):
    """Lo que un estudiante necesita saber al entrar."""
    avisos = []
    matricula = _matricula_activa(estudiante)

    # 1. Tareas sin entregar cuya fecha no pasó todavía
    if matricula is not None:
        tareas = Tarea.objects.filter(
            asignacion__curso=matricula.curso,
            fecha_entrega__gte=timezone.localdate(),
        ).select_related('asignacion__materia').order_by('fecha_entrega')

        entregadas = set(
            EntregaTarea.objects.filter(
                estudiante=estudiante, tarea__in=tareas,
                estado__in=[EntregaTarea.Estado.ENTREGADA, EntregaTarea.Estado.ATRASADA],
            ).values_list('tarea_id', flat=True)
        )
        pendientes = [t for t in tareas if t.pk not in entregadas]

        if pendientes:
            proxima = pendientes[0]
            if len(pendientes) == 1:
                texto = format_html(
                    'Tienes <strong>1 tarea por entregar</strong>: <strong>{}</strong>, vence {}.',
                    proxima.titulo, _fecha_legible(proxima.fecha_entrega),
                )
            else:
                texto = format_html(
                    'Tienes <strong>{} tareas por entregar</strong>. La más próxima, '
                    '<strong>{}</strong>, vence {}.',
                    len(pendientes), proxima.titulo, _fecha_legible(proxima.fecha_entrega),
                )
            avisos.append({'tono': 'atencion', 'texto': texto})

    # 2. Citaciones pendientes
    citacion = (
        Citacion.objects.filter(estudiante=estudiante, estado=Citacion.Estado.PENDIENTE)
        .order_by('fecha').first()
    )
    if citacion is not None:
        hora = f' a las {citacion.hora:%H:%M}' if citacion.hora else ''
        avisos.append({'tono': 'urgente', 'texto': format_html(
            'Te citaron para {}{} en {}: {}',
            _fecha_legible(citacion.fecha), hora,
            citacion.lugar or 'el colegio', citacion.motivo,
        )})

    # 3. Cómo va: promedio o inasistencias
    from apps.calificaciones.services import gestion_actual, notas_de_gestion
    from apps.calificaciones.services import pivotar_notas

    gestion = gestion_actual(estudiante)
    _, totales = pivotar_notas(notas_de_gestion(estudiante, gestion))
    if totales and totales['promedio'] != '-':
        # number_format aplica la coma decimal del idioma, como hacen las plantillas
        avisos.append({'tono': 'bien', 'texto': format_html(
            'Tu promedio va en <strong>{}</strong>.', number_format(totales['promedio'], 2),
        )})

    faltas = Asistencia.objects.filter(
        estudiante=estudiante, estado=Asistencia.Estado.FALTA,
    ).count()
    if faltas:
        avisos.append({'tono': 'atencion', 'texto': format_html(
            'Acumulas <strong>{} falta{}</strong> este año.', faltas, '' if faltas == 1 else 's',
        )})

    return avisos


def para_padre(hijos):
    """Lo que un padre necesita saber, nombrando a cada hijo."""
    avisos = []
    for hijo in hijos:
        nombre = hijo.usuario.first_name or hijo.usuario.get_full_name()

        citacion = (
            Citacion.objects.filter(estudiante=hijo, estado=Citacion.Estado.PENDIENTE)
            .order_by('fecha').first()
        )
        if citacion is not None:
            hora = f' a las {citacion.hora:%H:%M}' if citacion.hora else ''
            avisos.append({'tono': 'urgente', 'texto': format_html(
                'La citaron por <strong>{}</strong> {}{} en {}.',
                nombre, _fecha_legible(citacion.fecha), hora, citacion.lugar or 'el colegio',
            )})

        matricula = _matricula_activa(hijo)
        if matricula is not None:
            tareas = Tarea.objects.filter(
                asignacion__curso=matricula.curso,
                fecha_entrega__gte=timezone.localdate(),
            )
            entregadas = set(
                EntregaTarea.objects.filter(
                    estudiante=hijo, tarea__in=tareas,
                    estado__in=[EntregaTarea.Estado.ENTREGADA, EntregaTarea.Estado.ATRASADA],
                ).values_list('tarea_id', flat=True)
            )
            pendientes = [t for t in tareas if t.pk not in entregadas]
            if pendientes:
                avisos.append({'tono': 'atencion', 'texto': format_html(
                    '<strong>{}</strong> tiene <strong>{} tarea{} sin entregar</strong>.',
                    nombre, len(pendientes), '' if len(pendientes) == 1 else 's',
                )})

        faltas = Asistencia.objects.filter(estudiante=hijo, estado=Asistencia.Estado.FALTA).count()
        if faltas >= 3:
            avisos.append({'tono': 'urgente', 'texto': format_html(
                '<strong>{}</strong> acumula <strong>{} faltas</strong>. Conviene hablar con la dirección.',
                nombre, faltas,
            )})

    if not avisos:
        avisos.append({'tono': 'bien', 'texto': format_html(
            'Todo en orden: sin citaciones pendientes ni tareas atrasadas.',
        )})
    return avisos


def para_direccion(gestion):
    """El pulso del colegio hoy, para el administrador."""
    from apps.asistencia.services import cursos_en_capacitacion, matriculas_del_dia

    avisos = []
    hoy = timezone.localdate()
    if gestion is None:
        return avisos

    esperados = matriculas_del_dia(gestion, hoy).count()
    registros = list(Asistencia.objects.filter(fecha=hoy))
    presentes = sum(1 for a in registros if a.estado == Asistencia.Estado.PRESENTE)
    atrasos = sum(1 for a in registros if a.estado == Asistencia.Estado.ATRASO)
    faltas = sum(1 for a in registros if a.estado == Asistencia.Estado.FALTA)

    if esperados:
        avisos.append({'tono': 'bien' if faltas == 0 else 'atencion', 'texto': format_html(
            'Han entrado <strong>{} de {}</strong> estudiantes. '
            '<strong>{}</strong> atraso{} y <strong>{}</strong> falta{}.',
            presentes + atrasos, esperados,
            atrasos, '' if atrasos == 1 else 's',
            faltas, '' if faltas == 1 else 's',
        )})

    en_capacitacion = list(cursos_en_capacitacion(hoy).filter(gestion=gestion))
    if en_capacitacion:
        sin_registrar = [
            curso for curso in en_capacitacion
            if not Asistencia.objects.filter(
                fecha=hoy, estudiante__matriculas__curso=curso,
                estudiante__matriculas__activa=True,
            ).exists()
        ]
        nombres = ', '.join(str(c) for c in (sin_registrar or en_capacitacion))
        if sin_registrar:
            avisos.append({'tono': 'atencion', 'texto': format_html(
                '<strong>{}</strong> está en capacitación: falta registrar su asistencia.', nombres,
            )})
        else:
            avisos.append({'tono': 'bien', 'texto': format_html(
                'La asistencia de capacitación de <strong>{}</strong> ya está registrada.', nombres,
            )})

    pendientes = Citacion.objects.filter(estado=Citacion.Estado.PENDIENTE).count()
    if pendientes:
        # "citación" pierde la tilde en plural: citaciones, no "citaciónes"
        palabra = 'citación pendiente' if pendientes == 1 else 'citaciones pendientes'
        avisos.append({'tono': 'urgente', 'texto': format_html(
            'Hay <strong>{} {}</strong> de atender.', pendientes, palabra,
        )})

    return avisos


def para_regente(gestion):
    """Cómo va la puerta hoy."""
    avisos = []
    if gestion is None:
        return avisos

    from apps.asistencia.services import cursos_en_capacitacion, hora_limite, matriculas_del_dia

    hoy = timezone.localdate()
    esperados = matriculas_del_dia(gestion, hoy).count()
    registrados = Asistencia.objects.filter(fecha=hoy).count()
    faltan = max(0, esperados - registrados)

    if faltan:
        avisos.append({'tono': 'atencion', 'texto': format_html(
            'Faltan <strong>{} estudiante{}</strong> por registrar de {} esperados.',
            faltan, '' if faltan == 1 else 's', esperados,
        )})
    elif esperados:
        avisos.append({'tono': 'bien', 'texto': format_html(
            'Los <strong>{}</strong> estudiantes de hoy ya están registrados.', esperados,
        )})

    en_capacitacion = list(cursos_en_capacitacion(hoy).filter(gestion=gestion))
    if en_capacitacion:
        avisos.append({'tono': 'dato', 'texto': format_html(
            'Hoy no pasan por la puerta: <strong>{}</strong>. Su asistencia la registra la administración.',
            ', '.join(str(c) for c in en_capacitacion),
        )})

    # La hora se formatea antes: format_html escapa los argumentos primero y
    # un especificador de fecha sobre el texto ya escapado revienta.
    avisos.append({'tono': 'dato', 'texto': format_html(
        'Después de las <strong>{}</strong> la entrada se marca como atraso.',
        hora_limite().strftime('%H:%M'),
    )})
    return avisos
