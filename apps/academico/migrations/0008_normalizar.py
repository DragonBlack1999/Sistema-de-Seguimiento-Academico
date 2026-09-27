"""Normalización: se eliminan las columnas redundantes.

Qué desaparece y por qué:
  - `Estudiante.nombre_tutor/ci_tutor/telefono_tutor/email_tutor`: eran una copia
    de los datos del `Usuario` del tutor. Dos hermanos guardaban lo mismo dos
    veces, y editar la ficha de uno dejaba la del otro desactualizada.
  - `Estudiante.curso_actual`: lo determina la matrícula activa. Cuando ambos
    discrepaban, el estudiante no aparecía en tareas ni podía escribir a sus
    profesores.
  - `Matricula.gestion` y `AsignacionDocente.gestion`: el curso ya identifica su
    año, así que nada impedía que dijeran años distintos.
  - `Horario.hora_inicio/hora_fin`: ahora apuntan al `Periodo`, que es donde vive
    la hora. Antes 4 de 7 clases no correspondían a ninguna fila de la grilla.

El paso previo `vincular_horarios_a_periodos` empareja cada horario con su
período por hora exacta; los períodos que faltaban se crearon antes de migrar.
"""

import django.db.models.deletion
from django.db import migrations, models


def vincular_horarios_a_periodos(apps, schema_editor):
    Horario = apps.get_model('academico', 'Horario')
    Periodo = apps.get_model('academico', 'Periodo')

    huerfanos = []
    for horario in Horario.objects.select_related('asignacion'):
        periodo = Periodo.objects.filter(
            curso_id=horario.asignacion.curso_id,
            hora_inicio=horario.hora_inicio,
            hora_fin=horario.hora_fin,
        ).first()
        if periodo is None:
            huerfanos.append(horario)
            continue
        horario.periodo_id = periodo.pk
        horario.save(update_fields=['periodo'])

    if huerfanos:
        # Preferimos fallar a perder clases en silencio.
        detalle = ', '.join(f'{h.dia} {h.hora_inicio}-{h.hora_fin}' for h in huerfanos)
        raise RuntimeError(
            f'Hay {len(huerfanos)} horarios sin período correspondiente: {detalle}. '
            'Créalos antes de aplicar esta migración.'
        )


def deshacer_vinculo(apps, schema_editor):
    """Al revertir, se recuperan las horas desde el período."""
    Horario = apps.get_model('academico', 'Horario')
    for horario in Horario.objects.select_related('periodo'):
        horario.hora_inicio = horario.periodo.hora_inicio
        horario.hora_fin = horario.periodo.hora_fin
        horario.save(update_fields=['hora_inicio', 'hora_fin'])


class Migration(migrations.Migration):

    dependencies = [
        ('academico', '0007_diacapacitacion'),
    ]

    operations = [
        # ── Horario: primero la columna nueva, luego el traspaso, luego las viejas ──
        migrations.AddField(
            model_name='horario',
            name='periodo',
            field=models.ForeignKey(
                null=True, on_delete=django.db.models.deletion.CASCADE,
                related_name='horarios', to='academico.periodo',
            ),
        ),
        migrations.RunPython(vincular_horarios_a_periodos, deshacer_vinculo),
        migrations.AlterField(
            model_name='horario',
            name='periodo',
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name='horarios', to='academico.periodo',
            ),
        ),
        migrations.RemoveField(model_name='horario', name='hora_inicio'),
        migrations.RemoveField(model_name='horario', name='hora_fin'),
        migrations.AlterModelOptions(
            name='horario',
            options={'ordering': ['dia', 'periodo__hora_inicio'],
                     'verbose_name': 'Horario', 'verbose_name_plural': 'Horarios'},
        ),
        migrations.AddConstraint(
            model_name='horario',
            constraint=models.UniqueConstraint(fields=('periodo', 'dia'), name='una_clase_por_celda'),
        ),

        # ── Estudiante: fuera la copia de los datos del tutor y el curso ──
        migrations.RemoveField(model_name='estudiante', name='nombre_tutor'),
        migrations.RemoveField(model_name='estudiante', name='ci_tutor'),
        migrations.RemoveField(model_name='estudiante', name='telefono_tutor'),
        migrations.RemoveField(model_name='estudiante', name='email_tutor'),
        migrations.RemoveField(model_name='estudiante', name='curso_actual'),
        migrations.AlterField(
            model_name='estudiante',
            name='tutor',
            field=models.ForeignKey(
                blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                related_name='hijos', limit_choices_to={'rol': 'PADRE'},
                to='accounts.usuario', verbose_name='Padre/tutor',
                help_text='Se crea y se vincula sola a partir del CI que se escriba en el formulario.',
            ),
        ),

        # ── Matrícula: la gestión sale del curso ──
        migrations.AlterUniqueTogether(name='matricula', unique_together=set()),
        migrations.RemoveField(model_name='matricula', name='gestion'),
        migrations.AlterModelOptions(
            name='matricula',
            options={'ordering': ['-curso__gestion__anio', 'curso'],
                     'verbose_name': 'Matrícula', 'verbose_name_plural': 'Matrículas'},
        ),
        migrations.AddConstraint(
            model_name='matricula',
            constraint=models.UniqueConstraint(fields=('estudiante', 'curso'), name='una_matricula_por_curso'),
        ),

        # ── Asignación docente: la gestión sale del curso ──
        migrations.AlterUniqueTogether(name='asignaciondocente', unique_together=set()),
        migrations.RemoveField(model_name='asignaciondocente', name='gestion'),
        migrations.AlterModelOptions(
            name='asignaciondocente',
            options={'ordering': ['curso', 'materia'],
                     'verbose_name': 'Asignación docente',
                     'verbose_name_plural': 'Asignaciones docentes'},
        ),
        migrations.AddConstraint(
            model_name='asignaciondocente',
            constraint=models.UniqueConstraint(fields=('curso', 'materia'), name='una_materia_por_curso'),
        ),
    ]
