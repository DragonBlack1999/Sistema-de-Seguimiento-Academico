"""Cambia los datos personales por otros inventados, dejando el colegio intacto.

    manage.py anonimizar

Sirve para probar el sistema en internet sin publicar los datos de 402 menores
de edad. Conserva exactamente lo que hay que probar —los 18 cursos, las
materias, los horarios, quién enseña qué, cuántos estudiantes tiene cada
curso— y reemplaza todo lo que señala a una persona: nombres, RUDE, carnets,
teléfonos, direcciones, fotos, mensajes y observaciones.

Los nombres inventados se comprueban contra los reales: ninguno puede coincidir.
Los RUDE empiezan con 9999 y los carnets con 90/95, que no existen de verdad, de
modo que un dato de prueba se reconoce a simple vista.

**Solo corre sobre una base cuyo nombre lleve la palabra «prueba».** El camino
es: copiar la base real, anonimizar la copia, y llevar esa copia al servidor.
"""
import random

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.mantenimiento.respaldos import BaseProtegida, asegurar_base_de_prueba

# Nombres y apellidos frecuentes en El Alto. Se combinan al azar y cada
# combinación se comprueba contra las reales: lo que se busca es que la lista se
# lea como una lista de verdad, no que se parezca a nadie en particular.
NOMBRES_M = [
    'Álvaro', 'Ariel', 'Brayan', 'Camilo', 'Cristian', 'Diego', 'Edwin', 'Fabio',
    'Gabriel', 'Gustavo', 'Iván', 'Jhonny', 'Joaquín', 'Kevin', 'Lucas', 'Marcelo',
    'Nelson', 'Óscar', 'Pablo', 'Ramiro', 'Rodrigo', 'Sergio', 'Tomás', 'Vladimir',
]
NOMBRES_F = [
    'Abigail', 'Andrea', 'Beatriz', 'Carla', 'Daniela', 'Elena', 'Fabiola', 'Gabriela',
    'Helen', 'Isabel', 'Jimena', 'Karina', 'Lucía', 'Mariela', 'Noemí', 'Olga',
    'Patricia', 'Rocío', 'Silvia', 'Tania', 'Verónica', 'Wendy', 'Ximena', 'Yolanda',
]
# El segundo nombre acompaña al primero, del mismo género: «Iván Luz» no se lee
# como un nombre de aquí.
SEGUNDOS_M = ['', '', '', 'Andrés', 'Carlos', 'José', 'Miguel', 'Ramiro']
SEGUNDOS_F = ['', '', '', 'Belén', 'Fernanda', 'Luz', 'Paola', 'Isabel']
APELLIDOS = [
    'Alanoca', 'Aruquipa', 'Callisaya', 'Catari', 'Chambi', 'Choque', 'Colque', 'Condori',
    'Cusi', 'Flores', 'Gutiérrez', 'Huanca', 'Laura', 'Limachi', 'Mamani', 'Nina',
    'Paco', 'Poma', 'Quenta', 'Quispe', 'Ramos', 'Rojas', 'Ticona', 'Vargas', 'Yujra',
]
ZONAS = [
    'Villa Adela', 'Ciudad Satélite', 'Río Seco', 'Villa Dolores', 'Senkata', '16 de Julio',
    'Alto Lima', 'Villa Tunari', 'Santiago II', 'Cosmos 79', 'Villa Ingenio', 'Munaypata',
]


class Command(BaseCommand):
    help = 'Reemplaza los datos personales por inventados. Solo en una base de prueba.'

    def add_arguments(self, parser):
        parser.add_argument('--semilla', type=int, default=2026,
                            help='Con la misma semilla salen los mismos nombres.')
        parser.add_argument('--cuentas', default='cuentas_de_prueba.txt',
                            help='Dónde escribir la lista de cuentas para repartir.')

    def handle(self, *args, **opciones):
        base = settings.DATABASES['default']['NAME']
        try:
            asegurar_base_de_prueba(base)
        except BaseProtegida as error:
            raise CommandError(
                f'{error}\n\nEl camino es copiar la base y anonimizar la copia:\n'
                f'    createdb -T {base} {base}_prueba\n'
                f'    set DB_NAME={base}_prueba\n'
                f'    manage.py anonimizar'
            )

        self.azar = random.Random(opciones['semilla'])
        self.stdout.write(f'Anonimizando «{base}»…')

        with transaction.atomic():
            self._olvidar_lo_que_no_se_puede_anonimizar()
            cuentas = self._personas()
            self._rastros()

        self._escribir_cuentas(opciones['cuentas'], cuentas)
        self.stdout.write(self.style.WARNING(
            '  Ojo: los archivos de media/ (fotos, adjuntos, entregas) son reales y NO se '
            'anonimizan. La base ya no los apunta; no los subas al servidor de prueba.'
        ))

    # ────────────────────── lo que directamente se borra ──────────────────────

    def _olvidar_lo_que_no_se_puede_anonimizar(self):
        """Hay cosas que no se pueden disfrazar: se van enteras.

        Un mensaje entre dos personas o un aviso ya emitido cuentan una historia
        real aunque se les cambie el nombre. Y las suscripciones al celular
        apuntan a teléfonos de verdad: mandarles algo desde el servidor de
        prueba sería mandárselo a esas personas.
        """
        from apps.comunicaciones.models import AlertaEmitida
        from apps.mensajeria.models import Conversacion, Mensaje
        from apps.notificaciones.models import Notificacion, SuscripcionPush

        borrados = {
            'mensajes': Mensaje.objects.all().delete()[0],
            'conversaciones': Conversacion.objects.all().delete()[0],
            'notificaciones': Notificacion.objects.all().delete()[0],
            'marcas de alerta': AlertaEmitida.objects.all().delete()[0],
            'avisos al celular': SuscripcionPush.objects.all().delete()[0],
        }
        self.stdout.write('  Se borran: ' + ', '.join(f'{v} {k}' for k, v in borrados.items()))

    # ─────────────────────────────── personas ────────────────────────────────

    def _nombres_inventados(self, cuantos, reales):
        """Combinaciones que no coinciden con ninguna persona real."""
        usados = set()
        salida = []
        while len(salida) < cuantos:
            varon = self.azar.random() < 0.5
            nombre = self.azar.choice(NOMBRES_M if varon else NOMBRES_F)
            segundo = self.azar.choice(SEGUNDOS_M if varon else SEGUNDOS_F)
            apellidos = f'{self.azar.choice(APELLIDOS)} {self.azar.choice(APELLIDOS)}'
            completo = f'{nombre} {segundo} {apellidos}'.replace('  ', ' ').strip()
            if completo in usados or completo.lower() in reales:
                continue
            usados.add(completo)
            salida.append(((f'{nombre} {segundo}').strip(), apellidos))
        return salida

    def _personas(self):
        from apps.academico.models import Estudiante
        from apps.accounts.models import Usuario
        from apps.accounts.services import username_tutor

        usuarios = list(Usuario.objects.order_by('pk'))
        reales = {u.get_full_name().strip().lower() for u in usuarios if u.get_full_name().strip()}
        inventados = self._nombres_inventados(len(usuarios), reales)

        estudiantes = {e.usuario_id: e for e in Estudiante.objects.select_related('usuario')}
        cuentas = {'ESTUDIANTE': [], 'PADRE': [], 'PROFESOR': [], 'ADMIN': [], 'REGENTE': []}
        siguiente = {'rude': 1, 'ci': 1, 'tutor': 1}
        apodos = set()

        for usuario, (nombre, apellidos) in zip(usuarios, inventados):
            usuario.first_name, usuario.last_name = nombre, apellidos
            # Sin correo: así el servidor de prueba no puede escribirle a nadie.
            usuario.email = ''
            usuario.telefono = f'7{self.azar.randint(1000000, 9999999)}'

            if usuario.rol == Usuario.Rol.ESTUDIANTE:
                rude = f'9999{siguiente["rude"]:011d}'
                ci = f'90{siguiente["ci"]:06d}'
                siguiente['rude'] += 1
                siguiente['ci'] += 1
                usuario.username = rude
                usuario.ci = ci
                # El estudiante entra con su RUDE y su carnet: no hay contraseña
                # que guardar, pero se deja una inservible en vez de la vieja.
                usuario.set_unusable_password()
                estudiante = estudiantes.get(usuario.pk)
                if estudiante is not None:
                    estudiante.rude = rude
                    estudiante.direccion = f'Zona {self.azar.choice(ZONAS)}, calle {self.azar.randint(1, 40)}'
                    estudiante.celular = usuario.telefono
                    estudiante.foto_perfil = ''
                    estudiante.save(update_fields=['rude', 'direccion', 'celular', 'foto_perfil'])
                cuentas['ESTUDIANTE'].append((usuario.get_full_name(), rude, ci))

            elif usuario.rol == Usuario.Rol.PADRE:
                ci = f'95{siguiente["tutor"]:06d}'
                siguiente['tutor'] += 1
                usuario.ci = ci
                usuario.username = username_tutor(ci)
                usuario.set_unusable_password()
                cuentas['PADRE'].append((usuario.get_full_name(), ci, ci))

            else:
                # Docentes, regencia y dirección sí tienen contraseña de verdad.
                # Se genera una distinta para cada uno: en la prueba anterior la
                # contraseña era igual al nombre de usuario, y eso en internet
                # es una puerta abierta.
                apodo = self._apodo(nombre, apellidos, apodos)
                clave = self._clave()
                if usuario.username not in ('admin', 'director', 'secretario'):
                    usuario.username = apodo
                usuario.ci = f'80{self.azar.randint(100000, 999999)}'
                usuario.set_password(clave)
                cuentas[usuario.rol].append((usuario.get_full_name(), usuario.username, clave))

            usuario.save()

        for rol, lista in cuentas.items():
            if lista:
                self.stdout.write(f'  {rol.lower()}: {len(lista)}')
        return cuentas

    def _apodo(self, nombre, apellidos, usados):
        base = (nombre.split()[0][0] + apellidos.split()[0]).lower()
        base = ''.join(c for c in base if c.isalnum())
        apodo, numero = base, 1
        while apodo in usados:
            numero += 1
            apodo = f'{base}{numero}'
        usados.add(apodo)
        return apodo

    def _clave(self):
        """Fácil de dictar por teléfono y difícil de adivinar a la primera."""
        palabras = ['illimani', 'quinua', 'chuspa', 'tarwi', 'sajama', 'khantuta',
                    'pututu', 'chacana', 'wiphala', 'titicaca']
        return f'{self.azar.choice(palabras)}{self.azar.randint(100, 999)}'

    # ───────────────────────── lo que queda escrito ──────────────────────────

    def _rastros(self):
        """Textos libres donde alguien pudo escribir un nombre o un motivo real."""
        from apps.asistencia.models import Asistencia
        from apps.comunicaciones.models import Citacion
        from apps.noticias.models import Noticia
        from apps.tareas.models import EntregaTarea, Tarea

        Asistencia.objects.exclude(observacion='').update(observacion='')
        Citacion.objects.update(
            motivo='Conversar sobre el seguimiento del estudiante.', observaciones='',
        )
        EntregaTarea.objects.update(comentario_estudiante='', archivo='', archivo_nombre='')
        Tarea.objects.update(archivo_adjunto='', archivo_nombre='')
        Noticia.objects.update(imagen='', archivo='', archivo_nombre='')
        self.stdout.write('  Observaciones, motivos y archivos adjuntos: vaciados.')

    def _escribir_cuentas(self, ruta, cuentas):
        """La lista para repartir a quienes van a probar."""
        lineas = [
            'Cuentas de prueba — Sistema de Seguimiento Académico',
            'TODOS los datos de esta base son inventados.',
            '',
            'Estudiante: entra con su RUDE y su carnet.',
            'Padre/tutor: entra con su carnet en los dos campos.',
            'Docente y dirección: usuario y contraseña.',
            '',
        ]
        for rol, titulo in [('ADMIN', 'Dirección y secretaría'), ('REGENTE', 'Regencia'),
                            ('PROFESOR', 'Docentes'), ('ESTUDIANTE', 'Estudiantes'),
                            ('PADRE', 'Padres y tutores')]:
            lista = cuentas.get(rol) or []
            if not lista:
                continue
            lineas.append(f'── {titulo} ({len(lista)}) ' + '─' * 20)
            # De estudiantes y padres hay cientos: alcanza con los primeros para
            # probar; el resto está en el sistema.
            recorte = lista if rol in ('ADMIN', 'REGENTE', 'PROFESOR') else lista[:15]
            for nombre, usuario, clave in recorte:
                lineas.append(f'  {nombre:<34} {usuario:<20} {clave}')
            if len(recorte) < len(lista):
                lineas.append(f'  … y {len(lista) - len(recorte)} más')
            lineas.append('')

        with open(ruta, 'w', encoding='utf-8') as archivo:
            archivo.write('\n'.join(lineas))
        self.stdout.write(self.style.SUCCESS(f'  Cuentas para repartir: {ruta}'))
