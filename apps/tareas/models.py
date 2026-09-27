from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone

from apps.academico.models import AsignacionDocente, Estudiante
from apps.calificaciones.models import MAXIMO, Dimension, Trimestre, aprueba

from .validators import ruta_enunciado, ruta_entrega, tipo_en_linea, validar_archivo


class Tarea(models.Model):
    asignacion = models.ForeignKey(
        AsignacionDocente, on_delete=models.CASCADE, related_name='tareas', verbose_name='asignación'
    )
    trimestre = models.PositiveSmallIntegerField(choices=Trimestre.choices)
    titulo = models.CharField('Título', max_length=150)
    descripcion = models.TextField('Enunciado / descripción', blank=True)
    fecha_asignacion = models.DateField('Fecha de asignación', default=timezone.localdate)
    fecha_entrega = models.DateField('Fecha límite de entrega')
    # Cada tarea es una columna de "hacer" en la planilla de notas: esa es su
    # actividad. No hay pesos; todas las tareas del trimestre valen lo mismo y su
    # promedio es la nota de la dimensión.
    actividad = models.OneToOneField(
        'calificaciones.Actividad', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='tarea',
    )
    permite_archivo = models.BooleanField('El estudiante puede adjuntar un archivo', default=True)
    permite_atraso = models.BooleanField('Permitir entregas después de la fecha límite', default=True)
    archivo_adjunto = models.FileField(
        'Archivo del enunciado', upload_to=ruta_enunciado,
        null=True, blank=True, validators=[validar_archivo],
    )
    archivo_nombre = models.CharField(max_length=255, blank=True)
    creado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='tareas_creadas',
    )
    fecha_creacion = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['trimestre', 'fecha_entrega', 'id']
        unique_together = ('asignacion', 'trimestre', 'titulo')
        verbose_name = 'Tarea'
        verbose_name_plural = 'Tareas'

    def clean(self):
        if self.fecha_entrega and self.fecha_asignacion and self.fecha_entrega < self.fecha_asignacion:
            raise ValidationError(
                {'fecha_entrega': 'La fecha de entrega no puede ser anterior a la fecha de asignación.'}
            )

    @property
    def vencida(self):
        return self.fecha_entrega < timezone.localdate()

    def __str__(self):
        # A propósito no toca self.asignacion: evita una query por fila en listados y en el admin.
        return f'{self.titulo} ({self.get_trimestre_display()})'


class EntregaTarea(models.Model):
    class Estado(models.TextChoices):
        PENDIENTE = 'PENDIENTE', 'Pendiente'
        ENTREGADA = 'ENTREGADA', 'Entregada'
        ATRASADA = 'ATRASADA', 'Entregada con retraso'
        NO_ENTREGADA = 'NO_ENTREGADA', 'No entregada'

    tarea = models.ForeignKey(Tarea, on_delete=models.CASCADE, related_name='entregas')
    estudiante = models.ForeignKey(Estudiante, on_delete=models.CASCADE, related_name='entregas_tareas')
    estado = models.CharField(max_length=15, choices=Estado.choices, default=Estado.PENDIENTE)
    archivo = models.FileField(
        upload_to=ruta_entrega, null=True, blank=True, validators=[validar_archivo]
    )
    archivo_nombre = models.CharField(max_length=255, blank=True)
    comentario_estudiante = models.TextField('Comentario del estudiante', blank=True)
    fecha_entrega_real = models.DateTimeField('Fecha de entrega', null=True, blank=True)
    observacion = models.TextField('Observación del profesor', blank=True)

    class Meta:
        unique_together = ('tarea', 'estudiante')
        ordering = ['estudiante__usuario__last_name', 'estudiante__usuario__first_name']
        verbose_name = 'Entrega de tarea'
        verbose_name_plural = 'Entregas de tareas'

    @property
    def puntaje(self):
        """Dónde vive la nota de esta entrega: en la columna de la tarea.

        La nota **no** se guarda aquí. Una tarea es una actividad de "hacer" y su
        nota es el puntaje de esa actividad; tenerla también en la entrega era la
        misma cifra en dos tablas, que tarde o temprano se contradicen.
        """
        from apps.calificaciones.models import Puntaje

        if self.tarea.actividad_id is None:
            return None
        return Puntaje.objects.filter(
            actividad_id=self.tarea.actividad_id, estudiante_id=self.estudiante_id,
        ).first()

    @property
    def nota(self):
        """La nota de la tarea, leída del puntaje.

        En listas largas no se usa: las vistas traen los puntajes en bloque para
        no hacer una consulta por fila.
        """
        puntaje = self.puntaje
        return puntaje.valor if puntaje is not None else None

    @property
    def calificada(self):
        return self.nota is not None

    @property
    def aprobada(self):
        # Aprobar es el 51% de lo que vale la tarea: 20,4 sobre 40.
        return aprueba(self.nota, MAXIMO[Dimension.HACER])

    @property
    def se_puede_ver(self):
        """True si el archivo se puede mostrar en pantalla sin descargarlo."""
        return bool(self.archivo) and tipo_en_linea(self.archivo.name) is not None

    def __str__(self):
        return f'{self.estudiante} — {self.tarea.titulo}'
