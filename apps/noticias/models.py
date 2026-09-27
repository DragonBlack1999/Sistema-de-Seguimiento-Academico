from django.conf import settings
from django.db import models

from apps.tareas.validators import validar_archivo

from .validators import ruta_adjunto_noticia, ruta_imagen_noticia, validar_imagen


class Noticia(models.Model):
    class Tipo(models.TextChoices):
        NOTICIA = 'NOTICIA', 'Noticia'
        ACTIVIDAD = 'ACTIVIDAD', 'Actividad'
        COMUNICADO = 'COMUNICADO', 'Comunicado'

    titulo = models.CharField('Título', max_length=200)
    cuerpo = models.TextField('Contenido')
    tipo = models.CharField(max_length=12, choices=Tipo.choices, default=Tipo.NOTICIA)
    curso = models.ForeignKey(
        'academico.Curso', on_delete=models.PROTECT, null=True, blank=True,
        related_name='noticias',
        help_text='Dejar vacío para publicar a todo el colegio.',
    )
    fecha_evento = models.DateField('Fecha de la actividad', null=True, blank=True)
    imagen = models.ImageField(
        upload_to=ruta_imagen_noticia, blank=True, validators=[validar_imagen],
    )
    archivo = models.FileField(
        'Archivo adjunto', upload_to=ruta_adjunto_noticia, blank=True, validators=[validar_archivo],
    )
    archivo_nombre = models.CharField(max_length=255, blank=True)
    publicada = models.BooleanField('Visible para los destinatarios', default=True)
    fijada = models.BooleanField('Fijar arriba', default=False)
    publicado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='noticias_publicadas',
    )
    fecha_publicacion = models.DateTimeField(auto_now_add=True)
    fecha_actualizacion = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-fijada', '-fecha_publicacion']
        verbose_name = 'Noticia'
        verbose_name_plural = 'Noticias'
        indexes = [models.Index(fields=['publicada', 'curso'], name='noticia_pub_curso_idx')]

    @property
    def es_general(self):
        return self.curso_id is None

    def __str__(self):
        # No toca self.curso: evita una query por fila en listados y en el admin.
        return self.titulo
