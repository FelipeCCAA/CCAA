"""
El análisis del silo — CCAA.REC.FORM.005.01.

El vale de trazabilidad de planta trae pH, acidez, grasa, SNG, proteína,
temperatura y densidad **del silo**, y es la fuente de los números que la
Hoja RC usa. Hasta ahora solo existían los controles del camión.
"""

from datetime import datetime, time, timezone as tz
from decimal import Decimal

from django.contrib.auth.models import User
from django.db.utils import IntegrityError
from django.test import TestCase

from maestros.models import Silo
from recepcion.models import AnalisisSilo, MovimientoSilo
from recepcion.tests import BaseAPIRecepcion


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


class VigenciaContraElLibroTests(TestCase):
    def setUp(self):
        self.silo = Silo.objects.create(
            codigo="SILO 4", tipo=Silo.Tipo.SILO, capacidad_l=Decimal("100000")
        )
        self.analisis = AnalisisSilo.objects.create(
            silo=self.silo,
            tomado_en=datetime(2026, 7, 15, 9, 40, tzinfo=tz.utc),
            grasa=Decimal("4.24"),
            sng=Decimal("8.69"),
        )

    def test_recien_tomado_esta_vigente(self):
        self.assertTrue(self.analisis.vigente)
        self.assertEqual(self.analisis.motivo_vigencia, "")

    def test_un_ingreso_posterior_lo_deja_fuera_de_vigencia(self):
        MovimientoSilo.objects.create(
            silo=self.silo,
            tipo=MovimientoSilo.Tipo.INGRESO,
            litros=Decimal("74834"),
            fecha_hora=datetime(2026, 7, 15, 14, 0, tzinfo=tz.utc),
        )

        self.assertFalse(self.analisis.vigente)
        self.assertIn("74834", self.analisis.motivo_vigencia)

    def test_una_salida_posterior_no_lo_invalida(self):
        """
        Sacar leche no cambia la composición de la que queda: el análisis
        sigue describiéndola. Invalidarlo obligaría a re-muestrear cada vez
        que una línea consume, que es todo el día.
        """
        MovimientoSilo.objects.create(
            silo=self.silo,
            tipo=MovimientoSilo.Tipo.SALIDA,
            litros=Decimal("20000"),
            fecha_hora=datetime(2026, 7, 15, 14, 0, tzinfo=tz.utc),
        )

        self.assertTrue(self.analisis.vigente)

    def test_un_ingreso_a_otro_silo_no_lo_invalida(self):
        otro = Silo.objects.create(
            codigo="SILO 5", tipo=Silo.Tipo.SILO, capacidad_l=Decimal("100000")
        )
        MovimientoSilo.objects.create(
            silo=otro,
            tipo=MovimientoSilo.Tipo.INGRESO,
            litros=Decimal("9337"),
            fecha_hora=datetime(2026, 7, 15, 14, 0, tzinfo=tz.utc),
        )

        self.assertTrue(self.analisis.vigente)

    def test_dice_que_falta_para_componer_un_vale(self):
        sin_sng = AnalisisSilo.objects.create(
            silo=self.silo,
            tomado_en=datetime(2026, 7, 15, 18, 0, tzinfo=tz.utc),
            grasa=Decimal("4.24"),
        )

        self.assertEqual(sin_sng.faltantes_para_vale, ["sng"])
        self.assertEqual(self.analisis.faltantes_para_vale, [])


class AnalisisSiloAPITests(BaseAPIRecepcion):
    def _resultados(self, respuesta):
        datos = respuesta.data
        return datos["results"] if "results" in datos else datos

    def test_registra_un_analisis_y_devuelve_su_vigencia(self):
        respuesta = self.cliente.post(
            "/api/recepcion/analisis-silo/",
            {
                "silo": self.silo.id,
                "tomado_en": "2026-07-15T09:40:00Z",
                "ph": "6.77",
                "acidez": "15.60",
                "grasa": "4.35",
                "sng": "8.90",
                "proteina": "3.44",
                "temperatura": "6.00",
                "densidad": "1032.00",
                "certificada": True,
                "inhibidores_resultado": "negativo",
                "metodo": "delvo_sp",
                "hora_lectura": "10:15",
            },
            format="json",
        )

        self.assertEqual(respuesta.status_code, 201, respuesta.data)
        self.assertIs(respuesta.data["vigente"], True)
        self.assertEqual(respuesta.data["faltantes_para_vale"], [])
        self.assertEqual(respuesta.data["silo_codigo"], "SILO 1")

    def test_el_analista_es_quien_lo_registra(self):
        respuesta = self.cliente.post(
            "/api/recepcion/analisis-silo/",
            {
                "silo": self.silo.id,
                "tomado_en": "2026-07-15T09:40:00Z",
                "grasa": "4.35",
                "sng": "8.90",
                "inhibidores_resultado": "negativo",
                "metodo": "delvo_sp",
                "hora_lectura": "10:15",
            },
            format="json",
        )

        self.assertEqual(respuesta.status_code, 201, respuesta.data)
        self.assertEqual(respuesta.data["analista_nombre"], "op")

    def test_quien_realiza_no_puede_poner_la_segunda_firma(self):
        analisis = AnalisisSilo.objects.create(
            silo=self.silo,
            tomado_en=datetime(2026, 7, 15, 9, 40, tzinfo=tz.utc),
            grasa="4.35", sng="8.90",
            inhibidores_resultado="negativo", metodo="delvo_sp",
            hora_lectura=time(10, 15), analista=User.objects.get(username="op"),
            estado=AnalisisSilo.Estado.CONFIRMADO,
        )

        respuesta = self.cliente.post(
            f"/api/recepcion/analisis-silo/{analisis.id}/visualizar/", {},
            format="json",
        )

        self.assertEqual(respuesta.status_code, 409)
        self.assertIn("distinta", respuesta.data["detail"])

    def test_filtra_por_silo(self):
        otro = Silo.objects.create(
            codigo="SILO 9", tipo=Silo.Tipo.SILO, capacidad_l=Decimal("50000")
        )
        AnalisisSilo.objects.create(
            silo=self.silo, tomado_en=datetime(2026, 7, 15, 9, 0, tzinfo=tz.utc)
        )
        AnalisisSilo.objects.create(
            silo=otro, tomado_en=datetime(2026, 7, 15, 9, 0, tzinfo=tz.utc)
        )

        respuesta = self.cliente.get(f"/api/recepcion/analisis-silo/?silo={otro.id}")

        self.assertEqual(respuesta.status_code, 200)
        resultados = self._resultados(respuesta)
        self.assertEqual(len(resultados), 1)
        self.assertEqual(resultados[0]["silo_codigo"], "SILO 9")

    def test_vigentes_deja_fuera_al_que_recibio_leche_despues(self):
        viejo = AnalisisSilo.objects.create(
            silo=self.silo, tomado_en=datetime(2026, 7, 15, 9, 0, tzinfo=tz.utc)
        )
        MovimientoSilo.objects.create(
            silo=self.silo,
            tipo=MovimientoSilo.Tipo.INGRESO,
            litros=Decimal("10000"),
            fecha_hora=datetime(2026, 7, 15, 12, 0, tzinfo=tz.utc),
        )
        nuevo = AnalisisSilo.objects.create(
            silo=self.silo, tomado_en=datetime(2026, 7, 15, 13, 0, tzinfo=tz.utc)
        )

        respuesta = self.cliente.get("/api/recepcion/analisis-silo/?vigentes=1")

        self.assertEqual(respuesta.status_code, 200)
        devueltos = {fila["id"] for fila in self._resultados(respuesta)}
        self.assertIn(nuevo.id, devueltos)
        self.assertNotIn(viejo.id, devueltos)
