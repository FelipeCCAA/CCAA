"""Contrato de seguridad de sesión única."""

from concurrent.futures import ThreadPoolExecutor

from django.contrib.auth.models import User
from django.core.cache import cache
from django.db import close_old_connections
from django.test import TestCase, TransactionTestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from .models import EventoSeguridad, PerfilUsuario, SesionUsuario


@override_settings(
    SESSION_IDLE_TIMEOUT_MINUTES=60,
    SESSION_ABSOLUTE_TIMEOUT_HOURS=12,
    SESSION_ACTIVITY_UPDATE_SECONDS=120,
)
class SesionUnicaTests(TestCase):
    password = "clave-correcta-123"

    def setUp(self):
        cache.clear()
        self.usuario = User.objects.create_user("operario-sesion", password=self.password)

    def login(self, password=None, client=None):
        return (client or self.client).post(
            "/api/usuarios/login/",
            {"username": self.usuario.username, "password": password or self.password},
            content_type="application/json",
        )

    def autenticar(self):
        respuesta = self.login()
        self.client.defaults["HTTP_AUTHORIZATION"] = f"Token {respuesta.json()['token']}"
        return respuesta

    def test_primer_login_crea_una_sesion_sin_guardar_el_token(self):
        respuesta = self.login()
        self.assertEqual(respuesta.status_code, 200)
        sesion = SesionUsuario.objects.get(usuario=self.usuario, fecha_cierre__isnull=True)
        self.assertNotEqual(sesion.token_hash, respuesta.json()["token"])
        self.assertNotIn(respuesta.json()["token"], str(sesion.__dict__))

    def test_segundo_login_correcto_es_rechazado(self):
        self.assertEqual(self.login().status_code, 200)
        respuesta = self.login(client=APIClient())
        self.assertEqual(respuesta.status_code, 409)
        self.assertEqual(respuesta.json()["code"], "SESSION_ALREADY_ACTIVE")
        self.assertEqual(SesionUsuario.objects.filter(fecha_cierre__isnull=True).count(), 1)

    def test_password_incorrecto_no_revela_la_sesion(self):
        self.login()
        respuesta = self.login(password="incorrecta", client=APIClient())
        self.assertEqual(respuesta.status_code, 401)
        self.assertNotIn("sesión activa", respuesta.json()["error"].lower())

    def test_logout_revoca_inmediatamente(self):
        acceso = self.autenticar()
        token = acceso.json()["token"]
        self.assertEqual(self.client.post("/api/usuarios/logout/").status_code, 200)
        cliente_antiguo = APIClient()
        cliente_antiguo.credentials(HTTP_AUTHORIZATION=f"Token {token}")
        respuesta = cliente_antiguo.get("/api/usuarios/yo/")
        self.assertEqual(respuesta.status_code, 401)
        self.assertEqual(respuesta.json()["code"], "SESSION_REVOKED")

    def test_cambio_password_revoca_la_sesion(self):
        acceso = self.autenticar()
        respuesta = self.client.post(
            "/api/usuarios/cambiar-password/",
            {
                "password_actual": self.password,
                "nueva_contrasena": "una-clave-nueva-muy-segura-456",
                "confirmar_contrasena": "una-clave-nueva-muy-segura-456",
            },
            format="json",
        )
        self.assertEqual(respuesta.status_code, 200)
        antiguo = APIClient()
        antiguo.credentials(HTTP_AUTHORIZATION=f"Token {acceso.json()['token']}")
        self.assertEqual(antiguo.get("/api/usuarios/yo/").status_code, 401)

    def test_usuario_desactivado_pierde_acceso(self):
        acceso = self.autenticar()
        User.objects.filter(pk=self.usuario.pk).update(is_active=False)
        cliente = APIClient()
        cliente.credentials(HTTP_AUTHORIZATION=f"Token {acceso.json()['token']}")
        respuesta = cliente.get("/api/usuarios/yo/")
        self.assertEqual(respuesta.status_code, 401)
        self.assertEqual(respuesta.json()["code"], "USER_DISABLED")

    def test_sesion_expirada_permite_login_nuevo(self):
        self.login()
        SesionUsuario.objects.filter(usuario=self.usuario).update(
            ultima_actividad=timezone.now() - timezone.timedelta(minutes=61)
        )
        respuesta = self.login(client=APIClient())
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(SesionUsuario.objects.filter(usuario=self.usuario).count(), 2)
        self.assertEqual(
            SesionUsuario.objects.filter(usuario=self.usuario, fecha_cierre__isnull=True).count(), 1
        )

    def test_eventos_no_guardan_password_ni_token(self):
        respuesta = self.login()
        contenido = " ".join(str(v) for v in EventoSeguridad.objects.values().first().values())
        self.assertNotIn(self.password, contenido)
        self.assertNotIn(respuesta.json()["token"], contenido)

    def test_cambio_forzado_limita_la_sesion_hasta_cambiar_password(self):
        PerfilUsuario.objects.create(usuario=self.usuario, debe_cambiar_password=True)
        acceso = self.autenticar()
        bloqueada = self.client.get("/api/maestros/productos/")
        self.assertEqual(bloqueada.status_code, 403)
        self.assertEqual(bloqueada.json()["code"], "PASSWORD_CHANGE_REQUIRED")

        respuesta = self.client.post(
            "/api/usuarios/cambiar-password/",
            {
                "password_actual": self.password,
                "nueva_contrasena": "otra-clave-obligatoria-segura-789",
                "confirmar_contrasena": "otra-clave-obligatoria-segura-789",
            },
            format="json",
        )
        self.assertEqual(respuesta.status_code, 200)
        self.usuario.perfil.refresh_from_db()
        self.assertFalse(self.usuario.perfil.debe_cambiar_password)
        antiguo = APIClient()
        antiguo.credentials(HTTP_AUTHORIZATION=f"Token {acceso.json()['token']}")
        self.assertEqual(antiguo.get("/api/usuarios/yo/").status_code, 401)


class CierreAdministrativoTests(TestCase):
    def setUp(self):
        cache.clear()
        self.usuario = User.objects.create_user("objetivo", password="clave-objetivo-123")
        self.admin = User.objects.create_superuser("supervisor", password="clave-admin-123")
        respuesta = self.client.post(
            "/api/usuarios/login/",
            {"username": "objetivo", "password": "clave-objetivo-123"},
            content_type="application/json",
        )
        self.token = respuesta.json()["token"]
        self.sesion = SesionUsuario.objects.get(usuario=self.usuario, fecha_cierre__isnull=True)

    def test_admin_autorizado_cierra_y_el_equipo_antiguo_recibe_401(self):
        administrador = APIClient()
        administrador.force_authenticate(self.admin)
        respuesta = administrador.post(
            f"/api/usuarios/sesiones/{self.sesion.identificador}/cerrar/", {}, format="json"
        )
        self.assertEqual(respuesta.status_code, 200)
        antiguo = APIClient()
        antiguo.credentials(HTTP_AUTHORIZATION=f"Token {self.token}")
        self.assertEqual(antiguo.get("/api/usuarios/yo/").status_code, 401)
        self.assertTrue(EventoSeguridad.objects.filter(accion="SESION_CERRADA_ADMIN").exists())

    def test_usuario_normal_no_puede_cerrar_sesion_ajena(self):
        atacante = APIClient()
        atacante.force_authenticate(User.objects.create_user("normal"))
        respuesta = atacante.post(
            f"/api/usuarios/sesiones/{self.sesion.identificador}/cerrar/", {}, format="json"
        )
        self.assertEqual(respuesta.status_code, 403)

    def test_staff_sin_permiso_no_puede_cerrar_sesion(self):
        staff = User.objects.create_user("staff", is_staff=True)
        cliente = APIClient()
        cliente.force_authenticate(staff)
        respuesta = cliente.post(
            f"/api/usuarios/sesiones/{self.sesion.identificador}/cerrar/", {}, format="json"
        )
        self.assertEqual(respuesta.status_code, 403)


class LoginConcurrenteTests(TransactionTestCase):
    reset_sequences = True

    def setUp(self):
        cache.clear()
        User.objects.create_user("concurrente", password="clave-concurrente-123")

    @staticmethod
    def _entrar():
        close_old_connections()
        try:
            return APIClient().post(
                "/api/usuarios/login/",
                {"username": "concurrente", "password": "clave-concurrente-123"},
                format="json",
            ).status_code
        finally:
            close_old_connections()

    def test_dos_logins_simultaneos_no_crean_dos_sesiones(self):
        with ThreadPoolExecutor(max_workers=2) as ejecutor:
            codigos = list(ejecutor.map(lambda _: self._entrar(), range(2)))
        self.assertEqual(sorted(codigos), [200, 409])
        self.assertEqual(SesionUsuario.objects.filter(fecha_cierre__isnull=True).count(), 1)
