"""Quién puede conversar con quién, y que la URL no salte esa regla."""
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse

from apps.academico.models import AsignacionDocente, Curso, Estudiante, Gestion, Materia, Matricula
from apps.accounts.models import Usuario

from .models import Conversacion, Mensaje
from .services import puede_conversar, usuarios_contactables
from .validators import validar_adjunto


class ContactosPermitidosTests(TestCase):
    def setUp(self):
        gestion = Gestion.objects.create(anio=2026, activa=True)
        curso_a = Curso.objects.create(gestion=gestion, nivel=Curso.Nivel.SECUNDARIA, grado=1, paralelo='A')
        curso_b = Curso.objects.create(gestion=gestion, nivel=Curso.Nivel.SECUNDARIA, grado=1, paralelo='B')
        materia = Materia.objects.create(nombre='Matemática')

        self.admin = Usuario.objects.create(username='direccion', rol=Usuario.Rol.ADMIN)
        self.profe_a = Usuario.objects.create(username='profe_a', rol=Usuario.Rol.PROFESOR)
        self.profe_b = Usuario.objects.create(username='profe_b', rol=Usuario.Rol.PROFESOR)
        AsignacionDocente.objects.create(profesor=self.profe_a, curso=curso_a, materia=materia)
        AsignacionDocente.objects.create(profesor=self.profe_b, curso=curso_b, materia=materia)

        self.tutor = Usuario.objects.create(username='TUT-1', ci='1001', rol=Usuario.Rol.PADRE)
        self.alumno_a = Usuario.objects.create(username='alumno_a', rol=Usuario.Rol.ESTUDIANTE)
        self.alumno_b = Usuario.objects.create(username='alumno_b', rol=Usuario.Rol.ESTUDIANTE)
        estudiante_a = Estudiante.objects.create(usuario=self.alumno_a, tutor=self.tutor, rude='R-A')
        estudiante_b = Estudiante.objects.create(usuario=self.alumno_b, rude='R-B')
        self.matricula_a = Matricula.objects.create(estudiante=estudiante_a, curso=curso_a)
        Matricula.objects.create(estudiante=estudiante_b, curso=curso_b)

    def test_el_docente_escribe_solo_a_estudiantes_y_familias_de_sus_cursos(self):
        contactos = set(usuarios_contactables(self.profe_a))
        self.assertEqual(contactos, {self.alumno_a, self.tutor})

    def test_el_tutor_escribe_a_los_docentes_de_su_hijo_y_a_la_direccion(self):
        self.assertEqual(set(usuarios_contactables(self.tutor)), {self.profe_a, self.admin})

    def test_el_estudiante_no_escribe_a_otros_estudiantes(self):
        self.assertTrue(puede_conversar(self.alumno_a, self.profe_a))
        self.assertFalse(puede_conversar(self.alumno_a, self.alumno_b))
        self.assertFalse(puede_conversar(self.alumno_a, self.profe_b))

    def test_la_relacion_es_simetrica(self):
        for uno, otro in [(self.profe_a, self.alumno_a), (self.profe_a, self.tutor),
                          (self.admin, self.tutor)]:
            with self.subTest(uno=uno.username, otro=otro.username):
                self.assertTrue(puede_conversar(uno, otro))
                self.assertTrue(puede_conversar(otro, uno))

    def test_matricula_inactiva_o_cuenta_dada_de_baja_cortan_el_contacto(self):
        self.matricula_a.activa = False
        self.matricula_a.save()
        self.assertFalse(puede_conversar(self.profe_a, self.alumno_a))

        self.matricula_a.activa = True
        self.matricula_a.save()
        self.profe_a.is_active = False
        self.profe_a.save()
        self.assertFalse(puede_conversar(self.tutor, self.profe_a))

    def test_forzar_la_url_no_abre_una_conversacion_no_permitida(self):
        self.client.force_login(self.tutor)
        respuesta = self.client.get(reverse('mensajeria:conversacion', args=[self.profe_b.pk]))
        self.assertEqual(respuesta.status_code, 403)
        self.assertFalse(Conversacion.objects.exists())

    def test_solo_los_participantes_descargan_un_adjunto(self):
        hilo, _ = Conversacion.entre(self.profe_a, self.alumno_a)
        mensaje = Mensaje.objects.create(
            conversacion=hilo, autor=self.profe_a, destinatario=self.alumno_a, cuerpo='Hola',
        )
        self.client.force_login(self.alumno_b)
        respuesta = self.client.get(reverse('mensajeria:descargar_adjunto', args=[mensaje.pk]))
        self.assertEqual(respuesta.status_code, 403)

    def test_un_solo_hilo_por_pareja_sin_importar_quien_escribe(self):
        primero, creada = Conversacion.entre(self.profe_a, self.tutor)
        segundo, creada_de_nuevo = Conversacion.entre(self.tutor, self.profe_a)
        self.assertTrue(creada)
        self.assertFalse(creada_de_nuevo)
        self.assertEqual(primero.pk, segundo.pk)


class AdjuntosDeMensajeTests(TestCase):
    def test_solo_pdf_e_imagenes(self):
        validar_adjunto(SimpleUploadedFile('tarea.PDF', b'%PDF-1.4'))
        for nombre in ('virus.exe', 'pagina.html', 'sin_extension'):
            with self.subTest(nombre=nombre):
                with self.assertRaises(ValidationError):
                    validar_adjunto(SimpleUploadedFile(nombre, b'x'))

    def test_tamano_maximo(self):
        grande = SimpleUploadedFile('foto.jpg', b'0' * (5 * 1024 * 1024 + 1))
        with self.assertRaises(ValidationError):
            validar_adjunto(grande)
