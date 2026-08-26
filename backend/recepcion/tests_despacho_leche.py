import uuid
from datetime import timedelta

from django.contrib.auth.models import User
from django.utils import timezone

from .models import AnalisisSilo, DespachoLeche, MovimientoSilo
from .servicios import saldo_silo
from .tests import BaseAPIRecepcion


class DespachoLecheAPITests(BaseAPIRecepcion):
    def test_despacha_con_liberacion_y_descuenta_el_silo(self):
        ahora = timezone.now()
        MovimientoSilo.objects.create(
            silo=self.silo, tipo=MovimientoSilo.Tipo.INGRESO,
            litros="1000", fecha_hora=ahora - timedelta(hours=2),
        )
        firma = User.objects.create_user(username="firma-despacho", password="x")
        analisis = AnalisisSilo.objects.create(
            silo=self.silo, tomado_en=ahora - timedelta(hours=1),
            grasa="4.20", sng="8.80", inhibidores_resultado="negativo",
            metodo="delvo_sp", hora_lectura=timezone.localtime().time(),
            analista=User.objects.get(username="op"), visualizado_por=firma,
            visualizado_en=ahora, estado=AnalisisSilo.Estado.CONFIRMADO,
        )

        respuesta = self.cliente.post(
            "/api/recepcion/despachos-leche/",
            {
                "silo": self.silo.id, "litros": "400.00",
                "destino": "Cliente Sur", "guia_despacho": "GD-100",
                "patente": "ABCD-12", "fecha_hora": ahora.isoformat(),
                "operacion_id": str(uuid.uuid4()),
            },
            format="json",
        )

        self.assertEqual(respuesta.status_code, 201, respuesta.data)
        despacho = DespachoLeche.objects.get()
        self.assertEqual(despacho.liberacion_analisis, analisis)
        self.assertEqual(despacho.movimiento.origen_tipo, "despacho")
        self.assertEqual(saldo_silo(self.silo), 600)

        reversa = self.cliente.post(
            f"/api/recepcion/despachos-leche/{despacho.id}/reversar/",
            {"motivo": "Guía digitada por error"}, format="json",
        )

        self.assertEqual(reversa.status_code, 200, reversa.data)
        despacho.refresh_from_db()
        self.assertIsNotNone(despacho.reversa_id)
        self.assertEqual(despacho.reversa.origen_tipo, "devolucion")
        self.assertEqual(saldo_silo(self.silo), 1000)
