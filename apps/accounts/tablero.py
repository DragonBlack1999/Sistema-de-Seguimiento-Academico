"""Cálculos del tablero de dirección.

Criterio de qué entra aquí: solo lo que lleva a una decisión. Contar mensajes o
noticias no le sirve al director para nada; saber qué estudiantes se están
quedando atrás, en qué materia y desde cuándo, sí.

Los cuatro bloques son:
  1. Estudiantes que necesitan atención  (a quién llamar)
  2. Rendimiento por materia             (dónde reforzar)
  3. Asistencia de las últimas semanas   (si empeora)
  4. Pendientes de gestión               (qué está trabado)
"""

import datetime
from collections import Counter, defaultdict

from django.db.models import Avg, Count, Exists, OuterRef
from django.utils import timezone

from apps.academico.models import AsignacionDocente, Curso, Matricula
from apps.asistencia.models import Asistencia
from apps.asistencia.services import DIA_POR_WEEKDAY
from apps.calificaciones.models import NOTA_APROBACION, Nota
from apps.comunicaciones.models import Citacion
from apps.tareas.models import EntregaTarea
from apps.tareas.pendientes import tareas_vencidas_sin_entregar

DIAS_DE_TENDENCIA = 24          # cuatro semanas de clase, de lunes a sábado
LIMITE_ATENCION = 8             # cuántos estudiantes se listan


def _dias_de_clase(hasta, cantidad):
    # Los mismos días que la puerta: el sábado se controla asistencia.
    dias, fecha = [], hasta
    while len(dias) < cantidad:
        if fecha.weekday() in DIA_POR_WEEKDAY:
            dias.append(fecha)
        fecha -= datetime.timedelta(days=1)
    return sorted(dias)


def necesitan_atencion(gestion):
    """Estudiantes ordenados por cuánta atención necesitan.

    Se combinan cuatro señales en una sola puntuación para poder ordenarlas
    juntas. Los pesos son un criterio, no una fórmula sagrada: una citación
    pendiente pesa más que una tarea sin entregar porque ya hubo una decisión
    humana detrás.
    """
    filas = []
    matriculas = (
        Matricula.objects.filter(activa=True, curso__gestion=gestion)
        .select_related('estudiante__usuario', 'curso__gestion')
    )

    faltas_por_estudiante = dict(Asistencia.objects.filter(
        fecha__year=gestion.anio, estado=Asistencia.Estado.FALTA,
    ).values_list('estudiante_id').annotate(total=Count('pk')))
    citaciones_por_estudiante = dict(Citacion.objects.filter(
        estado=Citacion.Estado.PENDIENTE,
    ).values_list('estudiante_id').annotate(total=Count('pk')))

    materias_reprobadas = defaultdict(list)
    promedios_bajos = (
        Nota.objects.calificadas().filter(asignacion__curso__gestion=gestion)
        .values('estudiante_id', 'asignacion__materia__nombre')
        .annotate(promedio=Avg('nota')).filter(promedio__lt=NOTA_APROBACION)
        .order_by('asignacion__materia__nombre')
    )
    for fila in promedios_bajos:
        materias_reprobadas[fila['estudiante_id']].append(fila['asignacion__materia__nombre'])

    pendientes = Counter(m.pk for m, _ in tareas_vencidas_sin_entregar(gestion, matriculas))
    for matricula in matriculas:
        estudiante = matricula.estudiante
        faltas = faltas_por_estudiante.get(estudiante.pk, 0)
        citaciones = citaciones_por_estudiante.get(estudiante.pk, 0)
        reprobadas = materias_reprobadas[estudiante.pk]
        sin_entregar = pendientes[matricula.pk]

        puntos = faltas * 2 + len(reprobadas) * 5 + citaciones * 6 + sin_entregar * 2
        if puntos == 0:
            continue

        filas.append({
            'estudiante': estudiante,
            'curso': matricula.curso,
            'faltas': faltas,
            'reprobadas': reprobadas,
            'citaciones': citaciones,
            'sin_entregar': sin_entregar,
            'puntos': puntos,
        })

    filas.sort(key=lambda f: -f['puntos'])
    return filas[:LIMITE_ATENCION], len(filas)


def rendimiento_por_materia(gestion):
    """Promedio de cada materia, para ver dónde hay que reforzar."""
    datos = (
        Nota.objects.calificadas().filter(asignacion__curso__gestion=gestion)
        .values('asignacion__materia__nombre')
        .annotate(promedio=Avg('nota'), cuantas=Count('id'))
        .order_by('promedio')
    )
    estudiantes = Counter()
    reprobados = Counter()
    por_estudiante = (
        Nota.objects.calificadas().filter(asignacion__curso__gestion=gestion)
        .values('asignacion__materia__nombre', 'estudiante_id').annotate(promedio=Avg('nota'))
    )
    for registro in por_estudiante:
        materia = registro['asignacion__materia__nombre']
        estudiantes[materia] += 1
        if registro['promedio'] < NOTA_APROBACION:
            reprobados[materia] += 1
    filas = []
    for fila in datos:
        promedio = float(fila['promedio'])
        materia = fila['asignacion__materia__nombre']
        filas.append({
            'materia': fila['asignacion__materia__nombre'],
            'promedio': round(promedio, 1),
            'porcentaje': round(promedio),          # la escala es 0-100, sirve de ancho
            'notas': fila['cuantas'],
            'estudiantes': estudiantes[materia],
            'reprobados': reprobados[materia],
            'aprueba': promedio >= NOTA_APROBACION,
        })
    return filas


def asistencia_por_dia(gestion, dias=DIAS_DE_TENDENCIA):
    """Serie diaria de las últimas semanas, desglosada por estado."""
    hoy = timezone.localdate()
    fechas = _dias_de_clase(hoy, dias)

    registros = (
        Asistencia.objects.filter(fecha__in=fechas)
        .values('fecha', 'estado').annotate(n=Count('id'))
    )
    por_fecha = {}
    for r in registros:
        por_fecha.setdefault(r['fecha'], {})[r['estado']] = r['n']

    serie = []
    for fecha in fechas:
        conteo = por_fecha.get(fecha, {})
        presentes = conteo.get(Asistencia.Estado.PRESENTE, 0)
        atrasos = conteo.get(Asistencia.Estado.ATRASO, 0)
        faltas = conteo.get(Asistencia.Estado.FALTA, 0)
        licencias = conteo.get(Asistencia.Estado.LICENCIA, 0)
        total = presentes + atrasos + faltas + licencias
        serie.append({
            'fecha': fecha,
            'presentes': presentes, 'atrasos': atrasos,
            'faltas': faltas, 'licencias': licencias,
            'total': total,
            # Alturas en porcentaje: es lo que dibuja la barra apilada
            'alto_presentes': round(presentes / total * 100) if total else 0,
            'alto_atrasos': round(atrasos / total * 100) if total else 0,
            'alto_faltas': round(faltas / total * 100) if total else 0,
            'alto_licencias': round(licencias / total * 100) if total else 0,
            'asistio': round((presentes + atrasos) / total * 100) if total else 0,
        })
    return serie


def pendientes(gestion):
    """Lo que está trabado y alguien tiene que destrabar."""
    hoy = timezone.localdate()
    lista = []

    from apps.tareas.notas import sin_calificar as entregas_sin_calificar

    pendientes_de_calificar = (
        entregas_sin_calificar(EntregaTarea.objects.filter(
            estado__in=[EntregaTarea.Estado.ENTREGADA, EntregaTarea.Estado.ATRASADA],
            tarea__asignacion__curso__gestion=gestion,
        ))
        .values('tarea__asignacion__profesor__first_name', 'tarea__asignacion__profesor__last_name')
        .annotate(n=Count('id')).order_by('-n')
    )
    for fila in pendientes_de_calificar:
        nombre = f"{fila['tarea__asignacion__profesor__first_name']} {fila['tarea__asignacion__profesor__last_name']}".strip()
        lista.append({
            'tono': 'atencion',
            'texto': f"{nombre} tiene {fila['n']} entrega(s) sin calificar.",
            'url_nombre': None,
        })

    citaciones = Citacion.objects.filter(estado=Citacion.Estado.PENDIENTE).count()
    if citaciones:
        palabra = 'citación pendiente' if citaciones == 1 else 'citaciones pendientes'
        lista.append({'tono': 'urgente', 'texto': f'Hay {citaciones} {palabra} de atender.',
                      'url_nombre': 'comunicaciones:lista_citaciones'})

    # Cursos sin ninguna nota registrada este año
    cursos = Curso.objects.filter(gestion=gestion).filter(
        Exists(Matricula.objects.filter(curso=OuterRef('pk'), activa=True))
    ).select_related('gestion').annotate(
        tiene_notas=Exists(Nota.objects.calificadas().filter(asignacion__curso=OuterRef('pk'))),
        tiene_horario=Exists(AsignacionDocente.objects.filter(curso=OuterRef('pk'), horarios__isnull=False)),
    )
    sin_notas = [str(curso) for curso in cursos if not curso.tiene_notas]
    if sin_notas:
        lista.append({'tono': 'atencion',
                      'texto': f"Sin notas registradas todavía: {', '.join(sin_notas)}.",
                      'url_nombre': None})

    # Cursos sin horario armado
    sin_horario = [str(curso) for curso in cursos if not curso.tiene_horario]
    if sin_horario:
        lista.append({'tono': 'dato',
                      'texto': f"Sin horario armado: {', '.join(sin_horario)}.",
                      'url_nombre': 'academico:horario_constructor'})

    # Días de clase sin asistencia registrada: la última semana, sábado incluido
    fechas = _dias_de_clase(hoy, 6)
    con_registro = set(
        Asistencia.objects.filter(fecha__in=fechas).values_list('fecha', flat=True)
    )
    faltantes = [f for f in fechas if f not in con_registro]
    if faltantes:
        lista.append({
            'tono': 'urgente',
            'texto': f"Sin asistencia registrada: {', '.join(f.strftime('%d/%m') for f in faltantes)}.",
            'url_nombre': 'asistencia:puerta',
        })

    if not lista:
        lista.append({'tono': 'bien', 'texto': 'Nada pendiente: todo al día.', 'url_nombre': None})
    return lista


def cifras(gestion):
    """Las cuatro cifras de cabecera, cada una con su lectura."""
    matriculas = Matricula.objects.filter(activa=True, curso__gestion=gestion)
    total = matriculas.count()

    notas = Nota.objects.calificadas().filter(asignacion__curso__gestion=gestion)
    promedio = notas.aggregate(p=Avg('nota'))['p']

    hoy = timezone.localdate()
    fechas = _dias_de_clase(hoy, DIAS_DE_TENDENCIA)
    registros = Asistencia.objects.filter(fecha__in=fechas)
    asistidos = registros.filter(
        estado__in=[Asistencia.Estado.PRESENTE, Asistencia.Estado.ATRASO]
    ).count()
    tasa = round(asistidos / registros.count() * 100) if registros.count() else None

    por_estudiante = notas.values('estudiante').annotate(p=Avg('nota'))
    reprobando = sum(1 for e in por_estudiante if e['p'] < NOTA_APROBACION)

    return {
        'estudiantes': total,
        'promedio': round(float(promedio), 1) if promedio is not None else None,
        'asistencia': tasa,
        'reprobando': reprobando,
    }
