from datetime import date

from django.contrib.auth.models import User
from django.test import TestCase
from rest_framework.test import APIClient

from inventario.models import Insumo
from usuarios.models import Empresa, PerfilUsuario, Rol, Sucursal

from .models import Mandante, Producto, RecetaComponente


class RecetasApiTests(TestCase):
    def setUp(self):
        empresa = Empresa.objects.create(rut="REC-API", nombre="Recetas API")
        sucursal = Sucursal.objects.create(empresa=empresa, codigo="REC", nombre="Planta")
        usuario = User.objects.create_user("calidad-recetas")
        PerfilUsuario.objects.create(
            usuario=usuario, empresa=empresa, sucursal=sucursal,
            rol=Rol.CALIDAD, area=PerfilUsuario.Area.CALIDAD,
        )
        mandante = Mandante.objects.create(empresa=empresa, nombre="CCAA recetas")
        self.producto = Producto.objects.create(
            mandante=mandante, nombre="Polvo 25 kg", unidad_base="kg",
        )
        self.insumo_proceso = Insumo.objects.create(
            empresa=empresa, codigo="ADITIVO", nombre="Aditivo", unidad="kg",
        )
        self.insumo_envase = Insumo.objects.create(
            empresa=empresa, codigo="SACO", nombre="Saco 25 kg", unidad="un",
            categoria=Insumo.Categoria.EMPAQUE,
        )
        self.cliente = APIClient()
        self.cliente.force_authenticate(usuario)

    def test_crea_version_con_consumos_separados_y_la_lista(self):
        respuesta = self.cliente.post("/api/maestros/recetas/", {
            "producto": self.producto.pk,
            "version": 1,
            "cantidad_base": "25",
            "vigente_desde": date(2026, 9, 3).isoformat(),
            "fuente": "Ficha aprobada QA-01",
            "componentes": [
                {
                    "insumo": self.insumo_proceso.pk, "fase": "proceso",
                    "cantidad": "0.1000", "unidad": "kg", "merma": "0",
                },
                {
                    "insumo": self.insumo_envase.pk, "fase": "envasado",
                    "cantidad": "1", "unidad": "un", "merma": "0",
                },
            ],
        }, format="json")

        self.assertEqual(respuesta.status_code, 201, respuesta.data)
        self.assertEqual(
            set(RecetaComponente.objects.values_list("fase", flat=True)),
            {"proceso", "envasado"},
        )
        listado = self.cliente.get("/api/maestros/recetas/")
        self.assertEqual(listado.status_code, 200)
        self.assertEqual(len(listado.data["results"][0]["componentes"]), 2)

