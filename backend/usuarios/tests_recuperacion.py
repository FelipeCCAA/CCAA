"""Pruebas del flujo seguro de recuperación de contraseña."""

from unittest.mock import patch
from urllib.parse import parse_qs, urlparse

from django.contrib.auth.models import User
from django.contrib.auth.tokens import default_token_generator
from django.core import mail
from django.core.cache import cache
from django.db import DatabaseError
from django.test import TestCase, override_settings
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient

from .views import MENSAJE_SOLICITUD_RECUPERACION


@override_settings(
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    PASSWORD_RESET_FRONTEND_URL="https://app.example/restablecer-contrasena",
)
class SolicitudRecuperacionTests(TestCase):
    def setUp(self):
        cache.clear()
        self.cliente = APIClient()
        self.usuario = User.objects.create_user(
            username="operador",
            email="operador@example.com",
            password="Clave-anterior-2026!",
        )

    def test_envia_un_enlace_nativo_al_correo_registrado(self):
        respuesta = self.cliente.post(
            "/api/usuarios/recuperar-contrasena/",
            {"email": self.usuario.email},
            format="json",
        )

        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(
            respuesta.json()["mensaje"],
            MENSAJE_SOLICITUD_RECUPERACION,
        )
        self.assertEqual(len(mail.outbox), 1)

        cuerpo = mail.outbox[0].body
        enlace = next(line for line in cuerpo.splitlines() if line.startswith("https://"))
        parametros = parse_qs(urlparse(enlace).query)

        self.assertIn("uid", parametros)
        self.assertIn("token", parametros)

    def test_no_revela_si_el_correo_no_existe(self):
        existente = self.cliente.post(
            "/api/usuarios/recuperar-contrasena/",
            {"email": self.usuario.email},
            format="json",
        )
        inexistente = self.cliente.post(
            "/api/usuarios/recuperar-contrasena/",
            {"email": "nadie@example.com"},
            format="json",
        )

        self.assertEqual(existente.status_code, inexistente.status_code)
        self.assertEqual(existente.json(), inexistente.json())
        self.assertEqual(len(mail.outbox), 1)

    def test_no_envia_a_una_cuenta_inactiva(self):
        self.usuario.is_active = False
        self.usuario.save(update_fields=["is_active"])

        respuesta = self.cliente.post(
            "/api/usuarios/recuperar-contrasena/",
            {"email": self.usuario.email},
            format="json",
        )

        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(len(mail.outbox), 0)

    def test_rechaza_un_correo_mal_formado(self):
        respuesta = self.cliente.post(
            "/api/usuarios/recuperar-contrasena/",
            {"email": "no-es-un-correo"},
            format="json",
        )

        self.assertEqual(respuesta.status_code, 400)

    def test_limita_solicitudes_repetidas_por_ip(self):
        for _ in range(5):
            respuesta = self.cliente.post(
                "/api/usuarios/recuperar-contrasena/",
                {"email": "nadie@example.com"},
                format="json",
            )
            self.assertEqual(respuesta.status_code, 200)

        respuesta = self.cliente.post(
            "/api/usuarios/recuperar-contrasena/",
            {"email": "nadie@example.com"},
            format="json",
        )

        self.assertEqual(respuesta.status_code, 429)

    @patch(
        "usuarios.views.PasswordResetForm.save",
        side_effect=DatabaseError("base no disponible"),
    )
    def test_un_fallo_de_base_de_datos_devuelve_500_generico(self, _guardar):
        respuesta = self.cliente.post(
            "/api/usuarios/recuperar-contrasena/",
            {"email": self.usuario.email},
            format="json",
        )

        self.assertEqual(respuesta.status_code, 500)
        self.assertNotIn("base no disponible", str(respuesta.content))


class ConfirmacionRecuperacionTests(TestCase):
    NUEVA_CLAVE = "Clave-nueva-segura-2026!"

    def setUp(self):
        cache.clear()
        self.cliente = APIClient()
        self.usuario = User.objects.create_user(
            username="operador",
            email="operador@example.com",
            password="Clave-anterior-2026!",
        )
        self.token_api = Token.objects.create(user=self.usuario)
        self.uid = urlsafe_base64_encode(force_bytes(self.usuario.pk))
        self.token = default_token_generator.make_token(self.usuario)

    def _datos(self, **cambios):
        datos = {
            "uid": self.uid,
            "token": self.token,
            "nueva_contrasena": self.NUEVA_CLAVE,
            "confirmar_contrasena": self.NUEVA_CLAVE,
        }
        datos.update(cambios)
        return datos

    def test_cambia_la_clave_e_invalida_token_de_recuperacion_y_api(self):
        respuesta = self.cliente.post(
            "/api/usuarios/restablecer-contrasena/",
            self._datos(),
            format="json",
        )

        self.assertEqual(respuesta.status_code, 200)
        self.usuario.refresh_from_db()
        self.assertTrue(self.usuario.check_password(self.NUEVA_CLAVE))
        self.assertFalse(Token.objects.filter(pk=self.token_api.pk).exists())

        reutilizacion = self.cliente.post(
            "/api/usuarios/restablecer-contrasena/",
            self._datos(),
            format="json",
        )
        self.assertEqual(reutilizacion.status_code, 400)

    def test_rechaza_uid_o_token_invalidos_sin_distinguir_el_motivo(self):
        uid_invalido = self.cliente.post(
            "/api/usuarios/restablecer-contrasena/",
            self._datos(uid="uid-invalido"),
            format="json",
        )
        token_invalido = self.cliente.post(
            "/api/usuarios/restablecer-contrasena/",
            self._datos(token="token-invalido"),
            format="json",
        )

        self.assertEqual(uid_invalido.status_code, 400)
        self.assertEqual(token_invalido.status_code, 400)
        self.assertEqual(uid_invalido.json(), token_invalido.json())

    def test_aplica_los_validadores_de_contrasena_de_django(self):
        respuesta = self.cliente.post(
            "/api/usuarios/restablecer-contrasena/",
            self._datos(nueva_contrasena="123", confirmar_contrasena="123"),
            format="json",
        )

        self.assertEqual(respuesta.status_code, 400)
        self.assertIn("nueva_contrasena", respuesta.json())
        self.usuario.refresh_from_db()
        self.assertTrue(self.usuario.check_password("Clave-anterior-2026!"))

    def test_rechaza_contrasenas_que_no_coinciden(self):
        respuesta = self.cliente.post(
            "/api/usuarios/restablecer-contrasena/",
            self._datos(confirmar_contrasena="otra-clave"),
            format="json",
        )

        self.assertEqual(respuesta.status_code, 400)
        self.assertIn("confirmar_contrasena", respuesta.json())

    def test_una_cuenta_inactiva_no_puede_confirmar(self):
        self.usuario.is_active = False
        self.usuario.save(update_fields=["is_active"])

        respuesta = self.cliente.post(
            "/api/usuarios/restablecer-contrasena/",
            self._datos(),
            format="json",
        )

        self.assertEqual(respuesta.status_code, 400)


@override_settings(
    EMAIL_BACKEND="usuarios.email_backends.MicrosoftGraphEmailBackend",
    MICROSOFT_GRAPH_TENANT_ID="",
    MICROSOFT_GRAPH_CLIENT_ID="",
    MICROSOFT_GRAPH_CLIENT_SECRET="",
    MICROSOFT_GRAPH_SENDER="",
)
class ConfiguracionRecuperacionTests(TestCase):
    def test_no_informa_envio_si_microsoft_graph_no_esta_configurado(self):
        respuesta = APIClient().post(
            "/api/usuarios/recuperar-contrasena/",
            {"email": "persona@example.com"},
            format="json",
        )

        self.assertEqual(respuesta.status_code, 503)
        self.assertEqual(
            respuesta.json()["error"],
            "El servicio de correo no está disponible.",
        )
