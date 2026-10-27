"""Gestión de datos: la pantalla que la secretaría necesita.

Hasta ahora «Gestionar datos» llevaba al panel de Django, y ahí chocaba: de las
tres cuentas de administración, solo el superusuario podía entrar. El director y
la secretaria veían un segundo inicio de sesión que su cuenta no pasa.

Estas vistas son genéricas: leen qué mostrar del registro de `fichas.py`. Así
las nueve pantallas se comportan igual —la misma búsqueda, la misma paginación,
los mismos textos cuando no hay nada— y arreglar algo se arregla una vez.
"""
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import ProtectedError
from django.http import Http404, HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from . import dependencias, fichas, listados

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
    from apps.accounts.claves import pendientes

    return render(request, 'datos/indice.html', {
        'grupos': grupos,
        'claves_pendientes': pendientes().count(),
    })


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


# ──────────────── alta, edición, baja y borrado ────────────────
#
# Las cuatro son genéricas: leen de la ficha qué formulario usar, cómo se da de
# baja esa entidad y qué cuelga de ella. Escribirlas por entidad serían treinta
# y seis vistas cuyo cuerpo es idéntico.


def _objeto(ficha, pk):
    return get_object_or_404(ficha.consulta(), pk=pk)


def _como_se_llama(objeto):
    return str(objeto)


@login_required
def editar(request, clave, pk=None):
    """Alta si no hay pk, edición si lo hay. La misma pantalla para las dos."""
    if not request.user.es_admin():
        return HttpResponseForbidden(MENSAJE_SOLO_ADMIN)

    ficha = _ficha(clave)
    if not ficha.se_puede_escribir:
        raise Http404(f'{ficha.titulo} no se edita desde aquí.')

    objeto = _objeto(ficha, pk) if pk else None

    if request.method == 'POST':
        formulario = ficha.formulario(request.POST, request.FILES, instance=objeto)
        if formulario.is_valid():
            guardado = formulario.save()
            # En neutro a propósito: «Materia guardado» no se dice, y el
            # género del singular no se puede deducir de su terminación.
            messages.success(
                request,
                f'Se guardó: {_como_se_llama(guardado)}.' if pk
                else f'Se agregó: {_como_se_llama(guardado)}.',
            )
            return redirect('datos:lista', clave=clave)
    else:
        formulario = ficha.formulario(instance=objeto)

    return render(request, 'datos/formulario.html', {
        'ficha': ficha,
        'formulario': formulario,
        'objeto': objeto,
        'es_edicion': objeto is not None,
    })


@login_required
@require_POST
def cambiar_estado(request, clave, pk, encender):
    """Dar de baja o volver a dar de alta. Solo por formulario, nunca por enlace."""
    if not request.user.es_admin():
        return HttpResponseForbidden(MENSAJE_SOLO_ADMIN)

    ficha = _ficha(clave)
    if not ficha.se_puede_dar_de_baja:
        raise Http404(f'{ficha.titulo} no tiene estado de alta y baja.')

    objeto = _objeto(ficha, pk)
    (ficha.dar_de_alta if encender else ficha.dar_de_baja)(objeto)
    messages.success(
        request,
        f'{_como_se_llama(objeto)}: ' + ('vuelve a estar activo.' if encender
                                         else 'queda dado de baja.'),
    )
    return redirect(request.POST.get('volver') or 'datos:lista', clave=clave)


@login_required
def eliminar(request, clave, pk):
    """Borrar de verdad, con lo que se pierde escrito delante.

    Si algo cuelga del registro, hay que escribir BORRAR. Un «¿estás seguro?»
    se aprieta sin leer; escribir una palabra, no.
    """
    if not request.user.es_admin():
        return HttpResponseForbidden(MENSAJE_SOLO_ADMIN)

    ficha = _ficha(clave)
    objeto = _objeto(ficha, pk)
    analisis = dependencias.analizar(objeto)
    arrastra = dependencias._enumerar(analisis['arrastra'])
    protegido = dependencias.frase_protegido(analisis['protegido'])

    if request.method == 'POST':
        if protegido:
            messages.error(
                request,
                f'No se puede borrar {_como_se_llama(objeto)}: {protegido} lo necesitan. '
                f'Da de baja en vez de borrar.',
            )
            return redirect('datos:lista', clave=clave)

        if arrastra and request.POST.get('confirmacion', '').strip().upper() != 'BORRAR':
            messages.error(request, 'Hay que escribir BORRAR para confirmar. No se borró nada.')
            return redirect('datos:eliminar', clave=clave, pk=pk)

        nombre = _como_se_llama(objeto)
        try:
            objeto.delete()
        except ProtectedError as error:
            # Red de seguridad: `analizar()` ya lo detecta antes de pintar el
            # botón. Si algo apareció entre medio, se dice qué, en vez de
            # mostrar el error de la base.
            cuantos = len(error.protected_objects)
            messages.error(
                request,
                f'No se puede borrar {nombre}: hay {cuantos} registro(s) que lo necesitan. '
                f'Da de baja en vez de borrar.',
            )
            return redirect('datos:lista', clave=clave)

        messages.success(request, f'Borrado: {nombre}.')
        return redirect('datos:lista', clave=clave)

    return render(request, 'datos/confirmar.html', {
        'ficha': ficha,
        'objeto': objeto,
        'nombre': _como_se_llama(objeto),
        'arrastra': arrastra,
        'protegido': protegido,
        'de_baja': bool(ficha.esta_de_baja and ficha.esta_de_baja(objeto)),
    })
