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

    return lote
