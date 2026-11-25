from datetime import timedelta
from io import StringIO
from unittest.mock import patch

from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from apps.academico.models import AsignacionDocente, Curso, Estudiante, Gestion, Materia, Matricula
from apps.asistencia.models import Asistencia
from apps.calificaciones.models import Nota, Puntaje
from apps.comunicaciones.models import Citacion
from apps.notificaciones.management.commands.alertas_diarias import Command
from apps.tareas.models import EntregaTarea, Tarea
from apps.tareas.notas import sincronizar_actividad
from . import tablero
from .models import IntentoFallido, Usuario


class TableroTareasPendientesTests(TestCase):
    def test_tablero_y_alertas_coinciden_por_estudiante(self):
        hoy = timezone.localdate()
        gestion = Gestion.objects.create(anio=hoy.year, activa=True)
        curso = Curso.objects.create(gestion=gestion, nivel=Curso.Nivel.SECUNDARIA, grado=1)
        profesor = Usuario.objects.create(username='profesor', rol=Usuario.Rol.PROFESOR)
        asignacion = AsignacionDocente.objects.create(
            profesor=profesor, curso=curso, materia=Materia.objects.create(nombre='Historia'),
        )
        alumnos = {}
        for nombre in ('papel', 'cero', 'entregada', 'atrasada', 'pendiente', 'sin_entrega', 'inactivo'):
            usuario = Usuario.objects.create(username=nombre, rol=Usuario.Rol.ESTUDIANTE)
            alumno = Estudiante.objects.create(usuario=usuario, rude=nombre)
            Matricula.objects.create(curso=curso, estudiante=alumno, activa=nombre != 'inactivo')
            alumnos[nombre] = alumno
        vencida = Tarea.objects.create(asignacion=asignacion, trimestre=1, titulo='Trabajo',
                                      fecha_entrega=hoy - timedelta(days=1))
        Tarea.objects.create(asignacion=asignacion, trimestre=1, titulo='Para hoy', fecha_entrega=hoy)
        sincronizar_actividad(vencida)
        for nombre, valor in [('papel', 35), ('cero', 0)]:
            Puntaje.objects.create(actividad=vencida.actividad, estudiante=alumnos[nombre], valor=valor)
        for nombre in ('entregada', 'atrasada', 'pendiente'):
            EntregaTarea.objects.create(tarea=vencida, estudiante=alumnos[nombre], estado=nombre.upper())

        # Los otros indicadores siguen contando, incluso si la tarea se calificó en papel.
        papel = alumnos['papel']
        Asistencia.objects.create(estudiante=papel, fecha=hoy, estado=Asistencia.Estado.FALTA)
        Citacion.objects.create(estudiante=papel, fecha=hoy)
        Nota.objects.create(estudiante=papel, asignacion=asignacion, trimestre=1, hacer=35, nota=35)
        with self.assertNumQueries(7):
            filas, total = tablero.necesitan_atencion(gestion)
        self.assertEqual(total, 3)
        self.assertEqual(filas[0]['estudiante'], papel)
        self.assertEqual((filas[0]['sin_entregar'], filas[0]['puntos'], filas[0]['reprobadas']),
                         (0, 13, ['Historia']))
        esperados = {alumnos['pendiente']: 1, alumnos['sin_entrega']: 1}
        conteos = {f['estudiante']: f['sin_entregar'] for f in filas if f['sin_entregar']}
        self.assertEqual(conteos, esperados)
        with patch('apps.notificaciones.management.commands.alertas_diarias.avisar_tarea_sin_entregar') as avisar:
            self.assertEqual(Command(stdout=StringIO())._tareas_vencidas(gestion), esperados)
        self.assertCountEqual([llamada.args for llamada in avisar.call_args_list],
                              [(alumno, vencida) for alumno in esperados])


class PermisoPanelDireccionTests(TestCase):
    def test_acceso_directo_por_rol(self):
        url = reverse('accounts:dashboard_admin')
        self.assertRedirects(self.client.get(url), reverse('accounts:login') + '?next=' + url)
        for rol in Usuario.Rol:
            with self.subTest(rol=rol):
                usuario = Usuario.objects.create(username=rol.value, rol=rol)
                self.client.force_login(usuario)
                esperado = 200 if rol == Usuario.Rol.ADMIN else 403
                self.assertEqual(self.client.get(url).status_code, esperado)


class SesionDeFormularioTests(TestCase):
    def test_formulario_abierto_antes_de_volver_a_ingresar(self):
        admin = Usuario.objects.create_user(username='direccion', password='prueba-123', rol=Usuario.Rol.ADMIN)
        navegador = Client(enforce_csrf_checks=True)
        navegador.force_login(admin)
        url = reverse('datos:nuevo', args=['familias'])
        navegador.get(url)
        token_anterior = navegador.cookies['csrftoken'].value
        navegador.logout()
        self.assertTrue(navegador.login(username='direccion', password='prueba-123'))
        sesion = navegador.get(reverse('accounts:sesion_formulario'))
        self.assertEqual(sesion.json()['usuario'], str(admin.pk))
        self.assertIn('no-store', sesion.headers['Cache-Control'])
        datos = {'ci': '12000', 'first_name': 'Tutor', 'last_name': 'Prueba'}
        rechazo = navegador.post(url, {**datos, 'csrfmiddlewaretoken': token_anterior})
        self.assertContains(rechazo, 'Vuelve a abrir el formulario', status_code=403)
        self.assertFalse(Usuario.objects.filter(ci='12000').exists())
        # El nuevo token queda ligado a la cookie de la sesión actual.
        guardado = navegador.post(url, {**datos, 'csrfmiddlewaretoken': sesion.json()['token']})
        self.assertEqual(guardado.status_code, 302)
        self.assertEqual(Usuario.objects.filter(ci='12000', rol=Usuario.Rol.PADRE).count(), 1)


class BajaDeCuentaTests(TestCase):
    def test_baja_desde_administracion_bloquea_la_sesion_abierta(self):
        admin = Usuario.objects.create(username='direccion', rol=Usuario.Rol.ADMIN)
        administracion = Client()
        administracion.force_login(admin)
        privada = reverse('comunicaciones:lista_citaciones')
        casos = [
            (Usuario.Rol.PADRE, 'familias', 'TUT-12345', '12345', '12345'),
            (Usuario.Rol.PROFESOR, 'docentes', 'docente', '54321', 'clave-de-prueba'),
        ]
        for rol, ficha, nombre, ci, clave in casos:
            with self.subTest(rol=rol):
                cuenta = Usuario.objects.create_user(username=nombre, password=clave, ci=ci, rol=rol)
                identificador = ci if rol == Usuario.Rol.PADRE else nombre
                navegador = Client()
                self.assertTrue(navegador.login(username=identificador, password=clave))
                self.assertEqual(navegador.get(privada).status_code, 200)

                baja = administracion.post(reverse('datos:baja', args=[ficha, cuenta.pk]))
                self.assertEqual(baja.status_code, 302)
                cuenta.refresh_from_db()
                self.assertFalse(cuenta.is_active)
                self.assertRedirects(navegador.get(privada), reverse('accounts:login') + '?next=' + privada)
                self.assertFalse(navegador.login(username=identificador, password=clave))


class LimiteDeIntentosTests(TestCase):
    """Quien prueba contraseñas queda frenado; quien entra bien, no."""

    def setUp(self):
        self.usuario = Usuario.objects.create_user(
            username='direccion', password='clave-buena-123', rol=Usuario.Rol.ADMIN, is_staff=True,
        )
        self.url = reverse('accounts:login')

    def _intentar(self, clave, usuario='direccion', url=None, ip='10.0.0.1'):
        return self.client.post(url or self.url, {'username': usuario, 'password': clave},
                                REMOTE_ADDR=ip)

    def test_tras_cinco_fallos_ni_la_clave_buena_entra(self):
        for _ in range(5):
            self.assertEqual(self._intentar('mala').status_code, 200)
        respuesta = self._intentar('clave-buena-123')
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, 'demasiados intentos fallidos')
        self.assertNotIn('_auth_user_id', self.client.session)
        # Durante el bloqueo no se suman fallos: si no, nunca terminaría.
        self.assertEqual(IntentoFallido.objects.count(), 5)

    def test_el_bloqueo_se_levanta_solo(self):
        for _ in range(5):
            self._intentar('mala')
        IntentoFallido.objects.update(fecha=timezone.now() - timedelta(minutes=16))
        self.assertRedirects(self._intentar('clave-buena-123'),
                             reverse('accounts:redirigir_dashboard'), fetch_redirect_response=False)

    def test_entrar_bien_borra_los_fallos(self):
        for _ in range(4):
            self._intentar('mala')
        self._intentar('clave-buena-123')
        self.assertFalse(IntentoFallido.objects.filter(usuario='direccion').exists())

    def test_el_usuario_se_cuenta_sin_importar_mayusculas(self):
        for usuario in ('Direccion', 'DIRECCION', ' direccion', 'direccion', 'DiReCcIoN'):
            self._intentar('mala', usuario=usuario)
        self.assertContains(self._intentar('clave-buena-123'), 'demasiados intentos fallidos')

    def test_limite_por_direccion_aunque_cambie_de_usuario(self):
        with self.settings(LOGIN_INTENTOS_POR_IP=3):
            for i in range(3):
                self._intentar('mala', usuario=f'otro{i}')
            self.assertContains(self._intentar('clave-buena-123'), 'demasiados intentos fallidos')
            # Desde otra computadora la cuenta sigue abierta.
            self.assertEqual(self._intentar('clave-buena-123', ip='10.0.0.2').status_code, 302)

    def test_el_admin_tiene_el_mismo_limite(self):
        url = reverse('admin:login')
        for _ in range(5):
            self._intentar('mala', url=url)
        respuesta = self._intentar('clave-buena-123', url=url)
        self.assertContains(respuesta, 'demasiados intentos fallidos')
        self.assertNotIn('_auth_user_id', self.client.session)


class PoliticaDeContenidoTests(TestCase):
    def test_la_pagina_lleva_csp_y_sus_scripts_el_nonce(self):
        import re

        respuesta = self.client.get(reverse('accounts:login'))
        politica = respuesta.headers['Content-Security-Policy']
        self.assertIn("object-src 'none'", politica)
        self.assertNotIn('unsafe-inline', politica.split('script-src')[1].split(';')[0])
        nonce = re.search(r"'nonce-([^']+)'", politica).group(1)
        self.assertContains(respuesta, f'<script nonce="{nonce}">')

    def test_las_plantillas_no_tienen_codigo_en_atributos(self):
        """onclick="…" y parecidos no corren con la CSP: van como data-… (ver acciones.js)."""
        import re
        from pathlib import Path

        from django.conf import settings

        culpables = []
        for plantilla in (Path(settings.BASE_DIR) / 'templates').rglob('*.html'):
            texto = plantilla.read_text(encoding='utf-8')
            if re.search(r'\son[a-z]+\s*=\s*["\']', texto) or 'javascript:' in texto:
                culpables.append(str(plantilla))
            if re.search(r'<script(?![^>]*\b(src|nonce)=)[^>]*>', texto):
                culpables.append(f'{plantilla} (<script> sin nonce)')
        self.assertEqual(culpables, [])
