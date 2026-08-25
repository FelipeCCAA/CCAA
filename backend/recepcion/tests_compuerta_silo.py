from datetime import timedelta

from django.test import SimpleTestCase
from django.utils import timezone

from . import dominio


class CompuertaSiloDominioTests(SimpleTestCase):
    def setUp(self):
        self.ahora = timezone.now()
        self.silo = {
            "activo": True,
            "estado": "disponible",
            "leche_mas_antigua_en": self.ahora - timedelta(hours=12),
        }
        self.analisis = {
            "vigente": True,
            "grasa": 4.2,
            "sng": 8.8,
            "inhibidores_resultado": "negativo",
            "apto_inocuidad": True,
            "analista_id": 1,
            "visualizado_por_id": 2,
            "alcohol_75_conforme": None,
            "hervor_conforme": None,
            "organoleptico_conforme": None,
        }

    def motivos(self, analisis=None, ciclo=None, para="proceso"):
        return dominio.motivos_silo_no_disponible(
            self.silo,
            self.analisis if analisis is None else analisis,
            ciclo,
            self.ahora,
            para=para,
        )

    def test_sin_analisis_no_inicia_proceso(self):
        motivos = dominio.motivos_silo_no_disponible(
            self.silo, None, None, self.ahora, para="proceso"
        )
        self.assertIn("análisis", motivos[0])

    def test_analisis_invalidado_por_ingreso_posterior_bloquea(self):
        analisis = {**self.analisis, "vigente": False, "motivo_vigencia": "Entró otro camión."}
        self.assertIn("otro camión", self.motivos(analisis)[0])

    def test_inhibidores_positivos_bloquean(self):
        analisis = {
            **self.analisis,
            "inhibidores_resultado": "positivo",
            "apto_inocuidad": False,
        }
        self.assertTrue(any("positivos" in motivo for motivo in self.motivos(analisis)))

    def test_cip_bloquea_proceso_y_descarga(self):
        ciclo = {"estado": "en_curso"}
        self.assertTrue(any("CIP" in motivo for motivo in self.motivos(ciclo=ciclo)))
        self.assertTrue(any("CIP" in motivo for motivo in self.motivos(ciclo=ciclo, para="descarga")))

    def test_leche_sobre_48_h_exige_revalidacion(self):
        self.silo["leche_mas_antigua_en"] = self.ahora - timedelta(hours=49)
        self.assertTrue(any("48 h" in motivo for motivo in self.motivos()))

    def test_analisis_completo_y_vigente_habilita(self):
        self.assertEqual(self.motivos(), [])
