from datetime import date, time
from io import BytesIO

from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone
from openpyxl import load_workbook

from apps.academico.models import Curso, DiaCapacitacion, Estudiante, Gestion, Horario, Matricula
from apps.accounts.models import Usuario
from apps.comunicaciones.models import Citacion
from apps.notificaciones.models import Notificacion
from .models import Asistencia


class RegistroDeJornadaTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.regente = Usuario.objects.create(username='regente', rol=Usuario.Rol.REGENTE)
        cls.gestion = Gestion.objects.create(anio=2026, activa=True, fecha_inicio=date(2026, 2, 2),
                                            fecha_fin=date(2026, 12, 4))
        curso = Curso.objects.create(gestion=cls.gestion, nivel='SECUNDARIA', grado=1)
        taller = Curso.objects.create(gestion=cls.gestion, nivel='SECUNDARIA', grado=2)
        DiaCapacitacion.objects.create(curso=taller, dia=Horario.Dia.LUNES)
        antiguo = Curso.objects.create(gestion=Gestion.objects.create(anio=2025), nivel='SECUNDARIA', grado=1)
        cls.alumnos = {}
        for nombre, destino in [('presente', curso), ('ausente', curso), ('taller', taller),
                                ('baja', curso), ('anterior', antiguo), ('nueva', curso),
                                ('inactivo', curso)]:
            usuario = Usuario.objects.create(username=nombre, rol=Usuario.Rol.ESTUDIANTE,
                                             is_active=nombre != 'inactivo')
            alumno = Estudiante.objects.create(usuario=usuario, rude=nombre)
            m = Matricula.objects.create(estudiante=alumno, curso=destino, activa=nombre != 'baja')
            inicio = date(2026, 2, 3) if nombre == 'nueva' else date(2026, 2, 2)
            Matricula.objects.filter(pk=m.pk).update(fecha_matricula=inicio)
            cls.alumnos[nombre] = alumno

    def setUp(self):
        self.client.force_login(self.regente)

    def marcar(self, nombre, fecha, **datos):
        url = reverse('asistencia:marcar', args=[self.alumnos[nombre].pk])
        return self.client.post(url, {'fecha': fecha, **datos})

    def cerrar(self, fecha):
        return self.client.post(reverse('asistencia:cerrar'), {'fecha': fecha})

    def test_fecha_invalida_no_genera_registros_ni_avisos(self):
        for fecha in ('2025-10-14', '2027-02-02', '2026-01-30', '2026-12-05', '2026-02-08', 'mal'):
            with self.subTest(fecha=fecha):
                self.assertEqual(self.marcar('presente', fecha, estado='FALTA').status_code, 400)
                self.assertRedirects(self.cerrar(fecha), reverse('asistencia:puerta'), fetch_redirect_response=False)
                self.assertFalse(Asistencia.objects.exists())
                self.assertFalse(Notificacion.objects.exists())
                self.assertFalse(Citacion.objects.exists())

    def test_lista_del_lunes_se_aplica_a_marca_y_cierre(self):
        fecha = '2026-02-02'
        for nombre in ('taller', 'baja', 'anterior', 'nueva', 'inactivo'):
            for datos in ({}, {'estado': 'FALTA'}):
                with self.subTest(nombre=nombre, datos=datos):
                    self.assertEqual(self.marcar(nombre, fecha, **datos).status_code, 400)
        self.assertFalse(Notificacion.objects.exists())
        self.assertEqual(self.marcar('presente', fecha, estado='PRESENTE').status_code, 200)
        self.cerrar(fecha)
        self.cerrar(fecha)
        filas = Asistencia.objects.values_list('estudiante__rude', 'estado')
        self.assertCountEqual(filas, [('presente', 'PRESENTE'), ('ausente', 'FALTA')])

    def test_sabado_es_lectivo_y_se_aceptan_limites_de_gestion(self):
        for fecha in ('2026-02-07', '2026-12-04'):
            self.assertEqual(self.marcar('taller', fecha).status_code, 200)

    def test_gestion_inactiva_no_admite_escrituras(self):
        Gestion.objects.filter(pk=self.gestion.pk).update(activa=False)
        self.assertEqual(self.marcar('presente', '2026-02-02').status_code, 400)
        self.cerrar('2026-02-02')
        self.assertFalse(Asistencia.objects.exists())

    def test_capacitacion_respeta_gestion_y_admite_recuperacion(self):
        self.client.force_login(Usuario.objects.create(username='direccion', rol=Usuario.Rol.ADMIN))
        alumno = self.alumnos['taller']
        datos = {'curso': alumno.matriculas.get().curso_id, f'estado_{alumno.pk}': 'PRESENTE'}
        url = reverse('asistencia:capacitacion')
        self.client.post(url, {**datos, 'fecha': '2027-02-02'})
        self.assertFalse(Asistencia.objects.exists())
        self.client.post(url, {**datos, 'fecha': '2026-02-03'})
        self.assertEqual(Asistencia.objects.get().estudiante, alumno)

    def test_descargas_por_curso_y_fecha(self):
        curso = self.alumnos['taller'].matriculas.get().curso
        alumno = self.alumnos['taller']
        taller = date(2026, 3, 2)
        entrada = date(2026, 2, 3)
        Asistencia.objects.create(estudiante=alumno, fecha=taller, estado='FALTA',
                                  observacion='Clase de capacitación')
        Asistencia.objects.create(estudiante=alumno, fecha=entrada, estado='ATRASO', hora_llegada=time(14, 5))
        Asistencia.objects.create(estudiante=self.alumnos['ausente'], fecha=date(2026, 3, 6), estado='FALTA')
        url = reverse('asistencia:puerta_excel')
        respuesta = self.client.get(url, {'curso': curso.pk, 'mes': 2, 'anio': 2026})
        self.assertEqual(respuesta.status_code, 200)
        self.assertIn('.xlsx', respuesta['Content-Disposition'])
        puerta = load_workbook(BytesIO(respuesta.content)).active
        self.assertEqual(puerta['C4'].value.date(), entrada)
        self.assertEqual(puerta['D4'].value, 'Presentes')
        self.assertEqual(puerta['B5'].value, alumno.rude)
        self.assertEqual(puerta['C5'].value, 'Atraso 14:05')
        self.assertEqual(puerta['F5'].value, 1)
        self.assertEqual(puerta['H5'].value, 1)

        cap = reverse('asistencia:capacitacion_excel')
        self.assertEqual(self.client.get(cap, {'curso': curso.pk}).status_code, 403)
        self.client.force_login(Usuario.objects.create(username='admin', rol=Usuario.Rol.ADMIN))
        libro = load_workbook(BytesIO(self.client.get(cap, {'curso': curso.pk}).content))
        self.assertEqual(len(libro.worksheets), 1)
        hoja = libro.active
        self.assertEqual([hoja[c].value.date() for c in ('C4', 'D4')], [entrada, taller])
        self.assertEqual(hoja['D4'].number_format, 'dd/mm/yyyy')
        self.assertEqual([hoja[c].value for c in ('C5', 'D5', 'F5', 'G5')], ['Atraso', 'Falta', 1, 0.5])
        self.client.force_login(alumno.usuario)
        self.assertEqual(self.client.get(url, {'curso': curso.pk}).status_code, 403)

    def test_excel_entrada_solo_incluye_fechas_y_totales_del_mes_y_curso(self):
        alumno = self.alumnos['presente']
        curso = alumno.matriculas.get().curso
        for fecha in [date(2025, 2, 7), date(2026, 1, 31), date(2026, 2, 2),
                      date(2026, 2, 28), date(2026, 3, 1)]:
            Asistencia.objects.create(estudiante=alumno, fecha=fecha, estado='FALTA')
        Asistencia.objects.create(estudiante=self.alumnos['taller'], fecha=date(2026, 2, 5))
        Asistencia.objects.create(estudiante=alumno, fecha=date(2026, 2, 6), observacion='Clase de capacitación')
        pagina = self.client.get(reverse('asistencia:puerta'), {'fecha': '2026-02-02'})
        self.assertContains(pagina, 'id="anioExcel"')
        self.assertContains(pagina, 'id="mesExcel"')
        self.assertContains(pagina, 'data-anio="2025"')
        url = reverse('asistencia:puerta_excel')
        datos = {'curso': curso.pk, 'anio': 2026, 'mes': 2}
        respuesta = self.client.get(url, datos)
        self.assertEqual(respuesta.status_code, 200)
        self.assertIn('2026-02.xlsx', respuesta['Content-Disposition'])
        hoja = load_workbook(BytesIO(respuesta.content)).active
        fechas = [c.value.date() for c in hoja[4] if c.is_date]
        self.assertEqual(fechas, [date(2026, 2, 2), date(2026, 2, 28)])
        fila = next(f for f in hoja.values if f[1] == alumno.rude)
        self.assertEqual(fila[5], 2)
        vacia = load_workbook(BytesIO(self.client.get(url, {**datos, 'mes': 4}).content)).active
        self.assertFalse(any(c.is_date for c in vacia[4]))
        self.assertIn('mes elegido', vacia.cell(vacia.max_row, 1).value)
        for cambio in [{'anio': 2025}, {'mes': 13}, {'anio': 'incorrecto'}]:
            with self.subTest(cambio=cambio):
                self.assertEqual(self.client.get(url, {**datos, **cambio}).status_code, 400)

    def test_excel_entrada_de_gestion_cerrada_con_cambio_de_paralelo(self):
        alumno = self.alumnos['anterior']
        inicial = alumno.matriculas.get()
        Matricula.objects.filter(pk=inicial.pk).update(activa=False, fecha_matricula=date(2025, 2, 1))
        nuevo = Curso.objects.create(gestion=inicial.curso.gestion, nivel='SECUNDARIA', grado=1, paralelo='B')
        traslado = Matricula.objects.create(estudiante=alumno, curso=nuevo, activa=False)
        Matricula.objects.filter(pk=traslado.pk).update(fecha_matricula=date(2025, 2, 15))
        for dia in [14, 15]:
            Asistencia.objects.create(estudiante=alumno, fecha=date(2025, 2, dia))
        for curso_id, dia in [(inicial.curso_id, 14), (nuevo.pk, 15)]:
            with self.subTest(curso=curso_id):
                respuesta = self.client.get(reverse('asistencia:puerta_excel'), {'curso': curso_id, 'mes': 2, 'anio': 2025})
                self.assertEqual(respuesta.status_code, 200)
                hoja = load_workbook(BytesIO(respuesta.content)).active
                self.assertEqual([c.value.date() for c in hoja[4] if c.is_date], [date(2025, 2, dia)])
                self.assertEqual(hoja['B5'].value, alumno.rude)

    def test_mi_asistencia_consulta_solo_el_mes_del_estudiante(self):
        alumno = self.alumnos['presente']
        for fecha, estado in [(date(2024, 1, 31), 'FALTA'), (date(2024, 2, 1), 'PRESENTE'),
                              (date(2024, 2, 29), 'ATRASO'), (date(2024, 3, 1), 'FALTA')]:
            Asistencia.objects.create(estudiante=alumno, fecha=fecha, estado=estado)
        Asistencia.objects.create(estudiante=self.alumnos['ausente'], fecha=date(2024, 2, 8), estado='FALTA')
        self.client.force_login(alumno.usuario)
        url = reverse('asistencia:mi_asistencia')
        with CaptureQueriesContext(connection) as consultas:
            respuesta = self.client.get(url, {'mes': 2, 'anio': 2024})
        self.assertContains(respuesta, 'Febrero de 2024')
        self.assertEqual([r.fecha for r in respuesta.context['registros']], [date(2024, 2, 29), date(2024, 2, 1)])
        self.assertEqual(respuesta.context['resumen'], {'presentes': 1, 'atrasos': 1, 'faltas': 0, 'licencias': 0})
        consultas_asistencia = [q['sql'] for q in consultas if Asistencia._meta.db_table in q['sql']]
        self.assertEqual(len(consultas_asistencia), 1)
        self.assertIn('BETWEEN', consultas_asistencia[0])
        self.assertIn('2024-02-01', consultas_asistencia[0])
        self.assertIn('2024-02-29', consultas_asistencia[0])

    def test_mi_asistencia_mes_inicial_vacio_y_seleccion_invalida(self):
        self.client.force_login(self.alumnos['presente'].usuario)
        url = reverse('asistencia:mi_asistencia')
        respuesta = self.client.get(url)
        self.assertEqual(respuesta.context['periodo'], timezone.localdate().replace(day=1))
        self.assertContains(respuesta, 'No hay registros de asistencia en este mes.')
        self.assertRedirects(self.client.get(url, {'mes': '13'}), url)

    def test_tutor_puede_cambiar_el_mes_y_anio_de_su_hijo(self):
        tutor = Usuario.objects.create(username='tutor', rol=Usuario.Rol.PADRE)
        hijo, hermano = self.alumnos['presente'], self.alumnos['ausente']
        Estudiante.objects.filter(pk__in=[hijo.pk, hermano.pk]).update(tutor=tutor)
        Asistencia.objects.create(estudiante=hijo, fecha=date(2025, 12, 31), estado='FALTA')
        Asistencia.objects.create(estudiante=hijo, fecha=date(2026, 1, 1), estado='PRESENTE')
        Asistencia.objects.create(estudiante=hermano, fecha=date(2026, 1, 2), estado='ATRASO')
        self.client.force_login(tutor)
        url = reverse('padres:asistencia_hijo', args=[hijo.pk])
        inicial = self.client.get(url)
        self.assertEqual(inicial.context['periodo'], timezone.localdate().replace(day=1))
        self.assertContains(inicial, 'Ver mes')
        for fecha, estado in [(date(2025, 12, 31), 'faltas'), (date(2026, 1, 1), 'presentes')]:
            with self.subTest(fecha=fecha), CaptureQueriesContext(connection) as consultas:
                pagina = self.client.get(url, {'mes': fecha.month, 'anio': fecha.year})
                self.assertEqual([r.fecha for r in pagina.context['registros']], [fecha])
                self.assertEqual(pagina.context['resumen'][estado], 1)
                self.assertEqual(sum(pagina.context['resumen'].values()), 1)
                self.assertEqual(sum(Asistencia._meta.db_table in q['sql'] for q in consultas), 1)
        vacio = self.client.get(url, {'mes': 2, 'anio': 2026})
        self.assertContains(vacio, 'No hay registros de asistencia en este mes.')
        self.assertRedirects(self.client.get(url, {'anio': 'inválido'}), url)

    def test_tutor_no_puede_consultar_la_asistencia_de_otra_familia(self):
        tutor = Usuario.objects.create(username='tutor', ci='111', rol=Usuario.Rol.PADRE)
        otro = Usuario.objects.create(username='otro', ci='222', rol=Usuario.Rol.PADRE)
        hijo = self.alumnos['presente']
        Estudiante.objects.filter(pk=hijo.pk).update(tutor=otro)
        self.client.force_login(tutor)
        url = reverse('padres:asistencia_hijo', args=[hijo.pk])
        self.assertEqual(self.client.get(url, {'mes': 3, 'anio': 2026}).status_code, 403)
