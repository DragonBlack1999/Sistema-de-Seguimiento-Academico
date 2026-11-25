"""Respaldos, rotación y protección de la base real."""
import datetime
import tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from django.core.management import CommandError, call_command
from django.test import SimpleTestCase, TestCase
from django.urls import reverse

from . import respaldos
from .respaldos import BaseProtegida, a_borrar, asegurar_base_de_prueba, listar, rotar

HOY = datetime.datetime(2026, 11, 22, 0, 0)
NOMBRES = [
    '2026-09-01_210000', '2026-09-15_210000', '2026-10-01_210000',
    '2026-10-20_210000', '2026-11-10_210000', '2026-11-20_210000',
]


class ProteccionDeLaBaseRealTests(SimpleTestCase):
    def test_solo_se_aceptan_bases_de_prueba(self):
        for nombre in ('seguimiento_prueba', 'PRUEBA_colegio', 'base_de_prueba_2026'):
            with self.subTest(nombre=nombre):
                self.assertEqual(asegurar_base_de_prueba(nombre), nombre)

    def test_la_base_real_se_rechaza(self):
        for nombre in ('seguimiento_academico', '', None):
            with self.subTest(nombre=nombre):
                with self.assertRaises(BaseProtegida):
                    asegurar_base_de_prueba(nombre)

    def test_borrar_la_base_real_no_ejecuta_nada(self):
        with mock.patch.object(respaldos, '_correr') as correr:
            with self.assertRaises(BaseProtegida):
                respaldos.borrar_base_de_prueba('seguimiento_academico')
        correr.assert_not_called()

    def test_la_anonimizacion_se_niega_sobre_la_base_real(self):
        falso = SimpleNamespace(DATABASES={'default': {'NAME': 'seguimiento_academico'}})
        with mock.patch('apps.mantenimiento.management.commands.anonimizar.settings', falso):
            with self.assertRaises(CommandError):
                call_command('anonimizar')


class RotacionDeRespaldosTests(SimpleTestCase):
    def carpetas(self):
        return [Path(nombre) for nombre in NOMBRES]

    def test_guarda_los_ultimos_dias_y_el_primero_de_cada_mes(self):
        sobran = a_borrar(self.carpetas(), dias=14, meses=12, hoy=HOY)
        self.assertEqual([c.name for c in sobran], ['2026-09-15_210000', '2026-10-20_210000'])

    def test_con_un_solo_mes_se_conserva_solo_el_mensual_mas_reciente(self):
        sobran = a_borrar(self.carpetas(), dias=14, meses=1, hoy=HOY)
        self.assertEqual(
            [c.name for c in sobran],
            ['2026-09-01_210000', '2026-09-15_210000', '2026-10-01_210000', '2026-10-20_210000'],
        )

    def test_listar_ignora_copias_a_medias_y_archivos_sueltos(self):
        with tempfile.TemporaryDirectory() as tmp:
            raiz = Path(tmp)
            for nombre in ('2026-11-20_210000', '2026-11-19_2100', '2026-11-21_210000.parcial', 'otra'):
                (raiz / nombre).mkdir()
            (raiz / '2026-11-18_210000').write_text('no es carpeta')
            self.assertEqual(
                [c.name for c in listar(raiz)], ['2026-11-19_2100', '2026-11-20_210000'],
            )

    def test_rotar_borra_solo_lo_que_sobra(self):
        with tempfile.TemporaryDirectory() as tmp:
            raiz = Path(tmp)
            for nombre in NOMBRES:
                (raiz / nombre).mkdir()
            borrados = rotar(raiz, dias=14, meses=12, hoy=HOY)
            self.assertEqual(len(borrados), 2)
            self.assertEqual(
                sorted(c.name for c in raiz.iterdir()),
                ['2026-09-01_210000', '2026-10-01_210000', '2026-11-10_210000', '2026-11-20_210000'],
            )


class SaludDelServicioTests(TestCase):
    def test_responde_bien_si_alcanza_la_base(self):
        respuesta = self.client.get(reverse('salud'))
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta.content, b'bien')
