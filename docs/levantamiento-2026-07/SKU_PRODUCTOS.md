# SKU de productos — estructura y generador

> Contexto para Claude Code. Define la **estructura del SKU** de productos de CCAA a partir del
> archivo `Recetas_Cód. Producto.xlsx` (hoja «Código de Producto») y cómo construir un
> **generador/validador de SKU** e integrarlo al modelo `maestros`.
> No confundir con el **código de lote** (`produccion/dominio.py`, POE.009.02): el SKU identifica
> un **producto** (maestro, estable); el código de lote identifica una **corrida de producción**
> (transaccional, por fecha). Son dos códigos distintos.
> **Fecha:** 2026-07-30.

---

## 1. Estructura del SKU

El SKU es un código numérico de **12 dígitos = 6 segmentos de 2 dígitos**, en este orden
(deducido y verificado contra los SKU reales del archivo; el orden **no** coincide con el de las
columnas de la planilla, que están desalineadas):

```
  NN  CL  CA  TI  FO  ME
  │   │   │   │   │   └─ Mercado
  │   │   │   │   └───── Formato
  │   │   │   └───────── Tipo
  │   │   └───────────── Categoría
  │   └───────────────── Cliente
  └───────────────────── Naturaleza (comercial)

Ej.:  010103010101  →  01·Servicio Terceros · 01·Nestlé · 03·Precondensados · 01·Entera · 01·Granel · 01·Local
      020005050301  →  02·Producto Propio · 00·s/cliente · 05·Mantequilla · 05·Sin sal · 03·Caja 20kg · 01·Local
```

## 2. Catálogos (código → valor)

**Naturaleza (comercial)** — *distinta* de `Producto.naturaleza` del modelo (que es materia_prima/intermedio/terminado):

| Cód | Valor |
|---|---|
| 01 | Servicio Terceros |
| 02 | Producto Propio |

**Cliente** *(≈ mandante)*:

| Cód | Valor |
|---|---|
| 00 | Cliente no definido *(= producto propio CCAA)* |
| 01 | Nestlé |
| 02 | Colun |
| 03 | Soprole |

**Categoría** *(01 sin uso en el archivo)*:

| Cód | Valor |  | Cód | Valor |
|---|---|---|---|---|
| 02 | Leche en Polvo | | 08 | Suero |
| 03 | Pre condensados | | 09 | Extracto de Malta |
| 04 | Crema | | 10 | Leche en Polvo Instantánea |
| 05 | Mantequilla | | 11 | Leche en Polvo c/Lecitina |
| 06 | Materiales Diversos | | 12 | Leche Fluida |
| 07 | Leche Fresca Estandarizada | | | |

**Tipo:** 01 Entera · 02 Semidescremada · 03 Descremada · 04 Con sal · 05 Sin sal · 06 Sin especificar · 07 No definido · 08 Estandarizada

**Formato:** 01 Granel · 02 Saco 25 kg · 03 Caja 20 kg

**Mercado:** 01 Local · 02 Exportación

## 3. Reglas de composición y validación

- **Naturaleza ↔ Cliente:** `Producto Propio` (02) va siempre con `Cliente no definido` (00);
  `Servicio Terceros` (01) va con un cliente real (01/02/03). El generador debe rechazar
  combinaciones fuera de esa regla (p. ej. Producto Propio + Nestlé).
- **Mercado** por defecto `01 Local` (todos los productos del archivo son locales).
- **Formato** condiciona el peso: Granel (sin peso), Saco 25 kg, Caja 20 kg.
- El SKU se compone **solo de catálogos**: el generador nunca inventa un código; si falta un valor
  de catálogo, falla en vez de improvisar.

## 4. Problemas detectados en el archivo fuente (a resolver antes de adoptarlo)

1. **El SKU no es único por producto.** 8 productos colapsan en 3 códigos porque la estructura no
   tiene segmento para ciertas variantes:
   - `010302010201` ← *Leche Entera Estándar 27% SP*, *Leche Entera c/LdS 27% SP*, *Leche Entera en Polvo Regular 25kg*
   - `010302030201` ← *Leche Descremada MH SP*, *Leche Descremada c/LdS SP*, *Leche en Polvo Descremada Regular*
   - `020003020101` ← *Precondensado SemiDescremado Rc0.201*, *P. Semidescremado ST 45% CCAA*

   La diferencia real (con/sin lecitina, «Regular» vs. estándar, Rc distinto) no está codificada.
   **Decisión pendiente:** agregar un 7.º segmento **correlativo/variante** de 2 dígitos
   (`…NNVV` → 14 dígitos) o un atributo explícito «con lecitina». Recomendado: correlativo de
   variante, para que el SKU siga siendo único aunque dos productos compartan los 6 segmentos.

2. **Dos filas mal codificadas** (categoría equivocada en el SKU del archivo):
   - *Leche Entera Estándar 28% NE 25kg* (LEP Nestlé) → SKU `0101**04**010201` codifica Categoría =
     Crema; debería ser Leche en Polvo (`02`) → `010102010201`.
   - Revisar además que *Leche Entera Instantánea 27% CN* sea Colun (`02`) y no otro cliente.

   Como el generador se construye desde los atributos, **será la fuente de verdad** y corrige estos
   casos automáticamente; conviene regenerar los SKU y no cargarlos tal cual del archivo.

3. La hoja **«Validación de productos»** marca los 17 productos como *«¿definido correctamente?» =
   False*: el catálogo aún no está validado por negocio. Confirmar antes de fijar los SKU.

## 5. Integración al modelo `maestros`

El SKU vive en el **maestro `Producto`**. Campos a agregar (ninguno existe hoy con esta semántica;
ojo: `Producto.naturaleza` del modelo es materia_prima/intermedio/terminado, **otra cosa** que la
«naturaleza comercial» del SKU):

| Segmento SKU | Campo en `Producto` | Nota |
|---|---|---|
| Naturaleza | `naturaleza_comercial` *(nuevo)* | `servicio_terceros` / `producto_propio` |
| Cliente | `mandante` *(ya existe, FK)* | mapear Mandante→código (Nestlé 01, Colun 02, Soprole 03, CCAA/propio 00) |
| Categoría | `categoria` *(nuevo)* | 11 valores; `familia` (polvo/crema/…) puede derivarse de aquí |
| Tipo | `tipo` *(nuevo)* | entera/semidesc/descremada/con-sal/sin-sal/… |
| Formato | `formato` *(nuevo)* | granel/saco-25/caja-20 |
| Mercado | `mercado` *(nuevo, def. local)* | local/exportación |
| — | `sku` *(nuevo)* | derivado; se recomienda **no** teclearlo sino generarlo |
| — | `variante` *(nuevo, opcional)* | correlativo para unicidad (ver §4.1) |

El `Mandante` necesita un `codigo_cliente` (00/01/02/03) para el segmento Cliente. Añadirlo al
maestro `Mandante`.

## 6. Borrador del generador (para `maestros/`)

Función pura, en línea con `produccion/dominio.py` (`generar_codigo_lote`). Catálogos en un módulo
aparte (`maestros/catalogos_sku.py`), como `maestros/catalogos.py`.

```python
# --- maestros/catalogos_sku.py ---
"""Catálogos del SKU de producto (Recetas_Cód. Producto.xlsx, hoja 'Código de Producto')."""

NATURALEZA = {"servicio_terceros": "01", "producto_propio": "02"}
CLIENTE    = {"no_definido": "00", "nestle": "01", "colun": "02", "soprole": "03"}
CATEGORIA  = {
    "leche_polvo": "02", "precondensado": "03", "crema": "04", "mantequilla": "05",
    "materiales_diversos": "06", "leche_fresca_est": "07", "suero": "08",
    "extracto_malta": "09", "lp_instantanea": "10", "lp_con_lecitina": "11", "leche_fluida": "12",
}
TIPO = {
    "entera": "01", "semidescremada": "02", "descremada": "03", "con_sal": "04",
    "sin_sal": "05", "sin_especificar": "06", "no_definido": "07", "estandarizada": "08",
}
FORMATO = {"granel": "01", "saco_25kg": "02", "caja_20kg": "03"}
MERCADO = {"local": "01", "exportacion": "02"}

# Naturaleza comercial ↔ cliente permitido
CLIENTES_POR_NATURALEZA = {
    "servicio_terceros": {"nestle", "colun", "soprole"},
    "producto_propio": {"no_definido"},
}
```

```python
# --- añadir a maestros/dominio.py (nuevo o existente) ---
from maestros.catalogos_sku import (
    NATURALEZA, CLIENTE, CATEGORIA, TIPO, FORMATO, MERCADO, CLIENTES_POR_NATURALEZA,
)

_SEGMENTOS = [
    ("naturaleza", NATURALEZA),
    ("cliente", CLIENTE),
    ("categoria", CATEGORIA),
    ("tipo", TIPO),
    ("formato", FORMATO),
    ("mercado", MERCADO),
]


def generar_sku(naturaleza, cliente, categoria, tipo, formato, mercado="local", variante=None):
    """
    Compone el SKU de un producto: 12 dígitos = Naturaleza+Cliente+Categoría+Tipo+Formato+Mercado.
    Cada argumento es una CLAVE de catálogo (p. ej. categoria="crema"), no el código.

    Reglas (Recetas_Cód. Producto.xlsx):
      - 'producto_propio' exige cliente 'no_definido'; 'servicio_terceros' exige cliente real.
      - `variante` (opcional, 2 dígitos) se agrega al final para garantizar unicidad cuando dos
        productos comparten los 6 segmentos (ver SKU_PRODUCTOS.md §4.1).
    """
    if cliente not in CLIENTES_POR_NATURALEZA.get(naturaleza, set()):
        raise ValueError(
            f"Cliente '{cliente}' no es válido para naturaleza '{naturaleza}'."
        )

    valores = {"naturaleza": naturaleza, "cliente": cliente, "categoria": categoria,
               "tipo": tipo, "formato": formato, "mercado": mercado}
    partes = []
    for clave, catalogo in _SEGMENTOS:
        v = valores[clave]
        if v not in catalogo:
            raise ValueError(f"Valor '{v}' desconocido para el segmento '{clave}'.")
        partes.append(catalogo[v])

    sku = "".join(partes)
    if variante is not None:
        sku += f"{int(variante):02d}"
    return sku


def sku_valido(sku):
    """Comprueba que un SKU respeta la estructura (12 dígitos, o 14 con variante,
    y cada segmento existe en su catálogo)."""
    if not sku or not sku.isdigit() or len(sku) not in (12, 14):
        return False
    seg = [sku[i:i+2] for i in range(0, 12, 2)]
    codigos = [set(c.values()) for _, c in _SEGMENTOS]
    return all(s in cod for s, cod in zip(seg, codigos))


def describir_sku(sku):
    """Devuelve un dict {segmento: valor legible} para mostrar/depurar un SKU."""
    if not sku_valido(sku):
        return None
    inv = [{v: k for k, v in c.items()} for _, c in _SEGMENTOS]
    seg = [sku[i:i+2] for i in range(0, 12, 2)]
    return {nombre: inv[i].get(seg[i]) for i, (nombre, _) in enumerate(_SEGMENTOS)}
```

Tests (`maestros/tests_dominio_sku.py`), con ejemplos verificados contra el archivo:

```python
from django.test import SimpleTestCase
from maestros.dominio import generar_sku, sku_valido, describir_sku


class GenerarSku(SimpleTestCase):
    def test_ejemplos_del_archivo(self):
        self.assertEqual(
            generar_sku("servicio_terceros", "nestle", "precondensado", "entera", "granel", "local"),
            "010103010101")
        self.assertEqual(
            generar_sku("producto_propio", "no_definido", "mantequilla", "sin_sal", "caja_20kg", "local"),
            "020005050301")
        self.assertEqual(
            generar_sku("servicio_terceros", "soprole", "leche_polvo", "entera", "saco_25kg"),
            "010302010201")

    def test_regla_naturaleza_cliente(self):
        with self.assertRaises(ValueError):
            generar_sku("producto_propio", "nestle", "crema", "entera", "granel")

    def test_valor_desconocido_falla(self):
        with self.assertRaises(ValueError):
            generar_sku("servicio_terceros", "nestle", "queso", "entera", "granel")

    def test_variante_para_unicidad(self):
        self.assertEqual(
            generar_sku("servicio_terceros", "soprole", "leche_polvo", "entera", "saco_25kg", variante=1),
            "01030201020101")

    def test_validador_y_descripcion(self):
        self.assertTrue(sku_valido("010103010101"))
        self.assertFalse(sku_valido("0101"))
        self.assertEqual(describir_sku("010103010101")["categoria"], "precondensado")
```

## 7. Bonus: el archivo también trae las recetas (BOM)

Las hojas «Recetas (detalle)», «Resumen por receta» y «Diccionario» son la **lista de materiales
por 100 kg** de cada producto (Sólidos Grasos/No Grasos, Saco de papel, Bolsa Film CE, Lecitina,
Caja cartón, Bolsa PEBD, Sal Fina) y ligan cada código de receta (5001, 5002, …) con el nombre de
producción. Eso alimenta el modelo **`Receta`** (multinivel) que está pendiente de portar del
prototipo (`prototipo/MODELO_DATOS.md` §2.7). Es material para una tarea aparte; aquí solo se deja
señalado porque vive en el mismo archivo.

## 8. Resumen para Claude Code

1. Agregar catálogos SKU (`maestros/catalogos_sku.py`) y `generar_sku`/`sku_valido`/`describir_sku`
   en `maestros/dominio.py`, con tests.
2. Ampliar `Producto` con `naturaleza_comercial`, `categoria`, `tipo`, `formato`, `mercado`, `sku`
   (y `variante` si se adopta el correlativo); ampliar `Mandante` con `codigo_cliente`.
3. Decidir con negocio: (a) el 7.º segmento de variante para unicidad; (b) corregir las 2 filas
   mal codificadas; (c) validar los 17 productos marcados como *no definidos*.
4. Regenerar los SKU desde los atributos (no cargarlos crudos del Excel).
