"""Reglas puras de inventario: sin ORM, testeables sin base."""
from datetime import date


def prefijo_numero_despacho(fecha: date) -> str:
    """
    Lo que comparten todos los despachos de un día: `DE6267-`.

    DE + último dígito del año + día juliano con tres cifras, igual que el vale
    (`VE…`) y el lote (`CCAA…`): quien ya lee uno lee los tres.
    """
    return f"DE{fecha.year % 10}{fecha.timetuple().tm_yday:03d}-"


def generar_numero_despacho(fecha: date, correlativo: int) -> str:
    """
    El número de una hoja de carga: `DE6267-01`.

    El correlativo va siempre, desde `-01`. Función pura: arma el texto y
    **no garantiza unicidad**; la garantiza la base (`despacho_numero_sucursal`).
    """
    return f"{prefijo_numero_despacho(fecha)}{correlativo:02d}"


def correlativo_de_numero(numero: str, prefijo: str) -> int | None:
    """
    El correlativo de un número con ese prefijo, o `None` si no tiene esa forma.

    `None` y no una excepción: hay despachos con números tecleados antes de esta
    regla (`D-1`), y ninguno debe romper el cálculo del siguiente.
    """
    if not numero or not numero.startswith(prefijo):
        return None
    resto = numero[len(prefijo):]
    return int(resto) if resto.isdigit() else None
