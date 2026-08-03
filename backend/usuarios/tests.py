"""
Pruebas de autenticación.

Las que importan no son las del camino feliz, sino las que comprueban que la
API queda CERRADA: que sin token no se lee ni se escribe nada.
"""

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import get_resolver
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient

from .models import PerfilUsuario, Rol


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
            usuario=self.usuario,
            cargo="Operadora",
            area="Producción",
            rol=Rol.PRODUCCION,
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
        self.assertEqual(datos["usuario"]["perfil"]["rol_etiqueta"], "Producción")
        self.assertEqual(datos["usuario"]["rol"], "produccion")

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


class PanelAdministracionTests(TestCase):
    def setUp(self):
        self.cliente = APIClient()
        self.admin = User.objects.create_user(
            username="administradora", password="clave-de-prueba"
        )
        PerfilUsuario.objects.create(
            usuario=self.admin,
            rol=Rol.ADMIN,
            nivel=PerfilUsuario.Nivel.ADMIN,
            area=PerfilUsuario.Area.ADMINISTRACION,
        )
        self.trabajador = User.objects.create_user(
            username="operador-area",
            password="clave-de-prueba",
            first_name="Juan",
            last_name="Soto",
        )
        PerfilUsuario.objects.create(
            usuario=self.trabajador,
            rol=Rol.PRODUCCION,
            area="Secado",
            cargo="Operador",
            turno="A",
        )

    def test_admin_ve_trabajadores_y_su_area(self):
        self.cliente.force_authenticate(self.admin)

        respuesta = self.cliente.get("/api/usuarios/trabajadores/")

        self.assertEqual(respuesta.status_code, 200)
        trabajador = next(
            usuario for usuario in respuesta.json()
            if usuario["username"] == "operador-area"
        )
        self.assertEqual(trabajador["perfil"]["area"], "Secado")
        self.assertEqual(trabajador["perfil"]["cargo"], "Operador")
        self.assertTrue(trabajador["activo"])

    def test_otro_rol_no_puede_ver_el_personal(self):
        self.cliente.force_authenticate(self.trabajador)

        respuesta = self.cliente.get("/api/usuarios/trabajadores/")

        self.assertEqual(respuesta.status_code, 403)

    def test_administrador_general_crea_administrador_de_area_sin_contrasena_visible(self):
        self.cliente.force_authenticate(self.admin)
        respuesta = self.cliente.post(
            "/api/usuarios/trabajadores/",
            {"username": "jefa-bodega", "area": "bodega", "nivel": "admin", "cargo": "Jefatura"},
            format="json",
        )
        self.assertEqual(respuesta.status_code, 201)
        creado = User.objects.get(username="jefa-bodega")
        self.assertTrue(creado.has_usable_password())
        self.assertEqual(creado.perfil.area, PerfilUsuario.Area.BODEGA)
        self.assertEqual(creado.perfil.nivel, PerfilUsuario.Nivel.ADMIN)

    def test_administrador_de_area_solo_crea_trabajadores_de_su_area(self):
        jefe = User.objects.create_user("jefe-secado", password="x")
        PerfilUsuario.objects.create(
            usuario=jefe, area=PerfilUsuario.Area.SECADO,
            nivel=PerfilUsuario.Nivel.ADMIN,
        )
        self.cliente.force_authenticate(jefe)
        respuesta = self.cliente.post(
            "/api/usuarios/trabajadores/",
            {"username": "nuevo", "area": "calidad", "nivel": "admin"},
            format="json",
        )
        self.assertEqual(respuesta.status_code, 201)
        perfil = User.objects.get(username="nuevo").perfil
        self.assertEqual(perfil.area, PerfilUsuario.Area.SECADO)
        self.assertEqual(perfil.nivel, PerfilUsuario.Nivel.TRABAJADOR)


def rutas_de_la_api():
    """
    Todas las rutas de `/api/` que no llevan parámetros, descubiertas del
    enrutador.

    Se descubren en vez de listarse a mano porque una lista escrita a mano
    envejece en silencio: cubre lo que había el día que se escribió y no lo
    que se agregó después, que es justamente el endpoint nuevo que podría
    haberse olvidado de declarar permisos. Esta lista ya se había quedado sin
    las rutas de Recepción.
    """
    rutas = []

    def recorrer(patrones, prefijo=""):
        for patron in patrones:
            ruta = prefijo + str(patron.pattern).replace("^", "").replace("$", "")

            if hasattr(patron, "url_patterns"):
                recorrer(patron.url_patterns, ruta)
            elif "<" not in ruta:
                rutas.append("/" + ruta)

    recorrer(get_resolver().url_patterns)

    return sorted(r for r in rutas if r.startswith("/api/"))


class ApiCerradaTests(TestCase):
    """
    La API completa exige identificarse.

    Si alguien agrega un endpoint y olvida declarar permisos, queda cerrado
    por defecto. Esta prueba lo vigila para todas las rutas descubiertas, no
    para una lista escrita a mano.

    Las excepciones son el login y la recuperación de contraseña, que declaran
    ``AllowAny`` explícitamente y se enumeran abajo. Abrir un endpoint nuevo
    obliga a agregarlo aquí, que es justamente el punto: la lista de lo que
    está abierto se mantiene corta y a la vista.
    """

    # Sin el login nadie podría obtener un token, y quien olvidó su contraseña
    # tampoco puede identificarse para pedir una nueva.
    ABIERTAS = {
        "/api/usuarios/login/",
        "/api/usuarios/recuperar-contrasena/",
        "/api/usuarios/restablecer-contrasena/",
    }

    def setUp(self):
        self.cliente = APIClient()

    def test_hay_rutas_que_vigilar(self):
        """
        Si el descubrimiento se rompe, la prueba de abajo pasaría sin
        comprobar nada. Esto lo delata.
        """
        self.assertGreater(len(rutas_de_la_api()), 10)

    def test_sin_token_no_se_lee_nada(self):
        for ruta in rutas_de_la_api():
            if ruta in self.ABIERTAS:
                continue

            with self.subTest(ruta=ruta):
                self.assertEqual(
                    self.cliente.get(ruta).status_code,
                    401,
                    f"{ruta} responde sin identificarse",
                )

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
