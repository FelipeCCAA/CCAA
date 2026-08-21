"""
Dos productos no comparten SKU.

El SKU identifica un producto y **se imprime**. Que dos filas del maestro
compartan uno significa que dos cosas distintas salen al mundo con la misma
identidad: la especificación que se audita, la receta que descuenta material y
el certificado que se emite dejan de tener un dueño único.

Hasta ahora nada lo impedía. El maestro llegó a tener seis grupos repetidos:
dos venían del sembrado de demo pisando el catálogo real, y cuatro del propio
archivo de origen, donde dos productos comparten los seis segmentos.

El mecanismo para desempatarlos ya existía —`Producto.variante`, que
`generar_sku` admite y que lleva el SKU de 12 a 14 dígitos—; lo que faltaba era
que el sistema **exigiera** usarlo.
"""

from django.core.exceptions import ValidationError
from django.db.utils import IntegrityError
from django.test import TestCase

from maestros.models import Mandante, Producto


class SkuUnicoTests(TestCase):
    def setUp(self):
        self.mandante = Mandante.objects.create(
            nombre="Nestlé", codigo_cliente="nestle"
        )

    def _producto(self, nombre, **extra):
        datos = {
            "nombre": nombre,
            "familia": Producto.Familia.POLVO,
            "mandante": self.mandante,
            "naturaleza_comercial": "servicio_terceros",
            "categoria": "leche_polvo",
            "tipo": "entera",
            "formato": "saco_25kg",
            "mercado": "local",
        }
        datos.update(extra)
        return Producto.objects.create(**datos)

    def test_dos_productos_con_los_mismos_atributos_no_conviven(self):
        primero = self._producto("Leche entera en polvo")
        self.assertNotEqual(primero.codigo, "")

        with self.assertRaises((IntegrityError, ValidationError)):
            self._producto("Leche Entera Estándar 28% NE")

    def test_el_aviso_nombra_al_producto_en_conflicto_y_la_salida(self):
        """
        Un `IntegrityError` crudo no le dice al operador qué hacer. La salida
        es `variante`, y el mensaje tiene que decirlo.
        """
        self._producto("Leche entera en polvo")

        otro = Producto(
            nombre="Leche Entera Estándar 28% NE",
            familia=Producto.Familia.POLVO,
            mandante=self.mandante,
            naturaleza_comercial="servicio_terceros",
            categoria="leche_polvo",
            tipo="entera",
            formato="saco_25kg",
            mercado="local",
        )

        with self.assertRaises(ValidationError) as caso:
            otro.full_clean()

        mensaje = str(caso.exception)
        self.assertIn("Leche entera en polvo", mensaje)
        self.assertIn("variante", mensaje.lower())

    def test_con_variante_distinta_si_conviven(self):
        primero = self._producto("Leche entera en polvo")
        segundo = self._producto("Leche Entera Estándar 28% NE", variante=1)

        self.assertNotEqual(primero.codigo, segundo.codigo)
        self.assertEqual(len(primero.codigo), 12)
        self.assertEqual(len(segundo.codigo), 14)

    def test_los_productos_sin_sku_no_chocan_entre_si(self):
        """
        Un producto sin atributos cargados no genera SKU y conserva el que
        tenga —vacío, en este caso—. Si el vacío contara como repetido, el
        maestro no admitiría dos productos a medio configurar.
        """
        uno = self._producto("Sin atributos 1", categoria="", tipo="", formato="")
        dos = self._producto("Sin atributos 2", categoria="", tipo="", formato="")

        self.assertEqual(uno.codigo, "")
        self.assertEqual(dos.codigo, "")
