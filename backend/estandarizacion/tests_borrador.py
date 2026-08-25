from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient

from recepcion.models import MovimientoSilo
from usuarios.models import PerfilUsuario, Rol

from .models import ValeEstandarizacion
from .tests_vale import BaseVale


class BorradorValeTests(BaseVale):
    def setUp(self):
        PerfilUsuario.objects.create(usuario=self.usuario, rol=Rol.RECEPCION)
        self.cliente = APIClient()
        self.cliente.credentials(
            HTTP_AUTHORIZATION=f"Token {Token.objects.create(user=self.usuario).key}"
        )

    def crear_borrador(self, **datos):
        respuesta = self.cliente.post(
            "/api/estandarizacion/vales/crear-borrador/",
            datos,
            format="json",
        )
        self.assertEqual(respuesta.status_code, 201, respuesta.json())
        return respuesta

    def datos_completos(self):
        return {
            "codigo_propuesto": "VE-BORRADOR-1",
            "producto": self.producto.id,
            "rc_objetivo": "0.2010",
            "volumen": "10000.00",
            "silo_entera": self.silo_entera.id,
            "silo_descremada": self.silo_descremada.id,
            "silo_destino": self.silo_destino.id,
            "entera_grasa": "3.90",
            "entera_sng": "8.60",
            "descremada_grasa": "0.05",
            "descremada_sng": "8.90",
            "litros_entera": "4000.00",
            "litros_descremada": "6000.00",
        }

    def test_borrador_parcial_es_recuperable_y_no_aparece_en_operacion(self):
        cuerpo = self.crear_borrador(
            codigo_propuesto="VE-PENDIENTE", observaciones="A medio completar"
        ).json()

        self.assertEqual(cuerpo["estado"], ValeEstandarizacion.Estado.BORRADOR)
        self.assertTrue(cuerpo["codigo"].startswith("BORRADOR-"))
        self.assertEqual(
            self.cliente.get("/api/estandarizacion/vales/mi-borrador/").json()["id"],
            cuerpo["id"],
        )
        ids_operativos = {
            item["id"]
            for item in self.cliente.get("/api/estandarizacion/vales/").json()["results"]
        }
        self.assertNotIn(cuerpo["id"], ids_operativos)
        self.assertEqual(MovimientoSilo.objects.count(), 0)

    def test_no_confirma_un_borrador_incompleto(self):
        borrador = self.crear_borrador(codigo_propuesto="VE-INCOMPLETO").json()

        respuesta = self.cliente.post(
            f"/api/estandarizacion/vales/{borrador['id']}/confirmar-borrador/"
        )

        self.assertEqual(respuesta.status_code, 400)
        self.assertGreater(len(respuesta.json()["motivos"]), 1)
        self.assertEqual(
            ValeEstandarizacion.objects.get(pk=borrador["id"]).estado,
            ValeEstandarizacion.Estado.BORRADOR,
        )

    def test_confirmar_reserva_el_codigo_sin_mover_leche(self):
        borrador = self.crear_borrador(observaciones="Inicio").json()
        respuesta_guardado = self.cliente.patch(
            f"/api/estandarizacion/vales/{borrador['id']}/guardar-borrador/",
            self.datos_completos(),
            format="json",
        )
        self.assertEqual(respuesta_guardado.status_code, 200, respuesta_guardado.json())

        respuesta = self.cliente.post(
            f"/api/estandarizacion/vales/{borrador['id']}/confirmar-borrador/"
        )

        self.assertEqual(respuesta.status_code, 200, respuesta.json())
        self.assertEqual(respuesta.json()["codigo"], "VE-BORRADOR-1")
        self.assertEqual(respuesta.json()["estado"], ValeEstandarizacion.Estado.CALCULADO)
        self.assertEqual(MovimientoSilo.objects.count(), 0)

