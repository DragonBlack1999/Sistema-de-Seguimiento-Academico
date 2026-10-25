from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils import timezone


class Usuario(AbstractUser):
    class Rol(models.TextChoices):
        ADMIN = 'ADMIN', 'Administrador'
        PROFESOR = 'PROFESOR', 'Profesor'
        ESTUDIANTE = 'ESTUDIANTE', 'Estudiante'
        PADRE = 'PADRE', 'Padre/Tutor'
        REGENTE = 'REGENTE', 'Regente'

    rol = models.CharField(max_length=12, choices=Rol.choices)
    ci = models.CharField('Carnet de identidad', max_length=20, blank=True)
    telefono = models.CharField(max_length=20, blank=True)
    # Qué materias dicta un profesor sale de `AsignacionDocente`: trece de los 33
    # dan dos o tres, así que una sola "materia principal" aquí era engañosa
    # además de repetida.

    def es_admin(self):
        return self.rol == self.Rol.ADMIN

    def es_profesor(self):
        return self.rol == self.Rol.PROFESOR

    def es_estudiante(self):
        return self.rol == self.Rol.ESTUDIANTE

    def es_padre(self):
        return self.rol == self.Rol.PADRE

    def es_regente(self):
        return self.rol == self.Rol.REGENTE

    class Meta(AbstractUser.Meta):
        constraints = [
            # Un CI identifica a un solo tutor: es lo que el padre escribe al entrar.
            models.UniqueConstraint(
                fields=['ci'], condition=models.Q(rol='PADRE'), name='unico_ci_por_tutor',
            ),
        ]

    def __str__(self):
        return f'{self.get_full_name() or self.username} ({self.get_rol_display()})'

    def tiene_clave_propia(self):
        """¿Esta persona puso una contraseña suya, distinta de su carnet?

        De esto depende que el carnet siga sirviendo para entrar. Mientras la
        contraseña guardada **sea** el carnet, el estudiante entra con su RUDE y
        su carnet como siempre; en cuanto pone una suya, el carnet deja de
        abrirle la puerta. Si no, cambiar la contraseña no cambiaría nada y la
        pantalla estaría mintiendo.
        """
        ci = (self.ci or '').strip()
        if not self.has_usable_password():
            # Cuentas sin contraseña de verdad: las de los tutores de la base
            # de prueba, que entran solo por carnet.
            return False
        return not ci or not self.check_password(ci)


class SolicitudDeClave(models.Model):
    """Alguien olvidó su contraseña y pide que se la devuelvan a su carnet.

    No se restablece sola. La solicitud llega a la secretaría, que es quien
    conoce a la persona: el carnet de identidad no es un secreto —está en la
    carpeta de cada estudiante— así que cualquiera podría pedir el de otro y
    entrar con él. Lo que vuelve seguro al carnet es que alguien del colegio
    confirme que quien pide es quien dice ser.
    """

    class Estado(models.TextChoices):
        PENDIENTE = 'PENDIENTE', 'Esperando a la secretaría'
        ATENDIDA = 'ATENDIDA', 'Contraseña restablecida'
        RECHAZADA = 'RECHAZADA', 'Rechazada'

    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='solicitudes_de_clave',
    )
    # Lo que la persona escribió para identificarse. Si no coincide con su
    # usuario (escribió el carnet de su hijo, por ejemplo), a la secretaría le
    # sirve para entender qué pasó.
    escrito = models.CharField('Lo que escribió', max_length=150)
    estado = models.CharField(max_length=10, choices=Estado.choices, default=Estado.PENDIENTE)
    fecha = models.DateTimeField(auto_now_add=True)
    atendida_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='solicitudes_de_clave_atendidas',
    )
    fecha_atendida = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-fecha']
        verbose_name = 'Solicitud de contraseña'
        verbose_name_plural = 'Solicitudes de contraseña'
        constraints = [
            # Una pendiente por persona: apretar diez veces el botón no puede
            # llenarle la bandeja a la secretaría.
            models.UniqueConstraint(
                fields=['usuario'], condition=models.Q(estado='PENDIENTE'),
                name='una_solicitud_de_clave_pendiente',
            ),
        ]

    def __str__(self):
        return f'{self.usuario} · {self.get_estado_display()}'

    def cerrar(self, estado, por):
        self.estado = estado
        self.atendida_por = por
        self.fecha_atendida = timezone.now()
        self.save(update_fields=['estado', 'atendida_por', 'fecha_atendida'])
