"""Armar trimestres de ejemplo, para los comandos de datos de prueba.

Solo lo usan los `seed_*`: el sistema real carga las notas desde la planilla del
docente. Vive aquí, y no dentro de un comando, porque son tres los comandos que
necesitan lo mismo y los tres tienen que producir notas con su desglose. Una
nota sin desglose no cuenta como calificada y no se vería en ningún lado.
"""
from decimal import Decimal

from .models import MAXIMO, Actividad, Dimension, Nota, Puntaje

# Dos actividades por dimensión: una planilla con una sola columna no se parece
# a la del colegio y no deja ver cómo se promedia.
ACTIVIDADES = {
    Dimension.SER: ['Participación', 'Puntualidad'],
    Dimension.SABER: ['Examen', 'Práctico'],
    Dimension.HACER: ['Trabajo en aula', 'Investigación'],
}


def actividades_de(asignacion, trimestre, creada_por=None):
    """Crea (una vez) las actividades de ejemplo de esa materia y trimestre."""
    creadas = []
    for dimension, nombres in ACTIVIDADES.items():
        for orden, nombre in enumerate(nombres):
            actividad, _ = Actividad.objects.get_or_create(
                asignacion=asignacion, trimestre=trimestre, dimension=dimension, orden=orden,
                defaults={'nombre': nombre, 'creada_por': creada_por},
            )
            creadas.append(actividad)
    return creadas


def cargar_trimestre(asignacion, estudiante, trimestre, total, azar, registrado_por=None):
    """Reparte un total (0 a 100) entre las dimensiones y guarda la nota.

    Cada dimensión recibe la parte que le toca del total, y sus dos actividades
    quedan una encima y otra debajo de esa parte, para que el promedio dé justo.
    """
    total = Decimal(total)
    actividades = actividades_de(asignacion, trimestre, creada_por=registrado_por)
    proporcion = total / Decimal('100')

    for actividad in actividades:
        maximo = MAXIMO[Dimension(actividad.dimension)]
        objetivo = maximo * proporcion
        diferencia = Decimal(azar.uniform(0.5, 2.5)).quantize(Decimal('0.01'))
        if actividad.orden == 1:
            diferencia = -diferencia
        valor = min(maximo, max(Decimal('0'), (objetivo + diferencia).quantize(Decimal('0.01'))))
        Puntaje.objects.update_or_create(
            actividad=actividad, estudiante=estudiante,
            defaults={'valor': valor, 'registrado_por': registrado_por or asignacion.profesor},
        )

    nota, _ = Nota.objects.get_or_create(
        asignacion=asignacion, estudiante=estudiante, trimestre=trimestre,
    )
    # La autoevaluación también sale del total buscado, si no las notas de
    # ejemplo quedarían siempre unos puntos por encima de lo previsto.
    from .models import MAXIMO_AUTOEVALUACION
    # Al medio punto más cercano, que es como se pone una autoevaluación.
    nota.autoevaluacion = (MAXIMO_AUTOEVALUACION * proporcion * 2).quantize(Decimal('1')) / 2
    nota.autoevaluacion_por = None          # en la demo nadie la puso en particular
    nota.extracurricular = Decimal(azar.choice([0, 0, 0, 1, 2]))
    nota.registrado_por = registrado_por or asignacion.profesor
    nota.recalcular()
    return nota
