from django.conf import settings
from django.db import models
from django.db.models import F, Q

from .validators import ruta_adjunto_mensaje, validar_adjunto


class Conversacion(models.Model):
    """Conversación 1 a 1 entre dos usuarios.

    Los participantes se guardan siempre ordenados por id (`usuario_menor` <
    `usuario_mayor`). Con eso, la restricción única impide que existan dos hilos
    paralelos para la misma pareja sin importar quién escriba primero, que es el
    error clásico de estos chats.
    """

    usuario_menor = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='conversaciones_como_menor',
    )
    usuario_mayor = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='conversaciones_como_mayor',
    )
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_ultimo_mensaje = models.DateTimeField(db_index=True, null=True, blank=True)

    class Meta:
        ordering = ['-fecha_ultimo_mensaje', '-fecha_creacion']
        verbose_name = 'Conversación'
        verbose_name_plural = 'Conversaciones'
        constraints = [
            models.UniqueConstraint(
                fields=['usuario_menor', 'usuario_mayor'], name='unica_conversacion_por_par',
            ),
            models.CheckConstraint(
                condition=Q(usuario_menor__lt=F('usuario_mayor')), name='par_de_conversacion_ordenado',
            ),
        ]

    @classmethod
    def entre(cls, uno, otro):
        """Devuelve (conversación, creada) para un par de usuarios, en cualquier orden."""
        menor_id, mayor_id = sorted((uno.pk, otro.pk))
        return cls.objects.get_or_create(usuario_menor_id=menor_id, usuario_mayor_id=mayor_id)

    def otro_participante(self, usuario):
        return self.usuario_mayor if usuario.pk == self.usuario_menor_id else self.usuario_menor

    def __str__(self):
        return f'{self.usuario_menor.get_full_name()} ↔ {self.usuario_mayor.get_full_name()}'


class Mensaje(models.Model):
    conversacion = models.ForeignKey(Conversacion, on_delete=models.CASCADE, related_name='mensajes')
    autor = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='mensajes_enviados',
    )
    # Redundante (se deduce de la conversación y el autor), pero guardado a
    # propósito: el contador de no leídos corre en cada página, y así es un
    # COUNT sobre un índice parcial en vez de un OR con join.
    destinatario = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='mensajes_recibidos',
    )
    cuerpo = models.TextField(blank=True)
    archivo = models.FileField(
        'Adjunto', upload_to=ruta_adjunto_mensaje, null=True, blank=True, validators=[validar_adjunto],
    )
    archivo_nombre = models.CharField(max_length=255, blank=True)
    leido = models.BooleanField(default=False)
    fecha_envio = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['fecha_envio', 'id']
        verbose_name = 'Mensaje'
        verbose_name_plural = 'Mensajes'
        indexes = [
            models.Index(fields=['destinatario'], condition=Q(leido=False), name='msg_no_leidos_idx'),
            models.Index(fields=['conversacion', 'fecha_envio'], name='msg_conversacion_fecha_idx'),
        ]

    def __str__(self):
        return f'{self.autor.get_full_name()}: {self.cuerpo[:40]}'
