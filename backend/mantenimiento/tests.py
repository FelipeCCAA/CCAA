from datetime import timedelta

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from maestros.models import Equipo
from usuarios.models import PerfilUsuario
from .models import OrdenTrabajo, PlanPreventivo
from .servicios import transicionar_orden


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
