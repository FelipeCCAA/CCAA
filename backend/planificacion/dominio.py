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
from datetime import datetime, time, timedelta
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
        horas = None
        inicio_dt = getattr(bloque, "fecha_hora_inicio", None)
        fin_dt = getattr(bloque, "fecha_hora_fin", None)
        semana = getattr(bloque, "semana", None)
        if inicio_dt and fin_dt and semana:
            tz = inicio_dt.tzinfo
            desde = datetime.combine(semana.fecha_del_dia(dia), time.min, tzinfo=tz)
            hasta = desde + timedelta(days=1)
            solape_inicio = max(inicio_dt, desde)
            solape_fin = min(fin_dt, hasta)
            if solape_fin <= solape_inicio:
                continue
            horas = (solape_fin - solape_inicio).total_seconds() / 3600
        elif bloque.dia != dia:
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

        if horas is None:
            horas = _numero(bloque.hora_fin) - _numero(bloque.hora_inicio)
        capacidad = _numero(getattr(bloque, "capacidad_hora", None)) or _numero(codigo.rendimiento_lh)
        litros = horas * capacidad

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
    if a.equipo != b.equipo:
        return False

    inicio_dt_a, fin_dt_a = getattr(a, "fecha_hora_inicio", None), getattr(a, "fecha_hora_fin", None)
    inicio_dt_b, fin_dt_b = getattr(b, "fecha_hora_inicio", None), getattr(b, "fecha_hora_fin", None)
    if inicio_dt_a and fin_dt_a and inicio_dt_b and fin_dt_b:
        return inicio_dt_a < fin_dt_b and inicio_dt_b < fin_dt_a
    if a.dia != b.dia:
        return False

    inicio_a, fin_a = _numero(a.hora_inicio), _numero(a.hora_fin)
    inicio_b, fin_b = _numero(b.hora_inicio), _numero(b.hora_fin)

    return inicio_a < fin_b and inicio_b < fin_a


def validar_bloque(bloque: Any, existentes: Iterable[Any] = ()) -> Validacion:
    """Comprueba un bloque antes de guardarlo. Devuelve motivos, no un booleano."""
    bloqueos: list[str] = []

    inicio_dt = getattr(bloque, "fecha_hora_inicio", None)
    fin_dt = getattr(bloque, "fecha_hora_fin", None)
    inicio = _numero(bloque.hora_inicio)
    fin = _numero(bloque.hora_fin)

    if inicio_dt and fin_dt:
        if fin_dt <= inicio_dt:
            bloqueos.append("La fecha y hora de término debe ser posterior al inicio.")
    elif fin <= inicio:
        bloqueos.append("La hora de término debe ser posterior a la de inicio.")

    if not inicio_dt and (not (0 <= inicio <= 24) or not (0 <= fin <= 24)):
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


def alertas_actividades(bloques: Iterable[Any]) -> list[dict[str, Any]]:
    """Advertencias accionables que no bloquean el trabajo en borrador."""
    alertas = []
    for bloque in bloques:
        tipo = getattr(getattr(bloque, "tipo_actividad", None), "codigo", None)
        faltan = []
        if tipo == "produccion" or bloque.tipo == "produccion":
            if not getattr(bloque, "producto_id", None) and not getattr(bloque, "codigo_id", None):
                faltan.append("producto")
            if not getattr(bloque, "origen_leche_id", None) and not getattr(getattr(bloque, "codigo", None), "mandante_id", None):
                faltan.append("origen")
            if _numero(getattr(bloque, "capacidad_hora", None)) <= 0 and _numero(getattr(getattr(bloque, "codigo", None), "rendimiento_lh", None)) <= 0:
                faltan.append("capacidad")
        if faltan:
            alertas.append({"tipo": "datos_incompletos", "actividad": bloque.id, "mensaje": f"Actividad {bloque.id}: falta {', '.join(faltan)}."})
    return alertas


def balance_por_movimientos(
    semana: Any,
    bloques: Iterable[Any],
    movimientos: Iterable[Any],
    stocks_seguridad: dict[int, float] | None = None,
) -> dict[str, Any]:
    """Proyección explicable por propietario usando únicamente movimientos visibles."""
    bloques = list(bloques)
    movimientos = list(movimientos)
    seguridad = stocks_seguridad or {}
    propietarios: dict[int, str] = {}
    for movimiento in movimientos:
        propietarios[movimiento.propietario_id] = str(movimiento.propietario)
    for bloque in bloques:
        propietario = getattr(bloque, "origen_leche", None) or getattr(getattr(bloque, "codigo", None), "mandante", None)
        if propietario:
            propietarios[propietario.id] = str(propietario)

    saldos = {propietario_id: 0.0 for propietario_id in propietarios}
    dias = []
    alertas = alertas_actividades(bloques)
    signos = {
        "recepcion": 1, "trasvasije_entrada": 1,
        "despacho": -1, "trasvasije_salida": -1,
    }

    for dia in range(DIAS):
        fecha = semana.fecha_del_dia(dia)
        detalle = []
        inicial = dict(saldos)
        for movimiento in movimientos:
            if movimiento.fecha_hora.date() != fecha:
                continue
            propietario_id = movimiento.propietario_id
            saldos.setdefault(propietario_id, 0.0)
            cantidad = _numero(movimiento.cantidad)
            if movimiento.tipo == "stock_inicial":
                saldos[propietario_id] = cantidad
                efecto = cantidad - inicial.get(propietario_id, 0.0)
            elif movimiento.tipo == "ajuste":
                efecto = cantidad
                saldos[propietario_id] += efecto
            else:
                efecto = cantidad * signos.get(movimiento.tipo, 0)
                saldos[propietario_id] += efecto
            detalle.append({
                "id": movimiento.id, "tipo": movimiento.tipo,
                "propietario": propietario_id, "cantidad": cantidad,
                "efecto": efecto, "documento": movimiento.documento,
                "observacion": movimiento.observacion,
            })

        consumo_total = 0.0
        consumo_por_propietario = {propietario_id: 0.0 for propietario_id in propietarios}
        for bloque in bloques:
            if not getattr(bloque, "consume_leche", False):
                continue
            propietario = getattr(bloque, "origen_leche", None) or getattr(getattr(bloque, "codigo", None), "mandante", None)
            if propietario is None:
                continue
            consumo = consumo_dia([bloque], [bloque.codigo] if bloque.codigo_id else [], dia).total
            consumo_por_propietario[propietario.id] = consumo_por_propietario.get(propietario.id, 0.0) + consumo
            saldos[propietario.id] = saldos.get(propietario.id, 0.0) - consumo
            consumo_total += consumo

        for propietario_id, saldo in saldos.items():
            minimo = _numero(seguridad.get(propietario_id))
            if saldo < 0:
                alertas.append({"tipo": "stock_negativo", "dia": dia, "propietario": propietario_id, "mensaje": f"{propietarios.get(propietario_id, propietario_id)} queda con {saldo:,.0f} L."})
            elif saldo < minimo:
                alertas.append({"tipo": "stock_seguridad", "dia": dia, "propietario": propietario_id, "mensaje": f"{propietarios.get(propietario_id, propietario_id)} queda bajo su stock de seguridad ({minimo:,.0f} L)."})

        dias.append({
            "dia": dia, "fecha": fecha, "stock_inicial": inicial,
            "movimientos": detalle, "consumo_por_propietario": consumo_por_propietario,
            "consumo": consumo_total, "stock_final": dict(saldos),
        })

    horas_por_equipo: dict[int, float] = {}
    for bloque in bloques:
        horas_por_equipo[bloque.equipo_id] = horas_por_equipo.get(bloque.equipo_id, 0.0) + bloque.horas
    utilizacion = {equipo_id: min(100.0, horas / (DIAS * 24) * 100) for equipo_id, horas in horas_por_equipo.items()}
    return {
        "propietarios": [{"id": id_, "nombre": nombre} for id_, nombre in propietarios.items()],
        "dias": dias,
        "alertas": alertas,
        "consumo_total": sum(dia["consumo"] for dia in dias),
        "stock_final_total": sum(saldos.values()),
        "utilizacion_por_equipo": utilizacion,
    }


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
