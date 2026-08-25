from recepcion.models import AnalisisSilo, MovimientoSilo
from recepcion.tests import BaseAPIRecepcion


class BorradorAnalisisSiloTests(BaseAPIRecepcion):
    url = "/api/recepcion/analisis-silo/"

    def test_guardar_a_medias_no_aparece_como_analisis_operativo(self):
        borrador = self.cliente.post(
            f"{self.url}crear-borrador/",
            {"silo": self.silo.id, "grasa": "4.35"},
            format="json",
        )

        self.assertEqual(borrador.status_code, 201, borrador.data)
        self.assertEqual(borrador.data["estado"], AnalisisSilo.Estado.BORRADOR)
        self.assertFalse(MovimientoSilo.objects.exists())
        listado = self.cliente.get(f"{self.url}?silo={self.silo.id}")
        self.assertEqual(listado.data["count"], 0)

    def test_reanuda_actualiza_y_confirma_el_mismo_analisis(self):
        creado = self.cliente.post(
            f"{self.url}crear-borrador/",
            {"silo": self.silo.id, "grasa": "4.35"},
            format="json",
        ).data

        reanudado = self.cliente.get(
            f"{self.url}mi-borrador/?silo={self.silo.id}"
        )
        guardado = self.cliente.patch(
            f"{self.url}{creado['id']}/guardar-borrador/",
            {"sng": "8.90"},
            format="json",
        )
        confirmado = self.cliente.post(
            f"{self.url}{creado['id']}/confirmar-borrador/", {}, format="json"
        )

        self.assertEqual(reanudado.data["id"], creado["id"])
        self.assertEqual(guardado.data["sng"], "8.90")
        self.assertEqual(confirmado.status_code, 200, confirmado.data)
        self.assertEqual(confirmado.data["estado"], AnalisisSilo.Estado.CONFIRMADO)
        self.assertEqual(confirmado.data["id"], creado["id"])

    def test_descartar_anula_sin_borrar(self):
        creado = self.cliente.post(
            f"{self.url}crear-borrador/", {"silo": self.silo.id}, format="json"
        ).data

        respuesta = self.cliente.post(
            f"{self.url}{creado['id']}/descartar-borrador/", {}, format="json"
        )

        self.assertEqual(respuesta.status_code, 204)
        self.assertEqual(
            AnalisisSilo.objects.get(pk=creado["id"]).estado,
            AnalisisSilo.Estado.ANULADO,
        )
