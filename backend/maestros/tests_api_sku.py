"""
Pruebas de la API de productos con SKU.

Lo que protegen: que la pantalla de Maestros no pueda escribir un SKU a mano
—se deriva de los atributos— y que los catálogos que alimentan sus
desplegables vengan del backend y no de una copia en el frontend, que se
separaría del generador sin que nadie lo note.
"""

from django.contrib.auth.models import User
from django.test import TestCase
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient

from usuarios.models import PerfilUsuario, Rol

from . import catalogos_sku
from .models import Mandante, Producto


class BaseApiMaestros(TestCase):
    def setUp(self):
        self.nestle = Mandante.objects.create(
            nombre="Nestlé", codigo_cliente=Mandante.Cliente.NESTLE
        )
        self.ccaa = Mandante.objects.create(
            nombre="CCAA", codigo_cliente=Mandante.Cliente.NO_DEFINIDO
        )
        self.cliente = self._cliente(Rol.ADMIN)

    def _cliente(self, rol):
        usuario = User.objects.create_user(f"u-{rol}", password="x")
        PerfilUsuario.objects.create(usuario=usuario, rol=rol)
        cliente = APIClient()
        cliente.credentials(
            HTTP_AUTHORIZATION=f"Token {Token.objects.create(user=usuario).key}"
        )
        return cliente

    def _crear(self, cliente=None, **extra):
        datos = {
            "nombre": "Leche entera en polvo",
            "mandante": self.nestle.id,
            "familia": "polvo",
            "naturaleza_comercial": "servicio_terceros",
            "categoria": "leche_polvo",
            "tipo": "entera",
            "formato": "saco_25kg",
        }
        datos.update(extra)

        return (cliente or self.cliente).post(
            "/api/maestros/productos/", datos, format="json"
        )


class CrearProductoTests(BaseApiMaestros):

    def test_el_sku_se_genera_al_crear(self):
        respuesta = self._crear()

        self.assertEqual(respuesta.status_code, 201)
        self.assertEqual(respuesta.data["codigo"], "010102010201")

    def test_la_respuesta_trae_el_sku_descompuesto(self):
        """
        Para poder contrastarlo con los atributos sin descomponerlo a mano:
        es la comprobación que faltaba en el archivo de origen.
        """
        legible = self._crear().data["sku_legible"]

        self.assertEqual(legible["categoria"], "leche_polvo")
        self.assertEqual(legible["cliente"], "nestle")

    def test_el_sku_no_se_puede_teclear(self):
        """
        Mandarlo desde el cliente permitiría un código que contradiga los
        atributos del mismo producto, que es el defecto de §4.2.
        """
        respuesta = self._crear(codigo="INVENTADO-1")

        self.assertEqual(respuesta.status_code, 201)
        self.assertEqual(respuesta.data["codigo"], "010102010201")

    def test_una_combinacion_imposible_se_rechaza_con_su_motivo(self):
        respuesta = self._crear(
            mandante=self.nestle.id, naturaleza_comercial="producto_propio"
        )

        self.assertEqual(respuesta.status_code, 400)
        self.assertIn("naturaleza_comercial", respuesta.data)

    def test_un_producto_sin_atributos_se_crea_igual(self):
        """Cargar el maestro a medias tiene que ser posible."""
        respuesta = self._crear(
            naturaleza_comercial="", categoria="", tipo="", formato=""
        )

        self.assertEqual(respuesta.status_code, 201)
        self.assertEqual(respuesta.data["codigo"], "")
        self.assertIsNone(respuesta.data["sku_legible"])

    def test_editar_un_atributo_recalcula_el_sku(self):
        producto = Producto.objects.get(pk=self._crear().data["id"])

        respuesta = self.cliente.patch(
            f"/api/maestros/productos/{producto.id}/",
            {"formato": "granel"},
            format="json",
        )

        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta.data["codigo"], "010102010101")

    def test_un_patch_parcial_no_pierde_los_otros_atributos(self):
        """
        La validación arma el candidato sobre lo que ya está guardado. Si
        mirara solo lo que llega, un PATCH de un campo se leería como un
        producto sin atributos y no validaría nada.
        """
        producto = Producto.objects.get(pk=self._crear().data["id"])

        respuesta = self.cliente.patch(
            f"/api/maestros/productos/{producto.id}/",
            {"naturaleza_comercial": "producto_propio"},
            format="json",
        )

        self.assertEqual(respuesta.status_code, 400)

    def test_produccion_no_toca_los_maestros(self):
        respuesta = self._crear(cliente=self._cliente(Rol.PRODUCCION))

        self.assertEqual(respuesta.status_code, 403)


class CatalogosSkuTests(BaseApiMaestros):

    def test_sirve_los_valores_de_cada_segmento(self):
        datos = self.cliente.get("/api/maestros/catalogos-sku/").json()

        for segmento in ("naturaleza_comercial", "categoria", "tipo", "formato",
                         "mercado", "cliente"):
            with self.subTest(segmento=segmento):
                self.assertTrue(datos[segmento])

    def test_los_valores_son_los_que_el_generador_acepta(self):
        """
        Es la razón de servirlos: una copia en el frontend ofrecería tarde o
        temprano un valor que el backend rechaza.
        """
        datos = self.cliente.get("/api/maestros/catalogos-sku/").json()

        pares = [
            ("naturaleza_comercial", catalogos_sku.NATURALEZA),
            ("categoria", catalogos_sku.CATEGORIA),
            ("tipo", catalogos_sku.TIPO),
            ("formato", catalogos_sku.FORMATO),
            ("mercado", catalogos_sku.MERCADO),
            ("cliente", catalogos_sku.CLIENTE),
        ]

        for segmento, catalogo in pares:
            with self.subTest(segmento=segmento):
                self.assertEqual(
                    {o["valor"] for o in datos[segmento]}, set(catalogo)
                )

    def test_cada_valor_trae_su_etiqueta(self):
        datos = self.cliente.get("/api/maestros/catalogos-sku/").json()

        self.assertTrue(all(o["etiqueta"] for o in datos["categoria"]))


class MandanteApiTests(BaseApiMaestros):

    def test_el_listado_trae_el_codigo_de_cliente(self):
        datos = self.cliente.get("/api/maestros/mandantes/").json()["results"]
        nestle = next(m for m in datos if m["nombre"] == "Nestlé")

        self.assertEqual(nestle["codigo_cliente"], "nestle")
        self.assertEqual(nestle["codigo_cliente_etiqueta"], "Nestlé")

    def test_se_puede_crear_un_mandante_con_su_cliente(self):
        respuesta = self.cliente.post(
            "/api/maestros/mandantes/",
            {"nombre": "Soprole", "codigo_cliente": "soprole"},
            format="json",
        )

        self.assertEqual(respuesta.status_code, 201)

    def test_sin_codigo_de_cliente_sus_productos_no_generan_sku(self):
        colun = Mandante.objects.create(nombre="Colun")

        respuesta = self._crear(nombre="Suero WPC", mandante=colun.id)

        self.assertEqual(respuesta.status_code, 201)
        self.assertEqual(respuesta.data["codigo"], "")
