from decimal import Decimal

from django.contrib.auth import get_user_model
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient

from recepcion.models import MovimientoSilo
from usuarios.models import PerfilUsuario, Rol

from .models import CorreccionValeEstandarizacion, ValeEstandarizacion
from .tests_vale import BaseVale


class CorreccionMuestraValeTests(BaseVale):
    def setUp(self):
        operador = get_user_model().objects.create_user(
            username="corrige-vale", password="x"
        )
        PerfilUsuario.objects.create(usuario=operador, rol=Rol.RECEPCION)
        self.cliente = APIClient()
        self.cliente.credentials(
            HTTP_AUTHORIZATION=f"Token {Token.objects.create(user=operador).key}"
        )

    def corregir(self, vale, grasa="1.79", sng="8.90"):
        return self.cliente.patch(
            f"/api/estandarizacion/vales/{vale.id}/corregir-muestra/",
            {
                "grasa": grasa,
                "sng": sng,
                "motivo": "Corrección del resultado transcrito",
            },
            format="json",
        )

    def test_corrige_la_muestra_y_recalcula_la_evaluacion(self):
        vale = self.crear_vale(
            estado=ValeEstandarizacion.Estado.MUESTREADO,
            grasa_real="2.50",
            sng_real="8.90",
        )

        respuesta = self.corregir(vale)

        self.assertEqual(respuesta.status_code, 200, respuesta.data)
        self.assertEqual(respuesta.data["estado"], ValeEstandarizacion.Estado.MUESTREADO)
        self.assertTrue(respuesta.data["evaluacion"]["cumple"])
        correccion = CorreccionValeEstandarizacion.objects.get(vale=vale)
        self.assertIn("transcrito", correccion.motivo)
        self.assertIn("grasa_real", correccion.cambios)

    def test_desde_corrigiendo_vuelve_a_decision_sin_mover_leche(self):
        vale = self.crear_vale(
            estado=ValeEstandarizacion.Estado.CORRIGIENDO,
            grasa_real="2.50",
            sng_real="8.90",
        )
        movimientos_antes = MovimientoSilo.objects.count()

        respuesta = self.corregir(vale)

        self.assertEqual(respuesta.status_code, 200, respuesta.data)
        self.assertEqual(respuesta.data["estado"], ValeEstandarizacion.Estado.MUESTREADO)
        self.assertEqual(MovimientoSilo.objects.count(), movimientos_antes)

    def test_un_vale_liberado_no_admite_corregir_la_muestra(self):
        vale = self.crear_vale(
            estado=ValeEstandarizacion.Estado.LIBERADO,
            grasa_real="1.79",
            sng_real="8.90",
        )

        respuesta = self.corregir(vale, grasa="1.80")

        self.assertEqual(respuesta.status_code, 409)
        vale.refresh_from_db()
        self.assertEqual(vale.grasa_real, Decimal("1.79"))
        self.assertFalse(CorreccionValeEstandarizacion.objects.exists())
