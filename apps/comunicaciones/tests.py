from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from apps.academico.models import Estudiante
from apps.accounts.models import Usuario
from .models import Citacion


class CitacionesPorFamiliaTests(TestCase):
    def test_cada_tutor_solo_ve_las_citaciones_de_sus_hijos(self):
        tutores = [
            Usuario.objects.create(username=f'tutor{i}', ci=str(i), rol=Usuario.Rol.PADRE)
            for i in range(3)
        ]
        for i, tutor in enumerate([tutores[0], tutores[0], tutores[1]]):
            usuario = Usuario.objects.create(username=f'alumno{i}', rol=Usuario.Rol.ESTUDIANTE)
            hijo = Estudiante.objects.create(usuario=usuario, tutor=tutor, rude=str(i))
            Citacion.objects.create(estudiante=hijo, motivo=f'Motivo {i}', fecha=timezone.localdate())

        for tutor, motivos in zip(tutores, [{'Motivo 0', 'Motivo 1'}, {'Motivo 2'}, set()]):
            with self.subTest(tutor=tutor.username):
                self.client.force_login(tutor)
                respuesta = self.client.get(reverse('comunicaciones:lista_citaciones'))
                self.assertEqual(respuesta.status_code, 200)
                self.assertEqual({c.motivo for c in respuesta.context['citaciones']}, motivos)


class EstadoCitacionTests(TestCase):
    def setUp(self):
        alumno = Usuario.objects.create(username='alumno', rol=Usuario.Rol.ESTUDIANTE)
        estudiante = Estudiante.objects.create(usuario=alumno, rude='123')
        self.citacion = Citacion.objects.create(estudiante=estudiante, fecha=timezone.localdate())
        self.client = Client(enforce_csrf_checks=True)

    def url_estado(self, estado):
        return reverse('comunicaciones:cambiar_estado_citacion', args=[self.citacion.pk, estado])

    def test_personal_solo_cambia_estado_con_post_y_csrf(self):
        for rol, estado in [(Usuario.Rol.ADMIN, 'ATENDIDA'), (Usuario.Rol.PROFESOR, 'NO_ASISTIO')]:
            with self.subTest(rol=rol):
                self.client.force_login(Usuario.objects.create(username=rol, rol=rol))
                lista = reverse('comunicaciones:lista_citaciones')
                pagina = self.client.get(lista)
                url = self.url_estado(estado)
                self.assertContains(pagina, f'action="{url}"')
                self.assertNotContains(pagina, f'href="{url}"')
                anterior = self.citacion.estado
                self.assertEqual(self.client.get(url).status_code, 405)
                self.assertEqual(self.client.post(url).status_code, 403)
                self.citacion.refresh_from_db()
                self.assertEqual(self.citacion.estado, anterior)

                datos = {'csrfmiddlewaretoken': self.client.cookies['csrftoken'].value}
                self.assertRedirects(self.client.post(url, datos), lista)
                self.assertEqual(self.client.post(self.url_estado('PENDIENTE'), datos).status_code, 400)
                self.citacion.refresh_from_db()
                self.assertEqual(self.citacion.estado, estado)

    def test_tutor_no_puede_modificar_el_estado(self):
        tutor = Usuario.objects.create(username='tutor', rol=Usuario.Rol.PADRE)
        self.client.force_login(tutor)
        self.client.get(reverse('comunicaciones:lista_citaciones'))
        datos = {'csrfmiddlewaretoken': self.client.cookies['csrftoken'].value}
        self.assertEqual(self.client.post(self.url_estado('ATENDIDA'), datos).status_code, 403)
        self.citacion.refresh_from_db()
        self.assertEqual(self.citacion.estado, Citacion.Estado.PENDIENTE)
