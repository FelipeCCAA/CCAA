"""Regresiones de atomicidad y fidelidad de escrituras masivas auditadas."""

from datetime import date, datetime
from queue import Queue
from threading import Event, Thread, current_thread
from time import monotonic
from unittest import skipUnless
from unittest.mock import patch

from django.contrib.auth.models import User
from django.db import connection, connections
from django.test import TestCase, TransactionTestCase
from rest_framework.test import APIClient

from inventario.models import (
    DetalleDespacho, ExistenciaProductoTerminado, MovimientoProductoTerminado,
)
from inventario.pruebas_base import EscenarioProductoTerminado
from inventario.servicios import ingresar_pallet, registrar_pallets_producidos
from maestros.models import Equipo, Mandante, Producto
from planificacion.models import BalanceDia, BloquePlan, MovimientoPlan, SemanaPlan
from produccion.models import Lote
from usuarios.models import Empresa, PerfilUsuario, Sucursal

from .models import RegistroAuditoria
from .contexto import Actor, fijar_actor, restaurar_actor
from .registro import (
    actualizar_en_lote_con_auditoria,
    actualizar_queryset_con_auditoria,
    crear_en_lote_con_auditoria,
)


class MasivosCriticosTests(TestCase):
    def setUp(self):
        mandante = Mandante.objects.create(nombre="OP07")
        self.producto = Producto.objects.create(
            nombre="Polvo OP07", familia=Producto.Familia.POLVO, mandante=mandante,
        )
        RegistroAuditoria.objects.all().delete()

    def _lote(self, codigo):
        return Lote(
            codigo_lote=codigo, producto=self.producto, fecha=date(2026, 10, 21),
        )

    def test_ignore_conflicts_no_puede_declarar_altas_ficticias(self):
        creado = Lote.objects.create(
            codigo_lote="OP07-EXISTENTE", producto=self.producto,
            fecha=date(2026, 10, 21),
        )
        RegistroAuditoria.objects.all().delete()

        with self.assertRaises(ValueError):
            crear_en_lote_con_auditoria(
                [self._lote("OP07-EXISTENTE"), self._lote("OP07-NUEVO")],
                ignore_conflicts=True,
            )

        self.assertTrue(Lote.objects.filter(pk=creado.pk).exists())
        self.assertFalse(Lote.objects.filter(codigo_lote="OP07-NUEVO").exists())
        self.assertFalse(RegistroAuditoria.objects.filter(modelo="produccion.Lote").exists())

    def test_fallo_de_auditoria_revierte_todas_las_altas(self):
        with patch("auditoria.registro._escribir", side_effect=RuntimeError("audit fail")):
            with self.assertRaisesMessage(RuntimeError, "audit fail"):
                crear_en_lote_con_auditoria([
                    self._lote("OP07-A"), self._lote("OP07-B"),
                ])

        self.assertFalse(Lote.objects.filter(codigo_lote__startswith="OP07-").exists())
        self.assertFalse(RegistroAuditoria.objects.filter(modelo="produccion.Lote").exists())

    def test_fallo_de_auditoria_revierte_queryset_update(self):
        lote = Lote.objects.create(
            codigo_lote="OP07-UPDATE", producto=self.producto, fecha=date(2026, 10, 21),
        )
        RegistroAuditoria.objects.all().delete()
        with patch("auditoria.registro._escribir", side_effect=RuntimeError("audit fail")):
            with self.assertRaisesMessage(RuntimeError, "audit fail"):
                actualizar_queryset_con_auditoria(
                    Lote.objects.filter(pk=lote.pk), estado=Lote.Estado.PRODUCIDO,
                )

        lote.refresh_from_db()
        self.assertEqual(lote.estado, Lote.Estado.EN_PROCESO)
        self.assertFalse(RegistroAuditoria.objects.filter(modelo="produccion.Lote").exists())

    def test_fallo_de_auditoria_revierte_bulk_update(self):
        lotes = [Lote.objects.create(
            codigo_lote=f"OP07-U-{numero}", producto=self.producto,
            fecha=date(2026, 10, 21),
        ) for numero in (1, 2)]
        RegistroAuditoria.objects.all().delete()
        for lote in lotes:
            lote.estado = Lote.Estado.PRODUCIDO
        with patch("auditoria.registro._escribir", side_effect=RuntimeError("audit fail")):
            with self.assertRaisesMessage(RuntimeError, "audit fail"):
                actualizar_en_lote_con_auditoria(lotes, ["estado"])

        self.assertEqual(
            list(Lote.objects.filter(pk__in=[l.pk for l in lotes]).values_list("estado", flat=True)),
            [Lote.Estado.EN_PROCESO, Lote.Estado.EN_PROCESO],
        )
        self.assertFalse(RegistroAuditoria.objects.filter(modelo="produccion.Lote").exists())


class PalletsYLibroTests(EscenarioProductoTerminado):
    def test_alta_fisica_audita_existencia_y_movimiento_con_ids_reales(self):
        RegistroAuditoria.objects.all().delete()
        testigo = fijar_actor(Actor(usuario=self.usuario, origen="api"))
        try:
            registrar_pallets_producidos([self.pallet], self.usuario)
        finally:
            restaurar_actor(testigo)

        existencia = ExistenciaProductoTerminado.objects.get(pallet=self.pallet)
        movimiento = MovimientoProductoTerminado.objects.get(pallet=self.pallet)
        for modelo, objeto in (
            ("inventario.ExistenciaProductoTerminado", existencia),
            ("inventario.MovimientoProductoTerminado", movimiento),
        ):
            evento = RegistroAuditoria.objects.get(modelo=modelo, objeto_id=str(objeto.pk))
            self.assertEqual(evento.accion, "creacion")
            self.assertEqual(evento.cambios["pallet"], [None, self.pallet.pk])
            self.assertEqual(evento.usuario_id, self.usuario.pk)
            self.assertEqual(evento.origen, "api")
            self.assertIsNotNone(evento.fecha_hora)
        evento_movimiento = RegistroAuditoria.objects.get(
            modelo="inventario.MovimientoProductoTerminado", objeto_id=str(movimiento.pk),
        )
        self.assertEqual(evento_movimiento.cambios["operacion"][1], str(movimiento.operacion))

        RegistroAuditoria.objects.filter(modelo="inventario.MovimientoProductoTerminado").delete()
        actualizar_queryset_con_auditoria(
            MovimientoProductoTerminado.objects.filter(pk=movimiento.pk),
            motivo="Aclaración OP07",
        )
        actualizar_queryset_con_auditoria(
            MovimientoProductoTerminado.objects.filter(pk=movimiento.pk),
            motivo="Aclaración OP07",
        )
        cambios = list(RegistroAuditoria.objects.filter(
            modelo="inventario.MovimientoProductoTerminado", accion="modificacion",
        ))
        movimiento.refresh_from_db()
        self.assertEqual(len(cambios), 1)
        self.assertEqual(cambios[0].cambios["motivo"][1], "Aclaración OP07")
        self.assertNotIn("operacion", cambios[0].cambios)
        self.assertEqual(str(movimiento.operacion), evento_movimiento.cambios["operacion"][1])

    def test_error_auditando_movimiento_revierte_tambien_existencia(self):
        from . import registro

        escribir_real = registro._escribir

        def fallar_en_movimiento(instancia, accion, cambios):
            if isinstance(instancia, MovimientoProductoTerminado):
                raise RuntimeError("audit fail movimiento")
            return escribir_real(instancia, accion, cambios)

        RegistroAuditoria.objects.all().delete()
        with patch("auditoria.registro._escribir", side_effect=fallar_en_movimiento):
            with self.assertRaisesMessage(RuntimeError, "audit fail movimiento"):
                registrar_pallets_producidos([self.pallet], self.usuario)

        self.assertFalse(ExistenciaProductoTerminado.objects.filter(pallet=self.pallet).exists())
        self.assertFalse(MovimientoProductoTerminado.objects.filter(pallet=self.pallet).exists())
        self.assertFalse(RegistroAuditoria.objects.filter(
            modelo__in=[
                "inventario.ExistenciaProductoTerminado", "inventario.MovimientoProductoTerminado",
            ],
        ).exists())

    def test_detalle_despacho_masivo_conserva_pallet_y_actor(self):
        self.dar_permiso("despacho_crear")
        self.liberar()
        ingresar_pallet(self.pallet, self.ubicacion, self.usuario)
        RegistroAuditoria.objects.all().delete()

        respuesta = self.api.post("/api/inventario/despachos/", {
            "cliente": self.cliente.pk, "pallet_ids": [self.pallet.pk],
        }, format="json")

        self.assertEqual(respuesta.status_code, 201, respuesta.data)
        detalle = DetalleDespacho.objects.get(despacho_id=respuesta.data["id"])
        evento = RegistroAuditoria.objects.get(
            modelo="inventario.DetalleDespacho", objeto_id=str(detalle.pk),
        )
        self.assertEqual(evento.cambios["pallet"], [None, self.pallet.pk])
        self.assertEqual(evento.usuario_id, self.usuario.pk)
        self.assertEqual(evento.origen, "api")


class CopiaPlanTests(TestCase):
    def setUp(self):
        empresa = Empresa.objects.create(rut="OP07-PLAN", nombre="Empresa plan")
        planta = Sucursal.objects.create(empresa=empresa, codigo="OP07", nombre="Planta")
        usuario = User.objects.create_user("op07-plan", password="x")
        PerfilUsuario.objects.create(
            usuario=usuario, empresa=empresa, sucursal=planta,
            area=PerfilUsuario.Area.SECADO, alcance=PerfilUsuario.Alcance.SUCURSAL,
        )
        self.api = APIClient()
        self.api.force_authenticate(usuario)
        self.usuario = usuario
        self.semana = SemanaPlan.objects.create(
            sucursal=planta, codigo="OP07-W1", anio=2026,
            fecha_inicio=date(2026, 10, 19),
        )
        equipo = Equipo.objects.create(
            sucursal=planta, codigo="OP07-EQ", nombre="Equipo", tipo=Equipo.Tipo.OTRO,
        )
        BalanceDia.objects.create(semana=self.semana, dia=0, recepcion_ccaa=1000)
        BloquePlan.objects.create(
            semana=self.semana, equipo=equipo, dia=0, hora_inicio=8, hora_fin=10,
            tipo=BloquePlan.Tipo.ESTADO, estado_equipo="A",
        )
        propietario = Mandante.objects.create(empresa=empresa, nombre="Mandante OP07")
        MovimientoPlan.objects.create(
            semana=self.semana, fecha_hora=datetime.fromisoformat("2026-10-19T08:00:00+00:00"),
            propietario=propietario, tipo=MovimientoPlan.Tipo.RECEPCION, cantidad=100,
        )
        RegistroAuditoria.objects.all().delete()

    def test_duplicar_semana_audita_todas_las_filas_copiadas(self):
        respuesta = self.api.post(
            f"/api/planificacion/semanas/{self.semana.pk}/duplicar/",
            {"codigo": "OP07-W2", "anio": 2026, "fecha_inicio": "2026-10-26"},
            format="json",
        )
        self.assertEqual(respuesta.status_code, 201)
        copia = SemanaPlan.objects.get(codigo="OP07-W2")
        for modelo, objeto in (
            ("planificacion.BalanceDia", copia.balances.get()),
            ("planificacion.BloquePlan", copia.bloques.get()),
            ("planificacion.MovimientoPlan", copia.movimientos_plan.get()),
        ):
            evento = RegistroAuditoria.objects.get(modelo=modelo, objeto_id=str(objeto.pk))
            self.assertEqual(evento.accion, "creacion")
            self.assertEqual(evento.cambios["semana"], [None, copia.pk])
            self.assertEqual(evento.usuario_id, self.usuario.pk)
            self.assertEqual(evento.origen, "api")

    def test_fallo_auditando_segunda_fila_revierte_copia_y_primer_evento(self):
        from . import registro

        escribir_real = registro._escribir

        def fallar_en_bloque(instancia, accion, cambios):
            if isinstance(instancia, BloquePlan):
                raise RuntimeError("audit fail bloque")
            return escribir_real(instancia, accion, cambios)

        with patch("auditoria.registro._escribir", side_effect=fallar_en_bloque):
            with self.assertRaisesMessage(RuntimeError, "audit fail bloque"):
                self.api.post(
                    f"/api/planificacion/semanas/{self.semana.pk}/duplicar/",
                    {"codigo": "OP07-W2", "anio": 2026, "fecha_inicio": "2026-10-26"},
                    format="json",
                )

        self.assertFalse(SemanaPlan.objects.filter(codigo="OP07-W2").exists())
        self.assertFalse(RegistroAuditoria.objects.filter(
            modelo__in=["planificacion.BalanceDia", "planificacion.BloquePlan"],
        ).exists())


@skipUnless(connection.vendor == "postgresql", "Requiere bloqueo real PostgreSQL")
class ActualizacionConcurrenteTests(TransactionTestCase):
    def test_dos_actualizaciones_encadenan_antes_despues_y_actor(self):
        from . import registro

        mandante = Mandante.objects.create(nombre="OP07 carrera")
        producto = Producto.objects.create(
            nombre="Polvo carrera", familia=Producto.Familia.POLVO, mandante=mandante,
        )
        lote = Lote.objects.create(
            codigo_lote="OP07-CARRERA", producto=producto, fecha=date(2026, 10, 21),
        )
        primero = User.objects.create_user("op07-primero")
        segundo = User.objects.create_user("op07-segundo")
        RegistroAuditoria.objects.all().delete()

        primer_bloqueo = Event()
        liberar_primero = Event()
        errores = Queue()
        segundo_pid = Queue()
        escribir_real = registro._escribir

        def retener_primera_auditoria(instancia, accion, cambios):
            if isinstance(instancia, Lote) and current_thread().name == "op07-primero":
                primer_bloqueo.set()
                if not liberar_primero.wait(15):
                    raise RuntimeError("No se liberó la primera transacción")
            return escribir_real(instancia, accion, cambios)

        def actualizar(usuario, estado, *, anunciar_pid=False):
            testigo = fijar_actor(Actor(usuario=usuario, origen="sistema"))
            try:
                if anunciar_pid:
                    with connection.cursor() as cursor:
                        cursor.execute("SELECT pg_backend_pid()")
                        segundo_pid.put(cursor.fetchone()[0])
                actualizar_queryset_con_auditoria(
                    Lote.objects.filter(pk=lote.pk), estado=estado,
                )
            except Exception as error:  # los errores de hilos no fallan el test solos
                errores.put(error)
            finally:
                restaurar_actor(testigo)
                connections.close_all()

        hilo_primero = Thread(
            target=actualizar, args=(primero, Lote.Estado.PRODUCIDO), name="op07-primero",
        )
        hilo_segundo = Thread(
            target=actualizar, args=(segundo, Lote.Estado.CERRADO),
            kwargs={"anunciar_pid": True}, name="op07-segundo",
        )
        with patch("auditoria.registro._escribir", side_effect=retener_primera_auditoria):
            hilo_primero.start()
            try:
                self.assertTrue(primer_bloqueo.wait(10))
                hilo_segundo.start()
                pid = segundo_pid.get(timeout=10)
                deadline = monotonic() + 10
                bloqueadores = []
                while monotonic() < deadline:
                    with connection.cursor() as cursor:
                        cursor.execute("SELECT pg_blocking_pids(%s)", [pid])
                        bloqueadores = cursor.fetchone()[0]
                    if bloqueadores or not hilo_segundo.is_alive():
                        break
                    hilo_segundo.join(timeout=0.05)
                self.assertTrue(bloqueadores, "La segunda conexión no esperó el lock de fila")
            finally:
                liberar_primero.set()
                hilo_primero.join(timeout=15)
                if hilo_segundo.ident is not None:
                    hilo_segundo.join(timeout=15)

        self.assertFalse(hilo_primero.is_alive())
        self.assertFalse(hilo_segundo.is_alive())
        self.assertTrue(errores.empty(), list(errores.queue))
        lote.refresh_from_db()
        self.assertEqual(lote.estado, Lote.Estado.CERRADO)
        eventos = list(RegistroAuditoria.objects.filter(
            modelo="produccion.Lote", objeto_id=str(lote.pk), accion="modificacion",
        ).order_by("pk"))
        self.assertEqual(len(eventos), 2)
        self.assertEqual(
            [evento.cambios["estado"] for evento in eventos],
            [
                [Lote.Estado.EN_PROCESO, Lote.Estado.PRODUCIDO],
                [Lote.Estado.PRODUCIDO, Lote.Estado.CERRADO],
            ],
        )
        self.assertEqual([evento.usuario_id for evento in eventos], [primero.pk, segundo.pk])

