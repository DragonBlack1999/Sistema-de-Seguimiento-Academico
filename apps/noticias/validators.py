from pathlib import Path
from uuid import uuid4

from django.core.exceptions import ValidationError

EXTENSIONES_IMAGEN = ['.jpg', '.jpeg', '.png', '.webp']
TAMANO_MAXIMO_IMAGEN_MB = 3


def _ruta(carpeta, filename):
    """Nombre en disco con UUID: la URL de MEDIA no queda adivinable."""
    return f'noticias/{carpeta}/{uuid4().hex}{Path(filename).suffix.lower()}'


def ruta_imagen_noticia(instance, filename):
    return _ruta('imagenes', filename)


def ruta_adjunto_noticia(instance, filename):
    return _ruta('adjuntos', filename)


def validar_imagen(archivo):
    extension = Path(archivo.name).suffix.lower()
    if extension not in EXTENSIONES_IMAGEN:
        raise ValidationError(
            f'Formato de imagen no permitido ({extension or "sin extensión"}). '
            f'Usa {", ".join(EXTENSIONES_IMAGEN)}.'
        )
    if archivo.size > TAMANO_MAXIMO_IMAGEN_MB * 1024 * 1024:
        raise ValidationError(f'La imagen no puede pesar más de {TAMANO_MAXIMO_IMAGEN_MB} MB.')
