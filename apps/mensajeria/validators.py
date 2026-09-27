from pathlib import Path
from uuid import uuid4

from django.core.exceptions import ValidationError

EXTENSIONES_PERMITIDAS = ['.pdf', '.jpg', '.jpeg', '.png']
TAMANO_MAXIMO_MB = 5


def validar_adjunto(archivo):
    """Valida extensión y tamaño. No se confía en content_type: lo controla el cliente."""
    extension = Path(archivo.name).suffix.lower()
    if extension not in EXTENSIONES_PERMITIDAS:
        raise ValidationError(
            f'Tipo de archivo no permitido ({extension or "sin extensión"}). '
            f'Permitidos: {", ".join(EXTENSIONES_PERMITIDAS)}.'
        )
    if archivo.size > TAMANO_MAXIMO_MB * 1024 * 1024:
        raise ValidationError(f'El archivo supera el tamaño máximo de {TAMANO_MAXIMO_MB} MB.')


def ruta_adjunto_mensaje(instance, filename):
    """El nombre en disco es un UUID: la URL de MEDIA no es adivinable."""
    return f'mensajeria/{instance.conversacion_id}/{uuid4().hex}{Path(filename).suffix.lower()}'
