"""Regresiones OP-01 por las operaciones reales de autorización y salida."""

from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from calidad.models import Liberacion
from calidad.evidencia import bloquear_catalogo
from calidad.vigencia import registrar_firma_lote
from maestros.models import Producto, Silo
from procesos.models import (
    EjecucionProceso, EntradaProceso, EtapaProceso, Proceso, ReservaSiloProceso, SalidaProceso,
)
from recepcion.models import MovimientoSilo
from recepcion.servicios import saldo_silo
from usuarios.models import Sucursal

from .models import (
    Bodega, Despacho, DetalleDespacho, DetalleDespachoGranel,
    ExistenciaProductoTerminado, MovimientoProductoTerminado, Ubicacion,
)
from .pruebas_base import EscenarioProductoTerminado
from .pruebas_firmas import firmar_salida_de_prueba
from .servicios import (
    autorizar_despacho, ejecutar_despacho, estado_autorizacion_despacho,
    ingresar_pallet, transferir_pallet,
)


class VigenciaDespachoOP01Tests(EscenarioProductoTerminado):
    def setUp(self):
        super().setUp()
        self.liberar()
        ingresar_pallet(self.pallet, self.ubicacion, self.usuario)
        self.secuencia = 0

    def _hoja(self, *, pallet=None, salida=None, cantidad="800"):
        self.secuencia += 1
        hoja = Despacho.objects.create(
            sucursal=self.planta, numero=f"OP01-{self.secuencia}",
            cliente=self.cliente, creado_por=self.usuario,
        )
        if pallet is not None:
            DetalleDespacho.objects.create(despacho=hoja, pallet=pallet)
        if salida is not None:
            DetalleDespachoGranel.objects.create(
                despacho=hoja, salida=salida,
                cantidad=Decimal(cantidad), unidad="L",
            )
        return hoja

    def _granel(self):
        self.secuencia += 1
        codigo = f"OP01-GR-{self.secuencia}"
        proceso = Proceso.objects.create(codigo=codigo, nombre="Granel OP01")
        etapa = EtapaProceso.objects.create(
            proceso=proceso, codigo="salida", nombre="Salida a granel",
            tipo=EtapaProceso.Tipo.EVAPORACION, orden=1, requiere_calidad=True,
        )
        ejecucion = EjecucionProceso.objects.create(
            codigo=codigo, etapa=etapa, sucursal=self.planta,
        )
        silo = Silo.objects.create(
            sucursal=self.planta, codigo=codigo, tipo=Silo.Tipo.SILO,
            capacidad_l=Decimal("2000"), estado=Silo.Estado.DISPONIBLE,
        )
        salida = SalidaProceso.objects.create(
            ejecucion=ejecucion, producto=self.producto, silo=silo,
            cantidad=Decimal("1000"), unidad="L",
            clasificacion=SalidaProceso.Clasificacion.GRANEL,
            destino=SalidaProceso.Destino.DESPACHO_DIRECTO,
        )
        MovimientoSilo.objects.create(
            silo=silo, tipo=MovimientoSilo.Tipo.INGRESO, litros=Decimal("1000"),
            fecha_hora=timezone.now(), origen_tipo=MovimientoSilo.OrigenTipo.PRODUCCION,
        )
        firmar_salida_de_prueba(salida, self.usuario)
        return salida, silo

    def _sin_salida(self, hoja, *, pallet=None, silo=None):
        hoja.refresh_from_db()
        self.assertNotEqual(hoja.estado, Despacho.Estado.DESPACHADO)
        self.assertFalse(MovimientoProductoTerminado.objects.filter(
            despacho=hoja, tipo=MovimientoProductoTerminado.Tipo.DESPACHO,
        ).exists())
        self.assertFalse(MovimientoSilo.objects.filter(
            detalle_despacho_granel__despacho=hoja,
        ).exists())
        if pallet is not None:
            self.assertTrue(ExistenciaProductoTerminado.objects.get(pallet=pallet).activo)
        if silo is not None:
            self.assertEqual(saldo_silo(silo), Decimal("1000"))

    def test_autorizar_rechaza_pallet_en_ubicacion_no_disponible(self):
        for tipo in (
            Ubicacion.Tipo.CUARENTENA, Ubicacion.Tipo.RECHAZADO,
            Ubicacion.Tipo.PRODUCCION,
        ):
            with self.subTest(tipo=tipo):
                pallet = self.crear_pallet(f"OP01-{tipo}")
                ingresar_pallet(pallet, self.ubicacion, self.usuario)
                ubicacion = Ubicacion.objects.create(
                    bodega=self.ubicacion.bodega, codigo=f"OP01-{tipo}", tipo=tipo,
                )
                transferir_pallet(pallet.existencia_producto, ubicacion, self.usuario)
                hoja = self._hoja(pallet=pallet)

                with self.assertRaises(ValidationError):
                    autorizar_despacho(hoja, self.usuario)

                hoja.refresh_from_db()
                self.assertEqual(hoja.estado, Despacho.Estado.BORRADOR)
                self._sin_salida(hoja, pallet=pallet)

    def test_autorizar_rechaza_ubicacion_inactiva(self):
        self.ubicacion.activo = False
        self.ubicacion.save(update_fields=["activo"])
        hoja = self._hoja(pallet=self.pallet)

        with self.assertRaises(ValidationError):
            autorizar_despacho(hoja, self.usuario)

        self._sin_salida(hoja, pallet=self.pallet)

    def test_cuarentena_posterior_bloquea_hoja_previamente_autorizada(self):
        hoja = self._hoja(pallet=self.pallet)
        autorizar_despacho(hoja, self.usuario)
        cuarentena = Ubicacion.objects.create(
            bodega=self.ubicacion.bodega, codigo="OP01-CUAR",
            tipo=Ubicacion.Tipo.CUARENTENA,
        )
        transferir_pallet(self.pallet.existencia_producto, cuarentena, self.usuario)

        with self.assertRaises(ValidationError):
            ejecutar_despacho(hoja, self.usuario)

        self._sin_salida(hoja, pallet=self.pallet)

    def test_ubicacion_desactivada_despues_de_autorizar_impide_salida(self):
        hoja = self._hoja(pallet=self.pallet)
        autorizar_despacho(hoja, self.usuario)
        self.ubicacion.activo = False
        self.ubicacion.save(update_fields=["activo"])

        with self.assertRaises(ValidationError):
            ejecutar_despacho(hoja, self.usuario)

        self._sin_salida(hoja, pallet=self.pallet)

    def test_cambiar_origen_disponible_exige_reautorizar_la_hoja(self):
        hoja = self._hoja(pallet=self.pallet)
        autorizar_despacho(hoja, self.usuario)
        destino = Ubicacion.objects.create(
            bodega=self.ubicacion.bodega, codigo="OP01-NUEVO-ORIGEN",
            tipo=Ubicacion.Tipo.DISPONIBLE,
        )
        transferir_pallet(self.pallet.existencia_producto, destino, self.usuario)

        with self.assertRaises(ValidationError):
            ejecutar_despacho(hoja, self.usuario)

        self._sin_salida(hoja, pallet=self.pallet)
        autorizar_despacho(hoja, self.usuario)
        ejecutar_despacho(hoja, self.usuario)
        movimiento = MovimientoProductoTerminado.objects.get(
            despacho=hoja, tipo=MovimientoProductoTerminado.Tipo.DESPACHO,
        )
        self.assertEqual(movimiento.origen_id, destino.pk)

    def test_granel_bloqueado_no_se_autoriza_aunque_calidad_este_liberada(self):
        salida, silo = self._granel()
        silo.estado = Silo.Estado.BLOQUEADO_CALIDAD
        silo.save(update_fields=["estado"])
        hoja = self._hoja(salida=salida)

        with self.assertRaises(ValidationError):
            autorizar_despacho(hoja, self.usuario)

        self._sin_salida(hoja, silo=silo)

    def test_cambios_de_estado_silo_impiden_ejecutar_hoja_autorizada(self):
        for estado in (
            Silo.Estado.RECIBIENDO, Silo.Estado.RESERVADO,
            Silo.Estado.BLOQUEADO_CALIDAD, Silo.Estado.PENDIENTE_CIP,
            Silo.Estado.EN_CIP, Silo.Estado.FUERA_SERVICIO,
        ):
            with self.subTest(estado=estado):
                salida, silo = self._granel()
                hoja = self._hoja(salida=salida)
                autorizar_despacho(hoja, self.usuario)
                silo.estado = estado
                silo.save(update_fields=["estado"])

                with self.assertRaises(ValidationError):
                    ejecutar_despacho(hoja, self.usuario)

                self._sin_salida(hoja, silo=silo)

    def test_silo_desactivado_despues_de_autorizar_impide_salida(self):
        salida, silo = self._granel()
        hoja = self._hoja(salida=salida)
        autorizar_despacho(hoja, self.usuario)
        silo.activo = False
        silo.save(update_fields=["activo"])

        with self.assertRaises(ValidationError):
            ejecutar_despacho(hoja, self.usuario)

        self._sin_salida(hoja, silo=silo)

    def test_hoja_mixta_fallida_no_descuenta_el_pallet_ni_el_granel(self):
        salida, silo = self._granel()
        hoja = self._hoja(pallet=self.pallet, salida=salida)
        autorizar_despacho(hoja, self.usuario)
        silo.estado = Silo.Estado.EN_CIP
        silo.save(update_fields=["estado"])

        with self.assertRaises(ValidationError):
            ejecutar_despacho(hoja, self.usuario)

        self._sin_salida(hoja, pallet=self.pallet, silo=silo)

    def test_granel_en_uso_sin_conflicto_admite_salida_y_reintento_unico(self):
        salida, silo = self._granel()
        silo.estado = Silo.Estado.EN_USO
        silo.save(update_fields=["estado"])
        hoja = self._hoja(salida=salida)
        autorizar_despacho(hoja, self.usuario)

        ejecutar_despacho(hoja, self.usuario)
        ejecutar_despacho(hoja, self.usuario)

        hoja.refresh_from_db()
        detalle = hoja.detalles_granel.get()
        self.assertEqual(hoja.estado, Despacho.Estado.DESPACHADO)
        self.assertEqual(saldo_silo(silo), Decimal("200"))
        self.assertEqual(MovimientoSilo.objects.filter(
            operacion_id=detalle.operacion_id,
        ).count(), 1)
        self.assertEqual(detalle.movimiento_silo.litros, Decimal("800"))

    def test_reintento_de_pallet_no_duplica_movimiento(self):
        hoja = self._hoja(pallet=self.pallet)
        autorizar_despacho(hoja, self.usuario)

        ejecutar_despacho(hoja, self.usuario)
        ejecutar_despacho(hoja, self.usuario)

        self.assertFalse(ExistenciaProductoTerminado.objects.get(pallet=self.pallet).activo)
        self.assertEqual(MovimientoProductoTerminado.objects.filter(
            despacho=hoja, tipo=MovimientoProductoTerminado.Tipo.DESPACHO,
        ).count(), 1)

    def test_el_operador_ve_la_causa_y_la_necesidad_de_reautorizar(self):
        hoja = self._hoja(pallet=self.pallet)
        autorizar_despacho(hoja, self.usuario)
        hoja.refresh_from_db()
        self.assertFalse(estado_autorizacion_despacho(hoja)["requiere_reautorizacion"])
        anterior = hoja.autorizacion_evidencia
        destino = Ubicacion.objects.create(
            bodega=self.ubicacion.bodega, codigo="OP01-AVISO",
            tipo=Ubicacion.Tipo.DISPONIBLE,
        )
        transferir_pallet(self.pallet.existencia_producto, destino, self.usuario)

        estado = estado_autorizacion_despacho(hoja)

        self.assertTrue(estado["requiere_reautorizacion"])
        self.assertIn("autoriza nuevamente", estado["motivo_reautorizacion"])
        hoja.refresh_from_db()
        self.assertEqual(hoja.autorizacion_evidencia, anterior)
        self._sin_salida(hoja, pallet=self.pallet)

    def test_la_api_no_permite_fabricar_el_respaldo_de_autorizacion(self):
        self.dar_permiso("despacho_crear")
        respuesta = self.api.post("/api/inventario/despachos/", {
            "cliente": self.cliente.pk, "pallet_ids": [self.pallet.pk],
            "autorizacion_evidencia": {"version": 1, "firma": "firma-no-autorizada"},
            "requiere_reautorizacion": False,
        }, format="json")

        self.assertEqual(respuesta.status_code, 201, respuesta.data)
        hoja = Despacho.objects.get(pk=respuesta.data["id"])
        self.assertEqual(hoja.estado, Despacho.Estado.BORRADOR)
        self.assertEqual(hoja.autorizacion_evidencia, {})

    def test_ingreso_posterior_a_la_muestra_impide_despachar_con_la_firma_anterior(self):
        salida, silo = self._granel()
        hoja = self._hoja(salida=salida)
        autorizar_despacho(hoja, self.usuario)
        MovimientoSilo.objects.create(
            silo=silo, tipo=MovimientoSilo.Tipo.INGRESO, litros=Decimal("100"),
            fecha_hora=timezone.now(), origen_tipo=MovimientoSilo.OrigenTipo.PRODUCCION,
        )

        with self.assertRaises(ValidationError):
            ejecutar_despacho(hoja, self.usuario)

        self.assertEqual(saldo_silo(silo), Decimal("1100"))
        self.assertIsNone(hoja.detalles_granel.get().movimiento_silo_id)
        hoja.refresh_from_db()
        self.assertTrue(estado_autorizacion_despacho(hoja)["requiere_reautorizacion"])

    def test_modificar_cantidad_de_la_hoja_exige_autorizacion_nueva(self):
        salida, silo = self._granel()
        hoja = self._hoja(salida=salida)
        autorizar_despacho(hoja, self.usuario)
        detalle = hoja.detalles_granel.get()
        detalle.cantidad = Decimal("700")
        detalle.save(update_fields=["cantidad"])

        with self.assertRaises(ValidationError):
            ejecutar_despacho(hoja, self.usuario)

        self._sin_salida(hoja, silo=silo)
        autorizar_despacho(hoja, self.usuario)
        ejecutar_despacho(hoja, self.usuario)
        self.assertEqual(saldo_silo(silo), Decimal("300"))

    def test_reserva_activa_ajena_bloquea_la_salida_pero_la_propietaria_no(self):
        salida, silo = self._granel()
        reserva = ReservaSiloProceso.objects.create(
            ejecucion=salida.ejecucion, silo=silo, tipo=ReservaSiloProceso.Tipo.ORIGEN,
            cantidad_planificada=Decimal("100"),
        )
        hoja = self._hoja(salida=salida)
        autorizar_despacho(hoja, self.usuario)
        otra_ejecucion = EjecucionProceso.objects.create(
            codigo="OP01-RESERVA-AJENA", etapa=salida.ejecucion.etapa, sucursal=self.planta,
        )
        reserva.ejecucion = otra_ejecucion
        reserva.save(update_fields=["ejecucion"])

        with self.assertRaises(ValidationError):
            ejecutar_despacho(hoja, self.usuario)

        self._sin_salida(hoja, silo=silo)

    def test_otro_proceso_activo_usando_el_silo_impide_despachar(self):
        salida, silo = self._granel()
        hoja = self._hoja(salida=salida)
        autorizar_despacho(hoja, self.usuario)
        otra_ejecucion = EjecucionProceso.objects.create(
            codigo="OP01-USO-AJENO", etapa=salida.ejecucion.etapa, sucursal=self.planta,
            estado=EjecucionProceso.Estado.EJECUCION,
        )
        EntradaProceso.objects.create(
            ejecucion=otra_ejecucion, silo=silo, cantidad=Decimal("100"), unidad="L",
        )

        with self.assertRaises(ValidationError):
            ejecutar_despacho(hoja, self.usuario)

        self._sin_salida(hoja, silo=silo)

    def test_producto_declarado_distinto_del_material_autorizado_impide_salida(self):
        salida, silo = self._granel()
        hoja = self._hoja(salida=salida)
        autorizar_despacho(hoja, self.usuario)
        otro = Producto.objects.create(
            mandante=self.producto.mandante, nombre="Otro producto OP01",
        )
        silo.producto_actual = otro
        silo.save(update_fields=["producto_actual"])

        with self.assertRaises(ValidationError):
            ejecutar_despacho(hoja, self.usuario)

        self._sin_salida(hoja, silo=silo)

    def test_una_firma_nueva_no_reactiva_la_autorizacion_anterior_de_la_hoja(self):
        hoja = self._hoja(pallet=self.pallet)
        autorizar_despacho(hoja, self.usuario)
        anterior = Liberacion.objects.get(lote=self.lote).firma_id
        with transaction.atomic():
            bloquear_catalogo()
            decision = Liberacion.objects.get(lote=self.lote)
            registrar_firma_lote(decision)
        self.assertNotEqual(decision.firma_id, anterior)

        with self.assertRaises(ValidationError):
            ejecutar_despacho(hoja, self.usuario)

        self._sin_salida(hoja, pallet=self.pallet)
        autorizar_despacho(hoja, self.usuario)
        ejecutar_despacho(hoja, self.usuario)
        self.assertFalse(ExistenciaProductoTerminado.objects.get(pallet=self.pallet).activo)

    def test_ubicacion_en_otra_planta_no_habilita_un_despacho_local(self):
        hoja = self._hoja(pallet=self.pallet)
        autorizar_despacho(hoja, self.usuario)
        otra_planta = Sucursal.objects.create(
            empresa=self.empresa, codigo="OP01-OTRA", nombre="Otra planta",
        )
        otra_bodega = Bodega.objects.create(
            sucursal=otra_planta, codigo="OP01-OTRA", nombre="Bodega de otra planta",
        )
        # Incluso conservar el mismo ID de ubicación no conserva el origen.
        self.ubicacion.bodega = otra_bodega
        self.ubicacion.save(update_fields=["bodega"])

        with self.assertRaises(ValidationError):
            ejecutar_despacho(hoja, self.usuario)

        self._sin_salida(hoja, pallet=self.pallet)

    def test_bodega_desactivada_despues_de_autorizar_impide_salida(self):
        hoja = self._hoja(pallet=self.pallet)
        autorizar_despacho(hoja, self.usuario)
        bodega = self.ubicacion.bodega
        bodega.activo = False
        bodega.save(update_fields=["activo"])

        with self.assertRaises(ValidationError):
            ejecutar_despacho(hoja, self.usuario)

        self._sin_salida(hoja, pallet=self.pallet)

    def test_muestra_del_silo_anterior_no_habilita_otro_silo_con_saldo(self):
        salida, _ = self._granel()
        hoja = self._hoja(salida=salida)
        autorizar_despacho(hoja, self.usuario)
        otro = Silo.objects.create(
            sucursal=self.planta, codigo="OP01-OTRO-SILO", tipo=Silo.Tipo.SILO,
            capacidad_l=Decimal("2000"), producto_actual=self.producto,
        )
        MovimientoSilo.objects.create(
            silo=otro, tipo=MovimientoSilo.Tipo.INGRESO, litros=Decimal("1000"),
            fecha_hora=timezone.now(), origen_tipo=MovimientoSilo.OrigenTipo.PRODUCCION,
        )
        salida.silo = otro
        salida.save(update_fields=["silo"])

        # No basta actualizar el respaldo de la hoja: la muestra aprobada
        # sigue perteneciendo al origen anterior.
        with self.assertRaises(ValidationError):
            autorizar_despacho(hoja, self.usuario)
        with self.assertRaises(ValidationError):
            ejecutar_despacho(hoja, self.usuario)

        self._sin_salida(hoja, silo=otro)
