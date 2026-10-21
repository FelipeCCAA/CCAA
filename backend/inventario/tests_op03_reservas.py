"""OP-03: traslado por ubicación sin mover reservas ni cambiar el lote."""

from decimal import Decimal
from queue import Queue
import threading
import time
import uuid
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import connection, connections, transaction
from django.test import TestCase, TransactionTestCase
from django.utils import timezone
from rest_framework.test import APIClient

from usuarios.models import PerfilUsuario, Rol

from .models import (
    Bodega,
    Existencia,
    Insumo,
    LoteInventario,
    MovimientoInventario,
    Ubicacion,
)
from .models import (
    DetalleSolicitudMaterial,
    EntregaProduccion,
    ReservaInventario,
    SolicitudMaterial,
)
from .servicios import (
    entregar_reserva,
    entregar_solicitud_material,
    registrar_entrada,
    reservar_fefo,
    trasladar_existencia,
)


class TrasladoConReservasOP03Tests(TestCase):
    def setUp(self):
        self.usuario = get_user_model().objects.create_user("bodega-reservas-op03")
        PerfilUsuario.objects.create(
            usuario=self.usuario,
            rol=Rol.OPERARIO,
            area=PerfilUsuario.Area.BODEGA,
        )
        self.api = APIClient()
        self.api.force_authenticate(self.usuario)
        self.insumo = Insumo.objects.create(
            codigo="OP03-INSUMO",
            nombre="Material ficticio OP03",
            area=PerfilUsuario.Area.BODEGA,
            unidad="un",
            requiere_calidad=True,
        )
        self.bodega = Bodega.objects.create(codigo="OP03-B", nombre="Bodega OP03")
        self.origen = Ubicacion.objects.create(bodega=self.bodega, codigo="OP03-A")
        self.destino = Ubicacion.objects.create(bodega=self.bodega, codigo="OP03-B")
        self.lote = LoteInventario.objects.create(
            insumo=self.insumo,
            codigo="OP03-LOTE-A",
            estado_calidad=LoteInventario.EstadoCalidad.APROBADO,
        )
        registrar_entrada(
            lote=self.lote,
            ubicacion=self.origen,
            cantidad=Decimal("100"),
            usuario=self.usuario,
            documento_tipo="OP03-Entrada",
            documento_id=1,
        )
        reservar_fefo(
            insumo_id=self.insumo.pk,
            cantidad=Decimal("40"),
            usuario=self.usuario,
            documento_tipo="OP03-ReservaAjena",
            documento_id=7,
        )
        self.existencia = Existencia.objects.get(lote=self.lote, ubicacion=self.origen)

    def _foto(self):
        return {
            modelo._meta.label: list(modelo.objects.order_by("pk").values())
            for modelo in (Existencia, MovimientoInventario)
        }

    def _trasladar(self, cantidad="25", *, clave=None):
        return trasladar_existencia(
            existencia_id=self.existencia.pk,
            destino=self.destino,
            cantidad=Decimal(cantidad),
            usuario=self.usuario,
            documento_tipo="OP03-Traslado",
            documento_id=11,
            motivo="Reubicación sintética",
            operacion_id=clave or uuid.uuid4(),
        )

    def _datos_api(self, **extra):
        return {
            "existencia": self.existencia.pk,
            "destino": self.destino.pk,
            "cantidad": "25.000",
            "operacion_id": str(uuid.uuid4()),
            "documento_tipo": "OP03-Traslado",
            "documento_id": 11,
            "motivo": "Reubicación sintética",
            **extra,
        }

    def _post(self, datos):
        return self.api.post(
            "/api/inventario/movimientos/trasladar/",
            datos,
            format="json",
        )

    def test_traslado_del_saldo_libre_conserva_fisico_total_reserva_y_lote(self):
        movimiento = self._trasladar("60")

        self.existencia.refresh_from_db()
        llegada = Existencia.objects.get(lote=self.lote, ubicacion=self.destino)
        self.assertEqual(self.existencia.cantidad_fisica, Decimal("40"))
        self.assertEqual(self.existencia.cantidad_reservada, Decimal("40"))
        self.assertEqual(self.existencia.cantidad_disponible, Decimal("0"))
        self.assertEqual(llegada.cantidad_fisica, Decimal("60"))
        self.assertEqual(llegada.cantidad_reservada, Decimal("0"))
        self.assertEqual(llegada.cantidad_disponible, Decimal("60"))
        self.assertEqual(llegada.lote_id, self.lote.pk)
        self.assertEqual(movimiento.lote_id, self.lote.pk)
        self.assertEqual(movimiento.origen_id, self.origen.pk)
        self.assertEqual(movimiento.destino_id, self.destino.pk)
        self.assertEqual(movimiento.tipo, MovimientoInventario.Tipo.TRASLADO)
        self.assertEqual(
            self.existencia.cantidad_fisica + llegada.cantidad_fisica,
            Decimal("100"),
        )

    def test_no_traslada_cantidad_reservada_ni_deja_efectos_parciales(self):
        antes = self._foto()
        with self.assertRaises(ValidationError):
            self._trasladar("60.001")
        self.assertEqual(self._foto(), antes)
        self.assertFalse(Existencia.objects.filter(ubicacion=self.destino).exists())

    def test_destino_no_mezcla_lotes_del_mismo_insumo(self):
        otro = LoteInventario.objects.create(
            insumo=self.insumo,
            codigo="OP03-LOTE-B",
            estado_calidad=LoteInventario.EstadoCalidad.APROBADO,
        )
        registrar_entrada(
            lote=otro,
            ubicacion=self.destino,
            cantidad=Decimal("20"),
            usuario=self.usuario,
            documento_tipo="OP03-Entrada",
            documento_id=2,
        )
        self._trasladar("25")

        self.assertEqual(
            Existencia.objects.get(lote=otro, ubicacion=self.destino).cantidad_fisica,
            Decimal("20"),
        )
        self.assertEqual(
            Existencia.objects.get(
                lote=self.lote, ubicacion=self.destino
            ).cantidad_fisica,
            Decimal("25"),
        )
        self.assertEqual(Existencia.objects.filter(ubicacion=self.destino).count(), 2)

    def test_revalida_calidad_al_ejecutar_y_no_consumir_reserva(self):
        LoteInventario.objects.filter(pk=self.lote.pk).update(
            estado_calidad=LoteInventario.EstadoCalidad.BLOQUEADO,
        )
        antes = self._foto()
        with self.assertRaises(ValidationError):
            self._trasladar()
        self.assertEqual(self._foto(), antes)

    def test_revalida_destino_inactivo_aunque_el_objeto_entregado_era_activo(self):
        Ubicacion.objects.filter(pk=self.destino.pk).update(activo=False)
        self.assertTrue(self.destino.activo)
        antes = self._foto()
        with self.assertRaises(ValidationError):
            self._trasladar()
        self.assertEqual(self._foto(), antes)

    def test_revalida_bodega_inactiva_sin_descontar_origen(self):
        Bodega.objects.filter(pk=self.bodega.pk).update(activo=False)
        antes = self._foto()
        with self.assertRaises(ValidationError):
            self._trasladar()
        self.assertEqual(self._foto(), antes)

    def test_api_exige_clave_de_operacion_antes_de_mover_stock(self):
        datos = self._datos_api()
        datos.pop("operacion_id")
        antes = self._foto()
        respuesta = self._post(datos)
        self.assertEqual(respuesta.status_code, 400, respuesta.data)
        self.assertEqual(self._foto(), antes)

    def test_api_reintento_equivalente_devuelve_mismo_movimiento_y_saldos(self):
        datos = self._datos_api()
        primera = self._post(datos)
        self.assertEqual(primera.status_code, 201, primera.data)
        antes = self._foto()

        repetida = self._post(datos)

        self.assertEqual(repetida.status_code, 200, repetida.data)
        self.assertEqual(repetida.data["id"], primera.data["id"])
        self.assertEqual(self._foto(), antes)
        self.assertEqual(
            MovimientoInventario.objects.filter(
                operacion_id=datos["operacion_id"],
            ).count(),
            1,
        )

    def test_reintento_confirmado_no_se_revalida_como_una_operacion_nueva(self):
        datos = self._datos_api()
        primera = self._post(datos)
        self.assertEqual(primera.status_code, 201, primera.data)
        LoteInventario.objects.filter(pk=self.lote.pk).update(
            estado_calidad=LoteInventario.EstadoCalidad.BLOQUEADO,
        )
        antes = self._foto()

        repetida = self._post(datos)

        self.assertEqual(repetida.status_code, 200, repetida.data)
        self.assertEqual(repetida.data["id"], primera.data["id"])
        self.assertEqual(self._foto(), antes)

    def test_api_misma_clave_con_carga_distinta_rechaza_sin_mover_stock(self):
        datos = self._datos_api()
        primera = self._post(datos)
        self.assertEqual(primera.status_code, 201, primera.data)
        antes = self._foto()
        for cambios in (
            {"cantidad": "26.000"},
            {"motivo": "Otro acto"},
            {"documento_id": 12},
        ):
            with self.subTest(cambios=cambios):
                respuesta = self._post({**datos, **cambios})
                self.assertEqual(respuesta.status_code, 409, respuesta.data)
                self.assertEqual(self._foto(), antes)


class EntregaReservasPropiasOP03Tests(TestCase):
    def setUp(self):
        # Sólo se reutiliza el montaje, no se heredan sus métodos de prueba.
        TrasladoConReservasOP03Tests.setUp(self)
        self.destino.tipo = Ubicacion.Tipo.PRODUCCION
        self.destino.save(update_fields=["tipo"])
        solicitudes = []
        for codigo, cantidad in (("OP03-PROPIA", "15"), ("OP03-AJENA", "25")):
            solicitud = SolicitudMaterial.objects.create(
                numero=codigo,
                area=PerfilUsuario.Area.SECADO,
                solicitante=self.usuario,
                fecha_requerida=timezone.localdate(),
                estado=SolicitudMaterial.Estado.PREPARADA,
            )
            detalle = DetalleSolicitudMaterial.objects.create(
                solicitud=solicitud,
                insumo=self.insumo,
                cantidad_solicitada=cantidad,
                cantidad_aprobada=cantidad,
            )
            reserva = ReservaInventario.objects.create(
                detalle=detalle,
                existencia=self.existencia,
                cantidad=cantidad,
            )
            solicitudes.append((solicitud, detalle, reserva))
        self.propia, self.detalle_propio, self.reserva_propia = solicitudes[0]
        self.ajena, self.detalle_ajeno, self.reserva_ajena = solicitudes[1]

    def _foto(self):
        return {
            modelo._meta.label: list(modelo.objects.order_by("pk").values())
            for modelo in (
                Existencia,
                MovimientoInventario,
                ReservaInventario,
                DetalleSolicitudMaterial,
                EntregaProduccion,
                SolicitudMaterial,
            )
        }

    def _entregar(self, reserva, cantidad):
        return entregar_reserva(
            reserva_id=reserva.pk,
            existencia_id=self.existencia.pk,
            cantidad=Decimal(cantidad),
            destino=self.destino,
            usuario=self.usuario,
            documento_tipo="inventario.SolicitudMaterial",
            documento_id=self.propia.pk,
        )

    def test_entrega_rechaza_destino_inactivo_y_conserva_reserva_y_libro(self):
        Ubicacion.objects.filter(pk=self.destino.pk).update(activo=False)
        self.assertTrue(self.destino.activo)
        antes = self._foto()

        with self.assertRaises(ValidationError):
            self._entregar(self.reserva_propia, "5")

        self.assertEqual(self._foto(), antes)

    def test_entrega_rechaza_bodega_destino_inactiva_sin_modificar_reserva(self):
        otra_bodega = Bodega.objects.create(
            codigo="OP03-B-DESTINO-ENTREGA",
            nombre="Bodega destino de entrega OP03",
            sucursal=self.bodega.sucursal,
        )
        self.destino.bodega = otra_bodega
        self.destino.save(update_fields=["bodega"])
        Bodega.objects.filter(pk=otra_bodega.pk).update(activo=False)
        self.bodega.refresh_from_db()
        self.assertTrue(self.bodega.activo, "Sólo se desactiva la bodega del destino.")
        antes = self._foto()

        with self.assertRaises(ValidationError):
            self._entregar(self.reserva_propia, "5")

        self.assertEqual(self._foto(), antes)

    def test_id_de_reserva_ajena_no_autoriza_entregar_por_solicitud_propia(self):
        antes = self._foto()
        with self.assertRaises(ValidationError):
            self._entregar(self.reserva_ajena, "5")
        self.assertEqual(self._foto(), antes)

    def test_no_entrega_mas_que_su_reserva_aunque_exista_saldo_reservado_ajeno(self):
        antes = self._foto()
        with self.assertRaises(ValidationError):
            self._entregar(self.reserva_propia, "20")
        self.assertEqual(self._foto(), antes)

    def test_entrega_parcial_descuenta_solo_reserva_propia_y_conserva_ajena(self):
        ajena = ReservaInventario.objects.values().get(pk=self.reserva_ajena.pk)

        movimiento = self._entregar(self.reserva_propia, "5")

        self.existencia.refresh_from_db()
        self.reserva_propia.refresh_from_db()
        self.assertEqual(self.existencia.cantidad_fisica, Decimal("95"))
        self.assertEqual(self.existencia.cantidad_reservada, Decimal("35"))
        self.assertEqual(self.existencia.cantidad_disponible, Decimal("60"))
        self.assertEqual(self.reserva_propia.cantidad, Decimal("10"))
        self.assertTrue(self.reserva_propia.activa)
        self.assertEqual(
            ReservaInventario.objects.values().get(pk=self.reserva_ajena.pk), ajena
        )
        self.assertEqual(movimiento.tipo, MovimientoInventario.Tipo.ENTREGA)
        self.assertEqual(movimiento.documento_id, self.propia.pk)
        llegada = Existencia.objects.get(lote=self.lote, ubicacion=self.destino)
        self.assertEqual(llegada.cantidad_fisica, Decimal("5"))
        self.assertEqual(llegada.cantidad_reservada, Decimal("0"))
        self.assertEqual(movimiento.lote_id, llegada.lote_id)

    def test_entrega_mrq_legitima_conserva_documento_y_reserva_ajena(self):
        ajena = ReservaInventario.objects.values().get(pk=self.reserva_ajena.pk)

        entrega = entregar_solicitud_material(
            solicitud=self.propia,
            destino=self.destino,
            entrega_por=self.usuario,
            recibe_por=self.usuario,
            selecciones=[{"reserva": self.reserva_propia.pk, "cantidad": "5"}],
        )

        self.assertEqual(entrega.solicitud_id, self.propia.pk)
        self.propia.refresh_from_db()
        self.detalle_propio.refresh_from_db()
        self.reserva_propia.refresh_from_db()
        self.assertEqual(self.propia.estado, SolicitudMaterial.Estado.PARCIAL)
        self.assertEqual(self.detalle_propio.cantidad_entregada, Decimal("5"))
        self.assertEqual(self.reserva_propia.cantidad, Decimal("10"))
        self.assertEqual(
            ReservaInventario.objects.values().get(pk=self.reserva_ajena.pk), ajena
        )
        self.assertTrue(
            MovimientoInventario.objects.filter(
                tipo=MovimientoInventario.Tipo.ENTREGA,
                documento_tipo="inventario.EntregaProduccion",
                documento_id=entrega.pk,
                cantidad=Decimal("5"),
                lote=self.lote,
            ).exists()
        )


class ConcurrenciaDestinoEntregaOP03Tests(TransactionTestCase):
    def setUp(self):
        if connection.vendor != "postgresql":
            self.skipTest("Requiere bloqueos reales entre conexiones PostgreSQL.")
        EntregaReservasPropiasOP03Tests.setUp(self)

    def test_desactivar_destino_espera_desde_validacion_hasta_commit_de_entrega(self):
        validada = threading.Event()
        continuar_escritura = threading.Event()
        servicio_terminado = threading.Event()
        permitir_commit = threading.Event()
        desactivacion_terminada = threading.Event()
        resultados, pids_entrega, pids_desactivacion = Queue(), Queue(), Queue()
        guardar_real = Existencia.save
        origen_id, destino_id = self.existencia.pk, self.destino.pk

        def guardar_con_barrera(instancia, *args, **kwargs):
            if (
                instancia.pk == origen_id
                and "cantidad_fisica" in (kwargs.get("update_fields") or ())
                and not validada.is_set()
            ):
                # La validación ya leyó destino/bodega; todavía no se escribió
                # el primer descuento. Se conserva el save real y su control.
                validada.set()
                if not continuar_escritura.wait(timeout=10):
                    raise RuntimeError(
                        "No se autorizó continuar la escritura sintética."
                    )
            return guardar_real(instancia, *args, **kwargs)

        def preparar_conexion(pids):
            with connection.cursor() as cursor:
                cursor.execute("SET lock_timeout = '12s'")
                cursor.execute("SET statement_timeout = '15s'")
                cursor.execute("SELECT pg_backend_pid()")
                pids.put(cursor.fetchone()[0])

        def entregar():
            try:
                preparar_conexion(pids_entrega)
                with transaction.atomic():
                    movimiento = entregar_reserva(
                        reserva_id=self.reserva_propia.pk,
                        existencia_id=origen_id,
                        cantidad=Decimal("5"),
                        destino=Ubicacion.objects.get(pk=destino_id),
                        usuario=get_user_model().objects.get(pk=self.usuario.pk),
                        documento_tipo="inventario.SolicitudMaterial",
                        documento_id=self.propia.pk,
                    )
                    servicio_terminado.set()
                    if not permitir_commit.wait(timeout=10):
                        raise RuntimeError("No se autorizó el commit sintético.")
                resultados.put(("entrega", movimiento.pk))
            except Exception as error:
                resultados.put(("error_entrega", repr(error)))
            finally:
                connections.close_all()

        def desactivar():
            try:
                preparar_conexion(pids_desactivacion)
                actualizadas = Ubicacion.objects.filter(pk=destino_id).update(
                    activo=False
                )
                resultados.put(("desactivacion", actualizadas))
            except Exception as error:
                resultados.put(("error_desactivacion", repr(error)))
            finally:
                desactivacion_terminada.set()
                connections.close_all()

        def espera_observada(pid_actualizacion, pid_entrega):
            limite = time.monotonic() + 3
            while time.monotonic() < limite:
                with connection.cursor() as cursor:
                    cursor.execute(
                        "SELECT %s = ANY(pg_blocking_pids(%s))",
                        [pid_entrega, pid_actualizacion],
                    )
                    if cursor.fetchone()[0]:
                        return True
                if desactivacion_terminada.is_set():
                    return False
                threading.Event().wait(0.01)
            return False

        hilo_entrega = threading.Thread(target=entregar, daemon=True)
        hilo_desactivacion = threading.Thread(target=desactivar, daemon=True)
        bloqueo_tras_validar = bloqueo_hasta_commit = False
        with patch.object(Existencia, "save", guardar_con_barrera):
            try:
                hilo_entrega.start()
                self.assertTrue(
                    validada.wait(timeout=6), "No se alcanzó la barrera tras validar."
                )
                pid_entrega = pids_entrega.get(timeout=1)
                hilo_desactivacion.start()
                pid_actualizacion = pids_desactivacion.get(timeout=6)
                self.assertNotEqual(pid_entrega, pid_actualizacion)
                bloqueo_tras_validar = espera_observada(pid_actualizacion, pid_entrega)
                continuar_escritura.set()
                self.assertTrue(
                    servicio_terminado.wait(timeout=6),
                    "La entrega no terminó su servicio.",
                )
                bloqueo_hasta_commit = espera_observada(pid_actualizacion, pid_entrega)
                # El servicio terminó, pero el commit del llamador sigue
                # pendiente: un tercero aún ve los saldos anteriores.
                self.assertEqual(
                    Existencia.objects.get(pk=origen_id).cantidad_fisica,
                    Decimal("100"),
                )
            finally:
                continuar_escritura.set()
                permitir_commit.set()
                for hilo in (hilo_entrega, hilo_desactivacion):
                    if hilo.ident is not None:
                        hilo.join(timeout=18)
                for hilo in (hilo_entrega, hilo_desactivacion):
                    self.assertFalse(
                        hilo.is_alive(), "Quedó un trabajador de entrega activo."
                    )

        entregados = [resultados.get(timeout=1) for _ in range(2)]
        self.assertEqual(
            {tipo for tipo, _ in entregados}, {"entrega", "desactivacion"}, entregados
        )
        self.assertTrue(
            bloqueo_tras_validar,
            "La desactivación no esperó después de validar el destino.",
        )
        self.assertTrue(
            bloqueo_hasta_commit, "La desactivación pasó antes del commit externo."
        )
        self.destino.refresh_from_db()
        self.existencia.refresh_from_db()
        self.reserva_propia.refresh_from_db()
        self.reserva_ajena.refresh_from_db()
        self.assertFalse(self.destino.activo)
        self.assertEqual(self.existencia.cantidad_fisica, Decimal("95"))
        self.assertEqual(self.existencia.cantidad_reservada, Decimal("35"))
        self.assertEqual(self.reserva_propia.cantidad, Decimal("10"))
        self.assertEqual(self.reserva_ajena.cantidad, Decimal("25"))
        self.assertTrue(self.reserva_ajena.activa)
        self.assertEqual(
            MovimientoInventario.objects.filter(
                tipo=MovimientoInventario.Tipo.ENTREGA,
                cantidad=Decimal("5"),
            ).count(),
            1,
        )
        self.assertEqual(
            Existencia.objects.get(
                lote=self.lote, ubicacion=self.destino
            ).cantidad_fisica,
            Decimal("5"),
        )
