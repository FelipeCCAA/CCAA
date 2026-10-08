from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal


@dataclass(frozen=True)
class BalanceDescremacion:
    descremada_esperada_l: Decimal | None
    crema_esperada_l: Decimal | None
    merma_declarada_l: Decimal | None
    desvio_grasa_kg: Decimal | None
    avisos: tuple[str, ...]


def calcular_balance_descremacion(
    litros_entrada, grasa_entrada, sng_entrada, grasa_descremada, grasa_crema,
    *, litros_descremada=None, litros_crema=None,
):
    """Balance orientativo: los parámetros reales de planta se informan, no se inventan."""
    volumen = Decimal(str(litros_entrada))
    gi, gd, gc = map(Decimal, map(str, (grasa_entrada, grasa_descremada, grasa_crema)))
    Decimal(str(sng_entrada))  # Valida que el dato usado para trazabilidad sea numérico.
    avisos = []
    esperada_crema = esperada_descremada = None
    if not (gd < gi < gc):
        avisos.append("Las grasas deben cumplir: descremada < entrada < crema.")
    else:
        esperada_crema = volumen * (gi - gd) / (gc - gd)
        esperada_descremada = volumen - esperada_crema

    merma = desvio = None
    if litros_descremada is not None and litros_crema is not None:
        ld, lc = Decimal(str(litros_descremada)), Decimal(str(litros_crema))
        merma = volumen - ld - lc
        grasa_entrada_kg = volumen * gi / Decimal("100")
        grasa_salida_kg = ld * gd / Decimal("100") + lc * gc / Decimal("100")
        desvio = grasa_entrada_kg - grasa_salida_kg
        if merma != 0:
            avisos.append(f"Diferencia volumétrica declarada: {merma:.2f} L.")
        if desvio != 0:
            avisos.append(f"Diferencia de grasa declarada: {desvio:.3f} kg.")
    return BalanceDescremacion(
        esperada_descremada, esperada_crema, merma, desvio, tuple(avisos)
    )


# Límites físicos de la descremación (docs/REGLAS_DE_PLANTA.md §2). Avisan,
# no bloquean: endurecerlos —que la grasa alta impida cerrar o retenga el
# TK— es decisión de Calidad y se hace aquí y en quien llama a
# `avisos_limites_descremacion`, no en una segunda regla.
LIMITE_GRASA_DESCREMADA = Decimal("0.1")  # %
RANGO_GRASA_CREMA_DESPACHO = (Decimal("42"), Decimal("43"))  # %


def _porcentaje(valor):
    """`Decimal("0.150")` → «0,15»: como se lee en planta."""
    return f"{valor.normalize():f}".replace(".", ",")


def avisos_limites_descremacion(*, grasa_descremada, grasa_crema, crema_a_despacho):
    """
    Los límites físicos que no cumple el cierre, como `(codigo, mensaje)`.

    Un valor ausente no avisa: todavía no se tecleó. El límite de la crema es
    el de «crema para despacho»: solo aplica si va a despacho directo; para
    Mantequilla o Estandarización el documento no da límite y no se inventa.
    Las RPM no están: no hay sensor ni campo, y en el documento son una
    alarma del arranque, no una medición del cierre.
    """
    avisos = []
    if grasa_descremada is not None:
        grasa = Decimal(str(grasa_descremada))
        if grasa > LIMITE_GRASA_DESCREMADA:
            avisos.append((
                "grasa_descremada_alta",
                f"Grasa de la descremada {_porcentaje(grasa)} % sobre el límite de "
                f"{_porcentaje(LIMITE_GRASA_DESCREMADA)} %.",
            ))
    if grasa_crema is not None and crema_a_despacho:
        grasa = Decimal(str(grasa_crema))
        minimo, maximo = RANGO_GRASA_CREMA_DESPACHO
        if not minimo <= grasa <= maximo:
            avisos.append((
                "grasa_crema_fuera_de_rango",
                f"Grasa de la crema para despacho {_porcentaje(grasa)} % fuera del rango "
                f"{_porcentaje(minimo)}–{_porcentaje(maximo)} %.",
            ))
    return avisos


# Pantalla donde se trabaja cada etapa, para los enlaces de los avisos.
# Misma tabla que `rutaDeEtapa` en `frontend/src/services/planta-ahora.ts`:
# si divergen, un aviso lleva a una sección que no existe.
RUTAS_POR_ETAPA = {
    "recepcion": "/leche",
    "estandarizacion": "/estandarizacion",
    "descremacion": "/produccion/descremado",
    "evaporacion": "/produccion/evaporacion",
    "condensacion": "/produccion/evaporacion",
    "secado": "/produccion/secado",
    "envasado": "/envasado",
    "mantequilla": "/procesos?seccion=mantequilla",
    "transferencia": "/produccion",
    "otro": "/produccion",
}


def ruta_de_etapa(tipo: str) -> str:
    """La pantalla donde se trabaja una etapa; el panel de producción si no se conoce."""
    return RUTAS_POR_ETAPA.get(tipo, "/produccion")


# Balance del cierre de Mantequilla. El cliente comparaba en milésimas de kg y
# el modelo exigía diferencia == 0: la misma regla. Tres decimales es la
# precisión de las columnas; cambiar la tolerancia es editar esta constante,
# no buscar dos comparaciones.
TOLERANCIA_BALANCE_MANTEQUILLA_KG = Decimal("0")
_MILESIMA = Decimal("0.001")

MENSAJE_FALTA_MANTEQUILLA = "Indica la mantequilla producida."
MENSAJE_SUERO_SIN_LOTE = "Esta corrida no tiene un lote de suero asociado: registra 0 kg."
MENSAJE_REPROCESO_SIN_MOTIVO = "Indica por qué este material requiere reproceso."


@dataclass(frozen=True)
class BalanceMantequilla:
    entrada_kg: Decimal
    clasificado_kg: Decimal
    diferencia_kg: Decimal  # entrada − clasificado
    cuadra: bool
    mensaje: str | None  # None si cuadra


def _kg(valor):
    """Un valor en kg redondeado a la milésima. Ausente cuenta como cero: se teclea de a poco."""
    bruto = Decimal("0") if valor is None or valor == "" else Decimal(str(valor))
    return bruto.quantize(_MILESIMA, rounding=ROUND_HALF_UP)


def balance_mantequilla(*, kg_crema, kg_mantequilla, kg_suero=0, kg_merma=0, kg_reproceso=0):
    """
    ¿Clasifica el cierre el 100 % de la crema? Mantequilla, suero, merma y
    reproceso contra los kg de crema que entraron.

    Es la única regla: la usan `CorridaMantequilla.clean()`, `cerrar_mantequilla`
    (antes de escribir) y `revisar-cierre/` mientras se teclea. Antes el
    cliente la calculaba en milésimas y el modelo en `Decimal`; coincidían por
    casualidad de redondeo, no por construcción.
    """
    entrada = _kg(kg_crema)
    clasificado = sum(
        (_kg(valor) for valor in (kg_mantequilla, kg_suero, kg_merma, kg_reproceso)),
        Decimal("0"),
    )
    diferencia = entrada - clasificado
    # 0 o negativo es, para el balance, lo mismo que no haberla tecleado: no
    # hay mantequilla que clasificar. `errores_cierre_mantequilla` repite el
    # mismo criterio para el error de campo; aquí decide si "cuadra".
    if kg_mantequilla is None or kg_mantequilla == "" or _kg(kg_mantequilla) <= 0:
        return BalanceMantequilla(entrada, clasificado, diferencia, False, MENSAJE_FALTA_MANTEQUILLA)
    if abs(diferencia) <= TOLERANCIA_BALANCE_MANTEQUILLA_KG:
        return BalanceMantequilla(entrada, clasificado, diferencia, True, None)
    sentido = "faltan por clasificar" if diferencia > 0 else "exceden la entrada"
    return BalanceMantequilla(
        entrada, clasificado, diferencia, False,
        f"El cierre debe clasificar el 100% de la crema: {abs(diferencia)} kg {sentido}.",
    )


def errores_cierre_mantequilla(
    *, tiene_lote_suero, kg_mantequilla=None, kg_suero=0, kg_reproceso=0, motivo_reproceso="",
):
    """
    Las otras reglas del cierre que dependen de lo tecleado, por campo:
    mantequilla en cero o negativa, suero sin lote donde registrarlo y
    reproceso sin motivo. Las mismas para `clean()`, el cierre y
    `revisar-cierre/`, con el mismo texto.

    `kg_mantequilla` ausente (`None`/`""`) no es un error de este campo: ya lo
    dice `balance_mantequilla` en su propio mensaje, antes de teclear nada.
    Tecleado en 0 o negativo sí lo es —antes `revisar-cierre/` lo daba por
    cuadrado mientras `cerrar/` lo rechazaba (serializer y `clean()`)—, con el
    mismo mensaje que la ausencia: para el balance, cero no clasifica nada.
    """
    errores = {}
    if kg_mantequilla not in (None, "") and _kg(kg_mantequilla) <= 0:
        errores["kg_mantequilla"] = MENSAJE_FALTA_MANTEQUILLA
    if _kg(kg_suero) > 0 and not tiene_lote_suero:
        errores["kg_suero"] = MENSAJE_SUERO_SIN_LOTE
    if _kg(kg_reproceso) > 0 and not (motivo_reproceso or "").strip():
        errores["motivo_reproceso"] = MENSAJE_REPROCESO_SIN_MOTIVO
    return errores


# Cómo se nombra una corrida de descremado en el puesto y en su historial:
# `(valor, etiqueta, estado de la corrida, estados de la ejecución o None)`,
# y gana la primera fila que coincide. Una sola tabla para la columna
# «Situación», el catálogo del filtro y el filtro mismo
# (`procesos.servicios.condicion_situacion_descremacion`): con dos, el
# filtro ofrecía «En curso» y la columna decía «En la descremadora», y
# «Cerrada» devolvía filas que la columna llamaba «Esperando Calidad».
SITUACIONES_DESCREMACION = (
    ("preparada", "Preparada", "borrador", frozenset({"borrador", "preparacion"})),
    ("en_curso", "En la descremadora", "en_curso", None),
    ("esperando_calidad", "Esperando Calidad", "cerrada", frozenset({"pendiente_control"})),
    ("terminada", "Terminada", "cerrada", None),
    ("anulada", "Anulada", "anulada", None),
    # Una corrida en borrador cuya ejecución ya no está en preparación: las
    # heredadas del modal anterior y los huérfanos.
    ("borrador", "Borrador", "borrador", None),
)


def situacion_descremacion(estado: str, estado_ejecucion: str) -> tuple[str, str]:
    """`(valor, etiqueta)` de la situación de una corrida (`SITUACIONES_DESCREMACION`)."""
    for valor, etiqueta, estado_corrida, estados_ejecucion in SITUACIONES_DESCREMACION:
        if estado == estado_corrida and (
            estados_ejecucion is None or estado_ejecucion in estados_ejecucion
        ):
            return valor, etiqueta
    return estado, estado
