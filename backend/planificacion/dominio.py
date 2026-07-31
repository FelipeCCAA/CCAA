"""
Reglas del planificador. Traducción de `prototipo/js/modelo/planificador.js`
y de `PLANIFICADOR.md` §4.

Funciones puras: no tocan la base de datos, no importan modelos y no dependen
de Django. Quien llama carga los bloques, los códigos y los balances una vez
y los pasa enteros.

El núcleo es `consumo_dia`: replica las fórmulas `COUNTIF(rango, código) ×
rendimiento` del Excel, pero sumando horas de bloques en vez de contando
celdas. Es lo que acopla el programa horario con el balance de leche, y ese
acoplamiento es la razón de ser de la herramienta.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable


CATEGORIAS = (
    "prec_nestle",
    "prec_ccaa",
    "secado_ccaa",
    "secado_nestle",
    "secado_colun",
)

#: Qué categorías descuentan de qué origen de leche.
ORIGEN_DE_CATEGORIA = {
    "prec_ccaa": "ccaa",
    "secado_ccaa": "ccaa",
    "prec_nestle": "nestle",
    "secado_nestle": "nestle",
    # Colún se seca con leche de P. Unión.
    "secado_colun": "punion",
}

ORIGENES = ("ccaa", "nestle", "punion")

DIAS = 7


def _numero(valor: Any) -> float:
    if valor is None or valor == "":
        return 0.0

    try:
        return float(valor)
    except (TypeError, ValueError):
        return 0.0


@dataclass(frozen=True)
class ConsumoDia:
    """Consumo de leche de un día, desglosado por categoría."""

    por_categoria: dict[str, float] = field(default_factory=dict)
    trasvasije: float = 0.0

    @property
    def derivado(self) -> float:
        """Lo que sale del programa horario, sin el trasvasije."""
        return sum(self.por_categoria.values())

    @property
    def total(self) -> float:
        return self.derivado + self.trasvasije


@dataclass(frozen=True)
class SaldoDia:
    """Una fila del balance, con todo lo derivado ya calculado."""

    dia: int
    stock_inicial: float
    recepciones: dict[str, float]
    consumo: ConsumoDia
    stock_por_origen: dict[str, float]

    @property
    def total_recepciones(self) -> float:
        return sum(self.recepciones.values())

    @property
    def total_disponible(self) -> float:
        return self.stock_inicial + self.total_recepciones

    @property
    def stock_final(self) -> float:
        return self.total_disponible - self.consumo.total

    @property
    def origenes_negativos(self) -> list[str]:
        """
        Un saldo negativo por origen es una alarma: falta leche de ese
        mandante para lo que se programó. Se informa, no se recorta a cero —
        el mismo criterio que la ocupación de silo (MODELO_DATOS.md §2.4).
        """
        return [o for o, v in self.stock_por_origen.items() if v < 0]


def consumo_dia(
    bloques: Iterable[Any],
    codigos: Iterable[Any],
    dia: int,
    trasvasije: float = 0.0,
) -> ConsumoDia:
    """
    Litros que consume el programa de un día, por categoría.

    Solo cuentan los bloques de **producción en evaporadores**. Un mismo
    código aparece en el evaporador y en la línea que lo recibe; sumar todos
    contaría la leche dos veces. El Excel lo evita sumando solo las filas de
    evaporadores, y esto hace lo mismo filtrando por equipo.
    """
    por_codigo = {c.id: c for c in codigos}
    acumulado = {categoria: 0.0 for categoria in CATEGORIAS}

    for bloque in bloques:
        if bloque.dia != dia:
            continue
        # Quién consume leche lo dice el propio equipo del bloque. Antes era
        # una tupla de códigos repetida aquí para no importar los modelos;
        # ahora el dato viaja con el objeto y sigue sin haber import.
        if bloque.tipo != "produccion" or not getattr(
            bloque.equipo, "consume_leche", False
        ):
            continue

        codigo = por_codigo.get(bloque.codigo_id)
        if codigo is None:
            continue

        horas = _numero(bloque.hora_fin) - _numero(bloque.hora_inicio)
        litros = horas * _numero(codigo.rendimiento_lh)

        if codigo.categoria in acumulado:
            acumulado[codigo.categoria] += litros

    return ConsumoDia(por_categoria=acumulado, trasvasije=_numero(trasvasije))


def balance_semana(
    bloques: Iterable[Any],
    codigos: Iterable[Any],
    balances: Iterable[Any],
    dias: int = DIAS,
) -> list[SaldoDia]:
    """
    El balance completo de la semana, día a día, con el arrastre de stock.

    El stock final de un día es el inicial del siguiente. Solo se teclea el
    del primer día; si algún día trae uno propio, manda sobre el arrastrado
    —sirve para corregir a mitad de semana sin rehacer el plan.

    El saldo por origen se arrastra igual, descontando cada categoría del
    mandante que le corresponde.
    """
    por_dia = {b.dia: b for b in balances}
    bloques = list(bloques)
    codigos = list(codigos)

    filas: list[SaldoDia] = []

    arrastre = 0.0
    arrastre_origen = {origen: 0.0 for origen in ORIGENES}

    for dia in range(dias):
        balance = por_dia.get(dia)

        declarado = _numero(getattr(balance, "stock_inicial", None)) if balance else 0.0
        tiene_declarado = (
            balance is not None and getattr(balance, "stock_inicial", None) is not None
        )

        stock_inicial = declarado if tiene_declarado else arrastre

        recepciones = {
            "ccaa": _numero(getattr(balance, "recepcion_ccaa", 0)) if balance else 0.0,
            "nestle": _numero(getattr(balance, "recepcion_nestle", 0)) if balance else 0.0,
            "punion": _numero(getattr(balance, "recepcion_punion", 0)) if balance else 0.0,
        }

        consumo = consumo_dia(
            bloques,
            codigos,
            dia,
            _numero(getattr(balance, "trasvasije", 0)) if balance else 0.0,
        )

        ajustes = (getattr(balance, "ajustes", None) or {}) if balance else {}

        stock_origen = {}
        for origen in ORIGENES:
            gastado = sum(
                litros
                for categoria, litros in consumo.por_categoria.items()
                if ORIGEN_DE_CATEGORIA.get(categoria) == origen
            )
            # El trasvasije sale de Nestlé, como en el Excel.
            if origen == "nestle":
                gastado += consumo.trasvasije

            stock_origen[origen] = (
                arrastre_origen[origen]
                + recepciones[origen]
                + _numero(ajustes.get(origen))
                - gastado
            )

        fila = SaldoDia(
            dia=dia,
            stock_inicial=stock_inicial,
            recepciones=recepciones,
            consumo=consumo,
            stock_por_origen=stock_origen,
        )
        filas.append(fila)

        arrastre = fila.stock_final
        arrastre_origen = stock_origen

    return filas


# ------------------------------------------------------------------ validación

@dataclass(frozen=True)
class Validacion:
    permitido: bool
    bloqueos: list[str] = field(default_factory=list)


def se_solapan(a: Any, b: Any) -> bool:
    """
    ¿Dos bloques del mismo equipo y día pisan el mismo tramo?

    Dos bloques contiguos —uno termina a las 14 y el otro empieza a las 14—
    NO se solapan: es la programación normal de un turno tras otro.
    """
    if a.equipo != b.equipo or a.dia != b.dia:
        return False

    inicio_a, fin_a = _numero(a.hora_inicio), _numero(a.hora_fin)
    inicio_b, fin_b = _numero(b.hora_inicio), _numero(b.hora_fin)

    return inicio_a < fin_b and inicio_b < fin_a


def validar_bloque(bloque: Any, existentes: Iterable[Any] = ()) -> Validacion:
    """Comprueba un bloque antes de guardarlo. Devuelve motivos, no un booleano."""
    bloqueos: list[str] = []

    inicio = _numero(bloque.hora_inicio)
    fin = _numero(bloque.hora_fin)

    if fin <= inicio:
        bloqueos.append("La hora de término debe ser posterior a la de inicio.")

    if not (0 <= inicio <= 24) or not (0 <= fin <= 24):
        bloqueos.append("Las horas deben estar entre 0 y 24.")

    if bloque.tipo == "produccion" and bloque.codigo_id is None:
        bloqueos.append("Un bloque de producción debe decir qué código produce.")

    if bloque.tipo == "estado" and not bloque.estado_equipo:
        bloqueos.append("Un bloque de estado debe decir qué pasa en el equipo.")

    for otro in existentes:
        if getattr(otro, "pk", None) is not None and otro.pk == getattr(bloque, "pk", None):
            continue

        if se_solapan(bloque, otro):
            bloqueos.append(
                f"Se solapa con otro bloque del mismo equipo entre "
                f"{_numero(otro.hora_inicio):g} y {_numero(otro.hora_fin):g}."
            )
            break

    return Validacion(permitido=not bloqueos, bloqueos=bloqueos)


def puede_publicar(
    semana: Any,
    bloques: Iterable[Any],
    codigos: Iterable[Any],
    balances: Iterable[Any],
    dias_habiles: int = 6,
) -> Validacion:
    """
    ¿La semana se puede publicar?

    Publicar es comprometerse con planta, así que se exige que el plan cuadre:
    cada día hábil con su balance y sin saldos negativos por origen. Un saldo
    negativo significa que se programó más leche de la que va a llegar, y
    publicarlo sería mandar a planta un programa que no se puede cumplir.
    """
    bloqueos: list[str] = []

    if not semana.puede_pasar_a("publicada"):
        bloqueos.append(
            f"Una semana {semana.get_estado_display().lower()} no se puede publicar."
        )

    bloques = list(bloques)

    if not bloques:
        bloqueos.append("La semana no tiene ningún bloque programado.")

    por_dia = {b.dia for b in balances}
    faltan = [d for d in range(dias_habiles) if d not in por_dia]

    if faltan:
        bloqueos.append(
            f"Faltan {len(faltan)} día(s) sin balance de leche cargado."
        )

    filas = balance_semana(bloques, codigos, balances, dias=dias_habiles)

    for fila in filas:
        if fila.origenes_negativos:
            origenes = ", ".join(fila.origenes_negativos)
            bloqueos.append(
                f"Día {fila.dia}: saldo negativo de {origenes}. "
                "Se programó más leche de la que se espera recibir."
            )

    # El solapamiento se valida al guardar cada bloque, pero se comprueba otra
    # vez aquí: publicar es el último punto donde el error sale barato.
    for i, bloque in enumerate(bloques):
        for otro in bloques[i + 1 :]:
            if se_solapan(bloque, otro):
                bloqueos.append(
                    f"Día {bloque.dia}: dos bloques se solapan en "
                    f"{bloque.equipo}."
                )
                break

    return Validacion(permitido=not bloqueos, bloqueos=bloqueos)


# ------------------------------------------------- calculadora de la hoja Base

def horas_corrida(kilos_objetivo: float, flujo: float) -> float | None:
    """
    Cuántas horas ocupa el equipo para sacar unos kilos, dado su flujo.

    Sirve para **sugerir** la hora de término al programar un bloque, no para
    imponerla: el programa lo decide Producción.
    """
    flujo = _numero(flujo)

    if flujo <= 0:
        return None

    return _numero(kilos_objetivo) / flujo


def factor_concentracion(sg: float, sng: float) -> float:
    """Sólidos grasos + no grasos sobre 100. De la hoja `Base` del Excel."""
    return (_numero(sg) + _numero(sng)) / 100
