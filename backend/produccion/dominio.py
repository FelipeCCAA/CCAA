"""
Reglas de calidad. Traducción de `prototipo/js/modelo/dominio.js`.

Funciones puras: no tocan la base de datos, no importan modelos y no dependen
de Django. Reciben datos y devuelven datos. Por eso se pueden probar solas y
por eso el prototipo las pudo trasladar aquí sin reescribirlas.

La regla que gobierna este archivo (MODELO_DATOS.md §2.2): el resultado de
calidad NUNCA se guarda. Se recalcula siempre desde los análisis y la
especificación vigente a la fecha del lote, de modo que al corregir una
especificación todo el histórico queda reevaluado con el criterio nuevo.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Any, Iterable, Sequence


# ---------------------------------------------------------------- resultados

CONFORME = "conforme"
NO_CONFORME = "no_conforme"
SIN_ANALISIS = "sin_analisis"
SIN_ESPECIFICACION = "sin_especificacion"

ETIQUETA_RESULTADO = {
    CONFORME: "Conforme",
    NO_CONFORME: "No conforme",
    SIN_ANALISIS: "Sin análisis",
    SIN_ESPECIFICACION: "Sin especificación",
}


# ------------------------------------------------------------------ detalles

@dataclass(frozen=True)
class DetalleParametro:
    """Cómo quedó un parámetro concreto frente a su rango."""

    parametro: str
    valor: float | None
    minimo: float | None
    maximo: float | None
    # en_rango | fuera_de_rango | faltante | no_medido
    estado: str
    # bajo | alto | None
    desvio: str | None = None

    @property
    def fuera_de_rango(self) -> bool:
        return self.estado == "fuera_de_rango"


@dataclass(frozen=True)
class EvaluacionAnalisis:
    """Veredicto de un análisis contra una especificación."""

    resultado: str
    detalle: list[DetalleParametro] = field(default_factory=list)
    desviaciones: list[DetalleParametro] = field(default_factory=list)
    faltantes: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class ResultadoLote:
    """Veredicto de un lote, agregando todos sus análisis."""

    resultado: str
    desviaciones: list[dict[str, Any]] = field(default_factory=list)
    evaluados: int = 0
    especificacion: Any = None

    @property
    def etiqueta(self) -> str:
        return ETIQUETA_RESULTADO[self.resultado]


# ------------------------------------------------------------------ ayudantes

def _es_vacio(valor: Any) -> bool:
    return valor is None or valor == ""


def _numero(valor: Any) -> float | None:
    """Convierte a número. Devuelve None si está vacío o no es convertible."""
    if _es_vacio(valor) or isinstance(valor, bool):
        return None

    try:
        numero = float(valor)
    except (TypeError, ValueError, InvalidOperation):
        return None

    # NaN no es comparable: se trata como "no medido".
    return None if numero != numero else numero


# ----------------------------------------------------------- especificaciones

def especificacion_vigente(
    especificaciones: Iterable[Any],
    producto_id: int,
    fecha: date,
) -> Any | None:
    """
    Especificación vigente para un producto en una fecha dada.

    Permite auditar un lote de mayo contra la especificación de mayo, aunque
    hoy esté vigente otra (MODELO_DATOS.md §2.3).

    Si dos versiones se solaparan, gana la de vigencia más reciente y, a
    igualdad de fecha, la de versión mayor.
    """
    candidatas = [
        e
        for e in (especificaciones or [])
        if e.producto_id == producto_id
        and e.vigente_desde <= fecha
        and (e.vigente_hasta is None or e.vigente_hasta >= fecha)
    ]

    if not candidatas:
        return None

    return max(candidatas, key=lambda e: (e.vigente_desde, e.version or 0))


# ------------------------------------------------------- evaluación de calidad

def evaluar_analisis(valores: dict[str, Any], especificacion: Any) -> EvaluacionAnalisis:
    """
    Evalúa los valores medidos de un análisis contra una especificación.

    Devuelve el detalle de cada parámetro además del veredicto, para que la
    interfaz pueda mostrar exactamente qué se salió de rango en vez de un
    "no conforme" sin explicación.
    """
    if especificacion is None:
        return EvaluacionAnalisis(resultado=SIN_ESPECIFICACION)

    detalle: list[DetalleParametro] = []
    medidos = valores or {}

    for parametro, rango in (especificacion.rangos or {}).items():
        minimo = _numero(rango.get("min"))
        maximo = _numero(rango.get("max"))
        valor = _numero(medidos.get(parametro))

        if valor is None:
            detalle.append(
                DetalleParametro(
                    parametro=parametro,
                    valor=None,
                    minimo=minimo,
                    maximo=maximo,
                    # Un parámetro no obligatorio que no se midió no penaliza.
                    estado="faltante" if rango.get("obligatorio") else "no_medido",
                )
            )
            continue

        bajo = minimo is not None and valor < minimo
        alto = maximo is not None and valor > maximo

        detalle.append(
            DetalleParametro(
                parametro=parametro,
                valor=valor,
                minimo=minimo,
                maximo=maximo,
                estado="fuera_de_rango" if (bajo or alto) else "en_rango",
                desvio="bajo" if bajo else ("alto" if alto else None),
            )
        )

    fuera_de_rango = [d for d in detalle if d.estado == "fuera_de_rango"]
    faltantes = [d for d in detalle if d.estado == "faltante"]
    con_valor = [d for d in detalle if d.valor is not None]

    if fuera_de_rango:
        resultado = NO_CONFORME
    elif faltantes or not con_valor:
        # Falta un obligatorio, o no se midió nada de lo que la spec pide.
        # No es conforme: es que no hay con qué afirmarlo.
        resultado = SIN_ANALISIS
    else:
        resultado = CONFORME

    return EvaluacionAnalisis(
        resultado=resultado,
        detalle=detalle,
        desviaciones=fuera_de_rango,
        faltantes=[d.parametro for d in faltantes],
    )


def resultado_calidad_lote(
    lote: Any,
    analisis: Sequence[Any],
    especificaciones: Iterable[Any],
) -> ResultadoLote:
    """
    Veredicto de calidad de un lote a partir de todos sus análisis.

    Agregación por el peor caso: si cualquier muestra del lote está fuera de
    especificación, el lote entero es no conforme. No se promedia, porque el
    producto físico ya está mezclado y no se puede separar la fracción
    defectuosa.

    Ese criterio está pendiente de confirmar con Calidad (MODELO_DATOS.md §8.2).
    """
    spec = especificacion_vigente(especificaciones, lote.producto_id, lote.fecha)

    if spec is None:
        return ResultadoLote(resultado=SIN_ESPECIFICACION)

    del_lote = [a for a in (analisis or []) if a.lote_id == lote.id]

    if not del_lote:
        return ResultadoLote(resultado=SIN_ANALISIS, especificacion=spec)

    evaluaciones = [(a, evaluar_analisis(a.valores, spec)) for a in del_lote]

    desviaciones = [
        {
            "analisis_id": a.id,
            "muestra": a.muestra,
            "parametro": d.parametro,
            "valor": d.valor,
            "min": d.minimo,
            "max": d.maximo,
            "desvio": d.desvio,
        }
        for a, ev in evaluaciones
        for d in ev.desviaciones
    ]

    resultados = {ev.resultado for _, ev in evaluaciones}

    if NO_CONFORME in resultados:
        resultado = NO_CONFORME
    elif SIN_ANALISIS in resultados:
        resultado = SIN_ANALISIS
    else:
        resultado = CONFORME

    return ResultadoLote(
        resultado=resultado,
        desviaciones=desviaciones,
        evaluados=len(del_lote),
        especificacion=spec,
    )


def kg_disponibles(lote: Any, kg_despachados: Decimal | float = 0) -> Decimal | None:
    """
    Kilos que quedan por despachar de un lote.

    Los despachos aún no existen como entidad, así que por ahora recibe el
    total despachado como parámetro. Cuando exista el módulo, se calculará
    desde ahí sin cambiar la firma para quien llame.

    Devuelve None mientras el lote no declare sus kilos: de un lote en proceso
    todavía no hay nada disponible, y contarlo como cero diría que se despachó
    todo.
    """
    if lote.kg_producidos is None:
        return None

    return Decimal(str(lote.kg_producidos)) - Decimal(str(kg_despachados))


# --------------------------------------------------------- código de lote

# Tipos de producto a efectos de la codificación (CCAA.Calidad.POE.009.02).
# No son la `familia` del producto: la familia agrupa por naturaleza (polvo,
# crema) y esto agrupa por cómo se codifica, que no es lo mismo — el
# precondensado y la crema comparten familia en algunos casos y llevan
# sufijos distintos.
TIPO_PRECONDENSADO = "precondensado"
TIPO_CREMA = "crema"
TIPO_LEP = "lep"  # leche entera o descremada en polvo

_SUFIJO_LINEA = {"E1": "1", "E2": "2"}

# CCAA + año(1) + juliano(3) + sufijo opcional + 'A' de segunda producción.
_PATRON_CODIGO = re.compile(r"^CCAA\d{4}(N|[12])?A?$")


def generar_codigo_lote(
    fecha: date,
    tipo: str,
    *,
    linea: str | None = None,
    nacional: bool = False,
    segunda_produccion: bool = False,
) -> str:
    """
    Arma el código de lote según CCAA.Calidad.POE.009.02.

    Base: 'CCAA' + último dígito del año + día juliano de tres dígitos. El
    sufijo depende del producto: 'N' para el precondensado de uso nacional,
    nada para la crema, y el número de la torre para el polvo (E1 → 1,
    E2 → 2). Si es la segunda producción del mismo día se agrega 'A', que es
    lo que el POE indica para no repetir el código.

    Es una función pura: arma el texto que el operador vería en papel, y nada
    más. **No garantiza unicidad** — la clave natural del lote sigue siendo
    `codigo_lote + producto + fecha`, que es lo que la base controla
    (MODELO_DATOS.md §2.1). Dos productos distintos del mismo día comparten
    código a propósito, igual que en planta.
    """
    base = f"CCAA{fecha.year % 10}{fecha.timetuple().tm_yday:03d}"

    if tipo == TIPO_PRECONDENSADO:
        sufijo = "N" if nacional else ""
    elif tipo == TIPO_CREMA:
        sufijo = ""
    elif tipo == TIPO_LEP:
        sufijo = _SUFIJO_LINEA.get(linea or "", "")
    else:
        raise ValueError(f"Tipo de producto desconocido para codificación: {tipo!r}")

    if segunda_produccion:
        sufijo += "A"

    return base + sufijo


def codigo_lote_valido(codigo: str) -> bool:
    """
    ¿El código respeta la forma del POE.009.02?

    Se ofrece para avisar en pantalla, **no para validar el modelo**. El
    histórico de planta tiene códigos que no siguen esta forma y que hay que
    poder registrar igual; convertir esto en una restricción del modelo
    impediría cargar lo que realmente pasó, que es justo lo contrario de lo
    que un registro de trazabilidad debe hacer.
    """
    return bool(_PATRON_CODIGO.match(codigo or ""))


def tipo_de_codificacion(producto) -> str:
    """
    Cómo se codifica este producto, a partir de su ficha de maestros.

    El POE agrupa por sufijo y el maestro agrupa por familia, y no son la
    misma partición: el precondensado es un líquido intermedio y lleva
    sufijo propio, mientras que la crema —que también sale líquida— no lleva
    ninguno. Por eso la regla mira la naturaleza antes que la familia.

    Lanza `ValueError` en vez de devolver un tipo por defecto: un producto
    que el POE no contempla necesita que alguien decida su sufijo, y elegir
    uno en silencio imprimiría códigos equivocados en las bolsas.
    """
    familia = getattr(producto, "familia", None)
    naturaleza = getattr(producto, "naturaleza", None)

    if familia == "polvo":
        return TIPO_LEP

    if familia == "crema":
        return TIPO_CREMA

    if naturaleza == "intermedio":
        return TIPO_PRECONDENSADO

    raise ValueError(
        f"El POE.009.02 no define cómo codificar «{producto}» "
        f"(familia {familia!r}, naturaleza {naturaleza!r})."
    )


@dataclass(frozen=True)
class DecisionCierre:
    """
    Una decisión con sus motivos, y con lo que solo hay que advertir.

    `bloqueos` impide; `avisos` deja pasar diciendo qué queda cojo. La
    distinción es el punto: mezclarlos obliga a elegir entre detener la
    producción por un dato completable o dejarlo pasar en silencio.
    """

    permitido: bool
    bloqueos: list[str] = field(default_factory=list)
    avisos: list[str] = field(default_factory=list)


def puede_declarar_producido(lote, asignaciones) -> DecisionCierre:
    """
    ¿Se puede cerrar la producción de este lote?

    Se declara producido cuando la corrida terminó, y ahí recién se conocen
    los kilos: por eso el lote se abre sin ellos y aquí se exigen. Sin kilos
    no hay rendimiento, no hay balance de despacho y no hay nada contra qué
    contrastar el plan.

    La leche asignada **no bloquea**: avisa. Un lote sin asignar es un lote
    sin trazabilidad hacia las recepciones, que es un problema real, pero
    impedir el cierre dejaría la producción del día detenida por un dato que
    se puede completar después. La decisión de endurecerlo es de Calidad, y
    se toma cambiando esta función, no parcheando la vista.

    Devuelve motivos, no un booleano (MODELO_DATOS.md §2.10).
    """
    bloqueos = []
    avisos = []

    if lote.kg_producidos is None:
        bloqueos.append(
            "Declara los kilos producidos: sin ellos no hay rendimiento ni "
            "balance de despacho."
        )
    elif Decimal(str(lote.kg_producidos)) <= 0:
        bloqueos.append("Los kilos producidos tienen que ser mayores que cero.")

    if not asignaciones:
        avisos.append(
            "El lote no tiene leche asignada: quedará sin trazabilidad hacia "
            "las recepciones."
        )

    return DecisionCierre(
        permitido=not bloqueos, bloqueos=bloqueos, avisos=avisos
    )
