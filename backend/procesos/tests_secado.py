from datetime import date
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from calidad.models import LiberacionProceso
from maestros.models import Equipo, Especificacion, Mandante, Producto
from produccion.models import Analisis, Lote, OrdenProduccion
from usuarios.models import Empresa, PerfilUsuario, Rol, Sucursal

from .models import (
    CorridaSecado, EjecucionProceso, EtapaProceso, Proceso, RutaProducto,
    SalidaProceso,
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
        self.producto = Producto.objects.create(
            mandante=mandante, nombre="Leche en polvo",
            familia=Producto.Familia.POLVO,
        )
        torre = Equipo.objects.create(
            sucursal=planta, codigo="TORRE-S", nombre="Torre Secado",
            tipo=Equipo.Tipo.TORRE,
        )
        proceso = Proceso.objects.create(codigo="secado-api", nombre="Secado")
        self.etapa = EtapaProceso.objects.create(
            proceso=proceso, codigo="secar", nombre="Secar",
            tipo=EtapaProceso.Tipo.SECADO, orden=1,
        )
        orden = OrdenProduccion.objects.create(
            sucursal=planta, codigo="OP-SEC-1", producto=self.producto,
            cantidad_planificada=Decimal("500"), unidad="kg", equipo=torre,
            estado=OrdenProduccion.Estado.EN_PROCESO,
        )
        ejecucion = EjecucionProceso.objects.create(
            codigo="EJ-SEC-1", etapa=self.etapa, sucursal=planta, equipo=torre,
            responsable=self.usuario, estado=EjecucionProceso.Estado.EJECUCION,
            inicio=timezone.now(),
        )
        lote = Lote.objects.create(
            sucursal=planta, codigo_lote="LOTE-SEC-1", producto=self.producto,
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
        self.assertFalse(LiberacionProceso.objects.filter(salida=salida).exists())
        self.assertEqual(respuesta.data["equipo_id"], self.corrida.ejecucion.equipo_id)
        self.assertEqual(respuesta.data["equipo_nombre"], "Torre Secado")
        self.assertIsNotNone(respuesta.data["iniciada_en"])
        self.assertFalse(respuesta.data["requiere_calidad"])
        self.assertEqual(respuesta.data["estado_calidad"], "no_requerida")

    def test_cierre_con_calidad_deja_material_pendiente_y_torre_disponible(self):
        self.etapa.requiere_calidad = True
        self.etapa.save(update_fields=["requiere_calidad"])

        respuesta = self.cliente.post(
            f"/api/procesos/secados/{self.corrida.pk}/cerrar/",
            {
                "kg_alimentacion": "600.000",
                "solidos_entrada_pct": "48.00",
                "kg_polvo": "280.000",
                "kg_finos": "5.000",
                "kg_merma": "3.000",
            },
            format="json",
        )

        self.assertEqual(respuesta.status_code, 200, respuesta.data)
        self.corrida.ejecucion.refresh_from_db()
        salida = SalidaProceso.objects.get(ejecucion=self.corrida.ejecucion)
        self.assertEqual(self.corrida.ejecucion.estado, EjecucionProceso.Estado.CERRADA)
        self.assertEqual(salida.destino, SalidaProceso.Destino.PENDIENTE)
        self.assertEqual(
            salida.liberacion_calidad.estado,
            LiberacionProceso.Estado.PENDIENTE,
        )
        self.assertTrue(respuesta.data["requiere_calidad"])
        self.assertEqual(respuesta.data["estado_calidad"], "pendiente")

        otra = EjecucionProceso.objects.create(
            codigo="EJ-SEC-LIBRE",
            etapa=self.etapa,
            sucursal=self.corrida.ejecucion.sucursal,
            equipo=self.corrida.ejecucion.equipo,
            estado=EjecucionProceso.Estado.PREPARACION,
        )
        self.assertEqual(otra.estado, EjecucionProceso.Estado.PREPARACION)

    def test_calidad_libera_salida_de_secado_hacia_la_siguiente_etapa(self):
        self.etapa.requiere_calidad = True
        self.etapa.save(update_fields=["requiere_calidad"])
        EtapaProceso.objects.create(
            proceso=self.etapa.proceso,
            codigo="envasar",
            nombre="Envasado",
            tipo=EtapaProceso.Tipo.ENVASADO,
            orden=2,
        )
        RutaProducto.objects.create(
            sucursal=self.corrida.ejecucion.sucursal,
            producto=self.producto,
            proceso=self.etapa.proceso,
        )
        cierre = self.cliente.post(
            f"/api/procesos/secados/{self.corrida.pk}/cerrar/",
            {
                "kg_alimentacion": "600.000",
                "solidos_entrada_pct": "48.00",
                "kg_polvo": "280.000",
                "kg_finos": "5.000",
                "kg_merma": "3.000",
            },
            format="json",
        )
        self.assertEqual(cierre.status_code, 200, cierre.data)
        especificacion = Especificacion.objects.create(
            producto=self.producto,
            version=1,
            vigente_desde=timezone.localdate(),
            rangos={"humedad": {"min": 0, "max": 5, "obligatorio": True}},
        )
        analisis = Analisis.objects.create(
            lote=self.corrida.lote,
            fecha=timezone.localdate(),
            valores={"humedad": 3},
            especificacion=especificacion,
        )
        calidad = User.objects.create_user("calidad-secado")
        PerfilUsuario.objects.create(
            usuario=calidad,
            empresa=self.corrida.ejecucion.sucursal.empresa,
            sucursal=self.corrida.ejecucion.sucursal,
            alcance=PerfilUsuario.Alcance.SUCURSAL,
            rol=Rol.CALIDAD,
            area=PerfilUsuario.Area.CALIDAD,
        )
        cliente_calidad = APIClient()
        cliente_calidad.force_authenticate(calidad)
        salida = SalidaProceso.objects.get(ejecucion=self.corrida.ejecucion)

        respuesta = cliente_calidad.post(
            f"/api/calidad/resultados-proceso/{salida.pk}/liberar/",
            {"analisis_lote_id": analisis.pk},
            format="json",
        )

        self.assertEqual(respuesta.status_code, 200, respuesta.data)
        salida.refresh_from_db()
        salida.liberacion_calidad.refresh_from_db()
        self.assertEqual(salida.destino, SalidaProceso.Destino.ENVASADO)
        self.assertEqual(
            salida.liberacion_calidad.estado,
            LiberacionProceso.Estado.LIBERADO,
        )

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
