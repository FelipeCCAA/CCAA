"""Firmas OP-01 frente a escritores reales en conexiones PostgreSQL distintas."""

from datetime import date
from queue import Queue
import threading
import time

from django.core.exceptions import ValidationError
from django.db import connection, connections, transaction
from django.test import TransactionTestCase

from maestros.models import Especificacion
from produccion.models import Analisis

from .models import Liberacion
from .tests_api import BaseAPI
from .vigencia import exigir_liberacion_lote_vigente


class ConcurrenciaFirmaOP01Tests(TransactionTestCase):
    _usuario = BaseAPI._usuario
    _cliente = BaseAPI._cliente
    _analisis = BaseAPI._analisis
    _checklist_completo = BaseAPI._checklist_completo

    def setUp(self):
        if connection.vendor != "postgresql":
            self.skipTest("Requiere bloqueos PostgreSQL entre conexiones reales.")
        BaseAPI.setUp(self)
        self.analisis = self._analisis()
        self._checklist_completo()

    def _firmar(self):
        respuesta = self.cliente.post(
            f"/api/calidad/expedientes/{self.lote.pk}/liberar/", {}, format="json",
        )
        self.assertEqual(respuesta.status_code, 200, respuesta.data)
        return Liberacion.objects.get(lote=self.lote)

    def _iniciar(self, guardar):
        resultados, pids = Queue(), Queue()

        def trabajar():
            try:
                with connection.cursor() as cursor:
                    cursor.execute("SET lock_timeout = '5s'")
                    cursor.execute("SELECT pg_backend_pid()")
                    pids.put(cursor.fetchone()[0])
                guardar()
                resultados.put(None)
            except Exception as error:
                resultados.put(repr(error))
            finally:
                connections.close_all()

        hilo = threading.Thread(target=trabajar, daemon=True)
        hilo.start()
        pid = pids.get(timeout=6)
        limite = time.monotonic() + 3
        bloqueado = False
        while time.monotonic() < limite:
            with connection.cursor() as cursor:
                cursor.execute("SELECT pg_blocking_pids(%s)", [pid])
                bloqueado = bool(cursor.fetchone()[0])
            if bloqueado:
                break
            threading.Event().wait(0.01)
        return hilo, resultados, bloqueado

    def _terminar(self, trabajo):
        hilo, resultados, bloqueado = trabajo
        hilo.join(timeout=6)
        self.assertFalse(hilo.is_alive(), "La segunda conexión no terminó.")
        self.assertTrue(bloqueado, "No se observó espera real entre conexiones.")
        self.assertIsNone(resultados.get(timeout=1))

    def test_escritor_con_instancia_antigua_no_conserva_una_firma_posterior(self):
        self._firmar()
        antigua = Analisis.objects.get(pk=self.analisis.pk)
        with transaction.atomic():
            Analisis.objects.select_for_update().get(pk=self.analisis.pk)
            trabajo = self._iniciar(lambda: antigua.save(update_fields=["valores"]))
            self.analisis.valores = {"mg": 29.0}
            self.analisis.save(update_fields=["valores"])
            nueva = self._firmar().firma_id
        self._terminar(trabajo)
        firma = Liberacion.objects.get(lote=self.lote)
        self.assertEqual(firma.firma_id, nueva)
        self.assertEqual(firma.estado, Liberacion.Estado.EN_REVISION)
        self.analisis.valores = {"mg": 29.0}
        self.analisis.save(update_fields=["valores"])
        with self.assertRaises(ValidationError):
            with transaction.atomic():
                exigir_liberacion_lote_vigente(self.lote.pk)

    def test_alta_de_especificacion_espera_la_firma_y_luego_la_invalida(self):
        def crear():
            Especificacion.objects.create(
                producto_id=self.producto.pk, version=2, vigente_desde=date(2026, 7, 1),
                rangos={"mg": {"min": 26, "max": 30, "obligatorio": True}},
            )

        with transaction.atomic():
            self._firmar()
            trabajo = self._iniciar(crear)
        self._terminar(trabajo)
        self.assertEqual(Liberacion.objects.get(lote=self.lote).estado, Liberacion.Estado.EN_REVISION)

    def test_alta_de_analisis_espera_la_firma_y_luego_la_invalida(self):
        def crear():
            Analisis.objects.create(lote_id=self.lote.pk, fecha=self.lote.fecha, valores={"mg": 29.0})

        with transaction.atomic():
            self._firmar()
            trabajo = self._iniciar(crear)
        self._terminar(trabajo)
        self.assertEqual(Liberacion.objects.get(lote=self.lote).estado, Liberacion.Estado.EN_REVISION)
