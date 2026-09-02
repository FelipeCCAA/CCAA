"""
El paso del vale al lote.

**Quien prepara la leche en los silos es el vale**: al transferirse saca de la
entera y del TK de descremada, deja la mezcla en el silo de destino y conserva
el producto para cuyo RC fue preparada.

Abrir el lote consume una cantidad parcial de esa entrada y hereda su producto.
Producción no vuelve a elegir ni producto ni silo: ambos los fijó el vale.

Antes esto no existía y el lote se creaba suelto, escogiendo un silo cualquiera
y descontándole litros. Dos consecuencias: la leche estandarizada y la cruda se
descontaban igual —como si secar leche cruda fuera posible— y no había forma de
responder de qué mezcla salió un saco.
"""

from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Sum
from django.utils import timezone

from . import dominio
from .models import Lote, PalletProducto, RegistroEnvase


def litros_ya_tomados(vale, excluyendo=None):
    """Cuántos litros de este vale se llevaron ya otros lotes."""
    from recepcion.models import MovimientoSilo

    lotes = vale.lotes.all()

    if excluyendo is not None:
        lotes = lotes.exclude(pk=excluyendo)

    total = MovimientoSilo.objects.filter(
        tipo=MovimientoSilo.Tipo.SALIDA,
        origen_tipo=MovimientoSilo.OrigenTipo.LOTE,
        origen_id__in=lotes.values_list("pk", flat=True),
        silo=vale.silo_destino,
    ).aggregate(total=Sum("litros"))["total"]

    return Decimal(str(total or 0))


@transaction.atomic
def abrir_lote_desde_vale(
    *, vale, codigo_lote, fecha, litros, usuario=None, producto=None,
    lote_borrador=None, **extra
):
    """
    Abre un lote con la leche que el vale dejó en su silo de destino.

    Todo o nada: si la regla no se cumple no se crea el lote **ni** se descuenta
    el silo. Salir con un `return` a mitad dejaría el silo descontado y el lote
    sin existir, que es peor que no haber empezado.

    El movimiento de silo se registra igual —la leche sale físicamente del silo
    de destino para secarse— pero ya no es una elección del lote: el silo y el
    tope los pone el vale.
    """
    from estandarizacion.models import ValeEstandarizacion
    from recepcion.models import MovimientoSilo

    # Se relee bloqueando: entre la comprobación y la escritura, otro lote del
    # mismo vale podría llevarse los litros que este acaba de dar por
    # disponibles, y los dos pasarían la regla por separado.
    vale = ValeEstandarizacion.objects.select_for_update().get(pk=vale.pk)

    decision = dominio.puede_abrir_lote_desde(
        vale, litros, consumido_por_otros_lotes=litros_ya_tomados(vale)
    )

    if not decision.permitido:
        raise ValidationError(list(decision.bloqueos))

    if producto is not None and producto.pk != vale.producto_id:
        raise ValidationError({
            "producto": (
                f"El vale {vale.codigo} fue estandarizado para "
                f"{vale.producto.nombre}; no puede usarse para otro producto."
            )
        })
    producto = vale.producto

    # Se bloquea la máquina, no solo la corrida encontrada. Así dos aperturas
    # simultáneas para una máquina todavía libre se serializan correctamente.
    # La regla también vive aquí porque ocultar una opción en React no impide
    # que un cliente antiguo o una llamada manual intente ocuparla.
    equipo = extra.get("equipo")
    if equipo is not None:
        from inventario.servicios import advertencia_aseo_equipo, motivo_equipo_no_habilitado
        from maestros.models import Equipo
        from procesos.servicios import adquirir_equipo

        equipo = adquirir_equipo(
            equipo_id=equipo.pk,
            ejecucion_id=getattr(lote_borrador, "ejecucion_id", None),
        )
        if not equipo.activo:
            raise ValidationError({"equipo": f"{equipo.nombre} está inactivo."})
        impedimento = motivo_equipo_no_habilitado(equipo)
        if impedimento:
            raise ValidationError({"equipo": impedimento})
        advertencia_aseo = advertencia_aseo_equipo(equipo)
        if advertencia_aseo:
            observacion = str(extra.get("observacion", "")).strip()
            marca = f"[ADVERTENCIA ASEO AL INICIO] {advertencia_aseo}"
            extra["observacion"] = "\n".join(parte for parte in (observacion, marca) if parte)
        extra["equipo"] = equipo

    if lote_borrador is None:
        lote = Lote.objects.create(
            sucursal=vale.silo_destino.sucursal,
            codigo_lote=codigo_lote,
            codigo_lote_propuesto=codigo_lote,
            producto=producto,
            vale=vale,
            fecha=fecha,
            estado=Lote.Estado.EN_PROCESO,
            **extra,
        )
    else:
        lote = Lote.objects.select_for_update().get(pk=lote_borrador.pk)
        if lote.estado != Lote.Estado.BORRADOR:
            raise ValidationError("El lote ya no está en borrador.")
        lote.sucursal = vale.silo_destino.sucursal
        lote.codigo_lote = codigo_lote
        lote.codigo_lote_propuesto = codigo_lote
        lote.producto = producto
        lote.vale = vale
        lote.fecha = fecha
        lote.estado = Lote.Estado.EN_PROCESO
        lote.litros_estandarizados_borrador = None
        for campo, valor in extra.items():
            setattr(lote, campo, valor)
        lote.save()

    salida = MovimientoSilo.objects.create(
        silo=vale.silo_destino,
        tipo=MovimientoSilo.Tipo.SALIDA,
        litros=Decimal(str(litros)),
        fecha_hora=timezone.now(),
        origen_tipo=MovimientoSilo.OrigenTipo.LOTE,
        origen_id=lote.id,
        lote=lote,
        producto=lote.producto,
        equipo=lote.equipo,
        usuario=usuario,
        motivo=(
            f"Leche estandarizada del vale {vale.codigo} al lote "
            f"{lote.codigo_lote}"
        ),
    )
    from recepcion.servicios import atribuir_salida
    atribuir_salida(salida)

    _encadenar_con_la_estandarizacion(vale, lote, litros, usuario=usuario)

    return lote


def _encadenar_con_la_estandarizacion(vale, lote, litros, usuario=None):
    """
    Abre la ejecución de la máquina elegida que toma la leche del vale.

    Es lo que cierra la cadena: la estandarización entregó al silo, y esta
    corrida saca de ese silo y devuelve un lote. Con las dos, `genealogia_lote`
    puede recorrer de un saco hacia atrás hasta los silos de origen.

    La ruta es obligatoria para operaciones nuevas. Una configuración
    incompleta se informa y la transacción revierte también lote y movimiento:
    nunca se permite producción física sin su ejecución trazable.
    """
    from maestros.models import Equipo
    from procesos.models import EjecucionProceso, EntradaProceso, EtapaProceso
    from procesos.servicios import exigir_etapa_inicial_para_producto

    tipo_etapa = {
        Equipo.Tipo.EVAPORADOR: EtapaProceso.Tipo.EVAPORACION,
        Equipo.Tipo.TORRE: EtapaProceso.Tipo.SECADO,
        Equipo.Tipo.ENVASADORA: EtapaProceso.Tipo.ENVASADO,
        Equipo.Tipo.LINEA: EtapaProceso.Tipo.ENVASADO,
    }.get(lote.equipo.tipo if lote.equipo else None, EtapaProceso.Tipo.SECADO)

    etapa = exigir_etapa_inicial_para_producto(
        producto=lote.producto,
        sucursal=lote.sucursal,
        tipo=tipo_etapa,
        etapa_previa_tipo=EtapaProceso.Tipo.ESTANDARIZACION,
    )

    ejecucion = EjecucionProceso.objects.create(
        # El código de lote no es globalmente único. La identidad de la base
        # evita colisiones entre productos, fechas y sucursales.
        codigo=f"EJ-PROD-{lote.pk}",
        etapa=etapa,
        sucursal=lote.sucursal,
        equipo=lote.equipo,
        responsable=usuario,
        estado=EjecucionProceso.Estado.EJECUCION,
        inicio=timezone.now(),
    )

    lote.ejecucion = ejecucion
    lote.save(update_fields=["ejecucion"])

    EntradaProceso.objects.create(
        ejecucion=ejecucion,
        silo=vale.silo_destino,
        tipo=EntradaProceso.Tipo.PRINCIPAL,
        cantidad=Decimal(str(litros)),
        unidad="L",
    )

    if tipo_etapa == EtapaProceso.Tipo.SECADO:
        from procesos.models import CorridaSecado

        CorridaSecado.objects.get_or_create(
            ejecucion=ejecucion,
            defaults={"orden": lote.orden, "lote": lote},
        )

    # **Sin salida todavía.** Los kilos no se saben al abrir el lote: se
    # declaran al terminar la corrida, que es la misma razón por la que
    # `kg_producidos` es nulable. Escribir aquí una cantidad de relleno dejaría
    # un balance de masa construido sobre un número inventado.
    return ejecucion


@transaction.atomic
def registrar_produccion(*, lote, destino_salida=None):
    """
    Cierra la ejecución productiva con los kilos que salieron.

    Se llama cuando el lote se declara producido: es el momento en que los
    kilos existen. Antes, la ejecución está abierta y sin salida — que es lo
    que está pasando en la torre.

    Es lo que completa la cadena: hasta que hay salida, `genealogia_lote` no
    puede llegar a este lote desde la leche que lo originó.
    """
    from procesos.models import EjecucionProceso, SalidaProceso

    if lote.kg_producidos is None or Decimal(str(lote.kg_producidos)) <= 0:
        raise ValidationError(
            "Sin kilos declarados no hay salida que registrar: el lote todavía "
            "no terminó."
        )

    ejecucion = lote.ejecucion

    if ejecucion is None:
        raise ValidationError({
            "ruta_producto": (
                "El lote no tiene una ejecución productiva trazable. "
                "Revisa la ruta configurada antes de declararlo producido."
            )
        })

    corrida_secado = getattr(ejecucion, "corrida_secado", None)
    if corrida_secado is not None and corrida_secado.kg_polvo is None:
        corrida_secado.kg_polvo = Decimal(str(lote.kg_producidos))
        corrida_secado.save(update_fields=["kg_polvo"])

    # La salida va en kilos y la entrada en litros: el balance de masa no las
    # compara, y hace bien — secar no es trasvasar, y sin un factor de
    # conversión declarado cualquier comparación sería inventada.
    if destino_salida is None:
        destino_salida = SalidaProceso.Destino.ENVASADO
    SalidaProceso.objects.get_or_create(
        ejecucion=ejecucion,
        lote=lote,
        defaults={
            "naturaleza": SalidaProceso.Naturaleza.PRINCIPAL,
            "clasificacion": SalidaProceso.Clasificacion.GRANEL,
            "destino": destino_salida,
            "cantidad": Decimal(str(lote.kg_producidos)),
            "unidad": "kg",
        },
    )

    if ejecucion.estado != EjecucionProceso.Estado.CERRADA:
        ejecucion.estado = EjecucionProceso.Estado.CERRADA
        ejecucion.termino = timezone.now()
        ejecucion.save(update_fields=["estado", "termino"])

    return ejecucion


def cerrar_lote_producido(*, lote, usuario, titulo=None, mensaje=None) -> str | None:
    """
    Lo que pasa **después** de declarar un lote producido, en un solo sitio.

    `registrar_produccion` cierra la ejecución con sus kilos; esto es la cola:
    la orden pasa a pendiente de Calidad, se descuenta el material de bodega y
    se avisa al área. Devuelve el motivo si el descuento no se pudo hacer, o
    `None`.

    Por qué está aquí y no repetido en cada camino
    ----------------------------------------------
    Había **tres** formas de declarar un lote producido —el `PATCH` del lote,
    `cerrar_mantequilla` y `cerrar_secado`— y cada una traía su propio
    subconjunto de esta cola. Secado se quedó sin las dos últimas partes: un
    lote cerrado desde su pantalla no descontaba su material ni llegaba a la
    bandeja de Calidad, y como el saldo de bodega quedaba alto sin que nada
    fallara, nadie se enteraba. Tres escritores del mismo hecho con reglas
    distintas es como se produce eso.

    **El descuento no bloquea.** Mismo criterio que la leche asignada: detener
    la producción del día porque bodega no cargó la receta o el material sigue
    en cuarentena traslada a la línea un problema que no es suyo. Lo que sí
    ocurre es que el consumo queda pendiente y a la vista —`consumo_inventario`
    en la ficha— para reintentarlo.

    Atrapar la excepción es seguro **solo porque `consumir_receta_produccion`
    es `@transaction.atomic`**: el servicio alcanza a crear la cabecera y a
    sacar lo que sí había antes de detectar que falta, y sin esa reversión el
    lote quedaría con un consumo «registrado» que descontó una fracción. Nadie
    volvería a mirarlo: ya figura hecho. `test_sin_stock_el_lote_igual_se_
    declara_y_avisa` lo fija; si alguien quita ese decorador, falla ahí.

    `titulo` y `mensaje` permiten que cada línea nombre su producto en el
    aviso. Lo que no se puede elegir es si el aviso se manda.
    """
    from inventario.servicios import _notificar_area, consumir_receta_produccion

    from .models import OrdenProduccion

    if lote.orden_id and lote.orden.estado == OrdenProduccion.Estado.EN_PROCESO:
        lote.orden.estado = OrdenProduccion.Estado.PENDIENTE_CALIDAD
        lote.orden.save(update_fields=["estado"])

    aviso = None
    try:
        consumir_receta_produccion(lote_produccion=lote, usuario=usuario)
    except ValidationError as error:
        aviso = (
            "No se descontó el material de bodega: "
            f"{' '.join(error.messages)} El consumo queda pendiente."
        )

    _notificar_area(
        "calidad",
        tipo="producto_pendiente_calidad",
        titulo=titulo or "Producto terminado pendiente de Calidad",
        mensaje=mensaje or (
            f"Lote {lote.codigo_lote} ({lote.producto.nombre}) terminado. "
            "Revisa análisis y checklist para liberarlo."
        ),
        documento_tipo="lote_produccion",
        documento_id=lote.id,
    )

    return aviso


@transaction.atomic
def registrar_envasado(
    *, lote_id, equipo, formato_kg, inicio, termino, pallets, usuario,
    controles=None, observacion="", operacion_id=None,
):
    """Registra envase y pallets como un único cierre físico e idempotente."""
    from django.core.exceptions import ValidationError
    from inventario.servicios import (
        motivo_equipo_no_habilitado, registrar_pallets_producidos,
    )

    if operacion_id:
        existente = RegistroEnvase.objects.filter(operacion_id=operacion_id).first()
        if existente:
            return existente
    lote = (
        Lote.objects.select_for_update(of=("self",))
        .select_related("sucursal", "producto")
        .prefetch_related(
            "salidas_proceso__ejecucion__etapa",
            "salidas_proceso__liberacion_calidad",
        )
        .get(pk=lote_id)
    )
    if lote.estado not in {Lote.Estado.PRODUCIDO, Lote.Estado.CERRADO}:
        raise ValidationError("El lote debe estar producido antes de envasarse.")
    from procesos.models import SalidaProceso
    salidas_productivas = SalidaProceso.objects.filter(
        lote=lote, naturaleza=SalidaProceso.Naturaleza.PRINCIPAL,
    )
    bloqueo_calidad = bloqueo_calidad_para_envasado(lote)
    if bloqueo_calidad:
        raise ValidationError(bloqueo_calidad)
    if salidas_productivas.exists() and not salidas_productivas.filter(
        destino=SalidaProceso.Destino.ENVASADO,
    ).exists():
        raise ValidationError(
            "El flujo del lote no tiene Envasado como destino; revisa su etapa productiva."
        )
    impedimento = motivo_equipo_no_habilitado(equipo)
    if impedimento:
        raise ValidationError(impedimento)
    if not isinstance(pallets, list) or not pallets:
        raise ValidationError({"pallets": "Registra al menos un pallet."})

    unidades = sum(int(item.get("unidades", 0)) for item in pallets)
    kg_total = sum(Decimal(str(item.get("kg_neto", 0))) for item in pallets)
    registro = RegistroEnvase(
        lote=lote, equipo=equipo, formato_kg=Decimal(str(formato_kg)),
        unidades=unidades, kg_envasados=kg_total, controles=controles or {},
        operador=usuario, inicio=inicio, termino=termino, observacion=observacion,
        **({"operacion_id": operacion_id} if operacion_id else {}),
    )
    registro.full_clean()
    registro.save()

    creados = []
    for item in pallets:
        pallet = PalletProducto(
            envase=registro, codigo=str(item.get("codigo", "")).strip(),
            unidades=int(item.get("unidades", 0)),
            kg_neto=Decimal(str(item.get("kg_neto", 0))),
        )
        if not pallet.codigo:
            raise ValidationError({"pallets": "Cada pallet requiere código."})
        pallet.full_clean()
        creados.append(pallet)
    PalletProducto.objects.bulk_create(creados)
    # El pallet ya existe físicamente al salir de envase. Inventario lo
    # registra una sola vez en cuarentena; Calidad luego cambia su estado, no
    # vuelve a crear stock.
    registrar_pallets_producidos(creados, usuario)
    return registro


def bloqueo_calidad_para_envasado(lote):
    """Devuelve la puerta material previa a Envase, sin mezclarla con el lote."""
    from calidad.models import LiberacionProceso
    from procesos.models import SalidaProceso

    for salida in lote.salidas_proceso.all():
        if salida.naturaleza != SalidaProceso.Naturaleza.PRINCIPAL:
            continue
        if not salida.ejecucion.etapa.requiere_calidad:
            continue
        decision = getattr(salida, "liberacion_calidad", None)
        if decision is None or decision.estado != LiberacionProceso.Estado.LIBERADO:
            return (
                f"{salida.ejecucion.etapa.get_tipo_display()} está pendiente "
                "de aprobación de Calidad antes de Envasado."
            )
    return ""
