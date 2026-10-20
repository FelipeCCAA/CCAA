"""Integración real OP-02 → Calidad → autorización y salida de granel."""

from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.utils import timezone

from calidad.models import LiberacionProceso
from inventario.models import ClienteDespacho, Despacho, DetalleDespachoGranel
from inventario.pruebas_firmas import firmar_salida_de_prueba
from inventario.servicios import autorizar_despacho, ejecutar_despacho
from procesos.models import EjecucionProceso, SalidaProceso
from recepcion.models import AnalisisSilo, ControlInhibidores, MovimientoSilo
from recepcion.servicios import saldo_silo
from usuarios.models import PerfilUsuario, Rol

from .models import ActoValeEstandarizacion
from .tests_op02_actos import EscenarioActosOP02
from .tests_vale import BaseVale


class DespachoEstandarizacionOP02Tests(EscenarioActosOP02, BaseVale):
    def setUp(self):
        self._clientes()
        self.bodega = get_user_model().objects.create_user("despacho-op02")
        PerfilUsuario.objects.create(
            usuario=self.bodega,
            rol=Rol.OPERARIO,
            area=PerfilUsuario.Area.DESPACHO,
            sucursal=self.silo_destino.sucursal,
            empresa=self.silo_destino.sucursal.empresa,
        )
        self.destinatario = ClienteDespacho.objects.create(
            empresa=self.silo_destino.sucursal.empresa,
            codigo="CLI-OP02",
            nombre="Cliente ficticio OP02",
        )

    def _vale_liberado(self):
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
        liberada = self._accion(vale, "decidir", cliente=self.cliente_calidad)
        self.assertEqual(liberada.status_code, 200, liberada.data)
        vale.refresh_from_db()
        return vale

    def _hoja_autorizada(self):
        vale = self._vale_liberado()
        salida = SalidaProceso.objects.get(ejecucion__vale=vale)
        # Configuración upstream, anterior a firmar: este resultado va a granel.
        salida.producto = self.producto
        salida.clasificacion = SalidaProceso.Clasificacion.GRANEL
        salida.destino = SalidaProceso.Destino.DESPACHO_DIRECTO
        salida.save(update_fields=["producto", "clasificacion", "destino"])
        decision = firmar_salida_de_prueba(salida, self.calidad)
        self.assertTrue(decision.firma_vigente)
        hoja = Despacho.objects.create(
            sucursal=self.silo_destino.sucursal,
            numero="OP02-DESPACHO-1",
            cliente=self.destinatario,
            creado_por=self.bodega,
        )
        DetalleDespachoGranel.objects.create(
            despacho=hoja,
            salida=salida,
            cantidad=Decimal("800.00"),
            unidad="L",
        )
        autorizar_despacho(hoja, self.bodega)
        hoja.refresh_from_db()
        self.assertEqual(hoja.estado, Despacho.Estado.AUTORIZADO)
        return vale, salida, decision, hoja

    @staticmethod
    def _libro():
        return list(MovimientoSilo.objects.order_by("pk").values())

    def _rechaza_autorizar_y_ejecutar_sin_salida(self, hoja):
        libro = self._libro()
        documento = Despacho.objects.values().get(pk=hoja.pk)
        detalle = hoja.detalles_granel.get()
        for operacion in (autorizar_despacho, ejecutar_despacho):
            with self.subTest(operacion=operacion.__name__):
                with self.assertRaises(ValidationError):
                    operacion(hoja, self.bodega)
                self.assertEqual(self._libro(), libro)
                self.assertEqual(Despacho.objects.values().get(pk=hoja.pk), documento)
                detalle.refresh_from_db()
                self.assertIsNone(detalle.movimiento_silo_id)
                self.assertFalse(
                    MovimientoSilo.objects.filter(
                        operacion_id=detalle.operacion_id,
                    ).exists()
                )

    def _ejecutar_una_vez_aunque_se_reintente(self, hoja, *, saldo):
        ejecutar_despacho(hoja, self.bodega)
        primera_salida = self._libro()
        ejecutar_despacho(hoja, self.bodega)
        self.assertEqual(self._libro(), primera_salida)
        hoja.refresh_from_db()
        self.assertEqual(hoja.estado, Despacho.Estado.DESPACHADO)
        detalle = hoja.detalles_granel.get()
        movimiento = MovimientoSilo.objects.get(operacion_id=detalle.operacion_id)
        self.assertEqual(movimiento.pk, detalle.movimiento_silo_id)
        self.assertEqual(movimiento.tipo, MovimientoSilo.Tipo.SALIDA)
        self.assertEqual(movimiento.origen_tipo, MovimientoSilo.OrigenTipo.DESPACHO)
        self.assertEqual(movimiento.litros, Decimal("800.00"))
        self.assertEqual(saldo_silo(self.silo_destino), Decimal(saldo))

    def test_discrepancia_retiene_hoja_autorizada_y_nueva_medicion_cero_permite_salida(
        self,
    ):
        vale, salida, decision, hoja = self._hoja_autorizada()
        firma = decision.firma_id
        evidencia_hoja = hoja.autorizacion_evidencia
        original = self._foto_original(vale)

        medida = self._accion(
            vale,
            "actos",
            self._datos_acto("medicion", volumen_medido="9900.00"),
            self.cliente_recepcion,
        )

        self.assertEqual(medida.status_code, 200, medida.data)
        self.assertEqual(medida.data["balance"]["diferencia"], "-100.00")
        self.assertTrue(medida.data["balance"]["pendiente"])
        self._rechaza_autorizar_y_ejecutar_sin_salida(hoja)
        self._original_intacto(vale, original)
        self.assertEqual(saldo_silo(self.silo_destino), Decimal("10000.00"))

        conciliada = self._accion(
            vale,
            "actos",
            self._datos_acto("medicion", volumen_medido="10000.00"),
            self.cliente_recepcion,
        )

        self.assertEqual(conciliada.status_code, 200, conciliada.data)
        self.assertEqual(conciliada.data["balance"]["diferencia"], "0.00")
        self.assertFalse(conciliada.data["balance"]["pendiente"])
        self.assertEqual(len(conciliada.data["actos"]), 2)
        decision.refresh_from_db()
        self.assertEqual(decision.firma_id, firma)
        self.assertTrue(decision.firma_vigente)
        hoja.refresh_from_db()
        self.assertEqual(hoja.autorizacion_evidencia, evidencia_hoja)
        self._ejecutar_una_vez_aunque_se_reintente(hoja, saldo="9200.00")
        salida.refresh_from_db()
        self.assertEqual(salida.cantidad, Decimal("10000.00"))
        self._original_intacto(vale, original)

    def test_adicion_exige_nuevo_ciclo_firma_y_autorizacion_antes_de_despachar(self):
        vale, salida, decision, hoja = self._hoja_autorizada()
        firma = decision.firma_id
        muestra_anterior = decision.analisis_silo_id
        evidencia_hoja = hoja.autorizacion_evidencia
        original = self._foto_original(vale)
        ejecucion_original = EjecucionProceso.objects.values("estado", "termino").get(
            vale=vale
        )
        datos = self._datos_acto("adicion")

        adicion = self._accion(vale, "actos", datos)

        self.assertEqual(adicion.status_code, 200, adicion.data)
        self.assertEqual(adicion.data["balance"]["volumen_ejecutado"], "10025.25")
        self.assertEqual(
            MovimientoSilo.objects.filter(operacion_id=datos["clave"]).count(), 2
        )
        decision.refresh_from_db()
        self.assertEqual(decision.estado, LiberacionProceso.Estado.PENDIENTE)
        self.assertEqual(decision.firma_id, firma)
        self.assertFalse(decision.firma_vigente)
        self._rechaza_autorizar_y_ejecutar_sin_salida(hoja)

        self.assertEqual(self._accion(vale, "reagitar").status_code, 200)
        self.assertEqual(
            self._accion(
                vale,
                "muestrear",
                {"grasa": "1.79", "sng": "8.90"},
            ).status_code,
            200,
        )
        liberada = self._accion(vale, "decidir", cliente=self.cliente_calidad)
        self.assertEqual(liberada.status_code, 200, liberada.data)
        decision.refresh_from_db()
        self.assertEqual(decision.estado, LiberacionProceso.Estado.PENDIENTE)
        self.assertEqual(decision.firma_id, firma)
        self.assertFalse(decision.firma_vigente)
        self._rechaza_autorizar_y_ejecutar_sin_salida(hoja)

        endpoint = f"/api/calidad/resultados-proceso/{salida.pk}/liberar/"
        vieja = self.cliente_calidad.post(
            endpoint,
            {"analisis_id": muestra_anterior},
            format="json",
        )
        self.assertEqual(vieja.status_code, 409, vieja.data)
        self.assertIn("posterior", str(vieja.data))
        ahora = timezone.now()
        muestra = AnalisisSilo.objects.create(
            silo=self.silo_destino,
            tomado_en=ahora,
            estado=AnalisisSilo.Estado.CONFIRMADO,
            grasa="1.79",
            sng="8.90",
            inhibidores_resultado=ControlInhibidores.Resultado.NEGATIVO,
            metodo=ControlInhibidores.Metodo.TRI_SENSOR,
            hora_lectura=ahora.time(),
            analista=self.calidad,
            visualizado_por=self.calidad,
            visualizado_en=ahora,
        )

        nueva = self.cliente_calidad.post(
            endpoint,
            {"analisis_id": muestra.pk},
            format="json",
        )

        self.assertEqual(nueva.status_code, 200, nueva.data)
        decision.refresh_from_db()
        self.assertEqual(decision.estado, LiberacionProceso.Estado.LIBERADO)
        self.assertNotEqual(decision.firma_id, firma)
        self.assertTrue(decision.firma_vigente)
        # La firma nueva no convierte la autorización anterior en una nueva.
        self._rechaza_ejecutar_sin_reautorizar(hoja)
        autorizar_despacho(hoja, self.bodega)
        hoja.refresh_from_db()
        self.assertNotEqual(hoja.autorizacion_evidencia, evidencia_hoja)
        self._ejecutar_una_vez_aunque_se_reintente(hoja, saldo="9225.25")
        self._original_intacto(vale, original)
        self.assertEqual(
            EjecucionProceso.objects.values("estado", "termino").get(vale=vale),
            ejecucion_original,
        )

        libro_despachado = self._libro()
        actos = list(ActoValeEstandarizacion.objects.order_by("pk").values())
        documento = Despacho.objects.values().get(pk=hoja.pk)
        posterior = self._accion(vale, "actos", self._datos_acto("adicion"))
        self.assertEqual(posterior.status_code, 409, posterior.data)
        self.assertEqual(self._libro(), libro_despachado)
        self.assertEqual(
            list(ActoValeEstandarizacion.objects.order_by("pk").values()), actos
        )
        self.assertEqual(Despacho.objects.values().get(pk=hoja.pk), documento)

    def _rechaza_ejecutar_sin_reautorizar(self, hoja):
        libro = self._libro()
        documento = Despacho.objects.values().get(pk=hoja.pk)
        with self.assertRaises(ValidationError):
            ejecutar_despacho(hoja, self.bodega)
        self.assertEqual(self._libro(), libro)
        self.assertEqual(Despacho.objects.values().get(pk=hoja.pk), documento)
