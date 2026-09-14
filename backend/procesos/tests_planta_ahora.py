from datetime import date
from decimal import Decimal

from django.contrib.auth.models import User
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.utils import timezone
from rest_framework.test import APIClient

from maestros.models import Equipo, Silo
from recepcion.models import MovimientoSilo, Recepcion
from usuarios.models import Empresa, PerfilUsuario, Rol, Sucursal

from .consultas_planta import consultar_planta_ahora
from .models import EjecucionProceso, EtapaProceso, Proceso


class PlantaAhoraTests(TestCase):
    def setUp(self):
        # Solo compatibilidad de campos históricos obligatorios. Planta Ahora
        # no consulta estas relaciones ni las expone en su contrato.
        self.empresa_legacy = Empresa.objects.create(
            rut="PA-LEGACY-1", nombre="Compatibilidad histórica"
        )
        self.sucursal_legacy = Sucursal.objects.create(
            empresa=self.empresa_legacy,
            codigo="PA-LEGACY",
            nombre="Registro histórico",
        )
        self.usuario = User.objects.create_user("supervisor-planta")
        PerfilUsuario.objects.create(
            usuario=self.usuario,
            empresa=self.empresa_legacy,
            sucursal=self.sucursal_legacy,
            alcance=PerfilUsuario.Alcance.SUCURSAL,
            area=PerfilUsuario.Area.ADMINISTRACION,
            rol=Rol.ADMIN,
        )
        proceso = Proceso.objects.create(codigo="panel", nombre="Panel")
        self.etapa = EtapaProceso.objects.create(
            proceso=proceso,
            codigo="secado-panel",
            nombre="Secado panel",
            tipo=EtapaProceso.Tipo.SECADO,
            orden=1,
        )
        self.equipo = Equipo.objects.create(
            sucursal=self.sucursal_legacy,
            codigo="TOR-PA",
            nombre="Torre Planta Ahora",
            tipo=Equipo.Tipo.TORRE,
        )

    @staticmethod
    def _cliente(usuario):
        cliente = APIClient()
        cliente.force_authenticate(usuario)
        return cliente

    def _ejecucion(self, codigo, estado, *, sucursal=None, equipo=None):
        return EjecucionProceso.objects.create(
            sucursal=sucursal or self.sucursal_legacy,
            codigo=codigo,
            etapa=self.etapa,
            equipo=equipo,
            responsable=self.usuario,
            estado=estado,
        )

    def test_contrato_entrega_conteos_completos_y_alertas_operacionales(self):
        self._ejecucion(
            "PA-ACTIVA", EjecucionProceso.Estado.EJECUCION, equipo=self.equipo
        )
        self._ejecucion("PA-CALIDAD", EjecucionProceso.Estado.PENDIENTE_CONTROL)
        self._ejecucion("PA-BLOQUEADA", EjecucionProceso.Estado.BLOQUEADA)
        self._ejecucion("PA-CERRADA", EjecucionProceso.Estado.CERRADA)
        Recepcion.objects.create(
            sucursal=self.sucursal_legacy,
            fecha=date(2026, 9, 11),
            tipo_leche=Recepcion.TipoLeche.ENTERA,
            litros=1000,
            estado=Recepcion.Estado.REGISTRADA,
        )
        Recepcion.objects.create(
            sucursal=self.sucursal_legacy,
            fecha=date(2026, 9, 11),
            tipo_leche=Recepcion.TipoLeche.ENTERA,
            litros=500,
            estado=Recepcion.Estado.RETENIDA,
            motivo="Control pendiente",
        )
        silo = Silo.objects.create(
            sucursal=self.sucursal_legacy,
            codigo="S-PA",
            tipo=Silo.Tipo.SILO,
            capacidad_l=100,
        )
        MovimientoSilo.objects.create(
            silo=silo,
            tipo=MovimientoSilo.Tipo.INGRESO,
            litros=120,
            fecha_hora=timezone.now(),
        )

        respuesta = self._cliente(self.usuario).get("/api/procesos/planta-ahora/")

        self.assertEqual(respuesta.status_code, 200, respuesta.data)
        self.assertNotIn("alcance", respuesta.data)
        self.assertEqual(respuesta.data["indicadores"]["procesos_activos"], 1)
        self.assertEqual(respuesta.data["indicadores"]["esperando_calidad"], 1)
        self.assertEqual(respuesta.data["indicadores"]["bloqueos"], 1)
        self.assertEqual(respuesta.data["indicadores"]["equipos_ocupados"], 1)
        self.assertEqual(respuesta.data["indicadores"]["recepciones_pendientes"], 1)
        self.assertEqual(respuesta.data["indicadores"]["recepciones_retenidas"], 1)
        self.assertEqual(respuesta.data["indicadores"]["silos_en_alerta"], 1)
        self.assertEqual(respuesta.data["procesos_por_etapa"][0]["total"], 3)
        self.assertEqual(respuesta.data["silos"]["litros"], Decimal("120.00"))
        self.assertEqual(
            {alerta["codigo"] for alerta in respuesta.data["alertas"]},
            {
                "procesos_bloqueados",
                "recepciones_retenidas",
                "silos_en_alerta",
                "calidad_pendiente",
            },
        )

    def test_campos_historicos_no_segmentan_los_conteos(self):
        otra_empresa_legacy = Empresa.objects.create(
            rut="PA-LEGACY-2", nombre="Otro dato histórico"
        )
        otra_sucursal_legacy = Sucursal.objects.create(
            empresa=otra_empresa_legacy,
            codigo="PA-LEGACY-2",
            nombre="Otro registro histórico",
        )
        equipo_legacy = Equipo.objects.create(
            sucursal=otra_sucursal_legacy,
            codigo="TOR-LEGACY-2",
            nombre="Torre histórica 2",
            tipo=Equipo.Tipo.TORRE,
        )
        self._ejecucion(
            "PA-PRIMERA", EjecucionProceso.Estado.EJECUCION, equipo=self.equipo
        )
        self._ejecucion(
            "PA-SEGUNDA",
            EjecucionProceso.Estado.BLOQUEADA,
            sucursal=otra_sucursal_legacy,
            equipo=equipo_legacy,
        )
        Recepcion.objects.create(
            sucursal=otra_sucursal_legacy,
            fecha=date(2026, 9, 11),
            tipo_leche=Recepcion.TipoLeche.ENTERA,
            litros=888,
            estado=Recepcion.Estado.RETENIDA,
            motivo="Debe contarse por su estado operacional",
        )

        datos = consultar_planta_ahora()

        self.assertEqual(datos["indicadores"]["procesos_activos"], 1)
        self.assertEqual(datos["indicadores"]["bloqueos"], 1)
        self.assertEqual(datos["indicadores"]["recepciones_retenidas"], 1)
        self.assertEqual(
            {item["codigo"] for item in datos["actividad_reciente"]},
            {"PA-PRIMERA", "PA-SEGUNDA"},
        )

    def test_numero_de_consultas_no_crece_con_la_actividad_reciente(self):
        self._ejecucion("PA-BASE", EjecucionProceso.Estado.PREPARACION)
        with CaptureQueriesContext(connection) as una:
            consultar_planta_ahora()
        for indice in range(10):
            self._ejecucion(
                f"PA-ESCALA-{indice}", EjecucionProceso.Estado.PENDIENTE_CONTROL
            )
        with CaptureQueriesContext(connection) as varias:
            consultar_planta_ahora()

        self.assertEqual(len(una), len(varias))

    def test_permiso_depende_de_responsabilidad_y_no_de_scope(self):
        trabajador = User.objects.create_user("trabajador-sin-jefatura")
        PerfilUsuario.objects.create(
            usuario=trabajador,
            empresa=self.empresa_legacy,
            sucursal=self.sucursal_legacy,
            alcance=PerfilUsuario.Alcance.SUCURSAL,
            area=PerfilUsuario.Area.SECADO,
            rol=Rol.PRODUCCION,
        )

        respuesta = self._cliente(trabajador).get("/api/procesos/planta-ahora/")

        self.assertEqual(respuesta.status_code, 403)
