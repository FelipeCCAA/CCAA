from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

from django.contrib.auth.models import User
from django.db import close_old_connections, connection
from django.test import TransactionTestCase
from rest_framework.test import APIClient

from maestros.models import Equipo
from usuarios.models import PerfilUsuario, Rol

from .models import EjecucionProceso, EtapaProceso, Proceso


class ConcurrenciaEquipoTests(TransactionTestCase):
    """Dos puestos no pueden reservar simultáneamente la misma máquina."""

    def setUp(self):
        self.usuarios = []
        for indice in (1, 2):
            usuario = User.objects.create_user(f"operador-equipo-{indice}")
            PerfilUsuario.objects.create(
                usuario=usuario,
                area=PerfilUsuario.Area.SECADO,
                rol=Rol.PRODUCCION,
            )
            self.usuarios.append(usuario)

        proceso = Proceso.objects.create(
            codigo="concurrencia-equipo", nombre="Concurrencia de Secado"
        )
        etapa = EtapaProceso.objects.create(
            proceso=proceso,
            codigo="reservar-torre",
            nombre="Reservar torre",
            tipo=EtapaProceso.Tipo.SECADO,
            orden=1,
        )
        equipo = Equipo.objects.create(
            codigo="TOR-RACE",
            nombre="Torre de secado concurrente",
            tipo=Equipo.Tipo.TORRE,
        )
        self.ejecuciones = [
            EjecucionProceso.objects.create(
                codigo=f"EJ-TOR-RACE-{indice}",
                etapa=etapa,
                equipo=equipo,
                responsable=usuario,
            )
            for indice, usuario in enumerate(self.usuarios, 1)
        ]

    def test_dos_usuarios_no_reservan_la_misma_torre(self):
        if not connection.features.has_select_for_update:
            self.skipTest("El motor no soporta bloqueos de fila")

        barrera = Barrier(2)

        def reservar(datos):
            usuario, ejecucion = datos
            close_old_connections()
            cliente = APIClient()
            cliente.force_authenticate(usuario)
            barrera.wait(timeout=10)
            try:
                respuesta = cliente.post(
                    f"/api/procesos/ejecuciones/{ejecucion.pk}/transicionar/",
                    {
                        "estado": EjecucionProceso.Estado.PREPARACION,
                        "version": ejecucion.version,
                    },
                    format="json",
                )
                return respuesta.status_code, respuesta.data
            finally:
                connection.close()

        with ThreadPoolExecutor(max_workers=2) as ejecutor:
            resultados = list(
                ejecutor.map(reservar, zip(self.usuarios, self.ejecuciones))
            )

        estados = sorted(estado for estado, _ in resultados)
        self.assertEqual(estados, [200, 409], resultados)
        ocupada = EjecucionProceso.objects.get(
            estado=EjecucionProceso.Estado.PREPARACION
        )
        rechazada = next(datos for estado, datos in resultados if estado == 409)
        self.assertEqual(rechazada["code"], "EQUIPO_OCUPADO")
        self.assertIn("Torre de secado concurrente", rechazada["message"])
        self.assertIn(f"ocupado por {ocupada.codigo}", rechazada["message"])
        self.assertIn("equipo", rechazada["details"])
        self.assertEqual(
            EjecucionProceso.objects.filter(
                equipo=ocupada.equipo,
                estado__in=[
                    EjecucionProceso.Estado.PREPARACION,
                    EjecucionProceso.Estado.EJECUCION,
                    EjecucionProceso.Estado.PAUSADA,
                    EjecucionProceso.Estado.BLOQUEADA,
                ],
            ).count(),
            1,
        )
