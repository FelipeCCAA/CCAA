from datetime import timedelta
from decimal import Decimal

from django.utils import timezone
from rest_framework.test import APIClient

from maestros.models import Equipo, Silo
from procesos.models import CorridaCondensacion, EjecucionProceso, ReservaSiloProceso
from recepcion.models import AnalisisSilo, MovimientoSilo
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
        self.assertIsNone(fila["bloqueo_silo_origen"])

    def test_sin_analisis_del_origen_la_preparada_dice_por_que(self):
        AnalisisSilo.objects.filter(silo=self.origen).delete()
        fila = self.fila(self.puesto(), self.equipo)
        self.assertEqual(fila["estado"], "preparada")
        self.assertIn(self.origen.codigo, fila["motivos_para_iniciar"][0])
        self.assertEqual(fila["bloqueo_silo_origen"], self.origen.codigo)

    def test_un_motivo_que_no_es_del_origen_no_marca_bloqueo_silo_origen(self):
        """Un destino sin capacidad no es un problema del silo de origen: la
        pantalla no debe ofrecer «Analizar silo» para algo que un análisis no
        resuelve."""
        self.destino.estado = Silo.Estado.EN_CIP
        self.destino.save(update_fields=["estado"])
        fila = self.fila(self.puesto(), self.equipo)
        self.assertEqual(fila["estado"], "preparada")
        self.assertTrue(fila["motivos_para_iniciar"])
        self.assertIsNone(fila["bloqueo_silo_origen"])

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
        self.assertEqual(fila["en_calidad"]["codigo"], self.ejecucion.codigo)

    def test_los_destinos_ofrecidos_son_solo_disponibles(self):
        bloqueado = Silo.objects.create(
            sucursal=self.planta, codigo="PC-BLOQ", tipo=Silo.Tipo.SILO,
            capacidad_l=1000, estado=Silo.Estado.BLOQUEADO_CALIDAD,
        )
        codigos = [item["codigo"] for item in self.puesto()["destinos"]]
        self.assertIn(self.destino.codigo, codigos)
        self.assertNotIn(bloqueado.codigo, codigos)

    def test_libre_l_del_destino_resta_salidas_y_suma_ingresos(self):
        """El `libre_l` de un destino usa la misma regla que `saldo_silo`."""
        MovimientoSilo.objects.create(
            silo=self.destino, tipo=MovimientoSilo.Tipo.INGRESO,
            litros=400, fecha_hora=timezone.now(),
        )
        MovimientoSilo.objects.create(
            silo=self.destino, tipo=MovimientoSilo.Tipo.SALIDA,
            litros=150, fecha_hora=timezone.now(),
        )
        destino = next(
            item for item in self.puesto()["destinos"] if item["codigo"] == self.destino.codigo
        )
        # capacidad 1000, saldo 400 - 150 = 250 -> libre 750. Como texto,
        # igual que los serializers: el tipo del frontend dice `string`.
        self.assertEqual(destino["libre_l"], "750.00")

    def test_litros_entrada_de_la_corrida_viajan_como_texto(self):
        fila = self.fila(self.puesto(), self.equipo)
        self.assertEqual(fila["corrida"]["litros_entrada"], "600.00")

    def test_un_destino_reservado_por_otra_ejecucion_no_se_ofrece(self):
        """`crear_condensacion_guiada` lo rechazaría (`exigir_destino_sin_reserva`):
        ofrecerlo es la pantalla prometiendo lo que el backend no acepta."""
        otra = EjecucionProceso.objects.create(
            codigo="EJ-RESERVA-PUESTO", etapa=self.ejecucion.etapa,
            sucursal=self.planta, responsable=self.usuario,
        )
        ReservaSiloProceso.objects.create(
            ejecucion=otra, silo=self.destino,
            tipo=ReservaSiloProceso.Tipo.DESTINO, cantidad_planificada=Decimal("100"),
        )
        codigos = [item["codigo"] for item in self.puesto()["destinos"]]
        self.assertNotIn(self.destino.codigo, codigos)

    def test_corridas_de_hoy_no_incluye_un_huerfano_iniciado_hoy(self):
        """Mismo criterio que la ocupación: una corrida en proceso cuya
        ejecución ya terminó no es «En proceso» hoy."""
        self.corrida.estado = CorridaCondensacion.Estado.EN_PROCESO
        self.corrida.iniciada_en = timezone.now()
        self.corrida.save(update_fields=["estado", "iniciada_en"])
        self.ejecucion.estado = EjecucionProceso.Estado.CANCELADA
        self.ejecucion.save(update_fields=["estado"])
        codigos = [item["codigo"] for item in self.puesto()["corridas_de_hoy"]]
        self.assertNotIn(self.ejecucion.codigo, codigos)

    def test_corridas_de_hoy_conserva_una_cerrada_hoy(self):
        """Una corrida terminada de verdad (ejecución cerrada tras Calidad)
        sigue siendo parte del día: lo que se excluye son los huérfanos."""
        self.corrida.estado = CorridaCondensacion.Estado.CERRADA
        self.corrida.iniciada_en = timezone.now()
        self.corrida.finalizada_en = timezone.now()
        self.corrida.save(update_fields=["estado", "iniciada_en", "finalizada_en"])
        self.ejecucion.estado = EjecucionProceso.Estado.CERRADA
        self.ejecucion.save(update_fields=["estado"])
        codigos = [item["codigo"] for item in self.puesto()["corridas_de_hoy"]]
        self.assertIn(self.ejecucion.codigo, codigos)

    def test_una_preparada_nueva_no_oculta_la_corrida_que_espera_calidad(self):
        """Una corrida preparada no borra que la anterior sigue en Calidad."""
        ejecucion_anterior = EjecucionProceso.objects.create(
            codigo="EJ-COND-ESPERA",
            etapa=self.ejecucion.etapa,
            sucursal=self.planta,
            equipo=self.equipo,
            responsable=self.usuario,
            estado=EjecucionProceso.Estado.PENDIENTE_CONTROL,
        )
        CorridaCondensacion.objects.create(
            ejecucion=ejecucion_anterior,
            orden=self.orden,
            lote=self.lote,
            silo_origen=self.origen,
            silo_destino=self.destino,
            litros_entrada=600,
            estado=CorridaCondensacion.Estado.CERRADA,
        )

        fila = self.fila(self.puesto(), self.equipo)

        self.assertEqual(fila["estado"], "preparada")
        self.assertEqual(fila["corrida"]["id"], self.corrida.pk)
        self.assertEqual(fila["en_calidad"]["codigo"], ejecucion_anterior.codigo)

    def test_corridas_de_hoy_no_incluye_un_borrador_de_otro_dia(self):
        EjecucionProceso.objects.filter(pk=self.ejecucion.pk).update(
            creada_en=timezone.now() - timedelta(days=2)
        )
        codigos = [item["codigo"] for item in self.puesto()["corridas_de_hoy"]]
        self.assertNotIn(self.ejecucion.codigo, codigos)

    def test_un_borrador_con_ejecucion_cerrada_es_huerfano_y_la_maquina_queda_disponible(self):
        """Un E2E abortado o un dato viejo no debe mostrar la máquina ocupada."""
        self.ejecucion.estado = EjecucionProceso.Estado.CERRADA
        self.ejecucion.save(update_fields=["estado"])
        fila = self.fila(self.puesto(), self.equipo)
        self.assertEqual(fila["estado"], "disponible")
        self.assertIsNone(fila["corrida"])

    def test_un_borrador_con_ejecucion_cancelada_es_huerfano_y_la_maquina_queda_disponible(self):
        self.ejecucion.estado = EjecucionProceso.Estado.CANCELADA
        self.ejecucion.save(update_fields=["estado"])
        fila = self.fila(self.puesto(), self.equipo)
        self.assertEqual(fila["estado"], "disponible")
        self.assertIsNone(fila["corrida"])

    def test_un_en_proceso_con_ejecucion_cerrada_es_huerfano_y_la_maquina_queda_disponible(self):
        self.corrida.estado = CorridaCondensacion.Estado.EN_PROCESO
        self.corrida.iniciada_en = timezone.now()
        self.corrida.save(update_fields=["estado", "iniciada_en"])
        self.ejecucion.estado = EjecucionProceso.Estado.CERRADA
        self.ejecucion.save(update_fields=["estado"])
        fila = self.fila(self.puesto(), self.equipo)
        self.assertEqual(fila["estado"], "disponible")
        self.assertIsNone(fila["corrida"])

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
