"""
Pruebas de la codificación de lote (CCAA.Calidad.POE.009.02).

Los ejemplos salen literalmente del POE, de la elaboración del 16-07-2025
—día juliano 197—, que es la referencia contra la que se puede discutir con
planta si algún día el código no cuadra.

`SimpleTestCase` y no `TestCase`: son funciones puras y no tocan la base.
"""

from datetime import date

from django.test import SimpleTestCase

from .dominio import (
    TIPO_CREMA,
    TIPO_LEP,
    TIPO_PRECONDENSADO,
    codigo_lote_valido,
    generar_codigo_lote,
)


class GenerarCodigoLoteTests(SimpleTestCase):
    """Ejemplos del POE.009.02, elaboración del 16-07-2025."""

    fecha = date(2025, 7, 16)  # día juliano 197

    def test_crema_sin_sufijo(self):
        self.assertEqual(generar_codigo_lote(self.fecha, TIPO_CREMA), "CCAA5197")

    def test_precondensado_nacional_lleva_N(self):
        self.assertEqual(
            generar_codigo_lote(self.fecha, TIPO_PRECONDENSADO, nacional=True),
            "CCAA5197N",
        )

    def test_precondensado_no_nacional_sin_sufijo(self):
        self.assertEqual(
            generar_codigo_lote(self.fecha, TIPO_PRECONDENSADO), "CCAA5197"
        )

    def test_lep_lleva_el_numero_de_su_torre(self):
        self.assertEqual(
            generar_codigo_lote(self.fecha, TIPO_LEP, linea="E1"), "CCAA51971"
        )
        self.assertEqual(
            generar_codigo_lote(self.fecha, TIPO_LEP, linea="E2"), "CCAA51972"
        )

    def test_la_segunda_produccion_del_dia_agrega_A(self):
        """Es lo que el POE indica para no repetir el código en un mismo día."""
        self.assertEqual(
            generar_codigo_lote(
                self.fecha, TIPO_LEP, linea="E1", segunda_produccion=True
            ),
            "CCAA51971A",
        )

    def test_un_tipo_desconocido_falla_en_vez_de_inventar(self):
        """
        Devolver un código sin sufijo para un producto que no se sabe cómo
        codificar sería peor que fallar: saldría a planta como si fuera bueno.
        """
        with self.assertRaises(ValueError):
            generar_codigo_lote(self.fecha, "queso")


class BaseDelCodigoTests(SimpleTestCase):
    """La parte que no depende del producto: año y día juliano."""

    def test_toma_el_ultimo_digito_del_anio(self):
        self.assertTrue(
            generar_codigo_lote(date(2026, 1, 1), TIPO_CREMA).startswith("CCAA6")
        )
        self.assertTrue(
            generar_codigo_lote(date(2030, 1, 1), TIPO_CREMA).startswith("CCAA0")
        )

    def test_el_dia_juliano_va_con_tres_digitos(self):
        """El 1 de enero es 001, no 1: si no, el código cambia de largo."""
        self.assertEqual(generar_codigo_lote(date(2025, 1, 1), TIPO_CREMA), "CCAA5001")
        self.assertEqual(generar_codigo_lote(date(2025, 12, 31), TIPO_CREMA), "CCAA5365")

    def test_el_anio_bisiesto_llega_a_366(self):
        self.assertEqual(generar_codigo_lote(date(2024, 12, 31), TIPO_CREMA), "CCAA4366")

    def test_una_linea_desconocida_no_pone_sufijo(self):
        """
        Mejor un código sin número de torre que uno con un número inventado:
        el operador ve que falta y lo corrige.
        """
        self.assertEqual(
            generar_codigo_lote(date(2025, 7, 16), TIPO_LEP, linea="E9"), "CCAA5197"
        )


class CodigoLoteValidoTests(SimpleTestCase):
    def test_acepta_las_formas_del_poe(self):
        for codigo in ["CCAA5197", "CCAA5197N", "CCAA51971", "CCAA51972", "CCAA51971A"]:
            with self.subTest(codigo=codigo):
                self.assertTrue(codigo_lote_valido(codigo))

    def test_rechaza_lo_que_no_tiene_esa_forma(self):
        for codigo in ["6134", "", "CCAA", "ccaa5197", "CCAA519", "LOTE-1"]:
            with self.subTest(codigo=codigo):
                self.assertFalse(codigo_lote_valido(codigo))

    def test_no_revienta_con_None(self):
        self.assertFalse(codigo_lote_valido(None))


class NoEsUnValidadorDelModeloTests(SimpleTestCase):
    """
    El validador informa, no restringe.

    El histórico de planta trae códigos que no siguen el POE, y hay que poder
    registrarlos igual: un registro de trazabilidad tiene que admitir lo que
    de verdad pasó. Si algún día alguien conecta esto al `clean()` de Lote,
    esta prueba explica por qué no debería.
    """

    def test_hay_codigos_reales_que_el_patron_rechaza(self):
        for codigo in ["CR-0088", "6134", "LOTE ANTIGUO 12"]:
            with self.subTest(codigo=codigo):
                self.assertFalse(codigo_lote_valido(codigo))
