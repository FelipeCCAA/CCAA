"""Contrato de la política explícita; no representa una firma de Calidad."""
from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from rest_framework.test import APIClient
from calidad import tests_continuidad_produccion as escenarios
from estandarizacion.tests_vale import BaseVale


class PoliticaContinuidadAPITests(TestCase):
    def setUp(self):
        self.cliente = APIClient()
        self.cliente.force_authenticate(get_user_model().objects.create_user(username="operador-aviso"))

    @override_settings(CCAA_CALIDAD_INTERMEDIA_AVISO=True)
    def test_politica_habilitada_se_informa_sin_liberar_material(self):
        respuesta = self.cliente.get("/api/calidad/politica-continuidad/")
        self.assertEqual(respuesta.status_code, 200)
        self.assertTrue(respuesta.data["avisos_intermedios"])

    @override_settings(CCAA_CALIDAD_INTERMEDIA_AVISO=False)
    def test_modo_estricto_sigue_siendo_explicito(self):
        respuesta = self.cliente.get("/api/calidad/politica-continuidad/?avisos_intermedios=true")
        self.assertEqual(respuesta.status_code, 200)
        self.assertFalse(respuesta.data["avisos_intermedios"])

    def test_cliente_no_puede_activar_la_politica(self):
        respuesta = self.cliente.post("/api/calidad/politica-continuidad/", {"avisos_intermedios": True}, format="json")
        self.assertEqual(respuesta.status_code, 405)

    def test_politica_requiere_identidad(self):
        self.cliente.force_authenticate(None)
        self.assertEqual(self.cliente.get("/api/calidad/politica-continuidad/").status_code, 401)


@override_settings(CCAA_CALIDAD_INTERMEDIA_AVISO=True)
class ContinuidadAccionAPITests(BaseVale):
    _fuente = escenarios.ContinuidadProduccionTests._fuente
    _transferir = escenarios.ContinuidadProduccionTests._transferir
    _muestrear_conforme = escenarios.ContinuidadProduccionTests._muestrear_conforme

    def setUp(self):
        escenarios.ContinuidadProduccionTests.setUp(self)
        self._muestrear_conforme()

    def test_accion_http_conserva_pendiente_sin_firmar(self):
        respuesta = self.cliente.post(
            f"/api/estandarizacion/vales/{self.vale.pk}/continuar-pendiente/",
            {"motivo": "Esperando revisión de Calidad"}, format="json",
        )
        self.assertEqual(respuesta.status_code, 200, respuesta.data)
        self.assertEqual(respuesta.data["estado"], "muestreado")
        self.assertFalse(respuesta.data["continuidad_pendiente_disponible"])

    def test_sin_permiso_operacional_no_puede_continuar(self):
        self.cliente.force_authenticate(self.visualizador)
        respuesta = self.cliente.post(
            f"/api/estandarizacion/vales/{self.vale.pk}/continuar-pendiente/",
            {"motivo": "Intento sin permiso"}, format="json",
        )
        self.assertEqual(respuesta.status_code, 403)
        self.assertEqual(self.vale.ejecucion.estado, "ejecucion")

    def test_payload_no_anula_configuracion_estricta(self):
        with override_settings(CCAA_CALIDAD_INTERMEDIA_AVISO=False):
            respuesta = self.cliente.post(
                f"/api/estandarizacion/vales/{self.vale.pk}/continuar-pendiente/",
                {"motivo": "No debe activar la política", "avisos_intermedios": True}, format="json",
            )
        self.assertEqual(respuesta.status_code, 409)
