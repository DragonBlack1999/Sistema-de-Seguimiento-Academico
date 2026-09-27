"""Búsqueda de estudiantes por nombre, apellido, RUDE o curso.

Dos cosas que el buscador resuelve a propósito:

- **El orden no importa.** "Condori María" y "María Condori" encuentran a la
  misma persona, porque cada palabra se busca por separado en todos los datos.
- **Las tildes no importan.** "maria" encuentra "María" sin necesidad de
  instalar extensiones en PostgreSQL.
"""
import re
import unicodedata

from django.db.models import Q

from .models import Estudiante

# Letras del español que deben encontrarse se escriba o no la tilde.
# La consulta usa `iregex`, que ya ignora mayúsculas, así que basta con minúsculas.
_EQUIVALENCIAS = {
    'a': 'aáàäâ',
    'e': 'eéèëê',
    'i': 'iíìïî',
    'o': 'oóòöô',
    'u': 'uúùüû',
    'n': 'nñ',
    'c': 'cç',
}


def _letra_base(caracter):
    """Devuelve la letra sin tilde de un carácter: 'á' -> 'a', 'Ñ' -> 'n'."""
    return unicodedata.normalize('NFD', caracter)[0].lower()


def _patron_flexible(termino):
    """Convierte un término en una expresión regular que ignora las tildes.

    Los caracteres que no son letras acentuables se escapan, de modo que lo que
    escriba el usuario nunca se interpreta como expresión regular.
    """
    partes = []
    for caracter in termino:
        equivalentes = _EQUIVALENCIAS.get(_letra_base(caracter))
        partes.append(f'[{equivalentes}]' if equivalentes else re.escape(caracter))
    return ''.join(partes)


def buscar_estudiantes(consulta, queryset=None):
    """Filtra estudiantes exigiendo que *cada* palabra aparezca en algún dato.

    Al pedir todas las palabras por separado (y no la frase completa), el orden
    en que se escriban deja de importar.
    """
    if queryset is None:
        queryset = Estudiante.objects.all()

    for termino in (consulta or '').split():
        patron = _patron_flexible(termino)
        criterio = (
            Q(usuario__first_name__iregex=patron)
            | Q(usuario__last_name__iregex=patron)
            | Q(matriculas__activa=True, matriculas__curso__nivel__iregex=patron)
            | Q(matriculas__activa=True, matriculas__curso__paralelo__iexact=termino)
        )

        # Un solo carácter dentro del RUDE es demasiado ambiguo: al buscar
        # "2 secundaria" el "2" traería a todos los RUDE que contengan un 2.
        if len(termino) > 1:
            criterio |= Q(rude__iregex=patron)

        # "2", "2do" y "2°" deben encontrar a los estudiantes de segundo grado.
        grado = re.match(r'\d+', termino)
        if grado:
            criterio |= Q(matriculas__activa=True, matriculas__curso__grado=int(grado.group()))

        # El curso llega por la matrícula (una fila por año), así que un mismo
        # estudiante puede aparecer repetido sin el distinct.
        queryset = queryset.filter(criterio).distinct()

    return queryset


def buscar_por_nombre(consulta, queryset):
    """Usuarios cuyo nombre o apellido contiene cada palabra, con las mismas reglas:
    sin importar el orden ni las tildes. Sirve para quien no es estudiante (un
    padre no tiene RUDE ni curso)."""
    for termino in (consulta or '').split():
        patron = _patron_flexible(termino)
        queryset = queryset.filter(Q(first_name__iregex=patron) | Q(last_name__iregex=patron))
    return queryset
