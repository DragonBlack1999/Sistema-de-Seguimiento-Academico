"""Contraseñas: cambiarla uno mismo, y pedir que se la devuelvan al carnet.

Dos caminos distintos, a propósito:

- **Cambiarla** la hace la propia persona, que ya entró. No necesita a nadie.
- **Olvidarla** no se arregla solo. La solicitud va a la secretaría, porque el
  carnet de identidad no es un secreto: está en la carpeta de cada estudiante y
  en la libreta. Si bastara con pedirlo, cualquiera que conozca el carnet de
  otro entraría con su cuenta. Lo que vuelve seguro al carnet es que alguien del
  colegio confirme que quien pide es quien dice ser.

El colegio no tiene el correo de nadie —ni de los docentes— así que el aviso no
puede ir por ahí: va a la campanita de la dirección y de la secretaría, que es
donde sí lo van a ver.
"""
from django.db import IntegrityError, transaction
from django.db.models import Q
from django.urls import reverse

from .models import SolicitudDeClave, Usuario


def buscar_usuario(escrito):
    """Encuentra a la persona por lo mismo con lo que entra al sistema.

    Estudiante por su RUDE, tutor por su carnet, docente y dirección por su
    usuario. Devuelve None si no hay nadie: quien pregunta no tiene por qué
    enterarse de si esa cuenta existe.
    """
    texto = (escrito or '').strip()
    if not texto:
        return None

    # El usuario manda sobre el carnet: si por un dato heredado el carnet de un
    # tutor coincidiera con el usuario de otra persona, gana el dueño del
    # usuario, nunca un tercero. Es la misma regla que usa el ingreso.
    return (
        Usuario.objects.filter(username__iexact=texto, is_active=True).first()
        or Usuario.objects.filter(
            Q(rol=Usuario.Rol.PADRE) & Q(ci__iexact=texto), is_active=True,
        ).order_by('pk').first()
    )


def pedir_restablecimiento(escrito):
    """Anota el pedido y avisa a la dirección. Devuelve la solicitud, o None.

    Si la persona ya tenía un pedido esperando, no se crea otro: se devuelve el
    que había. Apretar el botón diez veces no puede llenarle la bandeja a la
    secretaría ni mandarle diez avisos.
    """
    usuario = buscar_usuario(escrito)
    if usuario is None:
        return None

    try:
        with transaction.atomic():
            solicitud = SolicitudDeClave.objects.create(
                usuario=usuario, escrito=(escrito or '').strip()[:150],
            )
    except IntegrityError:
        # La constraint de «una pendiente por persona». Ya está pedido.
        return SolicitudDeClave.objects.filter(
            usuario=usuario, estado=SolicitudDeClave.Estado.PENDIENTE,
        ).first()

    _avisar_a_la_direccion(solicitud)
    return solicitud


def _avisar_a_la_direccion(solicitud):
    from apps.notificaciones.models import Notificacion
    from apps.notificaciones.services import crear_notificaciones

    quienes = Usuario.objects.filter(
        rol=Usuario.Rol.ADMIN, is_active=True,
    ).values_list('pk', flat=True)

    crear_notificaciones(
        list(quienes),
        tipo=Notificacion.Tipo.CLAVE,
        # Urgente a propósito: mientras no se atienda, esa persona no puede
        # entrar al sistema. No es algo para el resumen de la noche.
        nivel=Notificacion.Nivel.URGENTE,
        titulo='Alguien no puede entrar al sistema',
        mensaje=f'{solicitud.usuario.get_full_name() or solicitud.usuario.username} '
                f'({solicitud.usuario.get_rol_display()}) pide que le devuelvan su contraseña.',
        url=reverse('accounts:solicitudes_de_clave'),
    )


def restablecer(solicitud, por, ci=''):
    """Devuelve la contraseña de esa persona a su carnet de identidad.

    Si el colegio todavía no tiene su carnet —hoy es el caso de los 33 docentes
    y de la dirección entera, que se cargaron antes de que el colegio los
    entregara— la secretaría lo escribe al atender el pedido y queda guardado.
    Así el sistema termina de completarse por el único camino en que alguien
    tiene el documento delante.
    """
    usuario = solicitud.usuario
    nuevo = (ci or usuario.ci or '').strip()
    if not nuevo:
        raise ValueError('Falta el carnet de identidad: es lo que pasa a ser la contraseña.')

    usuario.ci = nuevo
    usuario.set_password(nuevo)
    usuario.save(update_fields=['ci', 'password'])

    solicitud.cerrar(SolicitudDeClave.Estado.ATENDIDA, por)
    _avisar_a_la_persona(usuario)
    return usuario


def _avisar_a_la_persona(usuario):
    from apps.notificaciones.models import Notificacion
    from apps.notificaciones.services import crear_notificaciones

    crear_notificaciones(
        [usuario.pk],
        tipo=Notificacion.Tipo.CLAVE,
        nivel=Notificacion.Nivel.URGENTE,
        titulo='Tu contraseña volvió a ser tu carnet de identidad',
        mensaje='Entra con él y cámbiala por una tuya.',
        url=reverse('accounts:cambiar_clave'),
    )


def pendientes():
    return SolicitudDeClave.objects.filter(
        estado=SolicitudDeClave.Estado.PENDIENTE,
    ).select_related('usuario')
