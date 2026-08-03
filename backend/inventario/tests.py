from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase
from rest_framework.test import APIClient

from maestros.models import Mandante, Producto
from usuarios.models import PerfilUsuario

from .models import ConsumoProducto, Insumo


class InventarioTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user("jefe-secado", password="x")
        PerfilUsuario.objects.create(
            usuario=self.admin,
            nivel=PerfilUsuario.Nivel.ADMIN,
            area=PerfilUsuario.Area.SECADO,
        )
        self.cliente = APIClient()
        self.cliente.force_authenticate(self.admin)
        mandante = Mandante.objects.create(nombre="CCAA")
        self.producto = Producto.objects.create(
            nombre="Leche en polvo", familia="polvo", mandante=mandante
        )
        self.bolsa = Insumo.objects.create(
            codigo="BOLSA-25",
            nombre="Bolsa 25 kg",
            area=PerfilUsuario.Area.SECADO,
            unidad="un",
            contenido_envase=1,
            stock_actual=100,
            demanda_anual=10000,
            costo_por_pedido=50,
            costo_mantencion_unitario=2,
            consumo_diario=40,
            plazo_reposicion_dias=5,
        )
        ConsumoProducto.objects.create(
            producto=self.producto,
            insumo=self.bolsa,
            cantidad_por_kg=Decimal("0.04"),
        )

    def test_eoq_y_punto_reposicion(self):
        self.assertAlmostEqual(float(self.bolsa.eoq), 707.106, places=2)
        self.assertEqual(self.bolsa.punto_reposicion, 200)

    def test_mrp_calcula_bolsas_y_faltante(self):
        respuesta = self.cliente.post(
            "/api/inventario/mrp/",
            {"producto": self.producto.id, "kilos_producir": 1_000_000},
            format="json",
        )
        self.assertEqual(respuesta.status_code, 200)
        material = respuesta.json()["materiales"][0]
        self.assertEqual(Decimal(material["requerido"]), Decimal("40000"))
        self.assertEqual(material["envases_a_pedir"], 39900)

    def test_administrador_de_area_no_ve_insumos_de_otra_area(self):
        Insumo.objects.create(
            codigo="LAB", nombre="Reactivo", area=PerfilUsuario.Area.CALIDAD,
            unidad="L",
        )
        respuesta = self.cliente.get("/api/inventario/insumos/")
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta.json()["count"], 1)
