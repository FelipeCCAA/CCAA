"""La receta disponible no sustituye el stock físico libre del silo."""

from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone
from rest_framework.test import APIClient

from estandarizacion.models import ValeEstandarizacion
from inventario.models import CicloCIP
from maestros.models import Silo
from procesos.models import (
    CorridaSecado,
    EjecucionProceso,
    EntradaProceso,
    ReservaSiloProceso,
    SalidaProceso,
)
from recepcion.models import AnalisisSilo, AtribucionRecepcion, MovimientoSilo
from recepcion.servicios import saldo_silo
from usuarios.models import PerfilUsuario, Rol

from .models import Lote
from .servicios import abrir_lote_desde_vale
from .tests_lote_desde_vale import BaseValeLote


class AperturaSaldoFisicoOP03Tests(BaseValeLote):
    def setUp(self):
        super().setUp()
        self.vale = ValeEstandarizacion.objects.create(
            codigo="OP03-VALE",
            fecha=timezone.localdate(),
            producto=self.producto,
            rc_objetivo="0.4000",
            volumen="1000.00",
            silo_entera=self.origen,
            silo_destino=self.destino,
            entera_grasa="3.60",
            entera_sng="8.60",
            litros_entera="1000.00",
            litros_descremada="0.00",
            estado=ValeEstandarizacion.Estado.LIBERADO,
            ejecutado_en=timezone.now(),
        )

    def _saldo_inicial(self, litros):
        MovimientoSilo.objects.create(
            silo=self.destino,
            tipo=MovimientoSilo.Tipo.INGRESO,
            litros=Decimal(litros),
            fecha_hora=timezone.now(),
            origen_tipo=MovimientoSilo.OrigenTipo.ESTANDARIZACION,
            origen_id=self.vale.pk,
            motivo="Saldo físico real del escenario OP03",
        )

    def _reservar(self, tipo, cantidad):
        ejecucion = EjecucionProceso.objects.create(
            codigo="OP03-EJECUCION-AJENA",
            etapa=self.ruta.proceso.etapas.get(),
            sucursal=self.planta,
            responsable=self.operador,
            estado=EjecucionProceso.Estado.EJECUCION,
        )
        return ReservaSiloProceso.objects.create(
            ejecucion=ejecucion,
            silo=self.destino,
            tipo=tipo,
            cantidad_planificada=Decimal(cantidad),
            producto=self.producto,
        )

    def _foto(self):
        return {
            modelo._meta.label: list(modelo.objects.order_by("pk").values())
            for modelo in (
                Lote,
                MovimientoSilo,
                AtribucionRecepcion,
                EjecucionProceso,
                EntradaProceso,
                SalidaProceso,
                CorridaSecado,
                ReservaSiloProceso,
            )
        }

    def _abrir(self, litros):
        return abrir_lote_desde_vale(
            vale=self.vale,
            codigo_lote="OP03-LOTE-SALDO",
            fecha=timezone.localdate(),
            litros=Decimal(litros),
            usuario=self.operador,
            producto=self.producto,
        )

    def _rechazar_sin_efectos(self, litros):
        antes = self._foto()
        with self.assertRaises(ValidationError):
            self._abrir(litros)
        self.assertEqual(self._foto(), antes)

    def test_volumen_de_receta_no_permite_abrir_sin_saldo_fisico_suficiente(self):
        self._saldo_inicial("300.00")
        self._rechazar_sin_efectos("500.00")

    def test_reserva_de_origen_ajena_no_se_consume_al_abrir_lote(self):
        self._saldo_inicial("800.00")
        self._reservar(ReservaSiloProceso.Tipo.ORIGEN, "700.00")
        self._rechazar_sin_efectos("200.00")

    def test_silo_reservado_como_destino_no_alimenta_un_lote_nuevo(self):
        self._saldo_inicial("800.00")
        self._reservar(ReservaSiloProceso.Tipo.DESTINO, "200.00")
        self._rechazar_sin_efectos("100.00")

    def test_solo_el_saldo_libre_abre_lote_y_deja_reserva_ajena_intacta(self):
        self._saldo_inicial("800.00")
        reserva = self._reservar(ReservaSiloProceso.Tipo.ORIGEN, "700.00")
        original = ReservaSiloProceso.objects.values().get(pk=reserva.pk)

        lote = self._abrir("100.00")

        self.assertEqual(lote.vale_id, self.vale.pk)
        self.assertEqual(lote.producto_id, self.producto.pk)
        movimiento = MovimientoSilo.objects.get(
            origen_tipo=MovimientoSilo.OrigenTipo.LOTE,
            origen_id=lote.pk,
        )
        self.assertEqual(movimiento.litros, Decimal("100.00"))
        self.assertEqual(movimiento.silo_id, self.destino.pk)
        self.assertEqual(saldo_silo(self.destino), Decimal("700.00"))
        self.assertEqual(
            ReservaSiloProceso.objects.values().get(pk=reserva.pk), original
        )
        self.assertEqual(Lote.objects.count(), 1)
        self.assertEqual(
            EntradaProceso.objects.get(ejecucion=lote.ejecucion).cantidad,
            Decimal("100.00"),
        )

    def test_calidad_del_silo_se_revalida_antes_de_escribir_lote_o_consumo(self):
        self._saldo_inicial("800.00")
        self.destino.estado = Silo.Estado.BLOQUEADO_CALIDAD
        self.destino.save(update_fields=["estado"])
        self._rechazar_sin_efectos("100.00")

    def test_get_vales_ofrece_solo_100_libres_y_excluye_origen_no_utilizable(self):
        self._saldo_inicial("800.00")
        reserva = self._reservar(ReservaSiloProceso.Tipo.ORIGEN, "700.00")
        PerfilUsuario.objects.create(
            usuario=self.operador,
            rol=Rol.PRODUCCION,
            area=PerfilUsuario.Area.CONDENSACION,
            sucursal=self.planta,
            empresa=self.empresa,
        )
        visor = get_user_model().objects.create_user("visor-op03-saldo")
        ahora = timezone.now()
        AnalisisSilo.objects.create(
            silo=self.destino,
            tomado_en=ahora,
            grasa="3.44",
            sng="8.60",
            inhibidores_resultado="negativo",
            metodo="delvo_sp",
            hora_lectura=timezone.localtime().time(),
            analista=self.operador,
            visualizado_por=visor,
            visualizado_en=ahora,
            estado=AnalisisSilo.Estado.CONFIRMADO,
        )
        api = APIClient()
        api.force_authenticate(self.operador)
        url = "/api/produccion/lotes/vales-disponibles/"
        antes = self._foto()

        respuesta = api.get(url)

        self.assertEqual(respuesta.status_code, 200, respuesta.data)
        fila = next((f for f in respuesta.data if f["id"] == self.vale.pk), None)
        self.assertIsNotNone(fila, respuesta.data)
        self.assertEqual(Decimal(str(fila["litros_disponibles"])), Decimal("100.00"))
        self.assertEqual(Decimal(str(fila["litros_preparados"])), Decimal("1000.00"))
        self.assertEqual(self._foto(), antes)

        for impedimento in ("sin_libre", "destino_reservado", "bloqueado", "cip"):
            with self.subTest(impedimento=impedimento):
                # Cada estado parte del mismo escenario; el GET no libera
                # reservas ni modifica stock y las variaciones se revierten.
                with transaction.atomic():
                    if impedimento == "sin_libre":
                        ReservaSiloProceso.objects.filter(pk=reserva.pk).update(
                            cantidad_planificada=Decimal("800.00"),
                        )
                    elif impedimento == "destino_reservado":
                        ReservaSiloProceso.objects.filter(pk=reserva.pk).update(
                            tipo=ReservaSiloProceso.Tipo.DESTINO,
                            cantidad_planificada=Decimal("200.00"),
                        )
                    elif impedimento == "bloqueado":
                        Silo.objects.filter(pk=self.destino.pk).update(
                            estado=Silo.Estado.BLOQUEADO_CALIDAD,
                        )
                    else:
                        CicloCIP.objects.create(
                            silo=self.destino,
                            sucursal=self.planta,
                            area=PerfilUsuario.Area.RECEPCION,
                            tipo_objetivo=CicloCIP.TipoObjetivo.SILO,
                            inicio=timezone.now(),
                            estado=CicloCIP.Estado.EN_CURSO,
                        )
                    esperada = self._foto()
                    retenida = api.get(url)
                    self.assertEqual(retenida.status_code, 200, retenida.data)
                    self.assertNotIn(self.vale.pk, [f["id"] for f in retenida.data])
                    self.assertEqual(self._foto(), esperada)
                    transaction.set_rollback(True)
