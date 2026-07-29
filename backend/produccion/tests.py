"""
Pruebas de los lotes y sus análisis.

Cubren las dos decisiones del modelo que son fáciles de romper sin darse
cuenta: que el código de lote NO identifica al lote (MODELO_DATOS.md §2.1) y
que el resultado de calidad NO se persiste (§2.2).
"""

from datetime import date

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase

from maestros.models import Mandante, Producto

from .models import Analisis, Lote


class LoteTests(TestCase):
    def setUp(self):
        mandante = Mandante.objects.create(nombre="Nestlé")
        self.entera = Producto.objects.create(
            nombre="Leche entera en polvo",
            familia=Producto.Familia.POLVO,
            mandante=mandante,
        )
        self.semi = Producto.objects.create(
            nombre="Leche semidescremada en polvo",
            familia=Producto.Familia.POLVO,
            mandante=mandante,
        )

    def _lote(self, **extra):
        datos = {
            "codigo_lote": "CCAA6140N",
            "producto": self.entera,
            "fecha": date(2026, 7, 20),
            "kg_producidos": 12500,
        }
        datos.update(extra)
        return Lote(**datos)

    def test_el_codigo_de_lote_se_repite_entre_productos(self):
        """
        En planta, CCAA6140N es el mismo día dos productos distintos. El código
        es un correlativo diario, no la identidad del lote.
        """
        self._lote(producto=self.entera).save()
        self._lote(producto=self.semi).save()

        self.assertEqual(Lote.objects.filter(codigo_lote="CCAA6140N").count(), 2)

    def test_el_codigo_de_lote_se_repite_entre_dias(self):
        self._lote(fecha=date(2026, 7, 20)).save()
        self._lote(fecha=date(2026, 7, 21)).save()

        self.assertEqual(Lote.objects.count(), 2)

    def test_la_clave_natural_completa_si_es_unica(self):
        """Mismo código + mismo producto + misma fecha es el mismo lote."""
        self._lote().save()

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                self._lote().save()

    def test_rechaza_kilos_negativos(self):
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                self._lote(kg_producidos=-1).save()

    def test_el_lote_no_guarda_el_resultado_de_calidad(self):
        """
        El veredicto se recalcula siempre desde los análisis y la especificación
        vigente. Si alguna vez aparece como campo, el histórico deja de
        reevaluarse al corregir una especificación y esta prueba avisa.
        """
        campos = {campo.name for campo in Lote._meta.get_fields()}

        self.assertNotIn("resultado", campos)
        self.assertNotIn("resultado_calidad", campos)
        self.assertNotIn("conforme", campos)

    def test_estado_inicial_es_en_proceso(self):
        lote = self._lote()
        lote.save()

        self.assertEqual(lote.estado, Lote.Estado.EN_PROCESO)


class AnalisisTests(TestCase):
    def setUp(self):
        mandante = Mandante.objects.create(nombre="Nestlé")
        producto = Producto.objects.create(
            nombre="Leche entera en polvo",
            familia=Producto.Familia.POLVO,
            mandante=mandante,
        )
        self.lote = Lote.objects.create(
            codigo_lote="CCAA6140N",
            producto=producto,
            fecha=date(2026, 7, 20),
            kg_producidos=12500,
        )

    def _analisis(self, **extra):
        datos = {
            "lote": self.lote,
            "fecha": date(2026, 7, 20),
            "valores": {"humedad": 3.2, "mg": 26.5},
        }
        datos.update(extra)
        return Analisis(**datos)

    def test_un_analisis_valido_pasa(self):
        self._analisis().full_clean()

    def test_un_lote_admite_varios_analisis(self):
        """Una muestra por despacho: el veredicto del lote las agrega."""
        self._analisis(muestra="M-01").save()
        self._analisis(muestra="M-02").save()

        self.assertEqual(self.lote.analisis.count(), 2)

    def test_rechaza_parametros_desconocidos(self):
        analisis = self._analisis(valores={"inventado": 1.0})

        with self.assertRaises(ValidationError) as caso:
            analisis.full_clean()

        self.assertIn("valores", caso.exception.message_dict)

    def test_rechaza_valores_no_numericos(self):
        analisis = self._analisis(valores={"humedad": "alta"})

        with self.assertRaises(ValidationError):
            analisis.full_clean()

    def test_al_borrar_el_lote_se_borran_sus_analisis(self):
        self._analisis().save()
        self.lote.delete()

        self.assertEqual(Analisis.objects.count(), 0)
