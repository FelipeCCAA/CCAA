from dataclasses import dataclass
from decimal import Decimal


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
