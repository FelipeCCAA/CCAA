# Estandarización — código de vale asignado por el sistema

**Fecha:** 2026-09-23
**Pedido:** el código del vale de estandarización se genera solo; el operador ya no lo teclea.

---

## 1. Qué pasa hoy

El operador escribe el código del vale en el formulario («Código de vale»). Mientras el
vale es borrador lleva un identificador provisional, `BORRADOR-xxxxxxxx`; al confirmar,
`ValeEstandarizacion.confirmar()` copia lo tecleado (`codigo_propuesto`) a `codigo`.

Lo que dejó eso en la base local, en vales ya liberados:

| Código | De dónde sale |
|---|---|
| `VE-316256` | Las pruebas E2E, que inventan un número al azar |
| `VE-20260901-01` | Alguien siguiendo una convención de fecha, a mano |
| `jkjfd` | Un código tecleado para salir del paso |

Tres formas para el mismo documento, y ninguna garantizada. Un campo libre invita a
eso: el sistema tiene todo lo necesario para componer el código y aun así se lo pide
a la persona.

**El vale nace por dos caminos**, y los dos aceptan hoy un código tecleado:

1. **Borrador:** `crear-borrador` → autoguardado → `confirmar-borrador`.
2. **Creación directa:** `POST /api/estandarizacion/vales/`, que crea el vale ya
   `calculado` con el `codigo` que manda el cliente (`views.py`, `perform_create`).

En el serializer, `codigo` y `codigo_propuesto` son **escribibles**. Cambiar solo la
confirmación dejaría abierto el segundo camino.

---

## 2. Decisiones

Tomadas con el usuario el 2026-09-23.

| Decisión | Elegido | Descartado |
|---|---|---|
| Formato | `VE` + año + día juliano + correlativo: **`VE6266-01`** | Fecha completa (`VE-20260923-01`); correlativo global (`VE-000124`) |
| ¿Editable? | **No.** El sistema lo asigna y el campo sale del formulario | Sugerido y editable, como el lote |
| ¿Cuándo? | **Al confirmar** | Al abrir el vale |

**Por qué el mismo formato que el lote.** El código de lote es
`CCAA` + año + juliano + sigla + correlativo (`CCAA6266E1-01`, `produccion/dominio.py`).
Quien ya lee el día juliano en los lotes lo lee igual en el vale, y los dos documentos
del mismo día quedan visiblemente emparentados.

**Por qué fijo, cuando el lote es editable.** El código de lote se *sugiere* porque hay
que poder registrar el histórico del POE anterior, con códigos que no siguen el patrón.
El vale no arrastra ese compromiso: el sistema parte en blanco y no se importan vales
históricos. Sin un caso que obligue a teclearlo, un campo editable solo conserva la
puerta por la que entró `jkjfd`.

**Por qué al confirmar.** Un borrador descartado nunca llega a tener número, así que los
correlativos del día quedan seguidos. Asignarlo al abrir quemaría un número por cada
borrador abandonado.

---

## 3. La regla

### 3.1 Formato

```
VE + último dígito del año + día juliano (3 dígitos) + "-" + correlativo (2 o más dígitos)

VE6266-01    primer vale del 23-09-2026
VE6266-02    segundo vale del mismo día
VE6267-01    primer vale del 24-09-2026
VE6001-01    primer vale del 01-01-2026
VE6266-100   centésimo vale del día
```

El correlativo va **siempre**, desde `-01` — mismo criterio que `generar_codigo_lote`:
ponerlo solo a partir del segundo deja dos formas conviviendo.

### 3.2 El día

Sale de **`vale.fecha`**, la fecha del documento, no del reloj al confirmar. Un vale
fechado ayer y confirmado hoy lleva el día de ayer, que es el día del proceso.
`fecha` ya es obligatoria para confirmar.

### 3.3 El correlativo

**El máximo correlativo existente con ese prefijo, más uno.** No un conteo:

- Un conteo repetiría un número si alguna vez faltara uno del medio. El máximo no.
- Los vales **anulados después de confirmarse** conservan su número y cuentan para el
  máximo: un número asignado no se reutiliza nunca.
- Los **borradores** no tienen número (su `codigo` es `BORRADOR-…`), así que no cuentan.
- Los **códigos históricos** con otra forma (`VE-316256`, `VE-20260901-01`, `jkjfd`) no
  empiezan por el prefijo del día (`VE6266-`), así que no entran en el cálculo.

### 3.4 Dos confirmaciones a la vez

Si dos vales del mismo día se confirman simultáneamente, los dos pueden calcular el mismo
número. La restricción `unique` de `codigo` rechaza al segundo. `asignar_codigo()`
**reintenta** recalculando el siguiente número, cada intento dentro de su propio savepoint
(`transaction.atomic()` anidado: sin él, el `IntegrityError` deja inutilizable la
transacción de la confirmación). **Hasta 5 intentos**; agotados, se devuelve el motivo
«No se pudo asignar un código de vale; vuelve a confirmar» en vez de un 500. Cinco
vales del mismo día confirmándose en el mismo instante no ocurren en una planta.

Es el criterio que ya está escrito en `generar_codigo_lote`: *«no garantiza unicidad; la
unicidad la garantiza la base»*. No se agrega un bloqueo aparte.

---

## 4. Dónde cambia

### 4.1 Dominio — `estandarizacion/dominio.py`

```python
def generar_codigo_vale(fecha: date, correlativo: int) -> str
def prefijo_codigo_vale(fecha: date) -> str          # "VE6266-"
def correlativo_de_codigo(codigo: str, prefijo: str) -> int | None
```

Funciones puras: arman y leen texto, sin ORM. `correlativo_de_codigo` devuelve `None`
para lo que no tiene la forma, de modo que un código raro no rompe el máximo.

### 4.2 Modelo — `estandarizacion/models.py`

- **`asignar_codigo()`**: calcula el siguiente correlativo sobre la base, guarda, y
  reintenta ante la colisión (§3.4). Es el **único** lugar que escribe un código
  definitivo.
- **`confirmar()`** llama a `asignar_codigo()` en lugar de copiar `codigo_propuesto`.
- **`motivos_para_confirmar()`** pierde el chequeo «El código de vale ya existe»: ya no
  hay código tecleado que pueda repetirse.
- **`CAMPOS_OBLIGATORIOS_AL_CONFIRMAR`** pierde `codigo_propuesto`.
- **Se elimina el campo `codigo_propuesto`.**

### 4.3 Migración

Un `RemoveField` de `codigo_propuesto`. Medido el 2026-09-23 sobre la base local:
**0 borradores abiertos**, así que no se pierde ningún código tecleado. Solo esquema,
sin migración de datos. Los códigos existentes no se reescriben: son registros
auditados y ya referenciados por sus lotes.

### 4.4 Serializer y vistas

- `codigo` pasa a **solo lectura**; `codigo_propuesto` sale de `fields`.
- `perform_create` (creación directa) llama a `asignar_codigo()`.
- Un cliente antiguo que todavía mande `codigo` **se ignora, no se rechaza** — el mismo
  criterio que CLAUDE.md fija para la sucursal: el backend no falla por un campo que ya
  no decide nada.

### 4.5 Frontend

- `pages/Estandarizacion/FormularioVale.tsx`: sale el campo «Código de vale». En su
  lugar, texto fijo:
  - borrador: *«Código: se asignará al confirmar»*;
  - confirmado: el código asignado, que viene en la respuesta de `confirmar-borrador`.
- Sale `codigo` del estado del formulario y del armado del payload.
- `services/estandarizacion.service.ts`: sale `codigo_propuesto` de los tipos.

### 4.6 Documentación

Una entrada en «Decisiones vigentes» de `CLAUDE.md`, junto a la del código de lote:
formato, que no es editable y por qué, y el contraste con el lote.

---

## 5. Pruebas

### 5.1 Dominio (sin base) — `estandarizacion/tests_dominio.py`

- `generar_codigo_vale(2026-09-23, 1)` → `VE6266-01`.
- 1 de enero → `VE6001-01` (juliano con ceros).
- Año por su último dígito: 5 de mayo de 2030 → `VE0125-01`.
- Correlativo 100 → `-100`.
- `correlativo_de_codigo` lee `VE6266-07` → 7, y devuelve `None` para `VE-316256`,
  `jkjfd` y `BORRADOR-2D9928CC`.

### 5.2 Modelo y API

- El primer vale confirmado del día → `-01`; el segundo → `-02`.
- El día sale de `fecha`, no de hoy: un vale fechado ayer toma el prefijo de ayer.
- Un borrador **descartado** no consume número: el siguiente confirmado sigue la serie.
- Un vale **anulado** tras confirmarse conserva su código, y el siguiente no lo reutiliza.
- Un código histórico con otra forma no altera el correlativo.
- **Colisión:** se fuerza el cálculo a proponer un número ya ocupado; el vale queda con
  el siguiente libre, no con un error 500.
- **Creación directa** con `codigo` en el cuerpo: se ignora y se asigna el generado.
- Un `PATCH` con `codigo` no lo cambia.

### 5.3 Pruebas existentes a ajustar

- `estandarizacion/tests_borrador.py` — 4 usos de `codigo_propuesto`.
- `produccion/tests_borrador.py` — 1 uso.

### 5.4 E2E — la prueba de aceptación

`frontend/e2e/circuito-polvo.spec.ts` teclea «Código de vale» (línea 335) y luego busca
el vale por ese código (línea 415). Deja de teclearlo y **lee el código de la respuesta
de `confirmar-borrador`**.

La cadena `circuito → evaporacion → flujo-polvo`, en verde desde el 2026-09-23, tiene
que seguir en verde de punta a punta.

---

## 6. Fuera de alcance

- **`BORRADOR-xxxxxxxx`** se queda como está. Es el identificador de un documento que
  todavía no existe para la planta; cambiarlo no es parte del pedido.
- **Reescribir los códigos históricos.** No se tocan (§4.3).
- **El código de lote** sigue sugerido y editable; esta decisión no lo alcanza.
