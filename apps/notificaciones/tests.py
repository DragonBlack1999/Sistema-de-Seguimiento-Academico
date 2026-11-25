import json
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from types import SimpleNamespace
from unittest.mock import Mock, patch

from django.db import connections
from django.test import TransactionTestCase, override_settings

from apps.accounts.models import Usuario
from .models import Notificacion, SuscripcionPush
from .services import enviar_resumen_diario


@override_settings(VAPID_PUBLIC_KEY='prueba', VAPID_PRIVATE_KEY='prueba')
class ResumenPushTests(TransactionTestCase):
    def setUp(self):
        self.usuario = Usuario.objects.create(username='familia', rol=Usuario.Rol.PADRE)
        self.aviso = self.crear_aviso('Una falta')
        self.webpush = Mock(return_value=SimpleNamespace(status_code=201))
        proveedor = SimpleNamespace(webpush=self.webpush)
        self.enterContext(patch.dict('sys.modules', pywebpush=proveedor))

    def crear_aviso(self, titulo):
        return Notificacion.objects.create(
            usuario=self.usuario, nivel=Notificacion.Nivel.ATENCION, tipo=Notificacion.Tipo.ASISTENCIA,
            titulo=titulo, url='/notificaciones/',
        )

    def suscribir(self, nombre):
        return SuscripcionPush.objects.create(usuario=self.usuario, endpoint='https://example.com/' + nombre)

    def test_reintento_parcial_con_un_aviso_nuevo(self):
        primero, segundo = self.suscribir('uno'), self.suscribir('dos')
        def responder(**datos):
            if datos['subscription_info']['endpoint'] == segundo.endpoint:
                raise TimeoutError()
            return SimpleNamespace(status_code=201)

        self.webpush.side_effect = responder
        self.assertEqual(enviar_resumen_diario(), 1)
        self.aviso.refresh_from_db()
        self.assertFalse(self.aviso.avisada)
        self.assertEqual(list(self.aviso.resumen_aceptado_por.all()), [primero])

        nuevo = self.crear_aviso('Otra falta')
        self.webpush.reset_mock(side_effect=True)
        self.assertEqual(enviar_resumen_diario(), 2)
        cargas = {c.kwargs['subscription_info']['endpoint']: json.loads(c.kwargs['data'])
                  for c in self.webpush.call_args_list}
        self.assertEqual(cargas[primero.endpoint]['titulo'], nuevo.titulo)
        self.assertEqual(cargas[segundo.endpoint]['mensaje'], 'Una falta · Otra falta')
        self.assertFalse(Notificacion.objects.filter(avisada=False).exists())
        self.assertEqual(enviar_resumen_diario(), 0)
        self.assertEqual(self.webpush.call_count, 2)

    def test_sin_destino_o_sin_aceptacion_sigue_pendiente(self):
        self.assertEqual(enviar_resumen_diario(), 0)
        destino = self.suscribir('uno')
        with self.settings(VAPID_PRIVATE_KEY=''):
            self.assertEqual(enviar_resumen_diario(), 0)
        self.webpush.assert_not_called()
        for codigo in (503, 410):
            self.webpush.return_value = SimpleNamespace(status_code=codigo)
            self.assertEqual(enviar_resumen_diario(), 0)
            self.aviso.refresh_from_db()
            self.assertFalse(self.aviso.avisada)
            self.assertEqual(SuscripcionPush.objects.filter(pk=destino.pk).exists(), codigo == 503)
        self.suscribir('nuevo')
        self.webpush.return_value = SimpleNamespace(status_code=202)
        self.assertEqual(enviar_resumen_diario(), 1)
        self.aviso.refresh_from_db()
        self.assertTrue(self.aviso.avisada)

    def test_ejecuciones_simultaneas_envian_una_vez(self):
        self.suscribir('uno')
        inicio = Barrier(2)

        def ejecutar():
            try:
                inicio.wait(timeout=10)
                return enviar_resumen_diario()
            finally:
                connections.close_all()

        with ThreadPoolExecutor(max_workers=2) as grupo:
            resultados = [grupo.submit(ejecutar) for _ in range(2)]
            self.assertEqual(sum(f.result(timeout=20) for f in resultados), 1)
        self.webpush.assert_called_once()
        self.aviso.refresh_from_db()
        self.assertTrue(self.aviso.avisada)
