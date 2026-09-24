from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth.models import User
from django.utils import timezone

from maestros.models import Equipo, Mandante, Producto
from produccion.models import Lote, PalletProducto, RegistroEnvase
from usuarios.models import Empresa, PerfilUsuario, Sucursal

from .models import Bodega, Existencia, ExistenciaProductoTerminado, Insumo, Ubicacion
from .pruebas_base import EscenarioProductoTerminado
from .servicios import crear_ajuste


class PendientesBodegaTests(EscenarioProductoTerminado):
    def setUp(self):
        super().setUp()
        self.cuarentena = Ubicacion.objects.create(
            bodega=self.ubicacion.bodega, codigo="PT-CUAR", tipo=Ubicacion.Tipo.CUARENTENA,
        )

    def pendientes(self):
        respuesta = self.api.get("/api/inventario/pendientes-bodega/")
        self.assertEqual(respuesta.status_code, 200, respuesta.data)
        return respuesta.data

    def material(self, codigo, *, requiere_calidad=False, stock_minimo=Decimal("0")):
        return Insumo.objects.create(
            empresa=self.empresa, codigo=codigo, nombre=f"Material {codigo}",
            categoria=Insumo.Categoria.EMPAQUE, area=PerfilUsuario.Area.BODEGA,
            unidad=Insumo.Unidad.UN, requiere_calidad=requiere_calidad, stock_minimo=stock_minimo,
        )

    def ingresar(self, insumo, lote, ubicacion, cantidad="20"):
        respuesta = self.api.post("/api/inventario/movimientos/ingresar-material/", {
            "insumo": insumo.pk, "codigo_lote": lote, "ubicacion": ubicacion.pk, "cantidad": cantidad,
        }, format="json")
        self.assertEqual(respuesta.status_code, 201, respuesta.data)

    def test_pallet_liberado_en_cuarentena_espera_ubicacion(self):
        ExistenciaProductoTerminado.objects.create(pallet=self.pallet, ubicacion=self.cuarentena)
        self.assertEqual(self.pendientes()["pallets_por_ubicar"], [])  # aún sin liberar
        self.liberar()
        fila = self.pendientes()["pallets_por_ubicar"][0]
        self.assertEqual(fila["pallet_codigo"], "PAL-PT")
        self.assertEqual(fila["ubicacion_codigo"], "PT-CUAR")
        self.assertEqual(fila["lote_codigo"], "L-PT")

    def test_material_en_cuarentena_aparece_con_su_unidad(self):
        insumo = self.material("CAL-1", requiere_calidad=True)
        self.ingresar(insumo, "PROV-CAL-1", self.cuarentena)
        fila = self.pendientes()["material_en_cuarentena"][0]
        self.assertEqual(fila["lote_codigo"], "PROV-CAL-1")
        self.assertEqual(fila["unidad"], "un")
        self.assertEqual(Decimal(str(fila["cantidad"])), Decimal("20"))
        # Recién ingresado, el lote está pendiente de inspección: no es
        # utilizable todavía y la decisión sigue siendo de Calidad.
        self.assertEqual(fila["estado_calidad"], "pendiente")
        self.assertFalse(fila["utilizable"])

    def test_bajo_minimo_cuando_el_disponible_no_alcanza(self):
        corto = self.material("CORTO", stock_minimo=Decimal("50"))
        holgado = self.material("HOLGADO", stock_minimo=Decimal("5"))
        sin_minimo = self.material("SIN-MIN")
        for insumo in (corto, holgado, sin_minimo):
            self.ingresar(insumo, f"L-{insumo.codigo}", self.ubicacion)
        codigos = [fila["codigo"] for fila in self.pendientes()["bajo_minimo"]]
        self.assertEqual(codigos, ["CORTO"])

    def test_ajuste_pendiente_trae_quien_lo_pidio(self):
        insumo = self.material("AJ-1")
        self.ingresar(insumo, "L-AJ-1", self.ubicacion)
        existencia = Existencia.objects.get(lote__codigo="L-AJ-1")
        crear_ajuste(existencia=existencia, tipo="negativo", cantidad="2", motivo="Conteo", solicitante=self.usuario)
        datos = self.pendientes()
        fila = datos["ajustes_pendientes"][0]
        self.assertEqual(fila["solicitante_id"], self.usuario.pk)
        self.assertEqual(fila["unidad"], "un")
        self.assertEqual(fila["existencia_id"], existencia.pk)
        self.assertEqual(datos["total"], 1)

    def test_no_muestra_lo_de_otra_empresa(self):
        otra = Empresa.objects.create(rut="PT-2", nombre="Otra")
        planta = Sucursal.objects.create(empresa=otra, codigo="PT2", nombre="Planta 2")
        mandante = Mandante.objects.create(empresa=otra, nombre="Mandante 2", codigo_cliente="p2")
        producto = Producto.objects.create(mandante=mandante, nombre="Polvo 2", unidad_base="kg")
        lote = Lote.objects.create(
            sucursal=planta, codigo_lote="L-OTRA", producto=producto, fecha=date(2026, 8, 17),
            estado=Lote.Estado.PRODUCIDO, kg_producidos=Decimal("500"),
        )
        equipo = Equipo.objects.create(sucursal=planta, codigo="ENV-2", nombre="Env 2", tipo=Equipo.Tipo.ENVASADORA)
        operador = User.objects.create_user("otra-empresa")
        envase = RegistroEnvase.objects.create(
            lote=lote, equipo=equipo, formato_kg=25, unidades=20, kg_envasados=500,
            operador=operador, inicio=timezone.now() - timedelta(hours=1), termino=timezone.now(),
        )
        pallet = PalletProducto.objects.create(
            envase=envase, codigo="PAL-OTRA", unidades=20, kg_neto=500, estado=PalletProducto.Estado.LIBERADO,
        )
        bodega = Bodega.objects.create(sucursal=planta, codigo="B2", nombre="Bodega 2")
        cuarentena = Ubicacion.objects.create(bodega=bodega, codigo="Q-2", tipo=Ubicacion.Tipo.CUARENTENA)
        ExistenciaProductoTerminado.objects.create(pallet=pallet, ubicacion=cuarentena)
        codigos = [fila["pallet_codigo"] for fila in self.pendientes()["pallets_por_ubicar"]]
        self.assertNotIn("PAL-OTRA", codigos)
