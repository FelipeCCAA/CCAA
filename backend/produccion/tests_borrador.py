from decimal import Decimal

from estandarizacion.models import ValeEstandarizacion
from recepcion.models import MovimientoSilo

from .models import Lote
from .tests_apertura import BaseApertura


class BorradorLoteTests(BaseApertura):
    def setUp(self):
        super().setUp()
        self.vale = ValeEstandarizacion.objects.create(
            codigo="VE-BOR-LOTE",
            codigo_propuesto="VE-BOR-LOTE",
            fecha="2026-07-16",
            producto=self.polvo,
            rc_objetivo=Decimal("0.4000"),
            volumen=Decimal("20000.00"),
            silo_entera=self.silo_a,
            silo_destino=self.silo_b,
            entera_grasa=Decimal("3.60"),
            entera_sng=Decimal("8.60"),
            descremada_grasa=Decimal("0.05"),
            descremada_sng=Decimal("8.90"),
            litros_entera=Decimal("19000.00"),
            litros_descremada=Decimal("1000.00"),
            estado=ValeEstandarizacion.Estado.LIBERADO,
        )

    def crear_borrador(self, **datos):
        respuesta = self.cliente.post(
            "/api/produccion/lotes/crear-borrador/", datos, format="json"
        )
        self.assertEqual(respuesta.status_code, 201, respuesta.json())
        return respuesta.json()

    def datos_completos(self):
        return {
            "codigo_lote_propuesto": "CCAA6197E1-01",
            "producto": self.polvo.id,
            "vale": self.vale.id,
            "litros_estandarizados_borrador": "12000.00",
            "equipo": self.equipo.id,
            "fecha": "2026-07-16",
            "linea": "E1",
            "turno": "A",
            "op": "OP-101",
            "observacion": "Corrida de prueba",
        }

    def test_el_borrador_parcial_se_recupera_y_no_aparece_como_lote(self):
        borrador = self.crear_borrador(observacion="A medio completar")

        self.assertEqual(borrador["estado"], Lote.Estado.BORRADOR)
        self.assertTrue(borrador["codigo_lote"].startswith("BORRADOR-"))
        recuperado = self.cliente.get(
            "/api/produccion/lotes/mi-borrador/"
        ).json()
        self.assertEqual(recuperado["id"], borrador["id"])
        ids = {
            item["id"]
            for item in self.cliente.get("/api/produccion/lotes/").json()["results"]
        }
        self.assertNotIn(borrador["id"], ids)
        self.assertEqual(MovimientoSilo.objects.count(), 0)

    def test_un_borrador_incompleto_no_abre_la_produccion(self):
        borrador = self.crear_borrador(codigo_lote_propuesto="LOTE-INCOMPLETO")

        respuesta = self.cliente.post(
            f"/api/produccion/lotes/{borrador['id']}/confirmar-borrador/"
        )

        self.assertEqual(respuesta.status_code, 400)
        self.assertTrue(respuesta.json()["motivos"])
        self.assertEqual(MovimientoSilo.objects.count(), 0)

    def test_confirmar_convierte_el_mismo_registro_y_descuenta_una_vez(self):
        borrador = self.crear_borrador(observacion="Inicio")
        guardado = self.cliente.patch(
            f"/api/produccion/lotes/{borrador['id']}/guardar-borrador/",
            self.datos_completos(),
            format="json",
        )
        self.assertEqual(guardado.status_code, 200, guardado.json())

        respuesta = self.cliente.post(
            f"/api/produccion/lotes/{borrador['id']}/confirmar-borrador/"
        )

        self.assertEqual(respuesta.status_code, 200, respuesta.json())
        self.assertEqual(respuesta.json()["id"], borrador["id"])
        self.assertEqual(respuesta.json()["codigo_lote"], "CCAA6197E1-01")
        self.assertEqual(respuesta.json()["estado"], Lote.Estado.EN_PROCESO)
        movimiento = MovimientoSilo.objects.get(origen_id=borrador["id"])
        self.assertEqual(movimiento.litros, Decimal("12000.00"))

    def test_autoguardado_de_borrador_no_exige_motivo_de_correccion(self):
        borrador = self.crear_borrador()
        respuesta = self.cliente.patch(
            f"/api/produccion/lotes/{borrador['id']}/guardar-borrador/",
            {"producto": self.polvo.id, "observacion": "Avance"},
            format="json",
        )
        self.assertEqual(respuesta.status_code, 200, respuesta.json())
        self.assertEqual(respuesta.json()["producto"], self.polvo.id)

