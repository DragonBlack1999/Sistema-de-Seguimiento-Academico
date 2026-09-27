"""Llena una base de prueba con movimiento: familias, asistencia, notas y tareas.

    manage.py datos_de_ejemplo

Una base recién copiada tiene los 18 cursos y sus 402 estudiantes, pero ninguna
falta, casi ninguna nota y ningún padre registrado. Así no se puede probar nada
de lo que importa: quien entra ve pantallas vacías y no sabe si el sistema
funciona o si está roto.

Esto le da el movimiento de unas semanas de clases. No inventa personas nuevas
—los estudiantes son los que ya están— salvo los padres, que en la base real
todavía no existen.

**Solo corre sobre una base cuyo nombre lleve la palabra «prueba».**
"""
import datetime
import random

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from apps.mantenimiento.respaldos import BaseProtegida, asegurar_base_de_prueba

# Cursos que quedan con las planillas llenas: uno de cada ciclo, para poder
# mirar un primero, un intermedio y un último. Llenar los dieciocho tarda mucho
# y no muestra nada nuevo.
CURSOS_CON_NOTAS = [(1, 'A'), (3, 'A'), (6, 'A')]

TAREAS = [
    ('Resolver la guía de ejercicios', 'Los ejercicios del 1 al 10 de la guía entregada en clase.'),
    ('Investigación en grupo', 'En grupos de tres, investigar el tema visto y exponerlo.'),
    ('Informe de laboratorio', 'Redactar el informe de la práctica, con conclusiones.'),
]


class Command(BaseCommand):
    help = 'Carga familias, asistencia, notas y tareas de ejemplo en una base de prueba.'

    def add_arguments(self, parser):
        parser.add_argument('--dias', type=int, default=15,
                            help='Cuántos días de clase de asistencia generar.')
        parser.add_argument('--semilla', type=int, default=2026)

    def handle(self, *args, **opciones):
        base = settings.DATABASES['default']['NAME']
        try:
            asegurar_base_de_prueba(base)
        except BaseProtegida as error:
            raise CommandError(str(error))

        self.azar = random.Random(opciones['semilla'])
        self.stdout.write(f'Llenando «{base}» con datos de ejemplo…')

        with transaction.atomic():
            self._familias()
            self._asistencia(opciones['dias'])
            self._notas()
            self._tareas()

        self.stdout.write(self.style.SUCCESS(
            'Listo. Para que además haya avisos pendientes: manage.py alertas_diarias'
        ))

    # ─────────────────────────────── familias ────────────────────────────────

    def _familias(self):
        """Un padre o madre por estudiante; algunos con dos hijos, como pasa.

        Sin esto no se puede probar nada de lo que se construyó para la familia:
        ni el panel de «Mis hijos», ni los avisos, ni el resumen del día.
        """
        from apps.academico.models import Estudiante
        from apps.accounts.services import obtener_o_crear_tutor

        estudiantes = list(Estudiante.objects.select_related('usuario').order_by('pk'))
        creados, compartidos = 0, 0
        anterior = None

        for numero, estudiante in enumerate(estudiantes, start=1):
            if estudiante.tutor_id:
                continue
            # Uno de cada quince comparte tutor con el anterior: hermanos. Es el
            # caso que rompe las cosas (el resumen del día, por ejemplo) y tiene
            # que estar representado.
            if anterior is not None and numero % 15 == 0:
                estudiante.tutor = anterior
                compartidos += 1
            else:
                apellidos = estudiante.usuario.last_name or 'Mamani Quispe'
                nombre = self.azar.choice(['Juana', 'Rosa', 'Elena', 'Santos', 'Félix', 'Mario',
                                           'Gregoria', 'Justina', 'Pedro', 'Eulogio'])
                tutor = obtener_o_crear_tutor(
                    ci=f'95{900000 + numero}',
                    nombre=f'{nombre} {apellidos}',
                    telefono=f'7{self.azar.randint(1000000, 9999999)}',
                )
                estudiante.tutor = tutor
                anterior = tutor
                creados += 1
            estudiante.save(update_fields=['tutor'])

        self.stdout.write(f'  Familias: {creados} cuentas nuevas, {compartidos} con dos hijos.')

    # ────────────────────────────── asistencia ───────────────────────────────

    def _asistencia(self, cuantos_dias):
        """La entrada de las últimas semanas, como la marcaría regencia.

        La mayoría llega a tiempo; unos pocos con atraso y unos pocos no vienen.
        Con eso ya hay algo que mirar en las pantallas de asistencia y en los
        avisos a la familia.
        """
        from apps.academico.models import Matricula
        from apps.accounts.models import Usuario
        from apps.asistencia.models import Asistencia

        regente = Usuario.objects.filter(rol=Usuario.Rol.REGENTE).first()
        estudiantes = [m.estudiante_id for m in Matricula.objects.filter(activa=True)]
        hoy = timezone.localdate()

        dias = []
        fecha = hoy
        while len(dias) < cuantos_dias:
            fecha -= datetime.timedelta(days=1)
            if fecha.weekday() != 6:            # el domingo no hay clases
                dias.append(fecha)

        filas = []
        for fecha in dias:
            for estudiante_id in estudiantes:
                suerte = self.azar.random()
                if suerte < 0.045:
                    estado, hora = Asistencia.Estado.FALTA, None
                elif suerte < 0.115:
                    estado = Asistencia.Estado.ATRASO
                    hora = datetime.time(13, self.azar.randint(51, 59))
                else:
                    estado = Asistencia.Estado.PRESENTE
                    hora = datetime.time(13, self.azar.randint(25, 49))
                filas.append(Asistencia(
                    estudiante_id=estudiante_id, fecha=fecha, hora_llegada=hora,
                    estado=estado, registrado_por=regente,
                ))

        Asistencia.objects.bulk_create(filas, batch_size=1000, ignore_conflicts=True)
        faltas = sum(1 for f in filas if f.estado == Asistencia.Estado.FALTA)
        self.stdout.write(
            f'  Asistencia: {len(dias)} día(s) de clase, {len(filas)} marcas, {faltas} faltas.'
        )

    # ──────────────────────────────── notas ──────────────────────────────────

    def _notas(self):
        """Planillas llenas en tres cursos: primer trimestre entero y parte del segundo."""
        from apps.academico.models import AsignacionDocente, Matricula
        from apps.calificaciones.demo import cargar_trimestre

        asignaciones = list(
            AsignacionDocente.objects.filter(
                curso__grado__in=[g for g, _ in CURSOS_CON_NOTAS],
                curso__paralelo__in=[p for _, p in CURSOS_CON_NOTAS],
            ).select_related('curso', 'materia', 'profesor')
        )
        asignaciones = [a for a in asignaciones if (a.curso.grado, a.curso.paralelo) in CURSOS_CON_NOTAS]

        por_curso = {}
        for matricula in Matricula.objects.filter(activa=True).select_related('estudiante'):
            por_curso.setdefault(matricula.curso_id, []).append(matricula.estudiante)

        cuantas = 0
        for asignacion in asignaciones:
            for estudiante in por_curso.get(asignacion.curso_id, []):
                # Una campana ancha: la mayoría aprueba, algunos quedan debajo
                # de 51 para que se vea el rojo y salten los avisos.
                base = min(100, max(25, int(self.azar.gauss(68, 14))))
                cargar_trimestre(asignacion, estudiante, 1, base, self.azar,
                                 registrado_por=asignacion.profesor)
                cuantas += 1
                if self.azar.random() < 0.6:    # el segundo trimestre va a medias
                    segundo = min(100, max(25, base + self.azar.randint(-8, 10)))
                    cargar_trimestre(asignacion, estudiante, 2, segundo, self.azar,
                                     registrado_por=asignacion.profesor)
                    cuantas += 1

        cursos = ', '.join(f'{g}° {p}' for g, p in CURSOS_CON_NOTAS)
        self.stdout.write(f'  Notas: {cuantas} trimestres cargados en {cursos}.')

    # ──────────────────────────────── tareas ─────────────────────────────────

    def _tareas(self):
        """Tareas con entregas, atrasos y quien no entregó."""
        from apps.academico.models import AsignacionDocente, Matricula
        from apps.tareas.models import EntregaTarea, Tarea
        from apps.tareas import notas as notas_de_tareas

        asignaciones = [
            a for a in AsignacionDocente.objects.select_related('curso', 'materia', 'profesor')
            if (a.curso.grado, a.curso.paralelo) in CURSOS_CON_NOTAS
        ][:6]

        hoy = timezone.localdate()
        creadas, entregas = 0, 0
        for asignacion in asignaciones:
            estudiantes = [m.estudiante for m in Matricula.objects.filter(
                curso=asignacion.curso, activa=True).select_related('estudiante')]
            for numero, (titulo, descripcion) in enumerate(TAREAS):
                vence = hoy - datetime.timedelta(days=4 * (len(TAREAS) - numero) - 2)
                tarea, nueva = Tarea.objects.get_or_create(
                    asignacion=asignacion, trimestre=1, titulo=titulo,
                    defaults={
                        'descripcion': descripcion,
                        'fecha_asignacion': vence - datetime.timedelta(days=7),
                        'fecha_entrega': vence,
                        'permite_archivo': True, 'permite_atraso': True,
                        'creado_por': asignacion.profesor,
                    },
                )
                if not nueva:
                    continue
                creadas += 1
                # La tarea es también una columna de «hacer» en la planilla.
                notas_de_tareas.sincronizar_actividad(tarea, usuario=asignacion.profesor)

                for estudiante in estudiantes:
                    suerte = self.azar.random()
                    if suerte < 0.12:           # no entregó: esto dispara los avisos
                        continue
                    estado = (EntregaTarea.Estado.ATRASADA if suerte < 0.22
                              else EntregaTarea.Estado.ENTREGADA)
                    EntregaTarea.objects.update_or_create(
                        tarea=tarea, estudiante=estudiante,
                        defaults={'estado': estado,
                                  'fecha_entrega_real': timezone.now() - datetime.timedelta(
                                      days=self.azar.randint(1, 5))},
                    )
                    notas_de_tareas.guardar_puntaje(
                        tarea, estudiante.pk, self.azar.randint(22, 40),
                        usuario=asignacion.profesor,
                    )
                    entregas += 1

        self.stdout.write(f'  Tareas: {creadas} con {entregas} entregas calificadas.')
