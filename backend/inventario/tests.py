from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.db import transaction
from django.test import TestCase
from django.utils import timezone
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
    consumir_receta_produccion, convertir_solicitud_en_ordenes,
    crear_solicitud_desde_mrp, decidir_inspeccion, decidir_solicitud_compra, entregar_reserva,
    entregar_solicitud_material,
    ejecutar_mrp_semana, enviar_orden_compra, recibir_detalle_compra, registrar_entrada, registrar_salida,
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
        from datetime import date, timedelta
        from maestros.models import Equipo
        from planificacion.models import BloquePlan, CodigoProduccion, SemanaPlan

        equipo = Equipo.objects.create(
            codigo="linea-mrp",
            nombre="Línea MRP",
            tipo=Equipo.Tipo.LINEA,
            consume_materiales=True,
        )
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

    def test_quien_consume_materiales_lo_dice_el_maestro_no_su_tipo(self):
        """
        El bloque cuenta según `consume_materiales`, no según el tipo del
        equipo. Antes el filtro comparaba `tipo == "linea"`, y cuando las
        líneas 1 y 2 se reconocieron como las torres Egron y cambiaron de
        tipo, sus bloques dejaron de contar: el MRP siguió corriendo y
        devolviendo cifras, solo que cortas.

        Una orden de compra corta no se ve distinta de una completa. Por eso
        se prueba con una **torre**, que es el tipo que el filtro anterior
        dejaba fuera.
        """
        from datetime import date, timedelta
        from maestros.models import Equipo
        from planificacion.models import BloquePlan, CodigoProduccion, SemanaPlan

        torre = Equipo.objects.create(
            codigo="torre-mrp",
            nombre="Torre MRP",
            tipo=Equipo.Tipo.TORRE,
            consume_materiales=True,
        )
        # El evaporador que la alimenta lleva el mismo código de producción.
        # Si contara también, el MRP pediría los sacos dos veces.
        evaporador = Equipo.objects.create(
            codigo="evap-mrp",
            nombre="Evaporador MRP",
            tipo=Equipo.Tipo.EVAPORADOR,
            consume_leche=True,
        )
        codigo = CodigoProduccion.objects.create(
            codigo="MRP-2", producto=self.producto, categoria="secado_ccaa",
            rendimiento_lh=1000,
        )
        semana = SemanaPlan.objects.create(
            codigo="W9", anio=2026, fecha_inicio=date(2026, 3, 2),
            estado=SemanaPlan.Estado.PUBLICADA,
        )

        for equipo in (torre, evaporador):
            BloquePlan.objects.create(
                semana=semana, equipo=equipo, dia=0, hora_inicio=8, hora_fin=9,
                tipo=BloquePlan.Tipo.PRODUCCION, codigo=codigo, cantidad_kg=1000,
            )

        ejecucion = ejecutar_mrp_semana(semana=semana, usuario=self.admin)
        resultado = ejecucion.resultados.get(insumo=self.bolsa)

        # 1.000 kg × 0,04 = 40 bolsas. Cuarenta, no ochenta: el bloque del
        # evaporador no vuelve a contarlas.
        self.assertEqual(resultado.necesidad_bruta, Decimal("40"))

    def test_consumo_de_lote_productivo_usa_receta_y_no_se_duplica(self):
        from datetime import date, timedelta
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


class CircuitoDeCompraTests(TestCase):
    """
    De lo que el MRP dice que falta a la orden del proveedor.

    Eran dos callejones sin salida del modelo: el estado `convertida` no lo
    alcanzaba nadie y `origen_mrp` no lo ponía nadie. Los dos apuntaban al
    mismo eslabón ausente, y sin él el MRP calculaba para que después alguien
    volviera a teclear las cantidades en otro formulario — que es donde se
    pierde el «para cuándo» y donde aparecen las diferencias entre lo que el
    sistema calculó y lo que se pidió.
    """

    def setUp(self):
        from .models import EjecucionMRP, ResultadoMRP

        self.usuario = User.objects.create_user("compras", password="x")
        PerfilUsuario.objects.create(
            usuario=self.usuario,
            nivel=PerfilUsuario.Nivel.ADMIN,
            area=PerfilUsuario.Area.COMPRAS,
        )
        self.jefe = User.objects.create_user("jefe-compras", password="x")

        self.bolsa = Insumo.objects.create(
            codigo="C-BOLSA", nombre="Bolsa 25 kg",
            area=PerfilUsuario.Area.BODEGA, unidad="un",
        )
        self.reactivo = Insumo.objects.create(
            codigo="C-REACT", nombre="Reactivo",
            area=PerfilUsuario.Area.CALIDAD, unidad="L",
        )

        self.envases = Proveedor.objects.create(rut="76.1-1", nombre="Envases del Sur")
        self.quimica = Proveedor.objects.create(rut="76.2-2", nombre="Química Austral")

        self.bodega = Bodega.objects.create(codigo="BC", nombre="Bodega central")

        self.ejecucion = EjecucionMRP.objects.create(
            fecha_corte=date(2026, 8, 10), horizonte_hasta=date(2026, 8, 16),
            ejecutada_por=self.usuario,
        )
        # Una línea con compra sugerida y otra sin ella: la segunda no debe
        # pedirse.
        ResultadoMRP.objects.create(
            ejecucion=self.ejecucion, insumo=self.bolsa,
            fecha_requerida=date(2026, 8, 12), necesidad_bruta=800,
            disponible_proyectado=0, necesidad_neta=800, compra_sugerida=1000,
            fecha_sugerida_orden=date(2026, 8, 2),
        )
        ResultadoMRP.objects.create(
            ejecucion=self.ejecucion, insumo=self.reactivo,
            fecha_requerida=date(2026, 8, 14), necesidad_bruta=50,
            disponible_proyectado=200, necesidad_neta=0, compra_sugerida=0,
            fecha_sugerida_orden=date(2026, 8, 14),
        )

    def _proveedores_principales(self):
        from .models import InsumoProveedor

        InsumoProveedor.objects.create(
            insumo=self.bolsa, proveedor=self.envases, principal=True,
            costo_unitario=120,
        )
        InsumoProveedor.objects.create(
            insumo=self.reactivo, proveedor=self.quimica, principal=True,
            costo_unitario=8000,
        )

    # ------------------------------------------------------- desde el MRP

    def test_solo_se_pide_lo_que_el_mrp_sugiere_comprar(self):
        """
        Una necesidad que el stock o las órdenes en camino ya cubren no se
        vuelve a pedir.
        """
        solicitud = crear_solicitud_desde_mrp(
            ejecucion=self.ejecucion, usuario=self.usuario
        )

        self.assertEqual(solicitud.detalles.count(), 1)
        self.assertEqual(solicitud.detalles.get().insumo, self.bolsa)

    def test_las_lineas_quedan_marcadas_como_venidas_del_mrp(self):
        """Es lo que se pregunta después de un quiebre: si esto salió del
        cálculo o alguien lo agregó a mano."""
        solicitud = crear_solicitud_desde_mrp(
            ejecucion=self.ejecucion, usuario=self.usuario
        )

        self.assertTrue(solicitud.detalles.get().origen_mrp)

    def test_manda_la_fecha_en_que_se_necesita_no_la_de_emitir(self):
        """Quien tramita decide cuándo lo hace; el plazo de la planta no se
        mueve por eso."""
        solicitud = crear_solicitud_desde_mrp(
            ejecucion=self.ejecucion, usuario=self.usuario
        )

        self.assertEqual(solicitud.detalles.get().fecha_requerida, date(2026, 8, 12))

    def test_el_mismo_calculo_no_genera_dos_solicitudes(self):
        """
        La unicidad del número lo impide. Duplicar la compra es peor que
        fallar: la segunda orden llega igual y hay que devolverla.
        """
        from django.db import IntegrityError

        crear_solicitud_desde_mrp(ejecucion=self.ejecucion, usuario=self.usuario)

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                crear_solicitud_desde_mrp(
                    ejecucion=self.ejecucion, usuario=self.usuario
                )

    def test_una_ejecucion_sin_faltantes_no_genera_solicitud(self):
        from .models import EjecucionMRP

        vacia = EjecucionMRP.objects.create(
            fecha_corte=date(2026, 9, 1), horizonte_hasta=date(2026, 9, 7),
            ejecutada_por=self.usuario,
        )

        with self.assertRaisesMessage(ValidationError, "no sugiere comprar nada"):
            crear_solicitud_desde_mrp(ejecucion=vacia, usuario=self.usuario)

    # --------------------------------------------------- a orden de compra

    def _solicitud_aprobada(self):
        from .models import DetalleSolicitudCompra

        solicitud = SolicitudCompra.objects.create(
            numero="SC-1", area=PerfilUsuario.Area.COMPRAS,
            solicitante=self.usuario, motivo="prueba",
            estado=SolicitudCompra.Estado.APROBADA,
        )
        for insumo, cantidad, cuando in (
            (self.bolsa, 1000, date(2026, 8, 12)),
            (self.reactivo, 20, date(2026, 8, 20)),
        ):
            DetalleSolicitudCompra.objects.create(
                solicitud=solicitud, insumo=insumo, cantidad=cantidad,
                fecha_requerida=cuando,
            )
        return solicitud

    def test_se_emite_una_orden_por_proveedor(self):
        """
        Una sola orden obligaría a elegir un proveedor y mandarle renglones
        que no vende.
        """
        self._proveedores_principales()
        solicitud = self._solicitud_aprobada()

        ordenes = convertir_solicitud_en_ordenes(
            solicitud=solicitud, usuario=self.usuario, bodega=self.bodega
        )

        self.assertEqual(len(ordenes), 2)
        self.assertEqual({o.proveedor for o in ordenes}, {self.envases, self.quimica})

        for orden in ordenes:
            self.assertEqual(orden.detalles.count(), 1)

    def test_la_orden_promete_la_fecha_mas_apretada_de_sus_lineas(self):
        """Prometer la más holgada dejaría a la planta sin material creyendo
        que va en plazo."""
        from .models import InsumoProveedor

        for insumo, costo in ((self.bolsa, 120), (self.reactivo, 8000)):
            InsumoProveedor.objects.create(
                insumo=insumo, proveedor=self.envases, principal=True,
                costo_unitario=costo,
            )

        orden = convertir_solicitud_en_ordenes(
            solicitud=self._solicitud_aprobada(),
            usuario=self.usuario,
            bodega=self.bodega,
        )[0]

        self.assertEqual(orden.fecha_comprometida, date(2026, 8, 12))

    def test_un_material_sin_proveedor_detiene_la_conversion_entera(self):
        """
        Emitir lo que sí se puede y callar el resto parte la solicitud sin que
        nadie lo note: lo que quedó fuera no se vuelve a mirar porque la
        solicitud figura convertida.
        """
        from .models import InsumoProveedor

        InsumoProveedor.objects.create(
            insumo=self.bolsa, proveedor=self.envases, principal=True,
            costo_unitario=120,
        )
        solicitud = self._solicitud_aprobada()

        with self.assertRaisesMessage(ValidationError, "Reactivo"):
            convertir_solicitud_en_ordenes(
                solicitud=solicitud, usuario=self.usuario, bodega=self.bodega
            )

        self.assertEqual(OrdenCompra.objects.count(), 0)
        solicitud.refresh_from_db()
        self.assertEqual(solicitud.estado, SolicitudCompra.Estado.APROBADA)

    def test_solo_se_convierte_una_solicitud_aprobada(self):
        self._proveedores_principales()
        solicitud = self._solicitud_aprobada()
        solicitud.estado = SolicitudCompra.Estado.PENDIENTE
        solicitud.save(update_fields=["estado"])

        with self.assertRaisesMessage(ValidationError, "aprobada"):
            convertir_solicitud_en_ordenes(
                solicitud=solicitud, usuario=self.usuario, bodega=self.bodega
            )

    def test_la_solicitud_convertida_queda_marcada(self):
        """El estado existía en el modelo desde el principio y no lo alcanzaba
        nadie: nada convertía nada."""
        self._proveedores_principales()
        solicitud = self._solicitud_aprobada()

        convertir_solicitud_en_ordenes(
            solicitud=solicitud, usuario=self.usuario, bodega=self.bodega
        )

        solicitud.refresh_from_db()
        self.assertEqual(solicitud.estado, SolicitudCompra.Estado.CONVERTIDA)


class ProveedorPrincipalTests(TestCase):
    """
    Un solo proveedor principal por material.

    Nada lo impedía, y los dos que lo consultan elegían distinto: el MRP
    tomaba el más antiguo y la conversión a orden el último del queryset. O
    sea que el cálculo salía con las condiciones de un proveedor y la orden se
    emitía al otro, sin que nada avisara.
    """

    def setUp(self):
        self.usuario = User.objects.create_user("compras-p", password="x")
        PerfilUsuario.objects.create(
            usuario=self.usuario,
            nivel=PerfilUsuario.Nivel.ADMIN,
            area=PerfilUsuario.Area.COMPRAS,
        )
        self.cliente = APIClient()
        self.cliente.force_authenticate(self.usuario)

        self.bolsa = Insumo.objects.create(
            codigo="P-BOLSA", nombre="Bolsa 25 kg",
            area=PerfilUsuario.Area.BODEGA, unidad="un",
        )
        self.uno = Proveedor.objects.create(rut="80.1-1", nombre="Envases Uno")
        self.otro = Proveedor.objects.create(rut="80.2-2", nombre="Envases Dos")

    def test_la_base_impide_dos_principales(self):
        from django.db import IntegrityError

        from .models import InsumoProveedor

        InsumoProveedor.objects.create(
            insumo=self.bolsa, proveedor=self.uno, principal=True
        )

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                InsumoProveedor.objects.create(
                    insumo=self.bolsa, proveedor=self.otro, principal=True
                )

    def test_varios_no_principales_si_conviven(self):
        """Tener alternativas cotizadas es normal; lo que no puede haber son
        dos que manden."""
        from .models import InsumoProveedor

        InsumoProveedor.objects.create(
            insumo=self.bolsa, proveedor=self.uno, principal=True
        )
        InsumoProveedor.objects.create(
            insumo=self.bolsa, proveedor=self.otro, principal=False
        )

        self.assertEqual(
            InsumoProveedor.objects.filter(insumo=self.bolsa).count(), 2
        )

    def test_la_api_explica_quien_es_el_principal_actual(self):
        """
        Un error de base de datos sale como 500 y no dice qué hacer. El
        serializer lo traduce antes de llegar ahí.
        """
        from .models import InsumoProveedor

        InsumoProveedor.objects.create(
            insumo=self.bolsa, proveedor=self.uno, principal=True
        )

        respuesta = self.cliente.post(
            "/api/inventario/insumo-proveedores/",
            {
                "insumo": self.bolsa.id,
                "proveedor": self.otro.id,
                "principal": True,
            },
            format="json",
        )

        self.assertEqual(respuesta.status_code, 400)
        self.assertIn("Envases Uno", str(respuesta.data))

    def test_cambiar_el_principal_exige_quitar_el_anterior(self):
        """El camino correcto: primero se le quita a uno, después se le pone
        al otro. Dos pasos, pero en ningún momento hay dos."""
        from .models import InsumoProveedor

        actual = InsumoProveedor.objects.create(
            insumo=self.bolsa, proveedor=self.uno, principal=True
        )
        nuevo = InsumoProveedor.objects.create(
            insumo=self.bolsa, proveedor=self.otro, principal=False
        )

        self.cliente.patch(
            f"/api/inventario/insumo-proveedores/{actual.id}/",
            {"principal": False},
            format="json",
        )
        respuesta = self.cliente.patch(
            f"/api/inventario/insumo-proveedores/{nuevo.id}/",
            {"principal": True},
            format="json",
        )

        self.assertEqual(respuesta.status_code, 200)
        nuevo.refresh_from_db()
        self.assertTrue(nuevo.principal)


class CicloDeLaOrdenTests(TestCase):
    """
    El estado de la orden avanza solo, según lo que llega.

    `parcial` y `recibida` existían en el modelo y no los ponía nadie: una
    orden entregada por completo seguía figurando abierta, y Compras no tenía
    cómo saber qué estaba pendiente sin sumar las líneas a mano.
    """

    def setUp(self):
        from .models import DetalleOrdenCompra

        self.usuario = User.objects.create_user("recepcionista", password="x")
        PerfilUsuario.objects.create(
            usuario=self.usuario,
            nivel=PerfilUsuario.Nivel.ADMIN,
            area=PerfilUsuario.Area.RECEPCION,
        )

        self.bolsa = Insumo.objects.create(
            codigo="R-BOLSA", nombre="Bolsa 25 kg",
            area=PerfilUsuario.Area.BODEGA, unidad="un",
            requiere_calidad=False, requiere_lote=False,
        )
        self.reactivo = Insumo.objects.create(
            codigo="R-REACT", nombre="Reactivo",
            area=PerfilUsuario.Area.CALIDAD, unidad="L",
            requiere_calidad=True, requiere_lote=True,
        )

        proveedor = Proveedor.objects.create(rut="90.1-1", nombre="Envases Sur")
        self.bodega = Bodega.objects.create(codigo="BR", nombre="Bodega recepción")
        self.disponible = Ubicacion.objects.create(
            bodega=self.bodega, codigo="DISP", tipo=Ubicacion.Tipo.DISPONIBLE
        )
        self.cuarentena = Ubicacion.objects.create(
            bodega=self.bodega, codigo="CUAR", tipo=Ubicacion.Tipo.CUARENTENA
        )

        self.orden = OrdenCompra.objects.create(
            numero="OC-R-1", proveedor=proveedor, bodega_entrega=self.bodega,
            estado=OrdenCompra.Estado.BORRADOR,
        )
        self.linea_bolsa = DetalleOrdenCompra.objects.create(
            orden=self.orden, insumo=self.bolsa, cantidad=1000, costo_unitario=120,
        )
        self.linea_reactivo = DetalleOrdenCompra.objects.create(
            orden=self.orden, insumo=self.reactivo, cantidad=20, costo_unitario=8000,
        )

    def _recepcion(self):
        return RecepcionCompra.objects.create(
            orden=self.orden, guia="G-1", receptor=self.usuario
        )

    def test_solo_se_envia_un_borrador(self):
        enviar_orden_compra(orden=self.orden)
        self.orden.refresh_from_db()
        self.assertEqual(self.orden.estado, OrdenCompra.Estado.ENVIADA)

        with self.assertRaisesMessage(ValidationError, "solo se envía un borrador"):
            enviar_orden_compra(orden=self.orden)

    def test_una_orden_sin_lineas_no_se_envia(self):
        vacia = OrdenCompra.objects.create(
            numero="OC-R-VACIA", proveedor=self.orden.proveedor,
            bodega_entrega=self.bodega,
        )

        with self.assertRaisesMessage(ValidationError, "no tiene líneas"):
            enviar_orden_compra(orden=vacia)

    def test_recibir_una_linea_deja_la_orden_parcial(self):
        recibir_detalle_compra(
            recepcion=self._recepcion(), detalle_orden_id=self.linea_bolsa.id,
            ubicacion=self.disponible, codigo_lote="", cantidad=1000,
            usuario=self.usuario,
        )

        self.orden.refresh_from_db()
        self.assertEqual(self.orden.estado, OrdenCompra.Estado.PARCIAL)

    def test_recibirlo_todo_deja_la_orden_recibida(self):
        recepcion = self._recepcion()

        recibir_detalle_compra(
            recepcion=recepcion, detalle_orden_id=self.linea_bolsa.id,
            ubicacion=self.disponible, codigo_lote="", cantidad=1000,
            usuario=self.usuario,
        )
        recibir_detalle_compra(
            recepcion=recepcion, detalle_orden_id=self.linea_reactivo.id,
            ubicacion=self.cuarentena, codigo_lote="LOTE-R-9", cantidad=20,
            usuario=self.usuario,
        )

        self.orden.refresh_from_db()
        self.assertEqual(self.orden.estado, OrdenCompra.Estado.RECIBIDA)

    def test_una_orden_cancelada_no_se_reabre_al_recibir(self):
        """
        Los estados finales son decisiones de alguien. Recibir contra una orden
        cancelada es un problema aparte, y no se arregla cambiándole el estado
        por debajo.
        """
        self.orden.estado = OrdenCompra.Estado.CANCELADA
        self.orden.save(update_fields=["estado"])

        recibir_detalle_compra(
            recepcion=self._recepcion(), detalle_orden_id=self.linea_bolsa.id,
            ubicacion=self.disponible, codigo_lote="", cantidad=500,
            usuario=self.usuario,
        )

        self.orden.refresh_from_db()
        self.assertEqual(self.orden.estado, OrdenCompra.Estado.CANCELADA)

    def test_el_material_de_calidad_entra_en_cuarentena_y_no_se_puede_usar(self):
        from .models import LoteInventario

        detalle = recibir_detalle_compra(
            recepcion=self._recepcion(), detalle_orden_id=self.linea_reactivo.id,
            ubicacion=self.cuarentena, codigo_lote="LOTE-R-1", cantidad=20,
            usuario=self.usuario,
        )

        lote = LoteInventario.objects.get(pk=detalle.lote_id)
        self.assertEqual(lote.estado_calidad, LoteInventario.EstadoCalidad.PENDIENTE)
        self.assertFalse(lote.utilizable)

    def test_no_se_recibe_mas_de_lo_pedido(self):
        with self.assertRaisesMessage(ValidationError, "supera la cantidad pendiente"):
            recibir_detalle_compra(
                recepcion=self._recepcion(), detalle_orden_id=self.linea_bolsa.id,
                ubicacion=self.disponible, codigo_lote="", cantidad=1500,
                usuario=self.usuario,
            )


class NoConformidadTests(TestCase):
    """
    Cerrar una no conformidad de material deja constancia de qué se hizo.

    `cerrada` era un booleano suelto: decía que el asunto se acabó y no qué se
    hizo, quién lo hizo ni cuándo. Para material que Calidad rechazó, eso es
    exactamente lo que un auditor pide.
    """

    def setUp(self):
        from .models import (
            InspeccionMaterial, LiberacionExcepcionalMaterial, LoteInventario,
            NoConformidadMaterial,
        )

        self.calidad = User.objects.create_user("calidad-nc", password="x")
        PerfilUsuario.objects.create(
            usuario=self.calidad,
            nivel=PerfilUsuario.Nivel.ADMIN,
            area=PerfilUsuario.Area.CALIDAD,
        )
        self.jefe = User.objects.create_user("jefe-nc", password="x")
        self.cliente = APIClient()
        self.cliente.force_authenticate(self.calidad)

        self.insumo = Insumo.objects.create(
            codigo="NC-BOLSA", nombre="Bolsa 25 kg",
            area=PerfilUsuario.Area.BODEGA, unidad="un", requiere_calidad=True,
        )
        self.lote = LoteInventario.objects.create(
            insumo=self.insumo, codigo="PROV-NC-1",
            estado_calidad=LoteInventario.EstadoCalidad.RECHAZADO,
        )
        self.inspeccion = InspeccionMaterial.objects.create(
            lote=self.lote, estado=InspeccionMaterial.Estado.RECHAZADA
        )
        self.modelo = NoConformidadMaterial
        self.modelo_liberacion = LiberacionExcepcionalMaterial

    def _no_conformidad(self, destino=None, **extra):
        return self.modelo.objects.create(
            inspeccion=self.inspeccion,
            descripcion="Bolsas con perforaciones",
            destino=destino or self.modelo.Destino.DEVOLUCION,
            creada_por=self.calidad,
            **extra,
        )

    def _cerrar(self, nc, accion="Devueltas al proveedor con guía 4471."):
        return self.cliente.post(
            f"/api/inventario/no-conformidades/{nc.id}/cerrar/",
            {"accion_tomada": accion},
            format="json",
        )

    def _concesion(self, **extra):
        datos = {
            "lote": self.lote,
            "cantidad": 50,
            "uso_especifico": "Solo para producto de consumo interno.",
            "justificacion": "Defecto cosmético, no afecta la barrera.",
            "solicitante": self.jefe,
            "aprobada_calidad_por": self.calidad,
            "vence_en": timezone.now() + timedelta(days=30),
        }
        datos.update(extra)

        return self.modelo_liberacion.objects.create(**datos)

    # ------------------------------------------------------------- cierre

    def test_cerrar_deja_quien_cuando_y_que_hizo(self):
        nc = self._no_conformidad()

        respuesta = self._cerrar(nc)

        self.assertEqual(respuesta.status_code, 200, respuesta.data)
        nc.refresh_from_db()
        self.assertTrue(nc.cerrada)
        self.assertEqual(nc.cerrada_por, self.calidad)
        self.assertIsNotNone(nc.cerrada_en)
        self.assertIn("4471", nc.accion_tomada)

    def test_no_se_cierra_sin_decir_que_se_hizo(self):
        nc = self._no_conformidad()

        respuesta = self._cerrar(nc, accion="   ")

        self.assertEqual(respuesta.status_code, 409)
        nc.refresh_from_db()
        self.assertFalse(nc.cerrada)

    def test_no_se_cierra_dos_veces(self):
        nc = self._no_conformidad()
        self._cerrar(nc)

        respuesta = self._cerrar(nc, accion="Otra cosa")

        self.assertEqual(respuesta.status_code, 409)

    def test_no_se_puede_marcar_cerrada_por_patch(self):
        """
        El cierre pasa por su acción, que exige la constancia. Si `cerrada`
        fuera escribible, un PATCH se saltaría la regla entera.
        """
        nc = self._no_conformidad()

        self.cliente.patch(
            f"/api/inventario/no-conformidades/{nc.id}/",
            {"cerrada": True},
            format="json",
        )

        nc.refresh_from_db()
        self.assertFalse(nc.cerrada)

    # ------------------------------------------------ liberación excepcional

    def test_destino_excepcional_exige_la_concesion_enlazada(self):
        """
        «Se liberó por concesión» sin poder mostrar cuál deja el material usado
        sin respaldo — que es peor que no documentarlo, porque parece que sí
        lo tiene.
        """
        nc = self._no_conformidad(destino=self.modelo.Destino.EXCEPCIONAL)

        respuesta = self._cerrar(nc, accion="Se usó bajo concesión.")

        self.assertEqual(respuesta.status_code, 409)
        self.assertIn("concesión", str(respuesta.data))

    def test_una_concesion_vencida_no_ampara_el_cierre(self):
        vencida = self._concesion(vence_en=timezone.now() - timedelta(days=1))
        nc = self._no_conformidad(
            destino=self.modelo.Destino.EXCEPCIONAL, liberacion=vencida
        )

        respuesta = self._cerrar(nc, accion="Se usó bajo concesión.")

        self.assertEqual(respuesta.status_code, 409)
        self.assertIn("vencida", str(respuesta.data))

    def test_con_concesion_vigente_si_cierra(self):
        nc = self._no_conformidad(
            destino=self.modelo.Destino.EXCEPCIONAL, liberacion=self._concesion()
        )

        respuesta = self._cerrar(nc, accion="Se usó en producto de consumo interno.")

        self.assertEqual(respuesta.status_code, 200, respuesta.data)

    def test_vigente_mira_el_vencimiento_y_no_solo_la_marca(self):
        """`vence_en` existía desde el principio y nadie lo miraba: una
        concesión de marzo figuraba igual de válida en agosto."""
        self.assertTrue(self._concesion().vigente)
        self.assertFalse(
            self._concesion(vence_en=timezone.now() - timedelta(minutes=1)).vigente
        )
        self.assertFalse(self._concesion(activa=False).vigente)

    def test_quien_solicita_la_concesion_no_la_aprueba(self):
        """
        Misma segregación que en las solicitudes de compra, y aquí pesa más:
        lo que se autoriza es usar material que Calidad no aprobó.
        """
        respuesta = self.cliente.post(
            "/api/inventario/liberaciones-excepcionales/",
            {
                "lote": self.lote.id,
                "cantidad": "50",
                "uso_especifico": "Consumo interno",
                "justificacion": "Defecto cosmético",
                "solicitante": self.calidad.id,
                "vence_en": (timezone.now() + timedelta(days=30)).isoformat(),
            },
            format="json",
        )

        self.assertEqual(respuesta.status_code, 400)
        self.assertIn("no puede aprobarla", str(respuesta.data))

    def test_la_segunda_firma_tiene_que_ser_de_otra_persona(self):
        with self.assertRaisesMessage(ValidationError, "dos firmas"):
            self._concesion(aprobada_jefatura_por=self.calidad).full_clean()


class ConsumoBajoConcesionTests(TestCase):
    """
    Una concesión ampara **solo la cantidad autorizada**, no el lote entero.

    Antes se registraba y no hacía nada: el lote seguía bloqueado y la
    concesión documentaba algo que no podía ocurrir. Ahora es el único camino
    para sacar material que Calidad no aprobó, y el movimiento registra cuál
    lo autorizó.

    El lote sigue con `utilizable = False`, así que no entra en el stock
    disponible ni lo toma el FEFO: la concesión autoriza un uso concreto, y
    repartirlo por ahí sería lo que justamente no se autorizó.
    """

    def setUp(self):
        from .models import LiberacionExcepcionalMaterial

        self.usuario = User.objects.create_user("bodega-conc", password="x")
        PerfilUsuario.objects.create(
            usuario=self.usuario,
            nivel=PerfilUsuario.Nivel.ADMIN,
            area=PerfilUsuario.Area.BODEGA,
        )
        self.calidad = User.objects.create_user("calidad-conc", password="x")

        self.insumo = Insumo.objects.create(
            codigo="CC-BOLSA", nombre="Bolsa 25 kg",
            area=PerfilUsuario.Area.BODEGA, unidad="un", requiere_calidad=True,
        )
        bodega = Bodega.objects.create(codigo="BCC", nombre="Bodega")
        self.cuarentena = Ubicacion.objects.create(
            bodega=bodega, codigo="CUAR", tipo=Ubicacion.Tipo.CUARENTENA
        )

        self.lote = LoteInventario.objects.create(
            insumo=self.insumo, codigo="PROV-CC-1",
            estado_calidad=LoteInventario.EstadoCalidad.RECHAZADO,
        )
        self.existencia = Existencia.objects.create(
            lote=self.lote, ubicacion=self.cuarentena, cantidad_fisica=1000
        )
        self.modelo = LiberacionExcepcionalMaterial

    def _concesion(self, cantidad=200, **extra):
        datos = {
            "lote": self.lote,
            "cantidad": cantidad,
            "uso_especifico": "Solo producto de consumo interno.",
            "justificacion": "Impresión corrida; no afecta la barrera.",
            "solicitante": self.usuario,
            "aprobada_calidad_por": self.calidad,
            "vence_en": timezone.now() + timedelta(days=30),
        }
        datos.update(extra)

        return self.modelo.objects.create(**datos)

    def _sacar(self, cantidad, liberacion=None):
        return registrar_salida(
            existencia_id=self.existencia.pk, cantidad=cantidad,
            usuario=self.usuario, documento_tipo="inventario.SalidaManual",
            documento_id=0, motivo="Consumo interno autorizado", consumo=True,
            liberacion=liberacion,
        )

    # ----------------------------------------------------- sin concesión

    def test_sin_concesion_el_material_rechazado_no_sale(self):
        with self.assertRaisesMessage(ValidationError, "aprobado por Calidad"):
            self._sacar(10)

    def test_la_concesion_no_lo_vuelve_stock_disponible(self):
        """
        El lote sigue bloqueado para todo lo demás. Si entrara al disponible,
        el FEFO lo repartiría en cualquier pedido — que es lo contrario de un
        uso autorizado.
        """
        self._concesion()

        self.existencia.refresh_from_db()
        self.assertEqual(self.existencia.cantidad_disponible, Decimal("0"))
        self.assertFalse(self.lote.utilizable)

    # ----------------------------------------------------- con concesión

    def test_con_concesion_sale_y_el_movimiento_dice_cual(self):
        concesion = self._concesion()

        movimiento = self._sacar(50, liberacion=concesion)

        self.assertEqual(movimiento.liberacion, concesion)
        self.existencia.refresh_from_db()
        self.assertEqual(self.existencia.cantidad_fisica, Decimal("950"))

    def test_no_se_saca_mas_de_lo_autorizado(self):
        concesion = self._concesion(cantidad=200)

        with self.assertRaisesMessage(ValidationError, "quedan"):
            self._sacar(201, liberacion=concesion)

    def test_el_saldo_se_suma_del_libro_y_se_agota(self):
        """Un contador guardado se desincroniza, y lo que se desajustaría es
        cuánto material no aprobado salió de bodega."""
        concesion = self._concesion(cantidad=200)

        self._sacar(120, liberacion=concesion)
        concesion.refresh_from_db()
        self.assertEqual(concesion.cantidad_usada, Decimal("120"))
        self.assertEqual(concesion.saldo, Decimal("80"))

        self._sacar(80, liberacion=concesion)
        concesion.refresh_from_db()
        self.assertEqual(concesion.saldo, Decimal("0"))

        with self.assertRaisesMessage(ValidationError, "quedan"):
            self._sacar(1, liberacion=concesion)

    def test_una_concesion_de_otro_lote_no_sirve(self):
        otro = LoteInventario.objects.create(
            insumo=self.insumo, codigo="PROV-CC-2",
            estado_calidad=LoteInventario.EstadoCalidad.RECHAZADO,
        )

        with self.assertRaisesMessage(ValidationError, "es del lote"):
            self._sacar(10, liberacion=self._concesion(lote=otro))

    def test_una_concesion_vencida_no_ampara(self):
        vencida = self._concesion(vence_en=timezone.now() - timedelta(days=1))

        with self.assertRaisesMessage(ValidationError, "vencida o inactiva"):
            self._sacar(10, liberacion=vencida)

    def test_una_concesion_inactiva_no_ampara(self):
        with self.assertRaisesMessage(ValidationError, "vencida o inactiva"):
            self._sacar(10, liberacion=self._concesion(activa=False))

    def test_ni_dos_firmas_hacen_consumible_lo_vencido(self):
        """
        Una concesión asume un riesgo conocido y medido sobre la calidad del
        material. Una fecha de vencimiento pasada no es un riesgo que dos
        firmas puedan asumir.
        """
        self.lote.vencimiento = timezone.localdate() - timedelta(days=1)
        self.lote.save(update_fields=["vencimiento"])

        with self.assertRaisesMessage(ValidationError, "vencido"):
            self._sacar(10, liberacion=self._concesion())

    def test_no_se_saca_mas_de_lo_que_hay_aunque_la_concesion_alcance(self):
        """La concesión autoriza, no inventa material."""
        concesion = self._concesion(cantidad=5000)

        with self.assertRaisesMessage(ValidationError, "supera el stock"):
            self._sacar(1500, liberacion=concesion)
