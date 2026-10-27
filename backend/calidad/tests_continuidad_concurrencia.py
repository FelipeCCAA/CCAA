"""Reejecuta las tres carreras reales de silo con la política de aviso activa."""
from django.test import override_settings

from estandarizacion import tests_reuso_concurrencia as escenarios


@override_settings(CCAA_CALIDAD_INTERMEDIA_AVISO=True)
class ContinuidadConcurrenciaTests(escenarios.ReusoConcurrenciaTests):
    """Mismo contrato físico con dos conexiones; nueva política, sin mocks de BD."""
