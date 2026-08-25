from datetime import date
from decimal import Decimal

from django.utils import timezone

from recepcion.models import MovimientoSilo

from .models import CorreccionLote, Lote
from .tests_apertura import BaseApertura


class CorreccionLoteTests(BaseApertura):
    def lote(self, **extra):
        datos = {
            "sucursal": self.sucursal,
            "codigo_lote": "LOTE-CORR-1",
            "codigo_lote_propuesto": "LOTE-CORR-1",
            "producto": self.polvo,
            "equipo": self.equipo,
            "fecha": date(2026, 7, 16),
            "linea": "E1",
            "estado": Lote.Estado.EN_PROCESO,
        }
        datos.update(extra)
        return Lote.objects.create(**datos)

    def editar(self, lote, **datos):
        return self.cliente.patch(
            f"/api/produccion/lotes/{lote.id}/", datos, format="json"
        )

    def test_corregir_un_paso_anterior_exige_motivo_y_lo_audita(self):
        lote = self.lote()

        sin_motivo = self.editar(lote, turno="B")
        con_motivo = self.editar(
            lote,
            turno="B",
            motivo_correccion="Turno digitado incorrectamente",
        )

        self.assertEqual(sin_motivo.status_code, 400)
        self.assertEqual(con_motivo.status_code, 200, con_motivo.data)
        correccion = CorreccionLote.objects.get(lote=lote)
        self.assertIn("incorrectamente", correccion.motivo)
        self.assertEqual(correccion.cambios["turno"], ["", "B"])

    def test_no_cambia_equipo_si_ya_existe_movimiento_de_leche(self):
        lote = self.lote()
        MovimientoSilo.objects.create(
            silo=self.silo_b,
            tipo=MovimientoSilo.Tipo.SALIDA,
            litros=Decimal("1000.00"),
            fecha_hora=timezone.now(),
            origen_tipo=MovimientoSilo.OrigenTipo.LOTE,
            origen_id=lote.id,
            lote=lote,
            producto=lote.producto,
            equipo=lote.equipo,
        )

        respuesta = self.editar(
            lote,
            equipo=self.otro_equipo.id,
            motivo_correccion="Equipo informado incorrectamente",
        )

        self.assertEqual(respuesta.status_code, 400)
        self.assertIn("movimiento", str(respuesta.data).lower())
        lote.refresh_from_db()
        self.assertEqual(lote.equipo, self.equipo)

    def test_kilos_producidos_no_se_reescriben_despues_del_cierre(self):
        lote = self.lote(
            estado=Lote.Estado.PRODUCIDO,
            kg_producidos=Decimal("1000.00"),
        )

        respuesta = self.editar(
            lote,
            kg_producidos="1200.00",
            motivo_correccion="Rectificación posterior",
        )

        self.assertEqual(respuesta.status_code, 400)
        self.assertIn("ajuste", str(respuesta.data).lower())
        lote.refresh_from_db()
        self.assertEqual(lote.kg_producidos, Decimal("1000.00"))

    def test_el_cierre_normal_con_kilos_no_pide_motivo_de_correccion(self):
        lote = self.lote()

        respuesta = self.editar(
            lote, estado=Lote.Estado.PRODUCIDO, kg_producidos="1000.00"
        )

        self.assertEqual(respuesta.status_code, 200, respuesta.data)
        lote.refresh_from_db()
        self.assertEqual(lote.estado, Lote.Estado.PRODUCIDO)

