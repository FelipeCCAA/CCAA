"""
El análisis del silo — CCAA.REC.FORM.005.01.

El vale de trazabilidad de planta trae pH, acidez, grasa, SNG, proteína,
temperatura y densidad **del silo**, y es la fuente de los números que la
Hoja RC usa. Hasta ahora solo existían los controles del camión.
"""

from datetime import datetime, time, timezone as tz
from decimal import Decimal

from django.db.utils import IntegrityError
from django.test import TestCase

from maestros.models import Silo
from recepcion.models import AnalisisSilo


class AnalisisSiloModeloTests(TestCase):
    def setUp(self):
        self.silo = Silo.objects.create(
            codigo="SILO 6", tipo=Silo.Tipo.SILO, capacidad_l=Decimal("100000")
        )

    def test_guarda_los_siete_parametros_del_formato(self):
        analisis = AnalisisSilo.objects.create(
            silo=self.silo,
            tomado_en=datetime(2026, 7, 15, 9, 40, tzinfo=tz.utc),
            hora_inicio_llenado=time(6, 0),
            ph=Decimal("6.77"),
            acidez=Decimal("15.60"),
            grasa=Decimal("4.35"),
            sng=Decimal("8.90"),
            proteina=Decimal("3.44"),
            temperatura=Decimal("6.00"),
            densidad=Decimal("1032"),
            certificada=True,
        )

        analisis.refresh_from_db()
        self.assertEqual(analisis.grasa, Decimal("4.35"))
        self.assertEqual(analisis.proteina, Decimal("3.44"))
        self.assertEqual(analisis.densidad, Decimal("1032"))
        self.assertIs(analisis.certificada, True)

    def test_dos_analisis_del_mismo_silo_en_el_mismo_instante_no_conviven(self):
        """
        Sería el mismo muestreo cargado dos veces. Dejar pasar el duplicado
        deja al vale eligiendo entre dos análisis que dicen cosas distintas
        de la misma leche.
        """
        momento = datetime(2026, 7, 15, 9, 40, tzinfo=tz.utc)
        AnalisisSilo.objects.create(silo=self.silo, tomado_en=momento, grasa=Decimal("4.35"))

        with self.assertRaises(IntegrityError):
            AnalisisSilo.objects.create(
                silo=self.silo, tomado_en=momento, grasa=Decimal("4.20")
            )

    def test_certificada_nula_no_es_lo_mismo_que_no_certificada(self):
        analisis = AnalisisSilo.objects.create(
            silo=self.silo, tomado_en=datetime(2026, 7, 15, 10, 0, tzinfo=tz.utc)
        )

        self.assertIsNone(analisis.certificada)
