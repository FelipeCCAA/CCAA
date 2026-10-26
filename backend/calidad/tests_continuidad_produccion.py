"""Continuidad física con Calidad pendiente, sin fabricar una liberación."""
from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch
from uuid import NAMESPACE_URL, uuid5

from django.core.exceptions import ValidationError
from django.test import override_settings
from django.utils import timezone

from calidad.continuidad import exigir_pendientes_entrada_resueltos, registrar
from calidad.models import LiberacionProceso
from calidad.vigencia import exigir_liberacion_salida_vigente
from estandarizacion import servicios as estandarizacion
from estandarizacion import tests_f01_f02_materiales as escenarios
from estandarizacion.tests_vale import BaseVale
from maestros.models import Silo
from procesos.models import EntradaProceso, EjecucionProceso, EtapaProceso, EventoProceso
from recepcion.models import AnalisisSilo, ControlInhibidores, MovimientoSilo
from recepcion.servicios import saldo_silo


@override_settings(CCAA_CALIDAD_INTERMEDIA_AVISO=True)
class ContinuidadProduccionTests(BaseVale):
    # Composición de fixture: no heredar la clase que contiene otras pruebas.
    _fuente = escenarios.MaterialesValeF01F02Tests._fuente

    def setUp(self):
        escenarios.MaterialesValeF01F02Tests.setUp(self)
        self.etapa.requiere_calidad = True
        self.etapa.save(update_fields=["requiere_calidad"])
        decision = LiberacionProceso.objects.get(salida=self.fuente)
        decision.estado = LiberacionProceso.Estado.PENDIENTE
        decision.firma_id = None
        decision.version_firmada = None
        decision.evidencia_firmada = {}
        decision.save(update_fields=["estado", "firma_id", "version_firmada", "evidencia_firmada"])

    def _transferir(self):
        return estandarizacion.transferir(vale_id=self.vale.pk, usuario=self.usuario)

    def _muestrear_conforme(self):
        self._transferir()
        estandarizacion.iniciar_agitacion(vale_id=self.vale.pk)
        estandarizacion.registrar_muestra(vale_id=self.vale.pk, grasa="1.79", sng="8.90")
        self.vale.refresh_from_db()
        self.assertTrue(self.vale.evaluacion().cumple)

    def test_politica_apagada_conserva_bloqueo_antes_de_mover_leche(self):
        antes = MovimientoSilo.objects.count()
        with override_settings(CCAA_CALIDAD_INTERMEDIA_AVISO=False):
            with self.assertRaises(ValidationError):
                self._transferir()
        self.assertEqual(MovimientoSilo.objects.count(), antes)
        self.assertFalse(EjecucionProceso.objects.filter(vale=self.vale).exists())

    def test_transferencia_pendiente_conserva_origen_y_no_inventa_firma(self):
        antes = MovimientoSilo.objects.count()
        self._transferir()
        ejecucion = EjecucionProceso.objects.get(vale=self.vale)
        entrada = EntradaProceso.objects.get(ejecucion=ejecucion, silo=self.silo_descremada)
        self.assertEqual(entrada.salida_origen_id, self.fuente.pk)
        self.assertEqual(MovimientoSilo.objects.count(), antes + 3)
        self.assertEqual(saldo_silo(self.silo_descremada), Decimal("4849.55"))
        decision = LiberacionProceso.objects.get(salida=self.fuente)
        self.assertEqual(decision.estado, LiberacionProceso.Estado.PENDIENTE)
        self.assertIsNone(decision.firma_id)
        evento = EventoProceso.objects.get(ejecucion=ejecucion, tipo="continuidad_calidad_pendiente")
        self.assertEqual(evento.motivo, "transferir_estandarizacion")
        self.assertFalse(evento.datos["liberacion_final"])
        self.assertTrue(evento.datos["avisos"])
        with self.assertRaises(ValidationError):
            exigir_liberacion_salida_vigente(self.fuente.pk)

    def test_reintento_de_transferencia_no_duplica_libro_ni_evento(self):
        self._transferir()
        foto = (MovimientoSilo.objects.count(), EntradaProceso.objects.count(),
                EventoProceso.objects.filter(tipo="continuidad_calidad_pendiente").count())
        self._transferir()
        self.assertEqual(foto, (
            MovimientoSilo.objects.count(), EntradaProceso.objects.count(),
            EventoProceso.objects.filter(tipo="continuidad_calidad_pendiente").count(),
        ))

    def test_fallo_tardio_revierte_consumo_y_aviso(self):
        antes = MovimientoSilo.objects.count()
        with patch("estandarizacion.servicios.registrar_estandarizacion",
                   side_effect=ValidationError("fallo controlado")):
            with self.assertRaisesMessage(ValidationError, "fallo controlado"):
                self._transferir()
        self.vale.refresh_from_db()
        self.assertIsNone(self.vale.ejecutado_en)
        self.assertEqual(MovimientoSilo.objects.count(), antes)
        self.assertFalse(EventoProceso.objects.filter(tipo="continuidad_calidad_pendiente").exists())

    def test_vale_con_rc_conforme_continua_sin_volverse_liberado(self):
        self._muestrear_conforme()
        estandarizacion.continuar_pendiente(
            vale_id=self.vale.pk, usuario=self.usuario, motivo="Esperando segunda revisión de Calidad",
        )
        self.vale.refresh_from_db()
        ejecucion = EjecucionProceso.objects.get(vale=self.vale)
        self.silo_destino.refresh_from_db()
        self.assertEqual(self.vale.estado, self.vale.Estado.MUESTREADO)
        self.assertEqual(ejecucion.estado, EjecucionProceso.Estado.CERRADA)
        self.assertEqual(self.silo_destino.estado, Silo.Estado.PENDIENTE_CALIDAD)
        self.assertTrue(EventoProceso.objects.filter(
            ejecucion=ejecucion, tipo="continuidad_calidad_pendiente",
            motivo="cerrar_estandarizacion_pendiente",
        ).exists())
        # Un resultado conforme pendiente sigue sin firma final, incluso con la política activa.
        salida = ejecucion.salidas.get(silo=self.silo_destino)
        with self.assertRaises(ValidationError):
            exigir_liberacion_salida_vigente(salida.pk)
        antes = EventoProceso.objects.filter(ejecucion=ejecucion, tipo="continuidad_calidad_pendiente").count()
        estandarizacion.continuar_pendiente(
            vale_id=self.vale.pk, usuario=self.usuario, motivo="Reintento sin duplicar",
        )
        self.assertEqual(EventoProceso.objects.filter(
            ejecucion=ejecucion, tipo="continuidad_calidad_pendiente",
        ).count(), antes)

    def test_rc_fuera_de_objetivo_y_balance_incongruente_no_se_disimulan(self):
        self._transferir()
        estandarizacion.iniciar_agitacion(vale_id=self.vale.pk)
        estandarizacion.registrar_muestra(vale_id=self.vale.pk, grasa="2.20", sng="8.90")
        with self.assertRaises(ValidationError):
            estandarizacion.continuar_pendiente(
                vale_id=self.vale.pk, usuario=self.usuario, motivo="No debe tapar un RC adverso",
            )
        self.assertEqual(EjecucionProceso.objects.get(vale=self.vale).estado,
                         EjecucionProceso.Estado.EJECUCION)
        estandarizacion.ValeEstandarizacion.objects.filter(pk=self.vale.pk).update(
            grasa_real=Decimal("1.79"), volumen=Decimal("15001.00"),
        )
        with self.assertRaises(ValidationError):
            estandarizacion.continuar_pendiente(
                vale_id=self.vale.pk, usuario=self.usuario, motivo="No debe tapar litros discordantes",
            )

    def test_medicion_cruda_pendiente_queda_fotografiada_y_se_resuelve_sin_cambiarla(self):
        analisis = AnalisisSilo.objects.filter(silo=self.silo_entera).latest("pk")
        analisis.visualizado_por = None
        analisis.visualizado_en = None
        analisis.save(update_fields=["visualizado_por", "visualizado_en"])
        self._transferir()
        ejecucion = EjecucionProceso.objects.get(vale=self.vale)
        evento = EventoProceso.objects.get(
            ejecucion=ejecucion, tipo="continuidad_calidad_pendiente",
            motivo="transferir_estandarizacion",
        )
        fotos = evento.datos["analisis_silo_pendientes"]
        self.assertEqual([f["id"] for f in fotos], [str(analisis.pk)])
        with self.assertRaises(ValidationError):
            exigir_pendientes_entrada_resueltos(ejecucion.pk)
        analisis.visualizado_por = self.visualizador
        analisis.visualizado_en = timezone.now()
        analisis.save(update_fields=["visualizado_por", "visualizado_en"])
        exigir_pendientes_entrada_resueltos(ejecucion.pk)
        analisis.grasa = Decimal(analisis.grasa) + Decimal("0.01")
        analisis.save(update_fields=["grasa"])
        with self.assertRaises(ValidationError):
            exigir_pendientes_entrada_resueltos(ejecucion.pk)


@override_settings(CCAA_CALIDAD_INTERMEDIA_AVISO=True)
class DeudaSinMuestraTests(BaseVale):
    """La muestra tardíamente registrada debe representar el material consumido."""

    def setUp(self):
        self.vale = self.crear_vale()
        etapa = EtapaProceso.objects.get(codigo="estandarizar-test")
        self.ejecucion = EjecucionProceso.objects.create(
            codigo="CONT-DEUDA-CRUDA", etapa=etapa, vale=self.vale,
            sucursal=self.silo_entera.sucursal, responsable=self.usuario,
            estado=EjecucionProceso.Estado.CERRADA,
        )
        self.entrada = EntradaProceso.objects.create(
            ejecucion=self.ejecucion, silo=self.silo_entera,
            cantidad=Decimal("4000.000"), unidad="L",
        )
        self.ingreso_en = timezone.now() - timedelta(hours=2)
        self.retiro_en = self.ingreso_en + timedelta(minutes=30)
        MovimientoSilo.objects.create(
            silo=self.silo_entera, tipo=MovimientoSilo.Tipo.INGRESO,
            litros=Decimal("4000.00"), fecha_hora=self.ingreso_en,
            origen_tipo=MovimientoSilo.OrigenTipo.AJUSTE,
            motivo="Ingreso ficticio para probar deuda de muestra",
        )
        MovimientoSilo.objects.create(
            silo=self.silo_entera, tipo=MovimientoSilo.Tipo.SALIDA,
            litros=Decimal("4000.00"), fecha_hora=self.retiro_en,
            origen_tipo=MovimientoSilo.OrigenTipo.ESTANDARIZACION,
            origen_id=self.vale.pk, usuario=self.usuario,
            operacion_id=uuid5(NAMESPACE_URL, f"ccaa:estandarizacion:{self.vale.pk}"),
        )

    def _registrar_deuda(self):
        registrar(self.ejecucion, self.usuario, "consumo_crudo_sin_muestra", [])
        return EventoProceso.objects.get(
            ejecucion=self.ejecucion, tipo="continuidad_calidad_pendiente",
            motivo="consumo_crudo_sin_muestra",
        )

    def _muestra(self, tomado_en):
        return AnalisisSilo.objects.create(
            silo=self.silo_entera, tomado_en=tomado_en,
            grasa=Decimal("3.90"), sng=Decimal("8.60"),
            inhibidores_resultado=ControlInhibidores.Resultado.NEGATIVO,
            metodo=ControlInhibidores.Metodo.DELVO_SP,
            hora_lectura=timezone.localtime().time(),
            analista=self.usuario, visualizado_por=self.visualizador,
            visualizado_en=timezone.now(), estado=AnalisisSilo.Estado.CONFIRMADO,
        )

    def test_sin_muestra_deja_deuda_y_retiene_la_firma_final(self):
        evento = self._registrar_deuda()
        pendientes = evento.datos["analisis_silo_pendientes"]
        self.assertEqual(len(pendientes), 1)
        self.assertEqual(pendientes[0]["tipo"], "sin_muestra")
        self.assertEqual(str(pendientes[0]["entrada_id"]), str(self.entrada.pk))
        self.assertEqual(str(pendientes[0]["silo_id"]), str(self.silo_entera.pk))
        with self.assertRaises(ValidationError):
            exigir_pendientes_entrada_resueltos(self.ejecucion.pk)

    def test_muestra_de_llenado_futuro_no_salda_consumo_anterior(self):
        self._registrar_deuda()
        futuro = self.retiro_en + timedelta(minutes=10)
        MovimientoSilo.objects.create(
            silo=self.silo_entera, tipo=MovimientoSilo.Tipo.INGRESO,
            litros=Decimal("5000.00"), fecha_hora=futuro,
            origen_tipo=MovimientoSilo.OrigenTipo.AJUSTE,
            motivo="Nuevo llenado ficticio que no cubre el consumo anterior",
        )
        self._muestra(futuro + timedelta(minutes=5))
        with self.assertRaises(ValidationError):
            exigir_pendientes_entrada_resueltos(self.ejecucion.pk)

    def test_muestra_registrada_tarde_pero_tomada_antes_del_retiro_salda_deuda(self):
        self._registrar_deuda()
        with self.assertRaises(ValidationError):
            exigir_pendientes_entrada_resueltos(self.ejecucion.pk)
        self._muestra(self.ingreso_en + timedelta(minutes=10))
        exigir_pendientes_entrada_resueltos(self.ejecucion.pk)
