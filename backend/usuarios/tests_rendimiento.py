"""Regresiones de consultas para usuarios y permisos."""

from types import SimpleNamespace

from django.contrib.auth.models import Permission, User
from django.test import TestCase

from .models import PerfilUsuario
from .serializers import TrabajadorSerializer
from .views import TrabajadorViewSet


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
        for numero in range(5):
            usuario = User.objects.create_user(f"trabajador-perf-{numero}")
            PerfilUsuario.objects.create(
                usuario=usuario, area=PerfilUsuario.Area.BODEGA
            )
            usuario.user_permissions.add(permiso)

        vista = TrabajadorViewSet()
        vista.request = SimpleNamespace(user=actor)
        consulta = vista.get_queryset()

        # Usuarios+perfil en una consulta; permisos industriales en otra.
        with self.assertNumQueries(2):
            datos = TrabajadorSerializer(consulta, many=True).data

        trabajadores = [fila for fila in datos if fila["username"].startswith("trabajador")]
        self.assertEqual(len(trabajadores), 5)
        self.assertTrue(all(
            fila["capacidades"] == ["inventario_transferir"]
            and fila["permisos_asignados"] == ["inventario_transferir"]
            for fila in trabajadores
        ))

