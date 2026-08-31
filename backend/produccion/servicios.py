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
        from procesos.models import EjecucionProceso

        equipo = Equipo.objects.select_for_update().get(pk=equipo.pk)
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
        ocupada = EjecucionProceso.objects.filter(
            equipo=equipo,
            estado=EjecucionProceso.Estado.EJECUCION,
        ).first()
        ejecucion_del_borrador = getattr(lote_borrador, "ejecucion_id", None)
        if ocupada and ocupada.pk != ejecucion_del_borrador:
            raise ValidationError({
                "equipo": f"{equipo.nombre} está ocupado por {ocupada.codigo}."
            })
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

    Si el maestro no declara la etapa que corresponde a la máquina, no se registra
    nada y la producción sigue: abrir un lote es una operación de planta y no
    puede quedarse detenida porque falte un maestro.
    """
    from maestros.models import Equipo
    from procesos.models import EjecucionProceso, EntradaProceso, EtapaProceso

    tipo_etapa = {
        Equipo.Tipo.EVAPORADOR: EtapaProceso.Tipo.EVAPORACION,
        Equipo.Tipo.TORRE: EtapaProceso.Tipo.SECADO,
        Equipo.Tipo.ENVASADORA: EtapaProceso.Tipo.ENVASADO,
        Equipo.Tipo.LINEA: EtapaProceso.Tipo.ENVASADO,
    }.get(lote.equipo.tipo if lote.equipo else None, EtapaProceso.Tipo.SECADO)

    etapa = (
        EtapaProceso.objects.filter(tipo=tipo_etapa, activa=True)
        .order_by("proceso__version", "orden")
        .last()
    )

    if etapa is None:
        return None

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

    # **Sin salida todavía.** Los kilos no se saben al abrir el lote: se
    # declaran al terminar la corrida, que es la misma razón por la que
    # `kg_producidos` es nulable. Escribir aquí una cantidad de relleno dejaría
    # un balance de masa construido sobre un número inventado.
    return ejecucion


@transaction.atomic
def registrar_produccion(*, lote):
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
        return None

    # La salida va en kilos y la entrada en litros: el balance de masa no las
    # compara, y hace bien — secar no es trasvasar, y sin un factor de
    # conversión declarado cualquier comparación sería inventada.
    SalidaProceso.objects.get_or_create(
        ejecucion=ejecucion,
        lote=lote,
        defaults={
            "naturaleza": SalidaProceso.Naturaleza.PRINCIPAL,
            "cantidad": Decimal(str(lote.kg_producidos)),
            "unidad": "kg",
        },
    )

    if ejecucion.estado != EjecucionProceso.Estado.CERRADA:
        ejecucion.estado = EjecucionProceso.Estado.CERRADA
        ejecucion.termino = timezone.now()
        ejecucion.save(update_fields=["estado", "termino"])

    return ejecucion


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
    lote = Lote.objects.select_for_update().select_related("sucursal").get(pk=lote_id)
    if lote.estado not in {Lote.Estado.PRODUCIDO, Lote.Estado.CERRADO}:
        raise ValidationError("El lote debe estar producido antes de envasarse.")
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
