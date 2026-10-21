"""Regresiones del contrato de alimentación y confirmación de Secado OP-04."""

from datetime import timedelta
from decimal import Decimal
from queue import Queue
import threading
import time
from unittest.mock import patch
from uuid import uuid4

from django.db import connection, connections, transaction
from django.contrib.auth.models import User
from django.test import TestCase, TransactionTestCase
from django.utils import timezone
from rest_framework.test import APIClient

from calidad.models import LiberacionProceso
from calidad.vigencia import registrar_firma_salida
from inventario.models import CicloCIP, Existencia, LoteInventario, MovimientoInventario
from maestros.models import Equipo, Silo
from produccion import servicios as produccion_servicios
from recepcion.models import AnalisisSilo, MovimientoSilo
from usuarios.models import PerfilUsuario, Rol
from .models import (
    CorridaSecado, EjecucionProceso, EntradaProceso, EtapaProceso,
    EventoProceso, Proceso, SalidaProceso,
)
from . import tests_secado as fixtures_secado
from produccion import tests_lote_desde_vale as fixtures_vale


class InicioSecadoOP04Tests(TestCase):
    def setUp(self):
        fixtures_secado.InicioSecadoDesdeInventarioTests.setUp(self)

    def _inicio(self, *, existencia=None, operacion_id=None, **extra):
        return self.cliente.post(
            "/api/procesos/secados/iniciar-desde-inventario/",
            {
                "orden": self.orden.pk,
                "existencia": (existencia or self.existencia).pk,
                "equipo": self.torre.pk,
                "codigo_lote": "OP04-POLVO",
                "cantidad": "100.000",
                "operacion_id": str(operacion_id or uuid4()),
                **extra,
            },
            format="json",
        )

    def test_fifo_no_admite_saltar_lote_mas_antiguo_sin_motivo(self):
        antiguo = LoteInventario.objects.create(
            sucursal=self.planta, insumo=self.insumo, codigo="PROV-ANTIGUO",
            estado_calidad=LoteInventario.EstadoCalidad.APROBADO,
            recibido_en=timezone.now() - timedelta(days=2),
        )
        existencia_antigua = Existencia.objects.create(
            lote=antiguo, ubicacion=self.existencia.ubicacion,
            cantidad_fisica=Decimal("200.000"),
        )
        respuesta = self._inicio()
        self.assertEqual(respuesta.status_code, 400, respuesta.data)
        self.assertEqual(self.existencia.cantidad_fisica, Decimal("1000"))

        respuesta = self._inicio(existencia=self.existencia,
            excepcion_fifo_motivo="Lote anterior reservado para ensayo de línea")
        self.assertEqual(respuesta.status_code, 201, respuesta.data)
        evento = EventoProceso.objects.get(
            ejecucion_id=respuesta.data["ejecucion"], tipo="inicio_secado_externo",
        )
        self.assertIn("ensayo", evento.motivo)
        existencia_antigua.refresh_from_db()
        self.assertEqual(existencia_antigua.cantidad_fisica, Decimal("200.000"))

    def test_reintento_inicio_mismo_uuid_recupera_sin_consumir_dos_veces(self):
        clave = uuid4()
        primera = self._inicio(operacion_id=clave)
        self.assertEqual(primera.status_code, 201, primera.data)
        segunda = self._inicio(operacion_id=clave)
        self.assertEqual(segunda.status_code, 200, segunda.data)
        self.assertEqual(primera.data["id"], segunda.data["id"])
        self.assertEqual(MovimientoInventario.objects.filter(
            documento_tipo="procesos.EjecucionProceso",
            documento_id=primera.data["ejecucion"],
            tipo=MovimientoInventario.Tipo.CONSUMO,
        ).count(), 1)
        distinto = self._inicio(operacion_id=clave, cantidad="101.000")
        self.assertEqual(distinto.status_code, 400, distinto.data)

    def test_ultimo_saldo_no_puede_consumirse_dos_veces(self):
        primera = self._inicio(cantidad="1000.000")
        self.assertEqual(primera.status_code, 201, primera.data)
        segunda_torre = Equipo.objects.create(
            sucursal=self.planta, codigo="TOR-OP04-2", nombre="Torre OP04 2",
            tipo=Equipo.Tipo.TORRE,
        )
        segunda = self._inicio(
            equipo=segunda_torre.pk, codigo_lote="OP04-POLVO-2",
            cantidad="0.001",
        )
        self.assertEqual(segunda.status_code, 400, segunda.data)
        self.existencia.refresh_from_db()
        self.assertEqual(self.existencia.cantidad_fisica, Decimal("0"))
        self.assertEqual(MovimientoInventario.objects.filter(
            lote=self.lote_externo,
            tipo=MovimientoInventario.Tipo.CONSUMO,
        ).count(), 1)

    def test_fallo_despues_del_consumo_revierte_movimiento_y_lote(self):
        from inventario import servicios as inventario_servicios
        from procesos.servicios import crear_secado_desde_inventario

        registrar_real = inventario_servicios.registrar_salida

        def fallo_despues_de_consumir(**kwargs):
            registrar_real(**kwargs)
            raise RuntimeError("fallo posterior al consumo")

        with patch.object(inventario_servicios, "registrar_salida", fallo_despues_de_consumir):
            with self.assertRaises(RuntimeError):
                crear_secado_desde_inventario(
                    orden=self.orden, existencia=self.existencia,
                    equipo=self.torre, codigo_lote="OP04-ROLLBACK",
                    cantidad=Decimal("100"), usuario=self.usuario,
                    operacion_id=uuid4(),
                )
        self.existencia.refresh_from_db()
        self.assertEqual(self.existencia.cantidad_fisica, Decimal("1000"))
        self.assertFalse(MovimientoInventario.objects.filter(
            lote=self.lote_externo, tipo=MovimientoInventario.Tipo.CONSUMO,
        ).exists())

    def test_cierre_externo_real_y_reintento_exactos(self):
        inicio = self._inicio()
        self.assertEqual(inicio.status_code, 201, inicio.data)
        corrida_id = inicio.data["id"]
        cierre = {
            "operacion_id": str(uuid4()),
            "kg_alimentacion": "100.000",
            "solidos_entrada_pct": "48.00",
            "kg_polvo": "50.000",
            "kg_finos": "2.000",
            "kg_merma": "1.000",
            "controles": {"temperatura_salida": 82},
        }
        url = f"/api/procesos/secados/{corrida_id}/cerrar/"
        primera = self.cliente.post(url, cierre, format="json")
        self.assertEqual(primera.status_code, 200, primera.data)
        self.assertEqual(primera.data["entradas_alimentacion"][0]["unidad"], "kg")
        self.assertFalse(primera.data["requiere_referencia_medicion_kg"])
        segunda = self.cliente.post(url, cierre, format="json")
        self.assertEqual(segunda.status_code, 200, segunda.data)
        self.assertEqual(SalidaProceso.objects.filter(
            ejecucion_id=inicio.data["ejecucion"],
        ).count(), 1)
        self.assertEqual(EventoProceso.objects.filter(
            ejecucion_id=inicio.data["ejecucion"], tipo="cierre_secado",
        ).count(), 1)
        distinto = self.cliente.post(
            url, {**cierre, "kg_polvo": "51.000"}, format="json",
        )
        self.assertEqual(distinto.status_code, 400, distinto.data)

    def test_calidad_bloqueada_despues_del_inicio_impide_cierre(self):
        inicio = self._inicio()
        self.assertEqual(inicio.status_code, 201, inicio.data)
        self.lote_externo.estado_calidad = LoteInventario.EstadoCalidad.BLOQUEADO
        self.lote_externo.save(update_fields=["estado_calidad"])
        cierre = self.cliente.post(
            f"/api/procesos/secados/{inicio.data['id']}/cerrar/",
            {
                "operacion_id": str(uuid4()), "kg_alimentacion": "100.000",
                "solidos_entrada_pct": "48.00", "kg_polvo": "50.000",
            }, format="json",
        )
        self.assertEqual(cierre.status_code, 400, cierre.data)
        self.assertFalse(SalidaProceso.objects.filter(
            ejecucion_id=inicio.data["ejecucion"],
        ).exists())
        self.assertFalse(EventoProceso.objects.filter(
            ejecucion_id=inicio.data["ejecucion"], tipo="cierre_secado",
        ).exists())

    def test_cliente_no_puede_escribir_metadatos_op04(self):
        inicio = self._inicio()
        self.assertEqual(inicio.status_code, 201, inicio.data)
        cierre = self.cliente.post(
            f"/api/procesos/secados/{inicio.data['id']}/cerrar/",
            {
                "operacion_id": str(uuid4()), "kg_alimentacion": "100.000",
                "solidos_entrada_pct": "48.00", "kg_polvo": "50.000",
                "controles": {"_op04": {"actor_id": 1}},
            }, format="json",
        )
        self.assertEqual(cierre.status_code, 400, cierre.data)
        self.assertIn("controles", cierre.data)


class CierreSecadoOP04Tests(TestCase):
    def setUp(self):
        fixtures_secado.CierreSecadoTests.setUp(self)

    def _cierre(self, **extra):
        datos = {
            "operacion_id": str(uuid4()),
            "kg_alimentacion": "600.000",
            "solidos_entrada_pct": "48.00",
            "kg_polvo": "280.000",
            "kg_finos": "5.000",
            "kg_merma": "3.000",
            **extra,
        }
        return self.cliente.post(
            f"/api/procesos/secados/{self.corrida.pk}/cerrar/", datos,
            format="json",
        )

    def test_sin_origen_real_no_se_puede_confirmar(self):
        EntradaProceso.objects.filter(ejecucion=self.corrida.ejecucion).delete()
        respuesta = self._cierre()
        self.assertEqual(respuesta.status_code, 400, respuesta.data)
        self.assertFalse(SalidaProceso.objects.filter(
            ejecucion=self.corrida.ejecucion,
        ).exists())

    def test_entrada_litros_requiere_referencia_de_kg_medidos(self):
        respuesta = self._cierre()
        self.assertEqual(respuesta.status_code, 400, respuesta.data)
        self.assertIn("referencia_medicion_kg", respuesta.data)

    def test_doble_entrada_del_mismo_silo_no_reutiliza_un_retiro(self):
        entrada = EntradaProceso.objects.get(ejecucion=self.corrida.ejecucion)
        EntradaProceso.objects.create(
            ejecucion=self.corrida.ejecucion, silo=entrada.silo,
            tipo=EntradaProceso.Tipo.PRINCIPAL,
            cantidad=Decimal("10"), unidad="L",
        )
        retiros_antes = MovimientoSilo.objects.filter(
            silo=entrada.silo, tipo=MovimientoSilo.Tipo.SALIDA,
        ).count()
        respuesta = self._cierre(
            referencia_medicion_kg="Ticket báscula 456",
        )
        self.assertEqual(respuesta.status_code, 400, respuesta.data)
        self.assertIn("alimentacion", respuesta.data)
        self.assertEqual(MovimientoSilo.objects.filter(
            silo=entrada.silo, tipo=MovimientoSilo.Tipo.SALIDA,
        ).count(), retiros_antes)
        self.corrida.lote.refresh_from_db()
        self.assertEqual(self.corrida.lote.estado, self.corrida.lote.Estado.EN_PROCESO)

    def test_continuacion_litros_retira_silo_en_mismo_cierre(self):
        silo = Silo.objects.create(
            sucursal=self.corrida.ejecucion.sucursal, codigo="S-CONT-OP04",
            tipo=Silo.Tipo.SILO, capacidad_l=Decimal("1000"),
        )
        MovimientoSilo.objects.create(
            silo=silo, tipo=MovimientoSilo.Tipo.INGRESO,
            litros=Decimal("600"), fecha_hora=timezone.now(),
            origen_tipo=MovimientoSilo.OrigenTipo.AJUSTE,
            motivo="Saldo sintético de continuación",
        )
        proceso = Proceso.objects.create(
            codigo="evap-op04", nombre="Evaporación OP04",
        )
        etapa = EtapaProceso.objects.create(
            proceso=proceso, codigo="evap-op04", nombre="Evaporar",
            tipo=EtapaProceso.Tipo.EVAPORACION, orden=1,
        )
        anterior = EjecucionProceso.objects.create(
            codigo="EJ-EVAP-OP04", etapa=etapa,
            sucursal=self.corrida.ejecucion.sucursal,
            estado=EjecucionProceso.Estado.CERRADA,
        )
        salida = SalidaProceso.objects.create(
            ejecucion=anterior, silo=silo, producto=self.producto,
            naturaleza=SalidaProceso.Naturaleza.PRINCIPAL,
            cantidad=Decimal("600"), unidad="L",
        )
        calidad = User.objects.create_user("calidad-cont-op04")
        PerfilUsuario.objects.create(
            usuario=calidad,
            empresa=self.corrida.ejecucion.sucursal.empresa,
            sucursal=self.corrida.ejecucion.sucursal,
            rol=Rol.CALIDAD, area=PerfilUsuario.Area.CALIDAD,
        )
        ahora = timezone.now()
        analisis = AnalisisSilo.objects.create(
            silo=silo, tomado_en=ahora,
            estado=AnalisisSilo.Estado.CONFIRMADO,
            grasa=Decimal("3.5"), sng=Decimal("9"),
            inhibidores_resultado="negativo", metodo="tri_sensor",
            hora_lectura=ahora.time(), analista=calidad,
            visualizado_por=calidad, visualizado_en=ahora,
        )
        decision = LiberacionProceso(
            salida=salida, estado=LiberacionProceso.Estado.LIBERADO,
            analisis_silo=analisis, decidida_por=calidad, decidida_en=ahora,
        )
        decision.full_clean()
        decision.save()
        EntradaProceso.objects.filter(ejecucion=self.corrida.ejecucion).delete()
        EntradaProceso.objects.create(
            ejecucion=self.corrida.ejecucion, silo=silo, salida_origen=salida,
            tipo=EntradaProceso.Tipo.PRINCIPAL,
            cantidad=Decimal("600"), unidad="L",
        )
        clave = uuid4()
        sin_firma = self._cierre(
            operacion_id=str(clave),
            referencia_medicion_kg="Ticket báscula continuidad 123",
        )
        self.assertEqual(sin_firma.status_code, 400, sin_firma.data)
        self.assertFalse(MovimientoSilo.objects.filter(
            silo=silo, tipo=MovimientoSilo.Tipo.SALIDA,
        ).exists())
        registrar_firma_salida(decision)
        cip = CicloCIP.objects.create(
            sucursal=self.corrida.ejecucion.sucursal,
            area=PerfilUsuario.Area.SECADO,
            tipo_objetivo=CicloCIP.TipoObjetivo.SILO, silo=silo,
            inicio=timezone.now(), estado=CicloCIP.Estado.EN_CURSO,
            responsable=self.usuario,
        )
        bloqueado_cip = self._cierre(
            operacion_id=str(clave),
            referencia_medicion_kg="Ticket báscula continuidad 123",
        )
        self.assertEqual(bloqueado_cip.status_code, 400, bloqueado_cip.data)
        self.assertFalse(MovimientoSilo.objects.filter(
            silo=silo, tipo=MovimientoSilo.Tipo.SALIDA,
        ).exists())
        cip.estado = CicloCIP.Estado.COMPLETADO
        cip.fin = timezone.now()
        cip.save(update_fields=["estado", "fin"])
        respuesta = self._cierre(
            operacion_id=str(clave),
            referencia_medicion_kg="Ticket báscula continuidad 123",
        )
        self.assertEqual(respuesta.status_code, 200, respuesta.data)
        retiros = MovimientoSilo.objects.filter(
            silo=silo, tipo=MovimientoSilo.Tipo.SALIDA,
            origen_tipo=MovimientoSilo.OrigenTipo.PRODUCCION,
            origen_id=self.corrida.pk,
        )
        self.assertEqual(retiros.count(), 1)
        self.assertEqual(retiros.get().litros, Decimal("600"))
        self.assertEqual(retiros.get().operacion_id, clave)
        repetida = self._cierre(
            operacion_id=str(clave),
            referencia_medicion_kg="Ticket báscula continuidad 123",
        )
        self.assertEqual(repetida.status_code, 200, repetida.data)
        self.assertEqual(retiros.count(), 1)


class CierreDesdeValeOP04Tests(TestCase):
    def setUp(self):
        fixtures_vale.BaseValeLote.setUp(self)
        torre = Equipo.objects.create(
            sucursal=self.planta, codigo="TOR-VALE-OP04", nombre="Torre vale",
            tipo=Equipo.Tipo.TORRE,
        )
        PerfilUsuario.objects.create(
            usuario=self.operador, empresa=self.empresa, sucursal=self.planta,
            alcance=PerfilUsuario.Alcance.SUCURSAL,
            rol=Rol.PRODUCCION, area=PerfilUsuario.Area.SECADO,
        )
        vale = fixtures_vale.BaseValeLote._vale(self)
        self.lote = produccion_servicios.abrir_lote_desde_vale(
            vale=vale, producto=self.producto, codigo_lote="VALE-SEC-OP04",
            fecha=timezone.localdate(), litros=Decimal("1000.00"),
            equipo=torre, usuario=self.operador,
        )
        self.corrida = CorridaSecado.objects.get(lote=self.lote)
        self.cliente = APIClient()
        self.cliente.force_authenticate(self.operador)

    def test_cierre_con_litros_reales_y_kg_medidos_conserva_ambas_unidades(self):
        entrada = EntradaProceso.objects.get(ejecucion=self.corrida.ejecucion)
        self.assertEqual(entrada.unidad, "L")
        self.assertEqual(entrada.cantidad, Decimal("1000.000"))
        self.assertEqual(MovimientoSilo.objects.filter(
            lote=self.lote, tipo=MovimientoSilo.Tipo.SALIDA,
        ).count(), 1)
        respuesta = self.cliente.post(
            f"/api/procesos/secados/{self.corrida.pk}/cerrar/",
            {
                "operacion_id": str(uuid4()),
                "kg_alimentacion": "600.000",
                "referencia_medicion_kg": "Ticket bascula T-123",
                "solidos_entrada_pct": "48.00", "kg_polvo": "280.000",
                "kg_finos": "5.000", "kg_merma": "3.000",
            }, format="json",
        )
        self.assertEqual(respuesta.status_code, 200, respuesta.data)
        entrada.refresh_from_db()
        self.assertEqual(entrada.cantidad, Decimal("1000.000"))
        self.assertEqual(entrada.unidad, "L")
        self.corrida.refresh_from_db()
        evidencia = self.corrida.controles["_op04"]["cierre"]
        self.assertEqual(evidencia["medicion_kg"]["referencia"], "Ticket bascula T-123")
        self.assertEqual(evidencia["actor_id"], self.operador.pk)
        self.assertTrue(evidencia["fecha"])
        self.assertEqual(respuesta.data["entradas_alimentacion"][0]["unidad"], "L")
        self.assertTrue(respuesta.data["requiere_referencia_medicion_kg"])


class CarreraInicioSecadoOP04Tests(TransactionTestCase):
    def setUp(self):
        if connection.vendor != "postgresql":
            self.skipTest("La carrera requiere bloqueos reales de PostgreSQL.")
        fixtures_secado.InicioSecadoDesdeInventarioTests.setUp(self)

    def test_dos_requests_mismo_uuid_esperan_y_recuperan_un_consumo(self):
        from procesos.servicios import _bloquear_operacion_secado

        clave = uuid4()
        datos = {
            "orden": self.orden.pk, "existencia": self.existencia.pk,
            "equipo": self.torre.pk, "codigo_lote": "OP04-CARRERA",
            "cantidad": "100.000", "operacion_id": str(clave),
        }
        pids, resultados = Queue(), Queue()

        def segundo_request():
            cliente = APIClient()
            cliente.force_authenticate(self.usuario)
            try:
                with connection.cursor() as cursor:
                    cursor.execute("SET lock_timeout = '5s'")
                    cursor.execute("SELECT pg_backend_pid()")
                    pids.put(cursor.fetchone()[0])
                respuesta = cliente.post(
                    "/api/procesos/secados/iniciar-desde-inventario/",
                    datos, format="json",
                )
                resultados.put((respuesta.status_code, respuesta.data))
            except Exception as error:
                resultados.put(("error", repr(error)))
            finally:
                connections.close_all()

        hilo = threading.Thread(target=segundo_request, daemon=True)
        bloqueado = False
        primero = None
        try:
            with transaction.atomic():
                _bloquear_operacion_secado(clave)
                hilo.start()
                pid = pids.get(timeout=6)
                limite = time.monotonic() + 3
                while time.monotonic() < limite:
                    with connection.cursor() as cursor:
                        cursor.execute("SELECT pg_blocking_pids(%s)", [pid])
                        bloqueado = bool(cursor.fetchone()[0])
                    if bloqueado:
                        break
                    threading.Event().wait(0.01)
                primero = self.cliente.post(
                    "/api/procesos/secados/iniciar-desde-inventario/",
                    datos, format="json",
                )
        finally:
            if hilo.ident is not None:
                hilo.join(timeout=7)
        self.assertFalse(hilo.is_alive(), "El segundo request no terminó.")
        self.assertTrue(bloqueado, "No se observó bloqueo real entre conexiones.")
        self.assertEqual(primero.status_code, 201, primero.data)
        codigo, detalle = resultados.get(timeout=1)
        self.assertEqual(codigo, 200, detalle)
        self.assertEqual(detalle["id"], primero.data["id"])
        self.assertEqual(MovimientoInventario.objects.filter(
            tipo=MovimientoInventario.Tipo.CONSUMO,
            documento_tipo="procesos.EjecucionProceso",
            documento_id=primero.data["ejecucion"],
        ).count(), 1)
