"""Pruebas del modelo de lectura de resultados productivos para Calidad."""

from decimal import Decimal

from django.contrib.auth.models import User
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from rest_framework.test import APIClient

from maestros.models import Silo
from procesos.models import EjecucionProceso, EtapaProceso, Proceso, SalidaProceso
from usuarios.models import Empresa, PerfilUsuario, Rol, Sucursal

from .consultas import consultar_resultados_intermedios


class ConsultaResultadosProcesoTests(TestCase):
    def setUp(self):
        self.empresa = Empresa.objects.create(rut="COLA-CAL-1", nombre="Empresa uno")
        self.sucursal = Sucursal.objects.create(
            empresa=self.empresa, codigo="P1", nombre="Planta uno"
        )
        self.usuario = User.objects.create_user("calidad-consultas")
        PerfilUsuario.objects.create(
            usuario=self.usuario,
            empresa=self.empresa,
            sucursal=self.sucursal,
            rol=Rol.CALIDAD,
            area=PerfilUsuario.Area.CALIDAD,
        )
        self.proceso = Proceso.objects.create(codigo="cola-calidad", nombre="Cola")
        self.etapa = EtapaProceso.objects.create(
            proceso=self.proceso,
            codigo="controlar",
            nombre="Controlar intermedio",
            tipo=EtapaProceso.Tipo.CONDENSACION,
            orden=1,
            requiere_calidad=True,
        )

    def _crear_salida(self, *, sucursal, correlativo):
        ejecucion = EjecucionProceso.objects.create(
            codigo=f"EJ-COLA-{sucursal.codigo}-{correlativo}",
            etapa=self.etapa,
            sucursal=sucursal,
            estado=EjecucionProceso.Estado.PENDIENTE_CONTROL,
        )
        silo = Silo.objects.create(
            sucursal=sucursal,
            codigo=f"TK-{correlativo}",
            tipo=Silo.Tipo.SILO,
            capacidad_l=Decimal("1000"),
        )
        return SalidaProceso.objects.create(
            ejecucion=ejecucion,
            silo=silo,
            cantidad=Decimal("100"),
            unidad="L",
        )

    def _consultar(self):
        return consultar_resultados_intermedios(
            self.usuario,
            solo_pendientes=True,
            pagina=1,
            limite=50,
        )

    def test_empresa_historica_no_oculta_trabajo_de_calidad(self):
        propia = self._crear_salida(sucursal=self.sucursal, correlativo=1)
        otra_empresa = Empresa.objects.create(rut="COLA-CAL-2", nombre="Empresa dos")
        otra_sucursal = Sucursal.objects.create(
            empresa=otra_empresa, codigo="P2", nombre="Planta dos"
        )
        ajena = self._crear_salida(sucursal=otra_sucursal, correlativo=2)

        resultados, total = self._consultar()

        self.assertEqual(total, 2)
        self.assertEqual(
            {item["id"] for item in resultados},
            {propia.id, ajena.id},
        )

    def test_el_numero_de_consultas_no_crece_por_resultado(self):
        self._crear_salida(sucursal=self.sucursal, correlativo=1)
        with CaptureQueriesContext(connection) as consultas_pocas:
            self._consultar()

        for correlativo in range(2, 12):
            self._crear_salida(sucursal=self.sucursal, correlativo=correlativo)
        with CaptureQueriesContext(connection) as consultas_muchas:
            self._consultar()

        self.assertEqual(
            len(consultas_pocas),
            len(consultas_muchas),
            (
                f"con 1 resultado hizo {len(consultas_pocas)} consultas y con 11 "
                f"hizo {len(consultas_muchas)}: existe un N+1"
            ),
        )

    def test_expedientes_ignora_el_parametro_legado_y_no_mezcla_procesos(self):
        self._crear_salida(sucursal=self.sucursal, correlativo=1)
        cliente = APIClient()
        cliente.force_authenticate(self.usuario)

        respuesta = cliente.get("/api/calidad/expedientes/", {"incluir_procesos": "1"})

        self.assertEqual(respuesta.status_code, 200, respuesta.data)
        self.assertNotIn("procesos", respuesta.data)
