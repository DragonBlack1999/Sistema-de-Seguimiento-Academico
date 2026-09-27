"""Llena el colegio con datos realistas para que el tablero tenga qué mostrar.

Sin esto el panel de dirección sale vacío: solo un estudiante tenía asistencia y
tres tenían notas. Aquí se generan notas y asistencia para todos, con perfiles
distintos para que el panel de "necesitan atención" tenga señal de verdad y no
sea una lista uniforme.

Es determinista (semilla fija): la demostración se ve igual cada vez que se corre,
y es idempotente.
"""

import datetime
import random
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction

from apps.academico.models import AsignacionDocente, Curso, Estudiante, Materia, Matricula
from apps.accounts.models import Usuario
from apps.asistencia.models import Asistencia
from apps.calificaciones.models import Nota

SEMANAS = 4

# Perfiles: qué proporción de estudiantes va bien, regular o mal. El panel de
# atención no sirve de nada si todos van igual.
PERFILES = [
    ('excelente', 0.20, (86, 98), 0.00),
    ('bien',      0.45, (70, 88), 0.03),
    ('justo',     0.20, (52, 68), 0.10),
    ('en riesgo', 0.15, (28, 55), 0.22),   # nota baja y muchas faltas
]


class Command(BaseCommand):
    help = 'Genera notas y asistencia realistas para todo el colegio (datos de demostración).'

    def add_arguments(self, parser):
        parser.add_argument('--semanas', type=int, default=SEMANAS,
                            help='Semanas de asistencia hacia atrás (por defecto 4).')

    @transaction.atomic
    def handle(self, *args, **opciones):
        azar = random.Random(2026)          # semilla fija: siempre el mismo resultado
        hoy = datetime.date.today()
        semanas = opciones['semanas']

        gestion = Curso.objects.order_by('-gestion__anio').first().gestion
        self.stdout.write(f'Gestión {gestion}')

        self._asignar_profesores(gestion)
        dias = self._dias_de_clase(hoy, semanas)
        self.stdout.write(f'  {len(dias)} días de clase generados ({semanas} semanas)')

        matriculas = list(
            Matricula.objects.filter(activa=True, curso__gestion=gestion)
            .select_related('estudiante__usuario', 'curso')
        )
        notas, asistencias = 0, 0

        for matricula in matriculas:
            perfil = self._perfil(azar)
            notas += self._notas(matricula, perfil, azar)
            asistencias += self._asistencia(matricula, perfil, dias, azar)

        self.stdout.write(self.style.SUCCESS(
            f'\n  {len(matriculas)} estudiantes · {notas} notas · {asistencias} registros de asistencia'
        ))
        self._resumen()

    # ------------------------------------------------------------------ partes

    def _asignar_profesores(self, gestion):
        """Los cursos nuevos no tenían materias: sin ellas no puede haber notas."""
        from apps.academico.models import Materia

        # Quién dicta qué sale de esta tabla y de ninguna otra, así que aquí se
        # reparten las materias entre los profesores que haya.
        profesores = list(Usuario.objects.filter(rol=Usuario.Rol.PROFESOR))
        materias = list(Materia.objects.all())
        creadas = 0
        if not profesores or not materias:
            return
        for curso in Curso.objects.filter(gestion=gestion):
            for indice, materia in enumerate(materias):
                _, creada = AsignacionDocente.objects.get_or_create(
                    curso=curso, materia=materia,
                    defaults={'profesor': profesores[indice % len(profesores)]},
                )
                creadas += int(creada)
        if creadas:
            self.stdout.write(f'  {creadas} asignaciones docentes creadas')

    @staticmethod
    def _dias_de_clase(hoy, semanas):
        dias, fecha = [], hoy
        while len(dias) < semanas * 5:
            if fecha.weekday() < 5:          # lunes a viernes
                dias.append(fecha)
            fecha -= datetime.timedelta(days=1)
        return sorted(dias)

    @staticmethod
    def _perfil(azar):
        tirada, acumulado = azar.random(), 0
        for nombre, proporcion, rango, falta in PERFILES:
            acumulado += proporcion
            if tirada <= acumulado:
                return nombre, rango, falta
        return PERFILES[-1][0], PERFILES[-1][2], PERFILES[-1][3]

    def _notas(self, matricula, perfil, azar):
        # Las notas se arman como en la planilla: actividades por dimensión, y de
        # ahí sale el total. Una nota escrita directa quedaría sin desglose y no
        # contaría como calificada.
        from apps.calificaciones.demo import cargar_trimestre

        _, rango, _ = perfil
        creadas = 0
        asignaciones = AsignacionDocente.objects.filter(curso=matricula.curso)
        for asignacion in asignaciones:
            # El tercer trimestre queda a medias a propósito: el año está en curso.
            for trimestre in (1, 2, 3):
                if trimestre == 3 and azar.random() < 0.4:
                    continue
                total = Decimal(str(round(azar.uniform(*rango), 2)))
                cargar_trimestre(
                    asignacion, matricula.estudiante, trimestre, total, azar,
                    registrado_por=asignacion.profesor,
                )
                creadas += 1
        return creadas

    def _asistencia(self, matricula, perfil, dias, azar):
        _, _, prob_falta = perfil
        regente = Usuario.objects.filter(rol=Usuario.Rol.REGENTE).first()
        creadas = 0
        for fecha in dias:
            tirada = azar.random()
            if tirada < prob_falta:
                estado, hora = Asistencia.Estado.FALTA, None
            elif tirada < prob_falta + 0.06:
                estado = Asistencia.Estado.ATRASO
                minuto = 51 + azar.randint(0, 34)      # 13:51 a 14:25, pasada la hora límite
                hora = datetime.time(13 + minuto // 60, minuto % 60)
            elif tirada < prob_falta + 0.08:
                estado, hora = Asistencia.Estado.LICENCIA, None
            else:
                estado = Asistencia.Estado.PRESENTE
                hora = datetime.time(13, azar.randint(20, 48))

            Asistencia.objects.update_or_create(
                estudiante=matricula.estudiante, fecha=fecha,
                defaults={
                    'gestion': matricula.curso.gestion, 'estado': estado,
                    'hora_llegada': hora, 'registrado_por': regente,
                },
            )
            creadas += 1
        return creadas

    def _resumen(self):
        from django.db.models import Avg, Count

        self.stdout.write('\n  Promedio por materia:')
        for materia in Materia.objects.all():
            prom = Nota.objects.filter(asignacion__materia=materia).aggregate(p=Avg('nota'))['p']
            if prom:
                self.stdout.write(f'    {materia}: {prom:.1f}')

        self.stdout.write('\n  Asistencia por estado:')
        for fila in Asistencia.objects.values('estado').annotate(n=Count('id')).order_by('-n'):
            self.stdout.write(f'    {fila["estado"]}: {fila["n"]}')
