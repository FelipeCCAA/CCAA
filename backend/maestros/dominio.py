"""
Reglas de los maestros. Hoy: el codificador de SKU de producto.

Funciones puras: no tocan la base, no importan modelos y no dependen de
Django. Misma línea que `produccion/dominio.py`.

El SKU se compone **solo de catálogos**. Si un atributo no está en su
catálogo, falla en vez de improvisar: un SKU con un segmento inventado se ve
igual de válido que uno correcto, y termina impreso en un saco.
"""

from __future__ import annotations

from .catalogos_sku import (
    CLIENTES_POR_NATURALEZA,
    PESO_POR_FORMATO,
    SEGMENTOS,
)


class SkuInvalido(ValueError):
    """El SKU no se puede componer con lo que se entregó."""


def generar_sku(
    naturaleza: str,
    cliente: str,
    categoria: str,
    tipo: str,
    formato: str,
    mercado: str = "local",
    variante: int | None = None,
) -> str:
    """
    Compone el SKU de un producto: 12 dígitos, o 14 si lleva variante.

    Cada argumento es una **clave** de catálogo (`categoria="crema"`), no el
    código. Pasar el código directo saltaría la validación, que es justo lo
    que este módulo existe para hacer.

    Reglas:

    - `producto_propio` exige cliente `no_definido`, y `servicio_terceros`
      exige un cliente real. No es formalidad: el segmento de cliente es lo
      que dice de quién es el producto que se está fabricando, y un producto
      propio con cliente —o uno de terceros sin él— describe algo que no
      existe.
    - `variante` es el correlativo de dos dígitos para los casos en que dos
      productos comparten los seis segmentos (`SKU_PRODUCTOS.md` §4.1). Es
      opcional a propósito: mientras negocio no decida adoptarlo, los SKU se
      componen de 12 dígitos como en el archivo.

    Levanta `SkuInvalido` —que es un `ValueError`— con el motivo.
    """
    permitidos = CLIENTES_POR_NATURALEZA.get(naturaleza)

    if permitidos is None:
        raise SkuInvalido(f"Naturaleza comercial desconocida: {naturaleza!r}.")

    if cliente not in permitidos:
        raise SkuInvalido(
            f"El cliente {cliente!r} no corresponde a la naturaleza "
            f"{naturaleza!r}. Admite: {', '.join(sorted(permitidos))}."
        )

    valores = {
        "naturaleza": naturaleza,
        "cliente": cliente,
        "categoria": categoria,
        "tipo": tipo,
        "formato": formato,
        "mercado": mercado,
    }

    partes = []

    for segmento, catalogo in SEGMENTOS:
        valor = valores[segmento]

        if valor not in catalogo:
            raise SkuInvalido(
                f"El segmento {segmento!r} no admite {valor!r}. "
                f"Valores: {', '.join(sorted(catalogo))}."
            )

        partes.append(catalogo[valor])

    sku = "".join(partes)

    if variante is None:
        return sku

    if not 0 <= int(variante) <= 99:
        raise SkuInvalido(
            f"La variante debe caber en dos dígitos; llegó {variante!r}."
        )

    return f"{sku}{int(variante):02d}"


def sku_valido(sku: str | None) -> bool:
    """
    ¿El SKU respeta la estructura y sus catálogos?

    Comprueba además la regla naturaleza↔cliente. Sin eso, un código que
    `generar_sku` se niega a componer —producto propio con cliente Nestlé—
    pasaría por válido, y el validador diría que está bien algo que el
    generador considera imposible.

    Como `codigo_lote_valido`, esto **avisa**: sirve para marcar en pantalla
    un SKU con forma rara, no para impedir que se guarde un maestro que ya
    existe con otro criterio.
    """
    if not sku or not sku.isdigit() or len(sku) not in (12, 14):
        return False

    descripcion = _descomponer(sku)

    if descripcion is None:
        return False

    permitidos = CLIENTES_POR_NATURALEZA.get(descripcion["naturaleza"], set())

    return descripcion["cliente"] in permitidos


def describir_sku(sku: str | None) -> dict[str, str] | None:
    """
    Traduce un SKU a los valores que codifica.

    Devuelve `None` si no se puede descomponer: media descripción sería peor
    que ninguna, porque se leería como una lectura completa.
    """
    if not sku_valido(sku):
        return None

    descripcion = _descomponer(sku)

    if len(sku) == 14:
        descripcion["variante"] = sku[12:]

    return descripcion


def peso_del_formato(formato: str) -> int | None:
    """
    Kilos que pesa un bulto de ese formato. `None` para granel.

    Es `None` y no `0` porque el granel no pesa cero: se mide de otra manera.
    """
    return PESO_POR_FORMATO.get(formato)


def _descomponer(sku: str) -> dict[str, str] | None:
    """Los seis segmentos a sus claves de catálogo, o None si alguno no está."""
    descripcion = {}

    for i, (segmento, catalogo) in enumerate(SEGMENTOS):
        codigo = sku[i * 2 : i * 2 + 2]
        inverso = {v: k for k, v in catalogo.items()}

        if codigo not in inverso:
            return None

        descripcion[segmento] = inverso[codigo]

    return descripcion
