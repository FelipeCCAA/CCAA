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
