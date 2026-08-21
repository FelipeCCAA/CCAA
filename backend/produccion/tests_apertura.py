"""
Pruebas de la apertura de un proceso productivo.

El cambio que cubren: antes un lote nacía ya producido —el formulario exigía
los kilos— y la asignación de leche era documentación retroactiva. Ahora el
lote se abre al empezar la corrida, con su leche y sin kilos, y los kilos se
declaran al cerrarla, que es cuando se saben.

Lo que protegen es que las dos mitades del cambio no se separen: que abrir sin
kilos sea posible, que declararse producido sin ellos NO lo sea, y que crear el
lote y asignarle leche sea una sola operación o ninguna.
"""

from datetime import date

from django.contrib.auth.models import User
from django.test import TestCase
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient

from maestros.models import Equipo, Mandante, Producto, Silo
from usuarios.models import Empresa, PerfilUsuario, Rol, Sucursal

from . import dominio
from .models import Lote


class BaseApertura(TestCase):
    def setUp(self):
        self.empresa = Empresa.objects.create(rut="APERTURA", nombre="Apertura")
        self.sucursal = Sucursal.objects.create(
            empresa=self.empresa, codigo="PLANTA", nombre="Planta apertura"
        )
        self.equipo = Equipo.objects.create(
            sucursal=self.sucursal, codigo="e1", nombre="Egron 1",
            tipo=Equipo.Tipo.TORRE, sigla="E1",
        )
        self.otro_equipo = Equipo.objects.create(
            sucursal=self.sucursal, codigo="e2", nombre="Egron 2",
            tipo=Equipo.Tipo.TORRE, sigla="E2",
        )
        self.mandante = Mandante.objects.create(empresa=self.empresa, nombre="Nestlé")

        # El SKU es parte del código de lote: sin él no hay codificación
        # automática.
        self.polvo = Producto.objects.create(
            codigo="LEP25",
            nombre="Leche entera en polvo",
            familia=Producto.Familia.POLVO,
            mandante=self.mandante,
        )
        self.crema = Producto.objects.create(
            codigo="CRE10",
            nombre="Crema",
            familia=Producto.Familia.CREMA,
            mandante=self.mandante,
        )
        self.silo_a = Silo.objects.create(
            sucursal=self.sucursal,
            codigo="SILO 1", tipo=Silo.Tipo.SILO, capacidad_l=200000
        )
        self.silo_b = Silo.objects.create(
            sucursal=self.sucursal,
            codigo="SILO 2", tipo=Silo.Tipo.SILO, capacidad_l=200000
        )

        self.cliente = self._cliente(Rol.PRODUCCION)

    def _cliente(self, rol):
        usuario = User.objects.create_user(f"u-{rol}", password="x")
        PerfilUsuario.objects.create(
            usuario=usuario,
            rol=rol,
            area=PerfilUsuario.Area.SECADO,
            empresa=self.empresa,
            sucursal=self.sucursal,
            alcance=PerfilUsuario.Alcance.SUCURSAL,
        )
        cliente = APIClient()
        cliente.credentials(
            HTTP_AUTHORIZATION=f"Token {Token.objects.create(user=usuario).key}"
        )
        return cliente

    def _abrir(self, **extra):
        datos = {
            "codigo_lote": "CCAA6197",
            "producto": self.polvo.id,
            "fecha": "2026-07-16",
        }
        datos.update(extra)

        return self.cliente.post("/api/produccion/lotes/", datos, format="json")


class AbrirProcesoTests(BaseApertura):

    def test_un_lote_se_abre_sin_kilos(self):
        """
        Los kilos se saben cuando la corrida termina. Exigirlos al abrir es lo
        que obligaba a registrar el lote al final del día, y con él toda su
        trazabilidad.
        """
        respuesta = self._abrir()

        self.assertEqual(respuesta.status_code, 201)
        self.assertIsNone(respuesta.data["kg_producidos"])

        lote = Lote.objects.get()
        self.assertEqual(lote.estado, Lote.Estado.EN_PROCESO)
        self.assertIsNone(lote.kg_producidos)

    def test_sin_asignaciones_el_lote_se_abre_igual(self):
        """Un lote histórico se carga sin leche; el aviso llega al cerrarlo."""
        respuesta = self._abrir()

        self.assertEqual(respuesta.status_code, 201)
        self.assertNotIn("asignacion", respuesta.data)

    def test_los_kilos_se_pueden_declarar_al_abrir(self):
        """Cargar un lote histórico completo sigue siendo posible."""
        respuesta = self._abrir(kg_producidos="12000.00")

        self.assertEqual(respuesta.status_code, 201)
        self.assertEqual(Lote.objects.get().kg_producidos, 12000)


class DeclararProducidoTests(BaseApertura):
    """Los kilos son obligatorios aquí, que es cuando se conocen."""

    def _lote_abierto(self, **extra):
        return Lote.objects.create(
            sucursal=self.sucursal,
            codigo_lote="CCAA6197",
            producto=self.polvo,
            fecha=date(2026, 7, 16),
            **extra,
        )

    def _producir(self, lote, **extra):
        datos = {"estado": "producido"}
        datos.update(extra)

        return self.cliente.patch(
            f"/api/produccion/lotes/{lote.id}/", datos, format="json"
        )

    def test_sin_kilos_no_se_declara_producido(self):
        lote = self._lote_abierto()

        respuesta = self._producir(lote)

        self.assertEqual(respuesta.status_code, 400)
        self.assertIn("kilos", str(respuesta.data).lower())

        lote.refresh_from_db()
        self.assertEqual(lote.estado, Lote.Estado.EN_PROCESO)

    def test_los_kilos_pueden_venir_en_la_misma_llamada(self):
        """
        Es como lo hace la pantalla: se declaran los kilos y se cierra la
        producción en un gesto. Validarlos contra lo que ya está guardado
        rechazaría un cierre perfectamente válido.
        """
        lote = self._lote_abierto()

        respuesta = self._producir(lote, kg_producidos="12000.00")

        self.assertEqual(respuesta.status_code, 200)

        lote.refresh_from_db()
        self.assertEqual(lote.estado, Lote.Estado.PRODUCIDO)
        self.assertEqual(lote.kg_producidos, 12000)

    def test_cero_kilos_no_es_una_produccion(self):
        lote = self._lote_abierto()

        respuesta = self._producir(lote, kg_producidos="0")

        self.assertEqual(respuesta.status_code, 400)

    def test_un_lote_con_kilos_cierra_sin_repetirlos(self):
        lote = self._lote_abierto(kg_producidos=12000)

        self.assertEqual(self._producir(lote).status_code, 200)

    def test_anular_no_exige_kilos_pero_si_motivo(self):
        """Un lote que no llegó a producirse no tiene kilos que declarar."""
        lote = self._lote_abierto()

        respuesta = self.cliente.patch(
            f"/api/produccion/lotes/{lote.id}/",
            {"estado": "anulado", "motivo_anulacion": "La corrida no se inició."},
            format="json",
        )

        self.assertEqual(respuesta.status_code, 200)


class ReglaDeCierreTests(TestCase):
    """
    La regla, sola. Es una función pura: se prueba sin base de datos y
    endurecerla —por ejemplo, exigir la leche asignada— es editarla aquí.
    """

    class _Lote:
        def __init__(self, kg):
            self.kg_producidos = kg

    def test_sin_kilos_bloquea(self):
        decision = dominio.puede_declarar_producido(self._Lote(None), [])

        self.assertFalse(decision.permitido)
        self.assertTrue(decision.bloqueos)

    def test_sin_leche_asignada_avisa_pero_deja_pasar(self):
        """
        Un lote sin asignar queda sin trazabilidad, que es un problema real.
        Pero impedir el cierre detendría la producción del día por un dato que
        se completa después; endurecerlo es decisión de Calidad.
        """
        decision = dominio.puede_declarar_producido(self._Lote(12000), [])

        self.assertTrue(decision.permitido)
        self.assertTrue(decision.avisos)

    def test_con_kilos_y_leche_no_hay_nada_que_decir(self):
        decision = dominio.puede_declarar_producido(self._Lote(12000), ["una salida"])

        self.assertTrue(decision.permitido)
        self.assertFalse(decision.bloqueos)
        self.assertFalse(decision.avisos)


class CodigoSugeridoTests(BaseApertura):

    def _sugerir(self, **params):
        params.setdefault("equipo", self.equipo.id)
        params.setdefault("fecha", "2026-07-16")

        return self.cliente.get("/api/produccion/lotes/codigo-sugerido/", params)

    def test_mezcla_anio_dia_juliano_y_sigla(self):
        # 2026 → '6'; el 16 de julio de 2026 es el día juliano 197.
        self.assertEqual(self._sugerir().json()["codigo"], "CCAA6197E1-01")

    def test_el_correlativo_se_deduce_de_los_lotes_que_ya_existen(self):
        """
        Preguntárselo al operador sería pedirle un dato que el sistema ya
        tiene, y equivocarse ahí repite un código de lote.
        """
        Lote.objects.create(
            sucursal=self.sucursal,
            codigo_lote="CCAA6197E1-01", equipo=self.equipo,
            producto=self.polvo,
            fecha=date(2026, 7, 16),
        )

        datos = self._sugerir().json()

        self.assertEqual(datos["codigo"], "CCAA6197E1-02")
        self.assertEqual(datos["correlativo"], 2)

    def test_un_lote_de_otra_maquina_no_corre_el_correlativo(self):
        """
        El correlativo cuenta por producto: es lo que distingue dos corridas
        del mismo SKU, no la actividad del día.
        """
        Lote.objects.create(
            sucursal=self.sucursal,
            codigo_lote="CCAA6197E2-01", producto=self.crema, equipo=self.otro_equipo,
            fecha=date(2026, 7, 16),
        )

        self.assertEqual(self._sugerir().json()["codigo"], "CCAA6197E1-01")

    def test_un_lote_de_otra_fecha_no_corre_el_correlativo(self):
        Lote.objects.create(
            sucursal=self.sucursal,
            codigo_lote="CCAA6196E1-01", equipo=self.equipo,
            producto=self.polvo,
            fecha=date(2026, 7, 15),
        )

        self.assertEqual(self._sugerir().json()["codigo"], "CCAA6197E1-01")

    def test_dos_maquinas_del_mismo_dia_se_distinguen_por_la_sigla(self):
        self.assertNotEqual(
            self._sugerir().json()["codigo"],
            self._sugerir(equipo=self.otro_equipo.id).json()["codigo"],
        )

    def test_un_equipo_sin_sigla_no_frena_el_lote(self):
        """
        Devuelve 200 con `codigo: null` y un motivo que dice qué falta y
        dónde. Un 400 se leería como que el lote no se puede crear, y sí se
        puede: el código se escribe a mano.
        """
        self.equipo.sigla = ""
        self.equipo.save()
        respuesta = self._sugerir()

        self.assertEqual(respuesta.status_code, 200)
        self.assertIsNone(respuesta.json()["codigo"])
        self.assertIn("sigla", respuesta.json()["motivo"])
        self.assertIn("Maestros", respuesta.json()["motivo"])

    def test_sin_producto_o_fecha_no_se_inventa_un_codigo(self):
        respuesta = self.cliente.get("/api/produccion/lotes/codigo-sugerido/")

        self.assertEqual(respuesta.status_code, 400)

    def test_una_fecha_ilegible_se_dice_en_vez_de_reventar(self):
        respuesta = self._sugerir(fecha="16-07-2026")

        self.assertEqual(respuesta.status_code, 400)
        self.assertIn("AAAA-MM-DD", respuesta.json()["detail"])


class ConsumoDeInventarioTests(BaseApertura):
    """
    Declarar el lote producido descuenta su material de bodega.

    Antes esto no pasaba en ninguna parte: `inventario` tenía el servicio y
    nadie lo llamaba, así que la trazabilidad se cortaba justo donde el
    material se consume.
    """

    def setUp(self):
        super().setUp()

        from inventario.models import Bodega, LoteInventario, Insumo, Ubicacion
        from inventario.servicios import registrar_entrada
        from maestros.models import Receta, RecetaComponente

        self.bolsa = Insumo.objects.create(
            codigo="BOLSA-25",
            nombre="Bolsa 25 kg",
            area=PerfilUsuario.Area.SECADO,
            unidad="un",
        )
        receta = Receta.objects.create(
            producto=self.polvo, version=1, cantidad_base=1,
            vigente_desde=date(2020, 1, 1),
        )
        RecetaComponente.objects.create(
            receta=receta, insumo=self.bolsa, cantidad="0.04", unidad="un",
        )

        bodega = Bodega.objects.create(codigo="B1", nombre="Bodega")
        self.ubicacion = Ubicacion.objects.create(bodega=bodega, codigo="DISP")
        self.material = LoteInventario.objects.create(
            insumo=self.bolsa, codigo="B-1",
            estado_calidad=LoteInventario.EstadoCalidad.APROBADO,
        )
        registrar_entrada(
            lote=self.material, ubicacion=self.ubicacion, cantidad=100,
            usuario=User.objects.create_user("bodeguero", password="x"),
            documento_tipo="recepcion", documento_id=1,
        )

    def _lote_abierto(self):
        return Lote.objects.create(
            sucursal=self.sucursal,
            codigo_lote="CCAA6197", producto=self.polvo, fecha=date(2026, 7, 16),
        )

    def _producir(self, lote, kg=1000):
        return self.cliente.patch(
            f"/api/produccion/lotes/{lote.id}/",
            {"estado": "producido", "kg_producidos": kg},
            format="json",
        )

    def _existencia(self):
        from inventario.models import Existencia

        return Existencia.objects.get(
            lote=self.material, ubicacion=self.ubicacion
        ).cantidad_fisica

    def test_declararse_producido_descuenta_el_material(self):
        from decimal import Decimal

        lote = self._lote_abierto()

        respuesta = self._producir(lote)

        self.assertEqual(respuesta.status_code, 200)
        # 1000 kg × 0,04 bolsas por kg = 40 bolsas.
        self.assertEqual(self._existencia(), Decimal("60.000"))
        self.assertTrue(respuesta.data["consumo_inventario"]["registrado"])
        self.assertFalse(respuesta.data["consumo_inventario"]["pendiente"])

    def test_sin_stock_el_lote_igual_se_declara_y_avisa(self):
        """
        El mismo criterio que la leche asignada: detener la producción del día
        porque bodega no alcanzó a cargar el material traslada a la línea un
        problema que no es suyo.
        """
        from decimal import Decimal

        lote = self._lote_abierto()

        # 100.000 kg piden 4.000 bolsas y solo hay 100.
        respuesta = self._producir(lote, kg=100_000)

        self.assertEqual(respuesta.status_code, 200)

        lote.refresh_from_db()
        self.assertEqual(lote.estado, Lote.Estado.PRODUCIDO)

        # Nada se descontó, ni a medias. El servicio alcanza a crear la
        # cabecera y a sacar las 100 bolsas que sí había antes de darse cuenta
        # de que faltan: si eso no se revirtiera, el lote quedaría con un
        # consumo «registrado» que descontó una fracción de lo que debía, y
        # nadie volvería a mirarlo porque ya figura hecho.
        from inventario.models import ConsumoLoteProduccion

        self.assertEqual(self._existencia(), Decimal("100.000"))
        self.assertFalse(
            ConsumoLoteProduccion.objects.filter(lote_produccion=lote).exists()
        )
        self.assertTrue(respuesta.data["consumo_inventario"]["pendiente"])
        self.assertIn("Stock insuficiente", str(respuesta.data["avisos"]))

    def test_un_lote_sin_receta_no_bloquea_pero_queda_pendiente(self):
        lote = Lote.objects.create(
            sucursal=self.sucursal,
            codigo_lote="CCAA6198", producto=self.crema, fecha=date(2026, 7, 16),
        )

        respuesta = self._producir(lote)

        self.assertEqual(respuesta.status_code, 200)
        self.assertTrue(respuesta.data["consumo_inventario"]["pendiente"])

    def test_no_se_descuenta_dos_veces_al_reeditar(self):
        """
        Un PATCH posterior sobre un lote ya producido no vuelve a descontar:
        el material se consumió una vez y el stock no puede bajar de nuevo por
        haber corregido una observación.
        """
        from decimal import Decimal

        lote = self._lote_abierto()
        self._producir(lote)

        self.cliente.patch(
            f"/api/produccion/lotes/{lote.id}/",
            {"observacion": "corrección"},
            format="json",
        )

        self.assertEqual(self._existencia(), Decimal("60.000"))

    def test_un_lote_en_proceso_no_tiene_consumo_pendiente(self):
        """Todavía no tiene kilos: no hay nada que descontar."""
        lote = self._lote_abierto()

        respuesta = self.cliente.get(f"/api/produccion/lotes/{lote.id}/")

        self.assertFalse(respuesta.data["consumo_inventario"]["pendiente"])


class ReglaDeConsumoPendienteTests(TestCase):
    """La regla sola, sin base de datos."""

    class _Lote:
        def __init__(self, estado):
            self.estado = estado

    def test_en_proceso_no_hay_nada_pendiente(self):
        self.assertFalse(
            dominio.consumo_de_inventario_pendiente(self._Lote("en_proceso"), None)
        )

    def test_producido_sin_consumo_queda_pendiente(self):
        self.assertTrue(
            dominio.consumo_de_inventario_pendiente(self._Lote("producido"), None)
        )

    def test_producido_con_consumo_no_queda_pendiente(self):
        self.assertFalse(
            dominio.consumo_de_inventario_pendiente(
                self._Lote("producido"), object()
            )
        )

    def test_un_lote_cerrado_tambien_debio_descontar(self):
        self.assertTrue(
            dominio.consumo_de_inventario_pendiente(self._Lote("cerrado"), None)
        )
