from django.contrib.auth.models import Permission, User
from django.test import TestCase
from rest_framework.test import APIClient

from .models import Empresa, PerfilUsuario, Sucursal


class PermisosIndustrialesTests(TestCase):
    def setUp(self):
        self.empresa = Empresa.objects.create(rut="PERMISOS", nombre="Permisos")
        self.sucursal = Sucursal.objects.create(
            empresa=self.empresa, codigo="P1", nombre="Planta 1"
        )
        self.jefe = self._usuario("jefe", PerfilUsuario.Area.SECADO, True)
        self.operador = self._usuario("operador", PerfilUsuario.Area.SECADO)
        self.calidad = self._usuario("calidad", PerfilUsuario.Area.CALIDAD)
        self.cliente = APIClient()
        self.cliente.force_authenticate(self.jefe)

    def _usuario(self, nombre, area, administrador=False):
        usuario = User.objects.create_user(nombre, password="Clave-segura-2026!")
        PerfilUsuario.objects.create(
            usuario=usuario,
            area=area,
            nivel=(
                PerfilUsuario.Nivel.ADMIN
                if administrador
                else PerfilUsuario.Nivel.TRABAJADOR
            ),
            empresa=self.empresa,
            sucursal=self.sucursal,
            alcance=PerfilUsuario.Alcance.SUCURSAL,
        )
        return usuario

    def test_jefe_solo_ve_permisos_delegables_de_su_area(self):
        datos = self.cliente.get(
            "/api/usuarios/trabajadores/permisos-disponibles/"
        ).json()
        codigos = {fila["codigo"] for fila in datos}

        self.assertIn("secado_proceso_iniciar", codigos)
        self.assertNotIn("calidad_lote_liberar", codigos)
        self.assertNotIn("despacho_autorizar", codigos)

    def test_jefe_asigna_permiso_de_su_area(self):
        respuesta = self.cliente.patch(
            f"/api/usuarios/trabajadores/{self.operador.id}/",
            {"permisos": ["secado_proceso_iniciar"]},
            format="json",
        )
        self.operador.refresh_from_db()

        self.assertEqual(respuesta.status_code, 200)
        self.assertTrue(self.operador.has_perm("usuarios.secado_proceso_iniciar"))
        self.assertEqual(respuesta.json()["permisos_asignados"], ["secado_proceso_iniciar"])

    def test_jefe_no_asigna_calidad_ni_despacho(self):
        for permiso in ("calidad_lote_liberar", "despacho_autorizar"):
            with self.subTest(permiso=permiso):
                respuesta = self.cliente.patch(
                    f"/api/usuarios/trabajadores/{self.operador.id}/",
                    {"permisos": [permiso]},
                    format="json",
                )
                self.assertEqual(respuesta.status_code, 400)

    def test_jefe_no_administra_usuario_de_otra_area(self):
        respuesta = self.cliente.patch(
            f"/api/usuarios/trabajadores/{self.calidad.id}/",
            {"permisos": ["secado_proceso_iniciar"]},
            format="json",
        )
        self.assertEqual(respuesta.status_code, 404)

    def test_superusuario_puede_delegar_permiso_global_sin_crear_superuser(self):
        root = User.objects.create_superuser("root", password="x")
        self.cliente.force_authenticate(root)
        respuesta = self.cliente.patch(
            f"/api/usuarios/trabajadores/{self.operador.id}/",
            {"permisos": ["despacho_autorizar"]},
            format="json",
        )
        self.operador.refresh_from_db()

        self.assertEqual(respuesta.status_code, 200)
        self.assertFalse(self.operador.is_superuser)
        self.assertTrue(self.operador.has_perm("usuarios.despacho_autorizar"))
        self.assertTrue(Permission.objects.filter(codename="despacho_autorizar").exists())
