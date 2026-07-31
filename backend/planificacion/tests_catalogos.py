"""
Pruebas de los catálogos de planificación.

Existen porque su ausencia costó caro: el endpoint referenciaba una clase que
no existía, devolvía 500, y como la pantalla de Maestros pedía todo en el
mismo `Promise.all`, las seis pestañas aparecían vacías sin decir por qué.
Un catálogo es trivial de servir y trivial de romper.
"""

from django.contrib.auth.models import User
from django.test import TestCase
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient

from usuarios.models import PerfilUsuario, Rol

from .models import BloquePlan, CategoriaConsumo, CodigoProduccion, EstadoEquipo, SemanaPlan


class CatalogosPlanificacionTests(TestCase):
    def setUp(self):
        usuario = User.objects.create_user("u-admin", password="x")
        PerfilUsuario.objects.create(usuario=usuario, rol=Rol.ADMIN)
        self.cliente = APIClient()
        self.cliente.credentials(
            HTTP_AUTHORIZATION=f"Token {Token.objects.create(user=usuario).key}"
        )

    def test_responde_sin_reventar(self):
        self.assertEqual(
            self.cliente.get("/api/planificacion/catalogos/").status_code, 200
        )

    def test_sirve_cada_juego_de_opciones(self):
        datos = self.cliente.get("/api/planificacion/catalogos/").json()

        esperados = {
            "categoria_consumo": CategoriaConsumo,
            "formato": CodigoProduccion.Formato,
            "estado_semana": SemanaPlan.Estado,
            "tipo_bloque": BloquePlan.Tipo,
            "estado_equipo": EstadoEquipo,
        }

        for clave, choices in esperados.items():
            with self.subTest(catalogo=clave):
                self.assertEqual(
                    {o["valor"] for o in datos[clave]}, set(choices.values)
                )

    def test_cada_valor_trae_su_etiqueta(self):
        datos = self.cliente.get("/api/planificacion/catalogos/").json()

        for clave, opciones in datos.items():
            with self.subTest(catalogo=clave):
                self.assertTrue(all(o["etiqueta"] for o in opciones))
