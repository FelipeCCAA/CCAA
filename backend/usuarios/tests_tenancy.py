from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.test import TestCase
from rest_framework.test import APIClient

from .models import Empresa, PerfilUsuario, Sucursal
from .tenancy import scope_de


class TenancyUsuariosTests(TestCase):
    def setUp(self):
        self.empresa_a = Empresa.objects.create(rut="A-1", nombre="Empresa A")
        self.a1 = Sucursal.objects.create(
            empresa=self.empresa_a, codigo="A1", nombre="Sucursal A1"
        )
        self.a2 = Sucursal.objects.create(
            empresa=self.empresa_a, codigo="A2", nombre="Sucursal A2"
        )
        self.empresa_b = Empresa.objects.create(rut="B-1", nombre="Empresa B")
        self.b1 = Sucursal.objects.create(
            empresa=self.empresa_b, codigo="B1", nombre="Sucursal B1"
        )

    def usuario_admin(self, nombre, empresa, sucursal=None, alcance="sucursal"):
        usuario = User.objects.create_user(nombre, password="Clave-inicial-2026!")
        PerfilUsuario.objects.create(
            usuario=usuario,
            area=PerfilUsuario.Area.ADMINISTRACION,
            nivel=PerfilUsuario.Nivel.ADMIN,
            empresa=empresa,
            sucursal=sucursal,
            alcance=alcance,
        )
        return usuario

    def test_scope_sucursal_y_empresa_son_distintos(self):
        admin_a1 = self.usuario_admin("admin-a1", self.empresa_a, self.a1)
        admin_empresa = self.usuario_admin(
            "admin-a", self.empresa_a, None, PerfilUsuario.Alcance.EMPRESA
        )

        self.assertTrue(scope_de(admin_a1).permite_sucursal(self.a1.id, self.empresa_a.id))
        self.assertFalse(scope_de(admin_a1).permite_sucursal(self.a2.id, self.empresa_a.id))
        self.assertTrue(scope_de(admin_empresa).permite_sucursal(self.a2.id, self.empresa_a.id))
        self.assertFalse(scope_de(admin_empresa).permite_sucursal(self.b1.id, self.empresa_b.id))

    def test_sucursal_de_otra_empresa_no_se_guarda(self):
        usuario = User.objects.create_user("invalido")
        with self.assertRaises(ValidationError):
            PerfilUsuario.objects.create(
                usuario=usuario,
                empresa=self.empresa_a,
                sucursal=self.b1,
                alcance=PerfilUsuario.Alcance.SUCURSAL,
            )

    def test_get_y_patch_de_usuario_de_otra_sucursal_responden_404(self):
        admin_a1 = self.usuario_admin("admin-a1", self.empresa_a, self.a1)
        objetivo = self.usuario_admin("admin-a2", self.empresa_a, self.a2)
        cliente = APIClient()
        cliente.force_authenticate(admin_a1)

        self.assertEqual(
            cliente.get(f"/api/usuarios/trabajadores/{objetivo.id}/").status_code,
            404,
        )
        self.assertEqual(
            cliente.patch(
                f"/api/usuarios/trabajadores/{objetivo.id}/",
                {"cargo": "No autorizado"},
                format="json",
            ).status_code,
            404,
        )

    def test_post_rechaza_sucursal_de_otro_tenant(self):
        admin_a1 = self.usuario_admin("admin-a1", self.empresa_a, self.a1)
        cliente = APIClient()
        cliente.force_authenticate(admin_a1)
        respuesta = cliente.post(
            "/api/usuarios/trabajadores/",
            {
                "username": "intruso",
                "password": "Clave-inicial-2026!",
                "area": PerfilUsuario.Area.SECADO,
                "nivel": PerfilUsuario.Nivel.TRABAJADOR,
                "empresa": self.empresa_b.id,
                "sucursal": self.b1.id,
            },
            format="json",
        )

        self.assertEqual(respuesta.status_code, 400)
        self.assertFalse(User.objects.filter(username="intruso").exists())

    def test_admin_empresa_ve_sus_sucursales_pero_no_otra_empresa(self):
        admin_empresa = self.usuario_admin(
            "admin-a", self.empresa_a, None, PerfilUsuario.Alcance.EMPRESA
        )
        propio = self.usuario_admin("propio-a2", self.empresa_a, self.a2)
        ajeno = self.usuario_admin("ajeno-b1", self.empresa_b, self.b1)
        cliente = APIClient()
        cliente.force_authenticate(admin_empresa)

        ids = {fila["id"] for fila in cliente.get("/api/usuarios/trabajadores/").json()}
        self.assertIn(propio.id, ids)
        self.assertNotIn(ajeno.id, ids)
