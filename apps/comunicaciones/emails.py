from django.conf import settings
from django.core.mail import EmailMessage


def destinatarios_estudiante(estudiante):
    """Devuelve la lista de correos (estudiante + tutor) sin duplicados ni vacíos."""
    correos = {estudiante.email_estudiante, estudiante.email_tutor}
    return [c for c in correos if c]


def enviar_correo(asunto, cuerpo, destinatarios, adjunto_bytes=None, adjunto_nombre=None):
    if not destinatarios:
        return False

    email = EmailMessage(asunto, cuerpo, settings.DEFAULT_FROM_EMAIL, destinatarios)
    if adjunto_bytes is not None:
        email.attach(adjunto_nombre, adjunto_bytes, 'application/pdf')
    email.send(fail_silently=False)
    return True


def enviar_notificacion_citacion(citacion):
    """Envía el correo de aviso de una citación (manual o automática) al estudiante y su tutor."""
    destinatarios = destinatarios_estudiante(citacion.estudiante)
    if not destinatarios:
        return False

    cuerpo = (
        f'Estimado(a) padre/madre/tutor y estudiante {citacion.estudiante.usuario.get_full_name()}:\n\n'
        f'Se les cita a una reunión en el colegio.\n\n'
        f'Fecha: {citacion.fecha}\n'
        f'Hora: {citacion.hora or "Por confirmar"}\n'
        f'Lugar: {citacion.lugar}\n'
        f'Motivo: {citacion.motivo}\n\n'
        f'Favor confirmar su asistencia.\n\n'
        f'Unidad Educativa «Eduardo Abaroa Tarde» - Nivel Secundario'
    )
    return enviar_correo(f'Citación - {citacion.estudiante.usuario.get_full_name()}', cuerpo, destinatarios)
