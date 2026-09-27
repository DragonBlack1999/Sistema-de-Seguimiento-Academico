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
        hilo = threading.Thread(target=_repartir, args=(suscripciones, carga), daemon=True)
        hilo.start()
    else:
        _repartir(suscripciones, carga)
    return len(suscripciones)


def _repartir(suscripciones, carga):
    """Envía a cada teléfono y limpia las direcciones que ya no existen."""
    from pywebpush import WebPushException, webpush

    caducadas, enviadas = [], []

    def _uno(suscripcion):
        try:
            webpush(
                subscription_info={
                    'endpoint': suscripcion.endpoint,
                    'keys': {'p256dh': suscripcion.p256dh, 'auth': suscripcion.auth},
                },
                data=carga,
                vapid_private_key=settings.VAPID_PRIVATE_KEY,
                vapid_claims={'sub': settings.VAPID_CONTACTO},
                timeout=ESPERA,
            )
            enviadas.append(suscripcion.pk)
        except WebPushException as error:
            codigo = getattr(getattr(error, 'response', None), 'status_code', None)
            if codigo in (404, 410):
                # El teléfono desinstaló la app o borró los datos del navegador.
                caducadas.append(suscripcion.pk)
            else:
                registro.warning('No se pudo avisar a %s: %s', suscripcion.usuario_id, error)
        except Exception as error:                        # noqa: BLE001
            # Un fallo de red no puede tumbar la pantalla que disparó el aviso.
            registro.warning('Fallo enviando el aviso a %s: %s', suscripcion.usuario_id, error)

    try:
        with ThreadPoolExecutor(max_workers=EN_PARALELO) as grupo:
            list(grupo.map(_uno, suscripciones))

        if caducadas:
            SuscripcionPush.objects.filter(pk__in=caducadas).delete()
        if enviadas:
            SuscripcionPush.objects.filter(pk__in=enviadas).update(ultimo_envio=timezone.now())
    finally:
        # El hilo abre su propia conexión a la base: hay que cerrarla.
        connections.close_all()

    return len(enviadas)
