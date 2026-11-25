"""Portal del padre: cada tutor ve solo a sus hijos.

La regla de seguridad del módulo es que la pertenencia se resuelve dentro de la
consulta. Estas pruebas la recorren por las cuatro pantallas de un hijo.
"""
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.academico.models import Estudiante
from apps.accounts.models import Usuario
from apps.comunicaciones.models import Citacion

PANTALLAS_DEL_HIJO = ['notas_hijo', 'asistencia_hijo', 'tareas_hijo', 'citaciones_hijo']


class PortalDelPadreTests(TestCase):
    def setUp(self):
        self.tutor = Usuario.objects.create(username='TUT-1', ci='1001', rol=Usuario.Rol.PADRE)
        self.otro_tutor = Usuario.objects.create(username='TUT-2', ci='1002', rol=Usuario.Rol.PADRE)
        self.hijo = Estudiante.objects.create(
            usuario=Usuario.objects.create(username='hijo', rol=Usuario.Rol.ESTUDIANTE),
            tutor=self.tutor, rude='R-1',
        )
        self.ajeno = Estudiante.objects.create(
            usuario=Usuario.objects.create(username='ajeno', rol=Usuario.Rol.ESTUDIANTE),
            tutor=self.otro_tutor, rude='R-2',
        )

    def test_sin_sesion_se_pide_iniciar_sesion(self):
        for nombre in PANTALLAS_DEL_HIJO:
            with self.subTest(pantalla=nombre):
                respuesta = self.client.get(reverse(f'padres:{nombre}', args=[self.hijo.pk]))
                self.assertEqual(respuesta.status_code, 302)
                self.assertIn(reverse('accounts:login'), respuesta['Location'])

    def test_el_panel_es_solo_para_padres(self):
        for rol in (Usuario.Rol.PROFESOR, Usuario.Rol.REGENTE, Usuario.Rol.ESTUDIANTE):
            with self.subTest(rol=rol):
                self.client.force_login(Usuario.objects.create(username=f'u-{rol}', rol=rol))
                self.assertEqual(self.client.get(reverse('padres:panel')).status_code, 403)

    def test_un_tutor_no_ve_a_un_estudiante_ajeno(self):
        self.client.force_login(self.tutor)
        for nombre in PANTALLAS_DEL_HIJO:
            with self.subTest(pantalla=nombre):
                respuesta = self.client.get(reverse(f'padres:{nombre}', args=[self.ajeno.pk]))
                self.assertEqual(respuesta.status_code, 403)

    def test_estudiante_inexistente_responde_igual_que_uno_ajeno(self):
        self.client.force_login(self.tutor)
        url = reverse('padres:notas_hijo', args=[999999])
        self.assertEqual(self.client.get(url).status_code, 403)

    def test_un_docente_no_entra_a_las_pantallas_del_hijo(self):
        self.client.force_login(Usuario.objects.create(username='docente', rol=Usuario.Rol.PROFESOR))
        for nombre in PANTALLAS_DEL_HIJO:
            with self.subTest(pantalla=nombre):
                respuesta = self.client.get(reverse(f'padres:{nombre}', args=[self.hijo.pk]))
                self.assertEqual(respuesta.status_code, 403)

    def test_el_tutor_ve_solo_las_citaciones_de_su_hijo(self):
        Citacion.objects.create(estudiante=self.hijo, motivo='Propia', fecha=timezone.localdate())
        Citacion.objects.create(estudiante=self.ajeno, motivo='Ajena', fecha=timezone.localdate())
        self.client.force_login(self.tutor)
        respuesta = self.client.get(reverse('padres:citaciones_hijo', args=[self.hijo.pk]))
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual([c.motivo for c in respuesta.context['citaciones']], ['Propia'])
