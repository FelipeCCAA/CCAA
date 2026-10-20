"""Retenciones de discrepancias del vale en Calidad e Inventario."""

import uuid
from datetime import timedelta

from django.core.exceptions import ValidationError
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from maestros.models import Silo
from procesos.models import EjecucionProceso
from procesos.servicios import registrar_estandarizacion
from recepcion.models import AnalisisSilo
from usuarios.models import PerfilUsuario, Rol

from .models import ActoValeEstandarizacion, ValeEstandarizacion
from .tests_vale import BaseVale


class RetencionValeTests(BaseVale):
    def _acto(
        self, vale, tipo, *, litros=None, medido=None, diferencia=None, silo=None
    ):
        if tipo in {"adicion", "retiro"} and silo is None:
            silo = self.silo_entera
        rectificacion = {} if diferencia is None else {"diferencia": diferencia}
        return ActoValeEstandarizacion.objects.create(
            vale=vale,
            clave=uuid.uuid4(),
            tipo=tipo,
            motivo="Prueba sintética de retención",
            litros=litros,
            silo_contraparte=silo,
            volumen_medido=medido,
            rectificacion=rectificacion,
            solicitud={
                "tipo": tipo,
                "litros": litros,
                "silo_contraparte": silo.pk if silo else None,
                "volumen_medido": medido,
                "rectificacion": rectificacion,
            },
            usuario=self.usuario,
        )

    def _vale_ejecutado(self, **cambios):
        vale = self.crear_vale(**cambios)
        vale.estado = ValeEstandarizacion.Estado.TRANSFERIDO
        vale.ejecutado_en = timezone.now()
        vale.save(update_fields=["estado", "ejecutado_en"])
        return vale

    def test_discrepancia_original_retiene_silo_y_salida(self):
        from .bloqueos import exigir_sin_retencion_salida, motivo_retencion_silo

        vale = self._vale_ejecutado(volumen="12000.00")
        self.assertIn(
            "componentes", motivo_retencion_silo(self.silo_destino.pk).lower()
        )
        salida = registrar_estandarizacion(vale=vale).salidas.get()
        with self.assertRaises(ValidationError):
            exigir_sin_retencion_salida(salida.pk)

    def test_medicion_diferente_retiene_silo(self):
        from .bloqueos import motivo_retencion_silo

        vale = self._vale_ejecutado()
        self._acto(vale, "medicion", medido="10001.00", diferencia="1.00")
        self.assertIn("1.00 L", motivo_retencion_silo(self.silo_destino.pk))

    def test_correccion_fisica_requiere_medicion_y_liberacion_nuevas(self):
        from .bloqueos import exigir_sin_retencion_salida

        vale = self._vale_ejecutado()
        ejecucion = registrar_estandarizacion(vale=vale)
        salida = ejecucion.salidas.get()
        self._acto(vale, "adicion", litros="2.00")
        with self.assertRaises(ValidationError):
            exigir_sin_retencion_salida(salida.pk)

        vale.estado = ValeEstandarizacion.Estado.LIBERADO
        vale.save(update_fields=["estado"])
        self._acto(vale, "medicion", medido="10002.00", diferencia="0.00")
        exigir_sin_retencion_salida(salida.pk)


class MuestraPosteriorActoTests(BaseVale):
    _acto = RetencionValeTests._acto
    _vale_ejecutado = RetencionValeTests._vale_ejecutado

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.calidad = get_user_model().objects.create_user("calidad-op02-muestra")
        PerfilUsuario.objects.create(
            usuario=cls.calidad,
            rol=Rol.CALIDAD,
            area=PerfilUsuario.Area.CALIDAD,
            empresa=cls.silo_entera.sucursal.empresa,
            sucursal=cls.silo_entera.sucursal,
        )

    def setUp(self):
        self.cliente_calidad = APIClient()
        self.cliente_calidad.force_authenticate(self.calidad)

    def _muestra_silo(self, silo, tomada_en):
        return AnalisisSilo.objects.create(
            silo=silo,
            tomado_en=tomada_en,
            grasa="3.50",
            sng="9.00",
            inhibidores_resultado="negativo",
            metodo="tri_sensor",
            hora_lectura=timezone.localtime(tomada_en).time(),
            analista=self.calidad,
            visualizado_por=self.calidad,
            visualizado_en=tomada_en,
            estado=AnalisisSilo.Estado.CONFIRMADO,
        )

    def test_liberacion_salida_requiere_muestra_posterior_a_correccion(self):
        vale = self._vale_ejecutado()
        ejecucion = registrar_estandarizacion(vale=vale)
        ejecucion.etapa.requiere_calidad = True
        ejecucion.etapa.save(update_fields=["requiere_calidad"])
        ejecucion.estado = EjecucionProceso.Estado.PENDIENTE_CONTROL
        ejecucion.save(update_fields=["estado"])
        salida = ejecucion.salidas.get()
        anterior = self._muestra_silo(salida.silo, timezone.now())
        acto = self._acto(vale, "adicion", litros="1.00")
        vale.estado = ValeEstandarizacion.Estado.LIBERADO
        vale.save(update_fields=["estado"])
        url = f"/api/calidad/resultados-proceso/{salida.pk}/liberar/"

        respuesta = self.cliente_calidad.post(
            url,
            {"analisis_id": anterior.pk},
            format="json",
        )
        self.assertEqual(respuesta.status_code, 409, respuesta.data)
        self.assertIn("posterior", respuesta.data["analisis_id"])

        nueva = self._muestra_silo(salida.silo, acto.creado_en + timedelta(seconds=1))
        respuesta = self.cliente_calidad.post(
            url,
            {"analisis_id": nueva.pk},
            format="json",
        )
        self.assertEqual(respuesta.status_code, 200, respuesta.data)

    def test_muestra_debe_ser_posterior_a_acto_de_otro_vale_que_afecta_el_silo(self):
        from calidad.views import _ultimo_acto_fisico_vale_salida

        vale = self._vale_ejecutado()
        salida = registrar_estandarizacion(vale=vale).salidas.get()
        otro_vale = self.crear_vale(codigo="VE-OTRO-SILO-TEST")
        acto = self._acto(otro_vale, "adicion", litros="1.00")

        self.assertEqual(_ultimo_acto_fisico_vale_salida(salida), acto.creado_en)
