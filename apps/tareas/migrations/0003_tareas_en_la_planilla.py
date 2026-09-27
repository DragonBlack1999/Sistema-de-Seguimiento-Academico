"""Las tareas que ya existan pasan a ser columnas de «hacer».

Las notas de entrega venían sobre 100 y ahora van sobre 40, así que se escalan.
En la base del colegio todavía no hay ninguna tarea, así que ahí no cambia nada:
esto es para las copias de demostración y para no perder datos si alguien ya
había cargado tareas.
"""
from decimal import ROUND_HALF_UP, Decimal

from django.db import migrations

MAXIMOS = {'SER': Decimal('10'), 'SABER': Decimal('45'), 'HACER': Decimal('40')}
NOTA_MAXIMA = Decimal('100')


def _entero(valor):
    return None if valor is None else Decimal(valor).quantize(Decimal('1'), rounding=ROUND_HALF_UP)


def llevar_a_la_planilla(apps, schema_editor):
    Tarea = apps.get_model('tareas', 'Tarea')
    EntregaTarea = apps.get_model('tareas', 'EntregaTarea')
    Actividad = apps.get_model('calificaciones', 'Actividad')
    Puntaje = apps.get_model('calificaciones', 'Puntaje')
    Nota = apps.get_model('calificaciones', 'Nota')

    tocados = set()
    for tarea in Tarea.objects.all():
        if tarea.actividad_id is None:
            ultimo = (
                Actividad.objects
                .filter(asignacion_id=tarea.asignacion_id, trimestre=tarea.trimestre, dimension='HACER')
                .order_by('-orden').values_list('orden', flat=True).first()
            )
            actividad = Actividad.objects.create(
                asignacion_id=tarea.asignacion_id, trimestre=tarea.trimestre,
                dimension='HACER', nombre=tarea.titulo[:60],
                orden=0 if ultimo is None else ultimo + 1,
            )
            tarea.actividad = actividad
            tarea.save(update_fields=['actividad'])

        for entrega in EntregaTarea.objects.filter(tarea=tarea, nota__isnull=False):
            # Lo que estaba sobre 100 pasa a la escala de la dimensión.
            valor = entrega.nota
            if valor > MAXIMOS['HACER']:
                valor = _entero(valor * MAXIMOS['HACER'] / NOTA_MAXIMA)
            else:
                valor = _entero(valor)
            if valor != entrega.nota:
                entrega.nota = valor
                entrega.save(update_fields=['nota'])
            Puntaje.objects.update_or_create(
                actividad_id=tarea.actividad_id, estudiante_id=entrega.estudiante_id,
                defaults={'valor': valor},
            )
            tocados.add((tarea.asignacion_id, tarea.trimestre, entrega.estudiante_id))

    # Las notas de quienes recibieron puntajes se rehacen con la misma cuenta
    # que hace `Nota.recalcular()`, que aquí no está disponible.
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
            setattr(nota, campo, _entero(sum(valores) / len(valores)) if valores else None)

        suma = sum(
            v for v in (nota.ser, nota.saber, nota.hacer, nota.autoevaluacion, nota.extracurricular)
            if v is not None
        )
        nota.nota = _entero(min(NOTA_MAXIMA, Decimal(suma)))
        nota.save()


def deshacer(apps, schema_editor):
    """Se quitan las columnas creadas; las notas de entrega quedan sobre 40."""
    Tarea = apps.get_model('tareas', 'Tarea')
    Actividad = apps.get_model('calificaciones', 'Actividad')
    ids = [t.actividad_id for t in Tarea.objects.filter(actividad__isnull=False)]
    Tarea.objects.update(actividad=None)
    Actividad.objects.filter(pk__in=ids).delete()


class Migration(migrations.Migration):
    dependencies = [
        ('tareas', '0002_remove_tarea_peso_tarea_actividad_and_more'),
        ('calificaciones', '0002_nota_autoevaluacion_nota_autoevaluacion_por_and_more'),
    ]

    operations = [
        migrations.RunPython(llevar_a_la_planilla, deshacer),
    ]
