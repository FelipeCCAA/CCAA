from datetime import timedelta

from django.core.exceptions import ValidationError
from django.utils import timezone
from rest_framework.test import APIClient

from recepcion.models import AnalisisSilo, ControlInhibidores, MovimientoSilo
from usuarios.models import PerfilUsuario, Rol

from . import servicios
from .tests_vale import BaseVale


class CompuertaMuestreoEstandarizacionTests(BaseVale):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        PerfilUsuario.objects.update_or_create(
            usuario=cls.usuario,
            defaults={
                "rol": Rol.RECEPCION,
                "empresa": cls.silo_entera.sucursal.empresa,
                "sucursal": cls.silo_entera.sucursal,
            },
        )

    def setUp(self):
        self.cliente = APIClient()
        self.cliente.force_authenticate(self.usuario)

    def _analizar(self, silo, **extra):
        datos = {
            "silo": silo,
            "tomado_en": timezone.now(),
            "grasa": "4.20",
            "sng": "8.80",
            "inhibidores_resultado": ControlInhibidores.Resultado.NEGATIVO,
            "metodo": ControlInhibidores.Metodo.DELVO_SP,
            "hora_lectura": timezone.localtime().time(),
            "analista": self.usuario,
            "visualizado_por": self.usuario,
            "visualizado_en": timezone.now(),
            "estado": AnalisisSilo.Estado.CONFIRMADO,
        }
        datos.update(extra)
        return AnalisisSilo.objects.create(**datos)

    def test_transferir_sin_analisis_responde_409_con_motivo(self):
        vale = self.crear_vale()
        self.abastecer_origenes()
        respuesta = self.cliente.post(
            f"/api/estandarizacion/vales/{vale.id}/transferir/", {}, format="json"
        )
        self.assertEqual(respuesta.status_code, 409)
        self.assertIn("análisis", respuesta.data["detail"])

    def test_ingreso_posterior_invalida_y_bloquea(self):
        vale = self.crear_vale()
        self.abastecer_origenes()
        self._analizar(self.silo_entera)
        self._analizar(self.silo_descremada)
        MovimientoSilo.objects.create(
            silo=self.silo_entera,
            tipo=MovimientoSilo.Tipo.INGRESO,
            litros="10.00",
            fecha_hora=timezone.now() + timedelta(seconds=1),
            motivo="Nuevo camión",
        )
        with self.assertRaisesMessage(ValidationError, "vuelve a muestrear"):
            servicios.transferir(vale_id=vale.id, usuario=self.usuario)

    def test_analisis_vigentes_y_negativos_permiten_transferir(self):
        vale = self.crear_vale()
        self.abastecer_origenes()
        self._analizar(self.silo_entera)
        self._analizar(self.silo_descremada)
        transferido = servicios.transferir(vale_id=vale.id, usuario=self.usuario)
        self.assertEqual(transferido.estado, transferido.Estado.TRANSFERIDO)
