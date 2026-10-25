from django.contrib.auth import get_user_model
from django.contrib.auth.backends import BaseBackend


class CarnetBackend(BaseBackend):
    """Ingreso por carnet de identidad, comparado contra el campo `ci`.

    - Estudiante: usuario = su RUDE, contraseña = su CI.
    - Padre/tutor: usuario = su CI, contraseña = su CI. Su cuenta se guarda con
      el prefijo `TUT-` en el username, así que se lo busca por el campo `ci`.

    Se resuelve primero al estudiante: si por datos heredados hubiera una
    ambigüedad, gana el dueño del username, nunca un tercero.

    **El carnet abre la puerta solo mientras la persona no haya puesto una
    contraseña suya.** En cuanto la pone, este camino deja de aceptarla y el
    ingreso pasa por el camino normal. Sin esto, «cambiar mi contraseña» no
    cambiaría nada para los estudiantes y los tutores: su carnet seguiría
    entrando igual, y la pantalla estaría mintiendo.
    """

    def authenticate(self, request, username=None, password=None, **kwargs):
        if not username or not password:
            return None

        Usuario = get_user_model()
        identificador = username.strip()
        clave = password.strip().upper()

        usuario = Usuario.objects.filter(
            username__iexact=identificador, rol=Usuario.Rol.ESTUDIANTE,
        ).first()
        if usuario is None:
            usuario = Usuario.objects.filter(
                rol=Usuario.Rol.PADRE, ci__iexact=identificador,
            ).order_by('pk').first()

        if usuario is None or not usuario.is_active:
            return None

        ci = (usuario.ci or '').strip().upper()
        if ci and ci == clave and not usuario.tiene_clave_propia():
            return usuario
        return None

    def get_user(self, user_id):
        Usuario = get_user_model()
        try:
            return Usuario.objects.get(pk=user_id)
        except Usuario.DoesNotExist:
            return None
