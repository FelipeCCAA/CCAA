"""Actos OP-02 por API y carreras controladas sobre conexiones PostgreSQL."""

from decimal import Decimal
from queue import Queue
import threading
import time
import uuid
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import connection, connections, transaction
from django.test import TransactionTestCase
from django.utils import timezone
from rest_framework.test import APIClient

from calidad.models import LiberacionProceso
from calidad.vigencia import exigir_liberacion_salida_vigente
from inventario.pruebas_firmas import firmar_salida_de_prueba
from produccion.dominio import puede_abrir_lote_desde
from procesos.models import (
    EjecucionProceso,
    EntradaProceso,
    ReservaSiloProceso,
    SalidaProceso,
)
from recepcion.models import AtribucionRecepcion, MovimientoSilo
from usuarios.models import PerfilUsuario, Rol

from .balance import cantidad_operativa_salida
from .models import ActoValeEstandarizacion, ValeEstandarizacion
from .tests_vale import BaseVale


class EscenarioActosOP02:
    def _clientes(self):
        PerfilUsuario.objects.update_or_create(
            usuario=self.usuario,
            defaults={"rol": Rol.PRODUCCION, "area": PerfilUsuario.Area.CONDENSACION},
        )
        self.calidad = get_user_model().objects.create_user("calidad-actos-op02")
        PerfilUsuario.objects.create(
            usuario=self.calidad,
            rol=Rol.CALIDAD,
            area=PerfilUsuario.Area.CALIDAD,
        )
        self.recepcion = get_user_model().objects.create_user("recepcion-actos-op02")
        PerfilUsuario.objects.create(
            usuario=self.recepcion,
            rol=Rol.RECEPCION,
            area=PerfilUsuario.Area.RECEPCION,
        )
        self.cliente = self._cliente(self.usuario)
        self.cliente_calidad = self._cliente(self.calidad)
        self.cliente_recepcion = self._cliente(self.recepcion)

    @staticmethod
    def _cliente(usuario):
        cliente = APIClient()
        cliente.force_authenticate(usuario)
        return cliente

    def _preparado(self):
        vale = self.crear_vale()
        self.abastecer_origenes()
        self.analizar_origenes()
        return vale

    def _transferido(self):
        vale = self._preparado()
        respuesta = self._accion(vale, "transferir")
        self.assertEqual(respuesta.status_code, 200, respuesta.data)
        vale.refresh_from_db()
        return vale

    def _accion(self, vale, accion, datos=None, cliente=None):
        return (cliente or self.cliente).post(
            f"/api/estandarizacion/vales/{vale.pk}/{accion}/",
            datos or {},
            format="json",
        )

    def _datos_acto(self, tipo="adicion", **extra):
        datos = {
            "clave": str(uuid.uuid4()),
            "tipo": tipo,
            "motivo": "Corrección autorizada de la mezcla",
        }
        if tipo in {"adicion", "retiro"}:
            datos.update(litros="25.25", silo_contraparte=self.silo_entera.pk)
        elif tipo == "medicion":
            datos["volumen_medido"] = "10000.00"
        else:
            datos["rectificacion"] = {"litros_entera": "3999.00"}
        return {**datos, **extra}

    def _foto(self, vale):
        modelos = (
            MovimientoSilo,
            AtribucionRecepcion,
            EjecucionProceso,
            EntradaProceso,
            SalidaProceso,
            ActoValeEstandarizacion,
        )
        return {
            "vale": ValeEstandarizacion.objects.values().get(pk=vale.pk),
            **{
                modelo._meta.label: list(modelo.objects.order_by("pk").values())
                for modelo in modelos
            },
        }

    def _foto_original(self, vale):
        ejecucion = EjecucionProceso.objects.get(vale=vale)
        return {
            "movimientos": list(
                MovimientoSilo.objects.filter(
                    origen_tipo=MovimientoSilo.OrigenTipo.ESTANDARIZACION,
                    origen_id=vale.pk,
                )
                .order_by("pk")
                .values()
            ),
            "entradas": list(ejecucion.entradas.order_by("pk").values()),
            "salidas": list(ejecucion.salidas.order_by("pk").values()),
        }

    def _original_intacto(self, vale, original):
        ids = [fila["id"] for fila in original["movimientos"]]
        self.assertEqual(
            list(MovimientoSilo.objects.filter(pk__in=ids).order_by("pk").values()),
            original["movimientos"],
        )
        ejecucion = EjecucionProceso.objects.get(vale=vale)
        self.assertEqual(
            list(ejecucion.entradas.order_by("pk").values()), original["entradas"]
        )
        self.assertEqual(
            list(ejecucion.salidas.order_by("pk").values()), original["salidas"]
        )

    def _otra_ejecucion(self):
        primera = EjecucionProceso.objects.first()
        return EjecucionProceso.objects.create(
            codigo="EJ-OTRA-OP02",
            etapa=primera.etapa,
            sucursal=self.silo_destino.sucursal,
            responsable=self.usuario,
            estado=EjecucionProceso.Estado.EJECUCION,
            inicio=timezone.now(),
        )


class ActosOP02Tests(EscenarioActosOP02, BaseVale):
    def setUp(self):
        self._clientes()

    def test_recepcion_registra_faltante_y_muestreo_no_evade_retencion(self):
        vale = self._transferido()
        original = self._foto_original(vale)
        datos = self._datos_acto("medicion", volumen_medido="9900.00")

        medida = self._accion(vale, "actos", datos, self.cliente_recepcion)

        self.assertEqual(medida.status_code, 200, medida.data)
        self.assertEqual(medida.data["balance"]["volumen_ejecutado"], "10000.00")
        self.assertEqual(medida.data["balance"]["volumen_medido"], "9900.00")
        self.assertEqual(medida.data["balance"]["diferencia"], "-100.00")
        self.assertTrue(medida.data["balance"]["pendiente"])
        self.assertEqual(
            ActoValeEstandarizacion.objects.get(clave=datos["clave"]).usuario_id,
            self.recepcion.pk,
        )
        agitada = self._accion(vale, "agitar")
        self.assertEqual(agitada.status_code, 200, agitada.data)
        muestra = self._accion(
            vale, "muestrear", {"grasa": "1.79", "sng": "8.90"},
        )
        self.assertEqual(muestra.status_code, 200, muestra.data)
        self.assertTrue(muestra.data["evaluacion"]["cumple"])
        self.assertTrue(muestra.data["balance"]["pendiente"])

        decision = self._accion(vale, "decidir", cliente=self.cliente_calidad)

        self.assertEqual(decision.status_code, 409, decision.data)
        vale.refresh_from_db()
        self.assertEqual(vale.estado, vale.Estado.MUESTREADO)
        self.assertEqual(
            EjecucionProceso.objects.get(vale=vale).estado,
            EjecucionProceso.Estado.EJECUCION,
        )
        self._original_intacto(vale, original)

    def test_adicion_invalida_firma_salida_y_actualiza_disponible_sin_reescribir_foto(self):
        vale = self._transferido()
        self.assertEqual(self._accion(vale, "agitar").status_code, 200)
        self.assertEqual(self._accion(
            vale, "muestrear", {"grasa": "1.79", "sng": "8.90"},
        ).status_code, 200)
        self.assertEqual(self._accion(
            vale, "decidir", cliente=self.cliente_calidad,
        ).status_code, 200)
        salida = SalidaProceso.objects.get(ejecucion__vale=vale)
        # El fixture crea muestra y llama registrar_firma_salida bajo la
        # transacción y el bloqueo de catálogo reales de Calidad.
        liberacion = firmar_salida_de_prueba(salida, self.calidad)
        firma = liberacion.firma_id
        self.assertIsNotNone(firma)
        self.assertEqual(liberacion.version_evidencia, 0)
        self.assertEqual(liberacion.version_firmada, 0)
        self.assertTrue(liberacion.firma_vigente)
        with transaction.atomic():
            self.assertEqual(exigir_liberacion_salida_vigente(salida.pk), str(firma))
        original = self._foto_original(vale)

        corregida = self._accion(vale, "actos", self._datos_acto())

        self.assertEqual(corregida.status_code, 200, corregida.data)
        self.assertEqual(corregida.data["balance"]["volumen_ejecutado"], "10025.25")
        liberacion.refresh_from_db()
        self.assertEqual(liberacion.estado, LiberacionProceso.Estado.PENDIENTE)
        self.assertEqual(liberacion.version_evidencia, 1)
        self.assertEqual(liberacion.version_firmada, 0)
        self.assertEqual(liberacion.firma_id, firma)
        self.assertFalse(liberacion.firma_vigente)
        salida.refresh_from_db()
        self.assertEqual(salida.cantidad, Decimal("10000.00"))
        self.assertEqual(cantidad_operativa_salida(salida), Decimal("10025.25"))
        self._original_intacto(vale, original)

        self.assertEqual(self._accion(vale, "reagitar").status_code, 200)
        self.assertEqual(self._accion(
            vale, "muestrear", {"grasa": "1.79", "sng": "8.90"},
        ).status_code, 200)
        nuevamente_liberada = self._accion(vale, "decidir", cliente=self.cliente_calidad)
        self.assertEqual(nuevamente_liberada.status_code, 200, nuevamente_liberada.data)
        vale.refresh_from_db()
        disponible = puede_abrir_lote_desde(vale, Decimal("10025.25"))
        self.assertTrue(disponible.permitido, disponible.bloqueos)
        self.assertEqual(disponible.litros_disponibles, Decimal("10025.25"))
        self.assertFalse(puede_abrir_lote_desde(vale, Decimal("10025.26")).permitido)
        liberacion.refresh_from_db()
        self.assertEqual(liberacion.estado, LiberacionProceso.Estado.PENDIENTE)
        self.assertEqual(liberacion.firma_id, firma)
        self.assertEqual(liberacion.version_evidencia, 1)
        self.assertEqual(liberacion.version_firmada, 0)
        self.assertFalse(liberacion.firma_vigente)
        with transaction.atomic():
            with self.assertRaises(ValidationError):
                exigir_liberacion_salida_vigente(salida.pk)
        self._original_intacto(vale, original)

    def test_diferencia_medida_retiene_hasta_otra_medicion_sin_maquillar_libro(self):
        vale = self._transferido()
        self.assertEqual(self._accion(vale, "agitar").status_code, 200)
        self.assertEqual(
            self._accion(
                vale,
                "muestrear",
                {"grasa": "1.79", "sng": "8.90"},
            ).status_code,
            200,
        )
        original = self._foto_original(vale)

        medida = self._accion(
            vale,
            "actos",
            self._datos_acto("medicion", volumen_medido="10100.00"),
            self.cliente_calidad,
        )

        self.assertEqual(medida.status_code, 200, medida.data)
        self.assertEqual(medida.data["balance"]["volumen_ejecutado"], "10000.00")
        self.assertEqual(medida.data["balance"]["volumen_medido"], "10100.00")
        self.assertEqual(medida.data["balance"]["diferencia"], "100.00")
        self.assertTrue(medida.data["balance"]["pendiente"])
        rechazo = self._accion(vale, "decidir", cliente=self.cliente_calidad)
        self.assertEqual(rechazo.status_code, 409, rechazo.data)
        vale.refresh_from_db()
        self.assertEqual(vale.estado, vale.Estado.MUESTREADO)
        self.assertEqual(
            EjecucionProceso.objects.get(vale=vale).estado,
            EjecucionProceso.Estado.EJECUCION,
        )

        conciliada = self._accion(
            vale,
            "actos",
            self._datos_acto("medicion"),
            self.cliente_calidad,
        )
        self.assertEqual(conciliada.status_code, 200, conciliada.data)
        self.assertEqual(conciliada.data["balance"]["diferencia"], "0.00")
        self.assertFalse(conciliada.data["balance"]["pendiente"])
        self.assertEqual(len(conciliada.data["actos"]), 2)
        liberada = self._accion(vale, "decidir", cliente=self.cliente_calidad)
        self.assertEqual(liberada.status_code, 200, liberada.data)
        self.assertEqual(liberada.data["estado"], vale.Estado.LIBERADO)
        self._original_intacto(vale, original)

    def test_rectificacion_documental_conserva_original_y_registra_antes_despues(self):
        vale = self._transferido()
        original = self._foto(vale)
        datos = self._datos_acto("documental")

        respuesta = self._accion(vale, "actos", datos)

        self.assertEqual(respuesta.status_code, 200, respuesta.data)
        acto = ActoValeEstandarizacion.objects.get(clave=datos["clave"])
        self.assertEqual(acto.rectificacion["litros_entera"], ["4000.00", "3999.00"])
        self.assertEqual(acto.usuario_id, self.usuario.pk)
        self.assertEqual(acto.motivo, datos["motivo"])
        self.assertIsNotNone(acto.creado_en)
        actual = self._foto(vale)
        for clave in original:
            if clave != ActoValeEstandarizacion._meta.label:
                self.assertEqual(actual[clave], original[clave])

    def test_acto_persistido_no_se_edita_ni_elimina(self):
        vale = self._transferido()
        datos = self._datos_acto("documental")
        self.assertEqual(self._accion(vale, "actos", datos).status_code, 200)
        acto = ActoValeEstandarizacion.objects.get(clave=datos["clave"])
        original = self._foto(vale)
        acto.motivo = "Intento de sobrescritura"
        with self.assertRaises(ValidationError):
            acto.save()
        with self.assertRaises(ValidationError):
            acto.delete()
        self.assertEqual(self._foto(vale), original)

    def test_motivo_insuficiente_no_crea_acto_ni_movimientos(self):
        vale = self._transferido()
        original = self._foto(vale)
        for motivo in ("", "    ", "abcd"):
            with self.subTest(motivo=motivo):
                respuesta = self._accion(vale, "actos", self._datos_acto(motivo=motivo))
                self.assertEqual(respuesta.status_code, 400, respuesta.data)
                self.assertEqual(self._foto(vale), original)

    def test_solo_produccion_autoriza_adicion_retiro_y_rectificacion(self):
        vale = self._transferido()
        original = self._foto(vale)
        for tipo in ("adicion", "retiro", "documental"):
            for nombre, cliente in (
                ("Calidad", self.cliente_calidad),
                ("Recepcion", self.cliente_recepcion),
            ):
                with self.subTest(tipo=tipo, actor=nombre):
                    respuesta = self._accion(
                        vale, "actos", self._datos_acto(tipo), cliente
                    )
                    self.assertEqual(respuesta.status_code, 403, respuesta.data)
                    self.assertEqual(self._foto(vale), original)

    def test_adicion_retiro_dejan_dos_movimientos_nuevos_y_atribuciones(self):
        vale = self._transferido()
        original = self._foto_original(vale)
        for tipo, volumen in (("adicion", "10025.25"), ("retiro", "10000.00")):
            with self.subTest(tipo=tipo):
                datos = self._datos_acto(tipo)
                respuesta = self._accion(vale, "actos", datos)
                self.assertEqual(respuesta.status_code, 200, respuesta.data)
                self.assertEqual(
                    respuesta.data["balance"]["volumen_ejecutado"], volumen
                )
                movimientos = MovimientoSilo.objects.filter(operacion_id=datos["clave"])
                self.assertEqual(movimientos.count(), 2)
                self.assertEqual(
                    set(movimientos.values_list("tipo", flat=True)),
                    {MovimientoSilo.Tipo.INGRESO, MovimientoSilo.Tipo.SALIDA},
                )
                for movimiento in movimientos:
                    self.assertEqual(movimiento.litros, Decimal("25.25"))
                    self.assertEqual(movimiento.origen_id, vale.pk)
                    self.assertEqual(
                        sum(
                            movimiento.atribuciones_recepcion.values_list(
                                "litros", flat=True
                            ),
                            Decimal("0"),
                        ),
                        Decimal("25.25"),
                    )
                self._original_intacto(vale, original)
        vale.refresh_from_db()
        self.assertEqual(vale.volumen, Decimal("10000.00"))
        self.assertEqual(vale.litros_entera, Decimal("4000.00"))

    def test_repetir_clave_no_duplica_y_cambiar_solicitud_con_misma_clave_conflicta(
        self,
    ):
        vale = self._transferido()
        datos = self._datos_acto()
        self.assertEqual(self._accion(vale, "actos", datos).status_code, 200)
        original = self._foto(vale)

        repetida = self._accion(vale, "actos", datos)
        self.assertEqual(repetida.status_code, 200, repetida.data)
        self.assertEqual(self._foto(vale), original)
        distinta = self._accion(vale, "actos", {**datos, "litros": "25.26"})
        self.assertEqual(distinta.status_code, 409, distinta.data)
        self.assertEqual(self._foto(vale), original)

    def test_cuatro_decimales_se_rechazan_sin_redondear(self):
        vale = self._transferido()
        original = self._foto(vale)
        for datos in (
            self._datos_acto(litros="25.2501"),
            self._datos_acto("medicion", volumen_medido="10000.0001"),
        ):
            with self.subTest(tipo=datos["tipo"]):
                respuesta = self._accion(vale, "actos", datos)
                self.assertEqual(respuesta.status_code, 400, respuesta.data)
                self.assertEqual(self._foto(vale), original)

    def test_adicion_exige_nuevo_ciclo_sin_reabrir_ejecucion_historica(self):
        vale = self._transferido()
        self.assertEqual(self._accion(vale, "agitar").status_code, 200)
        self.assertEqual(
            self._accion(
                vale, "muestrear", {"grasa": "1.79", "sng": "8.90"}
            ).status_code,
            200,
        )
        self.assertEqual(
            self._accion(vale, "decidir", cliente=self.cliente_calidad).status_code, 200
        )
        original = self._foto_original(vale)

        ejecucion_inicial = EjecucionProceso.objects.values().get(vale=vale)

        corregida = self._accion(vale, "actos", self._datos_acto())
        self.assertEqual(corregida.status_code, 200, corregida.data)
        self.assertEqual(corregida.data["estado"], vale.Estado.CORRIGIENDO)
        vale.refresh_from_db()
        self.assertIsNone(vale.grasa_real)
        self.assertIsNone(vale.sng_real)
        self.assertIsNone(vale.muestreado_en)
        self.assertEqual(EjecucionProceso.objects.values().get(vale=vale), ejecucion_inicial)
        self.assertEqual(
            self._accion(vale, "decidir", cliente=self.cliente_calidad).status_code, 409
        )
        self.assertEqual(self._accion(vale, "reagitar").status_code, 200)
        self.assertEqual(
            self._accion(
                vale, "muestrear", {"grasa": "1.79", "sng": "8.90"}
            ).status_code,
            200,
        )
        liberada = self._accion(vale, "decidir", cliente=self.cliente_calidad)
        self.assertEqual(liberada.status_code, 200, liberada.data)
        self.assertEqual(liberada.data["estado"], vale.Estado.LIBERADO)
        self.assertEqual(
            EjecucionProceso.objects.get(vale=vale).estado,
            EjecucionProceso.Estado.CERRADA,
        )
        self.assertEqual(EjecucionProceso.objects.values().get(vale=vale), ejecucion_inicial)
        self._original_intacto(vale, original)

    def test_consumo_posterior_bloquea_correccion_fisica(self):
        vale = self._transferido()
        MovimientoSilo.objects.create(
            silo=self.silo_destino,
            tipo=MovimientoSilo.Tipo.SALIDA,
            litros="10.00",
            fecha_hora=timezone.now(),
            origen_tipo=MovimientoSilo.OrigenTipo.AJUSTE,
            motivo="Consumo posterior ajeno a la corrección",
        )
        self._rechazar_fisicos(vale)

    def test_entrada_de_otro_proceso_bloquea_correccion_fisica(self):
        vale = self._transferido()
        EntradaProceso.objects.create(
            ejecucion=self._otra_ejecucion(),
            silo=self.silo_destino,
            cantidad="10.00",
            unidad="L",
            tipo=EntradaProceso.Tipo.PRINCIPAL,
        )
        self._rechazar_fisicos(vale)

    def _rechazar_fisicos(self, vale):
        original = self._foto(vale)
        for tipo in ("adicion", "retiro"):
            with self.subTest(tipo=tipo):
                respuesta = self._accion(vale, "actos", self._datos_acto(tipo))
                self.assertEqual(respuesta.status_code, 409, respuesta.data)
                self.assertEqual(self._foto(vale), original)

    def test_capacidad_destino_insuficiente_bloquea_adicion(self):
        vale = self._transferido()
        self.silo_destino.capacidad_l = Decimal("10000.00")
        self.silo_destino.save(update_fields=["capacidad_l"])
        original = self._foto(vale)
        respuesta = self._accion(vale, "actos", self._datos_acto())
        self.assertEqual(respuesta.status_code, 409, respuesta.data)
        self.assertEqual(self._foto(vale), original)

    def test_saldo_insuficiente_bloquea_adicion(self):
        vale = self._transferido()
        original = self._foto(vale)
        respuesta = self._accion(vale, "actos", self._datos_acto(litros="16000.01"))
        self.assertEqual(respuesta.status_code, 409, respuesta.data)
        self.assertEqual(self._foto(vale), original)

    def test_reserva_de_origen_bloquea_consumir_litros_comprometidos(self):
        vale = self._transferido()
        ReservaSiloProceso.objects.create(
            ejecucion=self._otra_ejecucion(),
            silo=self.silo_entera,
            tipo=ReservaSiloProceso.Tipo.ORIGEN,
            cantidad_planificada="15999.00",
            producto=self.producto,
        )
        original = self._foto(vale)
        respuesta = self._accion(vale, "actos", self._datos_acto())
        self.assertEqual(respuesta.status_code, 409, respuesta.data)
        self.assertEqual(self._foto(vale), original)

    def test_reserva_del_destino_bloquea_adicion(self):
        vale = self._transferido()
        ReservaSiloProceso.objects.create(
            ejecucion=self._otra_ejecucion(),
            silo=self.silo_destino,
            tipo=ReservaSiloProceso.Tipo.DESTINO,
            cantidad_planificada="100.00",
            producto=self.producto,
        )
        original = self._foto(vale)
        respuesta = self._accion(vale, "actos", self._datos_acto())
        self.assertEqual(respuesta.status_code, 409, respuesta.data)
        self.assertEqual(self._foto(vale), original)

    def test_fallo_al_heredar_atribuciones_revierte_todo_el_acto(self):
        vale = self._transferido()
        original = self._foto(vale)
        with patch(
            "estandarizacion.actos.heredar_atribuciones",
            side_effect=RuntimeError("Fallo sintético de atribuciones"),
        ):
            with self.assertRaisesMessage(RuntimeError, "Fallo sintético"):
                self._accion(vale, "actos", self._datos_acto())
        self.assertEqual(self._foto(vale), original)


class ConcurrenciaOP02Tests(EscenarioActosOP02, TransactionTestCase):
    crear_vale = BaseVale.crear_vale
    abastecer_origenes = BaseVale.abastecer_origenes
    analizar_origenes = BaseVale.analizar_origenes

    def setUp(self):
        if connection.vendor != "postgresql":
            self.skipTest("Requiere conexiones PostgreSQL y bloqueos reales.")
        BaseVale.setUpTestData.__func__(type(self))
        self._clientes()

    def _trabajador(self, ejecutar, resultados, *, barrera=None, pids=None):
        try:
            with connection.cursor() as cursor:
                cursor.execute("SET lock_timeout = '8s'")
                cursor.execute("SET statement_timeout = '12s'")
                cursor.execute("SELECT pg_backend_pid()")
                if pids is not None:
                    pids.put(cursor.fetchone()[0])
            usuario = get_user_model().objects.get(pk=self.usuario.pk)
            cliente = self._cliente(usuario)
            if barrera is not None:
                barrera.wait(timeout=10)
            respuesta = ejecutar(cliente)
            resultados.put((respuesta.status_code, respuesta.data))
        except Exception as error:
            resultados.put(("error", repr(error)))
        finally:
            connections.close_all()

    def _dos_sesiones(self, ejecutar):
        resultados = Queue()
        barrera = threading.Barrier(3)
        hilos = [
            threading.Thread(
                target=self._trabajador,
                args=(ejecutar, resultados),
                kwargs={"barrera": barrera},
                daemon=True,
            )
            for _ in range(2)
        ]
        try:
            for hilo in hilos:
                hilo.start()
            barrera.wait(timeout=10)
        finally:
            for hilo in hilos:
                if hilo.ident is not None:
                    hilo.join(timeout=15)
            for hilo in hilos:
                self.assertFalse(
                    hilo.is_alive(), "El trabajador dejó una conexión activa."
                )
        return [resultados.get(timeout=1) for _ in hilos]

    def test_misma_clave_fisica_en_dos_sesiones_crea_un_solo_acto(self):
        vale = self._transferido()
        datos = self._datos_acto()

        resultados = self._dos_sesiones(
            lambda cliente: self._accion(vale, "actos", datos, cliente)
        )

        self.assertEqual([estado for estado, _ in resultados], [200, 200], resultados)
        self.assertEqual(
            ActoValeEstandarizacion.objects.filter(clave=datos["clave"]).count(), 1
        )
        self.assertEqual(
            MovimientoSilo.objects.filter(operacion_id=datos["clave"]).count(), 2
        )
        vale.refresh_from_db()
        self.assertEqual(vale.actos.get().litros, Decimal("25.25"))

    def test_dos_transferencias_simultaneas_no_duplican_libro_ni_ejecucion(self):
        vale = self._preparado()

        resultados = self._dos_sesiones(
            lambda cliente: self._accion(vale, "transferir", cliente=cliente)
        )

        self.assertEqual([estado for estado, _ in resultados], [200, 200], resultados)
        self.assertEqual(EjecucionProceso.objects.filter(vale=vale).count(), 1)
        movimientos = MovimientoSilo.objects.filter(
            origen_tipo=MovimientoSilo.OrigenTipo.ESTANDARIZACION,
            origen_id=vale.pk,
        )
        self.assertEqual(movimientos.count(), 3)
        self.assertEqual(
            movimientos.filter(tipo=MovimientoSilo.Tipo.INGRESO).get().litros,
            Decimal("10000.00"),
        )

    def test_patch_en_espera_no_reescribe_una_transferencia_confirmada(self):
        vale = self._preparado()
        resultados, pids = Queue(), Queue()
        hilo = threading.Thread(
            target=self._trabajador,
            args=(
                lambda cliente: cliente.patch(
                    f"/api/estandarizacion/vales/{vale.pk}/",
                    {"litros_entera": "4001.00", "litros_descremada": "5999.00"},
                    format="json",
                ),
                resultados,
            ),
            kwargs={"pids": pids},
            daemon=True,
        )
        bloqueado = False
        try:
            with transaction.atomic():
                respuesta = self._accion(vale, "transferir")
                self.assertEqual(respuesta.status_code, 200, respuesta.data)
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
        finally:
            if hilo.ident is not None:
                hilo.join(timeout=15)
            self.assertFalse(hilo.is_alive(), "La edición concurrente no terminó.")
        self.assertTrue(bloqueado, "No se observó espera real de la edición.")
        estado, cuerpo = resultados.get(timeout=1)
        self.assertEqual(estado, 400, cuerpo)
        vale.refresh_from_db()
        self.assertEqual(vale.litros_entera, Decimal("4000.00"))
        self.assertEqual(vale.litros_descremada, Decimal("6000.00"))
        ejecucion = EjecucionProceso.objects.get(vale=vale)
        self.assertEqual(
            sorted(ejecucion.entradas.values_list("cantidad", flat=True)),
            [Decimal("4000.00"), Decimal("6000.00")],
        )
