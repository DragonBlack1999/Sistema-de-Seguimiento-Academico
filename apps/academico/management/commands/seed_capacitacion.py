"""Crea los cursos de 3ro y 4to de Secundaria que pasan clases de capacitación.

Esos cursos no entran por la puerta el día de su capacitación: su asistencia la
registra el administrador. Es idempotente: se puede correr varias veces.
"""

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.academico.models import Curso, DiaCapacitacion, Estudiante, Gestion, Horario, Matricula
from apps.accounts.models import Usuario

# Cada paralelo con su día. 4to B lleva dos días a propósito, para que el caso
# de "varios días por paralelo" quede cubierto en la demostración.
CURSOS = [
    (3, 'A', [Horario.Dia.LUNES],                        ['Lucía Vargas', 'Diego Choque', 'Ana Poma']),
    (3, 'B', [Horario.Dia.MARTES],                       ['Marco Flores', 'Sofía Huanca']),
    (4, 'A', [Horario.Dia.MIERCOLES],                    ['Pablo Ticona', 'Valeria Nina', 'Jorge Apaza']),
    (4, 'B', [Horario.Dia.JUEVES, Horario.Dia.VIERNES],  ['Camila Mendoza', 'Luis Colque']),
]


class Command(BaseCommand):
    help = 'Crea 3ro y 4to de Secundaria con sus días de capacitación y estudiantes de prueba.'

    @transaction.atomic
    def handle(self, *args, **opciones):
        gestion = Gestion.objects.filter(activa=True).order_by('-anio').first()
        if gestion is None:
            raise CommandError('No hay ninguna gestión activa. Créala antes de correr este comando.')

        contador = 0
        for grado, paralelo, dias, nombres in CURSOS:
            curso, _ = Curso.objects.get_or_create(
                gestion=gestion, nivel=Curso.Nivel.SECUNDARIA, grado=grado, paralelo=paralelo,
            )
            for dia in dias:
                DiaCapacitacion.objects.get_or_create(curso=curso, dia=dia)

            etiquetas = ', '.join(
                dict(Horario.Dia.choices)[d] for d in dias
            )
            self.stdout.write(f'  {curso} -> capacitación: {etiquetas}')

            for indice, nombre in enumerate(nombres, start=1):
                contador += 1
                self._estudiante(nombre, curso, gestion, f'EST-{grado}{paralelo}{indice:02d}')

        self.stdout.write(self.style.SUCCESS(
            f'\nListo: {len(CURSOS)} cursos de capacitación con {contador} estudiantes.'
        ))
        self.stdout.write(
            '  Entra como "admin" y abre "Capacitación" para registrar su asistencia.'
        )

    def _estudiante(self, nombre_completo, curso, gestion, rude):
        nombres, apellidos = nombre_completo.split(' ', 1)
        # El CI hace de contraseña, igual que para el resto de estudiantes.
        ci = f'90{rude[-4:]}'

        usuario, creado = Usuario.objects.get_or_create(
            username=rude,
            defaults={
                'rol': Usuario.Rol.ESTUDIANTE,
                'first_name': nombres,
                'last_name': apellidos,
                'ci': ci,
            },
        )
        if creado:
            usuario.set_password(ci)
            usuario.save()

        estudiante, _ = Estudiante.objects.get_or_create(
            usuario=usuario, defaults={'rude': rude},
        )
        # El curso no se guarda en el estudiante: lo determina esta matricula.
        Matricula.objects.update_or_create(
            estudiante=estudiante, curso=curso, defaults={'activa': True},
        )
