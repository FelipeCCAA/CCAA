import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta, timezone as dt_timezone
from decimal import Decimal
from threading import Event, Lock
from unittest.mock import patch

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.db import close_old_connections, connection
from django.test import TestCase, TransactionTestCase
from django.utils import timezone
from rest_framework.test import APIClient

from calidad.models import LiberacionProceso
from maestros.models import (
    Equipo, Especificacion, FormatoEnvasado, Mandante, Producto, Receta,
    RecetaComponente,
)
from procesos.models import EjecucionProceso, EtapaProceso, Proceso, SalidaProceso
from inventario.models import (
    Bodega, ConsumoLoteProduccion, Existencia, ExistenciaProductoTerminado,
    Insumo, LoteInventario,
    MovimientoInventario, MovimientoProductoTerminado, Ubicacion,
)
from inventario.servicios import consumir_receta_produccion, registrar_entrada
from usuarios.models import Empresa, PerfilUsuario, Rol, Sucursal

from .models import Analisis, Lote, PalletProducto, RegistroEnvase
from .servicios import registrar_envasado
from .serializers import RegistroEnvaseSerializer


class EnvasePalletTests(TestCase):
    def setUp(self):
        empresa = Empresa.objects.create(rut="ENV-1", nombre="Empresa envase")
        self.planta = Sucursal.objects.create(
            empresa=empresa, codigo="ENV", nombre="Planta envase"
        )
        self.usuario = User.objects.create_user("operador-envase")
        PerfilUsuario.objects.create(
            usuario=self.usuario, empresa=empresa, sucursal=self.planta,
            rol=Rol.PRODUCCION, area=PerfilUsuario.Area.ENVASE,
        )
        mandante = Mandante.objects.create(
            empresa=empresa, nombre="Mandante envase", codigo_cliente="env"
        )
        self.producto = Producto.objects.create(
            mandante=mandante, nombre="Leche en polvo", unidad_base="kg",
            categoria=Producto.Categoria.LECHE_POLVO,
            formato=Producto.Formato.SACO_25KG,
        )
        self.lote = Lote.objects.create(
            sucursal=self.planta, codigo_lote="L-ENV-1", producto=self.producto,
            fecha=date(2026, 8, 17), estado=Lote.Estado.PRODUCIDO,
            kg_producidos=Decimal("1000"),
        )
        self.envasadora = Equipo.objects.create(
            sucursal=self.planta, codigo="rovema-test", nombre="Rovema test",
            tipo=Equipo.Tipo.ENVASADORA,
        )
        self.formato = FormatoEnvasado.objects.create(
            producto=self.producto, codigo="saco-25kg", nombre="Saco 25 kg",
            kg_neto=25, unidades_maximas_pallet=20,
        )
        self.formato.equipos.add(self.envasadora)
        bolsa = Insumo.objects.create(
            empresa=empresa, codigo="ENV-BASE-BOLSA", nombre="Bolsa de prueba",
            categoria=Insumo.Categoria.EMPAQUE, area=PerfilUsuario.Area.ENVASE,
            unidad=Insumo.Unidad.UN, requiere_calidad=False,
        )
        base = Insumo.objects.create(
            empresa=empresa, codigo="ENV-BASE-PALLET", nombre="Pallet de prueba",
            categoria=Insumo.Categoria.EMPAQUE, area=PerfilUsuario.Area.ENVASE,
            unidad=Insumo.Unidad.UN, requiere_calidad=False,
        )
        receta = Receta.objects.create(
            producto=self.producto, version=1, cantidad_base=Decimal("500"),
            vigente_desde=date(2026, 1, 1), fuente="Receta base de pruebas de Envase",
        )
        RecetaComponente.objects.create(
            receta=receta, insumo=bolsa, cantidad=Decimal("20"), unidad="un",
            fase=RecetaComponente.Fase.ENVASADO,
        )
        RecetaComponente.objects.create(
            receta=receta, insumo=base, cantidad=Decimal("1"), unidad="un",
            fase=RecetaComponente.Fase.ENVASADO,
        )
        bodega = Bodega.objects.create(
            sucursal=self.planta, codigo="B-BASE-ENV", nombre="Envases de prueba",
            area=PerfilUsuario.Area.BODEGA,
        )
        disponible = Ubicacion.objects.create(
            bodega=bodega, codigo="BASE-DISP", tipo=Ubicacion.Tipo.DISPONIBLE,
        )
        for insumo, cantidad in ((bolsa, 1000), (base, 100)):
            lote_material = LoteInventario.objects.create(
                sucursal=self.planta, insumo=insumo, codigo=f"BASE-{insumo.codigo}",
                estado_calidad=LoteInventario.EstadoCalidad.NO_REQUIERE,
            )
            registrar_entrada(
                lote=lote_material, ubicacion=disponible, cantidad=cantidad,
                usuario=self.usuario, documento_tipo="test", documento_id=insumo.pk,
            )

    def registrar(self, *, clave=None, pallets=None):
        inicio = timezone.now() - timedelta(hours=1)
        return registrar_envasado(
            lote_id=self.lote.pk, equipo=self.envasadora, formato_kg="25",
            inicio=inicio, termino=timezone.now(), usuario=self.usuario,
            operacion_id=clave,
            pallets=pallets or [
                {"codigo": "PAL-001", "unidades": 20, "kg_neto": "500"},
                {"codigo": "PAL-002", "unidades": 20, "kg_neto": "500"},
            ],
        )

    def test_registra_envase_y_pallets_sobre_el_mismo_lote(self):
        registro = self.registrar()

        self.assertEqual(registro.lote, self.lote)
        self.assertEqual(registro.unidades, 40)
        self.assertEqual(registro.kg_envasados, Decimal("1000"))
        self.assertEqual(registro.pallets.count(), 2)
        self.assertTrue(all(
            pallet.estado == PalletProducto.Estado.PENDIENTE_CALIDAD
            for pallet in registro.pallets.all()
        ))
        existencias = ExistenciaProductoTerminado.objects.filter(
            pallet__envase=registro, activo=True,
        )
        self.assertEqual(existencias.count(), 2)
        self.assertTrue(all(
            existencia.ubicacion.tipo == Ubicacion.Tipo.CUARENTENA
            for existencia in existencias.select_related("ubicacion")
        ))
        self.assertEqual(MovimientoProductoTerminado.objects.count(), 2)
        datos = RegistroEnvaseSerializer(registro).data
        self.assertIn("operador_nombre", datos)
        self.assertTrue(datos["inicio"])

    def test_registra_big_bag_700kg_como_unidad_logistica_independiente(self):
        self.formato.codigo = "big-bag-700"
        self.formato.nombre = "Big Bag 700 kg"
        self.formato.kg_neto = Decimal("700")
        self.formato.unidades_maximas_pallet = 1
        self.formato.tipo_unidad_logistica = (
            FormatoEnvasado.TipoUnidadLogistica.BIG_BAG
        )
        self.formato.full_clean()
        self.formato.save()
        self.lote.kg_producidos = Decimal("700")
        self.lote.save(update_fields=["kg_producidos"])

        registro = registrar_envasado(
            lote_id=self.lote.pk,
            equipo=self.envasadora,
            formato=self.formato,
            inicio=timezone.now() - timedelta(hours=1),
            termino=timezone.now(),
            usuario=self.usuario,
            pallets=[{"codigo": "BB-700-001", "unidades": 1, "kg_neto": "700"}],
        )

        unidad = registro.pallets.get()
        self.assertEqual(unidad.tipo_unidad_logistica, "big_bag")
        self.assertEqual(unidad.kg_neto, Decimal("700"))
        self.assertEqual(
            RegistroEnvaseSerializer(registro).data["pallets"][0][
                "tipo_unidad_logistica_etiqueta"
            ],
            "Big Bag",
        )

    def test_clave_idempotente_no_duplica_pallets(self):
        clave = uuid.uuid4()
        inicio = timezone.now() - timedelta(hours=1)
        datos = dict(
            lote_id=self.lote.pk, equipo=self.envasadora, formato=self.formato,
            inicio=inicio, termino=inicio + timedelta(hours=1), usuario=self.usuario,
            operacion_id=clave, observacion="cierre de turno",
            controles={"sellado": "conforme"},
            pallets=[{"codigo": "PAL-001", "unidades": 20, "kg_neto": "500"}],
        )
        primero = registrar_envasado(**datos)
        segundo = registrar_envasado(**datos)

        self.assertEqual(primero.pk, segundo.pk)
        self.assertEqual(RegistroEnvase.objects.count(), 1)
        self.assertEqual(PalletProducto.objects.count(), 1)
        self.assertEqual(ExistenciaProductoTerminado.objects.count(), 1)
        self.assertEqual(MovimientoProductoTerminado.objects.count(), 1)
        self.assertEqual(ConsumoLoteProduccion.objects.filter(fase="envasado").count(), 1)

        # La comparación usa el pedido original, aunque cambie el estado vivo.
        self.formato.nombre = "Nombre posterior"
        self.formato.save(update_fields=["nombre"])
        self.assertEqual(registrar_envasado(**datos).pk, primero.pk)
        distinto_huso = dt_timezone(timedelta(hours=-4))
        self.assertEqual(registrar_envasado(**{
            **datos,
            "inicio": inicio.astimezone(distinto_huso),
            "termino": (inicio + timedelta(hours=1)).astimezone(distinto_huso),
        }).pk, primero.pk)

    def test_misma_clave_con_otro_pedido_rechaza_sin_efectos(self):
        clave = uuid.uuid4()
        inicio = timezone.now() - timedelta(hours=1)
        datos = dict(
            lote_id=self.lote.pk, equipo=self.envasadora, formato=self.formato,
            inicio=inicio, termino=inicio + timedelta(hours=1), usuario=self.usuario,
            operacion_id=clave, observacion="original",
            pallets=[{"codigo": "PAL-001", "unidades": 20, "kg_neto": "500"}],
        )
        registrar_envasado(**datos)
        with self.assertRaisesMessage(ValidationError, "datos distintos"):
            registrar_envasado(**{**datos, "observacion": "alterado"})
        with self.assertRaisesMessage(ValidationError, "datos distintos"):
            registrar_envasado(**{**datos, "pallets": [
                {"codigo": "PAL-OTRO", "unidades": 20, "kg_neto": "500"}
            ]})
        self.assertEqual(RegistroEnvase.objects.count(), 1)
        self.assertEqual(PalletProducto.objects.count(), 1)
        self.assertEqual(MovimientoProductoTerminado.objects.count(), 1)

    def test_api_replay_respeta_actor_y_recupera_con_catalogos_inactivos(self):
        clave = str(uuid.uuid4())
        inicio = timezone.now() - timedelta(hours=1)
        pedido = {
            "operacion_id": clave, "lote": self.lote.pk,
            "equipo": self.envasadora.pk, "formato": self.formato.pk,
            "inicio": inicio.isoformat(),
            "termino": (inicio + timedelta(hours=1)).isoformat(),
            "observacion": "turno original",
            "pallets_datos": [{"codigo": "PAL-API-01", "unidades": 20, "kg_neto": "500"}],
        }
        cliente = APIClient()
        cliente.force_authenticate(self.usuario)
        primero = cliente.post("/api/produccion/envases/", pedido, format="json")
        self.assertEqual(primero.status_code, 201, primero.data)

        self.formato.activo = False
        self.formato.save(update_fields=["activo"])
        self.envasadora.activo = False
        self.envasadora.save(update_fields=["activo"])
        replay = cliente.post("/api/produccion/envases/", pedido, format="json")
        self.assertEqual(replay.status_code, 201, replay.data)
        self.assertEqual(replay.data["id"], primero.data["id"])

        otro = User.objects.create_user("otro-operador-envase")
        PerfilUsuario.objects.create(
            usuario=otro, empresa=self.planta.empresa, sucursal=self.planta,
            rol=Rol.PRODUCCION, area=PerfilUsuario.Area.ENVASE,
        )
        cliente.force_authenticate(otro)
        ajeno = cliente.post("/api/produccion/envases/", pedido, format="json")
        self.assertEqual(ajeno.status_code, 400, ajeno.data)
        self.assertIn("datos distintos", str(ajeno.data))
        self.assertEqual(RegistroEnvase.objects.count(), 1)
        self.assertEqual(MovimientoProductoTerminado.objects.count(), 1)

    def test_api_exige_clave_de_operacion(self):
        inicio = timezone.now() - timedelta(hours=1)
        cliente = APIClient()
        cliente.force_authenticate(self.usuario)
        respuesta = cliente.post("/api/produccion/envases/", {
            "lote": self.lote.pk, "equipo": self.envasadora.pk,
            "formato": self.formato.pk, "inicio": inicio.isoformat(),
            "termino": (inicio + timedelta(hours=1)).isoformat(),
            "pallets_datos": [{"codigo": "PAL-SIN-CLAVE", "unidades": 20, "kg_neto": "500"}],
        }, format="json")
        self.assertEqual(respuesta.status_code, 400, respuesta.data)
        self.assertIn("operacion_id", respuesta.data)
        self.assertFalse(RegistroEnvase.objects.exists())

    def test_registro_legado_sin_firma_no_inventa_pedido_para_replay(self):
        clave = uuid.uuid4()
        inicio = timezone.now() - timedelta(hours=1)
        datos = dict(
            lote_id=self.lote.pk, equipo=self.envasadora, formato=self.formato,
            inicio=inicio, termino=inicio + timedelta(hours=1), usuario=self.usuario,
            operacion_id=clave,
            pallets=[{"codigo": "PAL-LEGADO", "unidades": 20, "kg_neto": "500"}],
        )
        registro = registrar_envasado(**datos)
        RegistroEnvase.objects.filter(pk=registro.pk).update(solicitud_firma=None)
        with self.assertRaisesMessage(ValidationError, "histórico sin pedido verificable"):
            registrar_envasado(**datos)
        cliente = APIClient()
        cliente.force_authenticate(self.usuario)
        consulta = cliente.get(
            "/api/produccion/envases/por-operacion/", {"operacion_id": str(clave)}
        )
        self.assertEqual(consulta.status_code, 200, consulta.data)
        self.assertEqual(consulta.data["id"], registro.pk)
        self.assertEqual(consulta.data["pallets"][0]["codigo"], "PAL-LEGADO")
        self.assertEqual(RegistroEnvase.objects.count(), 1)

    def test_falla_tardia_revierte_cierre_consumos_y_auditoria(self):
        from auditoria.models import RegistroAuditoria

        inicio = timezone.now() - timedelta(hours=1)
        saldos = list(Existencia.objects.order_by("pk").values_list("pk", "cantidad_fisica"))
        auditoria_antes = RegistroAuditoria.objects.count()
        with patch("inventario.servicios.registrar_pallets_producidos", side_effect=ValidationError("fallo tardío")):
            with self.assertRaisesMessage(ValidationError, "fallo tardío"):
                registrar_envasado(
                    lote_id=self.lote.pk, equipo=self.envasadora, formato=self.formato,
                    inicio=inicio, termino=inicio + timedelta(hours=1), usuario=self.usuario,
                    operacion_id=uuid.uuid4(),
                    pallets=[{"codigo": "PAL-001", "unidades": 20, "kg_neto": "500"}],
                )
        self.assertFalse(RegistroEnvase.objects.exists())
        self.assertFalse(PalletProducto.objects.exists())
        self.assertFalse(ConsumoLoteProduccion.objects.filter(fase="envasado").exists())
        self.assertFalse(MovimientoInventario.objects.filter(tipo="consumo").exists())
        self.assertEqual(ExistenciaProductoTerminado.objects.count(), 0)
        self.assertEqual(MovimientoProductoTerminado.objects.count(), 0)
        self.assertEqual(auditoria_antes, RegistroAuditoria.objects.count())
        self.assertEqual(saldos, list(Existencia.objects.order_by("pk").values_list("pk", "cantidad_fisica")))

    def test_no_permite_envasar_mas_de_lo_producido(self):
        with self.assertRaises(ValidationError):
            self.registrar(pallets=[
                {"codigo": "PAL-EXCESO", "unidades": 41, "kg_neto": "1025"}
            ])

        self.assertEqual(RegistroEnvase.objects.count(), 0)
        self.assertEqual(PalletProducto.objects.count(), 0)

    def test_formato_limita_unidades_y_equipo_autorizado(self):
        otra = Equipo.objects.create(
            sucursal=self.planta, codigo="otra-env", nombre="Otra envasadora",
            tipo=Equipo.Tipo.ENVASADORA,
        )
        inicio = timezone.now() - timedelta(hours=1)
        with self.assertRaisesMessage(ValidationError, "no está autorizado"):
            registrar_envasado(
                lote_id=self.lote.pk, equipo=otra, formato=self.formato,
                inicio=inicio, termino=timezone.now(), usuario=self.usuario,
                pallets=[{"codigo": "PAL-EQUIPO", "unidades": 20, "kg_neto": 500}],
            )
        with self.assertRaisesMessage(ValidationError, "máximo 20 unidades"):
            registrar_envasado(
                lote_id=self.lote.pk, equipo=self.envasadora, formato=self.formato,
                inicio=inicio, termino=timezone.now(), usuario=self.usuario,
                pallets=[{"codigo": "PAL-MAX", "unidades": 21, "kg_neto": 525}],
            )

        self.assertEqual(RegistroEnvase.objects.count(), 0)

    def test_no_crea_pallet_si_falta_receta_de_materiales_de_envase(self):
        Receta.objects.filter(producto=self.producto).delete()

        with self.assertRaisesMessage(ValidationError, "receta de Envasado"):
            self.registrar()

        self.assertEqual(RegistroEnvase.objects.count(), 0)
        self.assertEqual(PalletProducto.objects.count(), 0)

    def test_no_crea_pallet_si_el_material_de_envase_no_tiene_stock(self):
        Existencia.objects.filter(
            lote__insumo__codigo="ENV-BASE-BOLSA"
        ).update(cantidad_fisica=0, cantidad_reservada=0)

        with self.assertRaisesMessage(ValidationError, "Stock insuficiente"):
            self.registrar()

        self.assertEqual(RegistroEnvase.objects.count(), 0)
        self.assertEqual(PalletProducto.objects.count(), 0)

    def test_un_producto_intermedio_no_aparece_como_producto_envasable(self):
        self.producto.naturaleza = Producto.Naturaleza.INTERMEDIO
        self.producto.save(update_fields=["naturaleza"])

        with self.assertRaises(ValidationError):
            self.registrar(pallets=[
                {"codigo": "PAL-INTERMEDIO", "unidades": 20, "kg_neto": "500"}
            ])

        self.assertEqual(RegistroEnvase.objects.count(), 0)

    def test_mantequilla_exige_liberacion_intermedia_antes_de_envasar(self):
        proceso = Proceso.objects.create(codigo="ruta-mant-env", nombre="Mantequilla")
        etapa = EtapaProceso.objects.create(
            proceso=proceso, codigo="batido", nombre="Batido",
            tipo=EtapaProceso.Tipo.MANTEQUILLA, orden=1, requiere_calidad=True,
        )
        ejecucion = EjecucionProceso.objects.create(
            codigo="EJ-MANT-ENV", etapa=etapa, sucursal=self.planta,
            estado=EjecucionProceso.Estado.PENDIENTE_CONTROL,
        )
        salida = SalidaProceso.objects.create(
            ejecucion=ejecucion, lote=self.lote,
            naturaleza=SalidaProceso.Naturaleza.PRINCIPAL,
            clasificacion=SalidaProceso.Clasificacion.GRANEL,
            destino=SalidaProceso.Destino.ENVASADO,
            cantidad=Decimal("1000"), unidad="kg",
        )
        decision = LiberacionProceso.objects.create(salida=salida)

        cliente = APIClient()
        cliente.force_authenticate(self.usuario)
        bandeja_bloqueada = cliente.get("/api/produccion/envases/bandeja/")

        self.assertEqual(bandeja_bloqueada.status_code, 200, bandeja_bloqueada.data)
        self.assertEqual(bandeja_bloqueada.data["materiales"], [])
        self.assertEqual(len(bandeja_bloqueada.data["bloqueados_calidad"]), 1)
        self.assertEqual(
            bandeja_bloqueada.data["bloqueados_calidad"][0]["lote_codigo"],
            self.lote.codigo_lote,
        )
        self.assertIn(
            "pendiente de aprobación de Calidad",
            bandeja_bloqueada.data["bloqueados_calidad"][0]["motivo_bloqueo"],
        )

        intento_api = cliente.post(
            "/api/produccion/envases/",
            {
                "operacion_id": str(uuid.uuid4()),
                "lote": self.lote.pk,
                "equipo": self.envasadora.pk,
                "formato": self.formato.pk,
                "inicio": (timezone.now() - timedelta(hours=1)).isoformat(),
                "termino": timezone.now().isoformat(),
                "pallets_datos": [
                    {"codigo": "PAL-BLOQUEADO", "unidades": 40, "kg_neto": "1000"}
                ],
            },
            format="json",
        )
        self.assertEqual(intento_api.status_code, 400, intento_api.data)
        self.assertIn("pendiente de aprobación", str(intento_api.data))
        self.assertFalse(RegistroEnvase.objects.exists())

        with self.assertRaisesMessage(ValidationError, "pendiente de aprobación"):
            self.registrar()

        especificacion = Especificacion.objects.create(
            producto=self.producto, version=1, vigente_desde=date(2026, 1, 1),
            rangos={"humedad": {"min": 0, "max": 5, "obligatorio": True}},
        )
        analisis = Analisis.objects.create(
            lote=self.lote, fecha=date(2026, 8, 17),
            valores={"humedad": 3}, especificacion=especificacion,
        )
        decision.estado = LiberacionProceso.Estado.LIBERADO
        decision.analisis_lote = analisis
        decision.decidida_por = self.usuario
        decision.decidida_en = timezone.now()
        decision.full_clean()
        decision.save()

        bandeja_liberada = cliente.get("/api/produccion/envases/bandeja/")
        self.assertEqual(bandeja_liberada.status_code, 200, bandeja_liberada.data)
        self.assertEqual(bandeja_liberada.data["bloqueados_calidad"], [])
        self.assertEqual(len(bandeja_liberada.data["materiales"]), 1)

        registro = self.registrar()
        self.assertEqual(registro.lote, self.lote)

    def test_endpoint_entrega_solo_material_liberado_con_formato(self):
        proceso = Proceso.objects.create(codigo="ruta-env-lista", nombre="Ruta envase")
        etapa = EtapaProceso.objects.create(
            proceso=proceso, codigo="secar-listo", nombre="Secado listo",
            tipo=EtapaProceso.Tipo.SECADO, orden=1, requiere_calidad=True,
        )
        ejecucion = EjecucionProceso.objects.create(
            codigo="EJ-ENV-LISTA", etapa=etapa, sucursal=self.planta,
            estado=EjecucionProceso.Estado.CERRADA,
        )
        salida = SalidaProceso.objects.create(
            ejecucion=ejecucion, lote=self.lote, producto=self.producto,
            naturaleza=SalidaProceso.Naturaleza.PRINCIPAL,
            clasificacion=SalidaProceso.Clasificacion.GRANEL,
            destino=SalidaProceso.Destino.ENVASADO,
            cantidad=Decimal("1000"), unidad="kg",
        )
        LiberacionProceso.objects.create(
            salida=salida, estado=LiberacionProceso.Estado.LIBERADO,
        )
        cliente = APIClient()
        cliente.force_authenticate(self.usuario)

        respuesta = cliente.get("/api/produccion/envases/materiales-habilitados/")

        self.assertEqual(respuesta.status_code, 200, respuesta.data)
        self.assertEqual(len(respuesta.data), 1)
        self.assertEqual(respuesta.data[0]["lote_id"], self.lote.pk)
        self.assertEqual(respuesta.data[0]["formato"], Producto.Formato.SACO_25KG)
        self.assertEqual(respuesta.data[0]["formato_kg"], Decimal("25"))
        self.assertEqual(respuesta.data[0]["formato_id"], self.formato.pk)
        self.assertEqual(
            respuesta.data[0]["equipos"][0]["id"], self.envasadora.pk
        )
        self.assertEqual(respuesta.data[0]["unidades_disponibles"], 40)
        self.assertEqual(respuesta.data[0]["cantidad_envasable"], Decimal("1000"))
        self.assertEqual(respuesta.data[0]["remanente_kg"], Decimal("0"))
        self.assertTrue(respuesta.data[0]["receta_envase_completa"])
        self.assertEqual(len(respuesta.data[0]["materiales_envase"]), 2)
        self.assertTrue(all(
            item["stock_disponible"] > 0
            for item in respuesta.data[0]["materiales_envase"]
        ))
        self.assertTrue(respuesta.data[0]["puede_envasar"])

        bandeja = cliente.get("/api/produccion/envases/bandeja/")
        self.assertEqual(bandeja.status_code, 200, bandeja.data)
        self.assertEqual(len(bandeja.data["materiales"]), 1)
        self.assertEqual(bandeja.data["materiales"][0]["pallets_total"], 0)
        self.assertEqual(bandeja.data["registros_recientes"], [])

        existencia_bolsa = Existencia.objects.get(
            lote__insumo__codigo="ENV-BASE-BOLSA"
        )
        existencia_bolsa.cantidad_fisica = 1
        existencia_bolsa.save(update_fields=["cantidad_fisica"])

        limitada = cliente.get("/api/produccion/envases/materiales-habilitados/")

        self.assertEqual(limitada.status_code, 200, limitada.data)
        self.assertEqual(limitada.data[0]["unidades_por_producto"], 40)
        self.assertEqual(limitada.data[0]["unidades_disponibles"], 1)
        self.assertEqual(limitada.data[0]["cantidad_envasable"], Decimal("25"))
        self.assertEqual(limitada.data[0]["pendiente_materiales_kg"], Decimal("975"))
        self.assertIn("espera de materiales", limitada.data[0]["advertencia_materiales"])

        existencia_bolsa.cantidad_fisica = 1000
        existencia_bolsa.save(update_fields=["cantidad_fisica"])

        self.producto.formato = Producto.Formato.CAJA_20KG
        self.producto.save(update_fields=["formato"])
        self.formato.nombre = "Caja 20 kg"
        self.formato.codigo = "caja-20kg"
        self.formato.kg_neto = 20
        self.formato.unidades_maximas_pallet = 25
        self.formato.save()
        self.lote.kg_producidos = Decimal("31")
        self.lote.save(update_fields=["kg_producidos"])
        salida.cantidad = Decimal("31")
        salida.save(update_fields=["cantidad"])

        respuesta = cliente.get("/api/produccion/envases/materiales-habilitados/")

        self.assertEqual(respuesta.status_code, 200, respuesta.data)
        self.assertEqual(respuesta.data[0]["unidades_disponibles"], 1)
        self.assertEqual(respuesta.data[0]["cantidad_envasable"], Decimal("20"))
        self.assertEqual(respuesta.data[0]["remanente_kg"], Decimal("11"))
        self.assertTrue(respuesta.data[0]["puede_envasar"])

        inicio = timezone.now() - timedelta(hours=1)
        registrar_envasado(
            lote_id=self.lote.pk,
            equipo=self.envasadora,
            formato_kg="20",
            inicio=inicio,
            termino=timezone.now(),
            usuario=self.usuario,
            pallets=[
                {"codigo": "PAL-MANT-20", "unidades": 1, "kg_neto": "20"}
            ],
        )

        respuesta = cliente.get("/api/produccion/envases/materiales-habilitados/")

        self.assertEqual(respuesta.status_code, 200, respuesta.data)
        self.assertEqual(respuesta.data[0]["unidades_disponibles"], 0)
        self.assertEqual(respuesta.data[0]["cantidad_disponible"], Decimal("11"))
        self.assertFalse(respuesta.data[0]["puede_envasar"])
        self.assertIn("menos que una unidad completa", respuesta.data[0]["motivo_bloqueo"])

    def test_secado_exige_liberacion_intermedia_antes_de_envasar(self):
        proceso = Proceso.objects.create(codigo="ruta-sec-env", nombre="Polvo")
        etapa = EtapaProceso.objects.create(
            proceso=proceso, codigo="secado", nombre="Secado",
            tipo=EtapaProceso.Tipo.SECADO, orden=1, requiere_calidad=True,
        )
        ejecucion = EjecucionProceso.objects.create(
            codigo="EJ-SEC-ENV", etapa=etapa, sucursal=self.planta,
            estado=EjecucionProceso.Estado.CERRADA,
        )
        salida = SalidaProceso.objects.create(
            ejecucion=ejecucion, lote=self.lote,
            naturaleza=SalidaProceso.Naturaleza.PRINCIPAL,
            clasificacion=SalidaProceso.Clasificacion.GRANEL,
            destino=SalidaProceso.Destino.PENDIENTE,
            cantidad=Decimal("1000"), unidad="kg",
        )
        LiberacionProceso.objects.create(salida=salida)

        with self.assertRaisesMessage(ValidationError, "Secado está pendiente"):
            self.registrar()

    def test_simulacion_pallet_25kg_consume_envases_y_respeta_500kg(self):
        """20 sacos + 1 pallet físico producen exactamente un pallet de 500 kg."""
        Receta.objects.filter(producto=self.producto).delete()
        bolsa = Insumo.objects.create(
            empresa=self.planta.empresa, codigo="ENV-SACO-25", nombre="Saco 25 kg",
            categoria=Insumo.Categoria.EMPAQUE, area=PerfilUsuario.Area.ENVASE,
            unidad=Insumo.Unidad.UN, requiere_calidad=False,
        )
        base = Insumo.objects.create(
            empresa=self.planta.empresa, codigo="ENV-PALLET-500", nombre="Pallet base 500 kg",
            categoria=Insumo.Categoria.EMPAQUE, area=PerfilUsuario.Area.ENVASE,
            unidad=Insumo.Unidad.UN, requiere_calidad=False,
        )
        receta = Receta.objects.create(
            producto=self.producto, version=1, cantidad_base=Decimal("500"),
            vigente_desde=date(2026, 1, 1), fuente="Simulación pallet 25 kg",
        )
        RecetaComponente.objects.create(
            receta=receta, insumo=bolsa, cantidad=Decimal("20"), unidad="un",
            fase=RecetaComponente.Fase.ENVASADO,
        )
        RecetaComponente.objects.create(
            receta=receta, insumo=base, cantidad=Decimal("1"), unidad="un",
            fase=RecetaComponente.Fase.ENVASADO,
        )
        bodega = Bodega.objects.create(
            sucursal=self.planta, codigo="B-ENV", nombre="Envases",
            area=PerfilUsuario.Area.BODEGA,
        )
        disponible = Ubicacion.objects.create(
            bodega=bodega, codigo="ENV-DISP", tipo=Ubicacion.Tipo.DISPONIBLE,
        )
        for insumo, cantidad in ((bolsa, 20), (base, 1)):
            lote_material = LoteInventario.objects.create(
                sucursal=self.planta, insumo=insumo, codigo=f"SIM-{insumo.codigo}",
                estado_calidad=LoteInventario.EstadoCalidad.NO_REQUIERE,
            )
            registrar_entrada(
                lote=lote_material, ubicacion=disponible, cantidad=cantidad,
                usuario=self.usuario, documento_tipo="simulacion", documento_id=insumo.pk,
            )

        self.lote.kg_producidos = Decimal("500")
        self.lote.save(update_fields=["kg_producidos"])
        consumo_proceso, movimientos_proceso = consumir_receta_produccion(
            lote_produccion=self.lote,
            usuario=self.usuario,
            permitir_vacio=True,
        )
        self.assertEqual(consumo_proceso.fase, ConsumoLoteProduccion.Fase.PROCESO)
        self.assertEqual(movimientos_proceso, [])
        existencias_simulacion = Existencia.objects.filter(
            lote__insumo__in=[bolsa, base]
        )
        self.assertTrue(all(e.cantidad_fisica > 0 for e in existencias_simulacion))

        registro = self.registrar(pallets=[
            {"codigo": "PAL-SIM-25KG", "unidades": 20, "kg_neto": "500"}
        ])

        pallet = registro.pallets.get()
        consumo = ConsumoLoteProduccion.objects.get(
            lote_produccion=self.lote,
            fase=ConsumoLoteProduccion.Fase.ENVASADO,
        )
        movimientos = MovimientoInventario.objects.filter(tipo="consumo")
        self.assertEqual((pallet.unidades, pallet.kg_neto), (20, Decimal("500")))
        self.assertEqual(consumo.kg_base, Decimal("500"))
        self.assertEqual(consumo.operacion_id, registro.operacion_id)
        self.assertEqual(
            sorted(m.cantidad for m in movimientos), [Decimal("1.000"), Decimal("20.000")]
        )
        self.assertTrue(all(
            e.cantidad_fisica == 0
            for e in Existencia.objects.filter(lote__insumo__in=[bolsa, base])
        ))
        self.assertEqual(MovimientoInventario.objects.filter(tipo="consumo").count(), 2)


class EnvaseConcurrenciaTests(TransactionTestCase):
    """Dos conexiones reales compiten por una operación de envasado."""

    def setUp(self):
        EnvasePalletTests.setUp(self)

    def _competir(self, *, cambiar_segundo):
        if connection.vendor != "postgresql":
            self.skipTest("El bloqueo de operación requiere PostgreSQL")
        from inventario import servicios as servicios_inventario

        clave = uuid.uuid4()
        inicio = timezone.now() - timedelta(hours=1)
        datos = dict(
            lote_id=self.lote.pk, equipo=self.envasadora.pk,
            formato=self.formato.pk, inicio=inicio,
            termino=inicio + timedelta(hours=1), usuario=self.usuario.pk,
            operacion_id=clave,
            pallets=[{"codigo": "PAL-CONCURRENT", "unidades": 20, "kg_neto": "500"}],
        )
        primero_en_escritura = Event()
        liberar_primero = Event()
        segundo_iniciado = Event()
        guardia = Lock()
        llamadas = 0
        original = servicios_inventario.registrar_pallets_producidos

        def detener_primero(*args, **kwargs):
            nonlocal llamadas
            with guardia:
                llamadas += 1
                primera = llamadas == 1
            if primera:
                primero_en_escritura.set()
                if not liberar_primero.wait(10):
                    raise AssertionError("El test agotó la espera del primer cierre")
            return original(*args, **kwargs)

        def ejecutar(pedido, senal=None):
            close_old_connections()
            try:
                if senal:
                    senal.set()
                return registrar_envasado(
                    **{**pedido,
                       "equipo": Equipo.objects.get(pk=pedido["equipo"]),
                       "usuario": User.objects.get(pk=pedido["usuario"])}
                ).pk
            finally:
                connection.close()

        segundo = {**datos, "observacion": "pedido diferente"} if cambiar_segundo else datos
        with patch.object(servicios_inventario, "registrar_pallets_producidos", detener_primero):
            with ThreadPoolExecutor(max_workers=2) as grupo:
                futuro_primero = grupo.submit(ejecutar, datos)
                self.assertTrue(primero_en_escritura.wait(10))
                futuro_segundo = grupo.submit(ejecutar, segundo, segundo_iniciado)
                self.assertTrue(segundo_iniciado.wait(10))
                try:
                    self.assertFalse(futuro_segundo.done())
                finally:
                    liberar_primero.set()
                id_primero = futuro_primero.result(timeout=10)
                if cambiar_segundo:
                    with self.assertRaisesMessage(ValidationError, "datos distintos"):
                        futuro_segundo.result(timeout=10)
                else:
                    self.assertEqual(futuro_segundo.result(timeout=10), id_primero)
        self.assertEqual(RegistroEnvase.objects.count(), 1)
        self.assertEqual(PalletProducto.objects.count(), 1)
        self.assertEqual(ConsumoLoteProduccion.objects.filter(fase="envasado").count(), 1)
        self.assertEqual(MovimientoProductoTerminado.objects.count(), 1)

    def test_dos_conexiones_misma_clave_mismo_pedido(self):
        self._competir(cambiar_segundo=False)

    def test_dos_conexiones_misma_clave_distinto_pedido(self):
        self._competir(cambiar_segundo=True)
