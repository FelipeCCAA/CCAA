"""
Pruebas de autenticación.

Las que importan no son las del camino feliz, sino las que comprueban que la
API queda CERRADA: que sin token no se lee ni se escribe nada.
"""

from django.contrib.auth.models import User
from django.test import TestCase
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient

from .models import PerfilUsuario


class LoginTests(TestCase):
    def setUp(self):
        self.cliente = APIClient()
        self.usuario = User.objects.create_user(
            username="operador",
            password="clave-de-prueba",
            first_name="Ana",
            last_name="Pérez",
        )
        PerfilUsuario.objects.create(
            usuario=self.usuario, cargo="Operadora", area="Producción", rol="TRABAJADOR"
        )

    def test_credenciales_correctas_devuelven_token_y_usuario(self):
        respuesta = self.cliente.post(
            "/api/usuarios/login/",
            {"username": "operador", "password": "clave-de-prueba"},
            format="json",
        )

        self.assertEqual(respuesta.status_code, 200)
        datos = respuesta.json()
        self.assertTrue(datos["token"])
        self.assertEqual(datos["usuario"]["nombre"], "Ana")
        self.assertEqual(datos["usuario"]["perfil"]["cargo"], "Operadora")
        self.assertEqual(datos["usuario"]["perfil"]["rol_etiqueta"], "Trabajador")

    def test_contrasena_incorrecta_no_entrega_token(self):
        respuesta = self.cliente.post(
            "/api/usuarios/login/",
            {"username": "operador", "password": "otra"},
            format="json",
        )

        self.assertEqual(respuesta.status_code, 401)
        self.assertNotIn("token", respuesta.json())

    def test_faltan_credenciales(self):
        respuesta = self.cliente.post(
            "/api/usuarios/login/", {"username": "operador"}, format="json"
        )

        self.assertEqual(respuesta.status_code, 400)

    def test_una_cuenta_desactivada_no_entra(self):
        self.usuario.is_active = False
        self.usuario.save()

        respuesta = self.cliente.post(
            "/api/usuarios/login/",
            {"username": "operador", "password": "clave-de-prueba"},
            format="json",
        )

        self.assertIn(respuesta.status_code, (401, 403))
        self.assertNotIn("token", respuesta.json())

    def test_un_usuario_sin_perfil_no_rompe_el_login(self):
        """`createsuperuser` no crea perfil: el login debe funcionar igual."""
        User.objects.create_user(username="admin2", password="clave-de-prueba")

        respuesta = self.cliente.post(
            "/api/usuarios/login/",
            {"username": "admin2", "password": "clave-de-prueba"},
            format="json",
        )

        self.assertEqual(respuesta.status_code, 200)
        self.assertIsNone(respuesta.json()["usuario"]["perfil"])


class SesionTests(TestCase):
    def setUp(self):
        self.cliente = APIClient()
        self.usuario = User.objects.create_user(
            username="operador", password="clave-de-prueba"
        )
        self.token = Token.objects.create(user=self.usuario)

    def _autenticar(self):
        self.cliente.credentials(HTTP_AUTHORIZATION=f"Token {self.token.key}")

    def test_yo_devuelve_el_usuario_del_token(self):
        self._autenticar()

        respuesta = self.cliente.get("/api/usuarios/yo/")

        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta.json()["username"], "operador")

    def test_yo_sin_token_es_401(self):
        self.assertEqual(self.cliente.get("/api/usuarios/yo/").status_code, 401)

    def test_logout_invalida_el_token(self):
        """
        Borrar el token del navegador no basta: hay que desactivarlo en el
        servidor, o uno robado serviría para siempre.
        """
        self._autenticar()

        self.assertEqual(self.cliente.post("/api/usuarios/logout/").status_code, 200)
        self.assertEqual(Token.objects.count(), 0)
        self.assertEqual(self.cliente.get("/api/usuarios/yo/").status_code, 401)

    def test_un_token_inventado_no_sirve(self):
        self.cliente.credentials(HTTP_AUTHORIZATION="Token 0123456789abcdef")

        self.assertEqual(self.cliente.get("/api/usuarios/yo/").status_code, 401)


class ApiCerradaTests(TestCase):
    """
    La API completa exige identificarse.

    Si alguien agrega un endpoint y olvida declarar permisos, queda cerrado
    por defecto. Esta prueba lo vigila para las rutas que ya existen.
    """

    RUTAS = [
        "/api/produccion/lotes/",
        "/api/produccion/analisis/",
        "/api/produccion/resumen/",
        "/api/maestros/productos/",
        "/api/maestros/mandantes/",
        "/api/maestros/especificaciones/",
        "/api/maestros/parametros/",
    ]

    def setUp(self):
        self.cliente = APIClient()

    def test_sin_token_no_se_lee_nada(self):
        for ruta in self.RUTAS:
            with self.subTest(ruta=ruta):
                self.assertEqual(self.cliente.get(ruta).status_code, 401)

    def test_sin_token_no_se_escribe_nada(self):
        self.assertEqual(
            self.cliente.post("/api/produccion/lotes/", {}, format="json").status_code,
            401,
        )

    def test_sin_token_no_se_borra_nada(self):
        self.assertEqual(
            self.cliente.delete("/api/produccion/lotes/1/").status_code, 401
        )

    def test_el_login_si_esta_abierto(self):
        """
        Es la única excepción: sin ella nadie podría obtener un token.

        Se comprueba con credenciales VÁLIDAS: con las inválidas el 401 sería
        el correcto y no distinguiría "cerrado" de "contraseña mala".
        """
        User.objects.create_user(username="alguien", password="clave-de-prueba")

        respuesta = self.cliente.post(
            "/api/usuarios/login/",
            {"username": "alguien", "password": "clave-de-prueba"},
            format="json",
        )

        self.assertEqual(respuesta.status_code, 200)
        self.assertTrue(respuesta.json()["token"])
