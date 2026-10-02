from decimal import Decimal

from django.test import SimpleTestCase

from .formato import formato_cantidad


class FormatoCantidadTests(SimpleTestCase):
    """
    `str(Decimal(...))` imprime en formato norteamericano: un mensaje que
    interpola un `Decimal` sin pasar por aquí dice «1500.000» donde debería
    decir «1.500», y «8000.00 L» se lee ocho mil coma cero.
    """

    def test_miles_con_punto_decimales_con_coma(self):
        self.assertEqual(formato_cantidad(Decimal("1500.000")), "1.500")
        self.assertEqual(formato_cantidad(Decimal("1234.5")), "1.234,5")

    def test_sin_decimales_no_arrastra_ceros(self):
        self.assertEqual(formato_cantidad(Decimal("500.000")), "500")
        self.assertEqual(formato_cantidad(Decimal("8000.00")), "8.000")

    def test_admite_numeros_simples(self):
        self.assertEqual(formato_cantidad(0), "0")
        self.assertEqual(formato_cantidad(25000), "25.000")

    def test_conserva_decimales_significativos(self):
        self.assertEqual(formato_cantidad(Decimal("1234.5")), "1.234,5")

    def test_el_tope_de_decimales_es_configurable(self):
        self.assertEqual(formato_cantidad(Decimal("0.3456"), decimales=2), "0,35")
