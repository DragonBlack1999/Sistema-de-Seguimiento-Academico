"""Lo que un docente necesita ver al entrar.

Hasta ahora su panel era un saludo y una tabla con los nombres de sus materias:
todo lo que decía ya lo sabía de memoria. Lo que no sabe de memoria —y lo que
va a buscar— es qué clases le tocan hoy, qué quedó sin calificar y cómo va cada
uno de sus cursos.

Las consultas van agrupadas a propósito. Trece de los 33 docentes dictan dos o
tres materias en varios cursos; preguntando por asignación, un docente con ocho
cursos haría cuarenta consultas para dibujar una pantalla.
"""
from django.db.models import Count
from django.utils.html import format_html

from apps.academico import clases
from apps.academico.models import AsignacionDocente, Matricula
from apps.calificaciones.models import NOTA_APROBACION, Nota
from apps.tareas.models import EntregaTarea, Tarea
from apps.tareas.notas import sin_calificar


def clases_de_hoy(profesor, fecha):
    """Las clases que dicta hoy, en el orden en que las dicta."""
    return clases.del_dia(fecha, profesor=profesor)


def _trimestre_en_curso(trimestres_con_notas):
    """El trimestre más avanzado que ya tiene algo cargado.

    El colegio no guarda en ningún lado en qué trimestre está: se deduce de
    dónde hay notas. Es más fiel que una fecha fija, porque un docente puede ir
    adelantado o atrasado respecto del calendario.
    """
    return max(trimestres_con_notas) if trimestres_con_notas else 1


def resumen_de_cursos(profesor):
    """Una fila por materia que dicta, con cómo va.

    Cuatro consultas en total, no cuatro por curso.
    """
    asignaciones = list(
        AsignacionDocente.objects
        .filter(profesor=profesor)
        .select_related('curso__gestion', 'materia')
        .order_by('curso__nivel', 'curso__grado', 'curso__paralelo', 'materia__nombre')
    )
    if not asignaciones:
        return []

    ids = [a.pk for a in asignaciones]
    cursos = {a.curso_id for a in asignaciones}

    matriculados = dict(
        Matricula.objects.filter(curso_id__in=cursos, activa=True)
        .values_list('curso_id').annotate(cuantos=Count('id'))
    )

    # Las notas de un trimestre son una fila por estudiante, así que el
    # promedio y los reprobados salen de la misma consulta.
    por_asignacion = {}
    for fila in (Nota.objects.calificadas().filter(asignacion_id__in=ids)
                 .values('asignacion_id', 'trimestre', 'nota')):
        if fila['nota'] is None:
            continue
        por_asignacion.setdefault(fila['asignacion_id'], {}).setdefault(
            fila['trimestre'], []).append(float(fila['nota']))

    esperando = dict(
        sin_calificar(EntregaTarea.objects.filter(
            tarea__asignacion_id__in=ids,
            estado__in=[EntregaTarea.Estado.ENTREGADA, EntregaTarea.Estado.ATRASADA],
        )).values_list('tarea__asignacion_id').annotate(cuantas=Count('id'))
    )

    tareas = dict(
        Tarea.objects.filter(asignacion_id__in=ids)
        .values_list('asignacion_id').annotate(cuantas=Count('id'))
    )

    filas = []
    for asignacion in asignaciones:
        notas_por_trimestre = por_asignacion.get(asignacion.pk, {})
        trimestre = _trimestre_en_curso(notas_por_trimestre.keys())
        notas = notas_por_trimestre.get(trimestre, [])
        filas.append({
            'asignacion': asignacion,
            'estudiantes': matriculados.get(asignacion.curso_id, 0),
            'trimestre': trimestre,
            'calificados': len(notas),
            'promedio': round(sum(notas) / len(notas), 1) if notas else None,
            'reprobando': sum(1 for n in notas if n < NOTA_APROBACION),
            'esperando': esperando.get(asignacion.pk, 0),
            'tareas': tareas.get(asignacion.pk, 0),
        })
    return filas


def avisos_para(filas, clases_hoy):
    """Las frases de arriba: lo que le está esperando, en orden de urgencia."""
    avisos = []

    esperando = sum(fila['esperando'] for fila in filas)
    if esperando:
        avisos.append({'tono': 'urgente', 'texto': format_html(
            'Tienes <strong>{} entrega{}</strong> esperando calificación.',
            esperando, '' if esperando == 1 else 's',
        )})

    # Materias en las que no cargó ninguna nota todavía: es lo que se olvida,
    # y el docente no lo ve mirando su lista de materias.
    sin_nada = [fila for fila in filas if fila['calificados'] == 0 and fila['estudiantes']]
    if sin_nada:
        avisos.append({'tono': 'atencion', 'texto': format_html(
            'Todavía sin ninguna nota cargada: <strong>{}</strong>.',
            _agrupar_por_materia(sin_nada),
        )})

    reprobando = sum(fila['reprobando'] for fila in filas)
    if reprobando:
        avisos.append({'tono': 'atencion', 'texto': format_html(
            '<strong>{} estudiante{}</strong> por debajo de {} en lo que llevas cargado.',
            reprobando, '' if reprobando == 1 else 's', NOTA_APROBACION,
        )})

    if clases_hoy:
        avisos.append({'tono': 'bien', 'texto': format_html(
            'Hoy dictas <strong>{} clase{}</strong>.',
            len(clases_hoy), '' if len(clases_hoy) == 1 else 's',
        )})
    else:
        # Sin nada que interpolar no se usa format_html: sin argumentos
        # revienta, y ya tumbó una pantalla de este proyecto una vez.
        avisos.append({'tono': 'info', 'texto': 'Hoy no tienes clases en el horario.'})

    return avisos


def _curso_corto(curso):
    """«1° de Secundaria "B" (2026)» -> «1° B», que es como lo nombran."""
    return f'{curso.grado}° {curso.paralelo}'


def _agrupar_por_materia(filas):
    """«Educación Musical en 1° B, 1° C, 2° A y 9 más».

    Agrupado y no fila por fila: diecisiete de los 33 docentes dictan la misma
    materia en varios cursos, y repetir su nombre doce veces convierte el aviso
    en algo que ya no se lee.
    """
    por_materia = {}
    for fila in filas:
        por_materia.setdefault(str(fila['asignacion'].materia), []).append(
            _curso_corto(fila['asignacion'].curso))

    partes = []
    for materia, cursos in list(por_materia.items())[:2]:
        visibles = ', '.join(cursos[:3])
        resto = len(cursos) - 3
        partes.append(f'{materia} en {visibles}' + (f' y {resto} más' if resto > 0 else ''))

    otras = len(por_materia) - 2
    if otras > 0:
        partes.append(f'y {otras} materia{"" if otras == 1 else "s"} más')
    return '; '.join(partes)
