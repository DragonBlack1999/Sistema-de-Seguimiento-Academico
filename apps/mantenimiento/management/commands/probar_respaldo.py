"""Comprueba que el respaldo se puede restaurar de verdad.

    manage.py probar_respaldo                  el más reciente
    manage.py probar_respaldo --carpeta X       uno en concreto
    manage.py probar_respaldo --conservar       deja la base de prueba para mirarla

Carga la copia en una base **aparte** y cuenta las filas, comparándolas con lo
que el informe dice que había el día que se hizo. Es la única forma de saber que
un respaldo sirve: el archivo puede existir, pesar bien y no restaurar.

Nunca toca la base real; si se le pide hacerlo, se niega.
"""
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from apps.mantenimiento import respaldos
from apps.mantenimiento.respaldos import BaseProtegida

BASE_DE_PRUEBA = 'seguimiento_prueba_respaldo'


class Command(BaseCommand):
    help = 'Restaura un respaldo en una base aparte y verifica que esté completo.'

    def add_arguments(self, parser):
        parser.add_argument('--carpeta', help='Carpeta del respaldo a probar.')
        parser.add_argument('--base', default=BASE_DE_PRUEBA,
                            help=f'Base donde restaurar la prueba (por defecto {BASE_DE_PRUEBA}).')
        parser.add_argument('--conservar', action='store_true',
                            help='No borra la base de prueba al terminar.')
        parser.add_argument('--usuario',
                            help='Cuenta de PostgreSQL con permiso para crear bases '
                                 '(su contraseña se lee de la variable PGPASSWORD).')

    def handle(self, *args, **opciones):
        # Este comando BORRA y rehace la base que se le indique. Por eso no
        # alcanza con comparar contra la base configurada: la configurada
        # cambia según desde dónde se corra. Solo acepta nombres que digan
        # «prueba», que ninguna base de verdad va a llevar.
        prueba = opciones['base']
        try:
            respaldos.asegurar_base_de_prueba(prueba)
        except BaseProtegida as error:
            raise CommandError(str(error))

        self.usuario = opciones['usuario']
        carpeta = self._elegir(opciones['carpeta'])
        archivo = carpeta / 'base.dump'
        if not archivo.exists():
            raise CommandError(f'{carpeta} no tiene base.dump.')

        self.stdout.write(f'Probando {carpeta.name} sobre la base «{prueba}»…')
        self._rehacer_base(prueba)
        self._restaurar(archivo, prueba)

        esperados = self._leer_informe(carpeta)
        obtenidos = self._contar(prueba)
        self._comparar(esperados, obtenidos)

        if opciones['conservar']:
            self.stdout.write(self.style.WARNING(f'  La base «{prueba}» quedó para revisarla.'))
        else:
            self._borrar_base(prueba)

    # ────────────────────────── pasos ──────────────────────────

    def _elegir(self, indicada):
        if indicada:
            carpeta = Path(indicada)
            if not carpeta.is_absolute():
                carpeta = respaldos.carpeta_de_respaldos() / indicada
            if not carpeta.exists():
                raise CommandError(f'No existe {carpeta}.')
            return carpeta

        hay = respaldos.listar()
        if not hay:
            raise CommandError('No hay ningún respaldo todavía. Corre primero «manage.py respaldar».')
        return hay[-1]

    def _rehacer_base(self, prueba):
        respaldos.borrar_base_de_prueba(prueba, usuario=self.usuario)
        resultado = respaldos._correr(
            [respaldos.binario('createdb'), *respaldos._conexion(self.usuario), prueba],
            usuario=self.usuario,
        )
        if resultado.returncode != 0:
            detalle = resultado.stderr.strip()[:300]
            if 'permiso' in detalle or 'permission' in detalle:
                raise CommandError(
                    f'La cuenta de la aplicación no puede crear bases, y está bien que no pueda: '
                    f'para copiar no hace falta. Para esta prueba, corre el comando con una cuenta '
                    f'de administrador de PostgreSQL:\n\n'
                    f'    set PGPASSWORD=la-clave\n'
                    f'    manage.py probar_respaldo --usuario postgres\n\n'
                    f'PostgreSQL dijo: {detalle}'
                )
            raise CommandError(f'No se pudo crear la base de prueba: {detalle}')

    def _restaurar(self, archivo, prueba):
        resultado = respaldos._correr([
            respaldos.binario('pg_restore'), *respaldos._conexion(self.usuario),
            '--dbname', prueba, '--no-owner', '--no-privileges', str(archivo),
        ], usuario=self.usuario)
        # pg_restore devuelve 1 por avisos que no impiden nada (dueños, permisos).
        # Lo que decide si el respaldo sirve es el conteo de filas, más abajo.
        if resultado.returncode != 0:
            self.stdout.write(self.style.WARNING(
                f'  pg_restore avisó: {resultado.stderr.strip().splitlines()[-1][:200]}'
            ))

    def _leer_informe(self, carpeta):
        informe = carpeta / 'informe.txt'
        if not informe.exists():
            return {}
        esperados = {}
        for linea in informe.read_text(encoding='utf-8').splitlines():
            partes = linea.split()
            if len(partes) == 2 and '.' in partes[0] and partes[1].isdigit():
                esperados[partes[0]] = int(partes[1])
        return esperados

    def _contar(self, prueba):
        from django.apps import apps

        pedazos = []
        for etiqueta, modelo in respaldos.TABLAS_DEL_INFORME:
            try:
                tabla = apps.get_model(etiqueta, modelo)._meta.db_table
            except LookupError:
                continue
            pedazos.append(f"select '{etiqueta}.{modelo}' as t, count(*) as n from {tabla}")

        resultado = respaldos._correr([
            respaldos.binario('psql'), *respaldos._conexion(self.usuario), '--dbname', prueba,
            '--tuples-only', '--no-align', '--field-separator', '|',
            '--command', ' union all '.join(pedazos),
        ], usuario=self.usuario)
        if resultado.returncode != 0:
            raise CommandError(f'No se pudo leer la base restaurada: {resultado.stderr.strip()[:300]}')

        conteos = {}
        for linea in resultado.stdout.splitlines():
            if '|' in linea:
                nombre, cuantas = linea.rsplit('|', 1)
                conteos[nombre.strip()] = int(cuantas)
        return conteos

    def _comparar(self, esperados, obtenidos):
        if not obtenidos:
            raise CommandError('La base restaurada no tiene ninguna de las tablas del sistema.')

        problemas = []
        for nombre, cuantas in sorted(obtenidos.items()):
            esperado = esperados.get(nombre)
            if esperado is None:
                self.stdout.write(f'  {nombre:<28} {cuantas}')
                continue
            if cuantas == esperado:
                self.stdout.write(f'  {nombre:<28} {cuantas}  ✓')
            else:
                self.stdout.write(self.style.ERROR(
                    f'  {nombre:<28} {cuantas}  (el informe decía {esperado})'
                ))
                problemas.append(nombre)

        if problemas:
            raise CommandError(
                'El respaldo no coincide con lo que dice su informe: '
                + ', '.join(problemas)
                + '. No confíes en esta copia.'
            )
        self.stdout.write(self.style.SUCCESS(
            '  El respaldo se restaura completo. Sirve para volver.'
        ))

    def _borrar_base(self, prueba):
        respaldos.borrar_base_de_prueba(prueba, usuario=self.usuario)
        self.stdout.write(f'  La base de prueba «{prueba}» se borró.')
