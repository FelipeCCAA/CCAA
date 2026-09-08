"""Prueba integral del suero recibido externamente hasta producto terminado.

Los valores y rangos de este archivo son datos aislados de prueba. No son
parámetros operacionales ni especificaciones oficiales de la planta.
"""

from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from calidad.models import Liberacion, LiberacionProceso, RegistroCalidad
from inventario.models import (
    Bodega,
    DetalleOrdenCompra,
    Existencia,
    ExistenciaProductoTerminado,
    InspeccionMaterial,
    Insumo,
    LoteInventario,
    MovimientoInventario,
    OrdenCompra,
    PlantillaInspeccion,
    Proveedor,
    RecepcionCompra,
    Ubicacion,
)
from inventario.servicios import (
    decidir_inspeccion,
    recibir_detalle_compra,
    registrar_entrada,
    trasladar_existencia,
)
from maestros.models import (
    DocumentoLiberacion,
    Equipo,
    Especificacion,
    FormatoEnvasado,
    Mandante,
    Producto,
    Receta,
    RecetaComponente,
)
from produccion.models import Analisis, Lote, OrdenProduccion, PalletProducto
from produccion.servicios import registrar_envasado
from usuarios.models import Empresa, PerfilUsuario, Rol, Sucursal

from .models import CorridaSecado, EtapaProceso, Proceso, RutaProducto, SalidaProceso


class FlujoSueroCompletoTests(TestCase):
    def setUp(self):
        DocumentoLiberacion.objects.all().delete()
        self.empresa = Empresa.objects.create(rut="E2E-SUERO", nombre="E2E suero")
        self.planta = Sucursal.objects.create(
            empresa=self.empresa, codigo="E2E-SUE", nombre="Planta E2E suero"
        )
        self.receptor = self._usuario(
            "e2e-recepcion-suero", Rol.OPERARIO, PerfilUsuario.Area.BODEGA
        )
        self.calidad = self._usuario("e2e-calidad-suero", Rol.CALIDAD, PerfilUsuario.Area.CALIDAD)
        self.secador = self._usuario("e2e-secador-suero", Rol.PRODUCCION, PerfilUsuario.Area.SECADO)
        self.envasador = self._usuario("e2e-envase-suero", Rol.PRODUCCION, PerfilUsuario.Area.ENVASE)

        self.bodega_mp = Bodega.objects.create(
            sucursal=self.planta, codigo="BMP-SUE", nombre="Materia prima externa",
            area=PerfilUsuario.Area.BODEGA,
        )
        self.cuarentena = Ubicacion.objects.create(
            bodega=self.bodega_mp, codigo="SUE-CUAR", tipo=Ubicacion.Tipo.CUARENTENA,
        )
        self.disponible = Ubicacion.objects.create(
            bodega=self.bodega_mp, codigo="SUE-DISP", tipo=Ubicacion.Tipo.DISPONIBLE,
        )
        self.insumo_suero = Insumo.objects.create(
            empresa=self.empresa, codigo="SUE-EXT-E2E", nombre="Suero externo E2E",
            categoria=Insumo.Categoria.MATERIA_PRIMA,
            area=PerfilUsuario.Area.SECADO, unidad=Insumo.Unidad.KG,
            requiere_calidad=True, requiere_lote=True,
        )
        PlantillaInspeccion.objects.create(
            empresa=self.empresa, nombre="Recepción suero E2E", insumo=self.insumo_suero,
            version=1, vigente_desde=date(2026, 1, 1),
            campos=[{"clave": "identidad", "etiqueta": "Identidad", "obligatorio": True}],
        )
        proveedor = Proveedor.objects.create(
            empresa=self.empresa, rut="E2E-SUE-1", nombre="Proveedor suero E2E"
        )
        orden_compra = OrdenCompra.objects.create(
            numero="OC-SUERO-E2E", proveedor=proveedor, bodega_entrega=self.bodega_mp,
            estado=OrdenCompra.Estado.ENVIADA,
        )
        self.detalle_compra = DetalleOrdenCompra.objects.create(
            orden=orden_compra, insumo=self.insumo_suero,
            cantidad=Decimal("1000"), costo_unitario=Decimal("1"),
        )
        self.recepcion = RecepcionCompra.objects.create(
            orden=orden_compra, guia="GUIA-SUERO-E2E", receptor=self.receptor,
        )

        mandante = Mandante.objects.create(
            empresa=self.empresa, codigo_cliente="E2E-SUE", nombre="Mandante suero E2E"
        )
        self.producto = Producto.objects.create(
            mandante=mandante, nombre="Suero en polvo E2E",
            familia=Producto.Familia.POLVO, categoria=Producto.Categoria.SUERO,
            naturaleza=Producto.Naturaleza.TERMINADO,
            formato=Producto.Formato.BIG_BAG, unidad_base="kg",
        )
        self.especificacion = Especificacion.objects.create(
            producto=self.producto, version=1, vigente_desde=date(2026, 1, 1),
            fuente="Rango simulado, exclusivo para prueba automatizada",
            rangos={"humedad": {"min": 0, "max": 10, "obligatorio": True}},
        )
        self.torre = Equipo.objects.create(
            sucursal=self.planta, codigo="TOR-SUE-E2E", nombre="Torre suero E2E",
            tipo=Equipo.Tipo.TORRE,
        )
        self.envasadora = Equipo.objects.create(
            sucursal=self.planta, codigo="ENV-SUE-E2E", nombre="Envasadora Big Bag E2E",
            tipo=Equipo.Tipo.ENVASADORA,
        )
        proceso = Proceso.objects.create(codigo="ruta-suero-e2e", nombre="Ruta suero E2E")
        EtapaProceso.objects.create(
            proceso=proceso, codigo="secado-suero-e2e", nombre="Secado suero",
            tipo=EtapaProceso.Tipo.SECADO, orden=1, requiere_calidad=True,
        )
        EtapaProceso.objects.create(
            proceso=proceso, codigo="envase-suero-e2e", nombre="Envasado suero",
            tipo=EtapaProceso.Tipo.ENVASADO, orden=2,
        )
        RutaProducto.objects.create(
            sucursal=self.planta, producto=self.producto, proceso=proceso,
            insumo_origen=self.insumo_suero,
            destino_final=RutaProducto.DestinoFinal.ENVASADO,
        )
        self.orden_produccion = OrdenProduccion.objects.create(
            sucursal=self.planta, codigo="OP-SUERO-E2E", producto=self.producto,
            cantidad_planificada=Decimal("700"), unidad="kg",
            estado=OrdenProduccion.Estado.PROGRAMADA,
        )

        self.formato = FormatoEnvasado.objects.create(
            producto=self.producto, codigo="big-bag-700-e2e", nombre="Big Bag 700 kg E2E",
            kg_neto=Decimal("700"), unidades_maximas_pallet=1,
            tipo_unidad_logistica=FormatoEnvasado.TipoUnidadLogistica.BIG_BAG,
        )
        self.formato.equipos.add(self.envasadora)
        envase = Insumo.objects.create(
            empresa=self.empresa, codigo="BB-700-E2E", nombre="Envase Big Bag E2E",
            categoria=Insumo.Categoria.EMPAQUE, area=PerfilUsuario.Area.ENVASE,
            unidad=Insumo.Unidad.UN, requiere_calidad=False,
        )
        receta = Receta.objects.create(
            producto=self.producto, version=1, cantidad_base=Decimal("700"),
            vigente_desde=date(2026, 1, 1), fuente="Receta simulada E2E",
        )
        RecetaComponente.objects.create(
            receta=receta, insumo=envase, cantidad=Decimal("1"), unidad="un",
            fase=RecetaComponente.Fase.ENVASADO,
        )
        bodega_envases = Bodega.objects.create(
            sucursal=self.planta, codigo="BENV-SUE", nombre="Envases E2E",
            area=PerfilUsuario.Area.BODEGA,
        )
        ubicacion_envases = Ubicacion.objects.create(
            bodega=bodega_envases, codigo="ENV-DISP", tipo=Ubicacion.Tipo.DISPONIBLE,
        )
        lote_envase = LoteInventario.objects.create(
            sucursal=self.planta, insumo=envase, codigo="LOTE-BB-E2E",
            estado_calidad=LoteInventario.EstadoCalidad.NO_REQUIERE,
        )
        registrar_entrada(
            lote=lote_envase, ubicacion=ubicacion_envases, cantidad=Decimal("2"),
            usuario=self.receptor, documento_tipo="prueba_e2e", documento_id=1,
        )
        self.documento = DocumentoLiberacion.objects.create(
            empresa=self.empresa,
            codigo="LIB-SUERO-E2E", nombre="Liberación suero E2E",
            aplica_a=[Producto.Familia.POLVO], orden=1,
            plantilla=[{
                "clave": "lote", "etiqueta": "Lote", "tipo": "texto",
                "req": True, "origen": "lote.codigo_lote",
            }],
        )

    def _usuario(self, username, rol, area):
        usuario = User.objects.create_user(username, password="e2e")
        PerfilUsuario.objects.create(
            usuario=usuario, empresa=self.empresa, sucursal=self.planta,
            alcance=PerfilUsuario.Alcance.SUCURSAL, rol=rol, area=area,
        )
        return usuario

    @staticmethod
    def _cliente(usuario):
        cliente = APIClient()
        cliente.force_authenticate(usuario)
        return cliente

    def test_recepcion_secado_calidad_envase_e_inventario(self):
        detalle = recibir_detalle_compra(
            recepcion=self.recepcion, detalle_orden_id=self.detalle_compra.pk,
            ubicacion=self.cuarentena, codigo_lote="SUERO-PROV-E2E",
            cantidad=Decimal("1000"), usuario=self.receptor,
        )
        self.assertEqual(detalle.lote.sucursal, self.planta)
        self.assertEqual(detalle.lote.estado_calidad, LoteInventario.EstadoCalidad.PENDIENTE)
        inspeccion = InspeccionMaterial.objects.get(lote=detalle.lote)

        decidir_inspeccion(
            inspeccion_id=inspeccion.pk, decision=InspeccionMaterial.Estado.APROBADA,
            usuario=self.calidad, resultados={"identidad": "conforme"},
            observaciones="Resultado simulado E2E conforme",
        )
        existencia_cuarentena = Existencia.objects.get(
            lote=detalle.lote, ubicacion=self.cuarentena
        )
        trasladar_existencia(
            existencia_id=existencia_cuarentena.pk, destino=self.disponible,
            cantidad=Decimal("1000"), usuario=self.receptor,
            documento_tipo="prueba_e2e", documento_id=detalle.pk,
            motivo="Lote aprobado por Calidad",
        )
        existencia = Existencia.objects.get(lote=detalle.lote, ubicacion=self.disponible)

        inicio = self._cliente(self.secador).post(
            "/api/procesos/secados/iniciar-desde-inventario/",
            {
                "orden": self.orden_produccion.pk, "existencia": existencia.pk,
                "equipo": self.torre.pk, "codigo_lote": "SUERO-POLVO-E2E",
                "cantidad": "800.000",
            },
            format="json",
        )
        self.assertEqual(inicio.status_code, 201, inicio.data)
        corrida = CorridaSecado.objects.get(pk=inicio.data["id"])
        existencia.refresh_from_db()
        self.assertEqual(existencia.cantidad_fisica, Decimal("200.000"))

        cierre = self._cliente(self.secador).post(
            f"/api/procesos/secados/{corrida.pk}/cerrar/",
            {
                "kg_alimentacion": "800.000", "solidos_entrada_pct": "90.00",
                "kg_polvo": "700.000", "kg_finos": "10.000", "kg_merma": "5.000",
                "controles": {"temperatura_salida": 80},
            },
            format="json",
        )
        self.assertEqual(cierre.status_code, 200, cierre.data)
        salida = SalidaProceso.objects.get(ejecucion=corrida.ejecucion)
        self.assertEqual(salida.destino, SalidaProceso.Destino.PENDIENTE)
        self.assertEqual(salida.liberacion_calidad.estado, LiberacionProceso.Estado.PENDIENTE)

        analisis = Analisis.objects.create(
            lote=corrida.lote, fecha=timezone.localdate(), valores={"humedad": 5},
            especificacion=self.especificacion,
        )
        liberacion_intermedia = self._cliente(self.calidad).post(
            f"/api/calidad/resultados-proceso/{salida.pk}/liberar/",
            {"analisis_lote_id": analisis.pk, "observacion": "Conforme E2E"},
            format="json",
        )
        self.assertEqual(liberacion_intermedia.status_code, 200, liberacion_intermedia.data)
        salida.refresh_from_db()
        self.assertEqual(salida.destino, SalidaProceso.Destino.ENVASADO)

        registro = registrar_envasado(
            lote_id=corrida.lote_id, equipo=self.envasadora, formato=self.formato,
            inicio=timezone.now() - timedelta(hours=1), termino=timezone.now(),
            usuario=self.envasador,
            pallets=[{"codigo": "BB-SUERO-E2E-001", "unidades": 1, "kg_neto": "700"}],
        )
        unidad = registro.pallets.get()
        self.assertEqual(unidad.tipo_unidad_logistica, PalletProducto.TipoUnidadLogistica.BIG_BAG)
        self.assertEqual(unidad.estado, PalletProducto.Estado.PENDIENTE_CALIDAD)

        RegistroCalidad.objects.create(
            lote=corrida.lote, documento=self.documento,
            estado=RegistroCalidad.Estado.COMPLETADO,
            valores={"lote": corrida.lote.codigo_lote}, completado_por=self.calidad,
        )
        liberacion_final = self._cliente(self.calidad).post(
            f"/api/calidad/expedientes/{corrida.lote_id}/liberar/",
            {"observacion": "Liberación final E2E"}, format="json",
        )
        self.assertEqual(liberacion_final.status_code, 200, liberacion_final.data)
        self.assertEqual(Liberacion.objects.get(lote=corrida.lote).estado, Liberacion.Estado.LIBERADO)

        envio = self._cliente(self.calidad).post(
            f"/api/calidad/expedientes/{corrida.lote_id}/enviar-bodega/"
        )
        self.assertEqual(envio.status_code, 200, envio.data)
        unidad.refresh_from_db()
        self.assertEqual(unidad.estado, PalletProducto.Estado.EN_INVENTARIO)
        existencia_final = ExistenciaProductoTerminado.objects.get(pallet=unidad, activo=True)
        self.assertEqual(existencia_final.ubicacion.tipo, Ubicacion.Tipo.DISPONIBLE)
        self.assertTrue(MovimientoInventario.objects.filter(
            lote=detalle.lote, tipo=MovimientoInventario.Tipo.CONSUMO,
            documento_id=corrida.ejecucion_id,
        ).exists())
        self.assertEqual(Lote.objects.get(pk=corrida.lote_id).kg_producidos, Decimal("700.00"))
