from datetime import date
from decimal import Decimal

from django.db.utils import IntegrityError
from django.test import TestCase

from maestros.models import Mandante, Producto
from produccion.models import Lote


class UnicidadDelCodigoTests(TestCase):
    def setUp(self):
        mandante = Mandante.objects.create(nombre="Nestlé")
        self.uno = Producto.objects.create(nombre="Leche entera en polvo", familia=Producto.Familia.POLVO, mandante=mandante)
        self.otro = Producto.objects.create(nombre="Leche entera regular", familia=Producto.Familia.POLVO, mandante=mandante)

    def test_dos_productos_distintos_no_comparten_codigo(self):
        Lote.objects.create(codigo_lote="CCAA6232E1-01", producto=self.uno, fecha=date(2026, 8, 20), kg_producidos=Decimal("1000"))
        with self.assertRaises(IntegrityError):
            Lote.objects.create(codigo_lote="CCAA6232E1-01", producto=self.otro, fecha=date(2026, 8, 20), kg_producidos=Decimal("1000"))
