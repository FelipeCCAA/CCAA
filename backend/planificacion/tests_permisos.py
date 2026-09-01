from django.contrib.auth.models import User
from django.test import TestCase
from rest_framework.test import APIClient

from usuarios.models import Empresa, PerfilUsuario, Sucursal


class PermisosPlanificacionPorAreaTests(TestCase):
    def setUp(self):
        self.empresa = Empresa.objects.create(rut="PERM-PLAN", nombre="Permisos plan")
        self.sucursal = Sucursal.objects.create(empresa=self.empresa, codigo="P", nombre="Planta")

    def cliente(self, area):
        usuario = User.objects.create_user(f"usuario-{area}", password="x")
        PerfilUsuario.objects.create(usuario=usuario, area=area, empresa=self.empresa, sucursal=self.sucursal)
        cliente = APIClient(); cliente.force_authenticate(usuario)
        return cliente

    def test_calidad_puede_consultar_pero_no_modificar_planificacion(self):
        cliente = self.cliente(PerfilUsuario.Area.CALIDAD)
        self.assertEqual(cliente.get("/api/planificacion/semanas/").status_code, 200)
        self.assertEqual(cliente.post("/api/planificacion/semanas/", {}, format="json").status_code, 403)

    def test_recepcion_no_entra_directamente_a_planificacion_de_produccion(self):
        cliente = self.cliente(PerfilUsuario.Area.RECEPCION)
        self.assertEqual(cliente.get("/api/planificacion/semanas/").status_code, 403)

    def test_secado_puede_operar_planificacion(self):
        cliente = self.cliente(PerfilUsuario.Area.SECADO)
        self.assertNotEqual(cliente.post("/api/planificacion/semanas/", {}, format="json").status_code, 403)
