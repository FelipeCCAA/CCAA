"""
El código del vale lo asigna el sistema.

Se prueba sobre el modelo porque la regla vive en su `save()`: así la cubren la
confirmación, la creación directa, el admin y los scripts, sin que ninguno tenga
que acordarse de llamarla.
"""

from datetime import date, timedelta
from unittest.mock import patch

from django.utils import timezone

from .dominio import prefijo_codigo_vale
from .models import CodigoValeNoAsignado, ValeEstandarizacion
from .tests_vale import BaseVale

#: Un día fijo, para que los códigos esperados no dependan de cuándo se corre.
DIA = date(2026, 9, 23)

BORRADOR = ValeEstandarizacion.Estado.BORRADOR
ANULADO = ValeEstandarizacion.Estado.ANULADO


class AsignacionCodigoValeTests(BaseVale):

    def confirmado(self, **extra):
        """Un vale ya confirmado (`calculado`) sin código: el modelo se lo asigna."""
        return self.crear_vale(codigo="", fecha=DIA, **extra)

    def borrador(self, **extra):
        vale = self.crear_vale(
            codigo=ValeEstandarizacion.nuevo_codigo_borrador(),
            fecha=DIA, estado=BORRADOR, **extra,
        )
        # Como la vista: confirmar() opera sobre el vale leído de la base, con
        # Decimal reales. `crear_vale` deja los decimales como texto en memoria.
        vale.refresh_from_db()
        return vale

    def anular(self, vale):
        vale.estado = ANULADO
        vale.save(update_fields=["estado", "actualizado_en"])
        vale.refresh_from_db()

    def test_el_primer_vale_del_dia_es_el_01(self):
        self.assertEqual(self.confirmado().codigo, "VE6266-01")

    def test_el_segundo_vale_del_dia_es_el_02(self):
        self.confirmado()

        self.assertEqual(self.confirmado().codigo, "VE6266-02")

    def test_el_dia_sale_de_la_fecha_del_vale_y_no_del_reloj(self):
        ayer = timezone.localdate() - timedelta(days=1)

        vale = self.crear_vale(codigo="", fecha=ayer)

        self.assertEqual(vale.codigo, f"{prefijo_codigo_vale(ayer)}01")

    def test_un_borrador_no_recibe_codigo(self):
        self.assertTrue(self.borrador().codigo.startswith("BORRADOR-"))

    def test_un_borrador_descartado_no_consume_numero(self):
        """Descartar anula el borrador; con su `BORRADOR-…` y sin número."""
        descartado = self.borrador()
        self.anular(descartado)

        self.assertTrue(descartado.codigo.startswith("BORRADOR-"))
        self.assertEqual(self.confirmado().codigo, "VE6266-01")

    def test_un_vale_anulado_conserva_su_numero_y_no_se_reutiliza(self):
        primero = self.confirmado()
        self.anular(primero)

        self.assertEqual(primero.codigo, "VE6266-01")
        self.assertEqual(self.confirmado().codigo, "VE6266-02")

    def test_los_codigos_de_antes_no_cuentan(self):
        for codigo in ("VE-316256", "VE-20260901-01", "jkjfd"):
            self.crear_vale(codigo=codigo, fecha=DIA)

        self.assertEqual(self.confirmado().codigo, "VE6266-01")

    def test_un_codigo_explicito_se_respeta(self):
        """Las pruebas y el histórico crean vales con código propio."""
        self.assertEqual(self.crear_vale(codigo="VE-1", fecha=DIA).codigo, "VE-1")

    def test_confirmar_un_borrador_le_asigna_el_codigo(self):
        vale = self.borrador()

        self.assertEqual(vale.confirmar(self.usuario), [])

        vale.refresh_from_db()
        self.assertEqual(vale.codigo, "VE6266-01")
        self.assertEqual(vale.estado, ValeEstandarizacion.Estado.CALCULADO)

    def test_una_colision_reintenta_con_el_siguiente_libre(self):
        """
        Dos confirmaciones simultáneas calculan el mismo número. Se simula
        forzando el primer cálculo a proponer uno ya ocupado.
        """
        self.confirmado()  # ocupa VE6266-01
        original = ValeEstandarizacion._siguiente_correlativo
        propuestas = iter([1])

        def forzado(vale, prefijo):
            return next(propuestas, None) or original(vale, prefijo)

        with patch.object(ValeEstandarizacion, "_siguiente_correlativo", forzado):
            vale = self.confirmado()

        self.assertEqual(vale.codigo, "VE6266-02")

    def test_agotados_los_intentos_falla_sin_guardar(self):
        self.confirmado()  # ocupa VE6266-01

        with patch.object(
            ValeEstandarizacion, "_siguiente_correlativo", lambda vale, prefijo: 1
        ):
            with self.assertRaises(CodigoValeNoAsignado):
                self.confirmado()

        self.assertEqual(ValeEstandarizacion.objects.filter(fecha=DIA).count(), 1)

    def test_confirmar_sin_codigo_libre_devuelve_motivo_y_sigue_en_borrador(self):
        vale = self.borrador()
        self.confirmado()  # ocupa VE6266-01

        with patch.object(
            ValeEstandarizacion, "_siguiente_correlativo", lambda vale, prefijo: 1
        ):
            motivos = vale.confirmar(self.usuario)

        self.assertEqual(
            motivos, ["No se pudo asignar un código de vale; vuelve a confirmar."]
        )
        vale.refresh_from_db()
        self.assertEqual(vale.estado, BORRADOR)
        self.assertTrue(vale.codigo.startswith("BORRADOR-"))
