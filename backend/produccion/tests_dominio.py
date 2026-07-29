"""
Pruebas de las reglas de calidad.

Portadas de `prototipo/js/modelo/pruebas.js` (bloque de calidad). Son las que,
si se rompen, dejan salir producto que no debería salir: por eso cada una
nombra la regla que protege.
"""

from datetime import date

from django.test import TestCase

from maestros.models import Especificacion, Mandante, Producto

from . import dominio
from .models import Analisis, Lote


class BaseCalidad(TestCase):
    """Un producto con especificación y un lote, que es el escenario mínimo."""

    def setUp(self):
        self.mandante = Mandante.objects.create(nombre="Nestlé")
        self.producto = Producto.objects.create(
            nombre="Leche entera en polvo",
            familia=Producto.Familia.POLVO,
            mandante=self.mandante,
        )
        self.spec = Especificacion.objects.create(
            producto=self.producto,
            version=1,
            vigente_desde=date(2026, 1, 1),
            rangos={
                "humedad": {"min": 2.0, "max": 4.0, "obligatorio": True},
                "mg": {"min": 26.0, "max": 28.0, "obligatorio": True},
            },
        )
        self.lote = Lote.objects.create(
            codigo_lote="CCAA6140N",
            producto=self.producto,
            fecha=date(2026, 7, 20),
            kg_producidos=12500,
        )

    def _analisis(self, valores, **extra):
        return Analisis.objects.create(
            lote=extra.pop("lote", self.lote),
            fecha=extra.pop("fecha", date(2026, 7, 20)),
            valores=valores,
            **extra,
        )

    def _resultado(self):
        return dominio.resultado_calidad_lote(
            self.lote,
            list(Analisis.objects.all()),
            list(Especificacion.objects.all()),
        )


class EspecificacionVigenteTests(BaseCalidad):
    def test_un_lote_se_evalua_con_la_especificacion_vigente_en_su_fecha(self):
        """Un lote de mayo se audita contra la spec de mayo, no contra la actual."""
        self.spec.vigente_hasta = date(2026, 5, 31)
        self.spec.save()

        nueva = Especificacion.objects.create(
            producto=self.producto,
            version=2,
            vigente_desde=date(2026, 6, 1),
            rangos={"humedad": {"min": 3.0, "max": 3.5}},
        )

        todas = list(Especificacion.objects.all())

        de_mayo = dominio.especificacion_vigente(todas, self.producto.id, date(2026, 5, 15))
        de_julio = dominio.especificacion_vigente(todas, self.producto.id, date(2026, 7, 20))

        self.assertEqual(de_mayo, self.spec)
        self.assertEqual(de_julio, nueva)

    def test_un_producto_sin_especificacion_devuelve_none(self):
        otro = Producto.objects.create(
            nombre="Crema",
            familia=Producto.Familia.CREMA,
            mandante=self.mandante,
        )

        vigente = dominio.especificacion_vigente(
            list(Especificacion.objects.all()), otro.id, date(2026, 7, 20)
        )

        self.assertIsNone(vigente)

    def test_una_fecha_anterior_a_toda_vigencia_no_devuelve_especificacion(self):
        vigente = dominio.especificacion_vigente(
            list(Especificacion.objects.all()), self.producto.id, date(2025, 12, 31)
        )

        self.assertIsNone(vigente)

    def test_vigencia_abierta_cubre_cualquier_fecha_posterior(self):
        """vigente_hasta vacío significa vigente indefinidamente."""
        vigente = dominio.especificacion_vigente(
            list(Especificacion.objects.all()), self.producto.id, date(2030, 1, 1)
        )

        self.assertEqual(vigente, self.spec)


class EvaluarAnalisisTests(BaseCalidad):
    def test_un_analisis_dentro_de_rango_es_conforme(self):
        ev = dominio.evaluar_analisis({"humedad": 3.0, "mg": 27.0}, self.spec)

        self.assertEqual(ev.resultado, dominio.CONFORME)
        self.assertEqual(ev.desviaciones, [])

    def test_un_analisis_fuera_de_rango_es_no_conforme_e_informa_el_parametro(self):
        ev = dominio.evaluar_analisis({"humedad": 5.0, "mg": 27.0}, self.spec)

        self.assertEqual(ev.resultado, dominio.NO_CONFORME)
        self.assertEqual([d.parametro for d in ev.desviaciones], ["humedad"])
        self.assertEqual(ev.desviaciones[0].desvio, "alto")

    def test_informa_cuando_el_desvio_es_por_debajo(self):
        ev = dominio.evaluar_analisis({"humedad": 1.0, "mg": 27.0}, self.spec)

        self.assertEqual(ev.desviaciones[0].desvio, "bajo")

    def test_el_limite_exacto_esta_dentro_de_rango(self):
        """El rango es inclusivo: 2.0 y 4.0 son valores aceptables."""
        ev = dominio.evaluar_analisis({"humedad": 2.0, "mg": 28.0}, self.spec)

        self.assertEqual(ev.resultado, dominio.CONFORME)

    def test_falta_un_parametro_obligatorio_no_es_conforme_sino_sin_analisis(self):
        """
        Que no haya nada fuera de rango no basta para afirmar que es conforme:
        si falta un obligatorio, no hay con qué afirmarlo.
        """
        ev = dominio.evaluar_analisis({"humedad": 3.0}, self.spec)

        self.assertEqual(ev.resultado, dominio.SIN_ANALISIS)
        self.assertEqual(ev.faltantes, ["mg"])

    def test_un_parametro_no_obligatorio_que_falta_no_penaliza(self):
        self.spec.rangos = {
            "humedad": {"min": 2.0, "max": 4.0, "obligatorio": True},
            "ph": {"min": 6.0, "max": 7.0},
        }

        ev = dominio.evaluar_analisis({"humedad": 3.0}, self.spec)

        self.assertEqual(ev.resultado, dominio.CONFORME)

    def test_sin_especificacion_no_se_inventa_un_veredicto(self):
        ev = dominio.evaluar_analisis({"humedad": 3.0}, None)

        self.assertEqual(ev.resultado, dominio.SIN_ESPECIFICACION)

    def test_un_valor_no_numerico_se_trata_como_no_medido(self):
        ev = dominio.evaluar_analisis({"humedad": "alta", "mg": 27.0}, self.spec)

        self.assertEqual(ev.resultado, dominio.SIN_ANALISIS)
        self.assertIn("humedad", ev.faltantes)

    def test_un_parametro_medido_que_la_spec_no_pide_se_ignora(self):
        ev = dominio.evaluar_analisis(
            {"humedad": 3.0, "mg": 27.0, "temperatura": 950.0}, self.spec
        )

        self.assertEqual(ev.resultado, dominio.CONFORME)


class ResultadoCalidadLoteTests(BaseCalidad):
    def test_un_lote_con_una_muestra_conforme_es_conforme(self):
        self._analisis({"humedad": 3.0, "mg": 27.0})

        self.assertEqual(self._resultado().resultado, dominio.CONFORME)

    def test_basta_una_muestra_fuera_de_rango_para_que_el_lote_sea_no_conforme(self):
        """
        No se promedia: el producto ya está mezclado y no se puede separar la
        fracción defectuosa.
        """
        self._analisis({"humedad": 3.0, "mg": 27.0}, muestra="M-01")
        self._analisis({"humedad": 9.0, "mg": 27.0}, muestra="M-02")

        resultado = self._resultado()

        self.assertEqual(resultado.resultado, dominio.NO_CONFORME)
        self.assertEqual(resultado.evaluados, 2)
        self.assertEqual(resultado.desviaciones[0]["muestra"], "M-02")

    def test_un_lote_sin_analisis_no_queda_como_conforme(self):
        resultado = self._resultado()

        self.assertEqual(resultado.resultado, dominio.SIN_ANALISIS)
        self.assertEqual(resultado.evaluados, 0)

    def test_un_lote_sin_especificacion_lo_dice(self):
        Especificacion.objects.all().delete()
        self._analisis({"humedad": 3.0, "mg": 27.0})

        self.assertEqual(self._resultado().resultado, dominio.SIN_ESPECIFICACION)

    def test_no_mezcla_los_analisis_de_otro_lote(self):
        otro = Lote.objects.create(
            codigo_lote="CCAA6141N",
            producto=self.producto,
            fecha=date(2026, 7, 21),
            kg_producidos=8000,
        )
        self._analisis({"humedad": 3.0, "mg": 27.0})
        self._analisis({"humedad": 9.0, "mg": 27.0}, lote=otro)

        self.assertEqual(self._resultado().resultado, dominio.CONFORME)

    def test_el_resultado_se_recalcula_al_cambiar_la_especificacion(self):
        """
        La razón de no persistir el veredicto: corregir una especificación
        reevalúa el histórico completo, sin migraciones ni recálculos manuales.
        """
        self._analisis({"humedad": 3.0, "mg": 27.0})

        self.assertEqual(self._resultado().resultado, dominio.CONFORME)

        self.spec.rangos = {"humedad": {"min": 0.5, "max": 1.0, "obligatorio": True}}
        self.spec.save()

        self.assertEqual(self._resultado().resultado, dominio.NO_CONFORME)

    def test_manda_el_peor_caso_sobre_el_incompleto(self):
        """No conforme pesa más que sin análisis."""
        self._analisis({"humedad": 3.0}, muestra="incompleta")
        self._analisis({"humedad": 9.0, "mg": 27.0}, muestra="fuera")

        self.assertEqual(self._resultado().resultado, dominio.NO_CONFORME)

    def test_la_etiqueta_es_legible(self):
        self._analisis({"humedad": 3.0, "mg": 27.0})

        self.assertEqual(self._resultado().etiqueta, "Conforme")
