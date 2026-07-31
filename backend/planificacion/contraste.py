"""
Contraste del plan contra lo que realmente pasó.

Es la otra mitad del planificador: publicar una semana es comprometerse, y
cerrarla exige poder mirar en qué se acertó y en qué no.

Los dos lados miden lo mismo con datos distintos, y esa es toda la idea:

    PLAN                              REAL
    ────                              ────
    leche que se espera recibir  vs   recepciones descargadas al silo
    consumo derivado del programa vs  salidas de silo de los lotes
    kilos objetivo de los bloques vs  kilos producidos de los lotes

El lado del plan sale de `BalanceDia` y de los bloques (proyección). El lado
real sale del libro mayor de silos y de los lotes (hechos). Ninguno se copia
del otro: si se copiaran, el contraste siempre cuadraría y no serviría para
nada.

Funciones puras, como el resto: reciben datos cargados y devuelven datos.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Any, Iterable

from . import dominio


def _numero(valor: Any) -> float:
    if valor is None or valor == "":
        return 0.0

    try:
        return float(valor)
    except (TypeError, ValueError):
        return 0.0


@dataclass(frozen=True)
class Desviacion:
    """Un par plan/real, con su diferencia ya calculada."""

    plan: float
    real: float

    @property
    def diferencia(self) -> float:
        return self.real - self.plan

    @property
    def pct(self) -> float | None:
        """
        Desviación relativa. `None` si no se planificó nada: dividir por cero
        daría un infinito, y decir "desvío del 0 %" sobre un plan vacío sería
        peor, porque parece que se cumplió.
        """
        if not self.plan:
            return None

        return round(self.diferencia / self.plan * 100, 1)


@dataclass(frozen=True)
class ContrasteDia:
    dia: int
    fecha: date
    leche_recibida: Desviacion
    leche_consumida: Desviacion
    kilos: Desviacion
    #: Lotes reales de ese día, para poder ir al detalle desde la pantalla.
    lotes: list[int] = field(default_factory=list)
    #: Verdad si hay algo real que contrastar. Un día sin producción todavía
    #: no es un día con desvío: es un día que no ha ocurrido.
    hubo_actividad: bool = False


def contrastar_semana(
    semana: Any,
    bloques: Iterable[Any],
    codigos: Iterable[Any],
    balances: Iterable[Any],
    recepciones: Iterable[Any],
    movimientos: Iterable[Any],
    lotes: Iterable[Any],
    dias: int = 7,
) -> list[ContrasteDia]:
    """
    Compara, día a día, lo planificado con lo ocurrido.

    `recepciones` deben venir ya filtradas a las **descargadas**: una
    recepción registrada pero no descargada no entró al silo, así que no es
    leche recibida todavía.

    `movimientos` son los del libro mayor; se cuentan solo las **salidas con
    origen en un lote**, que es el consumo real de producción. Los ajustes y
    los ingresos no son consumo.
    """
    filas_plan = dominio.balance_semana(bloques, codigos, balances, dias=dias)

    bloques = list(bloques)
    lotes = list(lotes)
    movimientos = list(movimientos)

    # Los lotes se agrupan por su fecha de producción, no por el día del plan:
    # es el dato que existe en la realidad.
    lotes_por_fecha: dict[date, list[Any]] = {}
    for lote in lotes:
        lotes_por_fecha.setdefault(lote.fecha, []).append(lote)

    recibido_por_fecha: dict[date, float] = {}
    for recepcion in recepciones:
        recibido_por_fecha[recepcion.fecha] = (
            recibido_por_fecha.get(recepcion.fecha, 0.0) + _numero(recepcion.litros)
        )

    # Consumo real: salidas de silo cuyo origen es un lote.
    consumo_por_lote: dict[int, float] = {}
    for movimiento in movimientos:
        if movimiento.tipo != "salida" or movimiento.origen_tipo != "lote":
            continue
        consumo_por_lote[movimiento.origen_id] = (
            consumo_por_lote.get(movimiento.origen_id, 0.0) + _numero(movimiento.litros)
        )

    salida: list[ContrasteDia] = []

    for fila in filas_plan:
        fecha = semana.fecha_del_dia(fila.dia)
        del_dia = lotes_por_fecha.get(fecha, [])

        kilos_reales = sum(_numero(l.kg_producidos) for l in del_dia)
        kilos_plan = sum(
            _numero(b.cantidad_kg) for b in bloques if b.dia == fila.dia and b.cantidad_kg
        )

        consumo_real = sum(consumo_por_lote.get(l.id, 0.0) for l in del_dia)
        recibido = recibido_por_fecha.get(fecha, 0.0)

        salida.append(
            ContrasteDia(
                dia=fila.dia,
                fecha=fecha,
                leche_recibida=Desviacion(
                    plan=fila.total_recepciones, real=recibido
                ),
                leche_consumida=Desviacion(
                    plan=fila.consumo.total, real=consumo_real
                ),
                kilos=Desviacion(plan=kilos_plan, real=kilos_reales),
                lotes=[l.id for l in del_dia],
                hubo_actividad=bool(del_dia) or recibido > 0,
            )
        )

    return salida


@dataclass(frozen=True)
class ResumenContraste:
    """Los totales de la semana, para encabezar la pantalla."""

    leche_recibida: Desviacion
    leche_consumida: Desviacion
    kilos: Desviacion
    dias_con_actividad: int


def resumir(contraste: Iterable[ContrasteDia]) -> ResumenContraste:
    filas = list(contraste)

    def sumar(atributo: str) -> Desviacion:
        return Desviacion(
            plan=sum(getattr(f, atributo).plan for f in filas),
            real=sum(getattr(f, atributo).real for f in filas),
        )

    return ResumenContraste(
        leche_recibida=sumar("leche_recibida"),
        leche_consumida=sumar("leche_consumida"),
        kilos=sumar("kilos"),
        dias_con_actividad=sum(1 for f in filas if f.hubo_actividad),
    )
