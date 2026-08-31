from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from calidad.models import Liberacion
from maestros.models import Equipo, Mandante, Producto
from produccion.models import Lote, PalletProducto, RegistroEnvase
from usuarios.models import Empresa, PerfilUsuario, Rol, Sucursal

from .models import (
    Bodega, ClienteDespacho, Despacho, DetalleDespacho,
    ExistenciaProductoTerminado, Insumo, LoteInventario,
    MovimientoProductoTerminado, Ubicacion,
)
from .servicios import autorizar_despacho, ejecutar_despacho, ingresar_pallet


class FlujoProductoTerminadoTests(TestCase):
    def setUp(self):
        self.empresa = Empresa.objects.create(rut="PT-1", nombre="Empresa PT")
        self.planta = Sucursal.objects.create(empresa=self.empresa, codigo="PT", nombre="Planta PT")
        self.usuario = User.objects.create_user("bodega-pt")
        PerfilUsuario.objects.create(
            usuario=self.usuario, empresa=self.empresa, sucursal=self.planta,
            rol=Rol.OPERARIO, area=PerfilUsuario.Area.BODEGA,
        )
        mandante = Mandante.objects.create(empresa=self.empresa, nombre="Mandante PT", codigo_cliente="pt")
        producto = Producto.objects.create(mandante=mandante, nombre="Polvo PT", unidad_base="kg")
        self.lote = Lote.objects.create(
            sucursal=self.planta, codigo_lote="L-PT", producto=producto,
            fecha=date(2026, 8, 17), estado=Lote.Estado.PRODUCIDO, kg_producidos=Decimal("500"),
        )
        equipo = Equipo.objects.create(
            sucursal=self.planta, codigo="ENV-PT", nombre="Envasadora PT", tipo=Equipo.Tipo.ENVASADORA,
        )
        envase = RegistroEnvase.objects.create(
            lote=self.lote, equipo=equipo, formato_kg=25, unidades=20, kg_envasados=500,
            operador=self.usuario, inicio=timezone.now() - timedelta(hours=1), termino=timezone.now(),
        )
        self.pallet = PalletProducto.objects.create(
            envase=envase, codigo="PAL-PT", unidades=20, kg_neto=500,
        )
        bodega = Bodega.objects.create(sucursal=self.planta, codigo="BPT", nombre="Bodega PT")
        self.ubicacion = Ubicacion.objects.create(bodega=bodega, codigo="A-01")
        self.cliente = ClienteDespacho.objects.create(empresa=self.empresa, codigo="CLI", nombre="Cliente PT")
        self.api = APIClient()
        self.api.force_authenticate(self.usuario)

    def liberar(self):
        Liberacion.objects.create(lote=self.lote, estado=Liberacion.Estado.LIBERADO)
        self.pallet.estado = PalletProducto.Estado.LIBERADO
        self.pallet.save(update_fields=["estado"])

    def test_no_ingresa_sin_liberacion_de_calidad(self):
        with self.assertRaises(ValidationError):
            ingresar_pallet(self.pallet, self.ubicacion, self.usuario)
        self.assertFalse(ExistenciaProductoTerminado.objects.exists())

    def test_ingreso_crea_existencia_y_movimiento(self):
        cuarentena = Ubicacion.objects.create(
            bodega=self.ubicacion.bodega, codigo="PT-CUAR", tipo=Ubicacion.Tipo.CUARENTENA,
        )
        existencia_cuarentena = ExistenciaProductoTerminado.objects.create(
            pallet=self.pallet, ubicacion=cuarentena,
        )
        self.liberar()
        existencia = ingresar_pallet(self.pallet, self.ubicacion, self.usuario)
        self.pallet.refresh_from_db()
        self.assertTrue(existencia.activo)
        self.assertEqual(existencia.pk, existencia_cuarentena.pk)
        self.assertEqual(existencia.ubicacion, self.ubicacion)
        self.assertEqual(self.pallet.estado, PalletProducto.Estado.EN_INVENTARIO)
        self.assertEqual(MovimientoProductoTerminado.objects.count(), 1)

    def test_ingreso_manual_asigna_sucursal_del_destino(self):
        material = Insumo.objects.create(
            empresa=self.empresa, codigo="ENV-TEST", nombre="Envase test",
            categoria=Insumo.Categoria.EMPAQUE, area=PerfilUsuario.Area.BODEGA,
            unidad=Insumo.Unidad.UN, requiere_calidad=False,
        )

        respuesta = self.api.post("/api/inventario/movimientos/ingresar-material/", {
            "insumo": material.pk, "codigo_lote": "PROV-ENV-1",
            "ubicacion": self.ubicacion.pk, "cantidad": "20",
        }, format="json")

        self.assertEqual(respuesta.status_code, 201)
        lote = LoteInventario.objects.get(insumo=material, codigo="PROV-ENV-1")
        self.assertEqual(lote.sucursal, self.planta)

        resumen = self.api.get("/api/inventario/estado-operacional/")
        self.assertEqual(resumen.status_code, 200)
        stock_material = next(
            item for item in resumen.data["materiales"] if item["insumo_id"] == material.pk
        )
        self.assertEqual(stock_material["fisico"], Decimal("20"))
        self.assertEqual(stock_material["disponible"], Decimal("20"))
        self.assertEqual(stock_material["reservado"], Decimal("0"))

    def test_despacho_revalida_calidad_y_no_duplica_salida(self):
        self.liberar()
        ingresar_pallet(self.pallet, self.ubicacion, self.usuario)
        despacho = Despacho.objects.create(
            sucursal=self.planta, numero="D-1", cliente=self.cliente, creado_por=self.usuario,
        )
        DetalleDespacho.objects.create(despacho=despacho, pallet=self.pallet)
        autorizar_despacho(despacho, self.usuario)
        ejecutar_despacho(despacho, self.usuario)
        ejecutar_despacho(despacho, self.usuario)
        self.assertEqual(
            MovimientoProductoTerminado.objects.filter(tipo="despacho").count(), 1
        )
        self.assertFalse(ExistenciaProductoTerminado.objects.get(pallet=self.pallet).activo)

    def test_bloqueo_posterior_impide_ejecutar_un_despacho_autorizado(self):
        self.liberar()
        ingresar_pallet(self.pallet, self.ubicacion, self.usuario)
        despacho = Despacho.objects.create(
            sucursal=self.planta, numero="D-2", cliente=self.cliente, creado_por=self.usuario,
        )
        DetalleDespacho.objects.create(despacho=despacho, pallet=self.pallet)
        autorizar_despacho(despacho, self.usuario)
        liberacion = self.lote.liberacion
        liberacion.estado = Liberacion.Estado.RECHAZADO
        liberacion.save(update_fields=["estado"])
        with self.assertRaises(ValidationError):
            ejecutar_despacho(despacho, self.usuario)
        self.assertTrue(ExistenciaProductoTerminado.objects.get(pallet=self.pallet).activo)

    def test_resumen_operacional_refleja_stock_sin_duplicarlo(self):
        self.liberar()
        ingresar_pallet(self.pallet, self.ubicacion, self.usuario)

        respuesta = self.api.get("/api/inventario/estado-operacional/")

        self.assertEqual(respuesta.status_code, 200)
        stock = respuesta.data["stock"]
        self.assertEqual(Decimal(str(stock["fisico_kg"])), Decimal("500"))
        self.assertEqual(Decimal(str(stock["disponible_kg"])), Decimal("500"))
        self.assertEqual(Decimal(str(stock["cuarentena_kg"])), Decimal("0"))
        self.assertEqual(stock["pallets"], 1)
        producto = respuesta.data["productos"][0]
        self.assertEqual(producto["producto_nombre"], "Polvo PT")
        self.assertEqual(producto["pallets_bodega"], 1)
        self.assertEqual(Decimal(str(producto["kg_bodega"])), Decimal("500"))
