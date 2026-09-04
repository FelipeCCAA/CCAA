from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

from django.contrib.auth.models import User
from django.db import close_old_connections
from django.test import TransactionTestCase
from rest_framework.test import APIClient

from maestros.models import Equipo
from usuarios.models import Empresa, PerfilUsuario, Rol, Sucursal

from .models import EjecucionProceso, EtapaProceso, Proceso


class ConcurrenciaVersionEjecucionTests(TransactionTestCase):
    reset_sequences = True

    def setUp(self):
        empresa = Empresa.objects.create(
            rut="77.900.100-8", nombre="Concurrencia procesos"
        )
        sucursal = Sucursal.objects.create(
            empresa=empresa, codigo="CON", nombre="Planta concurrencia"
        )
        self.usuario = User.objects.create_user("operador-concurrente")
        PerfilUsuario.objects.create(
            usuario=self.usuario, empresa=empresa, sucursal=sucursal,
            area=PerfilUsuario.Area.SECADO, rol=Rol.PRODUCCION,
        )
        proceso = Proceso.objects.create(codigo="concurrente", nombre="Concurrente")
        etapa = EtapaProceso.objects.create(
            proceso=proceso, codigo="secado-concurrente", nombre="Secado",
            tipo=EtapaProceso.Tipo.SECADO, orden=1,
        )
        equipo = Equipo.objects.create(
            sucursal=sucursal, codigo="TOR-CON", nombre="Torre concurrencia",
            tipo=Equipo.Tipo.TORRE,
        )
        self.ejecucion = EjecucionProceso.objects.create(
            sucursal=sucursal, codigo="EJ-CON-1", etapa=etapa, equipo=equipo,
            responsable=self.usuario,
        )

    def test_dos_sesiones_con_la_misma_version_no_se_pisan(self):
        barrera = Barrier(2)

        def editar(observacion):
            close_old_connections()
            cliente = APIClient()
            cliente.force_authenticate(self.usuario)
            barrera.wait(timeout=5)
            try:
                respuesta = cliente.patch(
                    f"/api/procesos/ejecuciones/{self.ejecucion.pk}/",
                    {"observaciones": observacion, "version": 1},
                    format="json",
                )
                return respuesta.status_code, respuesta.data
            finally:
                close_old_connections()

        with ThreadPoolExecutor(max_workers=2) as ejecutor:
            resultados = list(ejecutor.map(editar, ("Turno A", "Turno B")))

        self.ejecucion.refresh_from_db()
        self.assertEqual(sorted(estado for estado, _ in resultados), [200, 409])
        conflicto = next(datos for estado, datos in resultados if estado == 409)
        self.assertEqual(conflicto["code"], "version_conflict")
        self.assertEqual(conflicto["version_actual"], 2)
        self.assertEqual(self.ejecucion.version, 2)
        self.assertIn(self.ejecucion.observaciones, {"Turno A", "Turno B"})
