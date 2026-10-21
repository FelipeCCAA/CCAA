"""Reservas OP-03 en las operaciones reales de los silos de recepción."""

from decimal import Decimal
from queue import Queue
import threading
import time
import uuid
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.db import connection, connections, transaction
from django.test import TestCase, TransactionTestCase
from django.utils import timezone
from rest_framework.test import APIClient

from maestros.models import Silo
from inventario.models import CicloCIP
from procesos.models import EjecucionProceso, EtapaProceso, Proceso, ReservaSiloProceso
from usuarios.models import PerfilUsuario, Rol

from .models import AnalisisSilo, AtribucionRecepcion, DespachoLeche, MovimientoSilo
from .servicios import saldo_silo, transferir_silo


class ReservasRecepcionOP03Tests(TestCase):
    def setUp(self):
        self.usuario = get_user_model().objects.create_user("recepcion-reservas-op03")
        PerfilUsuario.objects.create(
            usuario=self.usuario,
            rol=Rol.RECEPCION,
            area=PerfilUsuario.Area.RECEPCION,
        )
        self.api = APIClient()
        self.api.force_authenticate(self.usuario)
        self.origen = Silo.objects.create(
            codigo="OP03-ORIGEN",
            tipo=Silo.Tipo.SILO,
            capacidad_l="1000.00",
        )
        self.destino = Silo.objects.create(
            sucursal=self.origen.sucursal,
            codigo="OP03-DESTINO",
            tipo=Silo.Tipo.SILO,
            capacidad_l="600.00",
        )
        MovimientoSilo.objects.create(
            silo=self.origen,
            tipo=MovimientoSilo.Tipo.INGRESO,
            litros="800.00",
            fecha_hora=timezone.now(),
            motivo="Existencia inicial sintética OP03",
        )
        self.analisis = AnalisisSilo.objects.create(
            silo=self.origen,
            tomado_en=timezone.now(),
            grasa="4.20",
            sng="8.80",
            inhibidores_resultado="negativo",
            metodo="delvo_sp",
            hora_lectura=timezone.localtime().time(),
            analista=self.usuario,
            visualizado_por=self.usuario,
            visualizado_en=timezone.now(),
            estado=AnalisisSilo.Estado.CONFIRMADO,
        )
        proceso = Proceso.objects.create(codigo="OP03-RESERVAS", nombre="Proceso OP03")
        etapa = EtapaProceso.objects.create(
            proceso=proceso,
            codigo="OP03-ETAPA",
            nombre="Etapa OP03",
            tipo=EtapaProceso.Tipo.CONDENSACION,
            orden=1,
        )
        self.ejecucion = EjecucionProceso.objects.create(
            codigo="OP03-RESERVA-1",
            etapa=etapa,
            sucursal=self.origen.sucursal,
            responsable=self.usuario,
            estado=EjecucionProceso.Estado.EJECUCION,
        )

    def _reservar(self, silo, tipo, cantidad):
        return ReservaSiloProceso.objects.create(
            ejecucion=self.ejecucion,
            silo=silo,
            tipo=tipo,
            cantidad_planificada=Decimal(cantidad),
        )

    def _foto(self):
        return {
            modelo._meta.label: list(modelo.objects.order_by("pk").values())
            for modelo in (
                MovimientoSilo,
                AtribucionRecepcion,
                DespachoLeche,
                ReservaSiloProceso,
            )
        }

    def _transferir(self, litros="300.00", *, clave=None):
        return self.api.post(
            "/api/recepcion/movimientos/transferir/",
            {
                "silo_origen": self.origen.pk,
                "silo_destino": self.destino.pk,
                "litros": litros,
                "operacion_id": str(clave or uuid.uuid4()),
                "motivo": "Traslado sintético OP03",
            },
            format="json",
        )

    def _despachar(self, litros="400.00", *, clave=None, fecha_hora=None):
        return self.api.post(
            "/api/recepcion/despachos-leche/",
            {
                "silo": self.origen.pk,
                "litros": litros,
                "destino": "Cliente sintético OP03",
                "guia_despacho": "OP03-GD-1",
                "patente": "ABCD-12",
                "fecha_hora": (fecha_hora or timezone.now()).isoformat(),
                "operacion_id": str(clave or uuid.uuid4()),
            },
            format="json",
        )

    def test_transferencia_no_consume_litros_reservados_por_otra_ejecucion(self):
        self._reservar(self.origen, ReservaSiloProceso.Tipo.ORIGEN, "700.00")
        antes = self._foto()

        respuesta = self._transferir()

        self.assertEqual(respuesta.status_code, 400, respuesta.data)
        self.assertEqual(self._foto(), antes)
        self.assertEqual(saldo_silo(self.origen), Decimal("800.00"))
        self.assertEqual(saldo_silo(self.destino), Decimal("0.00"))

    def test_transferencia_respeta_capacidad_reservada_del_destino(self):
        self._reservar(self.destino, ReservaSiloProceso.Tipo.DESTINO, "600.00")
        antes = self._foto()

        respuesta = self._transferir()

        self.assertEqual(respuesta.status_code, 400, respuesta.data)
        self.assertEqual(self._foto(), antes)

    def test_despacho_leche_no_consume_litros_reservados_por_otra_ejecucion(self):
        self._reservar(self.origen, ReservaSiloProceso.Tipo.ORIGEN, "700.00")
        antes = self._foto()

        respuesta = self._despachar()

        self.assertEqual(respuesta.status_code, 400, respuesta.data)
        self.assertEqual(self._foto(), antes)
        self.assertEqual(saldo_silo(self.origen), Decimal("800.00"))

    def test_ocupacion_distingue_fisico_reservado_libre_y_disponible(self):
        self._reservar(self.origen, ReservaSiloProceso.Tipo.ORIGEN, "700.00")
        self._reservar(self.destino, ReservaSiloProceso.Tipo.DESTINO, "600.00")
        respuesta = self.api.get("/api/recepcion/ocupacion/")
        self.assertEqual(respuesta.status_code, 200, respuesta.data)
        silos = {fila["silo_id"]: fila for fila in respuesta.data["silos"]}
        origen, destino = silos[self.origen.pk], silos[self.destino.pk]
        for campo, valor in {
            "litros": "800.00",
            "litros_reservados": "700.00",
            "litros_libres": "100.00",
            "litros_disponibles": "100.00",
            "capacidad_reservada": "0.00",
        }.items():
            self.assertEqual(Decimal(str(origen[campo])), Decimal(valor), campo)
        self.assertEqual(Decimal(str(destino["litros"])), Decimal("0.00"))
        self.assertEqual(
            Decimal(str(destino["capacidad_reservada"])), Decimal("600.00")
        )

        self.origen.estado = Silo.Estado.BLOQUEADO_CALIDAD
        self.origen.save(update_fields=["estado"])
        retenida = self.api.get("/api/recepcion/ocupacion/")
        self.assertEqual(retenida.status_code, 200, retenida.data)
        origen = next(
            f for f in retenida.data["silos"] if f["silo_id"] == self.origen.pk
        )
        self.assertEqual(Decimal(str(origen["litros_libres"])), Decimal("100.00"))
        self.assertEqual(Decimal(str(origen["litros_disponibles"])), Decimal("0.00"))

    def test_sugerencia_fifo_usa_100_libres_y_no_propone_origen_reservado_como_destino(
        self,
    ):
        reserva = self._reservar(self.origen, ReservaSiloProceso.Tipo.ORIGEN, "700.00")
        url = "/api/recepcion/silos/sugerencia/?volumen=300&tipo=silo"
        antes = self._foto()

        respuesta = self.api.get(url)

        self.assertEqual(respuesta.status_code, 200, respuesta.data)
        fila = next(
            f for f in respuesta.data["sugerencias"] if f["silo"] == self.origen.pk
        )
        self.assertTrue(fila["sugerido"])
        self.assertEqual(Decimal(str(fila["litros_disponibles"])), Decimal("100.00"))
        self.assertEqual(Decimal(str(fila["litros_sugeridos"])), Decimal("100.00"))
        self.assertEqual(self._foto(), antes)

        reserva.estado = ReservaSiloProceso.Estado.LIBERADA
        reserva.cerrada_en = timezone.now()
        reserva.save(update_fields=["estado", "cerrada_en"])
        self._reservar(self.origen, ReservaSiloProceso.Tipo.DESTINO, "200.00")
        antes = self._foto()

        retenida = self.api.get(url)

        self.assertEqual(retenida.status_code, 200, retenida.data)
        sugeridos = [f["silo"] for f in retenida.data["sugerencias"] if f["sugerido"]]
        self.assertNotIn(self.origen.pk, sugeridos)
        for candidato in retenida.data["sugerencias"]:
            if candidato["silo"] == self.origen.pk:
                self.assertEqual(
                    Decimal(str(candidato["litros_sugeridos"])), Decimal("0.00")
                )
                self.assertTrue(candidato["motivos_no_disponible"])
        self.assertEqual(self._foto(), antes)

    def test_transferencia_permite_solo_los_100_litros_libres_sin_mover_reserva(self):
        reserva = self._reservar(self.origen, ReservaSiloProceso.Tipo.ORIGEN, "700.00")
        original = ReservaSiloProceso.objects.values().get(pk=reserva.pk)
        clave = uuid.uuid4()
        respuesta = self._transferir("100.00", clave=clave)
        self.assertEqual(respuesta.status_code, 201, respuesta.data)
        self.assertEqual(saldo_silo(self.origen), Decimal("700.00"))
        self.assertEqual(saldo_silo(self.destino), Decimal("100.00"))
        self.assertEqual(
            ReservaSiloProceso.objects.values().get(pk=reserva.pk), original
        )
        movimientos = MovimientoSilo.objects.filter(operacion_id=clave)
        self.assertEqual(movimientos.count(), 2)
        self.assertEqual(
            set(movimientos.values_list("litros", flat=True)), {Decimal("100.00")}
        )

    def test_transferencia_reintento_no_duplica_ni_acepta_misma_clave_con_otro_payload(
        self,
    ):
        clave = uuid.uuid4()
        primera = self._transferir("100.00", clave=clave)
        self.assertEqual(primera.status_code, 201, primera.data)
        self.origen.estado = Silo.Estado.BLOQUEADO_CALIDAD
        self.origen.save(update_fields=["estado"])
        antes = self._foto()
        repetida = self._transferir("100.00", clave=clave)
        self.assertEqual(repetida.status_code, 201, repetida.data)
        self.assertEqual(self._foto(), antes)
        distinta = self._transferir("99.00", clave=clave)
        self.assertEqual(distinta.status_code, 400, distinta.data)
        self.assertEqual(self._foto(), antes)

    def test_despacho_reintento_conserva_operacion_aunque_ya_no_haya_saldo_libre_ni_calidad(
        self,
    ):
        self._reservar(self.origen, ReservaSiloProceso.Tipo.ORIGEN, "700.00")
        clave, fecha = uuid.uuid4(), timezone.now()
        primera = self._despachar("100.00", clave=clave, fecha_hora=fecha)
        self.assertEqual(primera.status_code, 201, primera.data)
        self.origen.estado = Silo.Estado.BLOQUEADO_CALIDAD
        self.origen.save(update_fields=["estado"])
        antes = self._foto()
        repetida = self._despachar("100.00", clave=clave, fecha_hora=fecha)
        self.assertEqual(repetida.status_code, 201, repetida.data)
        self.assertEqual(repetida.data["id"], primera.data["id"])
        self.assertEqual(self._foto(), antes)
        distinta = self._despachar("99.00", clave=clave, fecha_hora=fecha)
        self.assertEqual(distinta.status_code, 400, distinta.data)
        self.assertEqual(self._foto(), antes)

    def test_transferencia_revalida_analisis_y_rechaza_sin_liberacion_vigente(self):
        self.analisis.estado = AnalisisSilo.Estado.ANULADO
        self.analisis.save(update_fields=["estado"])
        antes = self._foto()
        respuesta = self._transferir()
        self.assertEqual(respuesta.status_code, 400, respuesta.data)
        self.assertEqual(self._foto(), antes)

    def _transferencia_bloqueada_por_cip(self, silo):
        CicloCIP.objects.create(
            silo=silo,
            sucursal=silo.sucursal,
            area=PerfilUsuario.Area.RECEPCION,
            tipo_objetivo=CicloCIP.TipoObjetivo.SILO,
            inicio=timezone.now(),
            estado=CicloCIP.Estado.EN_CURSO,
        )
        antes = self._foto()
        respuesta = self._transferir()
        self.assertEqual(respuesta.status_code, 400, respuesta.data)
        self.assertEqual(self._foto(), antes)

    def test_transferencia_no_retira_de_silo_con_cip_activo(self):
        self._transferencia_bloqueada_por_cip(self.origen)

    def test_transferencia_no_ingresa_a_silo_con_cip_activo(self):
        self._transferencia_bloqueada_por_cip(self.destino)

    def test_fallo_de_atribucion_revierte_ambos_asientos_y_permite_reintentar_la_clave(
        self,
    ):
        clave = uuid.uuid4()
        datos = {
            "silo_origen_id": self.origen.pk,
            "silo_destino_id": self.destino.pk,
            "litros": Decimal("100.00"),
            "operacion_id": clave,
            "usuario": self.usuario,
            "motivo": "Prueba de atomicidad OP03",
        }
        antes = self._foto()
        with patch(
            "recepcion.servicios.heredar_atribuciones",
            side_effect=RuntimeError("Fallo sintético después de crear los asientos"),
        ):
            with self.assertRaisesMessage(RuntimeError, "Fallo sintético"):
                transferir_silo(**datos)
        self.assertEqual(self._foto(), antes)
        self.assertFalse(MovimientoSilo.objects.filter(operacion_id=clave).exists())

        movimientos = transferir_silo(**datos)

        self.assertEqual(len(movimientos), 2)
        self.assertEqual(MovimientoSilo.objects.filter(operacion_id=clave).count(), 2)
        self.assertEqual(saldo_silo(self.origen), Decimal("700.00"))
        self.assertEqual(saldo_silo(self.destino), Decimal("100.00"))
        for movimiento in movimientos:
            self.assertEqual(
                sum(
                    movimiento.atribuciones_recepcion.values_list("litros", flat=True),
                    Decimal("0"),
                ),
                Decimal("100.00"),
            )


class ConcurrenciaReservasRecepcionOP03Tests(TransactionTestCase):
    _reservar = ReservasRecepcionOP03Tests._reservar

    def setUp(self):
        if connection.vendor != "postgresql":
            self.skipTest("Requiere bloqueos PostgreSQL entre conexiones reales.")
        ReservasRecepcionOP03Tests.setUp(self)
        self._reservar(self.origen, ReservaSiloProceso.Tipo.ORIGEN, "700.00")

    def _dos_transferencias_bloqueadas(self, claves):
        resultados, pids = Queue(), Queue()

        def trabajar(clave):
            try:
                with connection.cursor() as cursor:
                    cursor.execute("SET lock_timeout = '10s'")
                    cursor.execute("SET statement_timeout = '15s'")
                    cursor.execute("SELECT pg_backend_pid()")
                    pids.put(cursor.fetchone()[0])
                usuario = get_user_model().objects.get(pk=self.usuario.pk)
                api = APIClient()
                api.force_authenticate(usuario)
                respuesta = api.post(
                    "/api/recepcion/movimientos/transferir/",
                    {
                        "silo_origen": self.origen.pk,
                        "silo_destino": self.destino.pk,
                        "litros": "80.00",
                        "operacion_id": str(clave),
                        "motivo": "Carrera sintética OP03",
                    },
                    format="json",
                )
                resultados.put((respuesta.status_code, respuesta.data))
            except Exception as error:
                resultados.put(("error", repr(error)))
            finally:
                connections.close_all()

        hilos = [
            threading.Thread(target=trabajar, args=(clave,), daemon=True)
            for clave in claves
        ]
        bloqueados = False
        try:
            with transaction.atomic():
                Silo.objects.select_for_update().get(pk=self.origen.pk)
                for hilo in hilos:
                    hilo.start()
                identificadores = [pids.get(timeout=6) for _ in hilos]
                self.assertEqual(len(set(identificadores)), 2)
                limite = time.monotonic() + 3
                while time.monotonic() < limite:
                    with connection.cursor() as cursor:
                        cursor.execute(
                            "SELECT bool_and(cardinality(pg_blocking_pids(pid)) > 0) "
                            "FROM unnest(%s::int[]) AS pid",
                            [identificadores],
                        )
                        bloqueados = bool(cursor.fetchone()[0])
                    if bloqueados:
                        break
                    threading.Event().wait(0.01)
        finally:
            for hilo in hilos:
                if hilo.ident is not None:
                    hilo.join(timeout=18)
            for hilo in hilos:
                self.assertFalse(
                    hilo.is_alive(), "La transferencia dejó un trabajador vivo."
                )
        self.assertTrue(bloqueados, "No se observó competencia real por los bloqueos.")
        return [resultados.get(timeout=1) for _ in hilos]

    def test_dos_retiros_de_80_no_pueden_consumir_los_mismos_100_libres(self):
        resultados = self._dos_transferencias_bloqueadas([uuid.uuid4(), uuid.uuid4()])
        self.assertEqual(
            sorted(estado for estado, _ in resultados), [201, 400], resultados
        )
        self.assertEqual(saldo_silo(self.origen), Decimal("720.00"))
        self.assertEqual(saldo_silo(self.destino), Decimal("80.00"))
        self.assertEqual(
            ReservaSiloProceso.objects.get().cantidad_planificada, Decimal("700.00")
        )
        self.assertEqual(
            MovimientoSilo.objects.filter(
                origen_tipo=MovimientoSilo.OrigenTipo.TRANSFERENCIA,
            ).count(),
            2,
        )

    def test_misma_clave_en_dos_conexiones_crea_solo_un_par_de_asientos(self):
        clave = uuid.uuid4()
        resultados = self._dos_transferencias_bloqueadas([clave, clave])
        self.assertEqual([estado for estado, _ in resultados], [201, 201], resultados)
        self.assertEqual(MovimientoSilo.objects.filter(operacion_id=clave).count(), 2)
        self.assertEqual(saldo_silo(self.origen), Decimal("720.00"))
        self.assertEqual(saldo_silo(self.destino), Decimal("80.00"))
