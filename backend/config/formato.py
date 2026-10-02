"""
Formato chileno de cantidades para textos que arma el backend.

Una sola implementación para todas las apps: dos copias divergen, y lo primero
que divergen son los separadores — justo lo que hace que «1.500» se lea mil
quinientos y no uno y medio.
"""
from decimal import Decimal


def formato_cantidad(
    valor: Decimal | float | int | str, decimales: int = 3, fijos: bool = False,
) -> str:
    """
    Un número en formato chileno (punto de miles, coma decimal) para
    interpolar dentro de un mensaje ya armado por el backend —un motivo de
    bloqueo, un aviso—.

    `str(Decimal("1500.000"))` imprime «1500.000»: en Chile eso se lee mil
    quinientos con tres decimales en el mejor caso, y «8000.00 L» como ocho mil
    coma cero. Una cantidad que la pantalla muestra **sola**, sin texto
    alrededor, no usa esto: pasa por `cantidad()` en
    `frontend/src/services/formato.ts`, que es donde vive esa regla para todo
    lo que el backend entrega como dato (no como texto).

    Por omisión recorta los ceros decimales que sobran (13.000 → «13»). Con
    `fijos=True` los conserva: un RC a 4 decimales que se recorta a «0,201»
    pierde justo la cifra con la que se comparó contra la tolerancia.
    """
    numero = Decimal(str(valor))
    entero, _, parte_decimal = f"{numero:,.{decimales}f}".partition(".")
    if not fijos:
        parte_decimal = parte_decimal.rstrip("0")
    # Python separa miles con coma y decimales con punto; en Chile es al
    # revés. Se arma por partes en vez de intercambiar los dos símbolos a la
    # vez: una traducción simultánea no encadena, así que la coma de miles
    # recién puesta nunca se volvería a convertir en punto.
    entero = entero.replace(",", ".")
    return f"{entero},{parte_decimal}" if parte_decimal else entero
