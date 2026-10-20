"""Una rectificación de transcripción no sustituye al nuevo ciclo físico."""

from .tests_op02_actos import EscenarioActosOP02
from .tests_vale import BaseVale


class NuevoMuestreoOP02Tests(EscenarioActosOP02, BaseVale):
    def setUp(self):
        self._clientes()

    def test_no_se_fabrica_muestra_corrigiendo_una_eliminada_por_movimiento(self):
        vale = self._transferido()
        self.assertEqual(self._accion(vale, "actos", self._datos_acto()).status_code, 200)
        antes = self._foto(vale)
        url = f"/api/estandarizacion/vales/{vale.pk}/corregir-muestra/"
        datos = {"grasa": "1.79", "sng": "8.90", "motivo": "Rectificación de captura"}
        respuesta = self.cliente.patch(url, datos, format="json")
        self.assertEqual(respuesta.status_code, 409, respuesta.data)
        self.assertEqual(self._foto(vale), antes)
        self.assertEqual(self._accion(vale, "decidir", cliente=self.cliente_calidad).status_code, 409)

        self.assertEqual(self._accion(vale, "reagitar").status_code, 200)
        self.assertEqual(self._accion(vale, "muestrear", {"grasa": "1.78", "sng": "8.90"}).status_code, 200)
        # Sí se puede rectificar una muestra real recién registrada.
        respuesta = self.cliente.patch(url, datos, format="json")
        self.assertEqual(respuesta.status_code, 200, respuesta.data)
        self.assertEqual(self._accion(vale, "decidir", cliente=self.cliente_calidad).status_code, 200)
