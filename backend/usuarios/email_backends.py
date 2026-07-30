"""
Backend de correo para Microsoft 365 mediante Microsoft Graph y OAuth 2.0.

Usa el flujo ``client_credentials``: no almacena contraseñas de usuarios ni
requiere una sesión interactiva. El token de acceso se conserva en la caché de
Django hasta poco antes de expirar.
"""

from __future__ import annotations

import base64
import json
import logging
from email.mime.base import MIMEBase
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen

from django.conf import settings
from django.core.cache import cache
from django.core.exceptions import ImproperlyConfigured
from django.core.mail.backends.base import BaseEmailBackend


logger = logging.getLogger(__name__)


class MicrosoftGraphEmailError(RuntimeError):
    """Error seguro y sin credenciales devuelto por Microsoft Graph."""


class MicrosoftGraphEmailBackend(BaseEmailBackend):
    """Envía mensajes de Django usando el endpoint ``sendMail`` de Graph."""

    token_cache_prefix = "microsoft_graph_email_token"

    def __init__(self, fail_silently=False, **kwargs):
        super().__init__(fail_silently=fail_silently, **kwargs)
        self.tenant_id = settings.MICROSOFT_GRAPH_TENANT_ID
        self.client_id = settings.MICROSOFT_GRAPH_CLIENT_ID
        self.client_secret = settings.MICROSOFT_GRAPH_CLIENT_SECRET
        self.sender = settings.MICROSOFT_GRAPH_SENDER
        self.timeout = settings.MICROSOFT_GRAPH_TIMEOUT
        self.save_to_sent_items = settings.MICROSOFT_GRAPH_SAVE_TO_SENT_ITEMS

    def send_messages(self, email_messages):
        """Envía cada mensaje y devuelve la cantidad aceptada por Graph."""
        mensajes = list(email_messages or [])
        if not mensajes:
            return 0

        try:
            self.validate_configuration()
            token = self._obtener_token()
            enviados = 0

            for mensaje in mensajes:
                if not mensaje.recipients():
                    continue

                self._enviar_mensaje(token, mensaje)
                enviados += 1

            return enviados
        except Exception:
            if self.fail_silently:
                logger.exception("Microsoft Graph no pudo enviar el correo")
                return 0
            raise

    def validate_configuration(self):
        """Comprueba que las cuatro credenciales obligatorias estén presentes."""
        faltantes = [
            nombre
            for nombre, valor in (
                ("MICROSOFT_GRAPH_TENANT_ID", self.tenant_id),
                ("MICROSOFT_GRAPH_CLIENT_ID", self.client_id),
                ("MICROSOFT_GRAPH_CLIENT_SECRET", self.client_secret),
                ("MICROSOFT_GRAPH_SENDER", self.sender),
            )
            if not valor
        ]

        if faltantes:
            raise ImproperlyConfigured(
                "Falta configurar Microsoft Graph: " + ", ".join(faltantes)
            )

    @property
    def _cache_key(self):
        return f"{self.token_cache_prefix}:{self.tenant_id}:{self.client_id}"

    def _obtener_token(self):
        token_cacheado = cache.get(self._cache_key)
        if token_cacheado:
            return token_cacheado

        url = (
            "https://login.microsoftonline.com/"
            f"{quote(self.tenant_id, safe='.-')}/oauth2/v2.0/token"
        )
        cuerpo = urlencode(
            {
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "scope": "https://graph.microsoft.com/.default",
                "grant_type": "client_credentials",
            }
        ).encode("utf-8")

        respuesta = self._solicitar(
            Request(
                url,
                data=cuerpo,
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                method="POST",
            ),
            operacion="autenticación",
        )
        datos = self._leer_json(respuesta, "autenticación")
        token = datos.get("access_token")

        if not token:
            raise MicrosoftGraphEmailError(
                "Microsoft Entra no entregó un token de acceso."
            )

        expiracion = max(60, int(datos.get("expires_in", 3600)) - 120)
        cache.set(self._cache_key, token, timeout=expiracion)
        return token

    def _enviar_mensaje(self, token, mensaje):
        remitente = quote(self.sender, safe="@.-_")
        url = f"https://graph.microsoft.com/v1.0/users/{remitente}/sendMail"
        contenido, tipo = self._contenido(mensaje)

        payload: dict[str, Any] = {
            "message": {
                "subject": mensaje.subject,
                "body": {"contentType": tipo, "content": contenido},
                "toRecipients": self._destinatarios(mensaje.to),
                "ccRecipients": self._destinatarios(mensaje.cc),
                "bccRecipients": self._destinatarios(mensaje.bcc),
            },
            "saveToSentItems": self.save_to_sent_items,
        }

        reply_to = getattr(mensaje, "reply_to", None) or []
        if reply_to:
            payload["message"]["replyTo"] = self._destinatarios(reply_to)

        adjuntos = self._adjuntos(mensaje)
        if adjuntos:
            payload["message"]["attachments"] = adjuntos

        self._solicitar(
            Request(
                url,
                data=json.dumps(payload).encode("utf-8"),
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json",
                },
                method="POST",
            ),
            operacion="envío",
        )

    @staticmethod
    def _contenido(mensaje):
        for alternativa in getattr(mensaje, "alternatives", []):
            if alternativa.mimetype == "text/html":
                return alternativa.content, "HTML"
        return mensaje.body, "Text"

    @staticmethod
    def _destinatarios(direcciones):
        return [
            {"emailAddress": {"address": direccion}}
            for direccion in (direcciones or [])
        ]

    @staticmethod
    def _adjuntos(mensaje):
        resultado = []
        for adjunto in getattr(mensaje, "attachments", []):
            if isinstance(adjunto, MIMEBase):
                raise MicrosoftGraphEmailError(
                    "Los adjuntos MIME no son compatibles con este backend."
                )

            nombre, contenido, mimetype = adjunto
            if isinstance(contenido, str):
                contenido = contenido.encode("utf-8")

            resultado.append(
                {
                    "@odata.type": "#microsoft.graph.fileAttachment",
                    "name": nombre,
                    "contentType": mimetype or "application/octet-stream",
                    "contentBytes": base64.b64encode(contenido).decode("ascii"),
                }
            )
        return resultado

    def _solicitar(self, peticion, operacion):
        try:
            with urlopen(peticion, timeout=self.timeout) as respuesta:
                return respuesta.read()
        except HTTPError as error:
            detalle = self._detalle_http(error)
            raise MicrosoftGraphEmailError(
                f"Microsoft Graph rechazó la {operacion} "
                f"(HTTP {error.code}{detalle})."
            ) from error
        except (URLError, TimeoutError) as error:
            raise MicrosoftGraphEmailError(
                f"No fue posible conectar con Microsoft durante la {operacion}."
            ) from error

    @staticmethod
    def _leer_json(respuesta, operacion):
        try:
            return json.loads(respuesta.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise MicrosoftGraphEmailError(
                f"Microsoft devolvió una respuesta inválida durante la {operacion}."
            ) from error

    @staticmethod
    def _detalle_http(error):
        request_id = error.headers.get("request-id") if error.headers else None
        return f", request-id {request_id}" if request_id else ""
