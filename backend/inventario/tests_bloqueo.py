"""
Pruebas del candado de operaciones caras.

El MRP semanal explota las recetas multinivel de toda una semana dentro de la
petición HTTP. Lo correcto sería una cola, pero exige un proceso trabajador que
el despliegue actual no tiene. El riesgo concreto mientras tanto no es que
tarde: es que **se apile** —tres personas pulsando «calcular», o una pulsando
tres veces porque no ve respuesta, dan tres explosiones compitiendo por las
mismas conexiones—.
"""

from django.core.cache import cache
from django.test import TestCase

from .bloqueo import YaEnCurso, solo_uno


class SoloUnoTests(TestCase):

    def setUp(self):
        cache.clear()

    def tearDown(self):
        cache.clear()

    def test_el_segundo_no_entra(self):
        with solo_uno("prueba"):
            with self.assertRaises(YaEnCurso):
                with solo_uno("prueba"):
                    self.fail("no debería haber entrado")

    def test_se_suelta_al_terminar(self):
        with solo_uno("prueba"):
            pass

        with solo_uno("prueba"):
            pass

    def test_se_suelta_aunque_falle(self):
        """
        Si el cálculo revienta, el siguiente intento no tiene por qué esperar
        los cinco minutos del plazo.
        """
        with self.assertRaises(ZeroDivisionError):
            with solo_uno("prueba"):
                1 / 0

        with solo_uno("prueba"):
            pass

    def test_claves_distintas_no_se_estorban(self):
        """
        El candado es por semana: calcular la semana 30 no puede bloquear la
        31.
        """
        with solo_uno("mrp:semana:30"):
            with solo_uno("mrp:semana:31"):
                pass

    def test_el_candado_caduca_solo(self):
        """
        Un proceso que muere a mitad no alcanza a soltarlo. Sin caducidad, la
        operación quedaría bloqueada para siempre — hay que elegir entre un
        reintento prematuro y un bloqueo eterno, y lo segundo es peor.
        """
        cache.add("mrp:semana:30", True, 1)

        with self.assertRaises(YaEnCurso):
            with solo_uno("mrp:semana:30"):
                pass

        cache.delete("mrp:semana:30")

        with solo_uno("mrp:semana:30"):
            pass
