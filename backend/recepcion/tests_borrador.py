from decimal import Decimal

from inventario.models import Notificacion
from recepcion.models import MovimientoSilo, Recepcion
from recepcion.tests import BaseAPIRecepcion


class BorradorRecepcionTests(BaseAPIRecepcion):
    url = "/api/recepcion/recepciones/"

    def test_guardar_a_medias_no_mueve_saldo_ni_notifica(self):
        respuesta = self.cliente.post(
            f"{self.url}crear-borrador/", {"guia": "BORR-1"}, format="json"
        )

        self.assertEqual(respuesta.status_code, 201, respuesta.data)
        recepcion = Recepcion.objects.get(pk=respuesta.data["id"])
        self.assertEqual(recepcion.estado, Recepcion.Estado.BORRADOR)
        self.assertEqual(recepcion.guia, "BORR-1")
        self.assertFalse(MovimientoSilo.objects.exists())
        self.assertFalse(Notificacion.objects.exists())

    def test_confirmar_incompleto_devuelve_motivos_y_no_avanza(self):
        borrador = self.cliente.post(
            f"{self.url}crear-borrador/", {"guia": "BORR-2"}, format="json"
        ).data

        respuesta = self.cliente.post(
            f"{self.url}{borrador['id']}/confirmar-borrador/", {}, format="json"
        )

        self.assertEqual(respuesta.status_code, 400)
        self.assertGreaterEqual(len(respuesta.data["motivos"]), 3)
        self.assertEqual(
            Recepcion.objects.get(pk=borrador["id"]).estado,
            Recepcion.Estado.BORRADOR,
        )

    def test_reanuda_guarda_y_confirma_el_mismo_documento(self):
        creado = self.cliente.post(
            f"{self.url}crear-borrador/", {"guia": "BORR-3"}, format="json"
        ).data
        guardado = self.cliente.patch(
            f"{self.url}{creado['id']}/guardar-borrador/",
            {
                "fecha": "2026-08-25",
                "vehiculo": self.camion.id,
                "tipo_leche": "Entera",
                "litros": "12500",
                "modulos": [{"numero": 1, "crioscopia": "-0.521"}],
            },
            format="json",
        )

        self.assertEqual(guardado.status_code, 200, guardado.data)
        reanudado = self.cliente.get(f"{self.url}mi-borrador/")
        self.assertEqual(reanudado.data["id"], creado["id"])
        respuesta = self.cliente.post(
            f"{self.url}{creado['id']}/confirmar-borrador/", {}, format="json"
        )

        self.assertEqual(respuesta.status_code, 200, respuesta.data)
        self.assertEqual(respuesta.data["estado"], Recepcion.Estado.REGISTRADA)
        self.assertEqual(Decimal(respuesta.data["litros"]), Decimal("12500"))
        self.assertFalse(MovimientoSilo.objects.exists())

    def test_un_borrador_no_aparece_en_el_listado_operativo(self):
        self.cliente.post(
            f"{self.url}crear-borrador/", {"guia": "OCULTO"}, format="json"
        )

        respuesta = self.cliente.get(self.url)

        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta.data["count"], 0)

    def test_descartar_anula_sin_borrar(self):
        creado = self.cliente.post(
            f"{self.url}crear-borrador/", {"guia": "DESCARTAR"}, format="json"
        ).data

        respuesta = self.cliente.post(
            f"{self.url}{creado['id']}/descartar-borrador/", {}, format="json"
        )

        self.assertEqual(respuesta.status_code, 204)
        self.assertEqual(
            Recepcion.objects.get(pk=creado["id"]).estado,
            Recepcion.Estado.ANULADA,
        )
