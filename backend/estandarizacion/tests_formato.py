from decimal import Decimal

from django.test import SimpleTestCase

from .dominio import formato_cantidad


class FormatoCantidadTests(SimpleTestCase):
    """
    Los motivos de rechazo al transferir un vale interpolan litros de silo
    —`DecimalField(decimal_places=2)`— directo en el texto. Sin pasar por
    aquí, «8000.00 L» se lee como ocho mil coma cero, no como ocho mil litros.
    """

    def test_miles_con_punto_decimales_con_coma(self):
        self.assertEqual(formato_cantidad(Decimal("8000.00")), "8.000")
        self.assertEqual(formato_cantidad(Decimal("1500.000")), "1.500")

    def test_conserva_decimales_significativos(self):
        self.assertEqual(formato_cantidad(Decimal("1234.5")), "1.234,5")

    def test_el_tope_de_decimales_es_configurable(self):
        self.assertEqual(formato_cantidad(Decimal("0.3456"), decimales=2), "0,35")
