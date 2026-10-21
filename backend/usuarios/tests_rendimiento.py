"""Regresiones de consultas para usuarios y permisos."""

from types import SimpleNamespace

from django.contrib.auth.models import Group, Permission, User
from django.test import TestCase

from .models import PerfilUsuario, SesionUsuario
from .serializers import SesionUsuarioSerializer, TrabajadorSerializer
from .views import SesionUsuarioViewSet, TrabajadorViewSet


class RendimientoTrabajadoresTests(TestCase):
    def test_permisos_no_consultan_por_cada_trabajador(self):
        actor = User.objects.create_superuser(
            "admin-perf", "admin-perf@example.com", "x"
        )
        permiso = Permission.objects.get(
            content_type__app_label="usuarios",
            content_type__model="perfilusuario",
            codename="inventario_transferir",
        )
        permiso_grupo = Permission.objects.get(
            content_type__app_label="usuarios",
            content_type__model="perfilusuario",
            codename="inventario_ajustar",
        )
        grupo = Group.objects.create(name="bodega-perf")
        grupo.permissions.add(permiso_grupo)
        for numero in range(5):
            usuario = User.objects.create_user(f"trabajador-perf-{numero}")
            PerfilUsuario.objects.create(
                usuario=usuario, area=PerfilUsuario.Area.BODEGA
            )
            usuario.user_permissions.add(permiso)
            usuario.groups.add(grupo)

        vista = TrabajadorViewSet()
        vista.request = SimpleNamespace(user=actor)
        consulta = vista.get_queryset()

        # Usuarios, permisos directos, grupos y permisos del grupo: 4 consultas
        # para todos los trabajadores, sin una adicional por cada persona.
        with self.assertNumQueries(4):
            datos = TrabajadorSerializer(consulta, many=True).data

        trabajadores = [fila for fila in datos if fila["username"].startswith("trabajador")]
        self.assertEqual(len(trabajadores), 5)
        self.assertTrue(all(
            fila["capacidades"] == ["inventario_ajustar", "inventario_transferir"]
            and fila["permisos_asignados"] == ["inventario_transferir"]
            for fila in trabajadores
        ))

    def test_sesiones_precargan_permisos_de_grupo_sin_consulta_por_usuario(self):
        actor = User.objects.create_superuser("admin-sesiones-perf", password="x")
        permiso = Permission.objects.get(
            content_type__app_label="usuarios",
            content_type__model="perfilusuario",
            codename="inventario_ajustar",
        )
        grupo = Group.objects.create(name="sesiones-bodega-perf")
        grupo.permissions.add(permiso)
        for numero in range(5):
            usuario = User.objects.create_user(f"sesion-perf-{numero}")
            PerfilUsuario.objects.create(usuario=usuario, area=PerfilUsuario.Area.BODEGA)
            usuario.groups.add(grupo)
            SesionUsuario.objects.create(usuario=usuario, token_hash=f"{numero + 1:064x}")

        vista = SesionUsuarioViewSet()
        vista.request = SimpleNamespace(user=actor)
        with self.assertNumQueries(4):
            datos = SesionUsuarioSerializer(vista.get_queryset(), many=True).data

        self.assertEqual(len(datos), 5)
        self.assertTrue(all(
            fila["usuario"]["capacidades"] == ["inventario_ajustar"]
            for fila in datos
        ))

