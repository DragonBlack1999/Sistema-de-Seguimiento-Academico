import datetime

from django.core.management.base import BaseCommand

from apps.academico.models import (
    AsignacionDocente, Curso, Estudiante, Gestion, Horario, Materia, Matricula, Periodo,
)
from apps.accounts.models import Usuario
from apps.accounts.services import obtener_o_crear_tutor


class Command(BaseCommand):
    help = 'Crea un superusuario y datos de ejemplo (gestión, cursos, materias, profesores, estudiante) para probar el sistema.'

    def handle(self, *args, **options):
        if not Usuario.objects.filter(username='admin').exists():
            admin_user = Usuario.objects.create_superuser(username='admin', email='', password='admin123456')
            admin_user.rol = Usuario.Rol.ADMIN
            admin_user.first_name = 'Administrador'
            admin_user.save()

        gestion, _ = Gestion.objects.update_or_create(anio=2026, defaults={'activa': True})

        curso, _ = Curso.objects.update_or_create(
            gestion=gestion, nivel=Curso.Nivel.SECUNDARIA, grado=1, paralelo='A'
        )
        curso2, _ = Curso.objects.update_or_create(
            gestion=gestion, nivel=Curso.Nivel.SECUNDARIA, grado=2, paralelo='A'
        )

        materia_mat, _ = Materia.objects.get_or_create(nombre='Matemática')
        materia_len, _ = Materia.objects.get_or_create(nombre='Lenguaje')

        # jperez da Matemática, a dos cursos distintos (una sola materia, varios cursos).
        profesor, creado = Usuario.objects.get_or_create(
            username='jperez',
            defaults={
                'first_name': 'Juan', 'last_name': 'Pérez', 'rol': Usuario.Rol.PROFESOR,
                'ci': '5551234', 'is_staff': True,
            },
        )
        if creado:
            profesor.set_password('profesor123')
        profesor.save()

        # Segundo profesor de prueba: da Lenguaje (una materia distinta a jperez).
        profesor_len, creado = Usuario.objects.get_or_create(
            username='arojas',
            defaults={
                'first_name': 'Ana', 'last_name': 'Rojas', 'rol': Usuario.Rol.PROFESOR,
                'ci': '6662345', 'is_staff': True,
            },
        )
        if creado:
            profesor_len.set_password('profesor123')
        profesor_len.save()

        usuario_est, creado = Usuario.objects.get_or_create(
            username='EST-0001',
            defaults={
                'first_name': 'María', 'last_name': 'Condori', 'rol': Usuario.Rol.ESTUDIANTE,
                'ci': '9998887', 'email': 'omar.99.marca@gmail.com',
            },
        )
        if creado:
            usuario_est.set_password('9998887')
        usuario_est.email = 'omar.99.marca@gmail.com'
        usuario_est.save()

        estudiante, _ = Estudiante.objects.update_or_create(
            usuario=usuario_est, defaults={'rude': 'EST-0001'},
        )
        # El curso vive en la matricula y los datos del tutor en su Usuario.
        estudiante.tutor = obtener_o_crear_tutor(
            ci='4445556', nombre='Rosa Condori',
            email='omar.99.marca@gmail.com', telefono='70011122',
        )
        estudiante.save(update_fields=['tutor'])

        Matricula.objects.update_or_create(
            estudiante=estudiante, curso=curso, defaults={'activa': True},
        )

        # jperez (Matemática) en dos cursos distintos.
        asignacion_mat, _ = AsignacionDocente.objects.update_or_create(
            profesor=profesor, curso=curso, materia=materia_mat,
        )
        asignacion_mat2, _ = AsignacionDocente.objects.update_or_create(
            profesor=profesor, curso=curso2, materia=materia_mat,
        )
        # arojas (Lenguaje) en el primer curso.
        asignacion_len, _ = AsignacionDocente.objects.update_or_create(
            profesor=profesor_len, curso=curso, materia=materia_len,
        )

        # Primero la fila de la grilla, despues la clase que la ocupa. Los
        # periodos no llevan hora: se identifican por su orden en el dia.
        def franja(curso_del_periodo, orden, etiqueta):
            periodo, _ = Periodo.objects.get_or_create(
                curso=curso_del_periodo, orden=orden, defaults={'etiqueta': etiqueta},
            )
            return periodo

        Horario.objects.update_or_create(
            asignacion=asignacion_mat, dia=Horario.Dia.LUNES,
            periodo=franja(curso, 0, '1°'),
            defaults={'aula': 'Aula 3'},
        )
        Horario.objects.update_or_create(
            asignacion=asignacion_mat2, dia=Horario.Dia.LUNES,
            periodo=franja(curso2, 0, '1°'),
            defaults={'aula': 'Aula 5'},
        )
        Horario.objects.update_or_create(
            asignacion=asignacion_len, dia=Horario.Dia.MARTES,
            periodo=franja(curso, 1, '2°'),
            defaults={'aula': 'Aula 3'},
        )

        self.stdout.write(self.style.SUCCESS('Datos de prueba creados correctamente.'))
        self.stdout.write('Admin -> usuario: admin / contraseña: admin123456')
        self.stdout.write('Profesor (Matemática, 2 cursos) -> usuario: jperez / contraseña: profesor123')
        self.stdout.write('Profesor (Lenguaje) -> usuario: arojas / contraseña: profesor123')
        self.stdout.write('Estudiante -> usuario (RUDE): EST-0001 / contraseña (CI): 9998887')
