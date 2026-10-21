"""PostgreSQL races for OP-05: retry and last available cream."""

from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
from threading import Event, local
from time import monotonic, sleep
from unittest import skipUnless
from unittest.mock import patch
from uuid import uuid4

from django.core.exceptions import ValidationError
from django.db import connection, connections, transaction
from django.test import TransactionTestCase
from django.utils import timezone

from calidad.models import LiberacionProceso
from maestros.models import Equipo
from recepcion.models import MovimientoSilo

from . import tests_mantequilla as fixtures
from . import tests_op05_mantequilla as regresiones
from .models import EntradaProceso, EventoProceso
from .servicios import crear_mantequilla_guiada, iniciar_mantequilla


@skipUnless(connection.vendor == "postgresql", "La carrera exige bloqueos PostgreSQL reales.")
class MantequillaOp05ConcurrenciaTests(TransactionTestCase):
    def setUp(self):
        fixtures.MantequillaTests.setUp(self)
        with transaction.atomic():
            regresiones.MantequillaOp05BaselineTests._origen_tk(self)

    def _esperar_bloqueo(self, pid):
        limite = monotonic() + 8
        while monotonic() < limite:
            with connection.cursor() as cursor:
                cursor.execute("SELECT pg_blocking_pids(%s)", [pid])
                if cursor.fetchone()[0]:
                    return
            sleep(0.05)
        self.fail("El segundo operador no llegó a esperar un bloqueo real en PostgreSQL.")

    def _carrera(self, *, primero_id, segundo_id, punto_bloqueo):
        import procesos.servicios as servicios

        hilo = local()
        primero_tiene_lock = Event()
        liberar_primero = Event()
        segundo_conectado = Event()
        pids = {}
        original = getattr(servicios, punto_bloqueo)

        def interceptar(*args, **kwargs):
            resultado = original(*args, **kwargs)
            if getattr(hilo, "nombre", None) == "primero":
                primero_tiene_lock.set()
                if not liberar_primero.wait(timeout=10):
                    raise AssertionError("No se liberó al primer operador.")
            return resultado

        def ejecutar(nombre, corrida_id, operacion_id):
            hilo.nombre = nombre
            try:
                with connection.cursor() as cursor:
                    cursor.execute("SELECT pg_backend_pid()")
                    pids[nombre] = cursor.fetchone()[0]
                if nombre == "segundo":
                    segundo_conectado.set()
                try:
                    corrida = iniciar_mantequilla(
                        corrida_id=corrida_id, usuario=self.usuario,
                        operacion_id=operacion_id,
                    )
                    return ("ok", corrida.pk)
                except ValidationError:
                    return ("rechazado", None)
            finally:
                connections.close_all()

        with patch.object(servicios, punto_bloqueo, side_effect=interceptar):
            with ThreadPoolExecutor(max_workers=2) as ejecutor:
                primero = ejecutor.submit(ejecutar, "primero", *primero_id)
                try:
                    self.assertTrue(primero_tiene_lock.wait(timeout=8))
                    segundo = ejecutor.submit(ejecutar, "segundo", *segundo_id)
                    self.assertTrue(segundo_conectado.wait(timeout=8))
                    self._esperar_bloqueo(pids["segundo"])
                finally:
                    liberar_primero.set()
                return primero.result(timeout=10), segundo.result(timeout=10)

    def test_dos_conexiones_mismo_uuid_recuperan_un_solo_consumo(self):
        inicio_id = uuid4()
        resultados = self._carrera(
            primero_id=(self.corrida.pk, inicio_id),
            segundo_id=(self.corrida.pk, inicio_id),
            punto_bloqueo="_bloquear_operacion_mantequilla",
        )
        self.assertEqual(resultados, (("ok", self.corrida.pk), ("ok", self.corrida.pk)))
        self.assertEqual(EntradaProceso.objects.filter(ejecucion=self.corrida.ejecucion).count(), 1)
        self.assertEqual(MovimientoSilo.objects.filter(
            operacion_id=self.corrida.operacion_id,
            tipo=MovimientoSilo.Tipo.SALIDA,
        ).count(), 1)
        self.assertEqual(EventoProceso.objects.filter(operacion_id=inicio_id).count(), 1)

    def test_dos_corridas_compiten_ultimos_kg_y_perdedor_no_consume(self):
        self.lote_crema.kg_producidos = Decimal("200")
        self.lote_crema.save(update_fields=["kg_producidos"])
        # La firma incluye el lote; se renueva después del cambio de kg.
        from calidad.vigencia import registrar_firma_salida

        salida = self.corrida.salida_crema
        with transaction.atomic():
            decision = LiberacionProceso.objects.select_for_update().get(salida_id=salida.pk)
            decision.estado = LiberacionProceso.Estado.LIBERADO
            decision.decidida_por = self.usuario
            decision.decidida_en = timezone.now()
            decision.save(update_fields=["estado", "decidida_por", "decidida_en"])
            registrar_firma_salida(decision)
        otro_equipo = Equipo.objects.create(
            sucursal=self.planta, codigo="mant-op05-dos", nombre="Línea 2",
            tipo=Equipo.Tipo.LINEA,
        )
        segunda = crear_mantequilla_guiada(
            orden_id=self.corrida.orden_id, lote_crema_id=self.lote_crema.pk,
            salida_crema_id=salida.pk, equipo_id=otro_equipo.pk,
            codigo_lote_mantequilla="MANT-OP05-DOS", kg_crema="200",
            usuario=self.usuario, operacion_id=uuid4(),
        )
        resultados = self._carrera(
            primero_id=(self.corrida.pk, uuid4()),
            segundo_id=(segunda.pk, uuid4()),
            punto_bloqueo="_disponible_lote_crema",
        )
        self.assertEqual(resultados[0], ("ok", self.corrida.pk))
        self.assertEqual(resultados[1], ("rechazado", None))
        self.assertEqual(EntradaProceso.objects.filter(
            salida_origen_id=salida.pk,
        ).count(), 1)
        self.assertEqual(MovimientoSilo.objects.filter(
            tipo=MovimientoSilo.Tipo.SALIDA, lote=self.lote_crema,
        ).count(), 1)
