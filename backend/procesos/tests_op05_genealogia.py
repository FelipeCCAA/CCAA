"""La genealogía conserva el lote identificado por una salida física."""

from decimal import Decimal

from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from calidad.models import LiberacionProceso
from calidad.vigencia import registrar_firma_salida
from maestros.models import Silo
from recepcion.models import AnalisisSilo, MovimientoSilo
from usuarios.models import PerfilUsuario

from .models import EntradaProceso, EjecucionProceso, SalidaProceso
from .servicios import genealogia_lote
from . import tests_mantequilla as fixtures


class GenealogiaOrigenFisicoOP05Tests(TestCase):
    def setUp(self):
        fixtures.MantequillaTests.setUp(self)
        tk = Silo.objects.create(
            sucursal=self.planta, codigo="TK-GENEALOGIA-OP05",
            tipo=Silo.Tipo.TK_CREMA, capacidad_l=Decimal("2000"),
        )
        anterior = EjecucionProceso.objects.create(
            codigo="ORIGEN-GENEALOGIA-OP05", etapa=self.corrida.ejecucion.etapa,
            sucursal=self.planta, estado=EjecucionProceso.Estado.CERRADA,
        )
        fuente = SalidaProceso.objects.create(
            ejecucion=anterior, lote=self.lote_crema, silo=tk,
            cantidad=Decimal("1000"), unidad="L",
        )
        self.entrada = EntradaProceso.objects.create(
            ejecucion=self.corrida.ejecucion, silo=tk, salida_origen=fuente,
            cantidad=Decimal("200"), unidad="L",
        )
        SalidaProceso.objects.create(
            ejecucion=self.corrida.ejecucion,
            lote=self.corrida.lote_mantequilla,
            cantidad=Decimal("80"), unidad="kg",
        )

    def test_rastreo_atras_conserva_lote_crema_y_litros_retirados(self):
        resultado = genealogia_lote(self.corrida.lote_mantequilla_id, "atras")
        self.assertIn(self.lote_crema.pk, {n["id"] for n in resultado["nodos"]})
        enlace = next(e for e in resultado["enlaces"] if e["origen"] == self.lote_crema.pk)
        self.assertEqual(enlace["entrada"]["cantidad"], Decimal("200"))
        self.assertEqual(enlace["entrada"]["unidad"], "L")

    def test_rastreo_adelante_identifica_mantequilla_desde_crema(self):
        resultado = genealogia_lote(self.lote_crema.pk, "adelante")
        self.assertIn(self.corrida.lote_mantequilla_id, {n["id"] for n in resultado["nodos"]})
        self.assertEqual(len(resultado["enlaces"]), 1)

    def test_disponible_no_suma_dos_veces_entrada_y_retiro_fisico(self):
        fuente = self.entrada.salida_origen
        ahora = timezone.now()
        analisis = AnalisisSilo.objects.create(
            silo=fuente.silo, tomado_en=ahora, grasa=Decimal("40"),
            sng=Decimal("5"), densidad=Decimal("1000"),
            inhibidores_resultado="negativo", metodo="snap",
            hora_lectura=timezone.localtime().time(),
            estado=AnalisisSilo.Estado.CONFIRMADO,
            analista=self.usuario, visualizado_por=self.usuario,
        )
        decision = LiberacionProceso.objects.create(
            salida=fuente, estado=LiberacionProceso.Estado.LIBERADO,
            analisis_silo=analisis, decidida_por=self.usuario, decidida_en=ahora,
        )
        registrar_firma_salida(decision)
        self.corrida.salida_crema = fuente
        self.corrida.kg_crema = Decimal("200")
        self.corrida.iniciada_en = ahora
        self.corrida.save(update_fields=["salida_crema", "kg_crema", "iniciada_en"])
        MovimientoSilo.objects.create(
            silo=fuente.silo, tipo=MovimientoSilo.Tipo.SALIDA,
            litros=Decimal("200"), fecha_hora=ahora,
            origen_tipo=MovimientoSilo.OrigenTipo.PRODUCCION,
            origen_id=self.corrida.pk, lote=self.lote_crema,
            operacion_id=self.corrida.operacion_id,
        )
        self.usuario.perfil.area = PerfilUsuario.Area.CONDENSACION
        self.usuario.perfil.save(update_fields=["area"])
        cliente = APIClient()
        cliente.force_authenticate(self.usuario)
        respuesta = cliente.get("/api/procesos/salidas/disponibles/")
        self.assertEqual(respuesta.status_code, 200, respuesta.data)
        item = next(s for s in respuesta.data if s["id"] == fuente.pk)
        self.assertEqual(item["cantidad_consumida"], Decimal("200"))
        self.assertEqual(item["cantidad_disponible"], Decimal("800"))
        self.assertEqual(item["cantidad_consumida_kg"], Decimal("200"))
        self.assertEqual(item["cantidad_disponible_kg"], Decimal("800"))
