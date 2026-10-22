"""Buscar, filtrar y paginar: lo que toda lista hace igual.

Vive aparte de las vistas porque son decisiones de presentación que conviene
tomar una sola vez. En particular la de la página: hasta ahora ninguna pantalla
del sistema paginaba, y con cuatrocientos estudiantes en una sola tabla el
navegador del colegio sufre.
"""
from django.core.paginator import Paginator


def aplicar_filtros(request, ficha, queryset):
    """Aplica los filtros de la ficha que vengan en la URL.

    Devuelve el queryset filtrado y qué quedó elegido en cada desplegable, para
    que la pantalla los vuelva a mostrar marcados.
    """
    elegidos = {}
    for filtro in ficha.filtros:
        valor = (request.GET.get(filtro.clave) or '').strip()
        if not valor:
            continue
        elegidos[filtro.clave] = valor
        try:
            queryset = filtro.aplicar(queryset, valor)
        except (ValueError, TypeError):
            # Un valor manipulado en la URL no debe tumbar la pantalla.
            del elegidos[filtro.clave]
    return queryset, elegidos


def buscar(ficha, queryset, consulta):
    if not consulta or not ficha.buscador:
        return queryset
    return ficha.buscador(consulta, queryset)


def paginar(request, queryset, por_pagina):
    """La página pedida, o la primera si el número no sirve."""
    paginador = Paginator(queryset, por_pagina)
    return paginador.get_page(request.GET.get('page'))


def direccion_sin_pagina(request):
    """La misma búsqueda y filtros, sin el número de página.

    Sin esto, pasar a la página siguiente perdería lo que se estaba buscando.
    """
    parametros = request.GET.copy()
    parametros.pop('page', None)
    cadena = parametros.urlencode()
    return f'{cadena}&' if cadena else ''


def hay_algo_puesto(request, ficha):
    """True si la persona escribió una búsqueda o eligió algún filtro.

    Decide si se muestra el botón «Limpiar» y cuál de los dos mensajes de tabla
    vacía corresponde: no es lo mismo «no se encontró nada» que «todavía no hay
    nada cargado».
    """
    if (request.GET.get('q') or '').strip():
        return True
    return any((request.GET.get(f.clave) or '').strip() for f in ficha.filtros)
