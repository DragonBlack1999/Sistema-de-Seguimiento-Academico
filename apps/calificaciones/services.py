"""Consultas de notas compartidas por las vistas del estudiante, del padre, del boletín y del Excel."""

from apps.academico.models import Matricula

from .models import NOTA_APROBACION, Nota, redondear


def gestion_actual(estudiante):
    """Gestión vigente del estudiante: su matrícula activa, o la más reciente que tenga."""
    base = Matricula.objects.filter(estudiante=estudiante).select_related('curso__gestion')

    matricula = base.filter(activa=True).order_by('-curso__gestion__anio').first()
    if matricula is None:
        matricula = base.order_by('-curso__gestion__anio').first()
    if matricula is not None:
        return matricula.gestion

    # Sin ninguna matrícula: la gestión más reciente en la que tenga notas.
    nota = (
        Nota.objects.calificadas().filter(estudiante=estudiante)
        .select_related('asignacion__curso__gestion').order_by('-asignacion__curso__gestion__anio').first()
    )
    return nota.asignacion.gestion if nota else None


def notas_de_gestion(estudiante, gestion=None):
    """Notas de **una sola** gestión, ya calificadas.

    Sin el filtro por gestión, un estudiante con historial de años anteriores
    mezcla ambos años en la misma tabla: `pivotar_notas` agrupa por nombre de
    materia, así que "Matemática 2025" y "Matemática 2026" caen en la misma fila
    y gana la última leída — mostrando el año equivocado sin ningún aviso.

    `calificadas()` deja fuera las materias donde lo único cargado es la
    autoevaluación que se puso el propio estudiante: todavía no son una nota.
    """
    if gestion is None:
        gestion = gestion_actual(estudiante)

    notas = Nota.objects.calificadas().filter(estudiante=estudiante).select_related('asignacion__materia')
    if gestion is not None:
        notas = notas.filter(asignacion__curso__gestion=gestion)
    return notas


def pivotar_notas(notas):
    """Agrupa una lista/queryset de Nota por materia y calcula promedios y totales.

    Vive aquí y no en una vista porque la usan «Mis notas», el padre, el inicio
    y el Excel de notas por curso: todos tienen que dar el mismo número.

    Cada fila trae además `detalle`, con la Nota de cada trimestre, para poder
    mostrar de qué se compone (ser, saber, hacer, autoevaluación y extra).
    """
    por_materia = {}
    detalles = {}
    for nota in notas:
        materia = nota.asignacion.materia.nombre
        por_materia.setdefault(materia, {})[nota.trimestre] = nota.nota
        detalles.setdefault(materia, {})[nota.trimestre] = nota

    filas = []
    columnas_trimestre = {1: [], 2: [], 3: []}
    todas_las_notas = []
    for materia, trimestres in sorted(por_materia.items()):
        valores = list(trimestres.values())
        promedio = sum(valores) / len(valores) if valores else None
        for t in (1, 2, 3):
            if t in trimestres:
                columnas_trimestre[t].append(trimestres[t])
        todas_las_notas.extend(valores)
        filas.append({
            'materia': materia,
            't1': trimestres.get(1, '-'),
            't2': trimestres.get(2, '-'),
            't3': trimestres.get(3, '-'),
            'promedio': redondear(promedio) if promedio is not None else '-',
            'aprobado': promedio is not None and promedio >= NOTA_APROBACION,
            'detalle': [detalles[materia].get(t) for t in (1, 2, 3)],
        })

    totales = None
    if filas:
        totales = {
            't1': redondear(sum(columnas_trimestre[1]) / len(columnas_trimestre[1])) if columnas_trimestre[1] else '-',
            't2': redondear(sum(columnas_trimestre[2]) / len(columnas_trimestre[2])) if columnas_trimestre[2] else '-',
            't3': redondear(sum(columnas_trimestre[3]) / len(columnas_trimestre[3])) if columnas_trimestre[3] else '-',
            'promedio': redondear(sum(todas_las_notas) / len(todas_las_notas)) if todas_las_notas else '-',
        }

    return filas, totales
