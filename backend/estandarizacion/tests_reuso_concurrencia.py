"""Comprobación del lock real del silo y de su FK con dos conexiones PostgreSQL."""
from decimal import Decimal
from queue import Queue
import threading
import time
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.db import connection, connections, transaction
from django.test import TransactionTestCase

from procesos.models import EntradaProceso, SalidaProceso
from recepcion.models import MovimientoSilo, Recepcion
from recepcion.servicios import saldo_silo

from . import origenes
from .servicios import transferir
from . import tests_reuso_recepcion as escenarios
from .tests_vale import BaseVale


class ReusoConcurrenciaTests(TransactionTestCase):
    crear_vale = BaseVale.crear_vale
    analizar_origenes = BaseVale.analizar_origenes
    _fuente = escenarios.ReusoRecepcionTests._fuente

    def setUp(self):
        with transaction.atomic():
            BaseVale.setUpTestData.__func__(type(self))
            escenarios.ReusoRecepcionTests.setUp(self)

    def test_alta_salida_no_confirma_entre_validacion_del_ciclo_y_commit(self):
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT condeferrable, condeferred, convalidated FROM pg_constraint "
                "WHERE conrelid='procesos_salidaproceso'::regclass AND contype='f' "
                "AND confrelid='maestros_silo'::regclass",
            )
            self.assertEqual(cursor.fetchall(), [(True, True, True)])
        comprobado, continuar = threading.Event(), threading.Event()
        resultados, escritores = Queue(), Queue()
        original = origenes.preparar_origenes

        def validar(*args, **kwargs):
            resultado = original(*args, **kwargs)
            comprobado.set()
            if not continuar.wait(10):
                raise AssertionError("No se liberó el consumidor")
            return resultado

        def consumir():
            try:
                connections.close_all()
                with connection.cursor() as cursor:
                    cursor.execute("SET lock_timeout = '12s'")
                transferir(vale_id=self.vale.pk, usuario=self.usuario)
                resultados.put("vale confirmado")
            except Exception as error:
                resultados.put(error)
            finally:
                connections.close_all()

        def producir():
            try:
                connections.close_all()
                with connection.cursor() as cursor:
                    cursor.execute("SET lock_timeout = '12s'")
                    cursor.execute("SELECT pg_backend_pid()")
                    escritores.put(cursor.fetchone()[0])
                with transaction.atomic():
                    SalidaProceso.objects.create(
                        ejecucion_id=self.consumidora.pk, silo_id=self.silo_entera.pk,
                        cantidad="1", unidad="kg",
                    )
                resultados.put("salida confirmada")
            except Exception as error:
                resultados.put(error)
            finally:
                connections.close_all()

        consumidor = threading.Thread(target=consumir, daemon=True)
        escritor = threading.Thread(target=producir, daemon=True)
        with patch.object(origenes, "preparar_origenes", side_effect=validar):
            try:
                consumidor.start()
                self.assertTrue(comprobado.wait(8), "El vale no alcanzó la validación bajo lock")
                escritor.start()
                pid = escritores.get(timeout=8)
                limite, bloqueado = time.monotonic() + 8, False
                while time.monotonic() < limite:
                    with connection.cursor() as cursor:
                        cursor.execute("SELECT cardinality(pg_blocking_pids(%s))>0", [pid])
                        bloqueado = cursor.fetchone()[0]
                    if bloqueado:
                        break
                    time.sleep(0.02)
                self.assertTrue(bloqueado, "La FK no serializó la nueva salida con el silo bloqueado")
                self.assertTrue(resultados.empty(), "Ninguna transacción debe haber confirmado aún")
            finally:
                continuar.set()
                consumidor.join(timeout=15)
                if escritor.ident is not None:
                    escritor.join(timeout=15)
        self.assertFalse(consumidor.is_alive() or escritor.is_alive())
        obtenidos = [resultados.get(timeout=1) for _ in range(2)]
        for resultado in obtenidos:
            if isinstance(resultado, Exception):
                raise resultado
        self.assertCountEqual(obtenidos, ["vale confirmado", "salida confirmada"])
        self.assertEqual(saldo_silo(self.silo_entera), Decimal("4300.53"))
        self.assertEqual(EntradaProceso.objects.filter(ejecucion__vale=self.vale, silo=self.silo_entera).count(), 1)
        self.assertEqual(MovimientoSilo.objects.filter(origen_tipo="estandarizacion", origen_id=self.vale.pk).count(), 3)

    def test_salida_que_confirma_primero_obliga_a_rechazar_el_vale(self):
        resultados, pids = Queue(), Queue()

        def consumir():
            try:
                connections.close_all()
                with connection.cursor() as cursor:
                    cursor.execute("SET lock_timeout = '12s'")
                    cursor.execute("SELECT pg_backend_pid()")
                    pids.put(cursor.fetchone()[0])
                transferir(vale_id=self.vale.pk, usuario=self.usuario)
                resultados.put("confirmado")
            except ValidationError:
                resultados.put("conflicto")
            except Exception as error:
                resultados.put(error)
            finally:
                connections.close_all()

        hilo = threading.Thread(target=consumir, daemon=True)
        try:
            with transaction.atomic():
                SalidaProceso.objects.create(
                    ejecucion_id=self.consumidora.pk, silo_id=self.silo_entera.pk,
                    cantidad="1", unidad="L",
                )
                with connection.cursor() as cursor:
                    cursor.execute("SET CONSTRAINTS ALL IMMEDIATE")
                hilo.start()
                pid = pids.get(timeout=8)
                limite, bloqueado = time.monotonic() + 8, False
                while time.monotonic() < limite:
                    with connection.cursor() as cursor:
                        cursor.execute("SELECT cardinality(pg_blocking_pids(%s))>0", [pid])
                        bloqueado = cursor.fetchone()[0]
                    if bloqueado:
                        break
                    time.sleep(0.02)
                self.assertTrue(bloqueado, "El consumidor no esperó la FK de la nueva salida")
        finally:
            hilo.join(timeout=15)
        self.assertFalse(hilo.is_alive())
        resultado = resultados.get(timeout=1)
        if isinstance(resultado, Exception):
            raise resultado
        self.assertEqual(resultado, "conflicto")
        self.assertEqual(saldo_silo(self.silo_entera), Decimal("15000"))
        self.assertFalse(EntradaProceso.objects.filter(ejecucion__vale=self.vale).exists())
        self.assertFalse(MovimientoSilo.objects.filter(origen_tipo="estandarizacion", origen_id=self.vale.pk).exists())

    def test_tipo_de_recepcion_no_cambia_mientras_se_transfiere(self):
        resultados = Queue()
        original = origenes.preparar_origenes

        def cambiar_tipo():
            try:
                connections.close_all()
                recepcion = Recepcion.objects.get(pk=self.recepcion.pk)
                recepcion.tipo_leche = Recepcion.TipoLeche.DESCREMADA
                recepcion.save()
                resultados.put("modificado")
            except ValidationError:
                resultados.put("conflicto")
            except Exception as error:
                resultados.put(error)
            finally:
                connections.close_all()

        def validar(*args, **kwargs):
            resultado = original(*args, **kwargs)
            hilo = threading.Thread(target=cambiar_tipo, daemon=True)
            hilo.start()
            hilo.join(timeout=8)
            self.assertFalse(hilo.is_alive(), "El cambio de tipo no resolvió durante la transferencia")
            recibido = resultados.get(timeout=1)
            if isinstance(recibido, Exception):
                raise recibido
            self.assertEqual(recibido, "conflicto")
            return resultado

        with patch.object(origenes, "preparar_origenes", side_effect=validar):
            transferir(vale_id=self.vale.pk, usuario=self.usuario)
        self.recepcion.refresh_from_db()
        self.assertEqual(self.recepcion.tipo_leche, Recepcion.TipoLeche.ENTERA)
        self.assertEqual(saldo_silo(self.silo_entera), Decimal("4300.53"))
