"""Pone la demostración en el día que se la muestra.

    manage.py demo_al_dia

Los datos de ejemplo se generan una vez y se guardan en un volcado, pero la
demostración se abre otro día. Sin esto, la primera pantalla que se ve dice
«han entrado 0 de 402»: el colegio aparece como si no hubiera abierto, que es
justo lo contrario de lo que se quiere mostrar.

Lo que hace es dejar el día a media mañana: la mayoría ya entró, algunos con
atraso, y un tercio todavía no pasó por la puerta. Ese tercio es lo que le da
trabajo a la pantalla de regencia, que si no se ve toda en verde y no muestra
nada.

Es idempotente: si el día ya tiene asistencia, no toca nada. Se puede correr en
cada arranque sin que la demostración se vaya acumulando sola.

**Solo corre sobre una base cuyo nombre lleve «demo» o «prueba».**
"""
import datetime
import random

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

# Cuánta gente ya entró cuando se abre la demostración. Ni todos —no habría
# nada que hacer en la puerta— ni pocos —parecería que el día no empezó—.
PROPORCION_REGISTRADA = 0.68


class Command(BaseCommand):
    help = 'Deja la demostración como si el día de clases estuviera a media mañana.'

    def add_arguments(self, parser):
        parser.add_argument('--semilla', type=int, default=None)

    def handle(self, *args, **opciones):
        base = settings.DATABASES['default']['NAME']
        if 'demo' not in base and 'prueba' not in base:
            raise CommandError(
                f'«{base}» no parece una base de demostración. Esto solo corre '
                f'sobre bases cuyo nombre lleve «demo» o «prueba».'
            )

        from apps.academico.models import Gestion
        from apps.asistencia.models import Asistencia
        from apps.asistencia.services import matriculas_del_dia

        gestion = Gestion.objects.filter(activa=True).first()
        if gestion is None:
            self.stdout.write('No hay gestión activa: no hay nada que poner al día.')
            return

        hoy = timezone.localdate()
        if hoy.weekday() == 6:
            self.stdout.write('Hoy es domingo: en la puerta no hay nada que registrar.')
            return

        if Asistencia.objects.filter(fecha=hoy).exists():
            cuantas = Asistencia.objects.filter(fecha=hoy).count()
            self.stdout.write(f'El día ya tiene {cuantas} marca(s): no se toca nada.')
            return

        azar = random.Random(opciones['semilla'] if opciones['semilla'] is not None
                             else hoy.toordinal())
        self._marcar_el_dia(gestion, hoy, azar)
        self._citaciones_pendientes(gestion)

    @transaction.atomic
    def _marcar_el_dia(self, gestion, hoy, azar):
        from apps.accounts.models import Usuario
        from apps.asistencia.models import Asistencia
        from apps.asistencia.services import matriculas_del_dia

        regente = Usuario.objects.filter(rol=Usuario.Rol.REGENTE).first()
        matriculas = list(matriculas_del_dia(gestion, hoy))
        azar.shuffle(matriculas)

        cuantas = int(len(matriculas) * PROPORCION_REGISTRADA)
        filas = []
        for matricula in matriculas[:cuantas]:
            suerte = azar.random()
            if suerte < 0.08:
                estado, hora = Asistencia.Estado.ATRASO, datetime.time(13, azar.randint(51, 59))
            else:
                estado, hora = Asistencia.Estado.PRESENTE, datetime.time(13, azar.randint(25, 49))
            filas.append(Asistencia(
                estudiante_id=matricula.estudiante_id, fecha=hoy,
                hora_llegada=hora, estado=estado, registrado_por=regente,
            ))

        Asistencia.objects.bulk_create(filas, batch_size=500, ignore_conflicts=True)
        atrasos = sum(1 for f in filas if f.estado == Asistencia.Estado.ATRASO)
        self.stdout.write(
            f'  Puerta de hoy: {len(filas)} de {len(matriculas)} ya entraron '
            f'({atrasos} con atraso); {len(matriculas) - len(filas)} sin registrar.'
        )

    def _citaciones_pendientes(self, gestion):
        """Un par de citaciones esperando, para que la pantalla no salga vacía."""
        from apps.academico.models import Matricula
        from apps.accounts.models import Usuario
        from apps.comunicaciones.models import Citacion

        if Citacion.objects.filter(estado=Citacion.Estado.PENDIENTE).exists():
            return

        quien = Usuario.objects.filter(rol=Usuario.Rol.ADMIN, is_active=True).first()
        hoy = timezone.localdate()
        motivos = [
            'Reunión para conversar sobre su rendimiento en el trimestre.',
            'Entrega de boletín y firma del compromiso de asistencia.',
        ]
        estudiantes = [
            m.estudiante for m in Matricula.objects
            .filter(curso__gestion=gestion, activa=True)
            .select_related('estudiante')[:2]
        ]
        creadas = 0
        for estudiante, motivo in zip(estudiantes, motivos):
            Citacion.objects.create(
                estudiante=estudiante, motivo=motivo,
                fecha=hoy + datetime.timedelta(days=2),
                hora=datetime.time(15, 0), lugar='Dirección',
                estado=Citacion.Estado.PENDIENTE, generado_por=quien,
            )
            creadas += 1
        if creadas:
            self.stdout.write(f'  Citaciones: {creadas} esperando ser atendidas.')
