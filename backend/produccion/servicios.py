"""
El paso del vale al lote.

**Quien consume la leche de los silos es el vale**: al transferirse saca de la
entera y del TK de descremada, y deja la mezcla en el silo de destino. Ahí esa
leche ya está estandarizada al RC que un producto pide, pero todavía no es de
ningún producto.

Lo que hace abrir el lote es **formalizar a qué producto va**. Por eso el lote
nace del vale y no al revés, y por eso no elige silo: el silo lo eligió el vale.

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
from .models import Lote


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
def abrir_lote_desde_vale(*, vale, producto, codigo_lote, fecha, litros, **extra):
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

    lote = Lote.objects.create(
        sucursal=vale.silo_destino.sucursal,
        codigo_lote=codigo_lote,
        producto=producto,
        vale=vale,
        fecha=fecha,
        estado=Lote.Estado.EN_PROCESO,
        **extra,
    )

    MovimientoSilo.objects.create(
        silo=vale.silo_destino,
        tipo=MovimientoSilo.Tipo.SALIDA,
        litros=Decimal(str(litros)),
        fecha_hora=timezone.now(),
        origen_tipo=MovimientoSilo.OrigenTipo.LOTE,
        origen_id=lote.id,
        motivo=(
            f"Leche estandarizada del vale {vale.codigo} al lote "
            f"{lote.codigo_lote}"
        ),
    )

    _encadenar_con_la_estandarizacion(vale, lote, litros)

    return lote


def _encadenar_con_la_estandarizacion(vale, lote, litros):
    """
    Abre la ejecución de secado que toma la leche del vale y produce el lote.

    Es lo que cierra la cadena: la estandarización entregó al silo, y esta
    corrida saca de ese silo y devuelve un lote. Con las dos, `genealogia_lote`
    puede recorrer de un saco hacia atrás hasta los silos de origen.

    Si el maestro de procesos no declara una etapa de secado, no se registra
    nada y la producción sigue: abrir un lote es una operación de planta y no
    puede quedarse detenida porque falte un maestro.
    """
    from procesos.models import EjecucionProceso, EntradaProceso, EtapaProceso, SalidaProceso

    etapa = (
        EtapaProceso.objects.filter(tipo=EtapaProceso.Tipo.SECADO, activa=True)
        .order_by("proceso__version", "orden")
        .last()
    )

    if etapa is None:
        return None

    ejecucion = EjecucionProceso.objects.create(
        codigo=f"EJ-{lote.codigo_lote}",
        etapa=etapa,
        sucursal=lote.sucursal,
        estado=EjecucionProceso.Estado.EJECUCION,
        inicio=timezone.now(),
    )

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
    Cierra la ejecución de secado con los kilos que salieron.

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

    ejecucion = EjecucionProceso.objects.filter(codigo=f"EJ-{lote.codigo_lote}").first()

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
