"""
Pruebas de la caducidad del token.

El token de DRF no expira solo: una vez emitido servía para siempre. Con el
login sin límite de intentos, el vector completo era «fuerza bruta sin freno →
acceso perpetuo». Lo que se fija aquí es la mitad que cierra el plazo.
"""

from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.authtoken.models import Token


class CaducidadTests(TestCase):

    def setUp(self):
        cache.clear()
        self.usuario = User.objects.create_user(
            username="operario", password="clave-correcta-123"
        )
        self.token = Token.objects.create(user=self.usuario)

    def tearDown(self):
        cache.clear()

    def _yo(self):
        return self.client.get(
            "/api/usuarios/yo/", HTTP_AUTHORIZATION=f"Token {self.token.key}"
        )

    def _envejecer(self, horas):
        Token.objects.filter(pk=self.token.pk).update(
            created=timezone.now() - timezone.timedelta(hours=horas)
        )

    @override_settings(TOKEN_TTL_HORAS=12)
    def test_un_token_reciente_sirve(self):
        self.assertEqual(self._yo().status_code, 200)

    @override_settings(TOKEN_TTL_HORAS=12)
    def test_un_token_viejo_se_rechaza(self):
        self._envejecer(13)

        self.assertEqual(self._yo().status_code, 401)

    @override_settings(TOKEN_TTL_HORAS=12)
    def test_el_token_vencido_se_borra(self):
        """
        Se borra en vez de dejarlo pudrirse: si no, la tabla acumula claves
        muertas que siguen apareciendo en el admin como si fueran sesiones
        vivas.
        """
        self._envejecer(13)
        self._yo()

        self.assertFalse(Token.objects.filter(pk=self.token.pk).exists())

    @override_settings(TOKEN_TTL_HORAS=0)
    def test_cero_desactiva_la_caducidad(self):
        """Salida de emergencia, no valor recomendado."""
        self._envejecer(1000)

        self.assertEqual(self._yo().status_code, 200)


class RenovacionAlEntrarTests(TestCase):

    def setUp(self):
        cache.clear()
        self.usuario = User.objects.create_user(
            username="operario", password="clave-correcta-123"
        )

    def tearDown(self):
        cache.clear()

    def _login(self):
        return self.client.post(
            "/api/usuarios/login/",
            {"username": "operario", "password": "clave-correcta-123"},
            content_type="application/json",
        )

    @override_settings(TOKEN_TTL_HORAS=12)
    def test_entrar_de_nuevo_reinicia_el_reloj(self):
        """
        Sin esto la caducidad sería inservible: el token conservaría la fecha
        del primer login de su vida y quien trabaja a diario quedaría fuera al
        segundo día sin poder hacer nada al respecto.
        """
        token = Token.objects.create(user=self.usuario)
        Token.objects.filter(pk=token.pk).update(
            created=timezone.now() - timezone.timedelta(hours=11)
        )

        self.assertEqual(self._login().status_code, 200)

        token.refresh_from_db()
        antiguedad = timezone.now() - token.created

        self.assertLess(antiguedad, timezone.timedelta(minutes=1))

    @override_settings(TOKEN_TTL_HORAS=12)
    def test_la_clave_no_cambia_al_entrar(self):
        """
        `Token` es `OneToOne` con el usuario: todas sus sesiones comparten
        clave. Cambiarla al entrar echaría del sistema al terminal de planta
        cada vez que alguien inicia sesión desde el teléfono.
        """
        anterior = Token.objects.create(user=self.usuario).key

        self.assertEqual(self._login().json()["token"], anterior)

    @override_settings(TOKEN_TTL_HORAS=12)
    def test_el_token_devuelto_al_entrar_funciona(self):
        """
        Comprobación de punta a punta: el ciclo completo —entrar, usar— tiene
        que quedar en pie con la caducidad activada.
        """
        clave = self._login().json()["token"]

        respuesta = self.client.get(
            "/api/usuarios/yo/", HTTP_AUTHORIZATION=f"Token {clave}"
        )

        self.assertEqual(respuesta.status_code, 200)
