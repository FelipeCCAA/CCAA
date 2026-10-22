"""OP-08: nunca confundir solicitud, aceptación y contraseña cambiada."""
from unittest.mock import patch
from urllib.error import HTTPError, URLError
from io import BytesIO
import json

from django.contrib.auth.models import User
from django.core import mail
from django.core.cache import cache
from django.core.mail import EmailMessage, get_connection
from django.test import TestCase, SimpleTestCase, override_settings
from rest_framework.test import APIClient

from .email_backends import MicrosoftGraphEmailError
from .models import EventoSeguridad, PerfilUsuario
from .views import MENSAJE_SOLICITUD_RECUPERACION
from .tests_email_backend import CONFIGURACION_GRAPH, RespuestaHTTPFalsa


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
class RecuperacionOP08Tests(TestCase):
    def setUp(self):
        cache.clear()
        self.usuario = User.objects.create_user("op08", "op08@example.invalid", "Clave-inicial-2026!")
        PerfilUsuario.objects.create(usuario=self.usuario, area="recepcion", rol="recepcion")
        self.admin = User.objects.create_superuser("op08admin", "admin@example.invalid", "clave")
        self.api = APIClient()

    def test_admin_no_declara_envio_ni_cambio_password_si_falla_correo(self):
        self.api.force_authenticate(self.admin)
        with patch("django.core.mail.backends.locmem.EmailBackend.send_messages", side_effect=MicrosoftGraphEmailError("rechazado")):
            respuesta = self.api.post(f"/api/usuarios/trabajadores/{self.usuario.pk}/restablecer-contrasena/")
        self.assertEqual(respuesta.status_code, 503)
        self.assertFalse(EventoSeguridad.objects.filter(accion="PASSWORD_RESTABLECIDA", usuario=self.usuario).exists())
        self.usuario.refresh_from_db()
        self.assertTrue(self.usuario.check_password("Clave-inicial-2026!"))

    def test_aceptacion_admin_es_solicitud_no_password_restablecida(self):
        self.api.force_authenticate(self.admin)
        respuesta = self.api.post(f"/api/usuarios/trabajadores/{self.usuario.pk}/restablecer-contrasena/")
        self.assertEqual(respuesta.status_code, 202)
        self.assertEqual(respuesta.data["estado"], "aceptado")
        self.assertNotIn("entregado", respuesta.data["mensaje"].lower())
        self.assertFalse(EventoSeguridad.objects.filter(accion="PASSWORD_RESTABLECIDA", usuario=self.usuario).exists())
        self.assertEqual(len(mail.outbox), 1)

    def test_publico_mantiene_respuesta_identica_ante_fallo_y_cuenta_inexistente(self):
        with patch("django.core.mail.backends.locmem.EmailBackend.send_messages", side_effect=MicrosoftGraphEmailError("fallo privado")):
            real = self.api.post("/api/usuarios/recuperar-contrasena/", {"email": self.usuario.email})
            ausente = self.api.post("/api/usuarios/recuperar-contrasena/", {"email": "nadie@example.invalid"})
        self.assertEqual(real.status_code, ausente.status_code)
        self.assertEqual(real.data, ausente.data)
        self.assertEqual(real.data["mensaje"], MENSAJE_SOLICITUD_RECUPERACION)
        self.assertTrue(EventoSeguridad.objects.filter(accion="CORREO_RECUPERACION_FALLIDO").exists())

    def test_backend_cero_mensajes_no_se_anuncia_aceptado(self):
        self.api.force_authenticate(self.admin)
        with patch("django.core.mail.backends.locmem.EmailBackend.send_messages", return_value=0):
            respuesta = self.api.post(f"/api/usuarios/trabajadores/{self.usuario.pk}/restablecer-contrasena/")
        self.assertEqual(respuesta.status_code, 503)

    def test_reset_administrativo_no_envia_a_otra_cuenta_con_mismo_correo(self):
        User.objects.create_user("otra-cuenta", self.usuario.email, "otra-clave")
        self.api.force_authenticate(self.admin)
        respuesta = self.api.post(f"/api/usuarios/trabajadores/{self.usuario.pk}/restablecer-contrasena/")
        self.assertEqual(respuesta.status_code, 202)
        self.assertEqual(len(mail.outbox), 1)

    def test_cuenta_sin_password_utilizable_no_finge_aceptacion(self):
        self.usuario.set_unusable_password()
        self.usuario.save(update_fields=["password"])
        self.api.force_authenticate(self.admin)
        self.assertEqual(self.api.post(f"/api/usuarios/trabajadores/{self.usuario.pk}/restablecer-contrasena/").status_code, 503)


@override_settings(**CONFIGURACION_GRAPH, CACHES={"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}})
class TransporteOP08Tests(SimpleTestCase):
    def setUp(self):
        cache.clear()

    @patch("usuarios.email_backends.urlopen")
    def test_401_renueva_token_una_vez_sin_reenvio_ciego(self, abrir):
        conexion = get_connection()
        cache.set(conexion._cache_key, "viejo")
        abrir.side_effect = [HTTPError("https://graph.invalid", 401, "unauthorized", {}, BytesIO()),
                             RespuestaHTTPFalsa(json.dumps({"access_token": "nuevo", "expires_in": 3600}).encode()),
                             RespuestaHTTPFalsa()]
        self.assertEqual(conexion.send_messages([EmailMessage("prueba", "contenido", to=["nadie@example.invalid"])]), 1)
        self.assertEqual(abrir.call_count, 3)

    @patch("usuarios.email_backends.urlopen")
    def test_timeout_no_reintenta_envio_incierto(self, abrir):
        conexion = get_connection()
        cache.set(conexion._cache_key, "ficticio")
        abrir.side_effect = URLError("conexión cortada")
        with self.assertRaises(MicrosoftGraphEmailError) as resultado:
            conexion.send_messages([EmailMessage("prueba", "contenido", to=["nadie@example.invalid"])])
        self.assertEqual(getattr(resultado.exception, "estado", None), "incierto")
        self.assertEqual(abrir.call_count, 1)

    @patch("usuarios.email_backends.urlopen")
    def test_segundo_401_no_se_reintenta(self, abrir):
        conexion = get_connection()
        cache.set(conexion._cache_key, "viejo")
        abrir.side_effect = [HTTPError("https://graph.invalid", 401, "denied", {}, BytesIO()),
                             RespuestaHTTPFalsa(b'{"access_token":"nuevo","expires_in":3600}'),
                             HTTPError("https://graph.invalid", 401, "denied", {}, BytesIO())]
        with self.assertRaises(MicrosoftGraphEmailError):
            conexion.send_messages([EmailMessage("prueba", "contenido", to=["nadie@example.invalid"])])
        self.assertEqual(abrir.call_count, 3)

    @override_settings(MICROSOFT_GRAPH_TIMEOUT=31)
    def test_rechaza_timeout_no_acotado(self):
        from django.core.exceptions import ImproperlyConfigured
        with self.assertRaises(ImproperlyConfigured):
            get_connection().validate_configuration()
