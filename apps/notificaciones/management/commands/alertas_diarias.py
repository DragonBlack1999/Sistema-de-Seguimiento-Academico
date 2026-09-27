"""La revisión de cada noche: lo que nadie dispara con un clic.

Una falta o una nota baja ocurren cuando alguien las registra, y ahí mismo se
avisa. Pero "no entregó y ya venció el plazo" o "su promedio no alcanza" no son
momentos: son estados que hay que ir a mirar. Eso hace este comando.

Se corre una vez al día (en el servidor, a una hora fija). Al final manda el
resumen: un solo mensaje al celular por persona con todo lo del día.

    manage.py alertas_diarias
    manage.py alertas_diarias --sin-resumen    (solo revisa, no manda nada)
"""
import collections

from django.core.management.base import BaseCommand, CommandError
from django.db.models import Avg, Count
from django.utils import timezone

from apps.academico.models import Matricula
from apps.asistencia.services import gestion_vigente
from apps.calificaciones.models import NOTA_APROBACION, Nota
from apps.comunicaciones.alertas import (
    avisar_materia_reprobada, avisar_racha_tareas, avisar_tarea_sin_entregar,
)
from apps.notificaciones.services import enviar_resumen_diario
from apps.tareas.models import EntregaTarea, Tarea

# Con una sola nota no se puede decir que alguien "está reprobando": puede ser
# un mal día. Con dos trimestres, ya es una tendencia.
TRIMESTRES_PARA_HABLAR_DE_REPROBAR = 2


class Command(BaseCommand):
    help = 'Revisa tareas vencidas, rachas y promedios, y manda el resumen diario.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--sin-resumen', action='store_true',
            help='Solo revisa y crea los avisos; no manda nada al celular.',
        )

    def handle(self, *args, **opciones):
        gestion = gestion_vigente()
        if gestion is None:
            raise CommandError('No hay ninguna gestión escolar registrada.')

        self.stdout.write(f'Revisando la gestión {gestion.anio}…')
        pendientes_por_estudiante = self._tareas_vencidas(gestion)
        self._rachas(pendientes_por_estudiante)
        self._materias_reprobadas(gestion)

        if opciones['sin_resumen']:
            self.stdout.write(self.style.WARNING('Resumen no enviado (--sin-resumen).'))
            return
        personas = enviar_resumen_diario()
        self.stdout.write(self.style.SUCCESS(f'Resumen del día enviado a {personas} persona(s).'))

    # ────────────────────────── tareas vencidas ──────────────────────────

    def _tareas_vencidas(self, gestion):
        """Avisa por cada tarea cuyo plazo venció y sigue sin entregar.

        Devuelve cuántas acumula cada estudiante, que es lo que mira la racha.
        """
        hoy = timezone.localdate()
        tareas = list(
            Tarea.objects.filter(asignacion__curso__gestion=gestion, fecha_entrega__lt=hoy)
            .select_related('asignacion__curso', 'asignacion__materia')
        )
        if not tareas:
            self.stdout.write('  Tareas vencidas: ninguna todavía.')
            return {}

        matriculas = collections.defaultdict(list)
        for matricula in (
            Matricula.objects.filter(activa=True, curso__gestion=gestion)
            .select_related('estudiante__usuario')
        ):
            matriculas[matricula.curso_id].append(matricula)

        # Calificada = tiene puntaje en la columna de esa tarea.
        from apps.calificaciones.models import Puntaje

        calificadas = set(
            Puntaje.objects.filter(actividad__tarea__in=tareas)
            .values_list('actividad__tarea__id', 'estudiante_id')
        )
        entregadas = set(
            EntregaTarea.objects.filter(
                tarea__in=tareas,
                estado__in=[EntregaTarea.Estado.ENTREGADA, EntregaTarea.Estado.ATRASADA],
            ).values_list('tarea_id', 'estudiante_id')
        )

        avisadas = 0
        pendientes = collections.Counter()
        for tarea in tareas:
            for matricula in matriculas.get(tarea.asignacion.curso_id, []):
                clave = (tarea.pk, matricula.estudiante_id)
                if clave in calificadas or clave in entregadas:
                    continue
                pendientes[matricula.estudiante] += 1
                if avisar_tarea_sin_entregar(matricula.estudiante, tarea):
                    avisadas += 1

        self.stdout.write(
            f'  Tareas vencidas sin entregar: {sum(pendientes.values())} casos · '
            f'{avisadas} aviso(s) nuevo(s).'
        )
        return pendientes

    def _rachas(self, pendientes_por_estudiante):
        """Quien acumula tareas sin entregar, una tras otra: eso ya es urgente."""
        avisadas = 0
        for estudiante, cuantas in pendientes_por_estudiante.items():
            if avisar_racha_tareas(estudiante, cuantas):
                avisadas += 1
        if avisadas:
            self.stdout.write(self.style.WARNING(f'  Rachas avisadas como urgentes: {avisadas}.'))
        return avisadas

    # ────────────────────────── promedios ──────────────────────────

    def _materias_reprobadas(self, gestion):
        """Materias donde el promedio ya no alcanza, con al menos dos trimestres."""
        filas = (
            Nota.objects.calificadas()
            .filter(asignacion__curso__gestion=gestion)
            .values('estudiante_id', 'asignacion_id')
            .annotate(promedio=Avg('nota'), trimestres=Count('id'))
            .filter(trimestres__gte=TRIMESTRES_PARA_HABLAR_DE_REPROBAR,
                    promedio__lt=NOTA_APROBACION)
        )
        filas = list(filas)
        if not filas:
            self.stdout.write('  Materias reprobadas: ninguna.')
            return 0

        from apps.academico.models import AsignacionDocente, Estudiante

        estudiantes = Estudiante.objects.select_related('usuario').in_bulk(
            {f['estudiante_id'] for f in filas}
        )
        asignaciones = AsignacionDocente.objects.select_related('materia').in_bulk(
            {f['asignacion_id'] for f in filas}
        )

        avisadas = 0
        for fila in filas:
            estudiante = estudiantes.get(fila['estudiante_id'])
            asignacion = asignaciones.get(fila['asignacion_id'])
            if estudiante is None or asignacion is None:
                continue
            if avisar_materia_reprobada(estudiante, asignacion, fila['promedio']):
                avisadas += 1

        self.stdout.write(
            self.style.WARNING(f'  Materias reprobadas: {len(filas)} · {avisadas} aviso(s) nuevo(s).')
        )
        return avisadas
