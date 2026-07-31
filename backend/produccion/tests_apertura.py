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

from maestros.models import Mandante, Producto, Silo
from recepcion.models import MovimientoSilo
from usuarios.models import PerfilUsuario, Rol

from . import dominio
from .models import Lote


class BaseApertura(TestCase):
    def setUp(self):
        self.mandante = Mandante.objects.create(nombre="Nestlé")

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
            codigo="SILO 1", tipo=Silo.Tipo.SILO, capacidad_l=200000
        )
        self.silo_b = Silo.objects.create(
            codigo="SILO 2", tipo=Silo.Tipo.SILO, capacidad_l=200000
        )

        self.cliente = self._cliente(Rol.PRODUCCION)

    def _cliente(self, rol):
        usuario = User.objects.create_user(f"u-{rol}", password="x")
        PerfilUsuario.objects.create(usuario=usuario, rol=rol)
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

    def test_abrir_el_proceso_asigna_la_leche_en_la_misma_operacion(self):
        respuesta = self._abrir(
            asignaciones=[
                {"silo": self.silo_a.id, "litros": 40000},
                {"silo": self.silo_b.id, "litros": 20000},
            ]
        )

        self.assertEqual(respuesta.status_code, 201)
        self.assertEqual(respuesta.data["asignacion"]["asignado"], 60000)
        self.assertEqual(MovimientoSilo.objects.count(), 2)

    def test_si_la_asignacion_falla_no_queda_un_lote_abierto_sin_leche(self):
        """
        Es la razón de que vayan juntas. Un lote creado a medias parece
        completo, y nadie vuelve a completar lo que ya existe.
        """
        respuesta = self._abrir(
            asignaciones=[
                {"silo": self.silo_a.id, "litros": 40000},
                {"silo": self.silo_b.id, "litros": -5},
            ]
        )

        self.assertEqual(respuesta.status_code, 400)
        self.assertFalse(Lote.objects.exists())
        self.assertFalse(MovimientoSilo.objects.exists())

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

    def test_anular_no_exige_kilos(self):
        """Un lote que no llegó a producirse no tiene kilos que declarar."""
        lote = self._lote_abierto()

        respuesta = self.cliente.patch(
            f"/api/produccion/lotes/{lote.id}/", {"estado": "anulado"}, format="json"
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
        params.setdefault("producto", self.polvo.id)
        params.setdefault("fecha", "2026-07-16")

        return self.cliente.get("/api/produccion/lotes/codigo-sugerido/", params)

    def test_mezcla_anio_dia_juliano_y_sku(self):
        # 2026 → '6'; el 16 de julio de 2026 es el día juliano 197.
        self.assertEqual(self._sugerir().json()["codigo"], "CCAA6197LEP25-01")

    def test_el_correlativo_se_deduce_de_los_lotes_que_ya_existen(self):
        """
        Preguntárselo al operador sería pedirle un dato que el sistema ya
        tiene, y equivocarse ahí repite un código de lote.
        """
        Lote.objects.create(
            codigo_lote="CCAA6197LEP25-01",
            producto=self.polvo,
            fecha=date(2026, 7, 16),
        )

        datos = self._sugerir().json()

        self.assertEqual(datos["codigo"], "CCAA6197LEP25-02")
        self.assertEqual(datos["correlativo"], 2)
        self.assertIn("n.º 2", datos["motivo"])

    def test_un_lote_de_otro_producto_no_corre_el_correlativo(self):
        """
        El correlativo cuenta por producto: es lo que distingue dos corridas
        del mismo SKU, no la actividad del día.
        """
        Lote.objects.create(
            codigo_lote="CCAA6197CRE10-01",
            producto=self.crema,
            fecha=date(2026, 7, 16),
        )

        self.assertEqual(self._sugerir().json()["codigo"], "CCAA6197LEP25-01")

    def test_un_lote_de_otra_fecha_no_corre_el_correlativo(self):
        Lote.objects.create(
            codigo_lote="CCAA6196LEP25-01",
            producto=self.polvo,
            fecha=date(2026, 7, 15),
        )

        self.assertEqual(self._sugerir().json()["codigo"], "CCAA6197LEP25-01")

    def test_dos_productos_del_mismo_dia_se_distinguen_por_el_sku(self):
        self.assertNotEqual(
            self._sugerir().json()["codigo"],
            self._sugerir(producto=self.crema.id).json()["codigo"],
        )

    def test_un_producto_sin_sku_no_frena_el_lote(self):
        """
        Devuelve 200 con `codigo: null` y un motivo que dice qué falta y
        dónde. Un 400 se leería como que el lote no se puede crear, y sí se
        puede: el código se escribe a mano.
        """
        sin_sku = Producto.objects.create(
            nombre="Suero en polvo",
            familia=Producto.Familia.POLVO,
            mandante=self.mandante,
        )

        respuesta = self._sugerir(producto=sin_sku.id)

        self.assertEqual(respuesta.status_code, 200)
        self.assertIsNone(respuesta.json()["codigo"])
        self.assertIn("SKU", respuesta.json()["motivo"])
        self.assertIn("Maestros", respuesta.json()["motivo"])

    def test_sin_producto_o_fecha_no_se_inventa_un_codigo(self):
        respuesta = self.cliente.get("/api/produccion/lotes/codigo-sugerido/")

        self.assertEqual(respuesta.status_code, 400)

    def test_una_fecha_ilegible_se_dice_en_vez_de_reventar(self):
        respuesta = self._sugerir(fecha="16-07-2026")

        self.assertEqual(respuesta.status_code, 400)
        self.assertIn("AAAA-MM-DD", respuesta.json()["detail"])
