from datetime import date

from django.contrib.auth.models import User
from django.test import TestCase
from rest_framework.test import APIClient

from maestros.models import Equipo
from usuarios.models import Empresa, PerfilUsuario, Sucursal

from .models import BalanceDia, BloquePlan, SemanaPlan


class CicloSemanaTests(TestCase):
    def setUp(self):
        self.empresa = Empresa.objects.create(rut="PLAN", nombre="Planificación")
        self.sucursal = Sucursal.objects.create(
            empresa=self.empresa, codigo="P1", nombre="Planta 1"
        )
        usuario = User.objects.create_user("planificador", password="x")
        PerfilUsuario.objects.create(
            usuario=usuario,
            area=PerfilUsuario.Area.SECADO,
            empresa=self.empresa,
            sucursal=self.sucursal,
            alcance=PerfilUsuario.Alcance.SUCURSAL,
        )
        self.cliente = APIClient()
        self.cliente.force_authenticate(usuario)
        self.semana = SemanaPlan.objects.create(
            sucursal=self.sucursal, codigo="W35", anio=2026,
            fecha_inicio=date(2026, 8, 24),
        )

    def test_semana_vacia_en_borrador_se_puede_eliminar(self):
        respuesta = self.cliente.delete(
            f"/api/planificacion/semanas/{self.semana.id}/"
        )
        self.assertEqual(respuesta.status_code, 204)

    def test_semana_con_plan_no_se_elimina_y_se_cancela_con_motivo(self):
        BalanceDia.objects.create(semana=self.semana, dia=0)

        borrado = self.cliente.delete(
            f"/api/planificacion/semanas/{self.semana.id}/"
        )
        sin_motivo = self.cliente.post(
            f"/api/planificacion/semanas/{self.semana.id}/cancelar/", {}, format="json"
        )
        cancelada = self.cliente.post(
            f"/api/planificacion/semanas/{self.semana.id}/cancelar/",
            {"motivo": "Cambio del programa comercial."}, format="json",
        )
        self.semana.refresh_from_db()

        self.assertEqual(borrado.status_code, 409)
        self.assertEqual(sin_motivo.status_code, 400)
        self.assertEqual(cancelada.status_code, 200)
        self.assertEqual(self.semana.estado, SemanaPlan.Estado.CANCELADA)
        self.assertEqual(self.semana.cancelada_por.username, "planificador")

    def test_duplicar_copia_balance_y_bloques_como_borrador(self):
        equipo = Equipo.objects.create(
            sucursal=self.sucursal, codigo="EQ-PLAN", nombre="Equipo",
            tipo=Equipo.Tipo.OTRO,
        )
        BalanceDia.objects.create(semana=self.semana, dia=0, recepcion_ccaa=1000)
        BloquePlan.objects.create(
            semana=self.semana, equipo=equipo, dia=0, hora_inicio=8,
            hora_fin=10, tipo=BloquePlan.Tipo.ESTADO, estado_equipo="A",
        )

        respuesta = self.cliente.post(
            f"/api/planificacion/semanas/{self.semana.id}/duplicar/",
            {"codigo": "W36", "anio": 2026, "fecha_inicio": "2026-08-31"},
            format="json",
        )
        copia = SemanaPlan.objects.get(codigo="W36")

        self.assertEqual(respuesta.status_code, 201)
        self.assertEqual(copia.estado, SemanaPlan.Estado.BORRADOR)
        self.assertEqual(copia.balances.count(), 1)
        self.assertEqual(copia.bloques.count(), 1)
