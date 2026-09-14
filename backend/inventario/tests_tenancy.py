from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase
from rest_framework.test import APIClient

from usuarios.models import Empresa, PerfilUsuario, Rol, Sucursal

from .models import Alerta, Bodega, Existencia, Insumo, LoteInventario, Ubicacion
from .servicios import actualizar_alertas_inventario


class CompatibilidadHistoricaInventarioTests(TestCase):
    def setUp(self):
        self.empresa = Empresa.objects.create(rut="INV-A", nombre="Empresa A")
        self.a1 = Sucursal.objects.create(empresa=self.empresa, codigo="A1", nombre="A1")
        self.a2 = Sucursal.objects.create(empresa=self.empresa, codigo="A2", nombre="A2")
        self.bodega_a1 = Bodega.objects.create(sucursal=self.a1, codigo="B1", nombre="Bodega A1")
        self.bodega_a2 = Bodega.objects.create(sucursal=self.a2, codigo="B2", nombre="Bodega A2")
        usuario = User.objects.create_user("bodega-a1", password="x")
        PerfilUsuario.objects.create(
            usuario=usuario, rol=Rol.LECTURA, area=PerfilUsuario.Area.BODEGA,
            empresa=self.empresa, sucursal=self.a1,
            alcance=PerfilUsuario.Alcance.SUCURSAL,
        )
        self.cliente = APIClient()
        self.cliente.force_authenticate(usuario)

    def test_lista_y_detalle_no_usan_sucursal_como_aislamiento(self):
        respuesta = self.cliente.get("/api/inventario/bodegas/")
        ids = {fila["id"] for fila in respuesta.data["results"]}
        self.assertEqual(ids, {self.bodega_a1.id, self.bodega_a2.id})
        self.assertEqual(
            self.cliente.get(f"/api/inventario/bodegas/{self.bodega_a2.id}/").status_code,
            200,
        )

    def test_patch_no_se_bloquea_por_sucursal_historica(self):
        respuesta = self.cliente.patch(
            f"/api/inventario/bodegas/{self.bodega_a2.id}/",
            {"nombre": "Bodega actualizada"}, format="json",
        )
        self.assertEqual(respuesta.status_code, 200)

    def test_create_no_toma_sucursal_del_perfil_como_scope(self):
        respuesta = self.cliente.post(
            "/api/inventario/bodegas/",
            {"codigo": "N", "nombre": "Nueva", "sucursal": self.a2.id},
            format="json",
        )
        self.assertEqual(respuesta.status_code, 201)
        self.assertNotEqual(Bodega.objects.get(codigo="N").sucursal_id, self.a2.id)

    def test_crea_ubicacion_sin_restringir_sucursal_historica(self):
        respuesta = self.cliente.post(
            "/api/inventario/ubicaciones/",
            {"bodega": self.bodega_a2.id, "codigo": "X"}, format="json",
        )
        self.assertEqual(respuesta.status_code, 201)
        self.assertTrue(Ubicacion.objects.filter(codigo="X").exists())

    def test_alerta_de_stock_suma_todas_las_ubicaciones_operacionales(self):
        ubicacion_a1 = Ubicacion.objects.create(
            bodega=self.bodega_a1, codigo="DISP-1", tipo=Ubicacion.Tipo.DISPONIBLE
        )
        ubicacion_a2 = Ubicacion.objects.create(
            bodega=self.bodega_a2, codigo="DISP-2", tipo=Ubicacion.Tipo.DISPONIBLE
        )
        insumo = Insumo.objects.create(
            empresa=self.empresa,
            codigo="ENV-GLOBAL",
            nombre="Envase operacional",
            categoria=Insumo.Categoria.EMPAQUE,
            area=PerfilUsuario.Area.ENVASE,
            unidad=Insumo.Unidad.UN,
            stock_minimo=Decimal("100"),
        )
        for indice, (sucursal, ubicacion) in enumerate(
            ((self.a1, ubicacion_a1), (self.a2, ubicacion_a2)), start=1
        ):
            lote = LoteInventario.objects.create(
                sucursal=sucursal,
                insumo=insumo,
                codigo=f"LOTE-{indice}",
                estado_calidad=LoteInventario.EstadoCalidad.NO_REQUIERE,
            )
            Existencia.objects.create(
                lote=lote, ubicacion=ubicacion, cantidad_fisica=Decimal("60")
            )

        actualizar_alertas_inventario()

        self.assertFalse(
            Alerta.objects.filter(insumo=insumo, tipo="stock_minimo", activa=True).exists()
        )
