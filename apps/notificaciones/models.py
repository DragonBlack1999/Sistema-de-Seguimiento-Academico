from django.conf import settings
from django.db import models


class SuscripcionPush(models.Model):
    """Un teléfono que aceptó recibir avisos, con la dirección que le dio su navegador.

    El navegador entrega una dirección única por teléfono (vive en el servicio de
    push) y dos llaves con las que se cifra cada mensaje. Nosotros solo guardamos
    eso: quién es el dueño y cómo llegarle.

    Una persona puede tener varias: el celular y la computadora de su casa. Y una
    dirección deja de servir cuando desinstala la app o borra los datos del
    navegador; el propio servicio nos lo dice al fallar el envío y ahí se borra.
    """

    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='suscripciones_push',
    )
    endpoint = models.URLField('Dirección del teléfono', max_length=500, unique=True)
    p256dh = models.CharField('Llave pública del teléfono', max_length=120)
    auth = models.CharField('Secreto de cifrado', max_length=60)
    dispositivo = models.CharField(max_length=120, blank=True, help_text='Para que el usuario reconozca cuál es.')
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    ultimo_envio = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-fecha_creacion']
        verbose_name = 'Suscripción push'
        verbose_name_plural = 'Suscripciones push'
        indexes = [models.Index(fields=['usuario'], name='push_usuario_idx')]

    def __str__(self):
        return f'{self.usuario} · {self.dispositivo or "dispositivo"}'


class Notificacion(models.Model):
    class Tipo(models.TextChoices):
        NOTICIA = 'NOTICIA', 'Noticia'
        CITACION = 'CITACION', 'Citación'
        TAREA = 'TAREA', 'Tarea'
        ASISTENCIA = 'ASISTENCIA', 'Asistencia'
        NOTA = 'NOTA', 'Calificación'

    class Nivel(models.TextChoices):
        """Cuánto corre cada aviso.

        No es solo un color: decide **cuándo** sale al celular. Lo urgente sale
        al instante; lo de atención espera al resumen del día, porque un padre
        con un hijo de trece materias que recibe quince avisos sueltos termina
        por no mirar ninguno.
        """

        INFORMATIVO = 'INFO', 'Informativo'
        ATENCION = 'ATENCION', 'Atención'
        URGENTE = 'URGENTE', 'Urgente'

    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='notificaciones',
    )
    # De qué estudiante habla el aviso, cuando habla de uno. Sirve para el
    # resumen del día: un padre con dos hijos recibe un mensaje por cada uno, no
    # uno solo donde se le mezclan. Las noticias del colegio lo dejan vacío.
    estudiante = models.ForeignKey(
        'academico.Estudiante', on_delete=models.CASCADE, null=True, blank=True,
        related_name='notificaciones',
    )
    tipo = models.CharField(max_length=12, choices=Tipo.choices)
    nivel = models.CharField(max_length=8, choices=Nivel.choices, default=Nivel.INFORMATIVO)
    titulo = models.CharField(max_length=200)
    mensaje = models.CharField(max_length=300, blank=True)
    url = models.CharField(max_length=300)   # ruta interna, resuelta con reverse() al crear
    leida = models.BooleanField(default=False)
    # Si ya salió al celular. Lo urgente e informativo sale al crearse; lo de
    # atención espera al resumen diario, que es quien marca esto.
    avisada = models.BooleanField('Ya salió al celular', default=False)
    fecha_creacion = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-fecha_creacion']
        verbose_name = 'Notificación'
        verbose_name_plural = 'Notificaciones'
        indexes = [
            # Índice parcial: el contador de la campanita corre en cada página.
            models.Index(fields=['usuario'], condition=models.Q(leida=False),
                         name='notif_no_leidas_idx'),
            models.Index(fields=['usuario', '-fecha_creacion'], name='notif_usuario_fecha_idx'),
        ]

    def __str__(self):
        return f'{self.get_tipo_display()}: {self.titulo}'
