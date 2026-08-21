from datetime import date

from django.test import SimpleTestCase

from .dominio import codigo_lote_valido, generar_codigo_lote


class GenerarCodigoLoteTests(SimpleTestCase):
    fecha = date(2026, 8, 20)

    def test_arma_el_codigo_con_anio_dia_juliano_sigla_y_correlativo(self):
        self.assertEqual(generar_codigo_lote(self.fecha, "E1"), "CCAA6232E1-01")

    def test_el_correlativo_va_siempre_desde_01(self):
        self.assertTrue(generar_codigo_lote(self.fecha, "E1").endswith("-01"))

    def test_el_correlativo_distingue_dos_corridas_de_la_misma_maquina(self):
        self.assertEqual(generar_codigo_lote(self.fecha, "E1", 2), "CCAA6232E1-02")

    def test_dos_maquinas_el_mismo_dia_no_comparten_codigo(self):
        self.assertNotEqual(generar_codigo_lote(self.fecha, "E1"), generar_codigo_lote(self.fecha, "E2"))

    def test_sin_sigla_no_hay_codigo(self):
        self.assertIsNone(generar_codigo_lote(self.fecha, ""))
        self.assertIsNone(generar_codigo_lote(self.fecha, None))

    def test_el_correlativo_de_tres_digitos_no_se_recorta(self):
        self.assertEqual(generar_codigo_lote(self.fecha, "E1", 100), "CCAA6232E1-100")

    def test_el_primero_de_enero_es_el_dia_001(self):
        self.assertEqual(generar_codigo_lote(date(2026, 1, 1), "E1"), "CCAA6001E1-01")


class CodigoLoteValidoTests(SimpleTestCase):
    def test_acepta_la_forma_vigente(self):
        self.assertTrue(codigo_lote_valido("CCAA6232E1-01"))
        self.assertTrue(codigo_lote_valido("CCAA6232VB-100"))

    def test_rechaza_el_formato_anterior_con_sku(self):
        self.assertFalse(codigo_lote_valido("CCAA6212010102010201-01"))

    def test_rechaza_basura(self):
        self.assertFalse(codigo_lote_valido(""))
        self.assertFalse(codigo_lote_valido(None))
        self.assertFalse(codigo_lote_valido("LOTE-1"))
