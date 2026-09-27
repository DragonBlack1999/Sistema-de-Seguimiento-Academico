from django.contrib.auth.models import AbstractUser
from django.db import models


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
