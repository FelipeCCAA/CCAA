"""El TK queda protegido antes de bloquear la evidencia compartida de Calidad."""

from queue import Queue
from threading import Thread
from unittest.mock import patch

from django.db import DatabaseError, connection, connections, transaction
from django.test import TransactionTestCase

from calidad import vigencia
from inventario import tests_op01_concurrencia_despacho as carreras_despacho
from inventario import tests_op01_despacho as escenarios_despacho
from inventario.servicios import autorizar_despacho
from maestros.models import Silo
from produccion.models import Lote

from . import servicios
from . import tests_mantequilla as escenarios_mantequilla
from . import tests_op04_secado as escenarios_secado
from . import tests_op05_mantequilla as regresiones_mantequilla
from .models import SalidaProceso


class OrdenBloqueosCompartidosOP05Tests(TransactionTestCase):
    def setUp(self):
        if connection.vendor != "postgresql":
            self.skipTest("Requiere bloqueos de filas entre conexiones PostgreSQL.")

    def _fila_esta_protegida(self, identificador, modelo=Silo):
        resultado = Queue()

        def intentar_tomar_tk():
            try:
                with transaction.atomic():
                    modelo.objects.select_for_update(nowait=True).get(pk=identificador)
                resultado.put("libre")
            except DatabaseError as error:
                codigo = getattr(error.__cause__, "pgcode", None)
                resultado.put("bloqueado" if codigo == "55P03" else repr(error))
            except Exception as error:
                resultado.put(repr(error))
            finally:
                connections.close_all()

        hilo = Thread(target=intentar_tomar_tk, daemon=True)
        hilo.start()
        hilo.join(timeout=5)
        self.assertFalse(hilo.is_alive(), "El observador del TK no terminó.")
        self.assertEqual(resultado.get(timeout=1), "bloqueado")

    def test_secado_protege_tk_antes_de_evidencia_compartida(self):
        escenarios_secado.CierreSecadoOP04Tests.setUp(self)
        verificar_real = vigencia.exigir_liberacion_salida_vigente
        observaciones = []

        def comprobar(salida_id, **kwargs):
            silo_id = SalidaProceso.objects.get(pk=salida_id).silo_id
            self._fila_esta_protegida(silo_id)
            observaciones.append(silo_id)
            return verificar_real(salida_id, **kwargs)

        def firmar(*args, **kwargs):
            # El fixture original es TestCase; aquí la firma debe confirmar
            # su propia transacción antes de observarla desde otra conexión.
            with transaction.atomic():
                return vigencia.registrar_firma_salida(*args, **kwargs)

        self._cierre = escenarios_secado.CierreSecadoOP04Tests._cierre.__get__(self)
        with (patch.object(vigencia, "exigir_liberacion_salida_vigente", comprobar),
              patch.object(escenarios_secado, "registrar_firma_salida", firmar)):
            escenarios_secado.CierreSecadoOP04Tests.test_continuacion_litros_retira_silo_en_mismo_cierre(self)
        self.assertGreaterEqual(len(observaciones), 3)

    def test_despacho_protege_tk_antes_de_evidencia_compartida(self):
        carreras_despacho.ConcurrenciaDespachoOP01Tests.setUp(self)
        salida, silo = escenarios_despacho.VigenciaDespachoOP01Tests._granel(self)
        hoja = escenarios_despacho.VigenciaDespachoOP01Tests._hoja(self, salida=salida)
        bloquear_real = vigencia.bloquear_evidencias_despacho
        observaciones = []

        def comprobar(**kwargs):
            self._fila_esta_protegida(silo.pk)
            observaciones.append(silo.pk)
            return bloquear_real(**kwargs)

        with patch.object(vigencia, "bloquear_evidencias_despacho", comprobar):
            autorizar_despacho(hoja, self.usuario)
        self.assertEqual(observaciones, [silo.pk])

    def test_continuacion_protege_lote_antes_de_disputar_la_salida(self):
        escenarios_mantequilla.MantequillaTests.setUp(self)
        with transaction.atomic():
            fuente, _, _ = regresiones_mantequilla.MantequillaOp05BaselineTests._origen_tk(self)
        siguiente_real = servicios.siguiente_etapa_para_salida
        observaciones = []

        def comprobar(**kwargs):
            self._fila_esta_protegida(self.lote_crema.pk, Lote)
            observaciones.append(self.lote_crema.pk)
            return siguiente_real(**kwargs)

        with patch.object(servicios, "siguiente_etapa_para_salida", comprobar):
            servicios.preparar_continuacion(
                salida_id=fuente.pk, etapa_id=self.corrida.ejecucion.etapa_id,
                equipo_id=self.corrida.ejecucion.equipo_id,
                cantidad="100", usuario=self.usuario,
            )
        self.assertEqual(observaciones, [self.lote_crema.pk])
