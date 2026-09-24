from datetime import timedelta

from django.utils import timezone

from usuarios.models import PerfilUsuario

from .models import Despacho, DetalleDespacho, Existencia, Insumo, LoteInventario, MovimientoInventario, Ubicacion
from .pruebas_base import EscenarioProductoTerminado
from .servicios import ingresar_pallet


def filas(respuesta):
    return respuesta.data["results"] if isinstance(respuesta.data, dict) else respuesta.data


class FiltrosInventarioTests(EscenarioProductoTerminado):
    def setUp(self):
        super().setUp()
        self.otra = Ubicacion.objects.create(bodega=self.ubicacion.bodega, codigo="B-02")
        self.saco = self.material("SACO-25", "Saco 25 kg")
        self.etiqueta = self.material("ETQ-1", "Etiqueta frontal")
        self.ingresar(self.saco, "PROV-SACO-1", self.ubicacion)
        self.ingresar(self.etiqueta, "PROV-ETQ-1", self.otra)

    def material(self, codigo, nombre):
        return Insumo.objects.create(
            empresa=self.empresa, codigo=codigo, nombre=nombre,
            categoria=Insumo.Categoria.EMPAQUE, area=PerfilUsuario.Area.BODEGA,
            unidad=Insumo.Unidad.UN, requiere_calidad=False,
        )

    def ingresar(self, insumo, codigo_lote, ubicacion):
        respuesta = self.api.post("/api/inventario/movimientos/ingresar-material/", {
            "insumo": insumo.pk, "codigo_lote": codigo_lote,
            "ubicacion": ubicacion.pk, "cantidad": "20",
        }, format="json")
        self.assertEqual(respuesta.status_code, 201, respuesta.data)

    def nombres(self, ruta):
        respuesta = self.api.get(ruta)
        self.assertEqual(respuesta.status_code, 200, respuesta.data)
        return [fila["insumo_nombre"] for fila in filas(respuesta)]

    # ---- existencias de material

    def test_q_busca_por_nombre_codigo_de_material_y_lote(self):
        self.assertEqual(self.nombres("/api/inventario/existencias/?q=saco"), ["Saco 25 kg"])
        self.assertEqual(self.nombres("/api/inventario/existencias/?q=ETQ-1"), ["Etiqueta frontal"])
        self.assertEqual(self.nombres("/api/inventario/existencias/?q=prov-saco"), ["Saco 25 kg"])

    def test_ubicacion_acota_las_existencias(self):
        self.assertEqual(
            self.nombres(f"/api/inventario/existencias/?ubicacion={self.otra.pk}"), ["Etiqueta frontal"]
        )

    def test_estado_filtra_por_estado_de_calidad_del_lote(self):
        estado = LoteInventario.objects.get(codigo="PROV-SACO-1").estado_calidad
        self.assertEqual(len(self.nombres(f"/api/inventario/existencias/?estado={estado}")), 2)
        self.assertEqual(self.nombres("/api/inventario/existencias/?estado=rechazado"), [])

    def test_con_saldo_esconde_las_existencias_en_cero(self):
        Existencia.objects.filter(lote__codigo="PROV-ETQ-1").update(cantidad_fisica=0)
        self.assertEqual(self.nombres("/api/inventario/existencias/?con_saldo=1"), ["Saco 25 kg"])

    def test_la_existencia_trae_su_unidad(self):
        fila = filas(self.api.get("/api/inventario/existencias/?q=saco"))[0]
        self.assertEqual(fila["unidad"], "un")
        self.assertEqual(fila["insumo_codigo"], "SACO-25")
        self.assertEqual(fila["bodega_nombre"], "Bodega PT")
        # Material sin Calidad: el lote nace "no_requiere", que es utilizable
        # desde que entra. La pantalla se apoya en este campo para no ofrecer
        # Consumir sobre algo que `registrar_salida` va a rechazar.
        self.assertTrue(fila["lote_utilizable"])

    # ---- movimientos de material

    def test_movimientos_filtran_por_q_tipo_ubicacion_y_fechas(self):
        tipo = MovimientoInventario.objects.first().tipo
        hoy = timezone.localdate()
        base = "/api/inventario/movimientos/"
        self.assertEqual(self.nombres(f"{base}?q=etiqueta"), ["Etiqueta frontal"])
        self.assertEqual(len(self.nombres(f"{base}?estado={tipo}")), 2)
        self.assertEqual(self.nombres(f"{base}?ubicacion={self.otra.pk}"), ["Etiqueta frontal"])
        self.assertEqual(len(self.nombres(f"{base}?desde={hoy}")), 2)
        self.assertEqual(self.nombres(f"{base}?hasta={hoy - timedelta(days=1)}"), [])

    def test_una_fecha_mal_escrita_es_un_400(self):
        respuesta = self.api.get("/api/inventario/movimientos/?desde=24-09-2026")
        self.assertEqual(respuesta.status_code, 400)

    def test_el_movimiento_se_lee_sin_traducir(self):
        fila = filas(self.api.get("/api/inventario/movimientos/?q=saco"))[0]
        self.assertTrue(fila["tipo_etiqueta"])
        self.assertNotEqual(fila["tipo_etiqueta"], fila["tipo"])
        self.assertEqual(fila["unidad"], "un")
        self.assertEqual(fila["usuario_nombre"], "bodega-pt")

    # ---- producto terminado

    def codigos(self, ruta):
        respuesta = self.api.get(ruta)
        self.assertEqual(respuesta.status_code, 200, respuesta.data)
        return sorted(fila["pallet_codigo"] for fila in filas(respuesta))

    def test_pallets_por_q_estado_y_cargable(self):
        self.liberar()
        ingresar_pallet(self.pallet, self.ubicacion, self.usuario)
        otro = self.crear_pallet("PAL-PT-2")
        ingresar_pallet(otro, self.ubicacion, self.usuario)
        despacho = Despacho.objects.create(
            sucursal=self.planta, numero="D-X", cliente=self.cliente, creado_por=self.usuario,
        )
        DetalleDespacho.objects.create(despacho=despacho, pallet=otro)
        base = "/api/inventario/producto-terminado/"
        self.assertEqual(self.codigos(f"{base}?q=pt-2"), ["PAL-PT-2"])
        self.assertEqual(self.codigos(f"{base}?estado=disponible"), ["PAL-PT", "PAL-PT-2"])
        self.assertEqual(self.codigos(f"{base}?estado=bloqueado"), [])
        self.assertEqual(self.codigos(f"{base}?cargable=1"), ["PAL-PT"])
        fila = filas(self.api.get(f"{base}?q=PAL-PT-2"))[0]
        self.assertEqual(fila["ubicacion_tipo"], "disponible")

    def test_movimientos_de_pallet_filtran_y_se_leen(self):
        self.liberar()
        ingresar_pallet(self.pallet, self.ubicacion, self.usuario)
        respuesta = self.api.get("/api/inventario/movimientos-producto-terminado/?q=PAL-PT&estado=ingreso")
        fila = filas(respuesta)[0]
        self.assertEqual(fila["pallet_codigo"], "PAL-PT")
        self.assertEqual(fila["lote_codigo"], "L-PT")
        self.assertEqual(fila["destino_codigo"], "A-01")
        self.assertEqual(fila["registrado_por_nombre"], "bodega-pt")
        self.assertTrue(fila["tipo_etiqueta"])
        self.assertEqual(
            filas(self.api.get("/api/inventario/movimientos-producto-terminado/?estado=despacho")), []
        )

    def test_el_catalogo_sirve_los_estados_que_entienden_los_filtros(self):
        datos = self.api.get("/api/inventario/catalogos/").data
        self.assertIn({"valor": "aprobado", "etiqueta": "Aprobado"}, datos["estado_calidad"])
        self.assertIn("ingreso", [o["valor"] for o in datos["tipo_movimiento_pallet"]])
        self.assertEqual([o["valor"] for o in datos["estado_pallet"]], ["disponible", "cuarentena", "bloqueado"])
        self.assertTrue(datos["tipo_movimiento"])

    def test_el_catalogo_sirve_los_estados_de_despacho(self):
        datos = self.api.get("/api/inventario/catalogos/").data
        self.assertEqual(
            datos["estado_despacho"],
            [
                {"valor": "borrador", "etiqueta": "Borrador"},
                {"valor": "autorizado", "etiqueta": "Autorizado"},
                {"valor": "despachado", "etiqueta": "Despachado"},
                {"valor": "cancelado", "etiqueta": "Cancelado"},
            ],
        )
