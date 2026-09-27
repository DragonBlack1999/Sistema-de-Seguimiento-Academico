"""`{% static_v %}`: la URL de un archivo estático con su versión.

Sin versión, el navegador guarda `sistema.css` y lo sigue usando aunque el
archivo haya cambiado: los estilos nuevos no llegan y la pantalla se ve rota
(pasó con el buscador de mensajes). La versión es la fecha de modificación del
archivo, así que cambia sola cada vez que se edita, sin tener que acordarse.
"""
import os

from django import template
from django.contrib.staticfiles import finders
from django.templatetags.static import static

register = template.Library()


@register.simple_tag
def static_v(ruta):
    url = static(ruta)
    archivo = finders.find(ruta)
    if archivo:
        url += f'?v={int(os.path.getmtime(archivo))}'
    return url
