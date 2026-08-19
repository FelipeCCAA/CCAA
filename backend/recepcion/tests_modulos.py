"""
Un camión, un registro. Solo la crioscopía se mide por compartimiento.

La planilla pone M1..M4 en una sola fila porque un camión trae hasta cuatro
módulos, pero los litros, el silo y el destino son del camión. Aquí se fija
esa forma.
"""

from datetime import date
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import TestCase

from usuarios.tenancy import sucursal_predeterminada_pruebas

from .models import ModuloRecepcion, Recepcion


class ModuloRecepcionTests(TestCase):
    def _recepcion(self):
        return Recepcion.objects.create(
            sucursal=sucursal_predeterminada_pruebas(),
            fecha=date(2026, 7, 31),
            tipo_leche=Recepcion.TipoLeche.ENTERA,
            litros=Decimal("19339"),
        )

    def test_un_camion_lleva_varios_modulos_con_su_crioscopia(self):
        recepcion = self._recepcion()

        for numero, valor in ((1, "-0.521"), (2, "-0.532"), (3, "-0.530"), (4, "-0.534")):
            ModuloRecepcion.objects.create(
                recepcion=recepcion, numero=numero, crioscopia=Decimal(valor)
            )

        self.assertEqual(recepcion.modulos.count(), 4)
        self.assertEqual(
            [m.numero for m in recepcion.modulos.order_by("numero")], [1, 2, 3, 4]
        )

    def test_no_se_repite_el_numero_de_modulo_en_el_mismo_camion(self):
        recepcion = self._recepcion()
        ModuloRecepcion.objects.create(recepcion=recepcion, numero=1)

        with self.assertRaises(Exception):
            ModuloRecepcion.objects.create(recepcion=recepcion, numero=1)

    def test_el_modulo_no_lleva_litros(self):
        """Los litros son del camión: que el módulo no los tenga es la regla."""
        self.assertFalse(
            any(campo.name == "litros" for campo in ModuloRecepcion._meta.get_fields())
        )

    def test_la_recepcion_ya_no_tiene_modulo_ni_llegada(self):
        nombres = {campo.name for campo in Recepcion._meta.get_fields()}

        self.assertNotIn("modulo", nombres)
        self.assertNotIn("llegada_id", nombres)
