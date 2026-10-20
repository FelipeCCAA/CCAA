"""Una aprobación declarada protege edición sin habilitar despacho histórico."""

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from calidad.evidencia import bloquear_catalogo
from calidad.models import Liberacion
from calidad.vigencia import exigir_liberacion_lote_vigente, registrar_firma_lote
from maestros.models import Silo
from recepcion.models import MovimientoSilo

from .models import Lote
from .tests_api import BaseAPI


class GuardasAprobacionDeclaradaOP01Tests(BaseAPI):
    def setUp(self):
        super().setUp()
        self.lote = self._lote(estado=Lote.Estado.PRODUCIDO)
        self.aprobacion = Liberacion.objects.create(
            lote=self.lote, estado=Liberacion.Estado.LIBERADO,
            autorizada_por=self.usuario, autorizada_en=timezone.now(),
        )
        self.silo = Silo.objects.create(
            sucursal=self.sucursal, codigo="OP01-GUARDAS", tipo=Silo.Tipo.SILO,
            capacidad_l=1000,
        )

    def _edicion_rechazada(self):
        anterior = self.lote.bultos
        respuesta = self.cliente.patch(
            f"/api/produccion/lotes/{self.lote.pk}/",
            {"bultos": 7, "motivo_correccion": "Corrección sintética OP01"},
            format="json",
        )
        self.assertEqual(respuesta.status_code, 400, respuesta.data)
        self.assertIn("revisar/", str(respuesta.data))
        self.lote.refresh_from_db()
        self.assertEqual(self.lote.bultos, anterior)

    def _asignacion_rechazada(self):
        respuesta = self.cliente.post(
            f"/api/produccion/lotes/{self.lote.pk}/asignacion/",
            {"asignaciones": [{"silo": self.silo.pk, "litros": 100}]},
            format="json",
        )
        self.assertEqual(respuesta.status_code, 409, respuesta.data)
        self.assertIn("revisar/", str(respuesta.data))
        self.assertFalse(MovimientoSilo.objects.filter(
            tipo=MovimientoSilo.Tipo.SALIDA,
            origen_tipo=MovimientoSilo.OrigenTipo.LOTE, origen_id=self.lote.pk,
        ).exists())

    def test_el_historico_sin_metadata_impide_editar_y_la_ficha_lo_advierte(self):
        self.assertFalse(self.aprobacion.liberado)
        with self.assertRaises(ValidationError):
            exigir_liberacion_lote_vigente(self.lote.pk)

        respuesta = self.cliente.get(f"/api/produccion/lotes/{self.lote.pk}/")

        self.assertEqual(respuesta.status_code, 200, respuesta.data)
        self.assertTrue(respuesta.data["liberacion"]["liberado"])
        self._edicion_rechazada()

    def test_el_historico_sin_metadata_impide_cambiar_origen_de_leche(self):
        self.assertFalse(self.aprobacion.firma_vigente)
        self._asignacion_rechazada()

    def test_el_respaldo_de_firma_vigente_conserva_las_dos_guardas(self):
        # Acto de aprobación ya validado aguas arriba; aquí se prueban las
        # guardas de Producción, no la decisión de Calidad del fixture.
        with transaction.atomic():
            bloquear_catalogo()
            registrar_firma_lote(self.aprobacion)
        self.assertTrue(self.aprobacion.firma_vigente)
        self.assertEqual(
            exigir_liberacion_lote_vigente(self.lote.pk), str(self.aprobacion.firma_id),
        )

        self._edicion_rechazada()
        self._asignacion_rechazada()
        self.aprobacion.refresh_from_db()
        self.assertTrue(self.aprobacion.firma_vigente)
