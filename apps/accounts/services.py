"""Alta y mantenimiento de las cuentas de padres/tutores.

El padre inicia sesión escribiendo su CI, pero la cuenta se guarda con el prefijo
``TUT-`` en el ``username``. Así el alta automática nunca puede tropezar con la
cuenta de un estudiante cuyo RUDE tenga forma de CI (que es un caso real: hay un
estudiante con RUDE "123456"). El backend de login resuelve al padre por su
campo ``ci``, de modo que él sigue escribiendo solo su carnet.
"""

import re

from django.core.exceptions import ValidationError
from django.db import transaction

from .models import Usuario

PREFIJO_TUTOR = 'TUT-'
_CI_VALIDO = re.compile(r'^[A-Z0-9\-]{4,20}$')


def normalizar_ci(ci):
    """'  444 5556 a ' -> '4445556A'."""
    if not ci:
        return ''
    return ''.join(str(ci).split()).upper()


def username_tutor(ci):
    return f'{PREFIJO_TUTOR}{normalizar_ci(ci)}'


def validar_ci_tutor_disponible(ci):
    """Valida el CI del tutor y devuelve su forma normalizada."""
    ci_norm = normalizar_ci(ci)
    if not ci_norm:
        return ''
    if not _CI_VALIDO.match(ci_norm):
        raise ValidationError('El CI del tutor solo admite letras, números y guiones (4 a 20 caracteres).')

    # El padre inicia sesión escribiendo su CI: no puede coincidir con el nombre
    # de usuario de un estudiante (su RUDE) ni de un profesor.
    choque = Usuario.objects.filter(username__iexact=ci_norm).exclude(rol=Usuario.Rol.PADRE).first()
    if choque is not None:
        raise ValidationError(
            f'El CI "{ci_norm}" ya es el nombre de usuario de '
            f'{choque.get_full_name() or choque.username} ({choque.get_rol_display()}). '
            'Dos personas no pueden entrar con el mismo código: revisa el dato.'
        )
    return ci_norm


@transaction.atomic
def obtener_o_crear_tutor(*, ci, nombre='', email='', telefono=''):
    """Devuelve la cuenta de padre correspondiente al CI, creándola si hace falta.

    Devuelve None si no hay CI. Si dos hermanos declaran el mismo CI, ambos
    quedan colgados de la misma cuenta.
    """
    # Se valida aquí y no solo en el formulario: así ningún camino (comando de
    # backfill, script, shell) puede crear una cuenta de tutor cuyo CI choque
    # con el nombre de usuario de un estudiante o profesor.
    ci_norm = validar_ci_tutor_disponible(ci)
    if not ci_norm:
        return None

    usuario, creado = Usuario.objects.get_or_create(
        username=username_tutor(ci_norm),
        defaults={'rol': Usuario.Rol.PADRE, 'ci': ci_norm},
    )
    if not creado and usuario.rol != Usuario.Rol.PADRE:
        raise ValidationError(f'El usuario "{usuario.username}" ya existe y no es una cuenta de tutor.')

    if creado:
        # La contraseña se fija solo al crear: editar un estudiante no debe
        # resetear la clave que el padre ya esté usando.
        usuario.set_password(ci_norm)

    partes = (nombre or '').strip().split()
    if partes:
        usuario.first_name = partes[0][:150]
        usuario.last_name = ' '.join(partes[1:])[:150]
    if email:
        usuario.email = email
    if telefono:
        usuario.telefono = telefono

    usuario.rol = Usuario.Rol.PADRE
    usuario.ci = ci_norm
    usuario.is_active = True      # reactiva una cuenta que vuelve a tener hijos
    usuario.is_staff = False      # un tutor nunca entra a /admin/
    usuario.is_superuser = False
    usuario.save()
    return usuario


def desactivar_tutor_huerfano(usuario_id, excluir_estudiante_id=None):
    """Si al tutor ya no le queda ningún hijo, desactiva la cuenta (no la borra)."""
    if not usuario_id:
        return
    from apps.academico.models import Estudiante  # import diferido: evita el ciclo entre apps

    quedan = Estudiante.objects.filter(tutor_id=usuario_id)
    if excluir_estudiante_id:
        quedan = quedan.exclude(pk=excluir_estudiante_id)
    if not quedan.exists():
        Usuario.objects.filter(pk=usuario_id).update(is_active=False)
