"""
El positivo ya no termina en 'retenida y nada más'.
"""

from datetime import date, time
from decimal import Decimal

from recepcion.models import BusquedaProveedor, ControlInhibidores, Recepcion
from recepcion.tests import BaseAPIRecepcion


class CierreConInhibidoresTests(BaseAPIRecepcion):
    def _recepcion_positiva(self):
        return Recepcion.objects.create(
            fecha=date(2026, 7, 31),
            tipo_leche=Recepcion.TipoLeche.ENTERA,
            litros=Decimal("5000"),
            controles={"delvo": "Positivo"},
            estado=Recepcion.Estado.RETENIDA,
            motivo="Delvo positivo",
        )

    def test_no_se_cierra_sin_buscar_al_proveedor(self):
        recepcion = self._recepcion_positiva()

        respuesta = self.cliente.post(
            f"/api/recepcion/recepciones/{recepcion.id}/cerrar/", {}, format="json"
        )

        self.assertEqual(respuesta.status_code, 400)
        recepcion.refresh_from_db()
        self.assertEqual(recepcion.estado, Recepcion.Estado.RETENIDA)

    def test_con_la_busqueda_registrada_cierra(self):
        recepcion = self._recepcion_positiva()
        control = ControlInhibidores.objects.create(
            recepcion=recepcion,
            resultado=ControlInhibidores.Resultado.POSITIVO,
            tiras_usadas=2,
            hora_lectura=time(9, 0),
        )
        BusquedaProveedor.objects.create(
            control=control,
            proveedor="Predio Los Álamos",
            resultado=ControlInhibidores.Resultado.POSITIVO,
        )

        respuesta = self.cliente.post(
            f"/api/recepcion/recepciones/{recepcion.id}/cerrar/", {}, format="json"
        )

        self.assertEqual(respuesta.status_code, 200)
        recepcion.refresh_from_db()
        self.assertEqual(recepcion.estado, Recepcion.Estado.CERRADA)

    def test_una_recepcion_limpia_cierra_sin_tramite(self):
        recepcion = Recepcion.objects.create(
            fecha=date(2026, 7, 31),
            tipo_leche=Recepcion.TipoLeche.ENTERA,
            litros=Decimal("5000"),
            controles={"delvo": "Negativo"},
            estado=Recepcion.Estado.DESCARGADA,
        )

        respuesta = self.cliente.post(
            f"/api/recepcion/recepciones/{recepcion.id}/cerrar/", {}, format="json"
        )

        self.assertEqual(respuesta.status_code, 200)
