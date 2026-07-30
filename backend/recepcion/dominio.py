"""
Reglas de recepción y silos. Traducción de `prototipo/js/modelo/dominio.js`.

Funciones puras, como las de calidad: reciben datos y devuelven datos.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any, Iterable


# Límites de control del camión.
#
# Son REFERENCIALES y están pendientes de confirmar con Calidad
# (MODELO_DATOS.md §8.5). Se declaran aquí, en un solo lugar, para que
# cambiarlos sea editar una línea y no buscar números por el código.
LIMITES = {
    "acidez_max": 18.0,
    "ph_min": 6.5,
    "ph_max": 6.9,
    "temperatura_max": 8.0,
    # La crioscopía detecta aguado: un valor MENOS negativo que este es
    # sospechoso, porque el agua sube el punto de congelación.
    "crioscopia_max": -0.510,
}


# Controles sin los cuales no se puede liberar.
#
# El Delvo detecta antibióticos, y esa leche no entra a la planta bajo ningún
# criterio: sin ese resultado no hay nada que autorizar. Que falte no es
# "conforme", es que nadie lo midió — la misma distinción que hace Calidad
# entre un lote conforme y uno sin análisis (MODELO_DATOS.md §2.2).
#
# Qué controles son obligatorios está pendiente de definir con Calidad (§8.5).
# Este es el piso de seguridad, no la lista final: agregar `inhibidores` u
# `organoleptico` es añadirlos a esta tupla.
CONTROLES_DECISIVOS = ("delvo",)


@dataclass(frozen=True)
class EvaluacionRecepcion:
    # ¿Lo que se midió está dentro de límites? NO significa que se pueda
    # liberar: para eso hay que haber medido lo decisivo. Las dos cosas se
    # separan a propósito, porque confundirlas es lo que dejaba pasar leche
    # sin analizar como si estuviera conforme.
    conforme: bool
    # liberada | retenida | sin_analisis
    estado: str
    motivos: list[str] = field(default_factory=list)
    faltantes: list[str] = field(default_factory=list)

    @property
    def analizada(self) -> bool:
        """¿Hay con qué decidir? Sin esto no se libera ni se retiene."""
        return self.estado != SIN_ANALISIS

    @property
    def liberable(self) -> bool:
        return self.estado == LIBERADA


LIBERADA = "liberada"
RETENIDA = "retenida"
SIN_ANALISIS = "sin_analisis"


@dataclass(frozen=True)
class Ocupacion:
    silo_id: int
    codigo: str
    litros: float
    capacidad: float
    pct: int
    excedido: bool
    negativo: bool


def _numero(valor: Any) -> float | None:
    if valor is None or valor == "" or isinstance(valor, bool):
        return None

    try:
        numero = float(valor)
    except (TypeError, ValueError):
        return None

    return None if numero != numero else numero


def evaluar_recepcion(controles: dict[str, Any], limites: dict | None = None) -> EvaluacionRecepcion:
    """
    ¿La leche del camión puede liberarse al silo?

    Delvo o inhibidores positivos retienen automáticamente: son presencia de
    antibióticos, y esa leche no entra a la planta.

    Devuelve los motivos, no solo un booleano, para que la pantalla pueda
    explicar por qué se retuvo (MODELO_DATOS.md §2.10).

    Sin los controles decisivos NO devuelve "liberada": devuelve
    `sin_analisis`. Antes, una recepción con los controles vacíos salía
    conforme —no había motivos que informar— y la pantalla decía "Sin
    alertas" sobre leche que nadie había medido.
    """
    c = controles or {}
    lim = {**LIMITES, **(limites or {})}
    motivos: list[str] = []

    faltantes = [
        control
        for control in CONTROLES_DECISIVOS
        if c.get(control) in (None, "")
    ]

    if c.get("delvo") == "Positivo":
        motivos.append("Delvo Test positivo (presencia de antibióticos).")

    if c.get("inhibidores") == "Positivo":
        motivos.append("Inhibidores positivos.")

    if c.get("organoleptico") == "No conforme":
        motivos.append("Evaluación organoléptica no conforme.")

    acidez = _numero(c.get("acidez"))
    if acidez is not None and acidez > lim["acidez_max"]:
        motivos.append(
            f"Acidez {acidez} °D sobre el máximo ({lim['acidez_max']} °D)."
        )

    ph = _numero(c.get("ph"))
    if ph is not None and not (lim["ph_min"] <= ph <= lim["ph_max"]):
        motivos.append(f"pH {ph} fuera del rango {lim['ph_min']}–{lim['ph_max']}.")

    temperatura = _numero(c.get("temperatura"))
    if temperatura is not None and temperatura > lim["temperatura_max"]:
        motivos.append(
            f"Temperatura {temperatura} °C sobre el máximo "
            f"({lim['temperatura_max']} °C)."
        )

    crioscopia = _numero(c.get("crioscopia"))
    if crioscopia is not None and crioscopia > lim["crioscopia_max"]:
        motivos.append(f"Crioscopía {crioscopia} indica posible aguado.")

    # Un motivo manda sobre la falta de datos: si el Delvo salió positivo, la
    # leche se retiene aunque falten los demás controles.
    if motivos:
        estado = RETENIDA
    elif faltantes:
        estado = SIN_ANALISIS
    else:
        estado = LIBERADA

    return EvaluacionRecepcion(
        # `conforme` sigue significando lo mismo que antes: nada de lo medido
        # se salió de rango. Lo que cambia es `estado`, que es el que decide.
        conforme=not motivos,
        estado=estado,
        motivos=motivos,
        faltantes=faltantes,
    )


def ocupacion_silo(silo: Any, movimientos: Iterable[Any], hasta=None) -> Ocupacion:
    """
    Ocupación real de un silo: la suma de su libro de movimientos.

    No es el acumulado histórico de recepciones — descuenta lo consumido
    (MODELO_DATOS.md §2.4).

    Un saldo negativo no se corrige aquí: se informa. Significa que el
    registro está descuadrado, y esconderlo con un max(0, …) haría que el
    error nunca se descubriera.
    """
    litros = Decimal("0")

    for movimiento in movimientos or []:
        if movimiento.silo_id != silo.id:
            continue

        if hasta is not None and movimiento.fecha_hora > hasta:
            continue

        valor = Decimal(str(movimiento.litros or 0))

        if movimiento.tipo == "ingreso":
            litros += valor
        elif movimiento.tipo == "salida":
            litros -= valor
        else:
            # Ajuste: suma con su signo, que puede ser negativo.
            litros += valor

    capacidad = Decimal(str(silo.capacidad_l or 0))

    return Ocupacion(
        silo_id=silo.id,
        codigo=silo.codigo,
        litros=float(litros),
        capacidad=float(capacidad),
        pct=int(round(litros / capacidad * 100)) if capacidad else 0,
        excedido=capacidad > 0 and litros > capacidad,
        negativo=litros < 0,
    )


def trazabilidad_lote(lote_id: int, movimientos: Iterable[Any]) -> list[dict]:
    """
    De qué silos consumió un lote y qué recepciones habían ingresado a esos
    silos antes del consumo.

    Devuelve un CONJUNTO de recepciones candidatas, no una cadena uno a uno
    (MODELO_DATOS.md §2.5): la leche se mezcla dentro del silo, así que
    prometer un vínculo exacto sería falso.
    """
    movimientos = list(movimientos or [])

    consumos = [
        m
        for m in movimientos
        if m.tipo == "salida" and m.origen_tipo == "lote" and m.origen_id == lote_id
    ]

    resultado = []

    for consumo in consumos:
        ids_recepcion = [
            m.origen_id
            for m in movimientos
            if m.silo_id == consumo.silo_id
            and m.tipo == "ingreso"
            and m.origen_tipo == "recepcion"
            and m.fecha_hora <= consumo.fecha_hora
        ]

        resultado.append(
            {
                "silo_id": consumo.silo_id,
                "litros": float(consumo.litros or 0),
                "fecha_hora": consumo.fecha_hora,
                "recepciones": ids_recepcion,
            }
        )

    return resultado
