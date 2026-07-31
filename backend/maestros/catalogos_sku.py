"""
Catálogos del SKU de producto.

Fuente: `docs/levantamiento-2026-07/Recetas_Cod_Producto.xlsx`, hoja «Código de
Producto», documentados en `SKU_PRODUCTOS.md`.

El SKU son 12 dígitos en 6 segmentos de 2:

    NN CL CA TI FO ME
    │  │  │  │  │  └─ Mercado
    │  │  │  │  └──── Formato
    │  │  │  └─────── Tipo
    │  │  └────────── Categoría
    │  └───────────── Cliente
    └──────────────── Naturaleza comercial

El orden **no** es el de las columnas de la planilla, que están desalineadas
respecto de los SKU que ella misma contiene. Se verificó componiendo los 24
SKU del archivo desde sus columnas `Cód.`; la prueba de regresión los rehace
todos, así que si alguien reordena los segmentos aquí, falla.

No confundir con el **código de lote** (`produccion/dominio.py`): el SKU
identifica un producto —maestro, estable— y el código de lote identifica una
corrida de producción.
"""

# Naturaleza *comercial*. Distinta de `Producto.naturaleza` del modelo, que
# dice dónde está el producto en la cadena (materia prima / intermedio /
# terminado). Comparten nombre y no significan lo mismo.
NATURALEZA = {
    "servicio_terceros": "01",
    "producto_propio": "02",
}

CLIENTE = {
    "no_definido": "00",  # producto propio CCAA
    "nestle": "01",
    "colun": "02",
    "soprole": "03",
}

# El 01 no se usa en el archivo. Se deja sin asignar en vez de reciclarlo:
# ocuparlo ahora chocaría con lo que sea que signifique en los códigos que ya
# están impresos.
CATEGORIA = {
    "leche_polvo": "02",
    "precondensado": "03",
    "crema": "04",
    "mantequilla": "05",
    "materiales_diversos": "06",
    "leche_fresca_est": "07",
    "suero": "08",
    "extracto_malta": "09",
    "lp_instantanea": "10",
    "lp_con_lecitina": "11",
    "leche_fluida": "12",
}

TIPO = {
    "entera": "01",
    "semidescremada": "02",
    "descremada": "03",
    "con_sal": "04",
    "sin_sal": "05",
    "sin_especificar": "06",
    "no_definido": "07",
    "estandarizada": "08",
}

FORMATO = {
    "granel": "01",
    "saco_25kg": "02",
    "caja_20kg": "03",
}

MERCADO = {
    "local": "01",
    "exportacion": "02",
}

# Qué cliente admite cada naturaleza comercial. Un producto propio es de CCAA
# y por eso no lleva cliente; uno de servicio a terceros es de alguien, y sin
# ese alguien el SKU no dice de quién es el producto que se está fabricando.
CLIENTES_POR_NATURALEZA = {
    "servicio_terceros": {"nestle", "colun", "soprole"},
    "producto_propio": {"no_definido"},
}

# Kilos por formato. Granel no tiene: se mide a granel, valga la redundancia.
PESO_POR_FORMATO = {
    "granel": None,
    "saco_25kg": 25,
    "caja_20kg": 20,
}

# El orden manda: es la estructura del SKU.
SEGMENTOS = (
    ("naturaleza", NATURALEZA),
    ("cliente", CLIENTE),
    ("categoria", CATEGORIA),
    ("tipo", TIPO),
    ("formato", FORMATO),
    ("mercado", MERCADO),
)
