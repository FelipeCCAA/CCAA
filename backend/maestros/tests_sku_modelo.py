"""
Pruebas del SKU en el maestro `Producto`.

El codificador puro se prueba en `tests_dominio_sku.py`. Aquí se prueba lo
otro: que el modelo derive el SKU de sus atributos en vez de dejarlo teclear,
y que los desplegables ofrezcan exactamente los valores que el generador
acepta.

Esa última es la que importa más de lo que parece. Los `TextChoices` del
modelo y los diccionarios de `catalogos_sku` son dos listas separadas; si
divergen, la pantalla ofrece un valor que el generador rechaza y el error
aparece al guardar, no al elegir.
"""

from django.core.exceptions import ValidationError
from django.test import TestCase

from . import catalogos_sku
from .models import Mandante, Producto


class ChoicesContraCatalogosTests(TestCase):
    """Las dos listas tienen que decir lo mismo."""

    def test_los_desplegables_ofrecen_lo_que_el_generador_acepta(self):
        pares = [
            ("naturaleza_comercial", Producto.NaturalezaComercial, catalogos_sku.NATURALEZA),
            ("categoria", Producto.Categoria, catalogos_sku.CATEGORIA),
            ("tipo", Producto.TipoProducto, catalogos_sku.TIPO),
            ("formato", Producto.Formato, catalogos_sku.FORMATO),
            ("mercado", Producto.Mercado, catalogos_sku.MERCADO),
        ]

        for campo, choices, catalogo in pares:
            with self.subTest(campo=campo):
                self.assertEqual(set(choices.values), set(catalogo))

    def test_el_cliente_del_mandante_tambien(self):
        self.assertEqual(
            set(Mandante.Cliente.values), set(catalogos_sku.CLIENTE)
        )


class DerivarSkuTests(TestCase):

    def setUp(self):
        self.nestle = Mandante.objects.create(
            nombre="Nestlé", codigo_cliente=Mandante.Cliente.NESTLE
        )
        self.ccaa = Mandante.objects.create(
            nombre="CCAA", codigo_cliente=Mandante.Cliente.NO_DEFINIDO
        )

    def _producto(self, mandante=None, **extra):
        datos = {
            "nombre": extra.pop("nombre", "Leche entera en polvo"),
            "mandante": mandante or self.nestle,
            "familia": Producto.Familia.POLVO,
            "naturaleza_comercial": Producto.NaturalezaComercial.SERVICIO_TERCEROS,
            "categoria": Producto.Categoria.LECHE_POLVO,
            "tipo": Producto.TipoProducto.ENTERA,
            "formato": Producto.Formato.SACO_25KG,
        }
        datos.update(extra)

        return Producto.objects.create(**datos)

    def test_el_sku_se_genera_al_guardar(self):
        producto = self._producto()

        self.assertEqual(producto.codigo, "010102010201")

    def test_el_cliente_sale_del_mandante(self):
        """
        No se pregunta dos veces: el mandante ya dice de quién es el producto.
        Un segundo campo se desincronizaría del primero.
        """
        propio = self._producto(
            mandante=self.ccaa,
            nombre="Crema",
            naturaleza_comercial=Producto.NaturalezaComercial.PRODUCTO_PROPIO,
            categoria=Producto.Categoria.CREMA,
            formato=Producto.Formato.GRANEL,
        )

        self.assertEqual(propio.codigo, "020004010101")

    def test_el_mercado_local_es_el_valor_por_defecto(self):
        self.assertTrue(self._producto().codigo.endswith("01"))

    def test_la_variante_alarga_el_sku(self):
        producto = self._producto(variante=3)

        self.assertEqual(producto.codigo, "01010201020103")

    def test_cambiar_un_atributo_recalcula_el_sku(self):
        """
        Los atributos son la fuente de verdad. Que el código quedara pegado al
        primero es justo lo que produce las filas mal codificadas del archivo
        de origen: un SKU que dice Crema sobre un producto de leche en polvo.
        """
        producto = self._producto()
        producto.formato = Producto.Formato.GRANEL
        producto.save()

        self.assertEqual(producto.codigo, "010102010101")

    def test_sin_atributos_no_se_inventa_un_sku(self):
        producto = Producto.objects.create(
            nombre="Producto a medio cargar",
            mandante=self.nestle,
            familia=Producto.Familia.OTRO,
        )

        self.assertEqual(producto.codigo, "")
        self.assertIsNone(producto.sku_derivado())

    def test_un_codigo_antiguo_sobrevive_si_no_hay_atributos(self):
        """
        El histórico está lleno de códigos escritos a mano y hay que poder
        registrarlos. Solo los pisa el generador cuando hay con qué generar.
        """
        producto = Producto.objects.create(
            nombre="Producto histórico",
            mandante=self.nestle,
            familia=Producto.Familia.OTRO,
            codigo="LEP-VIEJO-7",
        )

        self.assertEqual(producto.codigo, "LEP-VIEJO-7")

    def test_un_mandante_sin_codigo_de_cliente_no_genera_sku(self):
        colun = Mandante.objects.create(nombre="Colun")  # sin codigo_cliente

        producto = self._producto(mandante=colun, nombre="Suero WPC")

        self.assertEqual(producto.codigo, "")


class ReglaNaturalezaClienteTests(TestCase):
    """
    Un producto propio con cliente —o uno de terceros sin él— describe algo
    que no existe. El modelo lo traduce a error de formulario en vez de
    reventar al guardar.
    """

    def setUp(self):
        self.nestle = Mandante.objects.create(
            nombre="Nestlé", codigo_cliente=Mandante.Cliente.NESTLE
        )
        self.ccaa = Mandante.objects.create(
            nombre="CCAA", codigo_cliente=Mandante.Cliente.NO_DEFINIDO
        )

    def _sin_guardar(self, mandante, naturaleza):
        return Producto(
            nombre="X",
            mandante=mandante,
            familia=Producto.Familia.CREMA,
            naturaleza_comercial=naturaleza,
            categoria=Producto.Categoria.CREMA,
            tipo=Producto.TipoProducto.ENTERA,
            formato=Producto.Formato.GRANEL,
        )

    def test_producto_propio_con_cliente_real_se_rechaza(self):
        producto = self._sin_guardar(
            self.nestle, Producto.NaturalezaComercial.PRODUCTO_PROPIO
        )

        with self.assertRaises(ValidationError) as caso:
            producto.full_clean()

        self.assertIn("naturaleza_comercial", caso.exception.message_dict)

    def test_servicio_a_terceros_sin_cliente_se_rechaza(self):
        producto = self._sin_guardar(
            self.ccaa, Producto.NaturalezaComercial.SERVICIO_TERCEROS
        )

        with self.assertRaises(ValidationError):
            producto.full_clean()

    def test_la_combinacion_correcta_pasa(self):
        self._sin_guardar(
            self.ccaa, Producto.NaturalezaComercial.PRODUCTO_PROPIO
        ).full_clean()
