"""Qué se perdería al borrar un registro, y qué lo impide.

Borrar en cascada es silencioso: Django borra lo que cuelga sin decir qué era.
Quitar un curso se lleva sus matrículas, y con ellas las notas y las tareas de
un año entero. Antes de ofrecer el botón hay que poder decir cuánto se pierde.

Dos trampas, las dos encontradas probando:

1. **`Collector.data` no lo tiene todo.** Lo que Django puede borrar de una
   sola sentencia va a `collector.fast_deletes`, una lista de *querysets*
   aparte (`django/db/models/deletion.py`). Contar solo `data` dice de menos.
2. **`collect()` revienta si algo está protegido.** Un curso con una noticia
   tiene un `PROTECT` encima: el coleccionista lanza `ProtectedError` en vez de
   devolver una cuenta. Hay que atraparlo y decir quién lo protege, porque eso
   no es un error del programa: es la respuesta.

   (El `NestedObjects` del admin no hace ninguna de las dos cosas: se traga la
   protección y desactiva los borrados rápidos, al precio de traerse a memoria
   los 2353 puntajes de un curso para contar hasta 2353.)
"""
from django.db import router
from django.db.models.deletion import Collector, ProtectedError


def _por_modelo(pares):
    nombres = []
    for modelo, cuantos in pares.items():
        etiqueta = (modelo._meta.verbose_name if cuantos == 1
                    else modelo._meta.verbose_name_plural)
        nombres.append((str(etiqueta), cuantos))
    return sorted(nombres, key=lambda par: -par[1])


def analizar(objeto):
    """Qué arrastra este registro y qué impide borrarlo.

    Devuelve `{'arrastra': [(nombre, cuántos)], 'protegido': [(nombre, cuántos)]}`.
    Con `protegido` no vacío, borrar es imposible: hay que dar de baja.
    """
    coleccionista = Collector(using=router.db_for_write(objeto.__class__))

    try:
        coleccionista.collect([objeto])
    except ProtectedError as error:
        cuenta = {}
        for protegido in error.protected_objects:
            modelo = protegido.__class__
            cuenta[modelo] = cuenta.get(modelo, 0) + 1
        return {'arrastra': [], 'protegido': _por_modelo(cuenta)}

    cuenta = {}
    for modelo, instancias in coleccionista.data.items():
        cuantos = len(instancias)
        if modelo is objeto.__class__:
            cuantos -= 1          # el propio objeto no es daño colateral
        if cuantos > 0:
            cuenta[modelo] = cuenta.get(modelo, 0) + cuantos

    # Lo que se borra de una sentencia no aparece arriba. Es donde viven las
    # notas y los puntajes, que son justo lo que no se puede perder sin saberlo.
    for consulta in coleccionista.fast_deletes:
        cuantos = consulta.count()
        if cuantos:
            modelo = consulta.model
            cuenta[modelo] = cuenta.get(modelo, 0) + cuantos

    return {'arrastra': _por_modelo(cuenta), 'protegido': []}


def _enumerar(pares):
    partes = [f'{cuantos} {nombre.lower()}' for nombre, cuantos in pares]
    if not partes:
        return ''
    if len(partes) == 1:
        return partes[0]
    return ', '.join(partes[:-1]) + ' y ' + partes[-1]


def frase(objeto):
    """«23 notas, 180 puntajes y 1 matrícula», o '' si no cuelga nada."""
    return _enumerar(analizar(objeto)['arrastra'])


def frase_protegido(pares):
    """«1 noticia», para decir qué impide borrar."""
    return _enumerar(pares)
