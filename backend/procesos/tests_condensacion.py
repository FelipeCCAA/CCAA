from datetime import date
from decimal import Decimal

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from maestros.models import Equipo, Especificacion, Mandante, Producto, Silo
from produccion.models import Lote, OrdenProduccion
from recepcion.models import AnalisisSilo, MovimientoSilo
from usuarios.models import Empresa, PerfilUsuario, Rol, Sucursal

from .models import (
    CorridaCondensacion, EjecucionProceso, EntradaProceso, EtapaProceso, Proceso,
    RutaProducto, SalidaProceso,
)
from .servicios import cerrar_condensacion, crear_condensacion_guiada, iniciar_condensacion


class FlujoCondensacionTests(TestCase):
    def setUp(self):
        empresa = Empresa.objects.create(rut="COND-1", nombre="Empresa condensación")
        self.planta = Sucursal.objects.create(
            empresa=empresa, codigo="COND", nombre="Planta condensación"
        )
        self.usuario = User.objects.create_user("operador-condensacion")
        PerfilUsuario.objects.create(
            usuario=self.usuario, empresa=empresa, sucursal=self.planta,
            rol=Rol.PRODUCCION, area=PerfilUsuario.Area.CONDENSACION,
        )
        mandante = Mandante.objects.create(
            empresa=empresa, nombre="Mandante condensación", codigo_cliente="cond"
        )
        producto = Producto.objects.create(
            mandante=mandante, nombre="Precondensado", unidad_base="l"
        )
        self.equipo = Equipo.objects.create(
            sucursal=self.planta, codigo="ev-1", nombre="Evaporador 1",
            tipo=Equipo.Tipo.EVAPORADOR, consume_leche=True,
        )
        self.origen = Silo.objects.create(
            sucursal=self.planta, codigo="EST-1", tipo=Silo.Tipo.SILO,
            capacidad_l=2000,
        )
        self.destino = Silo.objects.create(
            sucursal=self.planta, codigo="PC-1", tipo=Silo.Tipo.SILO,
            capacidad_l=1000,
        )
        MovimientoSilo.objects.create(
            silo=self.origen, tipo=MovimientoSilo.Tipo.INGRESO,
            litros=Decimal("1500"), fecha_hora=timezone.now(),
        )
        proceso = Proceso.objects.create(codigo="cond", nombre="Condensación")
        etapa = EtapaProceso.objects.create(
            proceso=proceso, codigo="evaporar", nombre="Evaporar",
            tipo=EtapaProceso.Tipo.CONDENSACION, orden=1,
        )
        self.ejecucion = EjecucionProceso.objects.create(
            codigo="EJ-COND-1", etapa=etapa, sucursal=self.planta,
            equipo=self.equipo, responsable=self.usuario,
        )
        self.orden = OrdenProduccion.objects.create(
            sucursal=self.planta, codigo="OP-COND-1", producto=producto,
            cantidad_planificada=1000, unidad="l", equipo=self.equipo,
            estado=OrdenProduccion.Estado.PROGRAMADA,
        )
        self.lote = Lote.objects.create(
            sucursal=self.planta, codigo_lote="L-COND-1", orden=self.orden,
            op=self.orden.codigo, producto=producto, fecha=date(2026, 8, 17),
        )
        self.corrida = CorridaCondensacion.objects.create(
            ejecucion=self.ejecucion, orden=self.orden, lote=self.lote,
            silo_origen=self.origen, silo_destino=self.destino,
            litros_entrada=Decimal("600"),
        )

    def _crear_especificacion_precondensado(self, rangos=None):
        return Especificacion.objects.create(
            producto=self.lote.producto,
            version=1,
            vigente_desde=date(2026, 1, 1),
            rangos=rangos or {
                "mg": {"min": 6.5, "max": 7.5, "obligatorio": True},
                "st": {"min": 48.0, "max": 50.0, "obligatorio": True},
            },
            fuente="Especificación de prueba de precondensado",
        )

    def test_inicio_consume_saldo_real_y_activa_orden_ejecucion(self):
        iniciar_condensacion(corrida_id=self.corrida.pk, usuario=self.usuario)

        self.corrida.refresh_from_db()
        self.ejecucion.refresh_from_db()
        self.orden.refresh_from_db()
        self.assertEqual(self.corrida.estado, CorridaCondensacion.Estado.EN_PROCESO)
        self.assertEqual(self.ejecucion.estado, EjecucionProceso.Estado.EJECUCION)
        self.assertEqual(self.orden.estado, OrdenProduccion.Estado.EN_PROCESO)
        consumo = MovimientoSilo.objects.get(
            origen_tipo=MovimientoSilo.OrigenTipo.PRODUCCION,
            tipo=MovimientoSilo.Tipo.SALIDA,
        )
        self.assertEqual(consumo.litros, Decimal("600"))
        self.assertEqual(consumo.lote, self.lote)

    def test_cierre_deja_precondensado_y_balance_de_ejecucion(self):
        iniciar_condensacion(corrida_id=self.corrida.pk, usuario=self.usuario)

        cerrar_condensacion(
            corrida_id=self.corrida.pk, usuario=self.usuario,
            litros_precondensado="250",
            controles={"densidad_salida": Decimal("1.180"), "solidos_salida": 48},
        )

        self.corrida.refresh_from_db()
        self.ejecucion.refresh_from_db()
        self.assertEqual(self.corrida.estado, CorridaCondensacion.Estado.CERRADA)
        self.assertEqual(self.ejecucion.estado, EjecucionProceso.Estado.CERRADA)
        ingreso = self.destino.movimientos.get(tipo=MovimientoSilo.Tipo.INGRESO)
        self.assertEqual(ingreso.litros, Decimal("250"))
        self.assertEqual(self.ejecucion.entradas.get().cantidad, Decimal("600"))
        self.assertEqual(self.ejecucion.salidas.get().cantidad, Decimal("250"))

    def test_precondensado_finaliza_en_calidad_y_despacho_directo(self):
        self._crear_especificacion_precondensado()
        AnalisisSilo.objects.create(
            silo=self.origen, tomado_en=timezone.now(),
            grasa=Decimal("3.60"), sng=Decimal("8.60"),
            inhibidores_resultado="negativo", metodo="snap",
            hora_lectura=timezone.localtime().time(),
            estado=AnalisisSilo.Estado.CONFIRMADO,
            analista=self.usuario, visualizado_por=self.usuario,
        )
        RutaProducto.objects.create(
            sucursal=self.planta, producto=self.lote.producto,
            proceso=self.ejecucion.etapa.proceso,
            destino="Despacho directo",
        )
        iniciar_condensacion(corrida_id=self.corrida.pk, usuario=self.usuario)

        cerrar_condensacion(
            corrida_id=self.corrida.pk, usuario=self.usuario,
            litros_precondensado="250", controles={"densidad_salida": "1.180"},
        )

        salida = SalidaProceso.objects.get(ejecucion=self.ejecucion)
        self.orden.refresh_from_db()
        self.assertEqual(salida.lote, self.lote)
        self.assertEqual(salida.clasificacion, SalidaProceso.Clasificacion.GRANEL)
        self.assertEqual(salida.destino, SalidaProceso.Destino.DESPACHO_DIRECTO)
        self.assertEqual(self.orden.estado, OrdenProduccion.Estado.PENDIENTE_CALIDAD)
        self.ejecucion.refresh_from_db()
        self.assertEqual(self.ejecucion.estado, EjecucionProceso.Estado.PENDIENTE_CONTROL)

        analisis = AnalisisSilo.objects.create(
            silo=self.destino, tomado_en=timezone.now(),
            grasa=Decimal("7.00"), sng=Decimal("42.00"),
            inhibidores_resultado="negativo", metodo="snap",
            hora_lectura=timezone.localtime().time(),
            estado=AnalisisSilo.Estado.CONFIRMADO,
            analista=self.usuario, visualizado_por=self.usuario,
        )
        calidad = User.objects.create_user("calidad-despacho-directo")
        PerfilUsuario.objects.create(
            usuario=calidad, empresa=self.planta.empresa, sucursal=self.planta,
            rol=Rol.CALIDAD, area=PerfilUsuario.Area.CALIDAD,
        )
        cliente = APIClient()
        cliente.force_authenticate(calidad)
        respuesta = cliente.post(
            f"/api/calidad/resultados-proceso/{salida.pk}/liberar/",
            {"analisis_id": analisis.pk}, format="json",
        )

        self.assertEqual(respuesta.status_code, 200, respuesta.data)
        self.orden.refresh_from_db()
        self.assertEqual(self.orden.estado, OrdenProduccion.Estado.LIBERADA)

    def test_calidad_libera_precondensado_con_analisis_confirmado(self):
        self._crear_especificacion_precondensado()
        self.ejecucion.etapa.requiere_calidad = True
        self.ejecucion.etapa.save(update_fields=["requiere_calidad"])
        AnalisisSilo.objects.create(
            silo=self.origen, tomado_en=timezone.now(),
            grasa=Decimal("3.60"), sng=Decimal("8.60"),
            inhibidores_resultado="negativo", metodo="snap",
            hora_lectura=timezone.localtime().time(),
            estado=AnalisisSilo.Estado.CONFIRMADO,
            analista=self.usuario, visualizado_por=self.usuario,
        )
        iniciar_condensacion(corrida_id=self.corrida.pk, usuario=self.usuario)
        cerrar_condensacion(
            corrida_id=self.corrida.pk, usuario=self.usuario,
            litros_precondensado="250", controles={"densidad_salida": "1.180"},
        )
        self.destino.refresh_from_db()
        self.assertEqual(self.destino.estado, Silo.Estado.BLOQUEADO_CALIDAD)
        analisis = AnalisisSilo.objects.create(
            silo=self.destino, tomado_en=timezone.now(),
            grasa=Decimal("7.00"), sng=Decimal("42.00"),
            inhibidores_resultado="negativo", metodo="snap",
            hora_lectura=timezone.localtime().time(),
            estado=AnalisisSilo.Estado.CONFIRMADO,
            analista=self.usuario, visualizado_por=self.usuario,
        )
        calidad = User.objects.create_user("calidad-condensacion")
        PerfilUsuario.objects.create(
            usuario=calidad, empresa=self.planta.empresa, sucursal=self.planta,
            rol=Rol.CALIDAD, area=PerfilUsuario.Area.CALIDAD,
        )
        cliente = APIClient()
        cliente.force_authenticate(calidad)

        cola = cliente.get("/api/calidad/expedientes/", {"incluir_procesos": "1"})
        self.assertEqual(cola.status_code, 200, cola.data)
        pendiente = next(
            item for item in cola.data["procesos"]
            if item["id"] == self.ejecucion.salidas.get().pk
        )
        self.assertEqual(pendiente["especificacion"]["version"], 1)
        self.assertEqual(pendiente["analisis_disponibles"][0]["resultado"], "conforme")

        respuesta = cliente.post(
            f"/api/calidad/resultados-proceso/{self.ejecucion.salidas.get().pk}/liberar/",
            {"analisis_id": analisis.pk}, format="json",
        )

        self.assertEqual(respuesta.status_code, 200, respuesta.data)
        self.corrida.refresh_from_db()
        self.ejecucion.refresh_from_db()
        self.destino.refresh_from_db()
        self.assertEqual(self.corrida.estado, CorridaCondensacion.Estado.CERRADA)
        self.assertEqual(self.ejecucion.estado, EjecucionProceso.Estado.CERRADA)
        self.assertEqual(self.destino.estado, Silo.Estado.DISPONIBLE)

    def test_calidad_no_libera_precondensado_fuera_de_especificacion(self):
        self.ejecucion.etapa.requiere_calidad = True
        self.ejecucion.etapa.save(update_fields=["requiere_calidad"])
        AnalisisSilo.objects.create(
            silo=self.origen, tomado_en=timezone.now(),
            grasa=Decimal("3.60"), sng=Decimal("8.60"),
            inhibidores_resultado="negativo", metodo="snap",
            hora_lectura=timezone.localtime().time(),
            estado=AnalisisSilo.Estado.CONFIRMADO,
            analista=self.usuario, visualizado_por=self.usuario,
        )
        iniciar_condensacion(corrida_id=self.corrida.pk, usuario=self.usuario)
        cerrar_condensacion(
            corrida_id=self.corrida.pk, usuario=self.usuario,
            litros_precondensado="250", controles={"densidad_salida": "1.180"},
        )
        analisis = AnalisisSilo.objects.create(
            silo=self.destino, tomado_en=timezone.now(),
            grasa=Decimal("5.00"), sng=Decimal("40.00"),
            inhibidores_resultado="negativo", metodo="snap",
            hora_lectura=timezone.localtime().time(),
            estado=AnalisisSilo.Estado.CONFIRMADO,
            analista=self.usuario, visualizado_por=self.usuario,
        )
        calidad = User.objects.create_user("calidad-fuera-especificacion")
        PerfilUsuario.objects.create(
            usuario=calidad, empresa=self.planta.empresa, sucursal=self.planta,
            rol=Rol.CALIDAD, area=PerfilUsuario.Area.CALIDAD,
        )
        cliente = APIClient()
        cliente.force_authenticate(calidad)

        sin_especificacion = cliente.post(
            f"/api/calidad/resultados-proceso/{self.ejecucion.salidas.get().pk}/liberar/",
            {"analisis_id": analisis.pk}, format="json",
        )
        self.assertEqual(sin_especificacion.status_code, 409, sin_especificacion.data)
        self.assertEqual(sin_especificacion.data["resultado"], "sin_especificacion")

        self._crear_especificacion_precondensado()
        respuesta = cliente.post(
            f"/api/calidad/resultados-proceso/{self.ejecucion.salidas.get().pk}/liberar/",
            {"analisis_id": analisis.pk}, format="json",
        )

        self.assertEqual(respuesta.status_code, 409, respuesta.data)
        self.assertEqual(respuesta.data["resultado"], "no_conforme")
        self.assertEqual(
            {item["parametro"] for item in respuesta.data["desviaciones"]},
            {"mg", "st"},
        )
        self.ejecucion.refresh_from_db()
        self.destino.refresh_from_db()
        self.assertEqual(self.ejecucion.estado, EjecucionProceso.Estado.PENDIENTE_CONTROL)
        self.assertEqual(self.destino.estado, Silo.Estado.BLOQUEADO_CALIDAD)

    def test_no_inicia_con_saldo_insuficiente_o_silo_bloqueado(self):
        self.corrida.litros_entrada = Decimal("1600")
        self.corrida.save(update_fields=["litros_entrada"])
        with self.assertRaises(ValidationError):
            iniciar_condensacion(corrida_id=self.corrida.pk, usuario=self.usuario)
        self.corrida.litros_entrada = Decimal("600")
        self.corrida.save(update_fields=["litros_entrada"])
        self.origen.estado = Silo.Estado.BLOQUEADO_CALIDAD
        self.origen.save(update_fields=["estado"])
        with self.assertRaises(ValidationError):
            iniciar_condensacion(corrida_id=self.corrida.pk, usuario=self.usuario)

        self.assertFalse(MovimientoSilo.objects.filter(
            origen_tipo=MovimientoSilo.OrigenTipo.PRODUCCION
        ).exists())

    def test_adopta_la_ejecucion_del_lote_sin_consumir_dos_veces(self):
        """La corrida es el detalle especializado del mismo hecho físico."""
        self.lote.ejecucion = self.ejecucion
        self.lote.save(update_fields=["ejecucion"])
        self.ejecucion.estado = EjecucionProceso.Estado.EJECUCION
        self.ejecucion.inicio = timezone.now()
        self.ejecucion.save(update_fields=["estado", "inicio"])
        EntradaProceso.objects.create(
            ejecucion=self.ejecucion,
            silo=self.origen,
            cantidad=Decimal("600"),
            unidad="L",
        )
        MovimientoSilo.objects.create(
            silo=self.origen,
            tipo=MovimientoSilo.Tipo.SALIDA,
            litros=Decimal("600"),
            fecha_hora=timezone.now(),
            origen_tipo=MovimientoSilo.OrigenTipo.LOTE,
            origen_id=self.lote.pk,
            lote=self.lote,
        )

        iniciar_condensacion(corrida_id=self.corrida.pk, usuario=self.usuario)

        self.corrida.refresh_from_db()
        self.assertEqual(self.corrida.estado, CorridaCondensacion.Estado.EN_PROCESO)
        self.assertEqual(
            MovimientoSilo.objects.filter(
                silo=self.origen, tipo=MovimientoSilo.Tipo.SALIDA
            ).count(),
            1,
        )
        self.assertEqual(self.ejecucion.entradas.count(), 1)

    def test_alta_guiada_reutiliza_lote_ejecucion_entrada_y_orden(self):
        self.corrida.delete()
        self.lote.ejecucion = self.ejecucion
        self.lote.save(update_fields=["ejecucion"])
        EntradaProceso.objects.create(
            ejecucion=self.ejecucion, silo=self.origen,
            cantidad=Decimal("600"), unidad="L",
        )

        corrida = crear_condensacion_guiada(
            lote_id=self.lote.pk, silo_destino_id=self.destino.pk,
            usuario=self.usuario,
        )

        self.assertEqual(corrida.ejecucion, self.ejecucion)
        self.assertEqual(corrida.orden, self.orden)
        self.assertEqual(corrida.silo_origen, self.origen)
        self.assertEqual(corrida.litros_entrada, Decimal("600"))

    def test_opciones_alta_solo_exponen_lote_evaporador_preparado(self):
        self.corrida.delete()
        self.lote.ejecucion = self.ejecucion
        self.lote.save(update_fields=["ejecucion"])
        EntradaProceso.objects.create(
            ejecucion=self.ejecucion, silo=self.origen,
            cantidad=Decimal("600"), unidad="L",
        )
        cliente = APIClient()
        cliente.force_authenticate(self.usuario)

        respuesta = cliente.get("/api/procesos/condensaciones/opciones-alta/")

        self.assertEqual(respuesta.status_code, 200, respuesta.data)
        self.assertEqual([item["id"] for item in respuesta.data["lotes"]], [self.lote.pk])

    def test_no_adopta_una_ejecucion_activa_sin_consumo(self):
        self.lote.ejecucion = self.ejecucion
        self.lote.save(update_fields=["ejecucion"])
        self.ejecucion.estado = EjecucionProceso.Estado.EJECUCION
        self.ejecucion.inicio = timezone.now()
        self.ejecucion.save(update_fields=["estado", "inicio"])

        with self.assertRaisesMessage(ValidationError, "no tiene su consumo"):
            iniciar_condensacion(corrida_id=self.corrida.pk, usuario=self.usuario)

        self.assertFalse(MovimientoSilo.objects.filter(
            silo=self.origen, tipo=MovimientoSilo.Tipo.SALIDA
        ).exists())
