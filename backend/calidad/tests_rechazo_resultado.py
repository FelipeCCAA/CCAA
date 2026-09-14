from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase
from rest_framework.test import APIClient

from maestros.models import Equipo, Silo
from procesos.models import EjecucionProceso, EtapaProceso, Proceso, SalidaProceso
from usuarios.models import Empresa, PerfilUsuario, Rol, Sucursal

from .models import LiberacionProceso


class RechazoResultadoProcesoTests(TestCase):
    def setUp(self):
        empresa = Empresa.objects.create(rut="QA-RECHAZO", nombre="Compatibilidad QA")
        self.planta = Sucursal.objects.create(
            empresa=empresa, codigo="QA-R", nombre="Registro técnico QA"
        )
        self.calidad = User.objects.create_user("qa-calidad-rechazo")
        PerfilUsuario.objects.create(
            usuario=self.calidad,
            empresa=empresa,
            sucursal=self.planta,
            rol=Rol.CALIDAD,
            area=PerfilUsuario.Area.CALIDAD,
        )
        self.cliente = APIClient()
        self.cliente.force_authenticate(self.calidad)
        proceso = Proceso.objects.create(codigo="qa-rechazo", nombre="QA rechazo")
        etapa = EtapaProceso.objects.create(
            proceso=proceso,
            codigo="qa-evaporar",
            nombre="Evaporación QA",
            tipo=EtapaProceso.Tipo.CONDENSACION,
            orden=1,
            requiere_calidad=True,
        )
        self.equipo = Equipo.objects.create(
            sucursal=self.planta,
            codigo="EV-QA-R",
            nombre="Evaporador Scheffers QA",
            tipo=Equipo.Tipo.EVAPORADOR,
        )
        self.ejecucion = EjecucionProceso.objects.create(
            codigo="EJ-QA-RESULTADO",
            etapa=etapa,
            sucursal=self.planta,
            equipo=self.equipo,
            estado=EjecucionProceso.Estado.PENDIENTE_CONTROL,
        )
        silo = Silo.objects.create(
            sucursal=self.planta,
            codigo="TK-QA-R",
            tipo=Silo.Tipo.SILO,
            capacidad_l=Decimal("1000"),
        )
        self.salida = SalidaProceso.objects.create(
            ejecucion=self.ejecucion,
            silo=silo,
            cantidad=Decimal("500"),
            unidad="L",
        )
        self.competidora = EjecucionProceso.objects.create(
            codigo="EJ-PROD-COMPETIDORA",
            etapa=etapa,
            sucursal=self.planta,
            equipo=self.equipo,
            estado=EjecucionProceso.Estado.EJECUCION,
        )

    def test_rechazar_material_no_intenta_readquirir_el_equipo(self):
        respuesta = self.cliente.post(
            f"/api/calidad/resultados-proceso/{self.salida.pk}/rechazar/",
            {"motivo": "Resultado fuera de especificación"},
            format="json",
        )

        self.assertEqual(respuesta.status_code, 200, respuesta.content)
        self.assertEqual(respuesta.data["code"], "RESULTADO_RECHAZADO")
        self.assertEqual(
            LiberacionProceso.objects.get(salida=self.salida).estado,
            LiberacionProceso.Estado.RECHAZADO,
        )
        self.ejecucion.refresh_from_db()
        self.competidora.refresh_from_db()
        self.assertEqual(self.ejecucion.estado, EjecucionProceso.Estado.CERRADA)
        self.assertEqual(
            self.competidora.estado, EjecucionProceso.Estado.EJECUCION
        )

    def test_mantiene_pendiente_la_ejecucion_si_falta_decidir_otra_salida(self):
        otro_silo = Silo.objects.create(
            sucursal=self.planta,
            codigo="TK-QA-R-2",
            tipo=Silo.Tipo.SILO,
            capacidad_l=Decimal("1000"),
        )
        SalidaProceso.objects.create(
            ejecucion=self.ejecucion,
            silo=otro_silo,
            cantidad=Decimal("100"),
            unidad="L",
        )

        respuesta = self.cliente.post(
            f"/api/calidad/resultados-proceso/{self.salida.pk}/rechazar/",
            {"motivo": "Una rama fuera de especificación"},
            format="json",
        )

        self.assertEqual(respuesta.status_code, 200)
        self.ejecucion.refresh_from_db()
        self.assertEqual(
            self.ejecucion.estado, EjecucionProceso.Estado.PENDIENTE_CONTROL
        )
