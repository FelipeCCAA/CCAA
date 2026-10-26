"""Prueba acotada de leche cruda nueva en un silo consumido hasta cero.

No concilia ni reescribe salidas históricas. El llamador de escritura mantiene
el silo bloqueado; el catálogo sólo usa esta lectura como información.
"""
from dataclasses import dataclass
from decimal import Decimal

from maestros.models import Silo
from procesos.models import EntradaProceso, SalidaProceso
from produccion.models import Lote
from recepcion.models import MovimientoSilo, Recepcion


@dataclass(frozen=True)
class RecepcionNueva:
    recepcion_id: int
    ingreso: MovimientoSilo
    vaciado: MovimientoSilo
    saldo: Decimal


def recepcion_posterior_a_vaciado(silo, salidas):
    """Devuelve prueba sólo de una recepción entera exclusiva tras consumo real.

    Otras formas de vaciado, mezclas, ajustes, salidas de proceso posteriores
    o historia insuficiente conservan el bloqueo; no se deduce una composición.
    """
    if silo.tipo != Silo.Tipo.SILO:
        return None
    movimientos = list(
        MovimientoSilo.objects.filter(silo_id=silo.pk)
        .order_by("fecha_hora", "pk").prefetch_related("atribuciones_recepcion")
    )
    saldo, ultimo_cero = Decimal("0"), None
    for indice, movimiento in enumerate(movimientos):
        if movimiento.tipo not in MovimientoSilo.Tipo.values:
            return None
        if movimiento.tipo != MovimientoSilo.Tipo.AJUSTE and movimiento.litros <= 0:
            return None
        saldo += -movimiento.litros if movimiento.tipo == MovimientoSilo.Tipo.SALIDA else movimiento.litros
        if saldo < 0:
            return None
        if saldo == 0:
            ultimo_cero = indice
    if ultimo_cero is None or saldo <= 0:
        return None
    vaciado = movimientos[ultimo_cero]
    if vaciado.tipo != MovimientoSilo.Tipo.SALIDA or vaciado.origen_tipo != MovimientoSilo.OrigenTipo.LOTE:
        return None
    # Abrir un lote deja una salida física y una entrada a su ejecución. El
    # legado puede carecer de salida_origen; aquí sólo se prueba el vaciado.
    lote = Lote.objects.filter(
        pk=vaciado.origen_id, sucursal_id=silo.sucursal_id,
        vale__silo_destino_id=silo.pk, ejecucion__isnull=False,
    ).first()
    if lote is None or vaciado.lote_id != lote.pk:
        return None
    entradas = list(EntradaProceso.objects.filter(
        ejecucion_id=lote.ejecucion_id, silo_id=silo.pk, unidad__iexact="l",
    ))
    if len(entradas) != 1 or entradas[0].cantidad != vaciado.litros:
        return None
    # Un empate entre tablas no acredita qué registro pertenece al ciclo.
    if any(s.silo_id != silo.pk or s.registrada_en >= vaciado.fecha_hora for s in salidas):
        return None
    # El catálogo excluye mermas y otras unidades; ninguna salida posterior
    # puede quedar oculta al demostrar que sólo hay recepción cruda nueva.
    if SalidaProceso.objects.filter(silo_id=silo.pk, registrada_en__gte=vaciado.fecha_hora).exists():
        return None
    posteriores = movimientos[ultimo_cero + 1:]
    ingresos = [m for m in posteriores if m.tipo == MovimientoSilo.Tipo.INGRESO]
    if len(ingresos) != 1 or posteriores[0].pk != ingresos[0].pk:
        return None
    ingreso = ingresos[0]
    if ingreso.origen_tipo != MovimientoSilo.OrigenTipo.RECEPCION:
        return None
    recepcion = Recepcion.objects.filter(
        pk=ingreso.origen_id, silo_id=silo.pk, sucursal_id=silo.sucursal_id,
        tipo_leche=Recepcion.TipoLeche.ENTERA, litros=ingreso.litros,
        estado__in=[Recepcion.Estado.DESCARGADA, Recepcion.Estado.CERRADA],
    ).first()
    if recepcion is None:
        return None
    descargas = MovimientoSilo.objects.filter(
        origen_tipo=MovimientoSilo.OrigenTipo.RECEPCION, origen_id=recepcion.pk,
    )
    if descargas.count() != 1:
        return None
    for movimiento in posteriores:
        if movimiento.pk == ingreso.pk:
            continue
        if movimiento.tipo != MovimientoSilo.Tipo.SALIDA:
            return None
        atribuciones = list(movimiento.atribuciones_recepcion.all())
        if (not atribuciones or any(
            a.recepcion_id != recepcion.pk or a.origen_no_atribuible
            for a in atribuciones
        ) or sum((a.litros for a in atribuciones), Decimal("0")) != movimiento.litros):
            return None
    return RecepcionNueva(recepcion.pk, ingreso, vaciado, saldo)
