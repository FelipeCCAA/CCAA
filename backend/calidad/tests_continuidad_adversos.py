"""Los hallazgos adversos siguen deteniendo el flujo con la política activa."""
from datetime import time
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import override_settings
from django.utils import timezone

from calidad.continuidad import comprobar_salida
from calidad.models import LiberacionProceso
from estandarizacion import servicios as estandarizacion
from estandarizacion import tests_f01_f02_materiales as escenarios
from estandarizacion.tests_vale import BaseVale
from inocuidad.models import MonitoreoPPRO, PproLectura
from maestros.models import Equipo, Especificacion, Silo
from procesos.models import EjecucionProceso, EventoProceso
from produccion.models import ControlProceso, ControlProcesoLectura
from recepcion.models import AnalisisSilo, ControlInhibidores, MovimientoSilo


@override_settings(CCAA_CALIDAD_INTERMEDIA_AVISO=True)
class ContinuidadAdversosTests(BaseVale):
    # Reutilizar la preparación material sin heredar sus casos de prueba.
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

    def _rechazar_transferencia_sin_efecto_fisico(self):
        movimientos = MovimientoSilo.objects.count()
        with self.assertRaises(ValidationError):
            estandarizacion.transferir(vale_id=self.vale.pk, usuario=self.usuario)
        self.assertEqual(MovimientoSilo.objects.count(), movimientos)
        self.assertFalse(EjecucionProceso.objects.filter(vale=self.vale).exists())
        self.assertFalse(EventoProceso.objects.filter(tipo="continuidad_calidad_pendiente").exists())

    def test_rechazo_explicito_de_calidad_bloquea_la_transferencia(self):
        decision = LiberacionProceso.objects.get(salida=self.fuente)
        decision.estado = LiberacionProceso.Estado.RECHAZADO
        decision.save(update_fields=["estado"])
        self._rechazar_transferencia_sin_efecto_fisico()

    def test_inhibidores_positivos_en_origen_crudo_siguen_bloqueando(self):
        analisis = AnalisisSilo.objects.filter(silo=self.silo_entera).latest("pk")
        analisis.inhibidores_resultado = ControlInhibidores.Resultado.POSITIVO
        analisis.save(update_fields=["inhibidores_resultado"])
        self._rechazar_transferencia_sin_efecto_fisico()

    def test_inhibidores_positivos_en_salida_intermedia_siguen_bloqueando(self):
        decision = LiberacionProceso.objects.get(salida=self.fuente)
        analisis = decision.analisis_silo
        analisis.inhibidores_resultado = ControlInhibidores.Resultado.POSITIVO
        analisis.save(update_fields=["inhibidores_resultado"])
        self._rechazar_transferencia_sin_efecto_fisico()

    def test_medicion_real_fuera_de_especificacion_no_es_solo_firma_pendiente(self):
        decision = LiberacionProceso.objects.get(salida=self.fuente)
        self.assertGreater(decision.analisis_silo.grasa, Decimal("1.0"))
        Especificacion.objects.create(
            producto=self.producto_ld,
            tipo_analisis=Especificacion.TipoAnalisis.SILO,
            version=1,
            vigente_desde=timezone.localdate(self.fuente.registrada_en),
            rangos={"mg": {"min": 0.0, "max": 1.0, "obligatorio": True}},
            fuente="Rango ficticio para probar el bloqueo del análisis real",
        )
        with self.assertRaisesMessage(ValidationError, "no conforme"):
            comprobar_salida(self.fuente.pk)
        self._rechazar_transferencia_sin_efecto_fisico()

    def test_silo_bloqueado_o_en_cip_no_se_abre_por_el_aviso(self):
        for estado in (Silo.Estado.BLOQUEADO_CALIDAD, Silo.Estado.EN_CIP):
            with self.subTest(estado=estado):
                self.silo_entera.estado = estado
                self.silo_entera.save(update_fields=["estado"])
                self._rechazar_transferencia_sin_efecto_fisico()

    def test_pcc1_fuera_de_limite_bloquea_la_salida_pendiente(self):
        equipo = Equipo.objects.create(
            codigo="PCC-CONTINUAR", nombre="Evaporador de regresión",
            tipo=Equipo.Tipo.EVAPORADOR,
        )
        control = ControlProceso.objects.create(
            lote=self.fuente.lote, equipo=equipo, fecha=timezone.localdate(),
            pcc1_temp_min=Decimal("80.0"),
        )
        ControlProcesoLectura.objects.create(
            control=control, hora=time(10, 0), valores={"t_dsi": 75.0},
        )
        with self.assertRaisesMessage(ValidationError, "PCC 1"):
            comprobar_salida(self.fuente.pk)
        self._rechazar_transferencia_sin_efecto_fisico()

    def test_ppro_no_ok_sin_accion_correctiva_bloquea_la_salida(self):
        monitoreo = MonitoreoPPRO.objects.create(
            lote=self.fuente.lote, tipo=MonitoreoPPRO.Tipo.DETECTOR_METALES,
            fecha=timezone.localdate(),
        )
        PproLectura.objects.create(
            monitoreo=monitoreo, hora=time(10, 0), resultado=PproLectura.Resultado.NO_OK,
        )
        with self.assertRaisesMessage(ValidationError, "acción correctiva"):
            comprobar_salida(self.fuente.pk)
        self._rechazar_transferencia_sin_efecto_fisico()
