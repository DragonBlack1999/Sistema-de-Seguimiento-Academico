"""Llena el entorno de un estudiante para poder probar/demostrar todo el sistema.

Es idempotente: se puede correr varias veces sin duplicar nada. Solo toca los
datos del estudiante indicado (y la gestión anterior que necesita el historial).
"""

import datetime
from decimal import Decimal

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from apps.academico.models import AsignacionDocente, Curso, Estudiante, Gestion, Matricula
from apps.accounts.models import Usuario
from apps.accounts.services import obtener_o_crear_tutor
from apps.asistencia.models import Asistencia
from apps.calificaciones.models import Nota
from apps.comunicaciones.models import Citacion
from apps.mensajeria.models import Conversacion, Mensaje
from apps.noticias.models import Noticia
from apps.notificaciones.models import Notificacion
from apps.tareas.models import EntregaTarea, Tarea


class Command(BaseCommand):
    help = 'Llena notas, asistencia, tareas, citaciones, mensajes e historial de un estudiante.'

    def add_arguments(self, parser):
        parser.add_argument('--rude', default='123456', help='RUDE del estudiante a poblar.')

    @transaction.atomic
    def handle(self, *args, **opciones):
        rude = opciones['rude']
        try:
            estudiante = Estudiante.objects.select_related('usuario').get(rude=rude)
        except Estudiante.DoesNotExist:
            raise CommandError(f'No existe un estudiante con RUDE {rude}.')

        curso = estudiante.curso_actual
        if curso is None:
            raise CommandError(f'{estudiante} no tiene curso asignado. Asignaselo antes de poblar.')

        hoy = timezone.localdate()
        admin = Usuario.objects.filter(rol=Usuario.Rol.ADMIN).order_by('pk').first()

        self._perfil(estudiante)
        self._tutor(estudiante)
        self._matricula(estudiante, curso)
        asignaciones = self._asignaciones(curso)
        self._notas(estudiante, asignaciones)
        self._regente()
        self._asistencia(estudiante, curso.gestion, hoy)
        self._tareas(estudiante, asignaciones, hoy)
        self._citaciones(estudiante, admin, hoy)
        self._historial(estudiante, curso)
        self._noticia_del_curso(curso, admin, hoy)
        self._mensajes(estudiante, asignaciones, admin)
        self._notificaciones(estudiante)

        self.stdout.write(self.style.SUCCESS(f'\nEntorno de {estudiante} listo para la demo.'))
        self._resumen(estudiante)

    # ------------------------------------------------------------------ datos

    def _perfil(self, estudiante):
        """La ficha tenia datos de relleno ('asdfghjk') y una fecha de nacimiento de este mismo año."""
        estudiante.fecha_nacimiento = datetime.date(2012, 4, 17)
        estudiante.genero = Estudiante.Genero.MASCULINO
        estudiante.nacionalidad = 'Boliviana'
        estudiante.departamento = Estudiante.Departamento.LA_PAZ
        estudiante.direccion = 'Av. Buenos Aires #1450, zona Villa Victoria'
        estudiante.celular = '71234567'
        estudiante.grupo_sanguineo = Estudiante.GrupoSanguineo.O_POS
        estudiante.save()

        usuario = estudiante.usuario
        if not usuario.email:
            usuario.email = 'omar.jamachi@ejemplo.edu.bo'
            usuario.save(update_fields=['email'])
        self.stdout.write('  Perfil del estudiante completado.')

    def _tutor(self, estudiante):
        """El CI del tutor era el mismo RUDE del estudiante, asi que no podia tener cuenta."""
        # Los datos del tutor viven en su Usuario; aqui solo se enlaza la cuenta.
        if estudiante.tutor is None or estudiante.tutor.ci == estudiante.rude:
            estudiante.tutor = obtener_o_crear_tutor(
                ci='6789012', nombre='Elena Jamachi',
                email='elena.jamachi@ejemplo.com', telefono='72345678',
            )
            estudiante.save(update_fields=['tutor'])
        tutor = estudiante.tutor
        self.stdout.write(f'  Tutor: {tutor.get_full_name()} (CI {tutor.ci}) con cuenta de acceso.')

    def _matricula(self, estudiante, curso):
        Matricula.objects.update_or_create(
            estudiante=estudiante, curso=curso, defaults={'activa': True},
        )
        self.stdout.write(f'  Matricula activa en {curso}.')

    def _asignaciones(self, curso):
        asignaciones = list(
            AsignacionDocente.objects.filter(curso=curso)
            .select_related('materia', 'profesor')
        )
        if not asignaciones:
            raise CommandError(f'{curso} no tiene materias asignadas. Crealas antes de poblar.')
        return asignaciones

    def _notas(self, estudiante, asignaciones):
        # T1 y T2 completos; T3 solo en la primera materia, para que tambien se
        # vea como luce un trimestre todavia sin calificar. Cada nota se arma con
        # sus actividades por dimension, igual que en la planilla del docente.
        import random

        from apps.calificaciones.demo import cargar_trimestre

        azar = random.Random(2026)          # la demo se ve igual cada vez que se corre
        valores = {1: [Decimal('78.00'), Decimal('85.50')], 2: [Decimal('82.00'), Decimal('69.00')]}
        total = 0
        for trimestre, notas in valores.items():
            for asignacion, nota in zip(asignaciones, notas):
                cargar_trimestre(asignacion, estudiante, trimestre, nota, azar,
                                 registrado_por=asignacion.profesor)
                total += 1
        cargar_trimestre(asignaciones[0], estudiante, 3, Decimal('90.00'), azar,
                         registrado_por=asignaciones[0].profesor)
        self.stdout.write(f'  Notas: {total + 1} registros (T1 y T2 completos, T3 parcial).')

    def _asistencia(self, estudiante, gestion, hoy):
        """Asistencia diaria, como la registra el regente en la puerta."""
        import datetime as _dt

        # Un patron fijo, no aleatorio: la demo se ve igual cada vez que se corre.
        # Las horas son del turno de la tarde: la entrada cierra a las 13:50.
        patron = (
            [(Asistencia.Estado.PRESENTE, _dt.time(13, 35))] * 4
            + [(Asistencia.Estado.FALTA, None)]
            + [(Asistencia.Estado.PRESENTE, _dt.time(13, 42))] * 3
            + [(Asistencia.Estado.ATRASO, _dt.time(14, 11))]
            + [(Asistencia.Estado.PRESENTE, _dt.time(13, 30))] * 2
            + [(Asistencia.Estado.LICENCIA, None)]
            + [(Asistencia.Estado.PRESENTE, _dt.time(13, 38))] * 3
            + [(Asistencia.Estado.FALTA, None)]
        )
        regente = Usuario.objects.filter(rol=Usuario.Rol.REGENTE).order_by('pk').first()

        fecha = hoy
        for estado, hora in patron:
            while fecha.weekday() > 4:            # solo dias de clase
                fecha -= _dt.timedelta(days=1)
            Asistencia.objects.update_or_create(
                estudiante=estudiante, fecha=fecha,
                defaults={
                    'estado': estado,
                    'hora_llegada': hora, 'registrado_por': regente,
                },
            )
            fecha -= _dt.timedelta(days=1)

        faltas = Asistencia.objects.filter(
            estudiante=estudiante, estado=Asistencia.Estado.FALTA,
        ).count()
        self.stdout.write(
            f'  Asistencia: {len(patron)} dias registrados ({faltas} faltas, 1 atraso, 1 licencia).'
        )

    def _regente(self):
        """Cuenta del regente que controla la entrada."""
        usuario, creado = Usuario.objects.get_or_create(
            username='regente',
            defaults={'rol': Usuario.Rol.REGENTE, 'first_name': 'Marta', 'last_name': 'Quispe'},
        )
        if creado:
            usuario.set_password('regente123')
            usuario.rol = Usuario.Rol.REGENTE
            usuario.save()
        self.stdout.write('  Regente: Marta Quispe (usuario "regente").')

    def _tareas(self, estudiante, asignaciones, hoy):
        asignacion = asignaciones[0]
        # Una tarea de una materia que todavia no tenga ninguna, para que el
        # listado no muestre siempre la misma. Elegir "la segunda" a ciegas
        # dejaba todas las tareas en la misma materia.
        sin_tareas = [a for a in asignaciones if not Tarea.objects.filter(asignacion=a).exists()]
        if sin_tareas:
            otra = sin_tareas[0]
            Tarea.objects.get_or_create(
                asignacion=otra, trimestre=3, titulo=f'Trabajo de investigación de {otra.materia}',
                defaults={
                    'descripcion': f'Investiga y presenta un tema de {otra.materia} en una pagina.',
                    'fecha_asignacion': hoy,
                    'fecha_entrega': hoy + datetime.timedelta(days=12),
                    'creado_por': otra.profesor,
                },
            )

        tareas = list(
            Tarea.objects.filter(asignacion__curso=asignacion.curso).order_by('trimestre', 'fecha_entrega')
        )
        # Un estado distinto por tarea, recorriendo todos los casos posibles.
        # Las notas van sobre 40, que es lo que vale una tarea dentro de "hacer",
        # y se guardan donde viven: en la columna de la tarea.
        from apps.tareas.notas import guardar_puntaje

        guiones = [
            (EntregaTarea.Estado.NO_ENTREGADA, None, 'No presento el trabajo.'),
            (EntregaTarea.Estado.ENTREGADA, Decimal('35'), 'Buen desarrollo, cuida el orden.'),
            (EntregaTarea.Estado.ENTREGADA, Decimal('30'), 'Correcto, falto justificar el paso 3.'),
            (EntregaTarea.Estado.ATRASADA, Decimal('24'), 'Entregado fuera de plazo.'),
            (EntregaTarea.Estado.PENDIENTE, None, ''),
        ]
        for tarea, (estado, nota, observacion) in zip(tareas, guiones):
            entregada = estado in (EntregaTarea.Estado.ENTREGADA, EntregaTarea.Estado.ATRASADA)
            EntregaTarea.objects.update_or_create(
                tarea=tarea, estudiante=estudiante,
                defaults={
                    'estado': estado,
                    'observacion': observacion,
                    'comentario_estudiante': 'Trabajo realizado en el cuaderno.' if entregada else '',
                    'fecha_entrega_real': timezone.now() if entregada else None,
                },
            )
            guardar_puntaje(tarea, estudiante.pk, nota, tarea.asignacion.profesor)
        self.stdout.write(f'  Tareas: {len(tareas)} visibles, con entregas en distintos estados.')

    def _citaciones(self, estudiante, admin, hoy):
        Citacion.objects.update_or_create(
            estudiante=estudiante, motivo='Seguimiento de rendimiento en Matemática.',
            defaults={
                'fecha': hoy + datetime.timedelta(days=5),
                'hora': datetime.time(10, 30),
                'lugar': 'Dirección del colegio',
                'estado': Citacion.Estado.PENDIENTE,
                'generado_por': admin,
            },
        )
        Citacion.objects.update_or_create(
            estudiante=estudiante, motivo='Entrega de boletín del primer trimestre.',
            defaults={
                'fecha': hoy - datetime.timedelta(days=20),
                'hora': datetime.time(9, 0),
                'lugar': 'Sala de profesores',
                'estado': Citacion.Estado.ATENDIDA,
                'observaciones': 'Asistió la madre del estudiante.',
                'generado_por': admin,
            },
        )
        self.stdout.write('  Citaciones: 1 pendiente y 1 atendida.')

    def _historial(self, estudiante, curso_actual):
        """Gestion anterior con notas, para que "Historial academico" no salga vacio."""
        anterior, _ = Gestion.objects.get_or_create(
            anio=curso_actual.gestion.anio - 1, defaults={'activa': False},
        )
        curso_anterior, _ = Curso.objects.get_or_create(
            gestion=anterior, nivel=Curso.Nivel.PRIMARIA, grado=6, paralelo='A',
        )
        Matricula.objects.update_or_create(
            estudiante=estudiante, curso=curso_anterior, defaults={'activa': False},
        )

        notas_previas = {'Matematica': Decimal('71.00'), 'Lenguaje': Decimal('80.00')}
        for asignacion_actual in AsignacionDocente.objects.filter(
            curso=curso_actual
        ).select_related('materia', 'profesor'):
            asignacion, _ = AsignacionDocente.objects.get_or_create(
                curso=curso_anterior, materia=asignacion_actual.materia,
                defaults={'profesor': asignacion_actual.profesor},
            )
            base = notas_previas.get(asignacion_actual.materia.nombre, Decimal('75.00'))
            for trimestre in (1, 2, 3):
                Nota.objects.update_or_create(
                    asignacion=asignacion, estudiante=estudiante, trimestre=trimestre,
                    defaults={'nota': base + trimestre, 'registrado_por': asignacion.profesor},
                )
        self.stdout.write(f'  Historial: gestion {anterior.anio} en {curso_anterior} con notas completas.')

    def _noticia_del_curso(self, curso, admin, hoy):
        Noticia.objects.get_or_create(
            titulo=f'Salida educativa de {curso.grado}° {curso.paralelo}',
            defaults={
                'cuerpo': 'Visitaremos el Museo Nacional de Arqueologia. Traer credencial y merienda.',
                'tipo': Noticia.Tipo.ACTIVIDAD,
                'curso': curso,
                'fecha_evento': hoy + datetime.timedelta(days=9),
                'publicada': True,
                'publicado_por': admin,
            },
        )
        self.stdout.write('  Noticia dirigida a su curso publicada.')

    def _mensajes(self, estudiante, asignaciones, admin):
        yo = estudiante.usuario
        guiones = [
            (asignaciones[0].profesor, [
                (yo, f'Buenas tardes, ¿la tarea de {asignaciones[0].materia} se entrega impresa?'),
                (asignaciones[0].profesor, 'Buenas tardes. Puede ser a mano, en hoja cuadriculada.'),
            ]),
        ]
        if admin is not None:
            guiones.append((admin, [
                (admin, 'Omar, recuerda traer la fotocopia de tu carnet para completar tu expediente.'),
            ]))

        for otro, lineas in guiones:
            hilo, _ = Conversacion.entre(yo, otro)
            for autor, cuerpo in lineas:
                destinatario = otro if autor == yo else yo
                mensaje, creado = Mensaje.objects.get_or_create(
                    conversacion=hilo, autor=autor, cuerpo=cuerpo,
                    defaults={'destinatario': destinatario, 'leido': autor == yo},
                )
                if creado:
                    hilo.fecha_ultimo_mensaje = mensaje.fecha_envio
            hilo.save(update_fields=['fecha_ultimo_mensaje'])
        self.stdout.write('  Mensajeria: conversaciones con su profesor y con la direccion.')

    def _notificaciones(self, estudiante):
        avisos = [
            (Notificacion.Tipo.NOTICIA, 'Nueva actividad: salida educativa', '/noticias/'),
            (Notificacion.Tipo.TAREA, 'Tienes una tarea nueva por entregar', '/tareas/mis-tareas/'),
            (Notificacion.Tipo.CITACION, 'Tienes una citacion pendiente', '/comunicaciones/citaciones/'),
        ]
        for tipo, titulo, url in avisos:
            Notificacion.objects.get_or_create(
                usuario=estudiante.usuario, tipo=tipo, titulo=titulo,
                defaults={'url': url, 'leida': False},
            )
        self.stdout.write('  Notificaciones: 3 sin leer en la campanita.')

    def _resumen(self, estudiante):
        self.stdout.write(
            f'\n  Ingresa con  usuario: {estudiante.rude}   contrasena: {estudiante.usuario.ci}'
        )
        if estudiante.tutor_id:
            self.stdout.write(
                f'  Su tutor entra con  usuario: {estudiante.tutor.ci}   contrasena: {estudiante.tutor.ci}'
            )
