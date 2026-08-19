"""
Cálculos puros de recepción, sin ORM.

Los números de referencia salen de una fila real del formato
`CCAA.REC.FORM.002.02` (31-07-2026, camión JLKD92): 5.321 L de guía, 5.430 kg
de romana, grasa 4,5 y SNG 9,06.
"""

from datetime import time
from decimal import Decimal

from django.test import TestCase

from . import dominio


class PesajesTests(TestCase):
    def test_kilos_de_guia_desde_litros(self):
        self.assertEqual(dominio.kilos_desde_litros(5321), Decimal("5480.63"))

    def test_sin_litros_no_hay_kilos(self):
        """None no es cero: cero diría que el camión llegó vacío."""
        self.assertIsNone(dominio.kilos_desde_litros(None))

    def test_diferencia_es_romana_menos_guia(self):
        self.assertEqual(
            dominio.diferencia_pesaje(Decimal("5480.63"), Decimal("5430")),
            Decimal("-50.63"),
        )

    def test_sin_romana_no_hay_diferencia(self):
        """Falta el pesaje, no es que coincidan."""
        self.assertIsNone(dominio.diferencia_pesaje(Decimal("5480.63"), None))


class SolidosTests(TestCase):
    def test_totales_son_la_suma_de_grasa_y_sng(self):
        self.assertAlmostEqual(dominio.solidos_totales(4.5, 9.06), 13.56, places=2)

    def test_sin_una_de_las_dos_no_hay_total(self):
        self.assertIsNone(dominio.solidos_totales(4.5, None))

    def test_kilos_de_solidos_sobre_el_pesaje_real(self):
        self.assertAlmostEqual(
            dominio.solidos_totales_kg(5430, 13.56), 736.308, places=3
        )

    def test_sin_pesaje_no_hay_kilos_de_solidos(self):
        self.assertIsNone(dominio.solidos_totales_kg(None, 13.56))
