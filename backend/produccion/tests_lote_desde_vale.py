"""
El lote nace del vale, no elige silo.

Quien consume la leche de los silos es el **vale**: al transferirse saca de la
entera y del TK de descremada y deja la mezcla en el silo de destino. Esa leche
ya está estandarizada al RC que un producto pide, pero todavía no es de ningún
producto — abrir el lote es lo que formaliza a cuál va.

Las dos reglas que se fijan aquí:

1. Solo un vale **liberado** puede dar origen a un lote. Uno en corrección tiene
   un RC medido que no cumple.
2. No se puede sacar **más de lo que el vale preparó**, ni siquiera repartido
   entre varios lotes.
"""

from datetime import date
from decimal import Decimal

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.test import TestCase

from estandarizacion.models import ValeEstandarizacion
from maestros.models import Mandante, Producto, Silo
from produccion import servicios
from produccion.dominio import puede_abrir_lote_desde
from produccion.models import Lote
from recepcion.models import MovimientoSilo
from usuarios.models import Empresa, Sucursal


class BaseValeLote(TestCase):

    def setUp(self):
        self.empresa = Empresa.objects.create(rut="76.313.313-1", nombre="CCAA")
        self.planta = Sucursal.objects.create(
            empresa=self.empresa, codigo="PL", nombre="Planta"
        )
        mandante = Mandante.objects.create(
            empresa=self.empresa, nombre="Nestlé", codigo_cliente="nestle"
        )
        self.producto = Producto.objects.create(
            mandante=mandante, nombre="Leche entera en polvo", unidad_base="kg"
        )
        self.origen = Silo.objects.create(
            sucursal=self.planta, codigo="SILO 1", tipo=Silo.Tipo.SILO,
            capacidad_l=100000,
        )
        self.destino = Silo.objects.create(
            sucursal=self.planta, codigo="SILO 2", tipo=Silo.Tipo.SILO,
            capacidad_l=100000,
        )
        self.operador = User.objects.create_user(username="op", password="x")

    def _vale(self, estado=ValeEstandarizacion.Estado.LIBERADO, volumen="20000.00"):
        return ValeEstandarizacion.objects.create(
            codigo=f"VE-{estado}-{volumen}",
            fecha=date(2026, 8, 12),
            producto=self.producto,
            rc_objetivo=Decimal("0.4000"),
            volumen=Decimal(volumen),
            silo_entera=self.origen,
            silo_destino=self.destino,
            entera_grasa=Decimal("3.60"), entera_sng=Decimal("8.60"),
            descremada_grasa=Decimal("0.05"), descremada_sng=Decimal("8.90"),
            litros_entera=Decimal("19128.10"), litros_descremada=Decimal("871.90"),
            estado=estado,
        )

    def _abrir(self, vale, litros, codigo="CCAA6224010102010201-01"):
        return servicios.abrir_lote_desde_vale(
            vale=vale,
            producto=self.producto,
            codigo_lote=codigo,
            fecha=date(2026, 8, 12),
            litros=litros,
        )


class AperturaTests(BaseValeLote):

    def test_el_lote_queda_atado_al_vale_y_descuenta_su_silo(self):
        vale = self._vale()

        lote = self._abrir(vale, Decimal("20000.00"))

        self.assertEqual(lote.vale, vale)
        # No eligió silo: tomó el del vale.
        movimiento = MovimientoSilo.objects.get(origen_id=lote.id)
        self.assertEqual(movimiento.silo, vale.silo_destino)
        self.assertEqual(movimiento.litros, Decimal("20000.00"))

    def test_un_vale_no_liberado_no_abre_lote(self):
        """Su RC medido no cumple: esa leche no es la de ningún producto."""
        vale = self._vale(estado=ValeEstandarizacion.Estado.CORRIGIENDO)

        with self.assertRaises(ValidationError) as fallo:
            self._abrir(vale, Decimal("1000.00"))

        self.assertIn("liberado", str(fallo.exception))
        self.assertFalse(Lote.objects.exists())

    def test_no_se_puede_sacar_mas_de_lo_preparado(self):
        vale = self._vale(volumen="10000.00")

        with self.assertRaises(ValidationError):
            self._abrir(vale, Decimal("12000.00"))

        self.assertFalse(Lote.objects.exists())

    def test_un_vale_alimenta_varias_corridas_hasta_agotarse(self):
        """Veinte mil litros no se secan de una vez."""
        vale = self._vale(volumen="20000.00")

        self._abrir(vale, Decimal("12000.00"), codigo="LOTE-A")
        self._abrir(vale, Decimal("8000.00"), codigo="LOTE-B")

        self.assertEqual(vale.lotes.count(), 2)

        with self.assertRaises(ValidationError) as fallo:
            self._abrir(vale, Decimal("1.00"), codigo="LOTE-C")

        self.assertIn("quedan", str(fallo.exception))

    def test_si_la_regla_falla_no_queda_el_silo_descontado(self):
        """
        Todo o nada. Un descuento sin lote deja el saldo del silo mintiendo, y
        nadie lo nota porque no hay lote al que reclamarle esos litros.
        """
        vale = self._vale(volumen="5000.00")

        with self.assertRaises(ValidationError):
            self._abrir(vale, Decimal("9000.00"))

        self.assertFalse(MovimientoSilo.objects.exists())


class DecisionSinBaseTests(TestCase):
    """La regla pura, sin tocar la base: es lo que la hace comprobable."""

    class ValeDoble:
        codigo = "VE-1"
        estado = "liberado"
        volumen = Decimal("1000")

        def get_estado_display(self):
            return "Liberado"

    def test_liberado_y_dentro_del_volumen(self):
        decision = puede_abrir_lote_desde(self.ValeDoble(), Decimal("400"))

        self.assertTrue(decision.permitido)
        self.assertEqual(decision.litros_disponibles, Decimal("1000"))

    def test_descuenta_lo_que_ya_se_llevaron_otros(self):
        decision = puede_abrir_lote_desde(
            self.ValeDoble(), Decimal("400"), consumido_por_otros_lotes=Decimal("700")
        )

        self.assertFalse(decision.permitido)
        self.assertEqual(decision.litros_disponibles, Decimal("300"))

    def test_cero_litros_no_es_un_lote(self):
        self.assertFalse(
            puede_abrir_lote_desde(self.ValeDoble(), Decimal("0")).permitido
        )
