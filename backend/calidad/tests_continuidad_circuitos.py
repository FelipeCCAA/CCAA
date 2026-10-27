"""Continuidad pendiente en Mantequilla y Envase, con despacho siempre estricto."""
from decimal import Decimal
from uuid import uuid4

from django.core.exceptions import ValidationError
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from calidad.models import LiberacionProceso
from inventario.models import (
    ClienteDespacho, Despacho, DetalleDespacho, ExistenciaProductoTerminado,
    MovimientoProductoTerminado, Ubicacion,
)
from inventario.servicios import autorizar_despacho, ingresar_pallet
from maestros.models import Silo
from procesos import tests_op05_mantequilla as escenarios_mantequilla
from procesos.models import (
    EntradaProceso, EjecucionProceso, EtapaProceso, EventoProceso,
    Proceso, RutaProducto, SalidaProceso,
)
from procesos.servicios import cerrar_mantequilla, iniciar_mantequilla
from produccion import tests_envase as escenarios_envase
from produccion.models import PalletProducto, RegistroEnvase
from recepcion.models import MovimientoSilo


@override_settings(CCAA_CALIDAD_INTERMEDIA_AVISO=True)
class ContinuidadMantequillaTests(TestCase):
    _origen_tk = escenarios_mantequilla.MantequillaOp05BaselineTests._origen_tk

    def setUp(self):
        escenarios_mantequilla.MantequillaOp05BaselineTests.setUp(self)
        self.salida, self.analisis, self.tk = self._origen_tk(firmar=False)
        etapa = self.salida.ejecucion.etapa
        etapa.requiere_calidad = True
        etapa.save(update_fields=["requiere_calidad"])
        decision = LiberacionProceso.objects.get(salida=self.salida)
        decision.estado = LiberacionProceso.Estado.PENDIENTE
        decision.save(update_fields=["estado"])
        self.tk.estado = Silo.Estado.PENDIENTE_CALIDAD
        self.tk.save(update_fields=["estado"])

    def test_crema_pendiente_avanza_con_un_retiro_y_sin_firma_falsa(self):
        iniciar_mantequilla(
            corrida_id=self.corrida.pk, usuario=self.usuario, operacion_id=uuid4(),
        )
        entrada = EntradaProceso.objects.get(ejecucion=self.corrida.ejecucion)
        retiros = MovimientoSilo.objects.filter(
            operacion_id=self.corrida.operacion_id,
            origen_id=self.corrida.pk, silo=self.tk,
            tipo=MovimientoSilo.Tipo.SALIDA,
        )
        self.assertEqual(retiros.count(), 1)
        self.assertEqual(entrada.salida_origen_id, self.salida.pk)
        self.assertEqual(entrada.cantidad, retiros.get().litros)
        inicio = EventoProceso.objects.get(
            ejecucion=self.corrida.ejecucion, tipo="mantequilla_iniciada",
        )
        self.assertIsNone(inicio.datos["firma_salida"])
        self.assertTrue(inicio.datos["continuidad_pendiente"])
        self.assertEqual(inicio.datos["analisis_silo_id"], self.analisis.pk)
        cerrar_mantequilla(
            corrida_id=self.corrida.pk, usuario=self.usuario,
            kg_mantequilla="195", kg_merma="5", operacion_id=uuid4(),
        )
        cierre = EventoProceso.objects.get(
            ejecucion=self.corrida.ejecucion, tipo="mantequilla_cerrada",
        )
        self.assertIsNone(cierre.datos["firma_salida_inicio"])
        self.assertIsNone(cierre.datos["firma_vigente_al_cierre"])
        self.assertEqual(self.corrida.ejecucion.salidas.count(), 2)
        self.assertEqual(retiros.count(), 1)
        self.assertEqual(
            EventoProceso.objects.filter(
                ejecucion=self.corrida.ejecucion,
                tipo="continuidad_calidad_pendiente",
            ).count(), 2,
        )
        self.assertFalse(LiberacionProceso.objects.filter(
            salida__ejecucion=self.corrida.ejecucion,
            firma_id__isnull=False,
        ).exists())

    def test_catalogo_muestra_crema_pendiente_sin_etiqueta_de_liberacion(self):
        cliente = APIClient()
        cliente.force_authenticate(self.usuario)
        respuesta = cliente.get("/api/procesos/salidas/disponibles/")
        self.assertEqual(respuesta.status_code, 200, respuesta.data)
        material = next(item for item in respuesta.data if item["id"] == self.salida.pk)
        self.assertEqual(material["estado_calidad"], "pendiente")
        self.assertEqual(material["estado_material"], "pendiente")
        self.assertTrue(material["avisos_calidad"])
        self.assertNotIn(
            "preparar_despacho",
            {accion["codigo"] for accion in material["acciones_permitidas"]},
        )

    def test_catalogo_omite_salida_directa_pendiente_de_calidad(self):
        ruta_directa = RutaProducto.objects.create(
            sucursal=self.planta, producto=self.lote_crema.producto,
            proceso=self.salida.ejecucion.etapa.proceso,
            destino_final=RutaProducto.DestinoFinal.DESPACHO_DIRECTO,
        )
        self.salida.ruta_producto = ruta_directa
        self.salida.clasificacion = SalidaProceso.Clasificacion.GRANEL
        self.salida.destino = SalidaProceso.Destino.DESPACHO_DIRECTO
        self.salida.save(update_fields=["ruta_producto", "clasificacion", "destino"])
        cliente = APIClient()
        cliente.force_authenticate(self.usuario)
        respuesta = cliente.get("/api/procesos/salidas/disponibles/")
        self.assertEqual(respuesta.status_code, 200, respuesta.data)
        self.assertNotIn(self.salida.pk, {item["id"] for item in respuesta.data})


@override_settings(CCAA_CALIDAD_INTERMEDIA_AVISO=True)
class ContinuidadEnvaseTests(TestCase):
    def setUp(self):
        escenarios_envase.EnvasePalletTests.setUp(self)
        proceso = Proceso.objects.create(codigo="ruta-sec-aviso", nombre="Secado pendiente")
        etapa = EtapaProceso.objects.create(
            proceso=proceso, codigo="secar-aviso", nombre="Secado pendiente",
            tipo=EtapaProceso.Tipo.SECADO, orden=1, requiere_calidad=True,
        )
        ejecucion = EjecucionProceso.objects.create(
            codigo="EJ-SEC-AVISO", etapa=etapa, sucursal=self.planta,
            estado=EjecucionProceso.Estado.CERRADA,
        )
        self.lote.ejecucion = ejecucion
        self.lote.save(update_fields=["ejecucion"])
        self.salida = SalidaProceso.objects.create(
            ejecucion=ejecucion, lote=self.lote, producto=self.producto,
            naturaleza=SalidaProceso.Naturaleza.PRINCIPAL,
            clasificacion=SalidaProceso.Clasificacion.GRANEL,
            destino=SalidaProceso.Destino.ENVASADO,
            cantidad=Decimal("1000"), unidad="kg",
        )
        LiberacionProceso.objects.create(salida=self.salida)
        self.cliente_api = APIClient()
        self.cliente_api.force_authenticate(self.usuario)

    def test_envase_pendiente_crea_pallets_en_cuarentena_y_aviso_sin_liberar(self):
        materiales = self.cliente_api.get("/api/produccion/envases/materiales-habilitados/")
        self.assertEqual(materiales.status_code, 200, materiales.data)
        material = next(item for item in materiales.data if item["salida_id"] == self.salida.pk)
        self.assertEqual(material["calidad"], "pendiente")
        self.assertTrue(material["avisos_calidad"])
        self.assertTrue(material["puede_envasar"])

        registro = escenarios_envase.EnvasePalletTests.registrar(self)
        self.assertEqual(RegistroEnvase.objects.filter(pk=registro.pk).count(), 1)
        self.assertEqual(registro.pallets.count(), 2)
        self.assertTrue(all(
            pallet.estado == PalletProducto.Estado.PENDIENTE_CALIDAD
            for pallet in registro.pallets.all()
        ))
        existencias = ExistenciaProductoTerminado.objects.filter(pallet__envase=registro)
        self.assertEqual(existencias.count(), 2)
        self.assertTrue(all(
            existencia.ubicacion.tipo == Ubicacion.Tipo.CUARENTENA
            for existencia in existencias.select_related("ubicacion")
        ))
        self.assertEqual(MovimientoProductoTerminado.objects.filter(
            pallet__envase=registro, tipo=MovimientoProductoTerminado.Tipo.INGRESO,
        ).count(), 2)
        evento = EventoProceso.objects.get(
            ejecucion=self.lote.ejecucion, tipo="continuidad_calidad_pendiente",
            motivo=f"envasar:{registro.pk}",
        )
        self.assertFalse(evento.datos["liberacion_final"])
        self.assertTrue(evento.datos["avisos"])
        self.assertFalse(LiberacionProceso.objects.get(salida=self.salida).firma_id)

        pallet = registro.pallets.first()
        ubicacion = Ubicacion.objects.get(bodega__sucursal=self.planta, codigo="BASE-DISP")
        with self.assertRaises(ValidationError):
            ingresar_pallet(pallet, ubicacion, self.usuario)
        cliente = ClienteDespacho.objects.create(
            empresa=self.planta.empresa, codigo="CONT-ENV", nombre="Cliente de prueba",
        )
        hoja = Despacho.objects.create(
            sucursal=self.planta, numero="CONT-ENV-1", cliente=cliente,
            creado_por=self.usuario,
        )
        DetalleDespacho.objects.create(despacho=hoja, pallet=pallet)
        with self.assertRaises(ValidationError):
            autorizar_despacho(hoja, self.usuario)
        hoja.refresh_from_db()
        self.assertEqual(hoja.estado, Despacho.Estado.BORRADOR)
