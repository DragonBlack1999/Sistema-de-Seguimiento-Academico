"""Una sola pantalla, y no es para personas.

El servidor pregunta cada tanto si la aplicación sigue viva. Si deja de
responder, reinicia el contenedor solo. Por eso la revisión toca la base de
datos: un proceso que responde pero no alcanza su base no está sano, y conviene
que el servidor lo sepa.

No dice nada de adentro: quien no tiene cuenta solo ve «bien» o «mal».
"""
from django.db import connection
from django.http import HttpResponse
from django.views.decorators.cache import never_cache


@never_cache
def salud(request):
    try:
        with connection.cursor() as cursor:
            cursor.execute('SELECT 1')
            cursor.fetchone()
    except Exception:
        return HttpResponse('mal', content_type='text/plain', status=503)
    return HttpResponse('bien', content_type='text/plain')
