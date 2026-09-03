from django.contrib.auth.models import User
from django.test import TestCase
from rest_framework.test import APIClient

from usuarios.models import Empresa, PerfilUsuario, Sucursal

from .models import Equipo, Mandante, Producto


class TenancyMaestrosTests(TestCase):
    def setUp(self):
        self.empresa_a = Empresa.objects.create(rut="MA-A", nombre="Empresa A")
        self.a1 = Sucursal.objects.create(
            empresa=self.empresa_a, codigo="A1", nombre="A1"
        )
        self.a2 = Sucursal.objects.create(
            empresa=self.empresa_a, codigo="A2", nombre="A2"
        )
        self.empresa_b = Empresa.objects.create(rut="MA-B", nombre="Empresa B")
        self.b1 = Sucursal.objects.create(
            empresa=self.empresa_b, codigo="B1", nombre="B1"
        )

        self.mandante_a = Mandante.objects.create(
            empresa=self.empresa_a, nombre="Cliente A"
        )
        self.mandante_b = Mandante.objects.create(
            empresa=self.empresa_b, nombre="Cliente B"
        )
        self.producto_b = Producto.objects.create(
            nombre="Producto B",
            familia=Producto.Familia.POLVO,
            mandante=self.mandante_b,
        )
        self.equipo_a1 = Equipo.objects.create(
            sucursal=self.a1, codigo="EQ", nombre="Equipo A1", tipo=Equipo.Tipo.OTRO
        )
        self.equipo_a2 = Equipo.objects.create(
            sucursal=self.a2, codigo="EQ", nombre="Equipo A2", tipo=Equipo.Tipo.OTRO
        )

    def admin(self, nombre, empresa, sucursal=None, alcance="sucursal"):
        usuario = User.objects.create_user(nombre, password="x")
        PerfilUsuario.objects.create(
            usuario=usuario,
            area=PerfilUsuario.Area.ADMINISTRACION,
            nivel=PerfilUsuario.Nivel.ADMIN,
            empresa=empresa,
            sucursal=sucursal,
            alcance=alcance,
        )
        cliente = APIClient()
        cliente.force_authenticate(usuario)
        return cliente

    def test_equipos_usan_codigo_local_y_no_se_filtran_entre_sucursales(self):
        cliente = self.admin("admin-a1", self.empresa_a, self.a1)
        ids = {fila["id"] for fila in cliente.get("/api/maestros/equipos/").json()["results"]}
        self.assertIn(self.equipo_a1.id, ids)
        self.assertNotIn(self.equipo_a2.id, ids)

    def test_get_y_patch_de_equipo_ajeno_responden_404(self):
        cliente = self.admin("admin-a1", self.empresa_a, self.a1)
        ruta = f"/api/maestros/equipos/{self.equipo_a2.id}/"
        self.assertEqual(cliente.get(ruta).status_code, 404)
        self.assertEqual(
            cliente.patch(ruta, {"nombre": "Intrusión"}, format="json").status_code,
            404,
        )

    def test_post_no_acepta_mandante_de_otra_empresa(self):
        cliente = self.admin("admin-a1", self.empresa_a, self.a1)
        respuesta = cliente.post(
            "/api/maestros/productos/",
            {
                "nombre": "Producto cruzado",
                "familia": Producto.Familia.POLVO,
                "mandante": self.mandante_b.id,
            },
            format="json",
        )
        self.assertEqual(respuesta.status_code, 400)
        self.assertFalse(Producto.objects.filter(nombre="Producto cruzado").exists())

    def test_la_particion_enviada_por_el_cliente_se_ignora(self):
        cliente = self.admin("admin-a1", self.empresa_a, self.a1)
        respuesta = cliente.post(
            "/api/maestros/equipos/",
            {
                "sucursal": self.a2.id,
                "codigo": "NUEVO",
                "nombre": "No permitido",
                "tipo": Equipo.Tipo.OTRO,
            },
            format="json",
        )
        self.assertEqual(respuesta.status_code, 201, respuesta.data)
        self.assertEqual(Equipo.objects.get(codigo="NUEVO").sucursal_id, self.a1.id)

    def test_api_guarda_reglas_de_consumo_del_equipo(self):
        cliente = self.admin("admin-reglas", self.empresa_a, self.a1)

        respuesta = cliente.post(
            "/api/maestros/equipos/",
            {
                "codigo": "ENV-REGLAS",
                "nombre": "Envasadora reglas",
                "tipo": Equipo.Tipo.ENVASADORA,
                "consume_leche": False,
                "consume_materiales": True,
            },
            format="json",
        )

        self.assertEqual(respuesta.status_code, 201, respuesta.data)
        self.assertTrue(respuesta.data["consume_materiales"])
        self.assertTrue(Equipo.objects.get(codigo="ENV-REGLAS").consume_materiales)

    def test_admin_empresa_usa_la_configuracion_canonica(self):
        cliente = self.admin(
            "admin-empresa", self.empresa_a, None, PerfilUsuario.Alcance.EMPRESA
        )
        respuesta = cliente.post(
            "/api/maestros/equipos/",
            {
                "sucursal": self.a2.id,
                "codigo": "NUEVO",
                "nombre": "Equipo permitido",
                "tipo": Equipo.Tipo.OTRO,
            },
            format="json",
        )
        self.assertEqual(respuesta.status_code, 201)
        self.assertEqual(Equipo.objects.get(codigo="NUEVO").sucursal_id, self.a1.id)

    def test_admin_empresa_ignora_una_particion_ajena(self):
        cliente = self.admin(
            "admin-empresa", self.empresa_a, None, PerfilUsuario.Alcance.EMPRESA
        )
        respuesta = cliente.post(
            "/api/maestros/equipos/",
            {
                "sucursal": self.b1.id,
                "codigo": "CRUZADO",
                "nombre": "Equipo cruzado",
                "tipo": Equipo.Tipo.OTRO,
            },
            format="json",
        )
        self.assertEqual(respuesta.status_code, 201, respuesta.data)
        self.assertEqual(Equipo.objects.get(codigo="CRUZADO").sucursal_id, self.a1.id)
