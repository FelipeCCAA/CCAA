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


class PermanenciaTests(TestCase):
    def test_descuenta_las_dos_horas_libres(self):
        """Arriba 08:00, termina CIP 11:30: 3,5 h en planta, 1,5 a contar."""
        resultado = dominio.permanencia(time(8, 0), time(11, 30))

        self.assertEqual(resultado.horas_en_planta, 3.5)
        self.assertEqual(resultado.horas, 1.5)
        self.assertEqual(resultado.motivo, "")

    def test_dentro_del_limite_no_acumula(self):
        resultado = dominio.permanencia(time(8, 0), time(9, 30))

        self.assertEqual(resultado.horas, 0.0)

    def test_sin_arribo_no_devuelve_cero_sino_nada(self):
        """
        El defecto de la planilla: la hora programa estaba vacía en 602 de 603
        filas y el cálculo la trataba como cero, así que cada camión 'pagaba'
        la hora del reloj menos dos. Un dato que falta no es un dato que vale
        cero.
        """
        resultado = dominio.permanencia(None, time(11, 30))

        self.assertIsNone(resultado.horas)
        self.assertIsNone(resultado.horas_en_planta)
        self.assertIn("arribo", resultado.motivo.lower())

    def test_sin_termino_de_cip_tampoco(self):
        resultado = dominio.permanencia(time(8, 0), None)

        self.assertIsNone(resultado.horas)
        self.assertIn("cip", resultado.motivo.lower())

    def test_cruzar_la_medianoche_no_da_negativo(self):
        """Turno C: arriba 23:30, termina CIP 01:00. Son 1,5 h, no -22,5."""
        resultado = dominio.permanencia(time(23, 30), time(1, 0))

        self.assertEqual(resultado.horas_en_planta, 1.5)
        self.assertEqual(resultado.horas, 0.0)


class HorasAPagarTests(TestCase):
    def test_redondeo_comercial_sube_sobre_la_media_hora(self):
        self.assertEqual(dominio.horas_a_pagar(7.25), 7)
        self.assertEqual(dominio.horas_a_pagar(8.42), 8)
        self.assertEqual(dominio.horas_a_pagar(16.67), 17)

    def test_la_media_hora_exacta_no_sube(self):
        """El formato usa `>0,5`, no `>=`. Se respeta."""
        self.assertEqual(dominio.horas_a_pagar(9.5), 9)

    def test_sin_permanencia_no_hay_horas_que_pagar(self):
        self.assertIsNone(dominio.horas_a_pagar(None))


class HorasEntreTests(TestCase):
    def test_diferencia_simple(self):
        self.assertEqual(dominio.horas_entre(time(8, 30), time(10, 0)), 1.5)

    def test_falta_un_extremo(self):
        self.assertIsNone(dominio.horas_entre(time(8, 30), None))
