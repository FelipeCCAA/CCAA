from django.test import SimpleTestCase

from .dominio import ruta_de_etapa
from .models import EtapaProceso


class RutaDeEtapaTests(SimpleTestCase):
    """
    El enlace de un aviso tiene que llevar a una pantalla que existe. Antes la
    continuación de un concentrado liberado mandaba a `/procesos?seccion=evaporacion`,
    pero la evaporación vive en `/produccion`, y `/procesos` no tiene esa sección:
    el operador caía arriba de una página sin relación con su tarea.

    Misma tabla que `rutaDeEtapa` en `frontend/src/services/planta-ahora.ts`.
    """

    def test_cada_etapa_real_lleva_a_una_pantalla_que_existe(self):
        esperado = {
            "recepcion": "/leche",
            "estandarizacion": "/estandarizacion",
            "descremacion": "/procesos?seccion=descremacion",
            "evaporacion": "/produccion?seccion=evaporacion",
            "condensacion": "/produccion?seccion=evaporacion",
            "secado": "/secado",
            "envasado": "/envasado",
            "mantequilla": "/procesos?seccion=mantequilla",
            "transferencia": "/produccion",
            "otro": "/produccion",
        }
        for tipo, _ in EtapaProceso.Tipo.choices:
            with self.subTest(tipo=tipo):
                self.assertEqual(ruta_de_etapa(tipo), esperado[tipo])

    def test_una_etapa_desconocida_cae_en_el_panel(self):
        self.assertEqual(ruta_de_etapa("nueva"), "/produccion")
