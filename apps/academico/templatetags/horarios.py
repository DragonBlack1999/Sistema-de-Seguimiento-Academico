"""Nombres cortos para el horario impreso.

En la pantalla hay sitio para «Nelly Felisa Blanco Rodriguez» y para
«1° de Secundaria "B" (2026)». En una hoja no: cada uno de esos textos ocupa
tres renglones dentro de su celda, y cuarenta y dos celdas con tres renglones
son las que empujaban el septimo periodo a una segunda hoja.
"""
from django import template

register = template.Library()


@register.filter
def docente_corto(usuario):
    """«Nelly Felisa Blanco Rodriguez» -> «Nelly Blanco».

    El primer nombre y el primer apellido alcanzan para saber de quien se
    habla, y entran siempre en un solo renglon.
    """
    if usuario is None:
        return ''
    nombre = (usuario.first_name or '').split()
    apellido = (usuario.last_name or '').split()
    corto = ' '.join(filter(None, [nombre[0] if nombre else '',
                                   apellido[0] if apellido else '']))
    return corto or usuario.get_full_name() or usuario.username


@register.filter
def curso_corto(curso):
    """«1° de Secundaria "B" (2026)» -> «1° B».

    El nivel y la gestion ya estan en el membrete de la hoja: repetirlos en
    cuarenta y dos celdas no agrega nada.
    """
    if curso is None:
        return ''
    return f'{curso.grado}° {curso.paralelo}'
