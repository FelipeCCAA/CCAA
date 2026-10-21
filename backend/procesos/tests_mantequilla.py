from datetime import date
from decimal import Decimal
from uuid import uuid4

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from calidad.models import LiberacionProceso
from calidad.vigencia import registrar_firma_salida
from inventario.models import Notificacion
from maestros.models import Equipo, Especificacion, Mandante, Producto, Silo
from produccion.models import Analisis, Lote, OrdenProduccion
from recepcion.models import AnalisisSilo, MovimientoSilo
from usuarios.models import Empresa, PerfilUsuario, Rol, Sucursal

from .models import (
    AutorizacionReproceso, CorridaMantequilla, EjecucionProceso,
    EtapaProceso, Proceso, RutaProducto, SalidaProceso,
)
from .servicios import (
    cerrar_mantequilla, crear_mantequilla_guiada,
    genealogia_lote, iniciar_mantequilla,
)


class MantequillaTests(TestCase):
    def setUp(self):
        empresa = Empresa.objects.create(rut="MANT-1", nombre="Empresa mantequilla")
        planta = Sucursal.objects.create(empresa=empresa, codigo="MANT", nombre="Planta")
        self.empresa = empresa
        self.planta = planta
        self.usuario = User.objects.create_user("operador-mantequilla")
        PerfilUsuario.objects.create(
            usuario=self.usuario, empresa=empresa, sucursal=planta,
            rol=Rol.PRODUCCION, area=PerfilUsuario.Area.ENVASE,
        )
        mandante = Mandante.objects.create(
            empresa=empresa, nombre="Mandante mantequilla", codigo_cliente="mant"
        )
        crema = Producto.objects.create(
            mandante=mandante, nombre="Crema", familia=Producto.Familia.CREMA
        )
        mantequilla = Producto.objects.create(
            mandante=mandante, nombre="Mantequilla",
            categoria=Producto.Categoria.MANTEQUILLA,
        )
        suero = Producto.objects.create(
            mandante=mandante, nombre="Suero",
            categoria=Producto.Categoria.SUERO,
            naturaleza=Producto.Naturaleza.INTERMEDIO,
        )
        equipo = Equipo.objects.create(
            sucursal=planta, codigo="mant-1", nombre="Línea mantequilla",
            tipo=Equipo.Tipo.LINEA,
        )
        proceso = Proceso.objects.create(codigo="mantequilla", nombre="Mantequilla")
        etapa = EtapaProceso.objects.create(
            proceso=proceso, codigo="batir", nombre="Batido",
            tipo=EtapaProceso.Tipo.MANTEQUILLA, orden=1, requiere_calidad=True,
        )
        RutaProducto.objects.create(
            sucursal=planta, producto=mantequilla, proceso=proceso,
            destino_final=RutaProducto.DestinoFinal.ENVASADO,
        )
        ejecucion = EjecucionProceso.objects.create(
            codigo="EJ-MANT-1", etapa=etapa, sucursal=planta,
            equipo=equipo, responsable=self.usuario,
        )
        orden = OrdenProduccion.objects.create(
            sucursal=planta, codigo="OP-MANT-1", producto=mantequilla,
            cantidad_planificada=400, unidad="kg", equipo=equipo,
            estado=OrdenProduccion.Estado.PROGRAMADA,
        )
        self.lote_crema = Lote.objects.create(
            sucursal=planta, codigo_lote="CREMA-1", producto=crema,
            fecha=date(2026, 8, 17), estado=Lote.Estado.PRODUCIDO,
            kg_producidos=Decimal("1000"),
        )
        lote_mantequilla = Lote.objects.create(
            sucursal=planta, codigo_lote="MANT-1", producto=mantequilla,
            orden=orden, fecha=date(2026, 8, 17),
        )
        lote_suero = Lote.objects.create(
            sucursal=planta, codigo_lote="SUERO-1", producto=suero,
            fecha=date(2026, 8, 17),
        )
        self.corrida = CorridaMantequilla.objects.create(
            ejecucion=ejecucion, orden=orden, lote_crema=self.lote_crema,
            lote_mantequilla=lote_mantequilla, lote_suero=lote_suero,
            kg_crema=Decimal("1000"),
        )

    def _preparar_fuente(self):
        tk = Silo.objects.create(
            sucursal=self.planta, codigo="TK-CREMA-TEST",
            tipo=Silo.Tipo.TK_CREMA, capacidad_l=2000,
        )
        MovimientoSilo.objects.create(
            silo=tk, tipo=MovimientoSilo.Tipo.INGRESO, litros=1000,
            fecha_hora=timezone.now(), origen_tipo=MovimientoSilo.OrigenTipo.DESCREMACION,
        )
        origen_proceso = Proceso.objects.create(codigo="origen-mant-test", nombre="Origen crema")
        origen_etapa = EtapaProceso.objects.create(
            proceso=origen_proceso, codigo="origen-mant-test", nombre="Origen crema",
            tipo=EtapaProceso.Tipo.DESCREMACION, orden=1,
        )
        origen = EjecucionProceso.objects.create(
            codigo="EJ-CREMA-TEST", etapa=origen_etapa, sucursal=self.planta,
            estado=EjecucionProceso.Estado.CERRADA,
        )
        ruta_crema = RutaProducto.objects.create(
            sucursal=self.planta, producto=self.lote_crema.producto,
            proceso=self.corrida.ejecucion.etapa.proceso,
        )
        salida = SalidaProceso.objects.create(
            ejecucion=origen, lote=self.lote_crema, silo=tk,
            producto=self.lote_crema.producto, ruta_producto=ruta_crema,
            naturaleza=SalidaProceso.Naturaleza.COPRODUCTO,
            clasificacion=SalidaProceso.Clasificacion.INTERMEDIO,
            destino=SalidaProceso.Destino.SIGUIENTE_PROCESO,
            cantidad=Decimal("1000"), unidad="L",
        )
        analisis = AnalisisSilo.objects.create(
            silo=tk, tomado_en=timezone.now(), grasa=Decimal("40"),
            sng=Decimal("5"), densidad=Decimal("1000"),
            inhibidores_resultado="negativo", metodo="snap",
            hora_lectura=timezone.localtime().time(),
            estado=AnalisisSilo.Estado.CONFIRMADO,
            analista=self.usuario, visualizado_por=self.usuario,
        )
        decision = LiberacionProceso.objects.create(
            salida=salida, analisis_silo=analisis,
            estado=LiberacionProceso.Estado.LIBERADO,
            decidida_por=self.usuario, decidida_en=timezone.now(),
        )
        registrar_firma_salida(decision)
        self.corrida.salida_crema = salida
        self.corrida.save(update_fields=["salida_crema"])
        return salida

    def test_crema_mantequilla_y_merma_conservan_genealogia(self):
        self._preparar_fuente()
        iniciar_mantequilla(corrida_id=self.corrida.pk, usuario=self.usuario, operacion_id=uuid4())
        cerrar_mantequilla(
            corrida_id=self.corrida.pk, usuario=self.usuario,
            kg_mantequilla="990", kg_suero="0", kg_merma="10",
            controles={"humedad": 16}, operacion_id=uuid4(),
        )

        self.corrida.refresh_from_db()
        self.corrida.lote_mantequilla.refresh_from_db()
        self.corrida.lote_suero.refresh_from_db()
        self.corrida.orden.refresh_from_db()
        self.assertEqual(self.corrida.estado, CorridaMantequilla.Estado.PENDIENTE_CALIDAD)
        self.assertEqual(self.corrida.ejecucion.salidas.count(), 2)
        self.assertEqual(self.corrida.lote_mantequilla.estado, Lote.Estado.PRODUCIDO)
        self.assertEqual(self.corrida.lote_mantequilla.kg_producidos, Decimal("990"))
        self.assertIsNone(self.corrida.lote_suero.kg_producidos)
        self.assertEqual(self.corrida.orden.estado, OrdenProduccion.Estado.PENDIENTE_CALIDAD)
        self.assertEqual(
            self.corrida.ejecucion.salidas.get(
                naturaleza=SalidaProceso.Naturaleza.PRINCIPAL
            ).liberacion_calidad.estado,
            LiberacionProceso.Estado.PENDIENTE,
        )
        genealogia = genealogia_lote(self.corrida.lote_mantequilla_id, "atras")
        self.assertIn(self.lote_crema.pk, {n["id"] for n in genealogia["nodos"]})

    def test_no_cierra_si_queda_crema_sin_clasificar(self):
        self._preparar_fuente()
        iniciar_mantequilla(corrida_id=self.corrida.pk, usuario=self.usuario, operacion_id=uuid4())

        with self.assertRaisesMessage(ValidationError, "faltan por clasificar"):
            cerrar_mantequilla(
                corrida_id=self.corrida.pk, usuario=self.usuario,
                kg_mantequilla="420", kg_suero="0", kg_merma="10",
                operacion_id=uuid4(),
            )

        self.corrida.refresh_from_db()
        self.assertEqual(self.corrida.estado, CorridaMantequilla.Estado.EN_PROCESO)
        self.assertEqual(self.corrida.ejecucion.salidas.count(), 0)
        self.assertEqual(AutorizacionReproceso.objects.count(), 0)

    def test_reproceso_se_segrega_en_lote_propio_y_espera_calidad(self):
        self._preparar_fuente()
        iniciar_mantequilla(corrida_id=self.corrida.pk, usuario=self.usuario, operacion_id=uuid4())

        cerrar_mantequilla(
            corrida_id=self.corrida.pk, usuario=self.usuario,
            kg_mantequilla="970", kg_suero="0", kg_merma="10",
            kg_reproceso="20", motivo_reproceso="Textura fuera de objetivo",
            operacion_id=uuid4(),
        )

        self.corrida.refresh_from_db()
        self.assertIsNotNone(self.corrida.lote_reproceso_id)
        self.assertNotEqual(
            self.corrida.lote_reproceso_id, self.corrida.lote_mantequilla_id
        )
        self.assertEqual(self.corrida.lote_reproceso.kg_producidos, Decimal("20"))
        salida = self.corrida.ejecucion.salidas.get(
            naturaleza=SalidaProceso.Naturaleza.REPROCESO
        )
        self.assertEqual(salida.lote, self.corrida.lote_reproceso)
        self.assertEqual(salida.destino, SalidaProceso.Destino.REPROCESO)
        self.assertEqual(salida.cantidad, Decimal("20"))
        autorizacion = self.corrida.lote_reproceso.autorizacion_reproceso
        self.assertEqual(autorizacion.estado, AutorizacionReproceso.Estado.PENDIENTE)
        self.assertEqual(autorizacion.cantidad_kg, Decimal("20"))
        self.assertEqual(autorizacion.motivo, "Textura fuera de objetivo")
        self.corrida.lote_mantequilla.refresh_from_db()
        self.assertEqual(self.corrida.lote_mantequilla.kg_producidos, Decimal("970"))

    def test_api_rechaza_cantidades_negativas_antes_del_dominio(self):
        self._preparar_fuente()
        iniciar_mantequilla(corrida_id=self.corrida.pk, usuario=self.usuario, operacion_id=uuid4())
        self.usuario.perfil.area = PerfilUsuario.Area.CONDENSACION
        self.usuario.perfil.save(update_fields=["area"])
        cliente = APIClient()
        cliente.force_authenticate(self.usuario)

        respuesta = cliente.post(
            f"/api/procesos/mantequillas/{self.corrida.pk}/cerrar/",
            {
                "kg_mantequilla": "420",
                "kg_suero": "0",
                "kg_merma": "-1",
                "kg_reproceso": "1",
                "motivo_reproceso": "Recuperable",
                "operacion_id": str(uuid4()),
            },
            format="json",
        )

        self.assertEqual(respuesta.status_code, 400, respuesta.data)
        self.assertIn("kg_merma", respuesta.data)
        self.assertEqual(self.corrida.ejecucion.salidas.count(), 0)

    def test_calidad_libera_mantequilla_con_analisis_de_lote(self):
        self._preparar_fuente()
        iniciar_mantequilla(corrida_id=self.corrida.pk, usuario=self.usuario, operacion_id=uuid4())
        cerrar_mantequilla(
            corrida_id=self.corrida.pk, usuario=self.usuario,
            kg_mantequilla="990", kg_suero="0", kg_merma="10",
            controles={"humedad": 16}, operacion_id=uuid4(),
        )
        lote = self.corrida.lote_mantequilla
        especificacion = Especificacion.objects.create(
            producto=lote.producto, version=1, vigente_desde=date(2026, 1, 1),
            rangos={"humedad": {"min": 14, "max": 18, "obligatorio": True}},
        )
        analisis = Analisis.objects.create(
            lote=lote, fecha=timezone.localdate(), valores={"humedad": 16},
            especificacion=especificacion,
        )
        calidad = User.objects.create_user("calidad-mantequilla")
        PerfilUsuario.objects.create(
            usuario=calidad, empresa=self.empresa, sucursal=self.planta,
            alcance=PerfilUsuario.Alcance.SUCURSAL,
            rol=Rol.CALIDAD, area=PerfilUsuario.Area.CALIDAD,
        )
        envase = User.objects.create_user("envase-mantequilla")
        PerfilUsuario.objects.create(
            usuario=envase, empresa=self.empresa, sucursal=self.planta,
            alcance=PerfilUsuario.Alcance.SUCURSAL,
            rol=Rol.PRODUCCION, area=PerfilUsuario.Area.ENVASE,
        )
        cliente = APIClient()
        cliente.force_authenticate(calidad)
        salida = self.corrida.ejecucion.salidas.get(
            naturaleza=SalidaProceso.Naturaleza.PRINCIPAL
        )

        respuesta = cliente.post(
            f"/api/calidad/resultados-proceso/{salida.pk}/liberar/",
            {"analisis_lote_id": analisis.pk}, format="json",
        )

        self.assertEqual(respuesta.status_code, 200, respuesta.data)
        salida.liberacion_calidad.refresh_from_db()
        self.corrida.refresh_from_db()
        self.assertEqual(
            salida.liberacion_calidad.estado, LiberacionProceso.Estado.LIBERADO
        )
        self.assertEqual(salida.liberacion_calidad.analisis_lote, analisis)
        self.assertEqual(self.corrida.estado, CorridaMantequilla.Estado.CERRADA)
        aviso = Notificacion.objects.get(
            destinatario=envase,
            tipo="material_liberado_para_continuar",
        )
        self.assertEqual(aviso.accion_url, "/envasado")
        self.assertEqual(aviso.documento_id, salida.pk)

    def test_no_permite_consumir_mas_crema_que_la_disponible(self):
        self._preparar_fuente()
        self.corrida.kg_crema = Decimal("1001")
        self.corrida.save(update_fields=["kg_crema"])

        with self.assertRaises(ValidationError):
            iniciar_mantequilla(corrida_id=self.corrida.pk, usuario=self.usuario, operacion_id=uuid4())

    def test_lote_de_crema_desde_tk_descuenta_su_equivalente_en_litros(self):
        tk = Silo.objects.create(
            sucursal=self.corrida.ejecucion.sucursal,
            codigo="TK-CREMA-MANT", tipo=Silo.Tipo.TK_CREMA, capacidad_l=2000,
        )
        MovimientoSilo.objects.create(
            silo=tk, tipo=MovimientoSilo.Tipo.INGRESO, litros=1000,
            fecha_hora=timezone.now(), origen_tipo=MovimientoSilo.OrigenTipo.DESCREMACION,
        )
        proceso = Proceso.objects.create(codigo="origen-crema", nombre="Origen crema")
        etapa = EtapaProceso.objects.create(
            proceso=proceso, codigo="descremar", nombre="Descremación",
            tipo=EtapaProceso.Tipo.DESCREMACION, orden=1,
        )
        ejecucion = EjecucionProceso.objects.create(
            codigo="EJ-ORIGEN-CREMA", etapa=etapa,
            sucursal=self.corrida.ejecucion.sucursal,
            estado=EjecucionProceso.Estado.CERRADA,
        )
        ruta_crema = RutaProducto.objects.create(
            sucursal=self.planta, producto=self.lote_crema.producto,
            proceso=self.corrida.ejecucion.etapa.proceso,
        )
        salida = SalidaProceso.objects.create(
            ejecucion=ejecucion, lote=self.lote_crema, silo=tk,
            producto=self.lote_crema.producto, ruta_producto=ruta_crema,
            naturaleza=SalidaProceso.Naturaleza.COPRODUCTO,
            clasificacion=SalidaProceso.Clasificacion.INTERMEDIO,
            destino=SalidaProceso.Destino.SIGUIENTE_PROCESO,
            cantidad=Decimal("1000"), unidad="L",
        )
        analisis = AnalisisSilo.objects.create(
            silo=tk, tomado_en=timezone.now(), grasa=Decimal("40"),
            sng=Decimal("5"), densidad=Decimal("1000"),
            inhibidores_resultado="negativo", metodo="snap",
            hora_lectura=timezone.localtime().time(),
            estado=AnalisisSilo.Estado.CONFIRMADO,
            analista=self.usuario, visualizado_por=self.usuario,
        )
        decision = LiberacionProceso.objects.create(
            salida=salida, analisis_silo=analisis,
            estado=LiberacionProceso.Estado.LIBERADO,
            decidida_por=self.usuario, decidida_en=timezone.now(),
        )
        registrar_firma_salida(decision)
        self.corrida.kg_crema = Decimal("200")
        self.corrida.salida_crema = salida
        self.corrida.save(update_fields=["kg_crema", "salida_crema"])

        iniciar_mantequilla(corrida_id=self.corrida.pk, usuario=self.usuario, operacion_id=uuid4())

        consumo = MovimientoSilo.objects.get(
            operacion_id=self.corrida.operacion_id,
            silo=tk, tipo=MovimientoSilo.Tipo.SALIDA,
        )
        self.assertEqual(consumo.litros, Decimal("200.00"))
        self.assertEqual(consumo.lote, self.lote_crema)
        cliente = APIClient()
        cliente.force_authenticate(self.usuario)
        disponibles = cliente.get("/api/procesos/salidas/disponibles/")
        self.assertEqual(disponibles.status_code, 200, disponibles.data)
        material = next(item for item in disponibles.data if item["id"] == salida.pk)
        self.assertEqual(material["cantidad_consumida"], Decimal("200"))
        self.assertEqual(material["cantidad_disponible"], Decimal("800"))
        self.assertEqual(material["lote_codigo"], self.lote_crema.codigo_lote)

    def test_alta_guiada_crea_lote_ejecucion_y_corrida_atomicos(self):
        orden = self.corrida.orden
        equipo = self.corrida.ejecucion.equipo
        salida_crema = self._preparar_fuente()
        self.corrida.delete()

        corrida = crear_mantequilla_guiada(
            orden_id=orden.pk, lote_crema_id=self.lote_crema.pk,
            salida_crema_id=salida_crema.pk,
            equipo_id=equipo.pk, codigo_lote_mantequilla="MANT-GUIADA-1",
            kg_crema="400", usuario=self.usuario, operacion_id=uuid4(),
        )

        self.assertEqual(corrida.lote_mantequilla.codigo_lote, "MANT-GUIADA-1")
        self.assertEqual(corrida.ejecucion.etapa.tipo, EtapaProceso.Tipo.MANTEQUILLA)
        self.assertEqual(corrida.kg_crema, Decimal("400"))

    def test_opciones_alta_muestran_op_crema_y_linea_validas(self):
        salida_crema = self._preparar_fuente()
        cliente = APIClient()
        cliente.force_authenticate(self.usuario)

        respuesta = cliente.get("/api/procesos/mantequillas/opciones-alta/")

        self.assertEqual(respuesta.status_code, 200, respuesta.data)
        self.assertIn(self.corrida.orden_id, [item["id"] for item in respuesta.data["ordenes"]])
        self.assertIn(self.lote_crema.pk, [item["id"] for item in respuesta.data["cremas"]])
        self.assertIn(self.corrida.ejecucion.equipo_id, [item["id"] for item in respuesta.data["equipos"]])
        self.assertIn(salida_crema.pk, [item["salida_crema"] for item in respuesta.data["cremas"]])

    def test_opciones_alta_informan_la_reserva_del_equipo(self):
        self.corrida.ejecucion.estado = EjecucionProceso.Estado.PAUSADA
        self.corrida.ejecucion.save(update_fields=["estado"])
        cliente = APIClient()
        cliente.force_authenticate(self.usuario)

        respuesta = cliente.get("/api/procesos/mantequillas/opciones-alta/")

        self.assertEqual(respuesta.status_code, 200, respuesta.data)
        equipo = next(
            item for item in respuesta.data["equipos"]
            if item["id"] == self.corrida.ejecucion.equipo_id
        )
        self.assertEqual(equipo["ocupado_por"], self.corrida.ejecucion.codigo)

    def test_opciones_alta_separa_crema_pendiente_de_calidad(self):
        salida = self._preparar_fuente()
        salida.liberacion_calidad.delete()
        cliente = APIClient()
        cliente.force_authenticate(self.usuario)

        respuesta = cliente.get("/api/procesos/mantequillas/opciones-alta/")

        self.assertEqual(respuesta.status_code, 200, respuesta.data)
        self.assertNotIn(
            self.lote_crema.pk,
            [item["id"] for item in respuesta.data["cremas"]],
        )
        pendiente = next(
            item for item in respuesta.data["cremas_pendientes_calidad"]
            if item["id"] == self.lote_crema.pk
        )
        self.assertEqual(pendiente["estado_calidad"], "trazabilidad_incompleta")
        self.assertEqual(pendiente["etapa_origen"], "Descremación")

        LiberacionProceso.objects.create(
            salida=salida, estado=LiberacionProceso.Estado.PENDIENTE,
        )
        respuesta = cliente.get("/api/procesos/mantequillas/opciones-alta/")
        pendiente = next(
            item for item in respuesta.data["cremas_pendientes_calidad"]
            if item["id"] == self.lote_crema.pk
        )
        self.assertEqual(pendiente["estado_calidad"], "pendiente")
