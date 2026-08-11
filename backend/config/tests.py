from unittest.mock import patch

from django.core.exceptions import ImproperlyConfigured
from django.db import DatabaseError
from django.test import SimpleTestCase

from .seguridad import (
    errores_entorno_endurecido,
    exigir_postgresql,
    normalizar_entorno,
    validar_entorno_endurecido,
)


class ConfiguracionSeguraTests(SimpleTestCase):
    def configuracion_valida(self):
        return {
            "DEBUG": False,
            "SECRET_KEY": "x" * 64,
            "ALLOWED_HOSTS": ["ccaa.example.com"],
            "SECURE_SSL_REDIRECT": True,
            "SESSION_COOKIE_SECURE": True,
            "CSRF_COOKIE_SECURE": True,
            "SECURE_HSTS_SECONDS": 31536000,
            "CSRF_TRUSTED_ORIGINS": ["https://ccaa.example.com"],
            "DATABASE_CONFIGURED": True,
        }

    def test_entorno_desconocido_falla(self):
        with self.assertRaises(ImproperlyConfigured):
            normalizar_entorno("produccion")

    def test_sqlite_falla_explicando_la_garantia_perdida(self):
        with self.assertRaisesMessage(ImproperlyConfigured, "select_for_update"):
            exigir_postgresql("sqlite", "django.db.backends.postgresql")

    def test_database_url_no_postgresql_falla(self):
        with self.assertRaisesMessage(ImproperlyConfigured, "no es PostgreSQL"):
            exigir_postgresql("postgresql", "django.db.backends.sqlite3")

    def test_produccion_segura_pasa(self):
        validar_entorno_endurecido("production", self.configuracion_valida())

    def test_desarrollo_no_exige_endurecimiento_de_produccion(self):
        validar_entorno_endurecido("development", {})

    def test_produccion_insegura_informa_todos_los_errores(self):
        errores = errores_entorno_endurecido(
            {
                "DEBUG": True,
                "SECRET_KEY": "django-insecure-corta",
                "ALLOWED_HOSTS": ["*"],
                "SECURE_SSL_REDIRECT": False,
                "SESSION_COOKIE_SECURE": False,
                "CSRF_COOKIE_SECURE": False,
                "SECURE_HSTS_SECONDS": 0,
                "CSRF_TRUSTED_ORIGINS": ["http://inseguro.example.com"],
                "DATABASE_CONFIGURED": False,
            }
        )
        self.assertGreaterEqual(len(errores), 9)
        with self.assertRaisesMessage(ImproperlyConfigured, "DJANGO_DEBUG"):
            validar_entorno_endurecido("production", {
                "DEBUG": True,
                "SECRET_KEY": "django-insecure-corta",
            })


class HealthcheckTests(SimpleTestCase):
    def test_liveness_no_consulta_la_base(self):
        with patch("config.views.comprobar_postgresql") as comprobar:
            respuesta = self.client.get("/api/salud/")
        self.assertEqual(respuesta.status_code, 200)
        comprobar.assert_not_called()

    def test_readiness_comprueba_postgresql(self):
        with patch("config.views.comprobar_postgresql") as comprobar:
            respuesta = self.client.get("/api/salud/listo/")
        self.assertEqual(respuesta.status_code, 200)
        comprobar.assert_called_once_with()

    def test_readiness_responde_503_sin_filtrar_el_error(self):
        with patch(
            "config.views.comprobar_postgresql",
            side_effect=DatabaseError("password=secreto host=interno"),
        ):
            respuesta = self.client.get("/api/salud/listo/")
        self.assertEqual(respuesta.status_code, 503)
        self.assertEqual(respuesta.json(), {"estado": "no_disponible"})
        self.assertNotContains(respuesta, "secreto", status_code=503)

    def test_comprobacion_ejecuta_select_minimo(self):
        from .views import comprobar_postgresql

        with patch("config.views.connection") as base:
            comprobar_postgresql()
        cursor = base.cursor.return_value.__enter__.return_value
        cursor.execute.assert_called_once_with("SELECT 1")
        cursor.fetchone.assert_called_once_with()
