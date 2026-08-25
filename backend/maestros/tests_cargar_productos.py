from unittest.mock import patch

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase

from maestros.management.commands.cargar_productos import Command
from maestros.models import Mandante, Producto


class CargaProductosSeguraTests(TestCase):
    @staticmethod
    def _fila(nombre):
        return {
            "fila": 4,
            "nombre": nombre,
            "naturaleza_comercial": "producto_propio",
            "cliente": "no_definido",
            "categoria": "leche_polvo",
            "tipo": "entera",
            "formato": "saco_25kg",
            "corregido": None,
        }

    def test_aplicar_se_niega_antes_de_escribir_si_hay_colisiones(self):
        filas = [self._fila("Producto A"), self._fila("Producto B")]

        with patch.object(Command, "_leer", return_value=filas):
            with self.assertRaisesMessage(CommandError, "asigna una variante") as error:
                call_command("cargar_productos", "--aplicar")

        mensaje = str(error.exception)
        self.assertIn("Producto A", mensaje)
        self.assertIn("Producto B", mensaje)
        self.assertEqual(Producto.objects.count(), 0)
        self.assertEqual(Mandante.objects.count(), 0)
