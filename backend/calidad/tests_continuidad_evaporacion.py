"""Una salida líquida pendiente puede alimentar Secado sin duplicar el retiro."""
from decimal import Decimal
from uuid import uuid4

from django.test import TestCase, override_settings

from calidad.models import LiberacionProceso
from maestros.models import Equipo, Producto, Silo
from procesos import tests_condensacion as escenarios_condensacion
from procesos.models import CorridaSecado, EjecucionProceso, EntradaProceso, EtapaProceso, EventoProceso, RutaProducto, SalidaProceso
from procesos.servicios import (
    cerrar_condensacion, cerrar_secado, iniciar_condensacion,
    preparar_continuacion, transicionar_ejecucion,
)
from recepcion.models import MovimientoSilo


@override_settings(CCAA_CALIDAD_INTERMEDIA_AVISO=True)
class ContinuidadEvaporacionSecadoTests(TestCase):
    def setUp(self):
        escenarios_condensacion.FlujoCondensacionTests.setUp(self)
        producto = self.lote.producto
        producto.codigo = "LP-CONT-TEST"
        producto.nombre = "Leche en polvo ficticia de continuidad"
        producto.familia = Producto.Familia.POLVO
        producto.categoria = Producto.Categoria.LECHE_POLVO
        producto.unidad_base = Producto.Unidad.KG
        producto.save(update_fields=["codigo", "nombre", "familia", "categoria", "unidad_base"])
        etapa_origen = self.ejecucion.etapa
        etapa_origen.requiere_calidad = True
        etapa_origen.save(update_fields=["requiere_calidad"])
        self.etapa_secado = EtapaProceso.objects.create(
            proceso=etapa_origen.proceso, codigo="secar-aviso", nombre="Secado de prueba",
            tipo=EtapaProceso.Tipo.SECADO, orden=2, requiere_calidad=True,
        )
        EtapaProceso.objects.create(
            proceso=etapa_origen.proceso, codigo="envasar-aviso", nombre="Envase de prueba",
            tipo=EtapaProceso.Tipo.ENVASADO, orden=3, requiere_calidad=True,
        )
        RutaProducto.objects.create(
            sucursal=self.planta, producto=self.lote.producto,
            proceso=etapa_origen.proceso,
            destino_final=RutaProducto.DestinoFinal.ENVASADO,
        )
        self.torre = Equipo.objects.create(
            sucursal=self.planta, codigo="TOR-AVISO", nombre="Torre de prueba",
            tipo=Equipo.Tipo.TORRE,
        )

    def test_precondensado_pendiente_llega_a_secado_con_un_retiro_y_polvo_pendiente(self):
        iniciar_condensacion(corrida_id=self.corrida.pk, usuario=self.usuario)
        cerrar_condensacion(
            corrida_id=self.corrida.pk, usuario=self.usuario,
            litros_precondensado="250", controles={"densidad_salida": "1.180"},
        )
        fuente = SalidaProceso.objects.get(ejecucion=self.ejecucion)
        self.destino.refresh_from_db()
        self.assertEqual(self.destino.estado, Silo.Estado.PENDIENTE_CALIDAD)
        self.assertEqual(fuente.destino, SalidaProceso.Destino.SIGUIENTE_PROCESO)
        self.assertFalse(LiberacionProceso.objects.filter(
            salida=fuente, firma_id__isnull=False,
        ).exists())

        continuacion = preparar_continuacion(
            salida_id=fuente.pk, etapa_id=self.etapa_secado.pk,
            equipo_id=self.torre.pk, cantidad=Decimal("250"), usuario=self.usuario,
        )
        self.assertEqual(continuacion.estado, EjecucionProceso.Estado.PREPARACION)
        entrada = EntradaProceso.objects.get(ejecucion=continuacion)
        self.assertEqual(entrada.salida_origen_id, fuente.pk)
        self.assertEqual(entrada.silo_id, self.destino.pk)
        self.assertEqual(entrada.cantidad, Decimal("250"))
        transicionar_ejecucion(
            ejecucion_id=continuacion.pk,
            estado_nuevo=EjecucionProceso.Estado.EJECUCION,
            usuario=self.usuario,
        )
        secado = CorridaSecado.objects.get(ejecucion=continuacion)
        cierre_id = uuid4()
        cerrar_secado(
            corrida_id=secado.pk, usuario=self.usuario,
            kg_alimentacion="250", solidos_entrada_pct="48",
            kg_polvo="115", kg_finos="3", kg_merma="2",
            referencia_medicion_kg="Ticket ficticio de báscula: 250 kg",
            operacion_id=cierre_id,
        )

        retiros = MovimientoSilo.objects.filter(
            silo=self.destino, tipo=MovimientoSilo.Tipo.SALIDA,
            origen_tipo=MovimientoSilo.OrigenTipo.PRODUCCION,
            origen_id=secado.pk,
        )
        self.assertEqual(retiros.count(), 1)
        self.assertEqual(retiros.get().litros, entrada.cantidad)
        self.assertEqual(retiros.get().operacion_id, cierre_id)
        salida_polvo = SalidaProceso.objects.get(
            ejecucion=continuacion, naturaleza=SalidaProceso.Naturaleza.PRINCIPAL,
        )
        self.assertEqual(salida_polvo.cantidad, Decimal("115"))
        self.assertEqual(salida_polvo.destino, SalidaProceso.Destino.ENVASADO)
        decision = LiberacionProceso.objects.get(salida=salida_polvo)
        self.assertEqual(decision.estado, LiberacionProceso.Estado.PENDIENTE)
        self.assertIsNone(decision.firma_id)
        self.assertTrue(EventoProceso.objects.filter(
            ejecucion=continuacion, tipo="continuidad_calidad_pendiente",
            motivo="cerrar_secado",
        ).exists())
