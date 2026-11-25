from django.test import TestCase
from django.urls import reverse

from apps.accounts.models import Usuario
from .models import CierreDeGestion, Curso, Estudiante, Gestion, Matricula


class CierreConPreinscripcionTests(TestCase):
    def setUp(self):
        admin = Usuario.objects.create(username='direccion', rol=Usuario.Rol.ADMIN)
        self.client.force_login(admin)
        self.actual = Gestion.objects.create(anio=2026, activa=True)
        self.nueva = Gestion.objects.create(anio=2027)
        self.origen = self.curso(self.actual, 1, 'A')
        self.curso(self.actual, 2, 'A')

    def curso(self, gestion, grado, paralelo):
        return Curso.objects.create(gestion=gestion, grado=grado, paralelo=paralelo,
                                    nivel=Curso.Nivel.SECUNDARIA)

    def alumno(self, rude):
        usuario = Usuario.objects.create(username=rude, rol=Usuario.Rol.ESTUDIANTE)
        alumno = Estudiante.objects.create(rude=rude, usuario=usuario)
        Matricula.objects.create(estudiante=alumno, curso=self.origen)
        return alumno

    def cerrar(self, *promovidos):
        return self.client.post(reverse('academico:cerrar_gestion'), {
            'confirmacion': '2026', 'pasa': [e.pk for e in promovidos],
        })

    def test_respeta_paralelo_y_cuenta_cada_estudiante_una_vez(self):
        promovido, repitente, regular = [self.alumno(str(i)) for i in range(3)]
        otro = self.curso(self.nueva, 2, 'B')
        previa = Matricula.objects.create(estudiante=promovido, curso=otro)
        mismo = self.curso(self.nueva, 1, 'A')
        anterior = Matricula.objects.create(estudiante=repitente, curso=mismo, activa=False)

        self.assertRedirects(self.cerrar(promovido, regular), reverse('accounts:dashboard_admin'),
                             fetch_redirect_response=False)
        activas = Matricula.objects.filter(curso__gestion=self.nueva, activa=True)
        self.assertEqual(activas.get(estudiante=promovido).pk, previa.pk)
        self.assertEqual(activas.get(estudiante=repitente).pk, anterior.pk)
        self.assertEqual(activas.get(estudiante=regular).curso.grado, 2)
        self.assertFalse(Matricula.objects.filter(curso__gestion=self.actual, activa=True).exists())
        acta = CierreDeGestion.objects.get(gestion=self.actual)
        self.assertEqual((acta.promovidos, acta.repitentes), (2, 1))

    def test_si_el_grado_no_coincide_el_cierre_se_revierte(self):
        alumno = self.alumno('100')
        previa = Matricula.objects.create(estudiante=alumno, curso=self.curso(self.nueva, 1, 'B'))
        respuesta = self.cerrar(alumno)
        self.assertRedirects(respuesta, reverse('academico:cerrar_gestion'), fetch_redirect_response=False)
        self.assertFalse(CierreDeGestion.objects.exists())
        self.assertTrue(Gestion.objects.get(pk=self.actual.pk).activa)
        self.assertTrue(Matricula.objects.get(estudiante=alumno, curso=self.origen).activa)
        self.assertEqual(Matricula.objects.get(curso__gestion=self.nueva).pk, previa.pk)

    def test_dos_preinscripciones_activas_requieren_revision(self):
        alumno = self.alumno('101')
        for paralelo in ('A', 'B'):
            Matricula.objects.create(estudiante=alumno, curso=self.curso(self.nueva, 2, paralelo))
        respuesta = self.cerrar(alumno)
        self.assertRedirects(respuesta, reverse('academico:cerrar_gestion'), fetch_redirect_response=False)
        self.assertFalse(CierreDeGestion.objects.exists())
        self.assertTrue(Matricula.objects.get(estudiante=alumno, curso=self.origen).activa)
