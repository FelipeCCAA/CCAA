"""
La sigla del equipo: lo que entra en el código de lote.

`Equipo.codigo` es un slug pensado para identificar y comparar
(`carga_precondensado`, 19 caracteres). Meterlo en un código impreso daría
`CCAA6232carga_precondensado-01`. La sigla es corta, estable y **se
configura**: no es un mapa en el código, porque qué máquinas tiene esta
planta es configuración del despliegue.
"""

from django.db.utils import IntegrityError
from django.test import TestCase

from maestros.models import Equipo


class SiglaDeEquipoTests(TestCase):
    def test_los_equipos_sembrados_traen_su_sigla(self):
        self.assertEqual(Equipo.objects.get(codigo="e1").sigla, "E1")
        self.assertEqual(Equipo.objects.get(codigo="scheffers2").sigla, "S2")
        self.assertEqual(Equipo.objects.get(codigo="rovema4").sigla, "R4")

    def test_dos_equipos_no_comparten_sigla(self):
        """
        Dos siglas iguales producen dos corridas distintas con el mismo
        código de lote, que es exactamente lo que este cambio viene a
        impedir.
        """
        e1 = Equipo.objects.get(codigo="e1")

        with self.assertRaises(IntegrityError):
            Equipo.objects.create(
                sucursal_id=e1.sucursal_id,
                codigo="torre-nueva",
                nombre="Torre nueva",
                tipo=e1.tipo,
                sigla="E1",
            )

    def test_la_sigla_vacia_puede_repetirse(self):
        """
        Un equipo que no encabeza lotes no necesita sigla. Exigirla a todos
        obligaría a inventar dos letras para una bomba.
        """
        e1 = Equipo.objects.get(codigo="e1")
        Equipo.objects.create(
            sucursal_id=e1.sucursal_id, codigo="bomba-1", nombre="Bomba 1",
            tipo=e1.tipo, sigla="",
        )
        Equipo.objects.create(
            sucursal_id=e1.sucursal_id, codigo="bomba-2", nombre="Bomba 2",
            tipo=e1.tipo, sigla="",
        )

        self.assertEqual(
            Equipo.objects.filter(
                codigo__in=["bomba-1", "bomba-2"], sigla=""
            ).count(),
            2,
        )
