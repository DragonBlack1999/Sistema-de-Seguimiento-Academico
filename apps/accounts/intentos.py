"""Límite de intentos de inicio de sesión.

Sin esto, cualquiera puede probar contraseñas sin fin. Y aquí las contraseñas
iniciales son el carnet de identidad, que no es un secreto: un número de pocas
cifras que se prueba rápido.

Dos límites, contados en la misma ventana de tiempo:

- **Por cuenta**: tras `LOGIN_INTENTOS_POR_USUARIO` fallos seguidos con el
  mismo usuario, esa cuenta no acepta claves por `LOGIN_BLOQUEO_MINUTOS`. Frena
  a quien ataca a una persona en particular, aunque cambie de computadora.
- **Por dirección**: tras `LOGIN_INTENTOS_POR_IP` fallos desde la misma
  dirección, sea con el usuario que sea. Frena a quien recorre muchas cuentas.
  Es más alto porque en el colegio muchos entran desde la misma red.

Mientras dura el bloqueo ni siquiera se mira la contraseña: si se la mirara,
el que prueba sabría cuál es la buena aunque no lo dejaran entrar. Entrar bien
borra los fallos de esa cuenta.
"""
import math
from datetime import timedelta

from django.conf import settings
from django.utils import timezone

from .models import IntentoFallido


def _ajuste(nombre, omision):
    return getattr(settings, nombre, omision)


def _ventana():
    return timedelta(minutes=_ajuste('LOGIN_BLOQUEO_MINUTOS', 15))


def normalizar(usuario):
    return (usuario or '').strip().lower()[:150]


def ip_de(request):
    """La dirección de quien escribe, no la del intermediario.

    En el servidor la conexión llega a través del proxy de Railway, que agrega
    la dirección real al final de X-Forwarded-For. Se toma la última: las
    anteriores las puede inventar el propio navegador. En el colegio no hay
    intermediario y vale REMOTE_ADDR.
    """
    if request is None:
        return None
    if getattr(settings, 'SECURE_PROXY_SSL_HEADER', None):
        reenviada = request.META.get('HTTP_X_FORWARDED_FOR', '')
        partes = [p.strip() for p in reenviada.split(',') if p.strip()]
        if partes:
            return partes[-1]
    return request.META.get('REMOTE_ADDR') or None


def minutos_de_bloqueo(usuario, ip):
    """Cuántos minutos faltan para poder intentar de nuevo; 0 si no hay bloqueo."""
    ahora = timezone.now()
    desde = ahora - _ventana()
    recientes = IntentoFallido.objects.filter(fecha__gte=desde)

    hasta = None
    for filtro, limite in (
        ({'usuario': normalizar(usuario)}, _ajuste('LOGIN_INTENTOS_POR_USUARIO', 5)),
        ({'ip': ip}, _ajuste('LOGIN_INTENTOS_POR_IP', 30)),
    ):
        if not next(iter(filtro.values())):
            continue
        fechas = list(recientes.filter(**filtro).order_by('-fecha')
                      .values_list('fecha', flat=True)[:limite])
        if len(fechas) >= limite:
            # El bloqueo corre desde el último fallo que completó el límite.
            fin = fechas[0] + _ventana()
            hasta = fin if hasta is None else max(hasta, fin)

    if hasta is None or hasta <= ahora:
        return 0
    return max(1, math.ceil((hasta - ahora).total_seconds() / 60))


def registrar_fallo(usuario, ip):
    IntentoFallido.objects.create(usuario=normalizar(usuario), ip=ip)
    # La tabla no crece sin fin: lo que salió de la ventana ya no cuenta.
    IntentoFallido.objects.filter(fecha__lt=timezone.now() - 4 * _ventana()).delete()


def registrar_exito(usuario):
    IntentoFallido.objects.filter(usuario=normalizar(usuario)).delete()
