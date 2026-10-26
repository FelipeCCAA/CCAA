"""Un remuestreo conforme no dispone un resultado adverso conocido."""
from copy import copy
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import override_settings
from django.utils import timezone

from calidad import tests_continuidad_adversos as escenarios
from calidad import tests_continuidad_produccion as produccion_escenarios
from calidad.continuidad import AprobacionPendiente, comprobar_salida, exigir_pendientes_entrada_resueltos, registrar
from calidad.models import LiberacionProceso
from estandarizacion.tests_vale import BaseVale
from maestros.models import Especificacion
from procesos.models import EjecucionProceso, EventoProceso
from produccion.models import Analisis
from recepcion.models import AnalisisSilo, MovimientoSilo
from recepcion.servicios import motivos_silo_no_disponible


@override_settings(CCAA_CALIDAD_INTERMEDIA_AVISO=True)
class RemuestreoNoDisponeAdversoTests(BaseVale):
    _fuente = escenarios.ContinuidadAdversosTests._fuente
    setUp = escenarios.ContinuidadAdversosTests.setUp

    def _otra_muestra(self, anterior, **datos):
        nueva = copy(anterior)
        nueva.pk = None
        nueva.tomado_en = timezone.now()
        for campo, valor in datos.items():
            setattr(nueva, campo, valor)
        nueva.save(force_insert=True)
        return nueva

    def _sin_muestra_ligada(self):
        decision = LiberacionProceso.objects.get(salida=self.fuente)
        muestra = decision.analisis_silo
        decision.analisis_silo = None
        decision.save(update_fields=["analisis_silo"])
        return muestra

    def test_negativo_posterior_no_oculta_positivo_del_mismo_material(self):
        anterior = self._sin_muestra_ligada()
        anterior.inhibidores_resultado = "positivo"
        anterior.save(update_fields=["inhibidores_resultado"])
        self._otra_muestra(anterior, inhibidores_resultado="negativo")
        with self.assertRaisesMessage(ValidationError, "Inhibidores positivos"):
            comprobar_salida(self.fuente.pk)

    def test_conforme_posterior_no_oculta_no_conforme_del_mismo_material(self):
        anterior = self._sin_muestra_ligada()
        anterior.grasa = Decimal("3.5")
        anterior.save(update_fields=["grasa"])
        Especificacion.objects.create(
            producto=self.producto_ld, tipo_analisis=Especificacion.TipoAnalisis.SILO,
            version=1, vigente_desde=timezone.localdate(self.fuente.registrada_en),
            rangos={"mg": {"min": 0.0, "max": 1.0, "obligatorio": True}},
            fuente="Especificación ficticia para regresión",
        )
        self._otra_muestra(anterior, grasa=Decimal("0.2"))
        with self.assertRaisesMessage(ValidationError, "no conforme"):
            comprobar_salida(self.fuente.pk)

    def test_origen_crudo_no_oculta_positivo_con_otra_muestra_negativa(self):
        anterior = AnalisisSilo.objects.filter(silo=self.silo_entera).latest("pk")
        anterior.inhibidores_resultado = "positivo"
        anterior.save(update_fields=["inhibidores_resultado"])
        self._otra_muestra(anterior, inhibidores_resultado="negativo")
        motivos = motivos_silo_no_disponible(self.silo_entera, para="proceso", permitir_pendientes=True)
        self.assertTrue(any("inhibidores positivos" in motivo.lower() for motivo in motivos), motivos)

    def test_ajuste_a_cero_no_equivale_a_vaciado_fisico_del_origen(self):
        anterior = AnalisisSilo.objects.filter(silo=self.silo_entera).latest("pk")
        anterior.inhibidores_resultado = "positivo"
        anterior.save(update_fields=["inhibidores_resultado"])
        for tipo, litros in (("ajuste", "-20000"), ("ingreso", "20000")):
            MovimientoSilo.objects.create(silo=self.silo_entera, tipo=tipo, litros=litros,
                                         fecha_hora=timezone.now(), origen_tipo="ajuste", motivo="Ensayo ficticio")
        self._otra_muestra(anterior, inhibidores_resultado="negativo")
        motivos = motivos_silo_no_disponible(self.silo_entera, para="proceso", permitir_pendientes=True)
        self.assertTrue(any("inhibidores positivos" in motivo.lower() for motivo in motivos), motivos)

    def test_vaciado_fisico_separa_muestras_de_llenados_distintos(self):
        anterior = AnalisisSilo.objects.filter(silo=self.silo_entera).latest("pk")
        anterior.inhibidores_resultado = "positivo"
        anterior.save(update_fields=["inhibidores_resultado"])
        for tipo in ("salida", "ingreso"):
            MovimientoSilo.objects.create(silo=self.silo_entera, tipo=tipo, litros="20000",
                                         fecha_hora=timezone.now(), origen_tipo="ajuste", motivo="Ensayo ficticio")
        self._otra_muestra(anterior, inhibidores_resultado="negativo")
        motivos = motivos_silo_no_disponible(self.silo_entera, para="proceso", permitir_pendientes=True)
        self.assertFalse(any("inhibidores positivos" in motivo.lower() for motivo in motivos), motivos)

    def test_muestra_adversa_de_llenado_futuro_no_se_atribuye_a_salida_anterior(self):
        anterior = self._sin_muestra_ligada()
        for tipo in ("salida", "ingreso"):
            MovimientoSilo.objects.create(silo=self.silo_descremada, tipo=tipo, litros="9150.08",
                                         fecha_hora=timezone.now(), origen_tipo="ajuste", motivo="Ensayo ficticio")
        self._otra_muestra(anterior, inhibidores_resultado="positivo")
        firma, avisos = comprobar_salida(self.fuente.pk)
        self.assertIsNone(firma)
        self.assertTrue(avisos)

    def test_salida_con_silo_no_oculta_analisis_adverso_del_lote(self):
        especificacion = Especificacion.objects.create(
            producto=self.producto_ld, version=1, vigente_desde=timezone.localdate(),
            rangos={"mg": {"min": 0.0, "max": 1.0, "obligatorio": True}},
            fuente="Rango ficticio aplicado a análisis de lote",
        )
        Analisis.objects.create(lote=self.fuente.lote, fecha=timezone.localdate(),
                                especificacion=especificacion, valores={"mg": 3.5})
        with self.assertRaisesMessage(ValidationError, "no conforme"):
            comprobar_salida(self.fuente.pk)

    def test_positivo_tardio_del_origen_completo_bloquea_sus_descendientes(self):
        # Al consumir no había deuda de firma ni resultado adverso conocido.
        anterior = AnalisisSilo.objects.filter(silo=self.silo_entera).latest("pk")
        from estandarizacion.servicios import transferir
        transferir(vale_id=self.vale.pk, usuario=self.usuario)
        ejecucion = EjecucionProceso.objects.get(vale=self.vale)
        self._otra_muestra(anterior, tomado_en=anterior.tomado_en + timezone.timedelta(microseconds=1),
                           inhibidores_resultado="positivo")
        with self.assertRaises(ValidationError) as error:
            exigir_pendientes_entrada_resueltos(ejecucion.pk)
        self.assertNotIsInstance(error.exception, AprobacionPendiente)

    def test_adicion_sin_vaciado_no_oculta_resultado_tardio_del_contenido_anterior(self):
        anterior = AnalisisSilo.objects.filter(silo=self.silo_entera).latest("pk")
        MovimientoSilo.objects.create(silo=self.silo_entera, tipo="ingreso", litros="100",
                                     fecha_hora=timezone.now(), origen_tipo="ajuste", motivo="Adición ficticia")
        self._otra_muestra(anterior)
        from estandarizacion.servicios import transferir
        transferir(vale_id=self.vale.pk, usuario=self.usuario)
        ejecucion = EjecucionProceso.objects.get(vale=self.vale)
        self._otra_muestra(anterior, tomado_en=anterior.tomado_en + timezone.timedelta(microseconds=1),
                           inhibidores_resultado="positivo")
        with self.assertRaises(ValidationError) as error:
            exigir_pendientes_entrada_resueltos(ejecucion.pk)
        self.assertNotIsInstance(error.exception, AprobacionPendiente)

    def test_otro_acto_no_fotografia_muestra_posterior_al_retiro_original(self):
        original = AnalisisSilo.objects.filter(silo=self.silo_entera).latest("pk")
        from estandarizacion.servicios import transferir
        transferir(vale_id=self.vale.pk, usuario=self.usuario)
        ejecucion = EjecucionProceso.objects.get(vale=self.vale)
        futuro = self._otra_muestra(original)
        registrar(ejecucion, self.usuario, "segundo_acto_operacional", ["Firma de salida pendiente"])
        evento = EventoProceso.objects.get(ejecucion=ejecucion, motivo="segundo_acto_operacional")
        fotos = evento.datos["analisis_silo_pendientes"]
        self.assertIn(str(original.pk), [f["id"] for f in fotos])
        self.assertNotIn(str(futuro.pk), [f["id"] for f in fotos])


@override_settings(CCAA_CALIDAD_INTERMEDIA_AVISO=True)
class ResultadoTardioDeudaTests(BaseVale):
    setUp = produccion_escenarios.DeudaSinMuestraTests.setUp
    _registrar_deuda = produccion_escenarios.DeudaSinMuestraTests._registrar_deuda
    _muestra = produccion_escenarios.DeudaSinMuestraTests._muestra

    def test_deuda_sin_muestra_con_positivo_y_negativo_no_se_libera(self):
        self._registrar_deuda()
        positivo = self._muestra(self.ingreso_en + timezone.timedelta(minutes=5))
        positivo.inhibidores_resultado = "positivo"
        positivo.save(update_fields=["inhibidores_resultado"])
        self._muestra(self.ingreso_en + timezone.timedelta(minutes=10))
        with self.assertRaises(ValidationError) as error:
            exigir_pendientes_entrada_resueltos(self.ejecucion.pk)
        self.assertNotIsInstance(error.exception, AprobacionPendiente)
