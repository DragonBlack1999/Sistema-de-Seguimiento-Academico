"""La asistencia pasa de ser por materia a ser diaria, tomada por el regente.

Se recrea la tabla en vez de transformarla: los registros viejos eran por
materia (varios por estudiante y día) y no tienen equivalente directo en el
modelo diario. Por decisión del usuario, ese historial se descarta.
"""

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('asistencia', '0001_initial'),
        ('academico', '0006_estudiante_tutor'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.DeleteModel(name='Asistencia'),
        migrations.CreateModel(
            name='Asistencia',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('fecha', models.DateField()),
                ('hora_llegada', models.TimeField(
                    blank=True, null=True,
                    help_text='Se guarda al marcar la entrada. Vacío en faltas y licencias.',
                    verbose_name='Hora de llegada',
                )),
                ('estado', models.CharField(
                    choices=[('PRESENTE', 'Presente'), ('ATRASO', 'Atraso'),
                             ('FALTA', 'Falta'), ('LICENCIA', 'Licencia')],
                    default='PRESENTE', max_length=10,
                )),
                ('observacion', models.CharField(blank=True, max_length=200)),
                ('fecha_registro', models.DateTimeField(auto_now=True)),
                ('estudiante', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='asistencias', to='academico.estudiante',
                )),
                ('gestion', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='asistencias', to='academico.gestion',
                    help_text='Año escolar al que pertenece el registro.',
                )),
                ('registrado_por', models.ForeignKey(
                    blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                    related_name='asistencias_registradas', to=settings.AUTH_USER_MODEL,
                )),
            ],
            options={
                'verbose_name': 'Asistencia',
                'verbose_name_plural': 'Asistencias',
                'ordering': ['-fecha', 'estudiante__usuario__last_name'],
            },
        ),
        migrations.AddConstraint(
            model_name='asistencia',
            constraint=models.UniqueConstraint(
                fields=('estudiante', 'fecha'), name='una_asistencia_por_dia',
            ),
        ),
        migrations.AddIndex(
            model_name='asistencia',
            index=models.Index(fields=['fecha'], name='asistencia_fecha_idx'),
        ),
        migrations.AddIndex(
            model_name='asistencia',
            index=models.Index(fields=['estudiante', '-fecha'], name='asistencia_est_fecha_idx'),
        ),
    ]
