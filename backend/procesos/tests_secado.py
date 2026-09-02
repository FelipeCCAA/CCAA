from datetime import date
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase
from rest_framework.test import APIClient

from maestros.models import Equipo, Mandante, Producto
from produccion.models import Lote, OrdenProduccion
from usuarios.models import Empresa, PerfilUsuario, Rol, Sucursal

from .models import (
    CorridaSecado, EjecucionProceso, EtapaProceso, Proceso, SalidaProceso,
)


class CierreSecadoTests(TestCase):
    def setUp(self):
        empresa = Empresa.objects.create(rut="SEC-1", nombre="Empresa secado")
        planta = Sucursal.objects.create(empresa=empresa, codigo="SEC", nombre="Planta")
        self.usuario = User.objects.create_user("operador-secador")
        PerfilUsuario.objects.create(
            usuario=self.usuario, empresa=empresa, sucursal=planta,
            alcance=PerfilUsuario.Alcance.SUCURSAL,
            rol=Rol.PRODUCCION, area=PerfilUsuario.Area.SECADO,
        )
        mandante = Mandante.objects.create(
            empresa=empresa, nombre="Mandante secado", codigo_cliente="sec"
        )
        producto = Producto.objects.create(
            mandante=mandante, nombre="Leche en polvo",
            familia=Producto.Familia.POLVO,
        )
        torre = Equipo.objects.create(
            sucursal=planta, codigo="TORRE-S", nombre="Torre Secado",
            tipo=Equipo.Tipo.TORRE,
        )
        proceso = Proceso.objects.create(codigo="secado-api", nombre="Secado")
        etapa = EtapaProceso.objects.create(
            proceso=proceso, codigo="secar", nombre="Secar",
            tipo=EtapaProceso.Tipo.SECADO, orden=1,
        )
        orden = OrdenProduccion.objects.create(
            sucursal=planta, codigo="OP-SEC-1", producto=producto,
            cantidad_planificada=Decimal("500"), unidad="kg", equipo=torre,
            estado=OrdenProduccion.Estado.EN_PROCESO,
        )
        ejecucion = EjecucionProceso.objects.create(
            codigo="EJ-SEC-1", etapa=etapa, sucursal=planta, equipo=torre,
            responsable=self.usuario, estado=EjecucionProceso.Estado.EJECUCION,
        )
        lote = Lote.objects.create(
            sucursal=planta, codigo_lote="LOTE-SEC-1", producto=producto,
            orden=orden, equipo=torre, ejecucion=ejecucion,
            fecha=date(2026, 9, 2), estado=Lote.Estado.EN_PROCESO,
        )
        self.corrida = CorridaSecado.objects.create(
            ejecucion=ejecucion, orden=orden, lote=lote,
        )
        self.cliente = APIClient()
        self.cliente.force_authenticate(self.usuario)

    def test_cierre_registra_balance_salida_y_rendimiento(self):
        respuesta = self.cliente.post(
            f"/api/procesos/secados/{self.corrida.pk}/cerrar/",
            {
                "kg_alimentacion": "600.000",
                "solidos_entrada_pct": "48.00",
                "kg_polvo": "280.000",
                "kg_finos": "5.000",
                "kg_merma": "3.000",
                "controles": {"temperatura_salida": 82},
            },
            format="json",
        )

        self.assertEqual(respuesta.status_code, 200, respuesta.data)
        self.corrida.refresh_from_db()
        self.corrida.lote.refresh_from_db()
        self.corrida.ejecucion.refresh_from_db()
        self.assertEqual(self.corrida.lote.kg_producidos, Decimal("280.00"))
        self.assertEqual(self.corrida.ejecucion.estado, EjecucionProceso.Estado.CERRADA)
        self.assertEqual(self.corrida.rendimiento_recuperacion_pct, Decimal("47.50"))
        salida = SalidaProceso.objects.get(
            ejecucion=self.corrida.ejecucion,
            naturaleza=SalidaProceso.Naturaleza.PRINCIPAL,
        )
        self.assertEqual(salida.cantidad, Decimal("280.000"))

    def test_balance_imposible_no_cierra_el_lote(self):
        respuesta = self.cliente.post(
            f"/api/procesos/secados/{self.corrida.pk}/cerrar/",
            {
                "kg_alimentacion": "100.000",
                "solidos_entrada_pct": "48.00",
                "kg_polvo": "100.000",
                "kg_finos": "5.000",
                "kg_merma": "1.000",
            },
            format="json",
        )

        self.assertEqual(respuesta.status_code, 400, respuesta.data)
        self.corrida.lote.refresh_from_db()
        self.corrida.ejecucion.refresh_from_db()
        self.assertEqual(self.corrida.lote.estado, Lote.Estado.EN_PROCESO)
        self.assertEqual(self.corrida.ejecucion.estado, EjecucionProceso.Estado.EJECUCION)
        self.assertFalse(SalidaProceso.objects.filter(ejecucion=self.corrida.ejecucion).exists())
