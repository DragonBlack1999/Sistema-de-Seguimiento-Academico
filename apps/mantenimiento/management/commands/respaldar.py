"""La copia de respaldo de cada día.

    manage.py respaldar                 hace la copia, la verifica y rota las viejas
    manage.py respaldar --sin-rotar     no borra ninguna copia anterior
    manage.py respaldar --solo-rotar    no copia nada; solo limpia las vencidas

Pensado para correr solo, una vez al día (Programador de tareas en Windows, cron
en el servidor). Si algo sale mal termina con error y lo dice: un respaldo que
falla en silencio es peor que no tenerlo, porque da confianza sin dar nada.
"""
from django.core.management.base import BaseCommand, CommandError

from apps.mantenimiento import respaldos
from apps.mantenimiento.respaldos import ErrorDeRespaldo


class Command(BaseCommand):
    help = 'Copia de respaldo de la base de datos y los archivos subidos.'

    def add_arguments(self, parser):
        parser.add_argument('--sin-rotar', action='store_true',
                            help='No borra los respaldos viejos.')
        parser.add_argument('--solo-rotar', action='store_true',
                            help='Solo borra los vencidos; no hace copia nueva.')

    def handle(self, *args, **opciones):
        if not opciones['solo_rotar']:
            self._copiar()
        if not opciones['sin_rotar']:
            self._rotar()

    def _copiar(self):
        self.stdout.write(f'Guardando en {respaldos.carpeta_de_respaldos()}…')
        try:
            carpeta = respaldos.crear()
        except ErrorDeRespaldo as error:
            raise CommandError(str(error))

        peso = sum(a.stat().st_size for a in carpeta.iterdir() if a.is_file())
        self.stdout.write(self.style.SUCCESS(
            f'  {carpeta.name} · {respaldos._peso(peso)} · verificado.'
        ))

        copia, aviso = respaldos.copiar_afuera(carpeta)
        if copia:
            self.stdout.write(self.style.SUCCESS(f'  Segunda copia en {copia}.'))
        elif aviso:
            # No es un fracaso del respaldo: la copia local quedó bien hecha.
            self.stdout.write(self.style.WARNING(f'  {aviso}'))

    def _rotar(self):
        borrados = respaldos.rotar()
        quedan = len(respaldos.listar())
        if borrados:
            self.stdout.write(
                f'  Se borraron {len(borrados)} respaldo(s) vencido(s): '
                f'{", ".join(c.name for c in borrados[:5])}'
                f'{"…" if len(borrados) > 5 else ""}'
            )
        self.stdout.write(f'  Quedan {quedan} respaldo(s) guardado(s).')
