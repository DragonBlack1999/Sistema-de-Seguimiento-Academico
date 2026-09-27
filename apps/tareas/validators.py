from pathlib import Path
from uuid import uuid4

from django.core.exceptions import ValidationError

EXTENSIONES_PERMITIDAS = [
    '.pdf', '.doc', '.docx', '.odt', '.txt', '.rtf',
    '.jpg', '.jpeg', '.png', '.zip', '.xlsx', '.pptx',
]
TAMANO_MAXIMO_MB = 5

# Tipos que el navegador muestra tal cual, sin descargar. La lista es corta a
# propósito: nada de HTML ni SVG, que el navegador ejecutaría como página propia
# dentro de nuestro dominio. Un .docx tampoco se puede mostrar, se descarga.
TIPOS_EN_LINEA = {
    '.pdf': 'application/pdf',
    '.png': 'image/png',
    '.jpg': 'image/jpeg',
    '.jpeg': 'image/jpeg',
    '.txt': 'text/plain; charset=utf-8',
}


def tipo_en_linea(nombre):
    """Content-Type con el que ese archivo se puede mostrar sin descargar.

    Devuelve None si hay que descargarlo.
    """
    return TIPOS_EN_LINEA.get(Path(nombre or '').suffix.lower())


def validar_archivo(archivo):
    """Valida extensión y tamaño. No se confía en content_type: lo controla el cliente."""
    extension = Path(archivo.name).suffix.lower()
    if extension not in EXTENSIONES_PERMITIDAS:
        raise ValidationError(
            f'Tipo de archivo no permitido ({extension or "sin extensión"}). '
            f'Permitidos: {", ".join(EXTENSIONES_PERMITIDAS)}.'
        )
    if archivo.size > TAMANO_MAXIMO_MB * 1024 * 1024:
        raise ValidationError(f'El archivo supera el tamaño máximo de {TAMANO_MAXIMO_MB} MB.')


def ruta_enunciado(instance, filename):
    """El nombre en disco es un UUID: la URL de MEDIA no es adivinable."""
    return f'tareas/enunciados/{instance.asignacion_id}/{uuid4().hex}{Path(filename).suffix.lower()}'


def ruta_entrega(instance, filename):
    return f'tareas/entregas/{instance.tarea_id}/{uuid4().hex}{Path(filename).suffix.lower()}'
