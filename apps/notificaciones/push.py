"""Empujar avisos al celular, aunque el sistema esté cerrado.

El aviso viaja cifrado hasta el servicio de push del navegador (el de Google, en
Android) y de ahí al teléfono, que despierta al *service worker* para mostrarlo.
Nosotros solo firmamos con las llaves VAPID y entregamos el sobre.

Dos decisiones que conviene conocer:

- **Sin llaves configuradas no pasa nada.** La campanita del sistema sigue igual;
  solo no hay aviso en el teléfono. Así la demo de la laptop, que corre sin
  internet, no necesita tocar nada.
- **El envío va en segundo plano.** Una noticia para todo el colegio son
  cuatrocientos envíos a servidores de Google: hacerlos dentro de la petición
  dejaría al docente mirando una pantalla en blanco medio minuto.
"""
import json
import logging
import threading
from concurrent.futures import ThreadPoolExecutor

from django.conf import settings
from django.db import connections
from django.utils import timezone

from .models import SuscripcionPush

registro = logging.getLogger(__name__)

# Cuántos envíos en paralelo. Son llamadas de red que esperan, no cálculo.
EN_PARALELO = 8
ESPERA = 10           # segundos por envío


def hay_push():
    """Si este servidor está en condiciones de mandar avisos al celular."""
    return bool(settings.VAPID_PUBLIC_KEY and settings.VAPID_PRIVATE_KEY)


def enviar(usuarios, *, titulo, mensaje='', url='/', en_segundo_plano=True):
    """Manda el aviso a todos los teléfonos de esos usuarios. Devuelve cuántos.

    `usuarios` acepta ids. Si alguien tiene dos teléfonos, recibe en los dos.
    """
    if not hay_push():
        return 0

    suscripciones = list(SuscripcionPush.objects.filter(usuario_id__in=list(usuarios)))
    if not suscripciones:
        return 0

    carga = json.dumps({'titulo': titulo, 'mensaje': mensaje, 'url': url})
    if en_segundo_plano:
        hilo = threading.Thread(target=_repartir_en_hilo, args=(suscripciones, carga), daemon=True)
        hilo.start()
        return len(suscripciones)
    return _repartir(suscripciones, carga)


def enviar_a_suscripcion(suscripcion, carga):
    """Código HTTP del proveedor, o None cuando no se obtuvo respuesta."""
    try:
        from pywebpush import webpush

        respuesta = webpush(
            subscription_info={
                'endpoint': suscripcion.endpoint,
                'keys': {'p256dh': suscripcion.p256dh, 'auth': suscripcion.auth},
            },
            data=carga,
            vapid_private_key=settings.VAPID_PRIVATE_KEY,
            vapid_claims={'sub': settings.VAPID_CONTACTO},
            timeout=ESPERA,
        )
        codigo = respuesta.status_code
    except Exception as error:
        codigo = getattr(getattr(error, 'response', None), 'status_code', None)
    if not aceptado(codigo) and codigo not in (404, 410):
        registro.warning('Push pendiente para la suscripción %s (HTTP %s).', suscripcion.pk, codigo)
    return codigo


def aceptado(codigo):
    return codigo is not None and 200 <= codigo < 300


def _repartir_en_hilo(suscripciones, carga):
    try:
        _repartir(suscripciones, carga)
    finally:
        connections.close_all()


def _repartir(suscripciones, carga):
    """Distribuye el aviso inmediato y cuenta las respuestas aceptadas."""
    with ThreadPoolExecutor(max_workers=EN_PARALELO) as grupo:
        resultados = list(grupo.map(lambda s: enviar_a_suscripcion(s, carga), suscripciones))
    caducadas = [s.pk for s, codigo in zip(suscripciones, resultados) if codigo in (404, 410)]
    enviadas = [s.pk for s, codigo in zip(suscripciones, resultados) if aceptado(codigo)]
    SuscripcionPush.objects.filter(pk__in=caducadas).delete()
    SuscripcionPush.objects.filter(pk__in=enviadas).update(ultimo_envio=timezone.now())
    return len(enviadas)
