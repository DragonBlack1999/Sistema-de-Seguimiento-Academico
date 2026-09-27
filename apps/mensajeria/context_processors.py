from django.utils.functional import SimpleLazyObject

from .models import Mensaje


def mensajeria(request):
    """Contador de mensajes sin leer para el enlace "Mensajes" de la navegación.

    Perezoso por la misma razón que el de notificaciones: corre en cada request,
    así que si la plantilla no lo usa (el admin de Django, un PDF, un
    FileResponse) no se ejecuta ninguna consulta.
    """
    usuario = getattr(request, 'user', None)
    if usuario is None or not usuario.is_authenticated:
        return {}

    return {
        'mensajes_no_leidos': SimpleLazyObject(
            lambda: Mensaje.objects.filter(destinatario_id=usuario.pk, leido=False).count()
        ),
    }
