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

# CCAA + año(1) + juliano(3) + SKU + '-' + correlativo(2).
#
# El SKU es lo que distingue dos lotes del mismo día, y el correlativo lo que
# distingue dos lotes del mismo producto el mismo día. Antes el sufijo
# codificaba la torre y el uso nacional (POE.009.02); ahora eso vive dentro
# del SKU del producto, que es donde se mantiene una sola vez.
_PATRON_CODIGO = re.compile(r"^CCAA\d{4}[A-Za-z0-9]+-\d{2}$")


def generar_codigo_lote(fecha: date, sku: str, correlativo: int = 1) -> str | None:
    """
    Arma el código de un lote: CCAA + año + día juliano + SKU + correlativo.

    El correlativo va **siempre**, desde `-01`. Ponerlo solo a partir del
    segundo lote deja dos formas distintas conviviendo, y quien lee, ordena o
    busca códigos tiene que conocer la excepción.

    Devuelve `None` si el producto no tiene SKU. Es la única pieza que el
    sistema no puede deducir, y componer un código sin ella —o con un relleno
    inventado— imprimiría en la bolsa algo que no identifica al producto.

    Es una función pura: arma el texto y nada más. **No garantiza unicidad**;
    la clave natural del lote sigue siendo `codigo_lote + producto + fecha`,
    que es lo que la base controla (MODELO_DATOS.md §2.1).
    """
    limpio = (sku or "").strip()

    if not limpio:
        return None

    base = f"CCAA{fecha.year % 10}{fecha.timetuple().tm_yday:03d}"

    return f"{base}{limpio}-{correlativo:02d}"


def codigo_lote_valido(codigo: str) -> bool:
    """
    ¿El código respeta la forma vigente?

    Se ofrece para avisar en pantalla, **no para validar el modelo**. El
    histórico de planta tiene códigos que no siguen esta forma —empezando por
    todos los del POE.009.02 anterior— y que hay que poder registrar igual;
    convertir esto en una restricción del modelo impediría cargar lo que
    realmente pasó, que es justo lo contrario de lo que un registro de
    trazabilidad debe hacer.
    """
    return bool(_PATRON_CODIGO.match(codigo or ""))


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


#: Estados en los que el material ya debió descontarse de bodega. Un lote en
#: proceso todavía no tiene kilos, así que no hay nada que descontar.
ESTADOS_CON_CONSUMO = ("producido", "cerrado")


def consumo_de_inventario_pendiente(lote, consumo) -> bool:
    """
    ¿Este lote debió descontar material de bodega y todavía no lo hizo?

    El descuento se intenta solo al declarar el lote producido, que es cuando
    se conocen los kilos. Si falla —no hay receta cargada, falta stock, el
    material sigue en cuarentena— el lote **igual se declara**: es el mismo
    criterio que la leche asignada, y por la misma razón. Detener la
    producción del día por un dato que bodega puede completar después
    trasladaría a la línea un problema que no es suyo.

    Pero un descuento que falló y no se ve es peor que uno que no se intentó:
    el saldo de bodega queda alto y nadie lo sabe. Por eso queda pendiente y a
    la vista, para que se pueda reintentar.

    `consumo` es la cabecera `ConsumoLoteProduccion` del lote, o `None`. Se
    recibe ya resuelta para que esta función no consulte la base.
    """
    if lote.estado not in ESTADOS_CON_CONSUMO:
        return False

    return consumo is None


# --------------------------------------------------------------- PCC 1

#: Claves de `ControlProcesoLectura.valores` que vigila el PCC 1 de
#: uperización. Van aquí y no en el modelo porque el modelo guarda las
#: lecturas como JSON —los parámetros cambian por equipo— y esta es la única
#: parte de ese JSON que decide si un lote se puede liberar.
#:
#: **Tienen que coincidir con lo que escribe la pantalla de captura.** Si la
#: pantalla renombra el campo, el control deja de encontrarlo y el PCC pasa a
#: no vigilar nada en silencio, que es peor que fallar. De ahí que
#: `evaluar_pcc1` distinga «cumple» de «no se midió».
PCC1_TEMPERATURA = "t_dsi"
PCC1_CAUDAL = "flujo_entrada"


@dataclass(frozen=True)
class IncumplimientoPcc1:
    """Una lectura que se salió del límite crítico."""

    hora: Any
    parametro: str
    valor: float
    limite: float
    # 'bajo' para la temperatura, 'alto' para el caudal.
    sentido: str

    @property
    def descripcion(self) -> str:
        etiqueta = "Temperatura" if self.parametro == PCC1_TEMPERATURA else "Caudal"
        relacion = "por debajo del mínimo" if self.sentido == "bajo" else "sobre el máximo"

        return f"{etiqueta} {self.valor} {relacion} ({self.limite}) a las {self.hora}"


@dataclass(frozen=True)
class EvaluacionPcc1:
    """
    Cómo quedó el PCC 1 de un control de proceso.

    `sin_limites` y `sin_lecturas` no son lo mismo que cumplir: un control al
    que nadie le puso límites, o que no tiene ninguna lectura, no demuestra
    que la uperización ocurrió. Se distinguen para que la liberación pueda
    decir cuál de los dos falta.
    """

    cumple: bool
    incumplimientos: list[IncumplimientoPcc1] = field(default_factory=list)
    sin_limites: bool = False
    sin_lecturas: bool = False


def evaluar_pcc1(control: Any, lecturas: Iterable[Any] = ()) -> EvaluacionPcc1:
    """
    Evalúa las lecturas de un control contra su límite crítico.

    El límite se lee del propio control y no de un maestro: cambia por equipo
    y por producto —el VEB trabaja a 80,0 °C y el Scheffers 2 a 81,2— y un
    control de mayo tiene que auditarse contra el límite que regía en mayo.

    Una lectura que no trae el parámetro **no cuenta como incumplimiento**:
    no se midió. Lo que sí se informa es que el control entero no tiene
    lecturas, porque un PCC sin lecturas no vigiló nada.
    """
    temp_min = _numero(getattr(control, "pcc1_temp_min", None))
    caudal_max = _numero(getattr(control, "pcc1_caudal_max", None))

    propias = [
        lectura
        for lectura in (lecturas or [])
        if getattr(lectura, "control_id", None) == control.id
    ]

    if temp_min is None and caudal_max is None:
        return EvaluacionPcc1(cumple=True, sin_limites=True, sin_lecturas=not propias)

    incumplimientos: list[IncumplimientoPcc1] = []

    for lectura in propias:
        valores = getattr(lectura, "valores", None) or {}

        temperatura = _numero(valores.get(PCC1_TEMPERATURA))
        if temp_min is not None and temperatura is not None and temperatura < temp_min:
            incumplimientos.append(
                IncumplimientoPcc1(
                    hora=lectura.hora,
                    parametro=PCC1_TEMPERATURA,
                    valor=temperatura,
                    limite=temp_min,
                    sentido="bajo",
                )
            )

        caudal = _numero(valores.get(PCC1_CAUDAL))
        if caudal_max is not None and caudal is not None and caudal > caudal_max:
            incumplimientos.append(
                IncumplimientoPcc1(
                    hora=lectura.hora,
                    parametro=PCC1_CAUDAL,
                    valor=caudal,
                    limite=caudal_max,
                    sentido="alto",
                )
            )

    return EvaluacionPcc1(
        cumple=not incumplimientos,
        incumplimientos=incumplimientos,
        sin_lecturas=not propias,
    )


@dataclass(frozen=True)
class DecisionApertura:
    """Si de este vale puede nacer un lote, y por qué no."""

    permitido: bool
    bloqueos: tuple[str, ...] = ()
    litros_disponibles: Decimal = Decimal("0")


def puede_abrir_lote_desde(vale, litros, consumido_por_otros_lotes=0) -> DecisionApertura:
    """
    ¿Se puede abrir un lote con la leche de este vale?

    **Quien consume el silo es el vale, no el lote.** La leche entra al silo de
    destino cuando el vale se transfiere, y ahí deja de ser leche cruda: ya está
    estandarizada al RC que un producto pide. Lo que hace el lote después es
    declarar **a qué producto** va esa leche.

    De ahí salen las dos reglas:

    1. **Solo un vale liberado.** Un vale que no llegó a liberarse es uno cuyo
       RC medido no cumple —está en corrección, o se anuló—. Abrir un lote con
       esa leche es empezar a secar una mezcla que la propia planta declaró
       fuera de objetivo.

    2. **No se puede sacar más de lo que el vale preparó.** Un vale puede
       alimentar varias corridas —veinte mil litros no se secan de una vez— pero
       la suma no puede pasar del volumen preparado. Sin este tope, dos lotes
       del mismo vale dirían tener leche que nunca existió, y el rendimiento de
       los dos saldría mal.

    Devuelve motivos, no un booleano, como el resto de las decisiones.
    """
    bloqueos = []

    estado = getattr(vale, "estado", None)

    if estado != "liberado":
        etiqueta = getattr(vale, "get_estado_display", lambda: estado)()
        bloqueos.append(
            f"El vale {getattr(vale, 'codigo', '')} está «{etiqueta}» y no "
            "liberado: su RC medido no cumple el objetivo, así que esa leche "
            "todavía no es la de ningún producto."
        )

    preparado = Decimal(str(getattr(vale, "volumen", 0) or 0))
    ya_usado = Decimal(str(consumido_por_otros_lotes or 0))
    disponible = preparado - ya_usado

    pedido = Decimal(str(litros or 0))

    if pedido <= 0:
        bloqueos.append("Los litros que toma el lote tienen que ser mayores que cero.")
    elif pedido > disponible:
        bloqueos.append(
            f"El vale preparó {preparado} L y ya se usaron {ya_usado}: quedan "
            f"{disponible} L y se piden {pedido}."
        )

    return DecisionApertura(
        permitido=not bloqueos,
        bloqueos=tuple(bloqueos),
        litros_disponibles=disponible,
    )
