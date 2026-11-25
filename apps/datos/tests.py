"""Gestión de datos: solo la dirección y la secretaría entran."""
from django.test import TestCase
from django.urls import reverse

from apps.accounts.models import Usuario

ROLES_SIN_PERMISO = [
    Usuario.Rol.PROFESOR, Usuario.Rol.REGENTE, Usuario.Rol.PADRE, Usuario.Rol.ESTUDIANTE,
]


class AccesoAGestionDeDatosTests(TestCase):
    def setUp(self):
        self.admin = Usuario.objects.create(username='secretaria', rol=Usuario.Rol.ADMIN)

    def test_sin_sesion_se_pide_iniciar_sesion(self):
        respuesta = self.client.get(reverse('datos:indice'))
        self.assertEqual(respuesta.status_code, 302)
        self.assertIn(reverse('accounts:login'), respuesta['Location'])

    def test_los_demas_roles_no_entran_a_ninguna_pantalla(self):
        urls = [
            reverse('datos:indice'),
            reverse('datos:lista', args=['estudiantes']),
            reverse('datos:nuevo', args=['estudiantes']),
            reverse('datos:editar', args=['estudiantes', 1]),
            reverse('datos:eliminar', args=['estudiantes', 1]),
        ]
        for rol in ROLES_SIN_PERMISO:
            self.client.force_login(Usuario.objects.create(username=f'u-{rol}', rol=rol))
            for url in urls:
                with self.subTest(rol=rol, url=url):
                    self.assertEqual(self.client.get(url).status_code, 403)

    def test_dar_de_baja_solo_por_post_y_solo_la_administracion(self):
        url = reverse('datos:baja', args=['estudiantes', 1])
        self.client.force_login(self.admin)
        self.assertEqual(self.client.get(url).status_code, 405)

        self.client.force_login(Usuario.objects.create(username='docente', rol=Usuario.Rol.PROFESOR))
        self.assertEqual(self.client.post(url).status_code, 403)

    def test_una_seccion_que_no_existe_responde_404(self):
        self.client.force_login(self.admin)
        respuesta = self.client.get(reverse('datos:lista', args=['no-existe']))
        self.assertEqual(respuesta.status_code, 404)

    def test_la_administracion_ve_el_indice(self):
        self.client.force_login(self.admin)
        respuesta = self.client.get(reverse('datos:indice'))
        self.assertEqual(respuesta.status_code, 200)
        self.assertIn('grupos', respuesta.context)
