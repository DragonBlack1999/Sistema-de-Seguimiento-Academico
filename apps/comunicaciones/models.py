from django.conf import settings
from django.db import models

from apps.academico.models import Estudiante


class AlertaEmitida(models.Model):
    """Marca de que algo ya se avisó, para no repetirlo cada noche.

    La revisión diaria vuelve a mirar los mismos hechos una y otra vez: la misma
    tarea sigue vencida mañana y pasado. Sin esta marca, el padre recibiría el
    mismo aviso todos los días hasta fin de año.

    La clave describe el hecho en una línea: `falta:2026-09-25`, `tarea:41`,
    `nota-baja:12:1`, `racha:2`. Así se lee en la base qué se avisó y cuándo.
    """

    estudiante = models.ForeignKey(
        Estudiante, on_delete=models.CASCADE, related_name='alertas_emitidas',
    )
    clave = models.CharField(max_length=80)
    fecha_creacion = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['estudiante', 'clave'], name='una_alerta_por_hecho'),
        ]
        ordering = ['-fecha_creacion']
        verbose_name = 'Alerta emitida'
        verbose_name_plural = 'Alertas emitidas'

    def __str__(self):
        return f'{self.estudiante} · {self.clave}'


class Citacion(models.Model):
    class Estado(models.TextChoices):
        PENDIENTE = 'PENDIENTE', 'Pendiente'
        ATENDIDA = 'ATENDIDA', 'Atendida'
        NO_ASISTIO = 'NO_ASISTIO', 'No asistió'

    estudiante = models.ForeignKey(Estudiante, on_delete=models.CASCADE, related_name='citaciones')
    motivo = models.TextField('Motivo de la citación')
    fecha = models.DateField('Fecha de la citación')
    hora = models.TimeField('Hora', null=True, blank=True)
    lugar = models.CharField(max_length=150, blank=True, default='Dirección del colegio')
    estado = models.CharField(max_length=12, choices=Estado.choices, default=Estado.PENDIENTE)
    observaciones = models.TextField(blank=True)
    generado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='citaciones_generadas'
    )
    es_automatica = models.BooleanField('Generada automáticamente', default=False)
    fecha_creacion = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-fecha']
        verbose_name = 'Citación'
        verbose_name_plural = 'Citaciones'

    def __str__(self):
        return f'Citación a {self.estudiante} - {self.fecha}'
