from datetime import timedelta
from types import SimpleNamespace

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from maestros.models import Equipo
from usuarios.models import PerfilUsuario
from .models import OrdenTrabajo, PlanPreventivo, RepuestoUtilizado
from .serializers import OrdenTrabajoSerializer
from .servicios import transicionar_orden
from .views import OrdenTrabajoViewSet


class MantenimientoTests(TestCase):
    def setUp(self):
        self.usuario = User.objects.create_user("mantenedor", password="x")
        PerfilUsuario.objects.create(
            usuario=self.usuario,
            area=PerfilUsuario.Area.MANTENIMIENTO,
            nivel=PerfilUsuario.Nivel.TRABAJADOR,
        )
        self.cliente = APIClient()
        self.cliente.force_authenticate(self.usuario)
        self.equipo = Equipo.objects.create(
            codigo="egron-1", nombre="Egron 1", tipo=Equipo.Tipo.LINEA
        )
        self.plan = PlanPreventivo.objects.create(
            equipo=self.equipo, nombre="Inspección mensual", frecuencia_dias=30,
            proxima_ejecucion=timezone.localdate(),
        )
        self.orden = OrdenTrabajo.objects.create(
            numero="OT-001", tipo=OrdenTrabajo.Tipo.PREVENTIVA,
            equipo=self.equipo, plan=self.plan, descripcion="Inspeccionar transmisión",
            responsable=self.usuario, creada_por=self.usuario,
        )

    def test_cierre_exige_prueba_conforme(self):
        for estado in [
            OrdenTrabajo.Estado.PROGRAMADA,
            OrdenTrabajo.Estado.ASIGNADA,
            OrdenTrabajo.Estado.EJECUCION,
            OrdenTrabajo.Estado.PRUEBA,
        ]:
            transicionar_orden(
                orden_id=self.orden.id, estado_nuevo=estado, usuario=self.usuario
            )
        with self.assertRaises(ValidationError):
            transicionar_orden(
                orden_id=self.orden.id,
                estado_nuevo=OrdenTrabajo.Estado.CERRADA,
                usuario=self.usuario,
            )

    def test_cierre_reprograma_plan_preventivo(self):
        for estado in [
            OrdenTrabajo.Estado.PROGRAMADA,
            OrdenTrabajo.Estado.ASIGNADA,
            OrdenTrabajo.Estado.EJECUCION,
            OrdenTrabajo.Estado.PRUEBA,
        ]:
            transicionar_orden(
                orden_id=self.orden.id, estado_nuevo=estado, usuario=self.usuario
            )
        self.orden.refresh_from_db()
        self.orden.prueba_conforme = True
        self.orden.motivo_cierre = "Equipo probado sin vibraciones anormales"
        self.orden.save()
        transicionar_orden(
            orden_id=self.orden.id,
            estado_nuevo=OrdenTrabajo.Estado.CERRADA,
            usuario=self.usuario,
        )
        self.plan.refresh_from_db()
        self.assertEqual(
            self.plan.proxima_ejecucion,
            timezone.localdate() + timedelta(days=30),
        )

    def test_resumen_operativo(self):
        respuesta = self.cliente.get("/api/mantenimiento/resumen/")
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta.json()["ordenes_abiertas"], 1)

    def test_ot_no_se_elimina_fisicamente_por_api(self):
        respuesta = self.cliente.delete(f"/api/mantenimiento/ordenes/{self.orden.id}/")
        self.assertEqual(respuesta.status_code, 405)


class RepuestoRespaldadoTests(TestCase):
    """
    El repuesto pasa por bodega, y este registro tiene que poder demostrarlo.

    No descuenta stock —lo descuenta la entrega de bodega, y hacerlo también
    aquí lo restaría dos veces— pero sin el enlace a esa entrega no había forma
    de distinguir un repuesto que salió por bodega de uno que alguien tomó del
    pañol. Las dos cosas se ven idénticas en la orden de trabajo, y en el
    segundo caso el saldo de bodega queda mintiendo.
    """

    def setUp(self):
        from inventario.models import (
            Bodega, DetalleEntregaProduccion, DetalleSolicitudMaterial,
            EntregaProduccion, Insumo, LoteInventario, SolicitudMaterial,
            Ubicacion,
        )

        self.usuario = User.objects.create_user("mantenedor-r", password="x")
        PerfilUsuario.objects.create(
            usuario=self.usuario,
            area=PerfilUsuario.Area.MANTENIMIENTO,
            nivel=PerfilUsuario.Nivel.ADMIN,
        )
        self.cliente = APIClient()
        self.cliente.force_authenticate(self.usuario)

        self.equipo = Equipo.objects.create(
            codigo="veb-r", nombre="VEB", tipo=Equipo.Tipo.EVAPORADOR
        )
        self.orden = OrdenTrabajo.objects.create(
            numero="OT-R-1", tipo=OrdenTrabajo.Tipo.CORRECTIVA,
            equipo=self.equipo, descripcion="Cambiar empaquetadura",
            responsable=self.usuario, creada_por=self.usuario,
        )

        self.empaquetadura = Insumo.objects.create(
            codigo="M-EMP", nombre="Empaquetadura 3 pulgadas",
            area=PerfilUsuario.Area.MANTENIMIENTO, unidad="un",
        )
        self.rodamiento = Insumo.objects.create(
            codigo="M-ROD", nombre="Rodamiento 6204",
            area=PerfilUsuario.Area.MANTENIMIENTO, unidad="un",
        )

        bodega = Bodega.objects.create(codigo="BM", nombre="Pañol")
        Ubicacion.objects.create(
            bodega=bodega, codigo="DISP", tipo=Ubicacion.Tipo.DISPONIBLE
        )
        lote = LoteInventario.objects.create(
            insumo=self.empaquetadura, codigo="PROV-EMP-1",
            estado_calidad=LoteInventario.EstadoCalidad.NO_REQUIERE,
        )

        solicitud = SolicitudMaterial.objects.create(
            numero="MRQ-R-1", area=PerfilUsuario.Area.MANTENIMIENTO,
            solicitante=self.usuario, fecha_requerida=timezone.localdate(),
        )
        detalle_solicitud = DetalleSolicitudMaterial.objects.create(
            solicitud=solicitud, insumo=self.empaquetadura, cantidad_solicitada=4
        )
        entrega = EntregaProduccion.objects.create(
            solicitud=solicitud, entregada_por=self.usuario,
            recibida_por=self.usuario,
        )
        self.entrega = DetalleEntregaProduccion.objects.create(
            entrega=entrega, detalle_solicitud=detalle_solicitud, lote=lote,
            cantidad=4,
        )

    def _crear(self, **extra):
        datos = {
            "orden": self.orden.id,
            "insumo": self.empaquetadura.id,
            "cantidad": "1",
        }
        datos.update(extra)

        return self.cliente.post(
            "/api/mantenimiento/repuestos/", datos, format="json"
        )

    def test_un_repuesto_con_su_entrega_queda_respaldado(self):
        respuesta = self._crear(entrega=self.entrega.id, cantidad="2")

        self.assertEqual(respuesta.status_code, 201, respuesta.data)
        self.assertTrue(respuesta.data["respaldado"])
        self.assertEqual(respuesta.data["lote_codigo"], "PROV-EMP-1")

    def test_uno_sin_entrega_se_admite_pero_queda_marcado(self):
        """
        Una urgencia de madrugada no se detiene porque bodega esté cerrada. Lo
        que no puede es confundirse con uno que sí salió por bodega.
        """
        respuesta = self._crear()

        self.assertEqual(respuesta.status_code, 201, respuesta.data)
        self.assertFalse(respuesta.data["respaldado"])
        self.assertIsNone(respuesta.data["lote_codigo"])

    def test_listar_repuestos_respaldados_no_consulta_por_repuesto(self):
        RepuestoUtilizado.objects.bulk_create([
            RepuestoUtilizado(
                orden=self.orden,
                insumo=self.empaquetadura,
                entrega=self.entrega,
                cantidad=1,
            )
            for _ in range(4)
        ])
        # Deja el scope en la caché de la instancia antes de medir solo el
        # queryset y su serialización.
        _ = self.usuario.perfil
        vista = OrdenTrabajoViewSet()
        vista.request = SimpleNamespace(user=self.usuario, query_params={})
        consulta = vista.get_queryset().filter(pk=self.orden.pk)

        # Orden, fallas y repuestos (estos últimos ya unidos a entrega+lote).
        with self.assertNumQueries(3):
            datos = OrdenTrabajoSerializer(consulta, many=True).data

        self.assertEqual(len(datos[0]["repuestos"]), 4)
        self.assertTrue(all(
            repuesto["lote_codigo"] == "PROV-EMP-1"
            for repuesto in datos[0]["repuestos"]
        ))

    def test_no_se_imputa_mas_de_lo_que_bodega_entrego(self):
        self._crear(entrega=self.entrega.id, cantidad="3")

        respuesta = self._crear(entrega=self.entrega.id, cantidad="2")

        self.assertEqual(respuesta.status_code, 400)
        self.assertIn("quedan", str(respuesta.data))

    def test_una_entrega_puede_cubrir_dos_ordenes(self):
        """Bodega despacha cuatro y se usan de a dos en trabajos distintos."""
        otra = OrdenTrabajo.objects.create(
            numero="OT-R-2", tipo=OrdenTrabajo.Tipo.CORRECTIVA,
            equipo=self.equipo, descripcion="Otra máquina",
            responsable=self.usuario, creada_por=self.usuario,
        )

        primera = self._crear(entrega=self.entrega.id, cantidad="2")
        segunda = self._crear(
            entrega=self.entrega.id, cantidad="2", orden=otra.id
        )

        self.assertEqual(primera.status_code, 201, primera.data)
        self.assertEqual(segunda.status_code, 201, segunda.data)

    def test_la_entrega_tiene_que_ser_del_mismo_repuesto(self):
        """
        Si el insumo del registro y el de la entrega no coinciden, uno de los
        dos está mal y no se sabe cuál — así que ninguno respalda al otro.
        """
        respuesta = self._crear(
            entrega=self.entrega.id, insumo=self.rodamiento.id
        )

        self.assertEqual(respuesta.status_code, 400)
        self.assertIn("Empaquetadura", str(respuesta.data))

    def test_no_se_agregan_repuestos_a_una_orden_cerrada(self):
        """La regla ya estaba en el modelo; sin que el serializer llamara a
        `clean()` no se aplicaba nunca."""
        self.orden.estado = OrdenTrabajo.Estado.CERRADA
        self.orden.save(update_fields=["estado"])

        respuesta = self._crear(entrega=self.entrega.id)

        self.assertEqual(respuesta.status_code, 400)
        self.assertIn("finalizada", str(respuesta.data))
