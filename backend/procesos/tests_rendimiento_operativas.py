from decimal import Decimal

from django.contrib.auth.models import User
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from rest_framework.test import APIRequestFactory, force_authenticate

from maestros.models import Silo

from .models import (
    EjecucionProceso,
    EntradaProceso,
    EtapaProceso,
    Proceso,
    SalidaProceso,
)
from .views import EjecucionProcesoViewSet


class RendimientoBandejaOperativaTests(TestCase):
    def setUp(self):
        self.usuario = User.objects.create_superuser("perf-operativas")
        proceso = Proceso.objects.create(codigo="perf", nombre="Rendimiento")
        self.etapa = EtapaProceso.objects.create(
            proceso=proceso,
            codigo="perf-etapa",
            nombre="Etapa rendimiento",
            tipo=EtapaProceso.Tipo.SECADO,
            orden=1,
        )
        self.silo = Silo.objects.create(codigo="PERF-SILO", capacidad_l=10000)
        self.vista = EjecucionProcesoViewSet.as_view({"get": "operativas"})

    def _crear_ejecucion(self, numero):
        ejecucion = EjecucionProceso.objects.create(
            codigo=f"PERF-{numero}", etapa=self.etapa
        )
        EntradaProceso.objects.create(
            ejecucion=ejecucion,
            silo=self.silo,
            cantidad=Decimal("100"),
            unidad="L",
        )
        SalidaProceso.objects.create(
            ejecucion=ejecucion,
            silo=self.silo,
            cantidad=Decimal("90"),
            unidad="L",
        )

    def _consultar(self):
        request = APIRequestFactory().get("/api/procesos/ejecuciones/operativas/")
        force_authenticate(request, self.usuario)
        with CaptureQueriesContext(connection) as consultas:
            respuesta = self.vista(request)
        self.assertEqual(respuesta.status_code, 200)
        return respuesta.data, len(consultas)

    def test_entradas_y_salidas_no_agregan_consultas_por_ejecucion(self):
        self._crear_ejecucion(1)
        # DRF calcula y guarda los permisos del usuario en el primer acceso;
        # la medición compara exclusivamente el modelo de lectura operacional.
        self._consultar()
        una, consultas_una = self._consultar()

        for numero in range(2, 11):
            self._crear_ejecucion(numero)
        varias, consultas_varias = self._consultar()

        self.assertEqual(consultas_una, 3)
        self.assertEqual(consultas_varias, consultas_una)
        self.assertEqual(len(una), 1)
        self.assertEqual(len(varias), 10)
