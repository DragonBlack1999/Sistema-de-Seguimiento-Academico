from django.conf import settings
from django.db import models

from apps.academico.models import Estudiante


class Asistencia(models.Model):
    """Asistencia diaria, registrada por el regente en la puerta del colegio.

    Es **un registro por estudiante y día**, no por materia: quien controla la
    entrada es el regente, no el profesor de cada clase.
    """

    class Estado(models.TextChoices):
        PRESENTE = 'PRESENTE', 'Presente'
        ATRASO = 'ATRASO', 'Atraso'
        FALTA = 'FALTA', 'Falta'
        LICENCIA = 'LICENCIA', 'Licencia'

    estudiante = models.ForeignKey(Estudiante, on_delete=models.CASCADE, related_name='asistencias')
    # La gestión no se guarda: es el año de la fecha. Guardarla permitía un
    # registro fechado en 2026 apuntando a la gestión 2025.
    fecha = models.DateField()
    hora_llegada = models.TimeField(
        'Hora de llegada', null=True, blank=True,
        help_text='Se guarda al marcar la entrada. Vacío en faltas y licencias.',
    )
    estado = models.CharField(max_length=10, choices=Estado.choices, default=Estado.PRESENTE)
    observacion = models.CharField(max_length=200, blank=True)
    registrado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='asistencias_registradas',
    )
    fecha_registro = models.DateTimeField(auto_now=True)

    class Meta:
        # Un solo registro por estudiante y día: la entrada al colegio ocurre una vez.
        constraints = [
            models.UniqueConstraint(fields=['estudiante', 'fecha'], name='una_asistencia_por_dia'),
        ]
        ordering = ['-fecha', 'estudiante__usuario__last_name']
        verbose_name = 'Asistencia'
        verbose_name_plural = 'Asistencias'
        indexes = [
            models.Index(fields=['fecha'], name='asistencia_fecha_idx'),
            models.Index(fields=['estudiante', '-fecha'], name='asistencia_est_fecha_idx'),
        ]

    @property
    def gestion(self):
        """La gestión a la que pertenece el registro, por el año de su fecha."""
        from apps.academico.models import Gestion

        return Gestion.objects.filter(anio=self.fecha.year).first()

    @property
    def asistio(self):
        return self.estado in (self.Estado.PRESENTE, self.Estado.ATRASO)

    def __str__(self):
        return f'{self.estudiante} - {self.fecha} - {self.get_estado_display()}'
