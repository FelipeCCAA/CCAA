from datetime import date
from decimal import Decimal

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.test import TestCase
from rest_framework.test import APIClient

from maestros.models import Mandante, Producto, Receta, RecetaComponente
from usuarios.models import PerfilUsuario

from .models import Insumo
from .models import (
    Bodega, DetalleOrdenCompra, Existencia, InspeccionMaterial,
    LoteInventario, MovimientoInventario, OrdenCompra, Proveedor,
    RecepcionCompra, SolicitudCompra, SolicitudMaterial,
    DetalleSolicitudMaterial, Ubicacion,
)
from .servicios import (
    consumir_receta_produccion, decidir_inspeccion, decidir_solicitud_compra, entregar_reserva,
    entregar_solicitud_material,
    ejecutar_mrp_semana, recibir_detalle_compra, registrar_entrada, registrar_salida,
    reservar_fefo, reservar_solicitud_material,
)


class InventarioTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user("jefe-secado", password="x")
        PerfilUsuario.objects.create(
            usuario=self.admin,
            nivel=PerfilUsuario.Nivel.ADMIN,
            area=PerfilUsuario.Area.SECADO,
        )
        self.cliente = APIClient()
        self.cliente.force_authenticate(self.admin)
        mandante = Mandante.objects.create(nombre="CCAA")
        self.producto = Producto.objects.create(
            nombre="Leche en polvo", familia="polvo", mandante=mandante
        )
        self.bolsa = Insumo.objects.create(
            codigo="BOLSA-25",
            nombre="Bolsa 25 kg",
            area=PerfilUsuario.Area.SECADO,
            unidad="un",
            contenido_envase=1,
            demanda_anual=10000,
            costo_por_pedido=50,
            costo_mantencion_unitario=2,
            consumo_diario=40,
            plazo_reposicion_dias=5,
        )
        # La fórmula vive en el maestro de recetas, que es el único lugar
        # donde se declara: 0,04 bolsas por kilo, o sea una bolsa cada 25 kg.
        # `cantidad_base=1` porque los componentes se declaran por kilo.
        self.receta = Receta.objects.create(
            producto=self.producto,
            version=1,
            cantidad_base=1,
            vigente_desde=date(2020, 1, 1),
        )
        RecetaComponente.objects.create(
            receta=self.receta,
            insumo=self.bolsa,
            cantidad=Decimal("0.04"),
            unidad="un",
        )

    def test_eoq_y_punto_reposicion(self):
        self.assertAlmostEqual(float(self.bolsa.eoq), 707.106, places=2)
        self.assertEqual(self.bolsa.punto_reposicion, 200)

    def test_mrp_calcula_bolsas_y_faltante(self):
        respuesta = self.cliente.post(
            "/api/inventario/mrp/",
            {"producto": self.producto.id, "kilos_producir": 1_000_000},
            format="json",
        )
        self.assertEqual(respuesta.status_code, 200)
        material = respuesta.json()["materiales"][0]
        self.assertEqual(Decimal(material["requerido"]), Decimal("40000"))
        # El MRP usa el libro de existencias y no hay otro sitio de donde
        # sacar el saldo: sin una entrada trazable, no hay stock que descontar
        # del requerimiento.
        self.assertEqual(material["envases_a_pedir"], 40000)

    def test_administrador_de_area_no_ve_insumos_de_otra_area(self):
        Insumo.objects.create(
            codigo="LAB", nombre="Reactivo", area=PerfilUsuario.Area.CALIDAD,
            unidad="L",
        )
        respuesta = self.cliente.get("/api/inventario/insumos/")
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta.json()["count"], 1)

    def test_mrp_usa_semana_publicada_y_consumo_por_producto(self):
        from datetime import date
        from maestros.models import Equipo
        from planificacion.models import BloquePlan, CodigoProduccion, SemanaPlan

        equipo = Equipo.objects.create(codigo="linea-mrp", nombre="Línea MRP", tipo=Equipo.Tipo.LINEA)
        codigo = CodigoProduccion.objects.create(
            codigo="MRP-1", producto=self.producto, categoria="secado_ccaa",
            rendimiento_lh=1000,
        )
        semana = SemanaPlan.objects.create(
            codigo="W1", anio=2026, fecha_inicio=date(2026, 1, 5),
            estado=SemanaPlan.Estado.PUBLICADA,
        )
        BloquePlan.objects.create(
            semana=semana, equipo=equipo, dia=0, hora_inicio=8, hora_fin=9,
            tipo=BloquePlan.Tipo.PRODUCCION, codigo=codigo, cantidad_kg=1000,
        )
        ejecucion = ejecutar_mrp_semana(semana=semana, usuario=self.admin)
        resultado = ejecucion.resultados.get(insumo=self.bolsa)
        self.assertEqual(resultado.necesidad_bruta, Decimal("40"))
        self.assertEqual(resultado.necesidad_neta, Decimal("40"))

    def test_consumo_de_lote_productivo_usa_receta_y_no_se_duplica(self):
        from datetime import date
        from produccion.models import Lote

        bodega = Bodega.objects.create(codigo="BP", nombre="Bodega producción")
        ubicacion = Ubicacion.objects.create(bodega=bodega, codigo="DISP")
        lote_material = LoteInventario.objects.create(
            insumo=self.bolsa, codigo="B-RECETA",
            estado_calidad=LoteInventario.EstadoCalidad.APROBADO,
        )
        registrar_entrada(
            lote=lote_material, ubicacion=ubicacion, cantidad=100,
            usuario=self.admin, documento_tipo="recepcion", documento_id=1,
        )
        lote_produccion = Lote.objects.create(
            codigo_lote="LP-RECETA", producto=self.producto, fecha=date(2026, 8, 3),
            kg_producidos=1000, estado=Lote.Estado.PRODUCIDO,
        )
        _, movimientos = consumir_receta_produccion(lote_produccion=lote_produccion, usuario=self.admin)
        existencia = Existencia.objects.get(lote=lote_material, ubicacion=ubicacion)
        self.assertEqual(existencia.cantidad_fisica, Decimal("60"))
        self.assertEqual(sum((m.cantidad for m in movimientos), Decimal("0")), Decimal("40"))
        self.assertEqual(movimientos[0].documento_tipo, "produccion.Lote")
        self.assertEqual(movimientos[0].documento_id, lote_produccion.pk)
        with self.assertRaisesMessage(ValidationError, "ya fue consumida"):
            consumir_receta_produccion(lote_produccion=lote_produccion, usuario=self.admin)

    def test_el_descuento_usa_la_receta_que_regia_el_dia_del_lote(self):
        """
        El motivo de haber unificado las dos recetas. Con la tabla plana que
        el descuento leía antes —sin versión— corregir la fórmula hoy
        reescribía lo que había costado producir en mayo, y
        `ConsumoLoteProduccion` decía ser la cabecera auditable de ese cálculo.
        """
        from produccion.models import Lote

        # Desde julio se ocupan el doble de bolsas por kilo.
        nueva = Receta.objects.create(
            producto=self.producto, version=2, cantidad_base=1,
            vigente_desde=date(2026, 7, 1),
        )
        RecetaComponente.objects.create(
            receta=nueva, insumo=self.bolsa, cantidad=Decimal("0.08"), unidad="un",
        )

        bodega = Bodega.objects.create(codigo="BV", nombre="Bodega vigencia")
        ubicacion = Ubicacion.objects.create(bodega=bodega, codigo="DISP")
        lote_material = LoteInventario.objects.create(
            insumo=self.bolsa, codigo="B-VIGENCIA",
            estado_calidad=LoteInventario.EstadoCalidad.APROBADO,
        )
        registrar_entrada(
            lote=lote_material, ubicacion=ubicacion, cantidad=100,
            usuario=self.admin, documento_tipo="recepcion", documento_id=1,
        )

        # Un lote de junio: le toca la versión 1, o sea 0,04 por kilo.
        lote_junio = Lote.objects.create(
            codigo_lote="LP-JUNIO", producto=self.producto, fecha=date(2026, 6, 15),
            kg_producidos=1000, estado=Lote.Estado.PRODUCIDO,
        )
        _, movimientos = consumir_receta_produccion(
            lote_produccion=lote_junio, usuario=self.admin
        )

        self.assertEqual(
            sum((m.cantidad for m in movimientos), Decimal("0")), Decimal("40")
        )

    def test_una_cadena_cortada_no_descuenta_nada(self):
        """
        Un requerimiento a medias se parece demasiado a uno completo, y
        descontar con él dejaría el saldo de bodega mintiendo.
        """
        from produccion.models import Lote

        intermedio = Producto.objects.create(
            nombre="Concentrado sin receta",
            familia="polvo",
            naturaleza="intermedio",
            mandante=self.producto.mandante,
        )
        # El producto lleva un intermedio que no tiene receta propia: la
        # explosión no puede llegar hasta abajo.
        RecetaComponente.objects.create(
            receta=self.receta, producto=intermedio, cantidad=1, unidad="kg",
        )

        lote_produccion = Lote.objects.create(
            codigo_lote="LP-CORTADA", producto=self.producto, fecha=date(2026, 8, 3),
            kg_producidos=1000, estado=Lote.Estado.PRODUCIDO,
        )

        with self.assertRaisesMessage(ValidationError, "explotar hasta el final"):
            consumir_receta_produccion(
                lote_produccion=lote_produccion, usuario=self.admin
            )

        self.assertEqual(MovimientoInventario.objects.filter(tipo="consumo").count(), 0)


class LibroInventarioTests(TestCase):
    def setUp(self):
        self.usuario = User.objects.create_user("bodeguero", password="x")
        self.insumo = Insumo.objects.create(
            codigo="BOLSA", nombre="Bolsa 25 kg", area=PerfilUsuario.Area.BODEGA,
            unidad="un", requiere_calidad=True,
        )
        self.bodega = Bodega.objects.create(codigo="B1", nombre="Bodega principal")
        self.disponible = Ubicacion.objects.create(bodega=self.bodega, codigo="D-01")
        self.cuarentena = Ubicacion.objects.create(
            bodega=self.bodega, codigo="Q-01", tipo=Ubicacion.Tipo.CUARENTENA
        )
        self.produccion = Ubicacion.objects.create(
            bodega=self.bodega, codigo="PROD", tipo=Ubicacion.Tipo.PRODUCCION
        )

    def _lote(self, codigo, estado, vencimiento=None):
        return LoteInventario.objects.create(
            insumo=self.insumo, codigo=codigo, estado_calidad=estado,
            vencimiento=vencimiento,
        )

    def test_entrada_crea_movimiento_y_saldo(self):
        lote = self._lote("L1", LoteInventario.EstadoCalidad.PENDIENTE)
        registrar_entrada(
            lote=lote, ubicacion=self.cuarentena, cantidad=100,
            usuario=self.usuario, documento_tipo="recepcion", documento_id=1,
        )
        existencia = Existencia.objects.get(lote=lote)
        self.assertEqual(existencia.cantidad_fisica, 100)
        self.assertEqual(existencia.cantidad_disponible, 0)
        self.assertEqual(MovimientoInventario.objects.count(), 1)

    def test_cuarentena_no_se_puede_reservar(self):
        lote = self._lote("LQ", LoteInventario.EstadoCalidad.PENDIENTE)
        registrar_entrada(
            lote=lote, ubicacion=self.cuarentena, cantidad=100,
            usuario=self.usuario, documento_tipo="recepcion", documento_id=1,
        )
        with self.assertRaisesMessage(ValidationError, "Stock disponible insuficiente"):
            reservar_fefo(
                insumo_id=self.insumo.id, cantidad=1, usuario=self.usuario,
                documento_tipo="mrq", documento_id=1,
            )

    def test_cuarentena_no_permite_salida_ni_consumo(self):
        lote = self._lote("LQ-SAL", LoteInventario.EstadoCalidad.PENDIENTE)
        registrar_entrada(
            lote=lote, ubicacion=self.cuarentena, cantidad=10,
            usuario=self.usuario, documento_tipo="recepcion", documento_id=1,
        )
        existencia = Existencia.objects.get(lote=lote)
        with self.assertRaisesMessage(ValidationError, "Solo puede salir"):
            registrar_salida(
                existencia_id=existencia.id, cantidad=1, usuario=self.usuario,
                documento_tipo="consumo", documento_id=1, motivo="Prueba", consumo=True,
            )
        existencia.refresh_from_db()
        self.assertEqual(existencia.cantidad_fisica, 10)

    def test_consumo_aprobado_descuenta_y_crea_movimiento(self):
        lote = self._lote("L-OK", LoteInventario.EstadoCalidad.APROBADO)
        registrar_entrada(
            lote=lote, ubicacion=self.disponible, cantidad=10,
            usuario=self.usuario, documento_tipo="recepcion", documento_id=1,
        )
        existencia = Existencia.objects.get(lote=lote)
        movimiento = registrar_salida(
            existencia_id=existencia.id, cantidad=3, usuario=self.usuario,
            documento_tipo="orden-produccion", documento_id=8,
            motivo="Consumo lote productivo", consumo=True,
        )
        existencia.refresh_from_db()
        self.assertEqual(existencia.cantidad_fisica, 7)
        self.assertEqual(movimiento.tipo, MovimientoInventario.Tipo.CONSUMO)

    def test_fefo_reserva_el_vencimiento_mas_cercano(self):
        from datetime import timedelta
        from django.utils import timezone

        lejano = self._lote("L2", LoteInventario.EstadoCalidad.APROBADO, timezone.localdate() + timedelta(days=20))
        cercano = self._lote("L1", LoteInventario.EstadoCalidad.APROBADO, timezone.localdate() + timedelta(days=5))
        for lote in [lejano, cercano]:
            registrar_entrada(
                lote=lote, ubicacion=self.disponible, cantidad=10,
                usuario=self.usuario, documento_tipo="recepcion", documento_id=1,
            )
        reservas = reservar_fefo(
            insumo_id=self.insumo.id, cantidad=6, usuario=self.usuario,
            documento_tipo="mrq", documento_id=2,
        )
        self.assertEqual(reservas[0][0].lote, cercano)

    def test_entrega_exige_reserva_y_no_deja_stock_negativo(self):
        lote = self._lote("LA", LoteInventario.EstadoCalidad.APROBADO)
        registrar_entrada(
            lote=lote, ubicacion=self.disponible, cantidad=5,
            usuario=self.usuario, documento_tipo="recepcion", documento_id=1,
        )
        existencia, _ = reservar_fefo(
            insumo_id=self.insumo.id, cantidad=3, usuario=self.usuario,
            documento_tipo="mrq", documento_id=3,
        )[0]
        entregar_reserva(
            existencia_id=existencia.id, cantidad=3, destino=self.produccion,
            usuario=self.usuario, documento_tipo="entrega", documento_id=1,
        )
        existencia.refresh_from_db()
        self.assertEqual(existencia.cantidad_fisica, 2)
        self.assertEqual(existencia.cantidad_reservada, 0)
        with self.assertRaisesMessage(ValidationError, "supera la existencia reservada"):
            entregar_reserva(
                existencia_id=existencia.id, cantidad=1, destino=self.produccion,
                usuario=self.usuario, documento_tipo="entrega", documento_id=2,
            )

    def test_mrq_reserva_y_entrega_con_trazabilidad(self):
        from django.utils import timezone
        lote = self._lote("MRQ-L", LoteInventario.EstadoCalidad.APROBADO)
        registrar_entrada(
            lote=lote, ubicacion=self.disponible, cantidad=10,
            usuario=self.usuario, documento_tipo="recepcion", documento_id=1,
        )
        solicitud = SolicitudMaterial.objects.create(
            numero="MRQ-1", area=PerfilUsuario.Area.SECADO,
            solicitante=self.usuario, fecha_requerida=timezone.localdate(),
            estado=SolicitudMaterial.Estado.ENVIADA,
        )
        DetalleSolicitudMaterial.objects.create(
            solicitud=solicitud, insumo=self.insumo, cantidad_solicitada=4,
        )
        reservar_solicitud_material(solicitud=solicitud, usuario=self.usuario)
        solicitud.refresh_from_db()
        self.assertEqual(solicitud.estado, SolicitudMaterial.Estado.PREPARADA)
        entrega = entregar_solicitud_material(
            solicitud=solicitud, destino=self.produccion,
            entrega_por=self.usuario, recibe_por=self.usuario,
        )
        solicitud.refresh_from_db()
        self.assertEqual(solicitud.estado, SolicitudMaterial.Estado.ENTREGADA)
        self.assertEqual(entrega.detalles.get().lote, lote)


class CompraCalidadTests(TestCase):
    def setUp(self):
        self.receptor = User.objects.create_user("receptor", password="x")
        self.calidad = User.objects.create_user("inspectora", password="x")
        self.comprador = User.objects.create_user("comprador", password="x")
        self.jefatura = User.objects.create_user("jefatura", password="x")
        self.insumo = Insumo.objects.create(
            codigo="ING-1", nombre="Ingrediente", area=PerfilUsuario.Area.BODEGA,
            unidad="kg", requiere_calidad=True, requiere_lote=True,
        )
        self.proveedor = Proveedor.objects.create(rut="1-9", nombre="Proveedor")
        self.bodega = Bodega.objects.create(codigo="B", nombre="Bodega")
        self.cuarentena = Ubicacion.objects.create(
            bodega=self.bodega, codigo="Q", tipo=Ubicacion.Tipo.CUARENTENA,
        )
        self.orden = OrdenCompra.objects.create(
            numero="OC-1", proveedor=self.proveedor, bodega_entrega=self.bodega,
            estado=OrdenCompra.Estado.ENVIADA,
        )
        self.detalle_orden = DetalleOrdenCompra.objects.create(
            orden=self.orden, insumo=self.insumo, cantidad=100, costo_unitario=10,
        )
        self.recepcion = RecepcionCompra.objects.create(
            orden=self.orden, guia="G-1", receptor=self.receptor,
        )

    def test_recepcion_sujeta_a_calidad_nace_en_cuarentena_y_crea_inspeccion(self):
        detalle = recibir_detalle_compra(
            recepcion=self.recepcion, detalle_orden_id=self.detalle_orden.id,
            ubicacion=self.cuarentena, codigo_lote="LP-1", cantidad=50,
            usuario=self.receptor,
        )
        self.assertEqual(detalle.lote.estado_calidad, LoteInventario.EstadoCalidad.PENDIENTE)
        self.assertTrue(InspeccionMaterial.objects.filter(lote=detalle.lote).exists())
        self.assertEqual(Existencia.objects.get(lote=detalle.lote).cantidad_disponible, 0)

        inspeccion = detalle.lote.inspeccion
        decidir_inspeccion(
            inspeccion_id=inspeccion.id, decision=InspeccionMaterial.Estado.APROBADA,
            usuario=self.calidad, resultados={"certificado": "conforme"},
        )
        existencia = Existencia.objects.get(lote=detalle.lote)
        self.assertEqual(existencia.cantidad_fisica, 50)
        self.assertEqual(existencia.cantidad_disponible, 0)

    def test_solicitante_no_aprueba_su_propia_compra(self):
        solicitud = SolicitudCompra.objects.create(
            numero="SC-1", area=PerfilUsuario.Area.COMPRAS,
            solicitante=self.comprador, motivo="Reposición",
            estado=SolicitudCompra.Estado.PENDIENTE,
        )
        with self.assertRaisesMessage(ValidationError, "propia solicitud"):
            decidir_solicitud_compra(
                solicitud=solicitud, aprobador=self.comprador, decision="aprobada",
            )
        decidir_solicitud_compra(
            solicitud=solicitud, aprobador=self.jefatura, decision="aprobada",
        )
        solicitud.refresh_from_db()
        self.assertEqual(solicitud.estado, SolicitudCompra.Estado.APROBADA)
