from django.contrib.auth.models import User
from django.core import mail
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from .models import Empresa, PerfilUsuario, Sucursal


class AdministracionPorAreaTests(TestCase):
    def setUp(self):
        self.cliente = APIClient()
        self.empresa = Empresa.objects.create(rut="ADMIN-AREA", nombre="Admin Área")
        self.sucursal = Sucursal.objects.create(
            empresa=self.empresa, codigo="P1", nombre="Planta 1"
        )
        self.admin_secado = self._usuario(
            "jefe-secado", PerfilUsuario.Area.SECADO, PerfilUsuario.Nivel.ADMIN
        )
        self.trabajador_secado = self._usuario(
            "operador-secado", PerfilUsuario.Area.SECADO
        )
        self.trabajador_calidad = self._usuario(
            "analista-calidad", PerfilUsuario.Area.CALIDAD
        )

    def _usuario(self, username, area, nivel=PerfilUsuario.Nivel.TRABAJADOR, email=""):
        usuario = User.objects.create_user(
            username=username,
            password="Clave-segura-2026!",
            email=email,
        )
        PerfilUsuario.objects.create(
            usuario=usuario,
            area=area,
            nivel=nivel,
            empresa=self.empresa,
            sucursal=self.sucursal,
            alcance=PerfilUsuario.Alcance.SUCURSAL,
        )
        usuario.refresh_from_db()
        return usuario

    def test_el_nivel_admin_sincroniza_is_staff(self):
        self.assertTrue(self.admin_secado.is_staff)
        self.assertTrue(self.admin_secado.perfil.es_admin_de_area)

    def test_el_permiso_exige_is_staff_y_perfil_admin(self):
        User.objects.filter(pk=self.admin_secado.pk).update(is_staff=False)
        self.admin_secado.refresh_from_db()
        self.cliente.force_authenticate(self.admin_secado)

        respuesta = self.cliente.get("/api/usuarios/trabajadores/")

        self.assertEqual(respuesta.status_code, 403)

    def test_admin_de_area_solo_lista_su_area(self):
        self.cliente.force_authenticate(self.admin_secado)

        usernames = {
            usuario["username"]
            for usuario in self.cliente.get("/api/usuarios/trabajadores/").json()
        }

        self.assertIn(self.trabajador_secado.username, usernames)
        self.assertNotIn(self.trabajador_calidad.username, usernames)

    def test_superusuario_lista_todas_las_areas(self):
        superusuario = User.objects.create_superuser("root", password="x")
        self.cliente.force_authenticate(superusuario)

        usernames = {
            usuario["username"]
            for usuario in self.cliente.get("/api/usuarios/trabajadores/").json()
        }

        self.assertIn(self.trabajador_secado.username, usernames)
        self.assertIn(self.trabajador_calidad.username, usernames)

    def test_creacion_fuerza_area_y_nivel_de_trabajador(self):
        self.cliente.force_authenticate(self.admin_secado)

        respuesta = self.cliente.post(
            "/api/usuarios/trabajadores/",
            {
                "username": "nuevo-operador",
                "password": "Clave-inicial-2026!",
                "area": PerfilUsuario.Area.CALIDAD,
                "nivel": PerfilUsuario.Nivel.ADMIN,
            },
            format="json",
        )

        self.assertEqual(respuesta.status_code, 201)
        perfil = User.objects.get(username="nuevo-operador").perfil
        self.assertEqual(perfil.area, PerfilUsuario.Area.SECADO)
        self.assertEqual(perfil.nivel, PerfilUsuario.Nivel.TRABAJADOR)
        self.assertFalse(perfil.usuario.is_staff)

    def test_un_trabajador_de_otra_area_no_es_accesible(self):
        self.cliente.force_authenticate(self.admin_secado)

        respuesta = self.cliente.patch(
            f"/api/usuarios/trabajadores/{self.trabajador_calidad.pk}/",
            {"activo": False},
            format="json",
        )

        self.assertEqual(respuesta.status_code, 404)
        self.trabajador_calidad.refresh_from_db()
        self.assertTrue(self.trabajador_calidad.is_active)

    @override_settings(
        EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
        PASSWORD_RESET_FRONTEND_URL="https://app.example/restablecer-contrasena",
        DEFAULT_FROM_EMAIL="no-responder@example.com",
    )
    def test_admin_envia_restablacimiento_a_trabajador_de_su_area(self):
        self.trabajador_secado.email = "operador@example.com"
        self.trabajador_secado.save(update_fields=["email"])
        self.cliente.force_authenticate(self.admin_secado)

        respuesta = self.cliente.post(
            f"/api/usuarios/trabajadores/{self.trabajador_secado.pk}/restablecer-contrasena/"
        )

        self.assertEqual(respuesta.status_code, 202)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("https://app.example/restablecer-contrasena", mail.outbox[0].body)

    @override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
    def test_no_puede_restablecer_a_un_usuario_de_otra_area(self):
        self.cliente.force_authenticate(self.admin_secado)

        respuesta = self.cliente.post(
            f"/api/usuarios/trabajadores/{self.trabajador_calidad.pk}/restablecer-contrasena/"
        )

        self.assertEqual(respuesta.status_code, 404)
        self.assertEqual(len(mail.outbox), 0)
