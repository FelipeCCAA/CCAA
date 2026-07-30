"""Pruebas aisladas del backend Microsoft Graph, sin llamadas externas."""

import json
from unittest.mock import patch

from django.core.cache import cache
from django.core.exceptions import ImproperlyConfigured
from django.core.mail import EmailMultiAlternatives, get_connection
from django.test import SimpleTestCase, override_settings


class RespuestaHTTPFalsa:
    def __init__(self, contenido=b""):
        self.contenido = contenido

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self):
        return self.contenido


CONFIGURACION_GRAPH = {
    "EMAIL_BACKEND": "usuarios.email_backends.MicrosoftGraphEmailBackend",
    "MICROSOFT_GRAPH_TENANT_ID": "tenant-prueba",
    "MICROSOFT_GRAPH_CLIENT_ID": "cliente-prueba",
    "MICROSOFT_GRAPH_CLIENT_SECRET": "secreto-prueba",
    "MICROSOFT_GRAPH_SENDER": "sistema@example.com",
    "MICROSOFT_GRAPH_TIMEOUT": 10,
    "MICROSOFT_GRAPH_SAVE_TO_SENT_ITEMS": False,
}


@override_settings(**CONFIGURACION_GRAPH)
class MicrosoftGraphEmailBackendTests(SimpleTestCase):
    def setUp(self):
        cache.clear()

    @patch("usuarios.email_backends.urlopen")
    def test_obtiene_token_y_envia_html_con_mail_send(self, solicitar):
        solicitar.side_effect = [
            RespuestaHTTPFalsa(
                json.dumps(
                    {"access_token": "token-oauth", "expires_in": 3600}
                ).encode()
            ),
            RespuestaHTTPFalsa(),
        ]
        mensaje = EmailMultiAlternatives(
            subject="Recuperación",
            body="Versión de texto",
            from_email="sistema@example.com",
            to=["persona@example.com"],
        )
        mensaje.attach_alternative("<strong>Recuperación</strong>", "text/html")

        enviados = mensaje.send()

        self.assertEqual(enviados, 1)
        self.assertEqual(solicitar.call_count, 2)

        peticion_token = solicitar.call_args_list[0].args[0]
        self.assertIn("tenant-prueba/oauth2/v2.0/token", peticion_token.full_url)
        self.assertIn(
            b"scope=https%3A%2F%2Fgraph.microsoft.com%2F.default",
            peticion_token.data,
        )

        peticion_envio = solicitar.call_args_list[1].args[0]
        self.assertEqual(
            peticion_envio.full_url,
            "https://graph.microsoft.com/v1.0/users/"
            "sistema@example.com/sendMail",
        )
        self.assertEqual(
            peticion_envio.get_header("Authorization"),
            "Bearer token-oauth",
        )

        payload = json.loads(peticion_envio.data)
        self.assertEqual(payload["message"]["body"]["contentType"], "HTML")
        self.assertEqual(
            payload["message"]["toRecipients"][0]["emailAddress"]["address"],
            "persona@example.com",
        )
        self.assertFalse(payload["saveToSentItems"])

    @patch("usuarios.email_backends.urlopen")
    def test_reutiliza_el_token_cacheado(self, solicitar):
        solicitar.side_effect = [
            RespuestaHTTPFalsa(
                json.dumps(
                    {"access_token": "token-oauth", "expires_in": 3600}
                ).encode()
            ),
            RespuestaHTTPFalsa(),
            RespuestaHTTPFalsa(),
        ]
        conexion = get_connection()
        mensajes = [
            EmailMultiAlternatives(
                subject=f"Mensaje {numero}",
                body="Contenido",
                from_email="sistema@example.com",
                to=[f"persona{numero}@example.com"],
            )
            for numero in (1, 2)
        ]

        enviados = conexion.send_messages(mensajes)

        self.assertEqual(enviados, 2)
        self.assertEqual(solicitar.call_count, 3)

    @override_settings(MICROSOFT_GRAPH_CLIENT_SECRET="")
    def test_falla_claro_si_faltan_credenciales(self):
        mensaje = EmailMultiAlternatives(
            subject="Prueba",
            body="Contenido",
            from_email="sistema@example.com",
            to=["persona@example.com"],
        )

        with self.assertRaises(ImproperlyConfigured) as contexto:
            mensaje.send()

        self.assertIn("MICROSOFT_GRAPH_CLIENT_SECRET", str(contexto.exception))
