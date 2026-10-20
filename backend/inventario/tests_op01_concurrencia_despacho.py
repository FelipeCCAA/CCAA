"""Carreras OP-01 en PostgreSQL, con evidencia de espera real entre conexiones."""

from queue import Queue
import threading
import time

from django.core.exceptions import ValidationError
from django.db import connection, connections, transaction
from django.test import TransactionTestCase

from maestros.models import Silo

from .models import (
    Despacho, DetalleDespacho, ExistenciaProductoTerminado,
    MovimientoProductoTerminado, Ubicacion,
)
from .pruebas_base import EscenarioProductoTerminado
from .servicios import (
    autorizar_despacho, ejecutar_despacho, ingresar_pallet, transferir_pallet,
)
from . import tests_op01_despacho as escenario_op01


class ConcurrenciaDespachoOP01Tests(TransactionTestCase):
    def setUp(self):
        if not connection.features.has_select_for_update:
            self.skipTest("Se requiere PostgreSQL con bloqueos de filas reales.")
        EscenarioProductoTerminado.setUp(self)
        EscenarioProductoTerminado.liberar(self)
        ingresar_pallet(self.pallet, self.ubicacion, self.usuario)
        self.secuencia = 0

    def _hoja_pallet(self):
        hoja = Despacho.objects.create(
            sucursal=self.planta, numero="OP01-CARRERA", cliente=self.cliente,
            creado_por=self.usuario,
        )
        DetalleDespacho.objects.create(despacho=hoja, pallet=self.pallet)
        autorizar_despacho(hoja, self.usuario)
        return hoja

    def _trabajador(self, hoja, resultados, pids=None, barrera=None):
        try:
            with connection.cursor() as cursor:
                cursor.execute("SET lock_timeout = '4s'")
                cursor.execute("SELECT pg_backend_pid()")
                pid = cursor.fetchone()[0]
            if pids is not None:
                pids.put(pid)
            if barrera is not None:
                barrera.wait(timeout=6)
            resultado = ejecutar_despacho(hoja, self.usuario)
            resultados.put(("ok", resultado.pk))
        except ValidationError as error:
            resultados.put(("rechazado", str(error)))
        except Exception as error:  # Propaga un diagnóstico visible al test.
            resultados.put(("error", repr(error)))
        finally:
            connections.close_all()

    def _esperar_bloqueo(self, pid):
        limite = time.monotonic() + 3
        while time.monotonic() < limite:
            with connection.cursor() as cursor:
                cursor.execute("SELECT pg_blocking_pids(%s)", [pid])
                if cursor.fetchone()[0]:
                    return True
            # Se espera una condición SQL observable, no una pausa que suponga
            # que el trabajador ya alcanzó el punto de carrera.
            threading.Event().wait(0.01)
        return False

    def _ejecutar_mientras_cambia(self, hoja, cambiar):
        resultados = Queue()
        pids = Queue()
        hilo = threading.Thread(
            target=self._trabajador, args=(hoja, resultados, pids), daemon=True,
        )
        try:
            with transaction.atomic():
                cambiar()
                hilo.start()
                pid = pids.get(timeout=6)
                bloqueado = self._esperar_bloqueo(pid)
        finally:
            if hilo.ident is not None:
                hilo.join(timeout=6)
        self.assertFalse(hilo.is_alive(), "La segunda conexión no terminó.")
        self.assertTrue(bloqueado, "No se observó una espera real de bloqueo en PostgreSQL.")
        resultado, detalle = resultados.get(timeout=1)
        self.assertEqual(resultado, "rechazado", detalle)

    def test_transferencia_y_ejecucion_no_despachan_un_pallet_en_cuarentena(self):
        hoja = self._hoja_pallet()
        cuarentena = Ubicacion.objects.create(
            bodega=self.ubicacion.bodega, codigo="OP01-CARRERA-CUAR",
            tipo=Ubicacion.Tipo.CUARENTENA,
        )

        self._ejecutar_mientras_cambia(hoja, lambda: transferir_pallet(
            self.pallet.existencia_producto, cuarentena, self.usuario,
        ))

        self.assertTrue(ExistenciaProductoTerminado.objects.get(pallet=self.pallet).activo)
        self.assertFalse(MovimientoProductoTerminado.objects.filter(
            despacho=hoja, tipo=MovimientoProductoTerminado.Tipo.DESPACHO,
        ).exists())
        hoja.refresh_from_db()
        self.assertEqual(hoja.estado, Despacho.Estado.AUTORIZADO)

    def test_bloqueo_silo_y_ejecucion_no_desplazan_material_bloqueado(self):
        salida, silo = escenario_op01.VigenciaDespachoOP01Tests._granel(self)
        hoja = escenario_op01.VigenciaDespachoOP01Tests._hoja(self, salida=salida)
        autorizar_despacho(hoja, self.usuario)

        def bloquear_silo():
            actual = Silo.objects.select_for_update().get(pk=silo.pk)
            actual.estado = Silo.Estado.BLOQUEADO_CALIDAD
            actual.save(update_fields=["estado"])

        self._ejecutar_mientras_cambia(hoja, bloquear_silo)

        escenario_op01.VigenciaDespachoOP01Tests._sin_salida(self, hoja, silo=silo)

    def test_dos_ejecuciones_simultaneas_generan_una_sola_salida(self):
        hoja = self._hoja_pallet()
        resultados = Queue()
        barrera = threading.Barrier(3)
        hilos = [threading.Thread(
            target=self._trabajador, args=(hoja, resultados),
            kwargs={"barrera": barrera}, daemon=True,
        ) for _ in range(2)]
        for hilo in hilos:
            hilo.start()
        barrera.wait(timeout=6)
        for hilo in hilos:
            hilo.join(timeout=6)
            self.assertFalse(hilo.is_alive(), "La ejecución concurrente no terminó.")
        for _ in hilos:
            resultado, detalle = resultados.get(timeout=1)
            self.assertEqual(resultado, "ok", detalle)
        self.assertEqual(MovimientoProductoTerminado.objects.filter(
            despacho=hoja, tipo=MovimientoProductoTerminado.Tipo.DESPACHO,
        ).count(), 1)
        self.assertFalse(ExistenciaProductoTerminado.objects.get(pallet=self.pallet).activo)
