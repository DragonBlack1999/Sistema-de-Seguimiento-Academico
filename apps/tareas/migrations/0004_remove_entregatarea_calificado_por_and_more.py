"""La nota de una tarea deja de estar en la entrega: vive en su puntaje.

Antes de borrar la columna se rescata lo que hubiera: si alguna entrega tenía
nota y su columna no, se crea el puntaje. Así la normalización no pierde nada
aunque las dos copias hubieran quedado distintas.
"""
from django.db import migrations


def rescatar_notas(apps, schema_editor):
    EntregaTarea = apps.get_model('tareas', 'EntregaTarea')
    Puntaje = apps.get_model('calificaciones', 'Puntaje')
    Nota = apps.get_model('calificaciones', 'Nota')

    rescatadas = 0
    tocados = set()
    for entrega in (
        EntregaTarea.objects.filter(nota__isnull=False, tarea__actividad__isnull=False)
        .select_related('tarea')
    ):
        _, creado = Puntaje.objects.get_or_create(
            actividad_id=entrega.tarea.actividad_id, estudiante_id=entrega.estudiante_id,
            defaults={'valor': entrega.nota},
        )
        if creado:
            rescatadas += 1
            tocados.add((entrega.tarea.asignacion_id, entrega.tarea.trimestre, entrega.estudiante_id))

    # El nombre de la columna de una tarea ahora lo pone la tarea: la copia sobra.
    Actividad = apps.get_model('calificaciones', 'Actividad')
    Actividad.objects.filter(tarea__isnull=False).update(nombre='')

    if not tocados:
        return
    # Lo que se haya rescatado cambia el promedio de "hacer": se rehace la nota.
    from decimal import ROUND_HALF_UP, Decimal

    for asignacion_id, trimestre, estudiante_id in tocados:
        nota, _ = Nota.objects.get_or_create(
            asignacion_id=asignacion_id, estudiante_id=estudiante_id, trimestre=trimestre,
        )
        promedios = {}
        for puntaje in Puntaje.objects.filter(
            estudiante_id=estudiante_id,
            actividad__asignacion_id=asignacion_id, actividad__trimestre=trimestre,
        ).select_related('actividad'):
            promedios.setdefault(puntaje.actividad.dimension, []).append(puntaje.valor)

        for dimension, campo in [('SER', 'ser'), ('SABER', 'saber'), ('HACER', 'hacer')]:
            valores = promedios.get(dimension)
            setattr(nota, campo, (sum(valores) / len(valores)).quantize(
                Decimal('1'), rounding=ROUND_HALF_UP) if valores else None)
        suma = sum(
            v for v in (nota.ser, nota.saber, nota.hacer, nota.autoevaluacion, nota.extracurricular)
            if v is not None
        )
        nota.nota = min(Decimal('100'), Decimal(suma))
        nota.save()


def sin_vuelta(apps, schema_editor):
    """Al revés no hay nada que hacer: la nota queda en el puntaje, que no se toca."""


class Migration(migrations.Migration):

    dependencies = [
        ('tareas', '0003_tareas_en_la_planilla'),
        ('calificaciones', '0003_alter_actividad_nombre_nota_nota_en_rango_and_more'),
    ]

    operations = [
        migrations.RunPython(rescatar_notas, sin_vuelta),
        migrations.RemoveField(
            model_name='entregatarea',
            name='calificado_por',
        ),
        migrations.RemoveField(
            model_name='entregatarea',
            name='fecha_calificacion',
        ),
        migrations.RemoveField(
            model_name='entregatarea',
            name='nota',
        ),
    ]
