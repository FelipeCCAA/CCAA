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


class CrioscopiaPoolTests(TestCase):
    def test_promedio_de_los_modulos_medidos(self):
        self.assertEqual(dominio.crioscopia_pool([-0.521, -0.532, -0.53]), -0.528)

    def test_ignora_los_modulos_sin_lectura(self):
        self.assertEqual(dominio.crioscopia_pool([-0.52, None, None]), -0.52)

    def test_sin_ninguna_lectura_no_hay_pool(self):
        self.assertIsNone(dominio.crioscopia_pool([None, None]))
        self.assertIsNone(dominio.crioscopia_pool([]))


class EvaluacionAmpliadaTests(TestCase):
    def test_una_crioscopia_de_modulo_fuera_de_rango_retiene(self):
        """
        Basta con que UN compartimiento venga aguado: la leche del camión se
        mezcla en el silo, así que el promedio escondería el módulo malo.
        """
        evaluacion = dominio.evaluar_recepcion(
            {"delvo": "Negativo"}, crioscopias=[(1, -0.52), (2, -0.505)]
        )

        self.assertEqual(evaluacion.estado, "retenida")
        self.assertTrue(any("M2" in motivo for motivo in evaluacion.motivos))

    def test_el_motivo_usa_el_numero_del_modulo_no_su_posicion_en_la_lista(self):
        """
        Los módulos registrados no tienen por qué ser contiguos: un camión
        puede traer M1 y M3, sin M2. Si el motivo se armara enumerando la
        lista por posición, el segundo par (numero=3) se etiquetaría "M2" —
        el motivo es lo que le dice a Calidad qué compartimiento
        re-muestrear, y culpar al módulo equivocado manda a revisar leche
        sana y deja pasar la aguada.
        """
        evaluacion = dominio.evaluar_recepcion(
            {"delvo": "Negativo"}, crioscopias=[(1, -0.52), (3, -0.505)]
        )

        self.assertEqual(evaluacion.estado, "retenida")
        self.assertTrue(any("M3" in motivo for motivo in evaluacion.motivos))
        self.assertFalse(any("M2" in motivo for motivo in evaluacion.motivos))

    def test_todas_las_crioscopias_en_rango_liberan(self):
        evaluacion = dominio.evaluar_recepcion(
            {"delvo": "Negativo"}, crioscopias=[(1, -0.52), (2, -0.53)]
        )

        self.assertEqual(evaluacion.estado, "liberada")

    def test_un_item_organoleptico_no_conforme_retiene(self):
        evaluacion = dominio.evaluar_recepcion(
            {"delvo": "Negativo", "sangre": "No conforme"}
        )

        self.assertEqual(evaluacion.estado, "retenida")
        self.assertTrue(any("sangre" in motivo.lower() for motivo in evaluacion.motivos))

    def test_el_organoleptico_viejo_se_sigue_entendiendo(self):
        """Las filas históricas traen una sola clave; no se las deja de leer."""
        evaluacion = dominio.evaluar_recepcion(
            {"delvo": "Negativo", "organoleptico": "No conforme"}
        )

        self.assertEqual(evaluacion.estado, "retenida")

    def test_el_ph_del_camion_fuera_de_rango_retiene(self):
        evaluacion = dominio.evaluar_recepcion({"delvo": "Negativo"}, ph_camion=9.2)

        self.assertEqual(evaluacion.estado, "retenida")
        self.assertTrue(any("camión" in motivo for motivo in evaluacion.motivos))

    def test_el_ph_del_camion_no_es_el_de_la_leche(self):
        """
        7,0 es válido para el enjuague del camión (5,5-8,5) y estaría fuera del
        rango de la leche (6,5-6,9 lo admite, pero 8,0 no). Confundirlos haría
        que el agua retuviera leche conforme.
        """
        evaluacion = dominio.evaluar_recepcion(
            {"delvo": "Negativo", "ph": 6.7}, ph_camion=8.0
        )

        self.assertEqual(evaluacion.estado, "liberada")


class BloqueosDeCierreTests(TestCase):
    def test_positivo_sin_busqueda_no_cierra(self):
        """
        Un positivo retiene, y ahí terminaba todo. El primer eslabón de la
        cadena de REGLAS_DE_PLANTA §1.2 es buscar al proveedor: sin eso, el
        registro dice que hubo antibióticos y no dice de quién.
        """
        bloqueos = dominio.bloqueos_de_cierre({"delvo": "Positivo"})

        self.assertEqual(len(bloqueos), 1)
        self.assertIn("proveedor", bloqueos[0].lower())

    def test_positivo_con_busqueda_cierra(self):
        self.assertEqual(
            dominio.bloqueos_de_cierre(
                {"delvo": "Positivo"}, busquedas_a_proveedor=1
            ),
            [],
        )

    def test_inhibidores_positivos_valen_igual_que_el_delvo(self):
        self.assertEqual(
            len(dominio.bloqueos_de_cierre({"inhibidores": "Positivo"})), 1
        )

    def test_sin_positivos_no_hay_bloqueo(self):
        self.assertEqual(dominio.bloqueos_de_cierre({"delvo": "Negativo"}), [])
