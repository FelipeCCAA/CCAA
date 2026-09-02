"""Operaciones transaccionales del libro de inventario.

Ninguna vista debe modificar ``Existencia`` directamente. Cada variación
queda acompañada por un movimiento inmutable dentro de la misma transacción.
"""

from decimal import Decimal, ROUND_HALF_UP
from uuid import uuid4

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import F, Sum
from django.utils import timezone

from .models import (
    Aprobacion, Bodega, DetalleRecepcionCompra, DetalleSolicitudMaterial, Existencia,
    InspeccionMaterial, LoteInventario, MovimientoInventario, Notificacion,
    ReservaInventario, Ubicacion, Despacho, DetalleDespacho, DetalleDespachoGranel,
    ExistenciaProductoTerminado, MovimientoProductoTerminado,
)


def _ubicacion_control_producto(sucursal):
    """Ubicación física estable para producto recién envasado."""
    bodega, _ = Bodega.objects.get_or_create(
        sucursal=sucursal,
        codigo="BPT",
        defaults={"nombre": "Bodega de producto terminado", "area": "bodega"},
    )
    ubicacion, _ = Ubicacion.objects.get_or_create(
        bodega=bodega,
        codigo="PT-CUAR",
        defaults={
            "tipo": Ubicacion.Tipo.CUARENTENA,
            "descripcion": "Producto terminado pendiente de decisión de Calidad",
        },
    )
    if ubicacion.tipo != Ubicacion.Tipo.CUARENTENA:
        raise ValidationError(
            "La ubicación maestra BPT/PT-CUAR debe ser de tipo cuarentena."
        )
    return ubicacion


@transaction.atomic
def registrar_pallets_producidos(pallets, usuario):
    """Da existencia física a pallets nuevos sin anticipar la liberación."""
    pallets = list(pallets)
    if not pallets:
        return []
    sucursal = pallets[0].envase.lote.sucursal
    if any(p.envase.lote.sucursal_id != sucursal.id for p in pallets):
        raise ValidationError("Todos los pallets deben pertenecer a la misma planta.")
    ubicacion = _ubicacion_control_producto(sucursal)
    existentes = set(
        ExistenciaProductoTerminado.objects.filter(
            pallet_id__in=[p.pk for p in pallets]
        ).values_list("pallet_id", flat=True)
    )
    nuevos = [p for p in pallets if p.pk not in existentes]
    ExistenciaProductoTerminado.objects.bulk_create([
        ExistenciaProductoTerminado(pallet=p, ubicacion=ubicacion, activo=True)
        for p in nuevos
    ])
    MovimientoProductoTerminado.objects.bulk_create([
        MovimientoProductoTerminado(
            operacion=uuid4(),
            pallet=p,
            tipo=MovimientoProductoTerminado.Tipo.INGRESO,
            destino=ubicacion,
            motivo="Ingreso automático desde envasado; pendiente de Calidad",
            registrado_por=usuario,
        )
        for p in nuevos
    ])
    return list(
        ExistenciaProductoTerminado.objects.filter(pallet_id__in=[p.pk for p in pallets])
    )


def _validar_pallet_liberado(pallet):
    from calidad.models import Liberacion
    liberacion = getattr(pallet.envase.lote, "liberacion", None)
    if not liberacion or liberacion.estado not in Liberacion.ESTADOS_LIBERADO:
        raise ValidationError("El lote del pallet no tiene una liberación de Calidad vigente.")


@transaction.atomic
def ingresar_pallet(pallet, ubicacion, usuario, *, operacion=None):
    from produccion.models import PalletProducto
    pallet = PalletProducto.objects.select_for_update().select_related("envase__lote__sucursal").get(pk=pallet.pk)
    ubicacion = Ubicacion.objects.select_for_update().select_related("bodega__sucursal").get(pk=ubicacion.pk)
    _validar_pallet_liberado(pallet)
    if pallet.envase.lote.sucursal_id != ubicacion.bodega.sucursal_id:
        raise ValidationError("El pallet y la ubicación pertenecen a plantas distintas.")
    if ubicacion.tipo != Ubicacion.Tipo.DISPONIBLE:
        raise ValidationError("El destino del pallet debe ser una ubicación disponible de Bodega.")
    if pallet.estado not in {PalletProducto.Estado.LIBERADO, PalletProducto.Estado.EN_INVENTARIO}:
        raise ValidationError("El pallet no está disponible para ingresar a inventario.")
    existencia, creada = ExistenciaProductoTerminado.objects.select_for_update().get_or_create(
        pallet=pallet, defaults={"ubicacion": ubicacion, "activo": True}
    )
    # El envasado ya crea existencia física en cuarentena. Tras la liberación,
    # ingresar mueve ese mismo pallet a la ubicación disponible elegida.
    if not creada and existencia.activo and existencia.ubicacion_id == ubicacion.id:
        raise ValidationError("El pallet ya está en inventario.")
    origen = None if creada else existencia.ubicacion
    existencia.ubicacion = ubicacion
    existencia.activo = True
    existencia.save(update_fields=["ubicacion", "activo", "actualizado_en"])
    MovimientoProductoTerminado.objects.create(
        operacion=operacion or uuid4(), pallet=pallet, tipo=MovimientoProductoTerminado.Tipo.INGRESO,
        origen=origen, destino=ubicacion, registrado_por=usuario,
    )
    pallet.estado = PalletProducto.Estado.EN_INVENTARIO
    pallet.save(update_fields=["estado"])
    return existencia


@transaction.atomic
def transferir_pallet(existencia, destino, usuario, *, motivo="", operacion=None):
    existencia = ExistenciaProductoTerminado.objects.select_for_update().select_related(
        "pallet__envase__lote__sucursal", "ubicacion__bodega__sucursal"
    ).get(pk=existencia.pk)
    destino = Ubicacion.objects.select_for_update().select_related("bodega__sucursal").get(pk=destino.pk)
    if not existencia.activo:
        raise ValidationError("El pallet ya no tiene existencia activa.")
    if existencia.ubicacion.bodega.sucursal_id != destino.bodega.sucursal_id:
        raise ValidationError("La transferencia no puede cruzar plantas.")
    origen = existencia.ubicacion
    existencia.ubicacion = destino
    existencia.save(update_fields=["ubicacion", "actualizado_en"])
    MovimientoProductoTerminado.objects.create(
        operacion=operacion or uuid4(), pallet=existencia.pallet,
        tipo=MovimientoProductoTerminado.Tipo.TRANSFERENCIA, origen=origen, destino=destino,
        motivo=motivo, registrado_por=usuario,
    )
    return existencia


@transaction.atomic
def autorizar_despacho(despacho, usuario):
    despacho = Despacho.objects.select_for_update().get(pk=despacho.pk)
    if despacho.estado != Despacho.Estado.BORRADOR:
        raise ValidationError("Solo un despacho en borrador puede autorizarse.")
    detalles = list(despacho.detalles.select_related("pallet__envase__lote").select_for_update())
    graneles = list(
        despacho.detalles_granel.select_related(
            "salida__ejecucion__sucursal"
        ).select_for_update()
    )
    if not detalles and not graneles:
        raise ValidationError("El despacho debe contener pallets o producto a granel.")
    for detalle in detalles:
        _validar_pallet_liberado(detalle.pallet)
        comprometido = DetalleDespacho.objects.filter(
            pallet=detalle.pallet,
            despacho__estado=Despacho.Estado.AUTORIZADO,
        ).exclude(despacho=despacho).exists()
        if comprometido:
            raise ValidationError(f"El pallet {detalle.pallet.codigo} ya está comprometido en otro despacho.")
        if not ExistenciaProductoTerminado.objects.filter(pallet=detalle.pallet, activo=True).exists():
            raise ValidationError(f"El pallet {detalle.pallet.codigo} no está disponible en inventario.")
    from calidad.models import LiberacionProceso
    from procesos.models import SalidaProceso
    for detalle in graneles:
        salida = SalidaProceso.objects.select_for_update().select_related(
            "ejecucion__sucursal"
        ).get(pk=detalle.salida_id)
        if salida.ejecucion.sucursal_id != despacho.sucursal_id:
            raise ValidationError("La salida a granel pertenece a otra planta.")
        if salida.destino != SalidaProceso.Destino.DESPACHO_DIRECTO:
            raise ValidationError(
                f"{salida.ejecucion.codigo} no está destinada a despacho directo."
            )
        if not LiberacionProceso.objects.filter(
            salida=salida, estado=LiberacionProceso.Estado.LIBERADO
        ).exists():
            raise ValidationError(
                f"{salida.ejecucion.codigo} todavía no está liberada por Calidad."
            )
        comprometido = DetalleDespachoGranel.objects.filter(
            salida=salida,
            despacho__estado__in=[Despacho.Estado.AUTORIZADO, Despacho.Estado.DESPACHADO],
        ).exclude(despacho=despacho).aggregate(total=Sum("cantidad"))["total"] or Decimal("0")
        disponible = salida.cantidad - comprometido
        if detalle.cantidad > disponible:
            raise ValidationError(
                f"{salida.ejecucion.codigo} tiene {disponible} {salida.unidad} disponibles."
            )
    despacho.estado = Despacho.Estado.AUTORIZADO
    despacho.autorizado_por = usuario
    despacho.autorizado_en = timezone.now()
    despacho.save(update_fields=["estado", "autorizado_por", "autorizado_en"])
    return despacho


@transaction.atomic
def ejecutar_despacho(despacho, usuario):
    from produccion.models import PalletProducto
    from calidad.models import LiberacionProceso
    from procesos.models import SalidaProceso
    despacho = Despacho.objects.select_for_update().get(pk=despacho.pk)
    if despacho.estado == Despacho.Estado.DESPACHADO:
        return despacho
    if despacho.estado != Despacho.Estado.AUTORIZADO:
        raise ValidationError("El despacho debe estar autorizado.")
    detalles = list(despacho.detalles.select_related("pallet__envase__lote").select_for_update())
    graneles = list(despacho.detalles_granel.select_related("salida").select_for_update())
    for detalle in detalles:
        _validar_pallet_liberado(detalle.pallet)
        existencia = ExistenciaProductoTerminado.objects.select_for_update().select_related("ubicacion").get(
            pallet=detalle.pallet, activo=True
        )
        existencia.activo = False
        existencia.save(update_fields=["activo", "actualizado_en"])
        MovimientoProductoTerminado.objects.create(
            operacion=uuid4(), pallet=detalle.pallet, tipo=MovimientoProductoTerminado.Tipo.DESPACHO,
            origen=existencia.ubicacion, despacho=despacho, registrado_por=usuario,
        )
        detalle.pallet.estado = PalletProducto.Estado.DESPACHADO
        detalle.pallet.save(update_fields=["estado"])
    for detalle in graneles:
        salida = SalidaProceso.objects.select_for_update().get(pk=detalle.salida_id)
        if salida.destino != SalidaProceso.Destino.DESPACHO_DIRECTO:
            raise ValidationError(
                f"{salida.ejecucion.codigo} ya no está destinada a despacho directo."
            )
        if not LiberacionProceso.objects.filter(
            salida=salida, estado=LiberacionProceso.Estado.LIBERADO
        ).exists():
            raise ValidationError(
                f"{salida.ejecucion.codigo} fue bloqueada por Calidad antes del despacho."
            )
    despacho.estado = Despacho.Estado.DESPACHADO
    despacho.despachado_en = timezone.now()
    despacho.save(update_fields=["estado", "despachado_en"])
    return despacho


def _notificar_area(area, *, tipo, titulo, mensaje, documento_tipo, documento_id):
    from usuarios.models import PerfilUsuario

    destinatarios = PerfilUsuario.objects.filter(area=area, usuario__is_active=True).values_list("usuario_id", flat=True)
    Notificacion.objects.bulk_create([
        Notificacion(
            destinatario_id=usuario_id, tipo=tipo, titulo=titulo, mensaje=mensaje,
            documento_tipo=documento_tipo, documento_id=documento_id,
        )
        for usuario_id in destinatarios
    ])


def _actualizar_alertas_inventario_legacy():
    from datetime import timedelta
    from django.utils import timezone
    from .models import Alerta, Insumo

    tipos = ["stock_minimo", "punto_reposicion", "proximo_vencer", "cuarentena_atrasada"]
    Alerta.objects.filter(tipo__in=tipos, activa=True).update(activa=False, resuelta_en=timezone.now())
    nuevas = []
    for insumo in Insumo.objects.filter(activo=True):
        disponible = sum(
            (e.cantidad_disponible for e in Existencia.objects.select_related("lote").filter(lote__insumo=insumo)),
            Decimal("0"),
        )
        if insumo.stock_minimo > 0 and disponible < insumo.stock_minimo:
            nuevas.append(Alerta(tipo="stock_minimo", severidad=Alerta.Severidad.CRITICA, insumo=insumo, mensaje=f"Stock disponible {disponible}, bajo mínimo {insumo.stock_minimo}."))
        elif insumo.punto_reposicion > 0 and disponible <= insumo.punto_reposicion:
            nuevas.append(Alerta(tipo="punto_reposicion", severidad=Alerta.Severidad.ADVERTENCIA, insumo=insumo, mensaje=f"Stock disponible {disponible}, alcanzó el punto de reposición {insumo.punto_reposicion}."))
    limite = timezone.localdate() + timedelta(days=30)
    for lote in LoteInventario.objects.filter(activo=True, vencimiento__isnull=False, vencimiento__lte=limite):
        nuevas.append(Alerta(tipo="proximo_vencer", severidad=Alerta.Severidad.ADVERTENCIA, lote=lote, insumo=lote.insumo, mensaje=f"Lote {lote.codigo} vence el {lote.vencimiento}."))
    umbral = timezone.now() - timedelta(hours=48)
    for inspeccion in InspeccionMaterial.objects.filter(estado=InspeccionMaterial.Estado.PENDIENTE, creada_en__lt=umbral).select_related("lote__insumo"):
        nuevas.append(Alerta(tipo="cuarentena_atrasada", severidad=Alerta.Severidad.CRITICA, lote=inspeccion.lote, insumo=inspeccion.lote.insumo, mensaje=f"Lote {inspeccion.lote.codigo} lleva más de 48 horas en cuarentena."))
    Alerta.objects.bulk_create(nuevas)
    return nuevas


def actualizar_alertas_inventario():
    """Recalcula alertas por sucursal, sin mezclar saldos entre tenants."""
    from datetime import timedelta

    from usuarios.models import Sucursal
    from .models import Alerta, Insumo

    tipos = ["stock_minimo", "punto_reposicion", "proximo_vencer", "cuarentena_atrasada"]
    Alerta.objects.filter(tipo__in=tipos, activa=True).update(
        activa=False, resuelta_en=timezone.now()
    )
    nuevas = []
    for insumo in Insumo.objects.filter(activo=True):
        for sucursal in Sucursal.objects.filter(empresa_id=insumo.empresa_id):
            existencias = Existencia.objects.select_related("lote").filter(
                lote__insumo=insumo, lote__sucursal=sucursal
            )
            disponible = sum((e.cantidad_disponible for e in existencias), Decimal("0"))
            if insumo.stock_minimo > 0 and disponible < insumo.stock_minimo:
                nuevas.append(Alerta(
                    sucursal=sucursal, tipo="stock_minimo",
                    severidad=Alerta.Severidad.CRITICA, insumo=insumo,
                    mensaje=f"Stock disponible {disponible}, bajo mínimo {insumo.stock_minimo}.",
                ))
            elif insumo.punto_reposicion > 0 and disponible <= insumo.punto_reposicion:
                nuevas.append(Alerta(
                    sucursal=sucursal, tipo="punto_reposicion",
                    severidad=Alerta.Severidad.ADVERTENCIA, insumo=insumo,
                    mensaje=f"Stock disponible {disponible}, alcanzó el punto de reposición {insumo.punto_reposicion}.",
                ))
    limite = timezone.localdate() + timedelta(days=30)
    for lote in LoteInventario.objects.filter(
        activo=True, vencimiento__isnull=False, vencimiento__lte=limite
    ):
        nuevas.append(Alerta(
            sucursal=lote.sucursal, tipo="proximo_vencer",
            severidad=Alerta.Severidad.ADVERTENCIA, lote=lote, insumo=lote.insumo,
            mensaje=f"Lote {lote.codigo} vence el {lote.vencimiento}.",
        ))
    umbral = timezone.now() - timedelta(hours=48)
    inspecciones = InspeccionMaterial.objects.filter(
        estado=InspeccionMaterial.Estado.PENDIENTE, creada_en__lt=umbral
    ).select_related("lote__insumo", "lote__sucursal")
    for inspeccion in inspecciones:
        nuevas.append(Alerta(
            sucursal=inspeccion.lote.sucursal, tipo="cuarentena_atrasada",
            severidad=Alerta.Severidad.CRITICA, lote=inspeccion.lote,
            insumo=inspeccion.lote.insumo,
            mensaje=f"Lote {inspeccion.lote.codigo} lleva más de 48 horas en cuarentena.",
        ))
    Alerta.objects.bulk_create(nuevas)
    return nuevas


@transaction.atomic
def decidir_solicitud_compra(*, solicitud, aprobador, decision, comentario=""):
    from .models import SolicitudCompra

    solicitud = SolicitudCompra.objects.select_for_update().get(pk=solicitud.pk)
    if solicitud.solicitante_id == aprobador.id:
        raise ValidationError("El solicitante no puede aprobar su propia solicitud.")
    if solicitud.estado not in {SolicitudCompra.Estado.ENVIADA, SolicitudCompra.Estado.PENDIENTE}:
        raise ValidationError("La solicitud no está pendiente de aprobación.")
    if decision not in Aprobacion.Decision.values:
        raise ValidationError("La decisión no es válida.")
    Aprobacion.objects.create(
        sucursal=solicitud.sucursal,
        documento_tipo="inventario.SolicitudCompra", documento_id=solicitud.pk,
        aprobador=aprobador, decision=decision, comentario=comentario,
    )
    solicitud.estado = (
        SolicitudCompra.Estado.APROBADA
        if decision == Aprobacion.Decision.APROBADA
        else SolicitudCompra.Estado.RECHAZADA
    )
    solicitud.save(update_fields=["estado"])
    return solicitud


def _cantidad(valor) -> Decimal:
    cantidad = Decimal(str(valor))
    if cantidad <= 0:
        raise ValidationError("La cantidad debe ser mayor que cero.")
    return cantidad


def catalogos_de_receta():
    """
    Productos y recetas cargados una vez, listos para explotar.

    `explosionar` no consulta la base a propósito —es dominio puro— así que
    quien la llama tiene que traerle los catálogos. Se cargan aquí y no dentro
    del bucle: el MRP semanal explota un bloque por cada turno programado, y
    releer el maestro en cada vuelta sería una consulta por bloque.
    """
    from maestros.models import Producto, Receta

    return (
        list(Producto.objects.all()),
        list(
            Receta.objects.prefetch_related(
                "componentes__insumo", "componentes__producto"
            )
        ),
    )


def insumos_requeridos(*, producto_id, cantidad, fecha, catalogos=None):
    """
    Qué insumos consume producir `cantidad` de un producto, y cuántos.

    Devuelve `{insumo_id: Decimal}`. La receta se resuelve **a esa fecha**: un
    lote de mayo se calcula con las cantidades de mayo, que es para lo que
    `Receta` está versionada.

    Es multinivel: si el producto se hace de crema y la crema lleva su propio
    empaque, ese empaque entra también. Antes esto era una tabla plana por
    producto y el segundo nivel simplemente no existía.

    Los tres caminos que calculan consumo —el descuento del lote, el MRP
    semanal y el MRP puntual— pasan por aquí. Con tres implementaciones, la
    orden de compra y el descuento podían pedir cantidades distintas para la
    misma fórmula.
    """
    from maestros.recetas import explosionar

    productos, recetas = catalogos if catalogos is not None else catalogos_de_receta()

    explosion = explosionar(productos, recetas, producto_id, float(cantidad), fecha)

    # La explosión trabaja en float —es aritmética de árbol, no de dinero—; se
    # vuelve a Decimal antes de que el número toque existencias o una orden de
    # compra, que es donde el redondeo tiene consecuencias.
    return explosion, {
        insumo_id: Decimal(str(total)).quantize(
            Decimal("0.001"), rounding=ROUND_HALF_UP
        )
        for insumo_id, total in explosion.insumos.items()
    }


@transaction.atomic
def registrar_entrada(*, lote, ubicacion, cantidad, usuario, documento_tipo, documento_id):
    cantidad = _cantidad(cantidad)
    if lote.utilizable and ubicacion.tipo != Ubicacion.Tipo.DISPONIBLE:
        raise ValidationError("Un lote aprobado debe ingresar a una ubicación disponible.")
    if not lote.utilizable and ubicacion.tipo != Ubicacion.Tipo.CUARENTENA:
        raise ValidationError("Un lote pendiente de Calidad solo puede ingresar a cuarentena.")
    existencia, _ = Existencia.objects.select_for_update().get_or_create(
        lote=lote, ubicacion=ubicacion,
        defaults={"cantidad_fisica": 0, "cantidad_reservada": 0},
    )
    anterior = existencia.cantidad_fisica
    existencia.cantidad_fisica = F("cantidad_fisica") + cantidad
    existencia.save(update_fields=["cantidad_fisica"])
    existencia.refresh_from_db()
    movimiento = MovimientoInventario(
        tipo=MovimientoInventario.Tipo.RECEPCION,
        lote=lote, cantidad=cantidad, destino=ubicacion,
        documento_tipo=documento_tipo, documento_id=documento_id, usuario=usuario,
        saldo_anterior=anterior, saldo_posterior=existencia.cantidad_fisica,
    )
    movimiento.full_clean()
    movimiento.save()
    return movimiento


@transaction.atomic
def registrar_salida(*, existencia_id, cantidad, usuario, documento_tipo, documento_id, motivo, consumo=False, liberacion=None):
    """
    Descuenta material liberado dejando un movimiento auditable.

    `liberacion` es el único camino para sacar material que Calidad **no**
    aprobó, y ampara **solo la cantidad autorizada** — no el lote entero. Un
    lote bajo concesión sigue con `utilizable = False`, así que no entra en el
    stock disponible ni lo toma el FEFO: la concesión autoriza un uso concreto
    y repartirlo por ahí sería justamente lo que no se autorizó.

    Lo vencido no se ampara. Una concesión asume un riesgo conocido y medido
    sobre la calidad del material; una fecha de vencimiento pasada no es un
    riesgo que dos firmas puedan asumir.
    """
    cantidad = _cantidad(cantidad)
    existencia = Existencia.objects.select_for_update().select_related("lote", "ubicacion").get(pk=existencia_id)

    if liberacion is None:
        if not existencia.lote.utilizable or existencia.ubicacion.tipo != Ubicacion.Tipo.DISPONIBLE:
            raise ValidationError("Solo puede salir o consumirse material aprobado por Calidad y vigente.")
    else:
        _validar_concesion(liberacion, existencia, cantidad)

    if existencia.cantidad_fisica - existencia.cantidad_reservada < cantidad:
        raise ValidationError("La salida supera el stock disponible no reservado.")
    if not str(motivo).strip():
        raise ValidationError("La salida o consumo exige un motivo.")
    anterior = existencia.cantidad_fisica
    existencia.cantidad_fisica -= cantidad
    existencia.full_clean()
    existencia.save(update_fields=["cantidad_fisica"])
    movimiento = MovimientoInventario.objects.create(
        tipo=MovimientoInventario.Tipo.CONSUMO if consumo else MovimientoInventario.Tipo.SALIDA,
        lote=existencia.lote, cantidad=cantidad, origen=existencia.ubicacion,
        documento_tipo=documento_tipo, documento_id=documento_id,
        usuario=usuario, motivo=motivo, saldo_anterior=anterior,
        saldo_posterior=existencia.cantidad_fisica,
        liberacion=liberacion,
    )
    actualizar_alertas_inventario()
    return movimiento


def _validar_concesion(liberacion, existencia, cantidad):
    """
    Qué tiene que cumplirse para sacar material bajo concesión.

    Se bloquea la concesión con `select_for_update` antes de sumar lo ya
    usado: sin eso, dos salidas simultáneas leen el mismo saldo y las dos se
    aprueban, que es como se consume el doble de lo autorizado.
    """
    from .models import LiberacionExcepcionalMaterial

    liberacion = (
        LiberacionExcepcionalMaterial.objects.select_for_update()
        .select_related("lote")
        .get(pk=liberacion.pk)
    )

    if liberacion.lote_id != existencia.lote_id:
        raise ValidationError(
            f"La concesión es del lote {liberacion.lote.codigo}, no de este."
        )

    if not liberacion.vigente:
        raise ValidationError(
            "La concesión está vencida o inactiva: ya no ampara el uso del "
            "material."
        )

    # Ni dos firmas hacen consumible lo vencido.
    if existencia.lote.vencido:
        raise ValidationError(
            "El lote está vencido. Una concesión cubre un defecto de calidad, "
            "no una fecha de vencimiento pasada."
        )

    if cantidad > liberacion.saldo:
        raise ValidationError(
            f"La concesión autorizó {liberacion.cantidad} y quedan "
            f"{liberacion.saldo}."
        )


@transaction.atomic
def ingresar_material_manual(*, insumo, codigo_lote, ubicacion, cantidad, usuario, elaboracion=None, vencimiento=None):
    """Crea el lote de proveedor y su entrada; Calidad decide su disponibilidad."""
    from .models import InspeccionMaterial

    if insumo.requiere_lote and not str(codigo_lote).strip():
        raise ValidationError("El material exige un código de lote.")
    if insumo.requiere_vencimiento and not vencimiento:
        raise ValidationError("El material exige fecha de vencimiento.")
    estado = (
        LoteInventario.EstadoCalidad.PENDIENTE
        if insumo.requiere_calidad else LoteInventario.EstadoCalidad.NO_REQUIERE
    )
    sucursal = ubicacion.bodega.sucursal
    if insumo.empresa_id != sucursal.empresa_id:
        raise ValidationError("El material y la ubicación pertenecen a empresas distintas.")
    codigo = codigo_lote or f"SIN-LOTE-{timezone.now():%Y%m%d%H%M%S}"
    lote = LoteInventario.objects.filter(
        sucursal=sucursal, insumo=insumo, codigo=codigo, proveedor=None
    ).first()
    if lote is None:
        lote = LoteInventario.objects.create(
            sucursal=sucursal, insumo=insumo, codigo=codigo,
            elaboracion=elaboracion or None, vencimiento=vencimiento or None,
            estado_calidad=estado,
        )
    elif lote.estado_calidad != estado:
        raise ValidationError("El lote existente tiene un estado de Calidad incompatible.")
    movimiento = registrar_entrada(
        lote=lote, ubicacion=ubicacion, cantidad=cantidad, usuario=usuario,
        documento_tipo="inventario.IngresoManual", documento_id=lote.pk,
    )
    if insumo.requiere_calidad and not InspeccionMaterial.objects.filter(lote=lote).exists():
        InspeccionMaterial.objects.create(lote=lote, estado=InspeccionMaterial.Estado.PENDIENTE)
    return movimiento


@transaction.atomic
def consumir_receta_produccion(*, lote_produccion, usuario):
    """
    Descuenta por FEFO los insumos que la receta del lote declara.

    La receta se resuelve **a la fecha del lote**, no a la de hoy: un lote de
    mayo se descuenta con las cantidades que regían en mayo. Antes esto leía
    `ConsumoProducto`, una tabla plana sin versión, así que corregir una
    fórmula reescribía en silencio lo que había costado producir seis meses
    atrás — y `ConsumoLoteProduccion` decía ser la cabecera auditable de ese
    cálculo.

    La explosión es multinivel: si el producto se hace de crema y la crema
    lleva su propio empaque, ese empaque también entra. Por eso se usa
    `explosionar` y no se recorren los componentes a mano.
    """
    from .models import ConsumoLoteProduccion, Insumo

    if lote_produccion.estado == lote_produccion.Estado.ANULADO:
        raise ValidationError("No se puede consumir inventario para un lote anulado.")
    if not lote_produccion.kg_producidos or lote_produccion.kg_producidos <= 0:
        raise ValidationError("El lote debe tener kilos producidos informados.")
    if ConsumoLoteProduccion.objects.filter(lote_produccion=lote_produccion).exists():
        raise ValidationError("La receta de este lote de Producción ya fue consumida.")

    explosion, requerido = insumos_requeridos(
        producto_id=lote_produccion.producto_id,
        cantidad=lote_produccion.kg_producidos,
        fecha=lote_produccion.fecha,
    )

    if not requerido:
        raise ValidationError(
            "La receta vigente del producto no declara insumos que descontar."
        )

    # Una cadena cortada da un número que se parece demasiado a uno completo:
    # descontar con él dejaría el saldo de bodega mintiendo.
    if not explosion.completa:
        raise ValidationError(
            "La receta no se puede explotar hasta el final: hay un producto sin "
            "receta o un ciclo. Corrígela antes de descontar."
        )

    por_id = {i.id: i for i in Insumo.objects.filter(id__in=requerido)}

    cabecera = ConsumoLoteProduccion.objects.create(
        lote_produccion=lote_produccion, kg_base=lote_produccion.kg_producidos,
        registrado_por=usuario,
    )
    movimientos = []
    # Orden estable: el diccionario de la explosión no lo garantiza, y dos
    # ejecuciones que tomen los lotes en distinto orden dan movimientos
    # distintos para el mismo consumo.
    for insumo_id in sorted(requerido):
        insumo = por_id[insumo_id]
        restante = requerido[insumo_id]
        if restante <= 0:
            continue
        candidatas = Existencia.objects.select_for_update().select_related("lote", "ubicacion").filter(
            lote__insumo=insumo, lote__activo=True,
            ubicacion__tipo=Ubicacion.Tipo.DISPONIBLE,
        ).order_by(F("lote__vencimiento").asc(nulls_last=True), "lote__recibido_en", "id")
        for existencia in candidatas:
            disponible = existencia.cantidad_disponible
            if disponible <= 0:
                continue
            tomada = min(disponible, restante)
            movimientos.append(registrar_salida(
                existencia_id=existencia.pk, cantidad=tomada, usuario=usuario,
                documento_tipo="produccion.Lote", documento_id=lote_produccion.pk,
                motivo=f"Consumo automático receta · {lote_produccion.codigo_lote}", consumo=True,
            ))
            restante -= tomada
            if restante == 0:
                break
        if restante > 0:
            raise ValidationError(f"Stock insuficiente de {insumo.nombre}. Faltan {restante}.")
    return cabecera, movimientos


@transaction.atomic
def cambiar_estado_calidad(*, lote_id, estado, usuario, documento_tipo, documento_id, motivo=""):
    lote = LoteInventario.objects.select_for_update().get(pk=lote_id)
    permitidos = {
        LoteInventario.EstadoCalidad.PENDIENTE: {
            LoteInventario.EstadoCalidad.MUESTRA,
            LoteInventario.EstadoCalidad.ANALISIS,
            LoteInventario.EstadoCalidad.APROBADO,
            LoteInventario.EstadoCalidad.RECHAZADO,
            LoteInventario.EstadoCalidad.BLOQUEADO,
        },
        LoteInventario.EstadoCalidad.MUESTRA: {
            LoteInventario.EstadoCalidad.ANALISIS,
            LoteInventario.EstadoCalidad.APROBADO,
            LoteInventario.EstadoCalidad.RECHAZADO,
        },
        LoteInventario.EstadoCalidad.ANALISIS: {
            LoteInventario.EstadoCalidad.APROBADO,
            LoteInventario.EstadoCalidad.OBSERVADO,
            LoteInventario.EstadoCalidad.RECHAZADO,
            LoteInventario.EstadoCalidad.BLOQUEADO,
        },
    }
    if estado not in permitidos.get(lote.estado_calidad, set()):
        raise ValidationError(f"No se puede pasar de {lote.estado_calidad} a {estado}.")
    lote.estado_calidad = estado
    lote.save(update_fields=["estado_calidad"])
    tipo = MovimientoInventario.Tipo.LIBERACION if lote.utilizable else (
        MovimientoInventario.Tipo.RECHAZO if estado == LoteInventario.EstadoCalidad.RECHAZADO
        else MovimientoInventario.Tipo.BLOQUEO
    )
    for existencia in Existencia.objects.select_for_update().filter(lote=lote):
        MovimientoInventario.objects.create(
            tipo=tipo, lote=lote, cantidad=existencia.cantidad_fisica,
            origen=existencia.ubicacion, destino=existencia.ubicacion,
            documento_tipo=documento_tipo, documento_id=documento_id,
            usuario=usuario, motivo=motivo,
            saldo_anterior=existencia.cantidad_fisica,
            saldo_posterior=existencia.cantidad_fisica,
        )
    return lote


@transaction.atomic
def reservar_fefo(*, insumo_id, cantidad, usuario, documento_tipo, documento_id):
    cantidad = _cantidad(cantidad)
    candidatas = list(
        Existencia.objects.select_for_update()
        .select_related("lote", "ubicacion")
        .filter(lote__insumo_id=insumo_id, lote__activo=True)
        .order_by(F("lote__vencimiento").asc(nulls_last=True), "lote__recibido_en", "id")
    )
    restantes = cantidad
    reservas = []
    for existencia in candidatas:
        disponible = existencia.cantidad_disponible
        if disponible <= 0:
            continue
        tomada = min(disponible, restantes)
        anterior = existencia.cantidad_reservada
        existencia.cantidad_reservada += tomada
        existencia.full_clean()
        existencia.save(update_fields=["cantidad_reservada"])
        MovimientoInventario.objects.create(
            tipo=MovimientoInventario.Tipo.RESERVA, lote=existencia.lote,
            cantidad=tomada, origen=existencia.ubicacion,
            documento_tipo=documento_tipo, documento_id=documento_id,
            usuario=usuario, saldo_anterior=anterior,
            saldo_posterior=existencia.cantidad_reservada,
        )
        reservas.append((existencia, tomada))
        restantes -= tomada
        if restantes == 0:
            break
    if restantes > 0:
        raise ValidationError(f"Stock disponible insuficiente. Faltan {restantes}.")
    return reservas


@transaction.atomic
def entregar_reserva(*, existencia_id, cantidad, destino, usuario, documento_tipo, documento_id):
    cantidad = _cantidad(cantidad)
    existencia = Existencia.objects.select_for_update().select_related("lote", "ubicacion").get(pk=existencia_id)
    if not existencia.lote.utilizable:
        raise ValidationError("El lote no está aprobado, está bloqueado, rechazado o vencido.")
    if existencia.cantidad_reservada < cantidad or existencia.cantidad_fisica < cantidad:
        raise ValidationError("La cantidad supera la existencia reservada.")
    anterior = existencia.cantidad_fisica
    existencia.cantidad_fisica -= cantidad
    existencia.cantidad_reservada -= cantidad
    existencia.full_clean()
    existencia.save(update_fields=["cantidad_fisica", "cantidad_reservada"])
    destino_existencia, _ = Existencia.objects.select_for_update().get_or_create(
        lote=existencia.lote, ubicacion=destino,
        defaults={"cantidad_fisica": 0, "cantidad_reservada": 0},
    )
    destino_existencia.cantidad_fisica = F("cantidad_fisica") + cantidad
    destino_existencia.save(update_fields=["cantidad_fisica"])
    return MovimientoInventario.objects.create(
        tipo=MovimientoInventario.Tipo.ENTREGA, lote=existencia.lote,
        cantidad=cantidad, origen=existencia.ubicacion, destino=destino,
        documento_tipo=documento_tipo, documento_id=documento_id,
        usuario=usuario, saldo_anterior=anterior,
        saldo_posterior=existencia.cantidad_fisica,
    )


def _avanzar_estado_orden(orden):
    """
    Mueve la orden a parcial o recibida según lo que ya llegó.

    Sin `atomic` propio: siempre se llama desde dentro de la transacción de la
    recepción, y un punto de retorno anidado aquí no protegería nada que la de
    afuera no proteja ya.

    Los dos estados existían en el modelo y no los ponía nadie: una orden
    entregada por completo seguía figurando abierta, y Compras no tenía cómo
    saber qué estaba pendiente sin sumar las líneas a mano.

    Se guarda en vez de derivarse porque el resto de los estados —cancelada,
    cerrada— son decisiones de alguien y no se deducen de las cantidades. Un
    campo mitad calculado y mitad decidido confunde más de lo que ahorra.

    Las canceladas y cerradas no se tocan: son finales, y recibir contra una
    orden cerrada es un problema aparte que no se arregla cambiándole el
    estado por debajo.
    """
    from .models import OrdenCompra

    if orden.estado in {OrdenCompra.Estado.CANCELADA, OrdenCompra.Estado.CERRADA}:
        return

    detalles = list(orden.detalles.all())
    completa = all(d.cantidad_recibida >= d.cantidad for d in detalles)
    algo = any(d.cantidad_recibida > 0 for d in detalles)

    nuevo = (
        OrdenCompra.Estado.RECIBIDA
        if detalles and completa
        else OrdenCompra.Estado.PARCIAL if algo else orden.estado
    )

    if nuevo != orden.estado:
        orden.estado = nuevo
        orden.save(update_fields=["estado"])


@transaction.atomic
def enviar_orden_compra(*, orden):
    """
    La orden sale al proveedor.

    Hasta que se envía es un borrador: el MRP no la cuenta como recepción
    programada, y con razón — un borrador no compromete a nadie. Enviarla es
    lo que la vuelve un compromiso, y a partir de ahí resta de lo que hay que
    volver a pedir.
    """
    from .models import OrdenCompra

    if orden.estado != OrdenCompra.Estado.BORRADOR:
        raise ValidationError(
            f"La orden está «{orden.get_estado_display()}»: solo se envía un borrador."
        )

    if not orden.detalles.exists():
        raise ValidationError("La orden no tiene líneas que enviar.")

    orden.estado = OrdenCompra.Estado.ENVIADA
    orden.save(update_fields=["estado"])

    return orden


@transaction.atomic
def recibir_detalle_compra(*, recepcion, detalle_orden_id, ubicacion, codigo_lote,
                           cantidad, usuario, vencimiento=None, elaboracion=None,
                           cantidad_danada=0, temperatura=None,
                           embalaje_conforme=True, certificado_recibido=False):
    from .models import DetalleOrdenCompra

    detalle_orden = DetalleOrdenCompra.objects.select_for_update().select_related("insumo", "orden__proveedor").get(pk=detalle_orden_id)
    insumo = detalle_orden.insumo
    cantidad = _cantidad(cantidad)
    if detalle_orden.cantidad_recibida + cantidad > detalle_orden.cantidad:
        raise ValidationError("La recepción supera la cantidad pendiente de la orden.")
    if insumo.requiere_lote and not str(codigo_lote).strip():
        raise ValidationError("Este material exige número de lote.")
    if insumo.requiere_vencimiento and vencimiento is None:
        raise ValidationError("Este material exige fecha de vencimiento.")
    if insumo.requiere_temperatura and temperatura is None:
        raise ValidationError("Este material exige temperatura de recepción.")
    if insumo.requiere_certificado and not certificado_recibido:
        raise ValidationError("Este material exige certificado del proveedor.")
    if insumo.requiere_calidad and ubicacion.tipo != Ubicacion.Tipo.CUARENTENA:
        raise ValidationError("El material sujeto a Calidad debe ingresar a cuarentena.")

    estado = (
        LoteInventario.EstadoCalidad.PENDIENTE
        if insumo.requiere_calidad else LoteInventario.EstadoCalidad.NO_REQUIERE
    )
    lote = LoteInventario.objects.create(
        insumo=insumo, proveedor=detalle_orden.orden.proveedor,
        codigo=codigo_lote or f"SIN-LOTE-{recepcion.pk}-{detalle_orden.pk}",
        elaboracion=elaboracion, vencimiento=vencimiento, estado_calidad=estado,
    )
    detalle = DetalleRecepcionCompra.objects.create(
        recepcion=recepcion, detalle_orden=detalle_orden, lote=lote,
        ubicacion_temporal=ubicacion, cantidad_recibida=cantidad,
        cantidad_danada=cantidad_danada, temperatura=temperatura,
        embalaje_conforme=embalaje_conforme,
        certificado_recibido=certificado_recibido,
    )
    util = cantidad - Decimal(str(cantidad_danada))
    if util <= 0:
        raise ValidationError("La cantidad utilizable debe ser mayor que cero.")
    registrar_entrada(
        lote=lote, ubicacion=ubicacion, cantidad=util, usuario=usuario,
        documento_tipo="inventario.DetalleRecepcionCompra", documento_id=detalle.pk,
    )
    detalle_orden.cantidad_recibida += cantidad
    detalle_orden.save(update_fields=["cantidad_recibida"])
    _avanzar_estado_orden(detalle_orden.orden)
    if insumo.requiere_calidad:
        from django.db.models import Q
        from .models import PlantillaInspeccion
        hoy = lote.recibido_en.date()
        plantilla = PlantillaInspeccion.objects.filter(
            Q(insumo=insumo) | Q(insumo__isnull=True, categoria=insumo.categoria),
            activa=True, vigente_desde__lte=hoy,
        ).filter(Q(vigente_hasta__isnull=True) | Q(vigente_hasta__gte=hoy)).order_by("-insumo_id", "-version").first()
        InspeccionMaterial.objects.create(lote=lote, plantilla=plantilla)
        from usuarios.models import PerfilUsuario
        _notificar_area(
            PerfilUsuario.Area.CALIDAD, tipo="inspeccion_material_solicitada",
            titulo="Material en cuarentena",
            mensaje=f"{insumo.nombre}, lote {lote.codigo}, requiere inspección.",
            documento_tipo="inventario.LoteInventario", documento_id=lote.pk,
        )
    actualizar_alertas_inventario()
    return detalle


@transaction.atomic
def decidir_inspeccion(*, inspeccion_id, decision, usuario, resultados, observaciones=""):
    inspeccion = InspeccionMaterial.objects.select_for_update().select_related("lote").get(pk=inspeccion_id)
    mapa = {
        InspeccionMaterial.Estado.APROBADA: LoteInventario.EstadoCalidad.APROBADO,
        InspeccionMaterial.Estado.OBSERVADA: LoteInventario.EstadoCalidad.OBSERVADO,
        InspeccionMaterial.Estado.RECHAZADA: LoteInventario.EstadoCalidad.RECHAZADO,
        InspeccionMaterial.Estado.BLOQUEADA: LoteInventario.EstadoCalidad.BLOQUEADO,
    }
    if decision not in mapa:
        raise ValidationError("La decisión final no es válida.")
    if inspeccion.estado in mapa:
        raise ValidationError("La inspección ya tiene una decisión final.")
    if inspeccion.plantilla_id:
        for campo in inspeccion.plantilla.campos:
            clave = campo.get("clave")
            if campo.get("obligatorio") and (clave not in resultados or resultados.get(clave) in (None, "")):
                raise ValidationError(f"Falta completar el campo obligatorio '{clave}'.")
            valor = resultados.get(clave)
            if valor not in (None, "") and isinstance(valor, (int, float)):
                if campo.get("min") is not None and valor < campo["min"]:
                    raise ValidationError(f"'{clave}' está bajo el mínimo permitido.")
                if campo.get("max") is not None and valor > campo["max"]:
                    raise ValidationError(f"'{clave}' supera el máximo permitido.")
    inspeccion.estado = decision
    inspeccion.responsable = usuario
    inspeccion.resultados = resultados
    inspeccion.observaciones = observaciones
    from django.utils import timezone
    inspeccion.decidida_en = timezone.now()
    inspeccion.save(update_fields=["estado", "responsable", "resultados", "observaciones", "decidida_en"])
    cambiar_estado_calidad(
        lote_id=inspeccion.lote_id, estado=mapa[decision], usuario=usuario,
        documento_tipo="inventario.InspeccionMaterial", documento_id=inspeccion.pk,
        motivo=observaciones,
    )
    from usuarios.models import PerfilUsuario
    for area in (PerfilUsuario.Area.BODEGA, PerfilUsuario.Area.COMPRAS):
        _notificar_area(
            area, tipo=f"material_{decision}",
            titulo=f"Decisión de Calidad: {inspeccion.lote.insumo.nombre}",
            mensaje=f"Lote {inspeccion.lote.codigo}: {decision}.",
            documento_tipo="inventario.InspeccionMaterial", documento_id=inspeccion.pk,
        )
    actualizar_alertas_inventario()
    return inspeccion


@transaction.atomic
def reservar_solicitud_material(*, solicitud, usuario):
    if solicitud.estado not in {solicitud.Estado.ENVIADA, solicitud.Estado.APROBADA}:
        raise ValidationError("La MRQ no está lista para reservar.")
    for detalle in DetalleSolicitudMaterial.objects.select_for_update().filter(solicitud=solicitud):
        cantidad = detalle.cantidad_aprobada or detalle.cantidad_solicitada
        if not detalle.cantidad_aprobada:
            detalle.cantidad_aprobada = cantidad
            detalle.save(update_fields=["cantidad_aprobada"])
        selecciones = reservar_fefo(
            insumo_id=detalle.insumo_id, cantidad=cantidad, usuario=usuario,
            documento_tipo="inventario.SolicitudMaterial", documento_id=solicitud.pk,
        )
        for existencia, tomada in selecciones:
            ReservaInventario.objects.create(detalle=detalle, existencia=existencia, cantidad=tomada)
    solicitud.estado = solicitud.Estado.PREPARADA
    solicitud.save(update_fields=["estado"])
    actualizar_alertas_inventario()
    return solicitud


@transaction.atomic
def entregar_solicitud_material(*, solicitud, destino, entrega_por, recibe_por, selecciones=None, observaciones=""):
    from .models import DetalleEntregaProduccion, EntregaProduccion, SolicitudMaterial

    solicitud = SolicitudMaterial.objects.select_for_update().get(pk=solicitud.pk)
    if solicitud.estado not in {SolicitudMaterial.Estado.PREPARADA, SolicitudMaterial.Estado.PARCIAL}:
        raise ValidationError("La MRQ no está preparada para entrega.")
    reservas = ReservaInventario.objects.select_for_update().select_related(
        "existencia__lote", "detalle"
    ).filter(detalle__solicitud=solicitud, activa=True)
    por_id = {int(item["reserva"]): Decimal(str(item["cantidad"])) for item in (selecciones or [])}
    entrega = EntregaProduccion.objects.create(
        solicitud=solicitud, entregada_por=entrega_por,
        recibida_por=recibe_por, observaciones=observaciones,
    )
    alguna = False
    for reserva in reservas:
        cantidad = por_id.get(reserva.pk, reserva.cantidad if not selecciones else Decimal("0"))
        if cantidad <= 0:
            continue
        if cantidad > reserva.cantidad:
            raise ValidationError("La entrega supera la cantidad reservada.")
        entregar_reserva(
            existencia_id=reserva.existencia_id, cantidad=cantidad, destino=destino,
            usuario=entrega_por, documento_tipo="inventario.EntregaProduccion",
            documento_id=entrega.pk,
        )
        DetalleEntregaProduccion.objects.create(
            entrega=entrega, detalle_solicitud=reserva.detalle,
            lote=reserva.existencia.lote, cantidad=cantidad,
        )
        reserva.detalle.cantidad_entregada = F("cantidad_entregada") + cantidad
        reserva.detalle.save(update_fields=["cantidad_entregada"])
        reserva.cantidad -= cantidad
        reserva.activa = reserva.cantidad > 0
        reserva.save(update_fields=["cantidad", "activa"])
        alguna = True
    if not alguna:
        raise ValidationError("No se seleccionó ninguna cantidad para entregar.")
    pendientes = DetalleSolicitudMaterial.objects.filter(solicitud=solicitud).filter(
        cantidad_entregada__lt=F("cantidad_aprobada")
    ).exists()
    solicitud.estado = SolicitudMaterial.Estado.PARCIAL if pendientes else SolicitudMaterial.Estado.ENTREGADA
    solicitud.save(update_fields=["estado"])
    actualizar_alertas_inventario()
    return entrega


@transaction.atomic
def trasladar_existencia(*, existencia_id, destino, cantidad, usuario, documento_tipo, documento_id, motivo=""):
    cantidad = _cantidad(cantidad)
    origen = Existencia.objects.select_for_update().select_related("lote", "ubicacion").get(pk=existencia_id)
    if origen.cantidad_fisica < cantidad or origen.cantidad_fisica - origen.cantidad_reservada < cantidad:
        raise ValidationError("La cantidad supera el saldo físico no reservado.")
    if origen.lote.estado_calidad in {
        LoteInventario.EstadoCalidad.PENDIENTE,
        LoteInventario.EstadoCalidad.MUESTRA,
        LoteInventario.EstadoCalidad.ANALISIS,
    } and destino.tipo != Ubicacion.Tipo.CUARENTENA:
        raise ValidationError("Un lote en cuarentena solo puede trasladarse a otra ubicación de cuarentena.")
    if origen.lote.estado_calidad in {
        LoteInventario.EstadoCalidad.RECHAZADO,
        LoteInventario.EstadoCalidad.BLOQUEADO,
    } and destino.tipo != Ubicacion.Tipo.RECHAZADO:
        raise ValidationError("Un lote rechazado o bloqueado solo puede ir a una ubicación de rechazados.")
    anterior = origen.cantidad_fisica
    origen.cantidad_fisica -= cantidad
    origen.save(update_fields=["cantidad_fisica"])
    llegada, _ = Existencia.objects.select_for_update().get_or_create(
        lote=origen.lote, ubicacion=destino,
        defaults={"cantidad_fisica": 0, "cantidad_reservada": 0},
    )
    llegada.cantidad_fisica = F("cantidad_fisica") + cantidad
    llegada.save(update_fields=["cantidad_fisica"])
    movimiento = MovimientoInventario.objects.create(
        tipo=MovimientoInventario.Tipo.TRASLADO, lote=origen.lote,
        cantidad=cantidad, origen=origen.ubicacion, destino=destino,
        documento_tipo=documento_tipo, documento_id=documento_id,
        usuario=usuario, motivo=motivo, saldo_anterior=anterior,
        saldo_posterior=origen.cantidad_fisica,
    )
    actualizar_alertas_inventario()
    return movimiento


@transaction.atomic
def crear_ajuste(*, existencia, tipo, cantidad, motivo, solicitante):
    from .models import AjusteInventario

    ajuste = AjusteInventario(
        existencia=existencia, tipo=tipo, cantidad=_cantidad(cantidad),
        motivo=motivo, solicitante=solicitante,
    )
    ajuste.full_clean()
    ajuste.save()
    return ajuste


@transaction.atomic
def decidir_y_aplicar_ajuste(*, ajuste, aprobador, aprobar):
    from django.utils import timezone
    from .models import AjusteInventario

    ajuste = AjusteInventario.objects.select_for_update().select_related("existencia__lote", "existencia__ubicacion").get(pk=ajuste.pk)
    if ajuste.estado != AjusteInventario.Estado.PENDIENTE:
        raise ValidationError("El ajuste ya fue decidido.")
    if ajuste.solicitante_id == aprobador.id:
        raise ValidationError("El solicitante no puede aprobar su propio ajuste.")
    ajuste.aprobador = aprobador
    if not aprobar:
        ajuste.estado = AjusteInventario.Estado.RECHAZADO
        ajuste.save(update_fields=["aprobador", "estado"])
        return ajuste
    existencia = Existencia.objects.select_for_update().get(pk=ajuste.existencia_id)
    anterior = existencia.cantidad_fisica
    positivo = ajuste.tipo == AjusteInventario.Tipo.POSITIVO
    if not positivo and existencia.cantidad_fisica - existencia.cantidad_reservada < ajuste.cantidad:
        raise ValidationError("El ajuste dejaría stock físico negativo o afectaría una reserva.")
    existencia.cantidad_fisica = anterior + ajuste.cantidad if positivo else anterior - ajuste.cantidad
    existencia.save(update_fields=["cantidad_fisica"])
    tipo_mov = (
        MovimientoInventario.Tipo.AJUSTE_POSITIVO if positivo
        else MovimientoInventario.Tipo.MERMA if ajuste.tipo == AjusteInventario.Tipo.MERMA
        else MovimientoInventario.Tipo.AJUSTE_NEGATIVO
    )
    MovimientoInventario.objects.create(
        tipo=tipo_mov, lote=existencia.lote, cantidad=ajuste.cantidad,
        origen=existencia.ubicacion, destino=existencia.ubicacion,
        documento_tipo="inventario.AjusteInventario", documento_id=ajuste.pk,
        usuario=aprobador, motivo=ajuste.motivo,
        saldo_anterior=anterior, saldo_posterior=existencia.cantidad_fisica,
    )
    ajuste.estado = AjusteInventario.Estado.APLICADO
    ajuste.aplicado_en = timezone.now()
    ajuste.save(update_fields=["aprobador", "estado", "aplicado_en"])
    actualizar_alertas_inventario()
    return ajuste


@transaction.atomic
def registrar_devolucion(*, detalle_entrega, cantidad, estado_material, motivo, usuario, ubicacion_destino):
    from .models import DevolucionProduccion

    devolucion = DevolucionProduccion(
        detalle_entrega=detalle_entrega, cantidad=_cantidad(cantidad),
        estado_material=estado_material, motivo=motivo, registrada_por=usuario,
    )
    devolucion.full_clean()
    ya_devuelto = DevolucionProduccion.objects.filter(detalle_entrega=detalle_entrega).aggregate(
        total=Sum("cantidad")
    )["total"] or Decimal("0")
    if ya_devuelto + devolucion.cantidad > detalle_entrega.cantidad:
        raise ValidationError("La suma de devoluciones supera la cantidad originalmente entregada.")
    if estado_material != DevolucionProduccion.EstadoMaterial.MERMA:
        tipo_esperado = (
            Ubicacion.Tipo.DISPONIBLE
            if estado_material == DevolucionProduccion.EstadoMaterial.UTILIZABLE
            else Ubicacion.Tipo.RECHAZADO
        )
        if ubicacion_destino is None or ubicacion_destino.tipo != tipo_esperado:
            raise ValidationError("La ubicación destino no corresponde al estado del material devuelto.")
    devolucion.save()
    movimiento_entrega = MovimientoInventario.objects.filter(
        tipo=MovimientoInventario.Tipo.ENTREGA,
        documento_tipo="inventario.EntregaProduccion",
        documento_id=detalle_entrega.entrega_id,
        lote=detalle_entrega.lote,
    ).order_by("-id").first()
    if not movimiento_entrega or not movimiento_entrega.destino_id:
        raise ValidationError("No se encontró la ubicación de la entrega original.")
    origen = Existencia.objects.select_for_update().get(
        lote=detalle_entrega.lote, ubicacion_id=movimiento_entrega.destino_id,
    )
    if origen.cantidad_fisica < devolucion.cantidad:
        raise ValidationError("La devolución supera el material existente en Producción.")
    if estado_material == DevolucionProduccion.EstadoMaterial.MERMA:
        anterior = origen.cantidad_fisica
        origen.cantidad_fisica -= devolucion.cantidad
        origen.save(update_fields=["cantidad_fisica"])
        MovimientoInventario.objects.create(
            tipo=MovimientoInventario.Tipo.MERMA, lote=origen.lote,
            cantidad=devolucion.cantidad, origen=origen.ubicacion,
            documento_tipo="inventario.DevolucionProduccion", documento_id=devolucion.pk,
            usuario=usuario, motivo=motivo, saldo_anterior=anterior,
            saldo_posterior=origen.cantidad_fisica,
        )
    else:
        trasladar_existencia(
            existencia_id=origen.pk, destino=ubicacion_destino,
            cantidad=devolucion.cantidad, usuario=usuario,
            documento_tipo="inventario.DevolucionProduccion", documento_id=devolucion.pk,
            motivo=motivo,
        )
    return devolucion


@transaction.atomic
def encolar_mrp_semana(*, semana, usuario):
    """
    Crea la ejecución y manda el cálculo a la cola. Devuelve la ejecución.

    **Lo que puede fallar rápido, falla aquí**: que la semana no esté publicada
    se comprueba antes de encolar, para que quien pulsa el botón lo sepa en el
    acto en vez de tener que consultar el estado para enterarse de un rechazo
    que no dependía del cálculo.

    Sin broker configurado, Celery corre la tarea en el momento. El contrato es
    el mismo en los dos casos —siempre se devuelve la ejecución y la pantalla
    consulta su estado— así que no hay dos caminos que mantener.
    """
    from datetime import timedelta

    from planificacion.models import SemanaPlan

    from .models import EjecucionMRP
    from .tareas import calcular_mrp_semana

    if semana.estado != SemanaPlan.Estado.PUBLICADA:
        raise ValidationError("El MRP solo puede ejecutarse sobre una semana publicada.")

    ejecucion = EjecucionMRP.objects.create(
        sucursal=semana.sucursal,
        fecha_corte=semana.fecha_inicio,
        horizonte_hasta=semana.fecha_inicio + timedelta(days=6),
        ejecutada_por=usuario,
        parametros={"semana": semana.pk, "codigo": semana.codigo},
        estado=EjecucionMRP.Estado.PENDIENTE,
    )

    # `on_commit` y no `delay()` a secas: sin esto, con un worker real la tarea
    # puede empezar antes de que la transacción de esta petición se confirme y
    # no encontrar la ejecución que acaba de crearse. Es una carrera que solo
    # aparece bajo carga, que es cuando peor viene.
    transaction.on_commit(lambda: calcular_mrp_semana.delay(ejecucion.pk))

    return ejecucion


def ejecutar_mrp_semana(*, semana, usuario, ejecucion=None):
    """
    Explota el programa publicado sin modificar Planificación ni sus bloques.

    `ejecucion` permite rellenar una fila ya creada —la que encoló la
    petición—. Sin ella crea la suya, que es el camino síncrono de siempre y el
    que usan las pruebas del cálculo.
    """
    from datetime import timedelta
    from math import ceil

    from planificacion.models import BloquePlan, SemanaPlan
    from .models import (
        DetalleOrdenCompra, EjecucionMRP, InsumoProveedor,
        OrdenCompra, ResultadoMRP,
    )

    semana = SemanaPlan.objects.prefetch_related("bloques__codigo__producto", "bloques__equipo").get(pk=semana.pk)
    if semana.estado != SemanaPlan.Estado.PUBLICADA:
        raise ValidationError("El MRP solo puede ejecutarse sobre una semana publicada.")
    # Solo el equipo del final de la cadena. Un mismo código se programa en el
    # evaporador y en la torre que lo recibe; contar los dos pediría los sacos
    # dos veces. Cuál cuenta lo dice el maestro (`consume_materiales`) y no una
    # comparación contra `tipo` aquí: cuando las líneas 1 y 2 se reconocieron
    # como las torres Egron y cambiaron de tipo, el filtro anterior las dejó
    # fuera y el MRP siguió devolviendo cifras, solo que cortas.
    bloques = [
        b for b in semana.bloques.all()
        if b.tipo == BloquePlan.Tipo.PRODUCCION
        and b.cantidad_kg and b.codigo_id and b.codigo.producto_id
        and b.equipo.consume_materiales
    ]
    # Los catálogos se cargan una vez para toda la semana: `explosionar` es
    # dominio puro y no consulta, así que releerlos por bloque serían tantas
    # consultas como turnos programados.
    catalogos = catalogos_de_receta()

    bruta: dict[int, Decimal] = {}
    fechas: dict[int, object] = {}
    for bloque in bloques:
        fecha = semana.fecha_del_dia(bloque.dia)
        # Se explota **a la fecha del bloque**: si una receta cambia a mitad de
        # semana, el martes se planifica con la de antes y el jueves con la
        # nueva. Una sola cifra para toda la semana escondería el cambio.
        _explosion, requerido = insumos_requeridos(
            producto_id=bloque.codigo.producto_id,
            cantidad=bloque.cantidad_kg,
            fecha=fecha,
            catalogos=catalogos,
        )

        for insumo_id, cantidad in requerido.items():
            bruta[insumo_id] = bruta.get(insumo_id, Decimal("0")) + cantidad
            fechas[insumo_id] = min(fechas.get(insumo_id, fecha), fecha)

    if ejecucion is None:
        ejecucion = EjecucionMRP.objects.create(
            sucursal=semana.sucursal,
            fecha_corte=semana.fecha_inicio,
            horizonte_hasta=semana.fecha_inicio + timedelta(days=6),
            ejecutada_por=usuario,
            parametros={"semana": semana.pk, "codigo": semana.codigo},
        )

    for insumo_id, necesidad_bruta in bruta.items():
        existencias = Existencia.objects.select_related("lote").filter(
            lote__insumo_id=insumo_id, lote__sucursal=semana.sucursal
        )
        disponible = sum((e.cantidad_disponible for e in existencias), Decimal("0"))
        programadas = sum(
            (
                d.cantidad - d.cantidad_recibida
                for d in DetalleOrdenCompra.objects.filter(
                    insumo_id=insumo_id,
                    orden__bodega_entrega__sucursal=semana.sucursal,
                    orden__estado__in=[OrdenCompra.Estado.APROBADA, OrdenCompra.Estado.ENVIADA, OrdenCompra.Estado.PARCIAL],
                )
            ),
            Decimal("0"),
        )
        from .models import Insumo
        insumo = Insumo.objects.get(pk=insumo_id)
        neta = max(Decimal("0"), necesidad_bruta + insumo.stock_seguridad - disponible - programadas)
        proveedor = InsumoProveedor.objects.filter(insumo_id=insumo_id, principal=True).order_by("id").first()
        sugerida = neta
        lead_time = insumo.plazo_reposicion_dias
        explicacion = {"formula": "bruta + seguridad - disponible - recepciones"}
        if proveedor:
            sugerida = max(sugerida, proveedor.compra_minima) if sugerida > 0 else Decimal("0")
            multiplo = proveedor.multiplo_compra or Decimal("1")
            sugerida = Decimal(ceil(sugerida / multiplo)) * multiplo if sugerida > 0 else Decimal("0")
            lead_time = proveedor.lead_time_dias
            explicacion.update({"proveedor": proveedor.proveedor.nombre, "minimo": str(proveedor.compra_minima), "multiplo": str(multiplo)})
        requerida = fechas[insumo_id]
        ResultadoMRP.objects.create(
            ejecucion=ejecucion, insumo=insumo, fecha_requerida=requerida,
            necesidad_bruta=necesidad_bruta, disponible_proyectado=disponible,
            recepciones_programadas=programadas, necesidad_neta=neta,
            compra_sugerida=sugerida,
            fecha_sugerida_orden=requerida - timedelta(days=lead_time),
            explicacion=explicacion,
        )
    return ejecucion


@transaction.atomic
def crear_solicitud_desde_mrp(*, ejecucion, usuario, area=None):
    """
    Convierte lo que el MRP dice que falta en una solicitud de compra.

    Es el eslabón que faltaba. El MRP calculaba qué comprar y ahí terminaba:
    alguien tenía que leer la pantalla y volver a teclear las cantidades en un
    formulario, que es donde se pierde el «para cuándo» y donde aparecen las
    diferencias entre lo que el sistema calculó y lo que se pidió.

    Solo entran las líneas con compra sugerida: una necesidad neta cubierta
    por el stock o por órdenes ya emitidas no se pide de nuevo.

    `origen_mrp` queda marcado en cada línea. Sirve para lo que se pregunta
    después de un quiebre: si esto salió del cálculo o alguien lo agregó a
    mano.

    El número lleva el id de la ejecución y `numero` es único, así que
    ejecutar esto dos veces sobre el mismo cálculo falla en vez de duplicar la
    compra. No es un efecto secundario afortunado: es la garantía.
    """
    from usuarios.models import PerfilUsuario

    from .models import DetalleSolicitudCompra, SolicitudCompra

    lineas = [r for r in ejecucion.resultados.all() if r.compra_sugerida > 0]

    if not lineas:
        raise ValidationError(
            "Esta ejecución no sugiere comprar nada: el stock y las órdenes "
            "ya emitidas cubren la necesidad."
        )

    perfil = getattr(usuario, "perfil", None)

    solicitud = SolicitudCompra.objects.create(
        sucursal=ejecucion.sucursal,
        numero=f"SC-MRP-{ejecucion.pk}",
        area=area or (perfil.area if perfil else PerfilUsuario.Area.BODEGA),
        solicitante=usuario,
        motivo=(
            f"Generada desde el MRP del {ejecucion.fecha_corte} "
            f"(horizonte hasta {ejecucion.horizonte_hasta})."
        ),
        estado=SolicitudCompra.Estado.BORRADOR,
    )

    DetalleSolicitudCompra.objects.bulk_create([
        DetalleSolicitudCompra(
            solicitud=solicitud,
            insumo_id=linea.insumo_id,
            cantidad=linea.compra_sugerida,
            # La fecha en que se necesita el material, no la de emitir la
            # orden: quien recibe la solicitud decide cuándo la tramita, pero
            # el plazo de la planta no se mueve.
            fecha_requerida=linea.fecha_requerida,
            origen_mrp=True,
        )
        for linea in lineas
    ])

    return solicitud


@transaction.atomic
def convertir_solicitud_en_ordenes(*, solicitud, usuario, bodega):
    """
    Emite las órdenes de compra de una solicitud aprobada.

    **Una orden por proveedor.** Una solicitud puede pedir sacos a uno y
    reactivos a otro; una sola orden obligaría a elegir un proveedor y
    mandarle renglones que no vende. El proveedor de cada material es el que
    esté marcado como principal.

    Un material sin proveedor principal **detiene la conversión entera** y se
    informa cuáles son. La alternativa —emitir las órdenes que sí se pueden y
    dejar el resto callado— parte la solicitud sin que nadie lo note, y lo que
    quedó fuera no se vuelve a mirar porque la solicitud figura convertida.

    El estado `convertida` existía en el modelo desde el principio y no era
    alcanzable: nada convertía nada.
    """
    from .models import (
        DetalleOrdenCompra, InsumoProveedor, OrdenCompra, SolicitudCompra,
    )

    if solicitud.estado != SolicitudCompra.Estado.APROBADA:
        raise ValidationError(
            "Solo se convierte una solicitud aprobada. Esta está "
            f"«{solicitud.get_estado_display()}»."
        )

    detalles = list(solicitud.detalles.select_related("insumo"))

    if not detalles:
        raise ValidationError("La solicitud no tiene líneas que convertir.")

    principales = {
        ip.insumo_id: ip
        for ip in InsumoProveedor.objects.filter(
            insumo_id__in=[d.insumo_id for d in detalles], principal=True
        ).select_related("proveedor")
    }

    huerfanos = [d.insumo.nombre for d in detalles if d.insumo_id not in principales]

    if huerfanos:
        raise ValidationError(
            "Sin proveedor principal, no se puede emitir la orden de: "
            f"{', '.join(sorted(huerfanos))}. Asígnalo en el catálogo de "
            "materiales."
        )

    por_proveedor: dict[int, list] = {}

    for detalle in detalles:
        por_proveedor.setdefault(principales[detalle.insumo_id].proveedor_id, []).append(
            detalle
        )

    ordenes = []

    # Orden estable: dos ejecuciones sobre la misma solicitud tienen que
    # numerar igual, y un diccionario no lo garantiza.
    for correlativo, proveedor_id in enumerate(sorted(por_proveedor), start=1):
        lineas = por_proveedor[proveedor_id]

        orden = OrdenCompra.objects.create(
            numero=f"OC-{solicitud.numero}-{correlativo:02d}",
            solicitud=solicitud,
            proveedor_id=proveedor_id,
            bodega_entrega=bodega,
            estado=OrdenCompra.Estado.BORRADOR,
            # El compromiso más apretado de la orden: si una línea se necesita
            # antes, la orden entera tiene esa fecha. Prometer la más holgada
            # dejaría a la planta sin material creyendo que va en plazo.
            fecha_comprometida=min(d.fecha_requerida for d in lineas),
        )

        DetalleOrdenCompra.objects.bulk_create([
            DetalleOrdenCompra(
                orden=orden,
                insumo_id=d.insumo_id,
                cantidad=d.cantidad,
                costo_unitario=principales[d.insumo_id].costo_unitario,
            )
            for d in lineas
        ])

        ordenes.append(orden)

    solicitud.estado = SolicitudCompra.Estado.CONVERTIDA
    solicitud.save(update_fields=["estado"])

    return ordenes


@transaction.atomic
def cerrar_no_conformidad(*, no_conformidad, usuario, accion_tomada):
    """
    Cierra una no conformidad de material dejando qué se hizo con él.

    `cerrada` era un booleano suelto: decía que el asunto se acabó y no qué se
    hizo, quién lo hizo ni cuándo. Para el material que Calidad rechazó, esa
    es justamente la información que un auditor pide.

    Si el destino es **liberación excepcional**, exige la concesión enlazada y
    vigente. Cerrar diciendo «se liberó por concesión» sin poder mostrar cuál
    —con su cantidad, su uso autorizado y su vencimiento— deja el material
    usado sin respaldo, que es peor que no haberlo documentado: parece que sí
    lo tiene.
    """
    from .models import NoConformidadMaterial

    if no_conformidad.cerrada:
        raise ValidationError("Esta no conformidad ya está cerrada.")

    if not str(accion_tomada or "").strip():
        raise ValidationError(
            "Registra qué se hizo con el material antes de cerrar."
        )

    if no_conformidad.destino == NoConformidadMaterial.Destino.EXCEPCIONAL:
        liberacion = no_conformidad.liberacion

        if liberacion is None:
            raise ValidationError(
                "El destino es liberación excepcional: enlaza la concesión que "
                "la autoriza antes de cerrar."
            )

        if not liberacion.vigente:
            raise ValidationError(
                "La concesión enlazada está vencida o inactiva: no ampara el "
                "uso del material."
            )

    no_conformidad.accion_tomada = accion_tomada.strip()
    no_conformidad.cerrada_por = usuario
    no_conformidad.cerrada_en = timezone.now()
    no_conformidad.cerrada = True
    no_conformidad.save(
        update_fields=["accion_tomada", "cerrada_por", "cerrada_en", "cerrada"]
    )

    return no_conformidad


def motivo_equipo_no_habilitado(equipo):
    """
    Por qué este equipo no puede producir, o `None` si puede.

    Solo bloquea el conflicto físico: un CIP ejecutándose en ese momento.
    La ausencia de aseo conforme o un resultado observado se informa mediante
    ``advertencia_aseo_equipo`` y queda trazada, pero no detiene Producción.

    Devuelve el motivo y no un booleano, por lo mismo que `puede_liberar`: un
    «no» sin causa obliga a adivinar qué corregir.
    """
    from .models import CicloCIP

    if equipo is None:
        return None

    if CicloCIP.objects.filter(
        equipo=equipo, estado=CicloCIP.Estado.EN_CURSO
    ).exists():
        return f"{equipo.nombre} está en CIP: no puede producir mientras se asea."

    return None


def advertencia_aseo_equipo(equipo):
    """Describe el último aseo como aviso; no detiene la producción."""
    from .models import CicloCIP

    if equipo is None:
        return ""
    ultimo = (
        CicloCIP.objects.filter(equipo=equipo)
        .exclude(estado=CicloCIP.Estado.PROGRAMADO)
        .order_by("-inicio", "-id")
        .first()
    )
    if ultimo is None:
        return f"{equipo.nombre} no tiene un aseo/CIP registrado. Verifica antes de operar."
    if ultimo.estado == CicloCIP.Estado.OBSERVADO or ultimo.verificacion == CicloCIP.Verificacion.OBSERVADO:
        return f"El último aseo de {equipo.nombre} quedó observado. Producción puede continuar con advertencia."
    if ultimo.verificacion != CicloCIP.Verificacion.CONFORME:
        return f"El aseo de {equipo.nombre} aún no tiene verificación conforme de Calidad."
    return ""


def equipo_produciendo(equipo):
    """
    ¿Hay una ejecución de proceso corriendo en este equipo?

    Es la regla № 15 por el otro lado: tampoco se empieza un CIP sobre un
    equipo que está produciendo. Con solo una de las dos direcciones, la regla
    se cumple o no según cuál de las dos acciones llegue primero.
    """
    from procesos.models import EjecucionProceso
    from procesos.servicios import ESTADOS_QUE_OCUPAN_EQUIPO

    if equipo is None:
        return None

    corriendo = EjecucionProceso.objects.filter(
        equipo=equipo, estado__in=ESTADOS_QUE_OCUPAN_EQUIPO
    ).first()

    if corriendo is None:
        return None

    return (
        f"{equipo.nombre} está produciendo ({corriendo.codigo}): no se puede "
        "asear mientras corre."
    )
