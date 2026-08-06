"""
Pruebas de la matemática de estandarización.

Sin base de datos: el dominio es puro y se comprueba solo. Lo que se fija aquí
no es que la fórmula esté escrita, sino que **la mezcla que devuelve dé el RC
pedido** — se recalcula el RC desde las cantidades y se compara con el
objetivo.
"""

from unittest import TestCase

from .dominio import Leche, calcular_mezcla, evaluar_rc, litros_a_agregar


# Composiciones representativas de la planta.
#
# La entera va al 3,9 % y no al 3,6 % por una razón que el cálculo destapó:
# **RC 0,422 exige leche entera de al menos ~3,63 % de grasa** (con 8,6 % de
# SNG). Por debajo de eso, mezclar entera con descremada no lo alcanza nunca —
# solo baja el RC—, y habría que agregar crema. Es un límite físico, no del
# programa, y hay una prueba que lo fija más abajo.
ENTERA = Leche(cantidad=30000, grasa=3.9, sng=8.6)
DESCREMADA = Leche(cantidad=30000, grasa=0.05, sng=8.9)


class CalcularMezclaTests(TestCase):

    def _rc_resultante(self, mezcla, entera=ENTERA, descremada=DESCREMADA):
        """Recalcula el RC desde las cantidades que devolvió el cálculo."""
        grasa = mezcla.entera * entera.grasa + mezcla.descremada * descremada.grasa
        sng = mezcla.entera * entera.sng + mezcla.descremada * descremada.sng

        return grasa / sng

    def test_la_mezcla_da_el_rc_pedido(self):
        """
        Lo que importa: no que la fórmula esté escrita, sino que el resultado
        cumpla. Se comprueba recalculando desde las cantidades.
        """
        for objetivo in (0.201, 0.422, 0.30):
            with self.subTest(rc=objetivo):
                mezcla = calcular_mezcla(
                    entera=ENTERA, descremada=DESCREMADA,
                    rc_objetivo=objetivo, volumen=10000,
                )

                self.assertTrue(mezcla.posible, mezcla.motivo)
                self.assertAlmostEqual(
                    self._rc_resultante(mezcla), objetivo, places=3
                )

    def test_las_partes_suman_el_volumen(self):
        mezcla = calcular_mezcla(
            entera=ENTERA, descremada=DESCREMADA, rc_objetivo=0.201, volumen=10000
        )

        self.assertAlmostEqual(mezcla.entera + mezcla.descremada, 10000, places=0)

    def test_un_rc_mas_alto_pide_mas_leche_entera(self):
        """La entera es la que aporta grasa: a más RC, más entera."""
        baja = calcular_mezcla(
            entera=ENTERA, descremada=DESCREMADA, rc_objetivo=0.201, volumen=10000
        )
        alta = calcular_mezcla(
            entera=ENTERA, descremada=DESCREMADA, rc_objetivo=0.422, volumen=10000
        )

        self.assertGreater(alta.entera, baja.entera)

    # ------------------------------------------------ objetivos imposibles

    def test_un_rc_por_encima_de_la_entera_no_se_alcanza(self):
        """
        Mezclar entera con descremada solo **baja** el RC: nunca lo sube por
        encima del de la entera. Pedir más exigiría agregar crema.

        La fórmula devolvería aquí un volumen mayor que el total —o negativo de
        descremada—. Tiene que decirlo, no entregar un número que alguien
        termine tecleando en una válvula.
        """
        mezcla = calcular_mezcla(
            entera=ENTERA, descremada=DESCREMADA, rc_objetivo=0.60, volumen=10000
        )

        self.assertFalse(mezcla.posible)
        self.assertIn("no se alcanza", mezcla.motivo)
        self.assertEqual(mezcla.entera, 0)

    def test_rc_0422_no_se_alcanza_con_entera_pobre(self):
        """
        Un límite operacional real, no del programa: **RC 0,422 exige leche
        entera de al menos ~3,63 % de grasa** con 8,6 % de SNG. Al 3,6 % la
        entera está en 0,4186 y ya no llega.

        Vale la pena que el sistema lo diga con ese detalle: en planta se
        traduce en «esta leche no da para el producto de RC 0,422», que es una
        decisión de qué producir, no un error de captura.
        """
        pobre = Leche(cantidad=30000, grasa=3.6, sng=8.6)

        mezcla = calcular_mezcla(
            entera=pobre, descremada=DESCREMADA, rc_objetivo=0.422, volumen=10000
        )

        self.assertFalse(mezcla.posible)
        self.assertIn("0.4186", mezcla.motivo)

    def test_un_rc_por_debajo_de_la_descremada_tampoco(self):
        mezcla = calcular_mezcla(
            entera=ENTERA, descremada=DESCREMADA, rc_objetivo=0.001, volumen=10000
        )

        self.assertFalse(mezcla.posible)

    def test_dos_leches_del_mismo_rc_no_mueven_nada(self):
        """Mezclar dos leches iguales da esa misma leche."""
        gemela = Leche(cantidad=10000, grasa=3.9, sng=8.6)

        mezcla = calcular_mezcla(
            entera=ENTERA, descremada=gemela, rc_objetivo=0.201, volumen=5000
        )

        self.assertFalse(mezcla.posible)
        self.assertIn("mismo RC", mezcla.motivo)

    def test_si_ya_estan_al_objetivo_se_usa_la_que_hay(self):
        gemela = Leche(cantidad=10000, grasa=3.9, sng=8.6)

        mezcla = calcular_mezcla(
            entera=ENTERA, descremada=gemela,
            rc_objetivo=ENTERA.rc, volumen=5000,
        )

        self.assertTrue(mezcla.posible)
        self.assertEqual(mezcla.entera, 5000)

    def test_un_volumen_no_positivo_se_rechaza(self):
        self.assertFalse(
            calcular_mezcla(
                entera=ENTERA, descremada=DESCREMADA, rc_objetivo=0.2, volumen=0
            ).posible
        )

    # ------------------------------------------------------ falta de leche

    def test_si_no_alcanza_la_leche_avisa_pero_calcula(self):
        """
        Se avisa en vez de fallar: el operador puede estar planificando contra
        un silo que todavía se está llenando, y negarle el cálculo no le ayuda
        a decidir.
        """
        poca = Leche(cantidad=100, grasa=3.6, sng=8.6)

        mezcla = calcular_mezcla(
            entera=poca, descremada=DESCREMADA, rc_objetivo=0.201, volumen=10000
        )

        self.assertTrue(mezcla.posible)
        self.assertTrue(any("Faltan" in a for a in mezcla.avisos))

    def test_con_leche_suficiente_no_hay_avisos(self):
        mezcla = calcular_mezcla(
            entera=ENTERA, descremada=DESCREMADA, rc_objetivo=0.201, volumen=10000
        )

        self.assertEqual(mezcla.avisos, [])


class EvaluarRcTests(TestCase):
    """
    El RC real casi nunca sale igual al calculado: la leche del silo no es
    exactamente la que se midió. Por eso el procedimiento incluye analizar
    después de agitar y corregir.
    """

    def test_dentro_de_tolerancia_cumple(self):
        resultado = evaluar_rc(grasa=1.79, sng=8.9, rc_objetivo=0.201)

        self.assertTrue(resultado.cumple)

    def test_con_grasa_de_mas_pide_descremada(self):
        resultado = evaluar_rc(grasa=2.20, sng=8.9, rc_objetivo=0.201)

        self.assertFalse(resultado.cumple)
        self.assertEqual(resultado.agregar, "descremada")
        self.assertIn("sobra", resultado.motivo)

    def test_con_grasa_de_menos_pide_entera(self):
        resultado = evaluar_rc(grasa=1.30, sng=8.9, rc_objetivo=0.201)

        self.assertFalse(resultado.cumple)
        self.assertEqual(resultado.agregar, "entera")
        self.assertIn("falta", resultado.motivo)

    def test_la_tolerancia_es_un_parametro(self):
        """La define Calidad; va como parámetro para que cambiarla no sea
        buscar un número por el código."""
        medida = {"grasa": 1.85, "sng": 8.9, "rc_objetivo": 0.201}

        self.assertFalse(evaluar_rc(**medida, tolerancia=0.001).cumple)
        self.assertTrue(evaluar_rc(**medida, tolerancia=0.02).cumple)

    def test_sin_solidos_no_hay_rc(self):
        resultado = evaluar_rc(grasa=3.0, sng=0, rc_objetivo=0.201)

        self.assertFalse(resultado.cumple)
        self.assertIsNone(resultado.rc_real)
        self.assertIn("revisa el análisis", resultado.motivo)


class LitrosAAgregarTests(TestCase):

    def test_lo_que_se_agrega_deja_el_rc_en_el_objetivo(self):
        """Se comprueba recalculando, no confiando en la fórmula."""
        volumen, grasa, sng, objetivo = 10000.0, 2.20, 8.9, 0.201

        litros = litros_a_agregar(
            volumen_actual=volumen, grasa=grasa, sng=sng,
            rc_objetivo=objetivo, correctora=DESCREMADA,
        )

        self.assertIsNotNone(litros)

        grasa_final = volumen * grasa + litros * DESCREMADA.grasa
        sng_final = volumen * sng + litros * DESCREMADA.sng

        self.assertAlmostEqual(grasa_final / sng_final, objetivo, places=3)

    def test_una_correctora_que_no_mueve_el_rc_devuelve_none(self):
        """
        Distinto de «cero litros»: con esa leche la corrección no existe, y
        confundirlo dejaría a alguien esperando que no hiciera falta agregar
        nada.
        """
        inutil = Leche(cantidad=1000, grasa=0.201, sng=1.0)

        self.assertIsNone(
            litros_a_agregar(
                volumen_actual=10000, grasa=2.20, sng=8.9,
                rc_objetivo=0.201, correctora=inutil,
            )
        )

    def test_si_no_hace_falta_corregir_devuelve_none(self):
        self.assertIsNone(
            litros_a_agregar(
                volumen_actual=10000, grasa=1.30, sng=8.9,
                rc_objetivo=0.201, correctora=DESCREMADA,
            )
        )
