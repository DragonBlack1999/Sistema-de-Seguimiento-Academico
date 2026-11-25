from io import BytesIO

from django.test import TestCase
from django.urls import reverse
from openpyxl import load_workbook

from apps.academico.models import AsignacionDocente, Curso, Estudiante, Gestion, Materia, Matricula
from apps.accounts.models import Usuario


class DescargaDePlanillasTests(TestCase):
    """Las dos planillas de notas en Excel se descargan y abren.

    Las dos dependen de `apps.asistencia.planillas.nombre_de_hoja`: cuando esa
    función se quitó, ambas descargas daban error 500 sin que ninguna prueba
    lo notara.
    """

    def setUp(self):
        gestion = Gestion.objects.create(anio=2026, activa=True)
        curso = Curso.objects.create(gestion=gestion, grado=1, paralelo='A',
                                     nivel=Curso.Nivel.SECUNDARIA)
        self.profesor = Usuario.objects.create(username='profe', rol=Usuario.Rol.PROFESOR)
        self.asignacion = AsignacionDocente.objects.create(
            profesor=self.profesor, curso=curso,
            materia=Materia.objects.create(nombre='Matemática'),
        )
        alumno = Usuario.objects.create(username='alumno', rol=Usuario.Rol.ESTUDIANTE,
                                        first_name='Ana', last_name='Quispe')
        Matricula.objects.create(estudiante=Estudiante.objects.create(usuario=alumno, rude='1'),
                                 curso=curso)

    def abrir(self, respuesta):
        self.assertEqual(respuesta.status_code, 200)
        return load_workbook(BytesIO(respuesta.content))

    def test_planilla_del_profesor(self):
        self.client.force_login(self.profesor)
        libro = self.abrir(self.client.get(
            reverse('calificaciones:planilla_excel', args=[self.asignacion.pk, 1])))
        self.assertEqual(len(libro.sheetnames), 1)
        self.assertLessEqual(len(libro.sheetnames[0]), 31)

    def test_notas_por_curso_de_direccion(self):
        self.client.force_login(Usuario.objects.create(username='direccion', rol=Usuario.Rol.ADMIN))
        libro = self.abrir(self.client.get(reverse('comunicaciones:notas_por_curso_excel')))
        self.assertGreaterEqual(len(libro.sheetnames), 2)
