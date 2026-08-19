"""
Lo derivado no se guarda: se calcula al leer, como el veredicto de calidad.

Los números salen de la fila real del camión JLKD92 del 31-07-2026.
"""

from datetime import date, time
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import TestCase

from usuarios.tenancy import sucursal_predeterminada_pruebas

from .models import ModuloRecepcion, Recepcion


class DerivadosTests(TestCase):
    def setUp(self):
        self.recepcion = Recepcion.objects.create(
            sucursal=sucursal_predeterminada_pruebas(),
            fecha=date(2026, 7, 31),
            tipo_leche=Recepcion.TipoLeche.ENTERA,
            litros=Decimal("5321"),
            kg_romana=Decimal("5430"),
            controles={"grasa": 4.5, "sng": 9.06},
            hora_arribo_porteria=time(7, 45),
            hora_inicio_descarga=time(8, 30),
            hora_termino_descarga=time(8, 45),
            hora_termino_cip=time(9, 15),
        )

    def test_kilos_de_guia_se_derivan_de_los_litros(self):
        self.assertEqual(self.recepcion.kg_guia, Decimal("5480.63"))

    def test_diferencia_de_pesaje(self):
        self.assertEqual(self.recepcion.diferencia_kg, Decimal("-50.63"))

    def test_solidos_totales(self):
        self.assertAlmostEqual(self.recepcion.solidos_totales, 13.56, places=2)
        self.assertAlmostEqual(self.recepcion.solidos_totales_kg, 736.308, places=3)

    def test_permanencia_descuenta_las_dos_horas_libres(self):
        self.assertEqual(self.recepcion.horas_en_planta, 1.5)
        self.assertEqual(self.recepcion.permanencia_horas, 0.0)
        self.assertEqual(self.recepcion.horas_a_pagar, 0)

    def test_sin_arribo_no_hay_horas_a_pagar(self):
        self.recepcion.hora_arribo_porteria = None
        self.assertIsNone(self.recepcion.permanencia_horas)
        self.assertIsNone(self.recepcion.horas_a_pagar)

    def test_tiempo_de_descarga(self):
        self.assertEqual(self.recepcion.tiempo_de_descarga_horas, 0.25)

    def test_pool_de_crioscopia_desde_los_modulos(self):
        ModuloRecepcion.objects.create(
            recepcion=self.recepcion, numero=1, crioscopia=Decimal("-0.521")
        )
        ModuloRecepcion.objects.create(
            recepcion=self.recepcion, numero=2, crioscopia=Decimal("-0.527")
        )

        self.assertEqual(self.recepcion.crioscopia_pool, -0.524)


class DestinoTests(TestCase):
    def _recepcion(self, **extra):
        return Recepcion(
            sucursal=sucursal_predeterminada_pruebas(),
            fecha=date(2026, 7, 31),
            tipo_leche=Recepcion.TipoLeche.ENTERA,
            litros=Decimal("5000"),
            **extra,
        )

    def test_el_numero_de_destino_exige_su_familia(self):
        """`n° 2` a secas no dice de qué. Un número suelto no es trazabilidad."""
        with self.assertRaises(ValidationError):
            self._recepcion(uso_numero=2).full_clean()

    def test_semi_con_su_numero_es_valido(self):
        recepcion = self._recepcion(uso=Recepcion.Uso.SEMI, uso_numero=2)
        recepcion.full_clean()

    def test_despacho_no_lleva_numero(self):
        with self.assertRaises(ValidationError):
            self._recepcion(uso=Recepcion.Uso.DESPACHO, uso_numero=2).full_clean()

    def test_ccaa_y_colun_son_procedencias_validas(self):
        valores = {opcion.value for opcion in Recepcion.Procedencia}
        self.assertIn("CCAA", valores)
        self.assertIn("Colun", valores)
