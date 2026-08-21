"""
De dónde salen la grasa y el SNG del vale.

Hasta ahora el operador los tecleaba y no quedaba de dónde. El vale sigue
**congelando** la composición en sus columnas —esa decisión no cambia—, pero
ahora además dice contra qué análisis se compuso.
"""

from datetime import datetime, timezone as tz
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient

from maestros.models import Silo
from recepcion.models import AnalisisSilo, MovimientoSilo
from usuarios.models import PerfilUsuario, Rol


class ComposicionDeSilosTests(TestCase):
    def setUp(self):
        usuario = User.objects.create_user(username="est", password="x")
        PerfilUsuario.objects.create(usuario=usuario, rol=Rol.RECEPCION)
        self.cliente = APIClient()
        self.cliente.credentials(
            HTTP_AUTHORIZATION=f"Token {Token.objects.create(user=usuario).key}"
        )

        self.entera = Silo.objects.create(
            codigo="SILO 6", tipo=Silo.Tipo.SILO, capacidad_l=Decimal("100000")
        )
        self.descremada = Silo.objects.create(
            codigo="TK LD 1", tipo=Silo.Tipo.TK_LD, capacidad_l=Decimal("50000")
        )

    def test_devuelve_el_ultimo_analisis_de_cada_silo(self):
        AnalisisSilo.objects.create(
            silo=self.entera,
            tomado_en=datetime(2026, 7, 15, 6, 0, tzinfo=tz.utc),
            grasa=Decimal("4.10"),
            sng=Decimal("8.80"),
        )
        AnalisisSilo.objects.create(
            silo=self.entera,
            tomado_en=datetime(2026, 7, 15, 9, 40, tzinfo=tz.utc),
            grasa=Decimal("4.35"),
            sng=Decimal("8.90"),
        )
        AnalisisSilo.objects.create(
            silo=self.descremada,
            tomado_en=datetime(2026, 7, 15, 9, 0, tzinfo=tz.utc),
            grasa=Decimal("0.09"),
            sng=Decimal("9.20"),
        )

        respuesta = self.cliente.get(
            "/api/estandarizacion/vales/composicion-silos/"
            f"?entera={self.entera.id}&descremada={self.descremada.id}"
        )

        self.assertEqual(respuesta.status_code, 200, respuesta.data)
        self.assertEqual(respuesta.data["entera"]["grasa"], "4.35")
        self.assertEqual(respuesta.data["entera"]["sng"], "8.90")
        self.assertIs(respuesta.data["entera"]["vigente"], True)
        self.assertEqual(respuesta.data["descremada"]["grasa"], "0.09")

    def test_avisa_cuando_el_analisis_quedo_fuera_de_vigencia(self):
        AnalisisSilo.objects.create(
            silo=self.entera,
            tomado_en=datetime(2026, 7, 15, 9, 40, tzinfo=tz.utc),
            grasa=Decimal("4.35"),
            sng=Decimal("8.90"),
        )
        MovimientoSilo.objects.create(
            silo=self.entera,
            tipo=MovimientoSilo.Tipo.INGRESO,
            litros=Decimal("21140"),
            fecha_hora=datetime(2026, 7, 15, 12, 0, tzinfo=tz.utc),
        )

        respuesta = self.cliente.get(
            f"/api/estandarizacion/vales/composicion-silos/?entera={self.entera.id}"
        )

        self.assertEqual(respuesta.status_code, 200)
        self.assertIs(respuesta.data["entera"]["vigente"], False)
        self.assertIn("21140", respuesta.data["entera"]["motivo"])

    def test_un_silo_sin_analisis_no_es_un_error_pero_lo_dice(self):
        respuesta = self.cliente.get(
            f"/api/estandarizacion/vales/composicion-silos/?entera={self.entera.id}"
        )

        self.assertEqual(respuesta.status_code, 200)
        self.assertIsNone(respuesta.data["entera"]["analisis"])
        self.assertIn("sin análisis", respuesta.data["entera"]["motivo"].lower())

    def test_dice_que_parametro_falta(self):
        AnalisisSilo.objects.create(
            silo=self.entera,
            tomado_en=datetime(2026, 7, 15, 9, 40, tzinfo=tz.utc),
            grasa=Decimal("4.35"),
        )

        respuesta = self.cliente.get(
            f"/api/estandarizacion/vales/composicion-silos/?entera={self.entera.id}"
        )

        self.assertEqual(respuesta.data["entera"]["faltantes"], ["sng"])
