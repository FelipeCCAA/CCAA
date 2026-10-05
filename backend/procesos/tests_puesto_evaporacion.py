from decimal import Decimal

from django.utils import timezone
from rest_framework.test import APIClient

from maestros.models import Equipo, Silo
from procesos.models import CorridaCondensacion, EjecucionProceso
from recepcion.models import AnalisisSilo
from usuarios.models import PerfilUsuario, Rol

from .tests_condensacion import FlujoCondensacionTests


class PuestoEvaporacionTests(FlujoCondensacionTests):
    def puesto(self, usuario=None):
        cliente = APIClient()
        cliente.force_authenticate(usuario or self.usuario)
        respuesta = cliente.get("/api/procesos/condensaciones/puesto/")
        self.assertEqual(respuesta.status_code, 200, respuesta.data)
        return respuesta.data

    def fila(self, datos, equipo):
        return next(item for item in datos["evaporadores"] if item["equipo_id"] == equipo.pk)

    def test_corrida_en_borrador_es_preparada_y_lista_para_iniciar(self):
        fila = self.fila(self.puesto(), self.equipo)
        self.assertEqual(fila["estado"], "preparada")
        self.assertEqual(fila["corrida"]["id"], self.corrida.pk)
        self.assertEqual(fila["motivos_para_iniciar"], [])

    def test_sin_analisis_del_origen_la_preparada_dice_por_que(self):
        AnalisisSilo.objects.filter(silo=self.origen).delete()
        fila = self.fila(self.puesto(), self.equipo)
        self.assertEqual(fila["estado"], "preparada")
        self.assertIn(self.origen.codigo, fila["motivos_para_iniciar"][0])

    def test_en_proceso_manda_sobre_una_preparada_del_mismo_equipo(self):
        self.corrida.estado = CorridaCondensacion.Estado.EN_PROCESO
        self.corrida.iniciada_en = timezone.now()
        self.corrida.save(update_fields=["estado", "iniciada_en"])
        fila = self.fila(self.puesto(), self.equipo)
        self.assertEqual(fila["estado"], "en_curso")
        self.assertEqual(fila["corrida"]["id"], self.corrida.pk)

    def test_un_evaporador_sin_corrida_activa_esta_disponible(self):
        libre = Equipo.objects.create(
            sucursal=self.planta, codigo="ev-2", nombre="Evaporador 2",
            tipo=Equipo.Tipo.EVAPORADOR,
        )
        fila = self.fila(self.puesto(), libre)
        self.assertEqual(fila["estado"], "disponible")
        self.assertIsNone(fila["corrida"])

    def test_ejecucion_en_control_de_calidad_espera_calidad(self):
        self.corrida.estado = CorridaCondensacion.Estado.CERRADA
        self.corrida.save(update_fields=["estado"])
        self.ejecucion.estado = EjecucionProceso.Estado.PENDIENTE_CONTROL
        self.ejecucion.save(update_fields=["estado"])
        fila = self.fila(self.puesto(), self.equipo)
        self.assertEqual(fila["estado"], "esperando_calidad")

    def test_los_destinos_ofrecidos_son_solo_disponibles(self):
        bloqueado = Silo.objects.create(
            sucursal=self.planta, codigo="PC-BLOQ", tipo=Silo.Tipo.SILO,
            capacidad_l=1000, estado=Silo.Estado.BLOQUEADO_CALIDAD,
        )
        codigos = [item["codigo"] for item in self.puesto()["destinos"]]
        self.assertIn(self.destino.codigo, codigos)
        self.assertNotIn(bloqueado.codigo, codigos)

    def test_un_usuario_de_calidad_puede_leer_el_puesto(self):
        calidad = self._crear_usuario_calidad()
        fila = self.fila(self.puesto(calidad), self.equipo)
        self.assertEqual(fila["estado"], "preparada")

    def _crear_usuario_calidad(self):
        from django.contrib.auth.models import User

        usuario = User.objects.create_user("calidad-puesto-evaporacion")
        PerfilUsuario.objects.create(
            usuario=usuario,
            empresa=self.planta.empresa,
            sucursal=self.planta,
            rol=Rol.CALIDAD,
            area=PerfilUsuario.Area.CALIDAD,
        )
        return usuario
