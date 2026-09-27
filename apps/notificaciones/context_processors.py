from django.conf import settings
from django.utils.functional import SimpleLazyObject

from .models import Notificacion

LIMITE_DROPDOWN = 5


def notificaciones(request):
    """Contador y lista corta para la campanita de la barra de navegación.

    Corre en cada request, así que los dos valores son perezosos: si la plantilla
    no los usa (el admin de Django, un PDF, un FileResponse), no se ejecuta
    ninguna consulta. Para usuarios anónimos devuelve un diccionario vacío.
    """
    usuario = getattr(request, 'user', None)
    if usuario is None or not usuario.is_authenticated:
        return {}

    base = Notificacion.objects.filter(usuario_id=usuario.pk)
    return {
        'notificaciones_no_leidas': SimpleLazyObject(lambda: base.filter(leida=False).count()),
        'notificaciones_recientes': base[:LIMITE_DROPDOWN],
        # La llave pública del servidor: con ella el navegador se suscribe. Es
        # pública a propósito; la privada nunca sale del servidor.
        'vapid_public_key': settings.VAPID_PUBLIC_KEY,
    }
