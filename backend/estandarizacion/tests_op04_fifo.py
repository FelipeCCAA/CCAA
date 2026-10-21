"""FIFO se decide al confirmar, sin confiar en la sugerencia del cliente."""

from datetime import timedelta
from decimal import Decimal
from queue import Queue
import threading
import time
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.db import connection, connections
from django.test import TransactionTestCase
from django.utils import timezone

from inventario.models import CicloCIP
from maestros.models import Silo
from procesos.models import EventoProceso, ReservaSiloProceso
from recepcion.models import AnalisisSilo, MovimientoSilo
from rest_framework.test import APIClient
from usuarios.models import PerfilUsuario, Rol

from . import servicios
from .tests_vale import BaseVale


class ConfirmacionFIFOOP04Tests(BaseVale):
    def setUp(self):
        self.abastecer_origenes()
        self.analizar_origenes()
        self.antiguo = Silo.objects.create(
            codigo="OP04-ANTIGUO", tipo=Silo.Tipo.SILO, capacidad_l=50000,
        )
        MovimientoSilo.objects.create(
            silo=self.antiguo, tipo=MovimientoSilo.Tipo.INGRESO,
            litros=10000, fecha_hora=timezone.now() - timedelta(hours=2),
            motivo="Stock sintético anterior",
        )
        self.analisis_antiguo = AnalisisSilo.objects.create(
            silo=self.antiguo, tomado_en=timezone.now(), grasa="4.20", sng="8.80",
            inhibidores_resultado="negativo", metodo="delvo_sp",
            hora_lectura=timezone.localtime().time(), analista=self.usuario,
            visualizado_por=self.visualizador, visualizado_en=timezone.now(),
            estado=AnalisisSilo.Estado.CONFIRMADO,
        )

    def _foto(self):
        return list(MovimientoSilo.objects.order_by("pk").values())

    def test_omitir_sugerencia_no_elude_justificacion_fifo(self):
        vale = self.crear_vale()
        antes = self._foto()
        with self.assertRaisesMessage(ValidationError, "FIFO"):
            servicios.transferir(vale_id=vale.pk, usuario=self.usuario)
        self.assertEqual(antes, self._foto())

        vale.refresh_from_db()
        self.assertIsNone(vale.ejecutado_en)

    def test_falsificar_sugerencia_no_elude_recalculo_del_servidor(self):
        vale = self.crear_vale(silo_sugerido_fifo=self.silo_entera)
        with self.assertRaisesMessage(ValidationError, "FIFO"):
            servicios.transferir(vale_id=vale.pk, usuario=self.usuario)

    def test_excepcion_registra_origen_recomendado_usuario_fecha_y_no_duplica(self):
        vale = self.crear_vale(motivo_desvio_fifo="Prioridad documentada de la línea")
        servicios.transferir(vale_id=vale.pk, usuario=self.usuario)
        vale.refresh_from_db()
        self.assertEqual(vale.silo_sugerido_fifo_id, self.antiguo.pk)
        evento = EventoProceso.objects.get(ejecucion__vale=vale, tipo="desvio_fifo")
        self.assertEqual(evento.usuario_id, self.usuario.pk)
        self.assertIsNotNone(evento.fecha_hora)
        self.assertEqual(evento.datos["silo_recomendado"], self.antiguo.pk)
        self.assertEqual(evento.datos["silo_utilizado"], self.silo_entera.pk)
        self.assertEqual(evento.motivo, vale.motivo_desvio_fifo)
        antes = self._foto()
        servicios.transferir(vale_id=vale.pk, usuario=self.usuario)
        self.assertEqual(antes, self._foto())
        self.assertEqual(EventoProceso.objects.filter(
            ejecucion__vale=vale, tipo="desvio_fifo",
        ).count(), 1)

    def test_origen_mas_antiguo_rechazado_no_es_recomendable(self):
        self.analisis_antiguo.inhibidores_resultado = "positivo"
        self.analisis_antiguo.save(update_fields=["inhibidores_resultado"])
        vale = self.crear_vale()
        servicios.transferir(vale_id=vale.pk, usuario=self.usuario)
        vale.refresh_from_db()
        self.assertEqual(vale.silo_sugerido_fifo_id, self.silo_entera.pk)

    def test_origen_mas_antiguo_en_cip_no_es_recomendable(self):
        CicloCIP.objects.create(
            silo=self.antiguo, tipo_objetivo=CicloCIP.TipoObjetivo.SILO,
            estado=CicloCIP.Estado.EN_CURSO, inicio=timezone.now(),
        )
        vale = self.crear_vale()
        servicios.transferir(vale_id=vale.pk, usuario=self.usuario)
        vale.refresh_from_db()
        self.assertEqual(vale.silo_sugerido_fifo_id, self.silo_entera.pk)

    def test_reserva_total_excluye_origen_antiguo_y_no_se_toca(self):
        # La reserva pertenece a otra ejecución, independiente del vale a ejecutar.
        from procesos.models import EjecucionProceso, EtapaProceso
        etapa = EtapaProceso.objects.get(codigo="estandarizar-test")
        ejecucion = EjecucionProceso.objects.create(codigo="OP04-AJENA", etapa=etapa)
        reserva = ReservaSiloProceso.objects.create(
            ejecucion=ejecucion, silo=self.antiguo,
            tipo=ReservaSiloProceso.Tipo.ORIGEN, cantidad_planificada=Decimal("10000"),
        )
        vale = self.crear_vale()
        servicios.transferir(vale_id=vale.pk, usuario=self.usuario)
        vale.refresh_from_db()
        self.assertEqual(vale.silo_sugerido_fifo_id, self.silo_entera.pk)
        reserva.refresh_from_db()
        self.assertEqual(reserva.estado, ReservaSiloProceso.Estado.ACTIVA)

    def test_motivo_no_habilita_material_rechazado(self):
        AnalisisSilo.objects.filter(silo=self.silo_entera).update(
            inhibidores_resultado="positivo",
        )
        vale = self.crear_vale(motivo_desvio_fifo="Prioridad documentada de la línea")
        antes = self._foto()
        with self.assertRaises(ValidationError):
            servicios.transferir(vale_id=vale.pk, usuario=self.usuario)
        self.assertEqual(antes, self._foto())

    def test_api_rechaza_transferencia_sin_motivo_y_conserva_libro(self):
        PerfilUsuario.objects.create(usuario=self.usuario, rol=Rol.PRODUCCION)
        api = APIClient()
        api.force_authenticate(self.usuario)
        vale = self.crear_vale(silo_sugerido_fifo=self.silo_entera)
        antes = self._foto()
        respuesta = api.post(f"/api/estandarizacion/vales/{vale.pk}/transferir/")
        self.assertEqual(respuesta.status_code, 409, respuesta.data)
        self.assertIn("FIFO", str(respuesta.data))
        self.assertEqual(antes, self._foto())

class CalidadConcurrenteFIFOOP04Tests(TransactionTestCase):
    def setUp(self):
        if connection.vendor != "postgresql":
            self.skipTest("Requiere bloqueos PostgreSQL entre conexiones.")
        BaseVale.setUpTestData.__func__(type(self))
        BaseVale.abastecer_origenes(self)
        BaseVale.analizar_origenes(self)

    def test_cambio_de_inhibidores_espera_hasta_confirmar_transferencia(self):
        vale = BaseVale.crear_vale(self)
        analisis_id = AnalisisSilo.objects.get(silo=self.silo_entera).pk
        resultados, pids = Queue(), Queue()
        terminado = threading.Event()
        crear_real = servicios.crear_en_lote_con_auditoria
        hilo = None
        observado = []

        def corregir_calidad():
            try:
                with connection.cursor() as cursor:
                    cursor.execute("SET lock_timeout = '8s'")
                    cursor.execute("SELECT pg_backend_pid()")
                    pids.put(cursor.fetchone()[0])
                analisis = AnalisisSilo.objects.get(pk=analisis_id)
                analisis.inhibidores_resultado = "positivo"
                analisis.save(update_fields=["inhibidores_resultado"])
                resultados.put("corregido")
            except Exception as error:
                resultados.put(repr(error))
            finally:
                terminado.set()
                connections.close_all()

        def intercalar(*args, **kwargs):
            nonlocal hilo
            hilo = threading.Thread(target=corregir_calidad, daemon=True)
            hilo.start()
            pid = pids.get(timeout=5)
            with connection.cursor() as cursor:
                cursor.execute("SELECT pg_backend_pid()")
                lector_pid = cursor.fetchone()[0]
            limite = time.monotonic() + 3
            bloqueado = False
            while time.monotonic() < limite:
                with connection.cursor() as cursor:
                    cursor.execute("SELECT %s = ANY(pg_blocking_pids(%s))", [lector_pid, pid])
                    bloqueado = cursor.fetchone()[0]
                if bloqueado or terminado.is_set():
                    break
                threading.Event().wait(0.01)
            observado.append(bloqueado)
            return crear_real(*args, **kwargs)

        try:
            with patch.object(servicios, "crear_en_lote_con_auditoria", intercalar):
                servicios.transferir(vale_id=vale.pk, usuario=self.usuario)
        finally:
            if hilo is not None:
                hilo.join(timeout=10)
                self.assertFalse(hilo.is_alive(), "Quedó una corrección de Calidad en ejecución.")
        self.assertEqual(observado, [True], "Calidad cambió antes de confirmar el retiro.")
        self.assertEqual(resultados.get(timeout=1), "corregido")
        self.assertEqual(MovimientoSilo.objects.filter(
            origen_tipo=MovimientoSilo.OrigenTipo.ESTANDARIZACION,
            origen_id=vale.pk, tipo=MovimientoSilo.Tipo.SALIDA,
            silo=self.silo_entera,
        ).count(), 1)
