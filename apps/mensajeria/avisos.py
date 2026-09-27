"""Avisar de un mensaje nuevo, sin convertirse en una molestia.

La campanita ya mostraba citaciones, tareas y noticias, pero no los mensajes:
alguien podía escribirle a un padre y ese padre no se enteraba hasta que entrara
a mirar. Esto lo arregla.

Dos decisiones que no son obvias:

- **Un aviso por conversación, no por mensaje.** Mientras el anterior siga sin
  leer, escribir tres renglones seguidos no genera tres avisos. Si no, una
  conversación normal llenaría la campanita y haría sonar el teléfono en cada
  frase.
- **El aviso no lleva el texto del mensaje.** Sale del colegio y pasa por el
  servicio de mensajería del navegador (Google, Mozilla, Microsoft), que vería
  su contenido. Dice quién escribió; lo que dijo se lee entrando, que es lo que
  promete el aviso de privacidad.
"""
from django.urls import reverse

from apps.notificaciones.models import Notificacion
from apps.notificaciones.services import crear_notificaciones


def _url_de(autor):
    return reverse('mensajeria:conversacion', args=[autor.pk])


def avisar_mensaje(mensaje):
    """Avisa al destinatario. Devuelve True si creó un aviso nuevo."""
    destinatario = mensaje.destinatario
    if destinatario is None or destinatario.pk == mensaje.autor_id:
        return False

    url = _url_de(mensaje.autor)
    ya_avisado = Notificacion.objects.filter(
        usuario_id=destinatario.pk, tipo=Notificacion.Tipo.MENSAJE, url=url, leida=False,
    ).exists()
    if ya_avisado:
        return False

    nombre = mensaje.autor.get_full_name() or mensaje.autor.username
    crear_notificaciones(
        [destinatario.pk],
        tipo=Notificacion.Tipo.MENSAJE,
        nivel=Notificacion.Nivel.INFORMATIVO,
        titulo=f'Te escribió {nombre}',
        mensaje=f'{mensaje.autor.get_rol_display()} · entra para leerlo.',
        url=url,
    )
    return True


def marcar_leidos(usuario, otro):
    """Al abrir la conversación, el aviso de esa conversación deja de estar pendiente.

    Sin esto, la campanita seguiría marcando un mensaje sin leer que la persona
    ya está leyendo, y ese contador que no baja termina por ignorarse entero.
    """
    return Notificacion.objects.filter(
        usuario_id=usuario.pk, tipo=Notificacion.Tipo.MENSAJE,
        url=_url_de(otro), leida=False,
    ).update(leida=True)
