"""Cerrar o cancelar libera sólo la obligación pendiente de esa ejecución."""

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from maestros.models import Silo
from recepcion.models import MovimientoSilo

from .models import (
    EjecucionProceso,
    EntradaProceso,
    EtapaProceso,
    Proceso,
    ReservaSiloProceso,
    SalidaProceso,
)
from .servicios import transicionar_ejecucion


class LiberacionReservasOP03Tests(TestCase):
    def setUp(self):
        self.usuario = get_user_model().objects.create_user("reservas-procesos-op03")
        proceso = Proceso.objects.create(codigo="OP03-PROCESOS", nombre="Proceso OP03")
        etapa = EtapaProceso.objects.create(
            proceso=proceso,
            codigo="OP03-ETAPA",
            nombre="Etapa OP03",
            tipo=EtapaProceso.Tipo.CONDENSACION,
            orden=1,
        )
        self.origen = Silo.objects.create(
            codigo="OP03-P-ORIGEN",
            tipo=Silo.Tipo.SILO,
            capacidad_l=2000,
        )
        self.destino = Silo.objects.create(
            codigo="OP03-P-DESTINO",
            tipo=Silo.Tipo.SILO,
            capacidad_l=1000,
        )
        self.ejecucion = EjecucionProceso.objects.create(
            codigo="OP03-PROPIA",
            etapa=etapa,
            sucursal=self.origen.sucursal,
            responsable=self.usuario,
            estado=EjecucionProceso.Estado.EJECUCION,
        )
        otra = EjecucionProceso.objects.create(
            codigo="OP03-AJENA",
            etapa=etapa,
            sucursal=self.origen.sucursal,
            responsable=self.usuario,
            estado=EjecucionProceso.Estado.EJECUCION,
        )
        self.pendiente = ReservaSiloProceso.objects.create(
            ejecucion=self.ejecucion,
            silo=self.destino,
            tipo=ReservaSiloProceso.Tipo.DESTINO,
            cantidad_planificada="200.00",
        )
        self.consumida = ReservaSiloProceso.objects.create(
            ejecucion=self.ejecucion,
            silo=self.origen,
            tipo=ReservaSiloProceso.Tipo.ORIGEN,
            cantidad_planificada="100.00",
            cantidad_real="100.00",
            estado=ReservaSiloProceso.Estado.CONSUMIDA,
            cerrada_en=timezone.now(),
        )
        self.ajena = ReservaSiloProceso.objects.create(
            ejecucion=otra,
            silo=self.origen,
            tipo=ReservaSiloProceso.Tipo.ORIGEN,
            cantidad_planificada="300.00",
        )
        ahora = timezone.now()
        for silo, tipo, litros in (
            (self.origen, MovimientoSilo.Tipo.INGRESO, "1000.00"),
            (self.origen, MovimientoSilo.Tipo.SALIDA, "100.00"),
            (self.destino, MovimientoSilo.Tipo.INGRESO, "80.00"),
        ):
            MovimientoSilo.objects.create(
                silo=silo,
                tipo=tipo,
                litros=litros,
                fecha_hora=ahora,
                origen_tipo=MovimientoSilo.OrigenTipo.PRODUCCION,
                origen_id=self.ejecucion.pk,
                usuario=self.usuario,
                motivo="Operación física previa a cierre o cancelación",
            )
        EntradaProceso.objects.create(
            ejecucion=self.ejecucion,
            silo=self.origen,
            cantidad="100.00",
            unidad="L",
            tipo=EntradaProceso.Tipo.PRINCIPAL,
        )
        SalidaProceso.objects.create(
            ejecucion=self.ejecucion,
            silo=self.destino,
            cantidad="80.00",
            unidad="L",
        )

    def _transicion_sin_reescribir_consumo_ni_reserva_ajena(self, nuevo):
        otras = list(
            ReservaSiloProceso.objects.filter(
                pk__in=[self.consumida.pk, self.ajena.pk],
            )
            .order_by("pk")
            .values()
        )
        libro = list(MovimientoSilo.objects.order_by("pk").values())

        transicionar_ejecucion(
            ejecucion_id=self.ejecucion.pk,
            estado_nuevo=nuevo,
            usuario=self.usuario,
            motivo="Terminó la obligación pendiente propia",
        )

        self.pendiente.refresh_from_db()
        self.assertEqual(self.pendiente.estado, ReservaSiloProceso.Estado.LIBERADA)
        self.assertIsNotNone(self.pendiente.cerrada_en)
        self.assertIsNone(self.pendiente.cantidad_real)
        self.assertEqual(
            list(
                ReservaSiloProceso.objects.filter(
                    pk__in=[self.consumida.pk, self.ajena.pk],
                )
                .order_by("pk")
                .values()
            ),
            otras,
        )
        self.assertEqual(list(MovimientoSilo.objects.order_by("pk").values()), libro)
        self.assertEqual(ReservaSiloProceso.objects.count(), 3)
        self.ejecucion.refresh_from_db()
        self.assertEqual(self.ejecucion.estado, nuevo)

    def test_cancelar_libera_solo_pendiente_propia_y_no_devuelve_consumo(self):
        self._transicion_sin_reescribir_consumo_ni_reserva_ajena(
            EjecucionProceso.Estado.CANCELADA,
        )

    def test_finalizar_libera_solo_pendiente_propia_y_conserva_historia_consumida(self):
        self.ejecucion.estado = EjecucionProceso.Estado.PENDIENTE_CONTROL
        self.ejecucion.save(update_fields=["estado"])
        self._transicion_sin_reescribir_consumo_ni_reserva_ajena(
            EjecucionProceso.Estado.CERRADA,
        )
