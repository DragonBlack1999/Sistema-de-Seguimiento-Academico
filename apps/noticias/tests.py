"""Quién ve cada noticia y a quién se le avisa."""
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse

from apps.academico.models import AsignacionDocente, Curso, Estudiante, Gestion, Materia, Matricula
from apps.accounts.models import Usuario

from .models import Noticia
from .services import destinatarios_de_noticia, noticias_visibles
from .validators import validar_imagen


class VisibilidadDeNoticiasTests(TestCase):
    def setUp(self):
        gestion = Gestion.objects.create(anio=2026, activa=True)
        self.curso_a = Curso.objects.create(gestion=gestion, nivel=Curso.Nivel.SECUNDARIA, grado=2, paralelo='A')
        self.curso_b = Curso.objects.create(gestion=gestion, nivel=Curso.Nivel.SECUNDARIA, grado=2, paralelo='B')

        self.admin = Usuario.objects.create(username='direccion', rol=Usuario.Rol.ADMIN)
        self.profe = Usuario.objects.create(username='profe', rol=Usuario.Rol.PROFESOR)
        self.profe_otro = Usuario.objects.create(username='profe_otro', rol=Usuario.Rol.PROFESOR)
        materia = Materia.objects.create(nombre='Lenguaje')
        AsignacionDocente.objects.create(profesor=self.profe, curso=self.curso_a, materia=materia)
        AsignacionDocente.objects.create(profesor=self.profe_otro, curso=self.curso_b, materia=materia)

        self.tutor = Usuario.objects.create(username='TUT-1', ci='1001', rol=Usuario.Rol.PADRE)
        self.alumno = Usuario.objects.create(username='alumno', rol=Usuario.Rol.ESTUDIANTE)
        estudiante = Estudiante.objects.create(usuario=self.alumno, tutor=self.tutor, rude='R-1')
        Matricula.objects.create(estudiante=estudiante, curso=self.curso_a)

        crear = lambda titulo, **extra: Noticia.objects.create(
            titulo=titulo, cuerpo='Texto', publicado_por=self.admin, **extra,
        )
        self.general = crear('General')
        self.borrador = crear('Borrador', publicada=False)
        self.del_curso = crear('Del curso A', curso=self.curso_a)
        self.de_otro_curso = crear('Del curso B', curso=self.curso_b)

    def titulos(self, usuario):
        return set(noticias_visibles(usuario).values_list('titulo', flat=True))

    def test_la_direccion_ve_tambien_los_borradores(self):
        self.assertEqual(self.titulos(self.admin), {'General', 'Borrador', 'Del curso A', 'Del curso B'})

    def test_el_docente_ve_todo_lo_publicado(self):
        self.assertEqual(self.titulos(self.profe), {'General', 'Del curso A', 'Del curso B'})

    def test_estudiante_y_tutor_ven_lo_general_y_lo_de_su_curso(self):
        for usuario in (self.alumno, self.tutor):
            with self.subTest(usuario=usuario.username):
                self.assertEqual(self.titulos(usuario), {'General', 'Del curso A'})

    def test_forzar_la_url_de_una_noticia_ajena_responde_404(self):
        self.client.force_login(self.alumno)
        for noticia in (self.de_otro_curso, self.borrador):
            with self.subTest(noticia=noticia.titulo):
                url = reverse('noticias:detalle', args=[noticia.pk])
                self.assertEqual(self.client.get(url).status_code, 404)
        url = reverse('noticias:detalle', args=[self.del_curso.pk])
        self.assertEqual(self.client.get(url).status_code, 200)

    def test_solo_la_direccion_publica(self):
        for usuario in (self.profe, self.tutor, self.alumno):
            with self.subTest(usuario=usuario.username):
                self.client.force_login(usuario)
                self.assertEqual(self.client.get(reverse('noticias:crear')).status_code, 403)

    def test_el_aviso_de_una_noticia_de_curso_va_solo_a_ese_curso(self):
        destinatarios = set(destinatarios_de_noticia(self.del_curso))
        self.assertEqual(destinatarios, {self.alumno.pk, self.tutor.pk, self.profe.pk})


class ImagenDeNoticiaTests(TestCase):
    def test_formatos_permitidos(self):
        validar_imagen(SimpleUploadedFile('portada.PNG', b'x'))
        with self.assertRaises(ValidationError):
            validar_imagen(SimpleUploadedFile('animacion.gif', b'x'))

    def test_tamano_maximo(self):
        with self.assertRaises(ValidationError):
            validar_imagen(SimpleUploadedFile('foto.jpg', b'0' * (3 * 1024 * 1024 + 1)))
