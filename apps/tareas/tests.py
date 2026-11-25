from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import IntegrityError
from django.test import TestCase
from django.urls import reverse

from apps.academico.models import AsignacionDocente, Curso, Estudiante, Gestion, Materia
from apps.accounts.models import Usuario
from apps.calificaciones.models import Actividad, Nota, Puntaje
from . import notas
from .models import Tarea


class GuardadoTareaTests(TestCase):
    def setUp(self):
        self.media = Path(self.enterContext(TemporaryDirectory()))
        self.enterContext(self.settings(MEDIA_ROOT=self.media))
        profesor = Usuario.objects.create(username='docente', rol=Usuario.Rol.PROFESOR)
        self.client.force_login(profesor)
        curso = Curso.objects.create(gestion=Gestion.objects.create(anio=2026),
                                     nivel=Curso.Nivel.SECUNDARIA, grado=1)
        self.asignacion = AsignacionDocente.objects.create(
            profesor=profesor, curso=curso, materia=Materia.objects.create(nombre='Historia'),
        )
        self.crear = reverse('tareas:crear_tarea', args=[self.asignacion.pk])

    def enviar(self, url, titulo='Trabajo', trimestre=1, adjunto=None):
        datos = {'titulo': titulo, 'trimestre': trimestre, 'fecha_asignacion': '2026-03-01',
                 'fecha_entrega': '2026-03-15'}
        if adjunto:
            datos['archivo_adjunto'] = SimpleUploadedFile(adjunto, b'Enunciado')
        return self.client.post(url, datos)

    def test_fallo_al_crear_revierte_tarea_columna_y_adjunto(self):
        sincronizar = notas.sincronizar_actividad

        def fallar(tarea, usuario):
            sincronizar(tarea, usuario)
            raise IntegrityError('Fallo de prueba después de crear la columna')

        with patch.object(notas, 'sincronizar_actividad', side_effect=fallar):
            with self.captureOnCommitCallbacks() as avisos:
                respuesta = self.enviar(self.crear, adjunto='nuevo.txt')
        self.assertContains(respuesta, 'No se guardó la tarea')
        self.assertFalse(Tarea.objects.exists())
        self.assertFalse(Actividad.objects.exists())
        self.assertFalse(any(p.is_file() for p in self.media.rglob('*')))
        self.assertEqual(avisos, [])

    def test_edicion_fallida_conserva_notas_y_adjunto_y_se_puede_reintentar(self):
        with patch('apps.tareas.views._notificar_tarea_nueva') as avisar:
            with self.captureOnCommitCallbacks(execute=True):
                self.assertEqual(self.enviar(self.crear, adjunto='original.txt').status_code, 302)
                avisar.assert_not_called()
            avisar.assert_called_once()
        tarea = Tarea.objects.get()
        columna = tarea.actividad_id
        original = Path(tarea.archivo_adjunto.path)
        usuario = Usuario.objects.create(username='estudiante', rol=Usuario.Rol.ESTUDIANTE)
        alumno = Estudiante.objects.create(usuario=usuario, rude='1000')
        Puntaje.objects.create(actividad_id=columna, estudiante=alumno, valor=32)
        nota = Nota.objects.create(asignacion=self.asignacion, estudiante=alumno, trimestre=1)
        nota.recalcular()
        editar = reverse('tareas:editar_tarea', args=[tarea.pk])
        recalcular = notas.recalcular

        def fallar(*args, **kwargs):
            recalcular(*args, **kwargs)
            raise IntegrityError('Fallo de prueba después del recálculo')

        with patch.object(notas, 'recalcular', side_effect=fallar):
            respuesta = self.enviar(editar, 'Investigación', 2, 'reemplazo.txt')
        self.assertContains(respuesta, 'No se guardaron los cambios')
        tarea.refresh_from_db()
        nota.refresh_from_db()
        self.assertEqual((tarea.titulo, tarea.trimestre, tarea.actividad.trimestre), ('Trabajo', 1, 1))
        self.assertEqual(nota.nota, 32)
        self.assertFalse(Nota.objects.filter(trimestre=2).exists())
        self.assertEqual(Path(tarea.archivo_adjunto.path), original)
        self.assertEqual([p for p in self.media.rglob('*') if p.is_file()], [original])

        self.assertEqual(self.enviar(editar, 'Investigación', 2).status_code, 302)
        tarea.refresh_from_db()
        nota.refresh_from_db()
        self.assertEqual((tarea.titulo, tarea.trimestre), ('Investigación', 2))
        self.assertEqual((tarea.actividad_id, tarea.actividad.trimestre), (columna, 2))
        self.assertEqual(Actividad.objects.count(), 1)
        self.assertEqual(nota.nota, 0)
        self.assertEqual(Nota.objects.get(trimestre=2).nota, 32)
