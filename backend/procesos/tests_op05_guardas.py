"""Disponibilidad específica del origen, reservas ajenas y limpieza en OP-05."""

from decimal import Decimal
from uuid import uuid4

from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone

from calidad.vigencia import registrar_firma_salida
from inventario.models import CicloCIP
from recepcion.models import MovimientoSilo

from . import tests_mantequilla as escenarios
from . import tests_op05_mantequilla as regresiones
from .models import EjecucionProceso, ReservaSiloProceso
from .servicios import iniciar_mantequilla


class GuardasFisicasMantequillaOP05Tests(TestCase):
    def setUp(self):
        escenarios.MantequillaTests.setUp(self)
        self.fuente, _, self.tk = regresiones.MantequillaOp05BaselineTests._origen_tk(self)

    def _rechaza_sin_retiro(self):
        with self.assertRaises(ValidationError):
            iniciar_mantequilla(
                corrida_id=self.corrida.pk, usuario=self.usuario,
                operacion_id=uuid4(),
            )
        self.assertFalse(MovimientoSilo.objects.filter(
            operacion_id=self.corrida.operacion_id,
        ).exists())
        self.assertEqual(self.corrida.ejecucion.entradas.count(), 0)
        self.corrida.refresh_from_db()
        self.assertEqual(self.corrida.estado, self.corrida.Estado.BORRADOR)

    def test_saldo_del_tk_no_sustituye_saldo_de_la_salida_elegida(self):
        # El TK tiene 1.000 L; esta salida sólo acredita 100 L de ese total.
        self.fuente.cantidad = Decimal("100")
        self.fuente.save(update_fields=["cantidad"])
        decision = self.fuente.liberacion_calidad
        decision.refresh_from_db()
        decision.estado = decision.Estado.LIBERADO
        decision.save(update_fields=["estado"])
        registrar_firma_salida(decision)
        self._rechaza_sin_retiro()

    def test_reserva_de_otra_corrida_no_se_consume(self):
        ajena = EjecucionProceso.objects.create(
            codigo="RESERVA-AJENA-OP05", etapa=self.corrida.ejecucion.etapa,
            sucursal=self.planta,
        )
        reserva = ReservaSiloProceso.objects.create(
            ejecucion=ajena, silo=self.tk, tipo=ReservaSiloProceso.Tipo.ORIGEN,
            cantidad_planificada=Decimal("900"),
        )
        self._rechaza_sin_retiro()
        reserva.refresh_from_db()
        self.assertEqual(reserva.estado, ReservaSiloProceso.Estado.ACTIVA)

    def test_cip_activo_impide_retirar_crema(self):
        CicloCIP.objects.create(
            sucursal=self.planta, area=self.usuario.perfil.area,
            tipo_objetivo=CicloCIP.TipoObjetivo.SILO, silo=self.tk,
            inicio=timezone.now(), estado=CicloCIP.Estado.EN_CURSO,
        )
        self._rechaza_sin_retiro()
