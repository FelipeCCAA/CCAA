"""Regresión para los listados paginados de inventario."""

from django.test import SimpleTestCase

from inventario.models import (
    AjusteInventario,
    Existencia,
    InspeccionMaterial,
    SolicitudMaterial,
)


class OrdenEstableTests(SimpleTestCase):
    def test_los_modelos_paginados_declaran_un_orden_determinista(self):
        for modelo in (
            Existencia,
            InspeccionMaterial,
            AjusteInventario,
            SolicitudMaterial,
        ):
            with self.subTest(modelo=modelo.__name__):
                self.assertEqual(modelo._meta.ordering, ["-id"])
