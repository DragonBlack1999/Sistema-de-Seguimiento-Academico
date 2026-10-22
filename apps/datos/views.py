"""Gestión de datos: la pantalla que la secretaría necesita.

Hasta ahora «Gestionar datos» llevaba al panel de Django, y ahí chocaba: de las
tres cuentas de administración, solo el superusuario podía entrar. El director y
la secretaria veían un segundo inicio de sesión que su cuenta no pasa.

Estas vistas son genéricas: leen qué mostrar del registro de `fichas.py`. Así
las nueve pantallas se comportan igual —la misma búsqueda, la misma paginación,
los mismos textos cuando no hay nada— y arreglar algo se arregla una vez.
"""
from django.contrib.auth.decorators import login_required
from django.http import Http404, HttpResponseForbidden
from django.shortcuts import render

from . import fichas, listados

MENSAJE_SOLO_ADMIN = 'Solo la dirección o la secretaría pueden gestionar los datos del colegio.'


def _ficha(clave):
    ficha = fichas.obtener(clave)
    if ficha is None:
        raise Http404('No existe esa sección de datos.')
    return ficha


@login_required
def indice(request):
    """El mapa de todo lo que se puede administrar, con sus cuentas."""
    if not request.user.es_admin():
        return HttpResponseForbidden(MENSAJE_SOLO_ADMIN)

    grupos = [
        (grupo, [{'ficha': f, 'cuantos': f.cuantos()} for f in lista])
        for grupo, lista in fichas.por_grupos()
    ]
    return render(request, 'datos/indice.html', {'grupos': grupos})


@login_required
def lista(request, clave):
    """Una ficha cualquiera: buscada, filtrada y paginada."""
    if not request.user.es_admin():
        return HttpResponseForbidden(MENSAJE_SOLO_ADMIN)

    ficha = _ficha(clave)
    consulta = (request.GET.get('q') or '').strip()

    queryset = ficha.consulta()
    queryset, filtros_elegidos = listados.aplicar_filtros(request, ficha, queryset)
    queryset = listados.buscar(ficha, queryset, consulta)

    pagina = listados.paginar(request, queryset, ficha.por_pagina)

    # Las columnas se calculan aquí y no en la plantilla: una plantilla no puede
    # llamar a una función con argumentos, y tampoco debería.
    filas = [
        {
            'objeto': objeto,
            'celdas': [
                {'rotulo': c.rotulo, 'valor': c.valor(objeto), 'principal': c.principal}
                for c in ficha.columnas
            ],
            'de_baja': bool(ficha.esta_de_baja and ficha.esta_de_baja(objeto)),
        }
        for objeto in pagina
    ]

    desplegables = [
        {
            'clave': f.clave, 'rotulo': f.rotulo, 'opciones': f.opciones(),
            'elegido': filtros_elegidos.get(f.clave, ''),
        }
        for f in ficha.filtros
    ]

    # Mientras se escribe en el buscador, el navegador pide solo la tabla: no
    # tiene sentido mandarle otra vez la barra, el escudo y los estilos.
    plantilla = ('datos/_tabla.html'
                 if request.headers.get('X-Requested-With') == 'XMLHttpRequest'
                 else 'datos/lista.html')

    return render(request, plantilla, {
        'ficha': ficha,
        'filas': filas,
        'pagina': pagina,
        'consulta': consulta,
        'desplegables': desplegables,
        'hay_filtros_puestos': listados.hay_algo_puesto(request, ficha),
        'direccion_sin_pagina': listados.direccion_sin_pagina(request),
        'total': pagina.paginator.count,
    })
