"""
Pruebas de la codificación de lote.

Forma vigente: `CCAA` + último dígito del año + día juliano (3) + SKU del
producto + `-` + correlativo del día (2). Ejemplo del 16-07-2025 —día juliano
197— con el SKU `LEP25`: `CCAA5197LEP25-01`.

Reemplaza al esquema del POE.009.02, donde el sufijo codificaba la torre de
secado (E1→1, E2→2) y el uso nacional del precondensado (N). Ese dato ahora
vive dentro del SKU, que es donde se mantiene una sola vez; duplicarlo en el
código abría la puerta a que las dos copias se contradijeran.

`SimpleTestCase` y no `TestCase`: son funciones puras y no tocan la base.
"""

from datetime import date

from django.test import SimpleTestCase

from .dominio import codigo_lote_valido, generar_codigo_lote


class GenerarCodigoLoteTests(SimpleTestCase):

    def setUp(self):
        self.fecha = date(2025, 7, 16)  # día juliano 197

    def test_mezcla_anio_dia_juliano_y_sku(self):
        self.assertEqual(
            generar_codigo_lote(self.fecha, "LEP25"), "CCAA5197LEP25-01"
        )

    def test_el_correlativo_distingue_dos_lotes_del_mismo_producto_y_dia(self):
        """
        Es lo único que los separa: mismo día, mismo producto, mismo SKU. Sin
        él, dos corridas distintas comparten identidad y la trazabilidad no
        puede decir de cuál salió una bolsa.
        """
        primero = generar_codigo_lote(self.fecha, "LEP25", 1)
        segundo = generar_codigo_lote(self.fecha, "LEP25", 2)

        self.assertEqual(primero, "CCAA5197LEP25-01")
        self.assertEqual(segundo, "CCAA5197LEP25-02")
        self.assertNotEqual(primero, segundo)

    def test_el_correlativo_va_desde_el_primero(self):
        """
        Ponerlo solo a partir del segundo dejaría dos formas conviviendo, y
        quien lee, ordena o busca códigos tendría que conocer la excepción.
        """
        self.assertTrue(generar_codigo_lote(self.fecha, "LEP25").endswith("-01"))

    def test_el_correlativo_lleva_dos_digitos(self):
        """Con relleno, el orden alfabético coincide con el cronológico."""
        self.assertEqual(
            generar_codigo_lote(self.fecha, "LEP25", 9), "CCAA5197LEP25-09"
        )

    def test_un_dia_de_mas_de_99_lotes_no_se_trunca(self):
        """Improbable, pero truncar inventaría un código repetido."""
        self.assertEqual(
            generar_codigo_lote(self.fecha, "LEP25", 100), "CCAA5197LEP25-100"
        )

    def test_dos_productos_del_mismo_dia_se_distinguen_por_el_sku(self):
        self.assertNotEqual(
            generar_codigo_lote(self.fecha, "LEP25"),
            generar_codigo_lote(self.fecha, "CRE10"),
        )

    def test_sin_sku_no_se_inventa_un_codigo(self):
        """
        El SKU es la única pieza que el sistema no puede deducir. Rellenarla
        imprimiría en la bolsa algo que no identifica al producto, y una bolsa
        mal identificada es peor que una sin código automático.
        """
        for vacio in ["", "   ", None]:
            with self.subTest(sku=vacio):
                self.assertIsNone(generar_codigo_lote(self.fecha, vacio))

    def test_el_sku_se_limpia_de_espacios(self):
        self.assertEqual(
            generar_codigo_lote(self.fecha, "  LEP25 "), "CCAA5197LEP25-01"
        )

    def test_el_anio_es_el_ultimo_digito(self):
        self.assertTrue(generar_codigo_lote(date(2026, 1, 1), "X").startswith("CCAA6"))
        self.assertTrue(generar_codigo_lote(date(2030, 1, 1), "X").startswith("CCAA0"))

    def test_el_dia_juliano_va_con_tres_digitos(self):
        self.assertEqual(generar_codigo_lote(date(2025, 1, 1), "X"), "CCAA5001X-01")
        self.assertEqual(generar_codigo_lote(date(2025, 12, 31), "X"), "CCAA5365X-01")

    def test_un_anio_bisiesto_llega_a_366(self):
        self.assertEqual(generar_codigo_lote(date(2024, 12, 31), "X"), "CCAA4366X-01")


class CodigoLoteValidoTests(SimpleTestCase):
    """
    Avisa, no restringe (CLAUDE.md). Sirve para marcar en pantalla un código
    con forma rara, nunca para impedir que se guarde.
    """

    def test_acepta_la_forma_vigente(self):
        for codigo in ["CCAA5197LEP25-01", "CCAA6212CRE10-12", "CCAA5001X-01"]:
            with self.subTest(codigo=codigo):
                self.assertTrue(codigo_lote_valido(codigo))

    def test_rechaza_lo_que_no_tiene_esa_forma(self):
        for codigo in ["6134", "", "CCAA", "ccaa5197lep25-01", "CCAA519LEP-01"]:
            with self.subTest(codigo=codigo):
                self.assertFalse(codigo_lote_valido(codigo))

    def test_los_codigos_del_poe_anterior_ya_no_tienen_la_forma_vigente(self):
        """
        Y aun así se registran: el histórico de planta está lleno de ellos.
        Que esto devuelva False es un aviso en pantalla, no un bloqueo — por
        eso `codigo_lote_valido` no cuelga del `clean()` del modelo.
        """
        for antiguo in ["CCAA5197", "CCAA5197N", "CCAA51971", "CCAA51971A"]:
            with self.subTest(codigo=antiguo):
                self.assertFalse(codigo_lote_valido(antiguo))

    def test_sin_correlativo_no_es_valido(self):
        self.assertFalse(codigo_lote_valido("CCAA5197LEP25"))

    def test_no_revienta_con_None(self):
        self.assertFalse(codigo_lote_valido(None))
