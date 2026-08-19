"""Pruebas de caducidad absoluta, inactividad y actividad controlada."""

from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import TestCase, override_settings
from django.utils import timezone

from .models import SesionUsuario
from .sesiones import nueva_credencial


class CaducidadTests(TestCase):
    def setUp(self):
        cache.clear()
        self.usuario = User.objects.create_user("operario", password="clave-correcta-123")
        self.token, digest = nueva_credencial()
        self.sesion = SesionUsuario.objects.create(usuario=self.usuario, token_hash=digest)

    def _yo(self):
        return self.client.get(
            "/api/usuarios/yo/", HTTP_AUTHORIZATION=f"Token {self.token}"
        )

    @override_settings(SESSION_ABSOLUTE_TIMEOUT_HOURS=12, SESSION_IDLE_TIMEOUT_MINUTES=60)
    def test_una_sesion_reciente_sirve(self):
        self.assertEqual(self._yo().status_code, 200)

    @override_settings(SESSION_ABSOLUTE_TIMEOUT_HOURS=12, SESSION_IDLE_TIMEOUT_MINUTES=60)
    def test_una_sesion_inactiva_se_cierra_y_rechaza(self):
        SesionUsuario.objects.filter(pk=self.sesion.pk).update(
            ultima_actividad=timezone.now() - timezone.timedelta(minutes=61)
        )
        respuesta = self._yo()
        self.assertEqual(respuesta.status_code, 401)
        self.sesion.refresh_from_db()
        self.assertEqual(self.sesion.motivo_cierre, SesionUsuario.MotivoCierre.INACTIVIDAD)

    @override_settings(SESSION_ABSOLUTE_TIMEOUT_HOURS=12, SESSION_IDLE_TIMEOUT_MINUTES=0)
    def test_una_sesion_supera_el_limite_absoluto(self):
        SesionUsuario.objects.filter(pk=self.sesion.pk).update(
            fecha_inicio=timezone.now() - timezone.timedelta(hours=13)
        )
        self.assertEqual(self._yo().status_code, 401)
        self.sesion.refresh_from_db()
        self.assertEqual(self.sesion.motivo_cierre, SesionUsuario.MotivoCierre.ABSOLUTA)

    @override_settings(SESSION_ABSOLUTE_TIMEOUT_HOURS=0, SESSION_IDLE_TIMEOUT_MINUTES=0)
    def test_cero_desactiva_ambos_limites(self):
        SesionUsuario.objects.filter(pk=self.sesion.pk).update(
            fecha_inicio=timezone.now() - timezone.timedelta(days=100),
            ultima_actividad=timezone.now() - timezone.timedelta(days=100),
        )
        self.assertEqual(self._yo().status_code, 200)

    @override_settings(
        SESSION_ABSOLUTE_TIMEOUT_HOURS=12,
        SESSION_IDLE_TIMEOUT_MINUTES=60,
        SESSION_ACTIVITY_UPDATE_SECONDS=120,
    )
    def test_no_actualiza_actividad_en_cada_request(self):
        original = self.sesion.ultima_actividad
        self.assertEqual(self._yo().status_code, 200)
        self.sesion.refresh_from_db()
        self.assertEqual(self.sesion.ultima_actividad, original)

    @override_settings(
        SESSION_ABSOLUTE_TIMEOUT_HOURS=12,
        SESSION_IDLE_TIMEOUT_MINUTES=60,
        SESSION_ACTIVITY_UPDATE_SECONDS=120,
    )
    def test_actualiza_actividad_despues_del_intervalo(self):
        antigua = timezone.now() - timezone.timedelta(seconds=121)
        SesionUsuario.objects.filter(pk=self.sesion.pk).update(ultima_actividad=antigua)
        self.assertEqual(self._yo().status_code, 200)
        self.sesion.refresh_from_db()
        self.assertGreater(self.sesion.ultima_actividad, antigua)


class LoginDespuesDeCaducarTests(TestCase):
    def setUp(self):
        cache.clear()
        self.usuario = User.objects.create_user("operario", password="clave-correcta-123")

    def _login(self):
        return self.client.post(
            "/api/usuarios/login/",
            {"username": "operario", "password": "clave-correcta-123"},
            content_type="application/json",
        )

    @override_settings(SESSION_ABSOLUTE_TIMEOUT_HOURS=12, SESSION_IDLE_TIMEOUT_MINUTES=60)
    def test_login_nuevo_cierra_la_sesion_expirada(self):
        self.assertEqual(self._login().status_code, 200)
        SesionUsuario.objects.filter(usuario=self.usuario, fecha_cierre__isnull=True).update(
            ultima_actividad=timezone.now() - timezone.timedelta(minutes=61)
        )
        self.assertEqual(self._login().status_code, 200)
        self.assertEqual(
            SesionUsuario.objects.filter(usuario=self.usuario, fecha_cierre__isnull=True).count(), 1
        )

    def test_la_credencial_devuelta_funciona(self):
        clave = self._login().json()["token"]
        respuesta = self.client.get(
            "/api/usuarios/yo/", HTTP_AUTHORIZATION=f"Token {clave}"
        )
        self.assertEqual(respuesta.status_code, 200)
