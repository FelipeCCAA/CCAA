"""Salida de planillas: el texto de planta nunca se ejecuta como fórmula."""

# Tope de trabajo síncrono; se verifica con 1000 recepciones y cuatro módulos
# por recepción en el ensayo OP-07. No es una tolerancia ni una cuota de planta.
MAX_RECEPCIONES_REPORTE = 1000


def texto_csv(valor):
    """CSV no tiene tipos: neutralizar sólo columnas textuales, no cantidades."""
    if isinstance(valor, str) and (
        valor.startswith(("\t", "\r", "\n"))
        or valor.lstrip(" \t\r\n\v\f").startswith(("=", "+", "-", "@"))
    ):
        return "'" + valor
    return valor


def agregar_fila_texto_literal(hoja, valores):
    """Conserva ceros iniciales y cantidades decimales textuales sin fórmulas."""
    from openpyxl.cell import WriteOnlyCell

    fila = []
    for valor in valores:
        if isinstance(valor, str):
            celda = WriteOnlyCell(hoja, value=valor)
            celda.data_type = "s"
            fila.append(celda)
        else:
            fila.append(valor)
    hoja.append(fila)
