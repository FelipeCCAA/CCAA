"""Dos vales reales disputan el mismo material bajo conexiones independientes."""
from decimal import Decimal
from queue import Queue
import threading
import time

from django.core.exceptions import ValidationError
from django.db import connection, connections, transaction
from django.test import TransactionTestCase

from maestros.models import Silo
from procesos.models import EntradaProceso, SalidaProceso
from recepcion.models import MovimientoSilo
from recepcion.servicios import saldo_silo

from .servicios import transferir
from . import tests_f01_f02_materiales as escenarios
from .tests_vale import BaseVale


class CarreraMaterialesF01F02Tests(TransactionTestCase):
    crear_vale = BaseVale.crear_vale
    analizar_origenes = BaseVale.analizar_origenes
    _fuente = escenarios.MaterialesValeF01F02Tests._fuente

    def setUp(self):
        with transaction.atomic():
            BaseVale.setUpTestData.__func__(type(self))
            escenarios.MaterialesValeF01F02Tests.setUp(self)

    def test_dos_vales_no_consumen_dos_veces_el_ultimo_saldo(self):
        self.vale.litros_entera = Decimal("1000")
        self.vale.litros_descremada = Decimal("6000")
        self.vale.volumen = Decimal("7000")
        self.vale.save()
        destino2 = Silo.objects.create(
            codigo="DESTINO-CARRERA-F02", sucursal=self.silo_destino.sucursal,
            tipo=Silo.Tipo.SILO, capacidad_l=50000,
        )
        otro = self.crear_vale(
            codigo="VE-CARRERA-2", litros_entera="1000", litros_descremada="6000",
            volumen="7000", silo_destino=destino2,
        )
        resultados, pids = Queue(), Queue()

        def operar(vale_id):
            try:
                connections.close_all()
                with connection.cursor() as cursor:
                    cursor.execute("SET lock_timeout = '12s'")
                    cursor.execute("SELECT pg_backend_pid()")
                    pids.put(cursor.fetchone()[0])
                transferir(vale_id=vale_id, usuario=self.usuario)
                resultados.put("confirmado")
            except ValidationError:
                resultados.put("conflicto")
            except Exception as error:
                resultados.put(error)
            finally:
                connections.close_all()

        hilos = [threading.Thread(target=operar, args=(pk,), daemon=True) for pk in (self.vale.pk, otro.pk)]
        try:
            with transaction.atomic():
                SalidaProceso.objects.select_for_update().get(pk=self.fuente.pk)
                for hilo in hilos:
                    hilo.start()
                procesos = [pids.get(timeout=8) for _ in hilos]
                limite = time.monotonic() + 8
                bloqueados = 0
                while time.monotonic() < limite:
                    with connection.cursor() as cursor:
                        cursor.execute(
                            "SELECT count(*) FROM pg_stat_activity WHERE pid=ANY(%s) AND cardinality(pg_blocking_pids(pid))>0",
                            [procesos],
                        )
                        bloqueados = cursor.fetchone()[0]
                    if bloqueados == 2:
                        break
                    time.sleep(0.02)
                self.assertEqual(bloqueados, 2, "No se observaron las dos conexiones esperando el origen real")
        finally:
            for hilo in hilos:
                hilo.join(timeout=15)
        self.assertFalse(any(hilo.is_alive() for hilo in hilos))
        obtenidos = [resultados.get(timeout=1) for _ in hilos]
        for resultado in obtenidos:
            if isinstance(resultado, Exception):
                raise resultado
        self.assertCountEqual(obtenidos, ["confirmado", "conflicto"])
        self.assertEqual(saldo_silo(self.silo_descremada), Decimal("3150.08"))
        self.assertEqual(EntradaProceso.objects.filter(salida_origen=self.fuente).count(), 1)
        self.assertEqual(MovimientoSilo.objects.filter(silo=self.silo_descremada, tipo="salida").count(), 1)
