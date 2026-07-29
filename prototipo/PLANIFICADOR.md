# Planificador de Producción — especificación para implementar

> **Para quien lo implementa (Claude Code / VS Code):** este documento describe un módulo
> nuevo, el **Planificador**, para la app *Gestión Productiva · Planta CCAA*
> (`App Gestión Productiva CCAA/`). Reproduce lo que hoy se hace a mano en el Excel
> `Programa Campos Australes W7.xlsx`. **Respeta la arquitectura existente descrita en
> `MODELO_DATOS.md` y `README.md`**: mismas capas, mismos espacios de nombre, sin módulos ES,
> repositorio asíncrono, formularios generados desde el esquema. No inventes una arquitectura
> paralela: el Planificador es un módulo más, hermano de Producción y Recepción.

---

## 0. TL;DR de lo que hay que construir

Una vista semanal de **programación de planta** con dos bloques acoplados:

1. **Programa horario (carta tipo Gantt).** Una grilla `equipos × horas de la semana`. Cada
   celda/bloque dice qué se produce (código de producto) o qué pasa en el equipo (aseo,
   mantención, preparación, etc.), con color.
2. **Balance de leche.** Una tabla `día × concepto` que parte del stock, suma las recepciones
   y **resta el consumo que se deduce automáticamente del programa horario**, arrastrando el
   stock de un día al siguiente.

La clave del archivo original —y lo que hay que preservar— es que **los dos bloques están
ligados**: el programa horario *genera* el consumo de leche del balance. No son dos tablas
independientes. Ese acoplamiento es la razón de ser de la herramienta.

Adicionalmente, una **calculadora de tiempos de corrida** (hoja `Base`): dado un objetivo de
kilos y la relación de concentración, estima cuántas horas ocupa el equipo. Es una ayuda de
apoyo, opcional en una primera entrega.

---

## 1. De dónde sale esto: anatomía del Excel `Programa Campos Australes W7.xlsx`

El libro tiene 7 hojas. Solo importan tres conceptos:

| Hoja | Rol | Se traduce a |
|---|---|---|
| `W6`, `W7`, `W8` | Una hoja por semana. `W7` = semana del **lun 9 al sáb 14 de feb 2026**. | Cada una es una **`semanaPlan`** con sus bloques y su balance. |
| `Vacio`, `Vacio (3)` | Plantillas en blanco que se clonan para abrir una semana nueva. | La acción **«nueva semana»** del módulo. |
| `BD` | Datos maestros: catálogo de códigos de producto (con su rendimiento en L/h) y la leyenda de estados de equipo. | Maestro **`codigoProduccion`** + catálogo **`estadosEquipo`**. |
| `Base` | Motor de cálculo de tiempos (flujo, RC, ST, factor 0,13122). | Dominio **`Planificador.horasCorrida()`** (calculadora auxiliar). |

### 1.1 Estructura de una hoja semanal (`W7`)

Dos bloques apilados verticalmente sobre el mismo eje de días.

**Bloque superior — Balance de leche (filas 2–18).** Columnas = días (Lunes…Sábado). Filas:

```
Fecha del día
STOCK 8 AM              (arrastrado del día anterior)
RECEPCIÓN CCAA
RECEPCIÓN NESTLE
RECEPCIÓN P. UNION
TOTAL DISPONIBLE       = stock + recepciones
CONSUMO:
  · Prec. Nestle       ┐
  · Prec. CCAA         │  cada uno se DEDUCE del programa horario
  · Secado CCAA        │  (ver §4.1). No se teclean a mano.
  · Secado Nestle      │
  · Secado Colun       │
  · Trasvasije         ┘
TOTAL CONSUMO          = suma de consumos
STOCK CCAA / NESTLE / P.UNION   (saldo por origen, arrastrado)
STOCK 8 AM (día siguiente) = total disponible − total consumo
```

Todo en **litros**. En `W7` la semana parte con 193.000 L de stock de fin de semana y cierra
con ~2.201.600 L de consumo total.

**Bloque inferior — Programa horario (filas 22–49).** La fila 22 es el eje de **horas (0–24)**
repetido por cada día; cada día ocupa 24 casillas horarias. Las filas son las líneas y equipos:

| Fila del Excel | Equipo | Etapa | ¿Consume leche cruda? |
|---|---|---|---|
| Carga de Precondensado | Preparación de precondensado | Apronte | No (secuencia de cargas) |
| Scheffers 2 | Evaporador SH2 | **Evaporación** | **Sí** → alimenta el balance |
| Scheffers 3 | Evaporador SH3 | **Evaporación** | **Sí** → alimenta el balance |
| VEB | Evaporador VEB | **Evaporación** | **Sí** → alimenta el balance |
| Línea 1 | Secado E1 | Secado | No (consume precondensado, no leche) |
| Línea 2 | Secado E2 | Secado | No (consume precondensado, no leche) |
| Línea Mantequilla | Línea de mantequilla | Batido | No (consume **crema**, ver §3.6) |
| Crema disponible (Ton) | Crema en estanque | — | Saldo en toneladas |
| Observaciones | Notas del turno | — | Texto libre |

> **Mapeo equipo↔proceso — resuelto desde las fórmulas del Excel (no es un supuesto).** Las
> fórmulas `COUNTIF` que calculan el consumo del balance suman **únicamente las tres filas de
> evaporadores** (`Scheffers 2`, `Scheffers 3`, `VEB`). Físicamente calza: el evaporador toma
> **leche cruda** y produce precondensado; las Líneas 1/2 **secan ese precondensado** (no vuelven
> a consumir leche cruda) y la Línea Mantequilla consume **crema**. Consecuencia para el modelo:
>
> - El balance de leche se alimenta **solo de los bloques cuyo `equipo` es un evaporador**. Las
>   líneas de secado y mantequilla se programan igual en la grilla, pero **no** entran en el
>   cálculo de consumo de leche (evitan el doble conteo: un mismo código como `LNSH2` aparece
>   tanto en el evaporador como en la línea, pero solo cuenta en el evaporador).
> - Dentro de esas filas, la **categoría** de consumo (precondensado vs. secado, Nestlé/CCAA/Colun)
>   la decide el **código**, no el equipo (ver §4.1).
> - Los códigos de estado vienen en el Excel en mayúscula y minúscula indistintamente
>   (`A`/`a`, `X`/`x`, `P`/`p`): **normaliza a mayúscula** al leer/validar.
>
> Queda solo por confirmar con Producción la **etiqueta visible** de cada equipo (que Scheffers
> 2/3 y VEB se rotulen «Evaporador…»), no la lógica.

### 1.2 El catálogo `BD` (códigos de producto y estados)

Códigos de producto = familia + formato + destino, cada uno con un **rendimiento en litros de
leche por hora de proceso**:

| Familia | Significado (confirmar con Producción) |
|---|---|
| `RC…` | Recepción / precondensado |
| `LN…` | Secado Nestlé |
| `LU…` | Secado Colun |
| `LC…` | Secado CCAA (variante `C`) |

| Formato | L/h de referencia |
|---|---|
| `SH2` (Scheffers 2) | 15.900 |
| `SH3` (Scheffers 3) | 11.000 |
| `VEB` | 12.400 |

Sufijo `N` = Nestlé, `C` = CCAA. Ej.: `RCSH2N`, `LNSH3`, `LCVEB`.

**Leyenda de estados de equipo** (lo que aparece como letras en la grilla):

| Código | Estado |
|---|---|
| `A` | Aseo |
| `P` | PNP (paro no programado) |
| `M` | Mantenimiento |
| `X` | Preparación |
| `AP` | Atraso de partida |

### 1.3 La hoja `Base` (calculadora de tiempos)

Convierte un objetivo de kilos y la relación de concentración en horas de corrida. Fórmulas
reales del Excel:

```
Tiempo (h)      = kilosObjetivo / flujo            (H = G / C)
factor concentr = (SG + SNG) / 100                 (L12 = (J12 + K12)/100 = 0,13122)
Fracción de día = (Tiempo·60)/60/24                (para pintar la carta)
```

Es una ayuda para dimensionar bloques; puede quedar para una segunda iteración.

---

## 2. Cómo encaja en la arquitectura actual (LEER antes de tocar código)

El Planificador **no** introduce tecnología nueva. Sigue exactamente el patrón del resto de la
app (ver `MODELO_DATOS.md §4`):

- **Sin módulos ES.** `file://` los bloquea. Se usan `<script>` globales con espacio de nombre.
  Agrega el tuyo: **`Planificador`** para el dominio del planificador, junto a `Esquema`,
  `Dominio`, `Repositorio`, `Semilla`, `UI`, `App`.
- **Cuatro capas, y solo una cambia al migrar:**
  - `js/modelo/esquema.js` → declara las entidades nuevas (§3). *Se reutiliza al migrar.*
  - `js/modelo/dominio.js` (o un nuevo `js/modelo/planificador.js`) → reglas puras (§4).
    **No importa DOM, ni red, ni almacenamiento.** Por eso es testeable.
  - `js/modelo/repositorio.js` → **no se toca la lógica**; solo se benefician las entidades
    nuevas de la validación/auditoría que ya existe.
  - `js/ui/componentes.js` + `js/app.js` → la vista (§5).
- **Los formularios se generan desde el esquema.** Si declaras bien las entidades en
  `esquema.js`, el alta/edición de bloques y el mantenedor de códigos aparecen validados sin
  escribir formularios a mano. Aprovéchalo.
- **El repositorio es asíncrono.** Usa `await` aunque hoy escriba en `localStorage`.
- **Decisiones devuelven motivos, no booleanos** (patrón `{ permitido, bloqueos[] }` de
  `MODELO_DATOS §2.6`). Aplícalo a las validaciones del planificador (solapamientos, etc.).

### 2.1 Reutiliza lo que ya existe, no lo dupliques

- Los **productos** ya viven en la entidad `producto` (con su `mandanteId` y `familia`). Un
  `codigoProduccion` del planificador **referencia** un `producto`; no reescribe el catálogo de
  productos. Así el planificador habla el mismo idioma que Producción y Calidad.
- Los **mandantes** (`Nestlé`, `CCAA`, `Colun`, `P. Unión`) ya son entidad `mandante`.
- Idealmente, «cerrar» un bloque del programa podría **proponer crear el `lote`** correspondiente
  en el módulo Producción (plan → real). No es obligatorio en la v1, pero deja el gancho previsto.

---

## 3. Modelo de datos nuevo (para `esquema.js`)

Declara estas entradas **siguiendo el estilo declarativo de `esquema.js`** (campos con
`tipo`/`req`/`ref`/`def`, `indices`, `grupo`, `rotulo`, `descripcion`). Tipos disponibles:
`id, texto, entero, decimal, fecha, fechaHora, hora, booleano, enum, ref, lista, objeto`.

### 3.1 Catálogos nuevos (en `Esquema.CATALOGOS`)

```js
equipos: [
  "carga_precondensado", "scheffers2", "scheffers3",
  "veb", "linea1", "linea2", "linea_mantequilla"
],
estadosEquipo: {          // leyenda BD; { codigo: { etiqueta, color } }
  A:  { etiqueta: "Aseo",             color: "#…" },
  P:  { etiqueta: "PNP",              color: "#…" },
  M:  { etiqueta: "Mantenimiento",    color: "#…" },
  X:  { etiqueta: "Preparación",      color: "#…" },
  AP: { etiqueta: "Atraso de partida",color: "#…" }
},
categoriasConsumo: [       // las filas de CONSUMO del balance
  // DERIVADAS del programa (se calculan desde los códigos en evaporadores, §4.1):
  "prec_nestle", "prec_ccaa", "secado_ccaa", "secado_nestle", "secado_colun",
  // MANUAL (no sale de ningún código; en el Excel está en 0, es un traspaso puntual):
  "trasvasije"
]
```

> Paleta de colores: usa el sistema de diseño de `css/estilos.css` y cumple contraste AA en
> claro y oscuro. Antes de fijar los colores de estados y de familias de producto, **lee la
> skill `dataviz`** (aplica a cualquier codificación por color en una grilla).

### 3.2 Entidad `semanaPlan` (maestro/transaccional — cabecera de la semana)

```
etiqueta: "Semana de planificación", grupo: "transaccional", rotulo: "codigo"
campos:
  id            : id
  codigo        : texto, req   (ej. "W7"; único)
  anio          : entero, req
  fechaInicio   : fecha, req   (lunes de la semana)
  estado        : enum ["borrador","publicada","cerrada"], def "borrador"
  observacion   : texto
indices: [{ campos: ["codigo","anio"], unico: true }]
```

### 3.3 Entidad `codigoProduccion` (maestro — la tabla `BD`)

```
etiqueta: "Código de producción", grupo: "maestro", rotulo: "codigo"
descripcion: "Receta programable: qué producto, en qué formato/evaporador, para qué mandante,
              y cuántos litros de leche consume por hora. Origen: hoja BD del Excel."
campos:
  id             : id
  codigo         : texto, req        (ej. "RCSH2N"; único)
  productoId     : ref → producto    (enlaza con el catálogo real de productos)
  mandanteId     : ref → mandante
  formato        : enum ["SH2","SH3","VEB"]
  categoria      : enum categoriasConsumo   (a qué fila de CONSUMO suma)
  rendimientoLh  : decimal, req, min 0      (litros de leche por hora — col. C de BD)
  activo         : booleano, def true
indices: [{ campos: ["codigo"], unico: true }]
```

### 3.4 Entidad `bloquePlan` (transaccional — cada corrida en la grilla)

Es la unidad del programa horario. **Un bloque = un tramo de horas en un equipo.** Reemplaza a
«celdas pintadas» del Excel por un intervalo explícito (mucho más limpio que replicar columnas).

```
etiqueta: "Bloque de programa", grupo: "transaccional"
campos:
  id            : id
  semanaId      : ref → semanaPlan, req
  equipo        : enum equipos, req
  dia           : entero, req, min 0, max 6      (0 = lunes … 6 = domingo)
  horaInicio    : decimal, req, min 0, max 24    (permite medias horas: 8.5)
  horaFin       : decimal, req, min 0, max 24
  tipo          : enum ["produccion","estado"], req
  codigoId      : ref → codigoProduccion   (obligatorio si tipo = "produccion")
  estadoEquipo  : enum estadosEquipo        (obligatorio si tipo = "estado")
  cantidadKg    : decimal, min 0            (objetivo de kilos, opcional)
  observacion   : texto
```

> Reglas que el **dominio** hará cumplir (no el esquema): `horaFin > horaInicio`; coherencia
> `tipo`↔(`codigoId`/`estadoEquipo`); **no solapar** dos bloques en el mismo equipo/día/tramo.
>
> Un bloque puede vivir en **cualquier** equipo (también líneas y mantequilla, para programarlas),
> pero **solo los bloques en evaporadores alimentan el balance de leche** (§1.1, §4.1).

### 3.5 Entidad `balanceDia` (transaccional — una fila por semana × día)

Guarda **solo lo que se ingresa a mano** (stock inicial y recepciones); el consumo y los saldos
son **derivados** (§4), nunca se persisten (mismo principio que «el resultado de calidad nunca se
guarda», `MODELO_DATOS §2.2`).

```
etiqueta: "Balance de leche del día", grupo: "transaccional"
campos:
  id              : id
  semanaId        : ref → semanaPlan, req
  dia             : entero, req, min 0, max 6
  stockInicial      : decimal, min 0     (solo el del primer día; el resto se arrastra)
  recepcionCCAA     : decimal, def 0
  recepcionNestle   : decimal, def 0
  recepcionPUnion   : decimal, def 0
  trasvasije        : decimal, def 0     (MANUAL: no sale de ningún código. En el Excel = 0)
  cremaDisponibleTon: decimal, min 0     (la fila «Crema disponible (Ton)»; ver §3.6)
  ajustes           : objeto             (correcciones puntuales por origen, como los ±40040 / −5800
                                          / −46000 que el Excel suma dentro de algunas celdas de consumo.
                                          Sugerido: { ccaa, nestle, punion } en litros, +/−)
  observacion       : texto
indices: [{ campos: ["semanaId","dia"], unico: true }]
derivados:
  consumoPorCategoria : "Planificador.consumoDia() — desde los bloques de EVAPORADORES (§4.1).
                         'trasvasije' NO es derivado: se toma de este registro."
  totalDisponible / totalConsumo / stockFinal / stockPorOrigen : "derivados, nunca se persisten"
```

### 3.6 Crema — dos niveles, elige según el tiempo disponible

En el Excel la crema aparece en dos formas: la fila **«Crema disponible (Ton)»** (saldo diario:
12, 6, 6, 24 t en `W7`) y los **despachos** anotados en Observaciones
(*«Despacho de crema 12 ton, a las 16 h, destino Los Ángeles»*).

- **v1 (mínimo, ya cubierto):** un campo `cremaDisponibleTon` por día en `balanceDia` (§3.5). Se
  teclea a mano y se muestra en la fila del programa. Suficiente para reproducir el Excel.
- **v2 (si Producción quiere trazar despachos):** entidad propia `despachoCrema`
  (`semanaId`, `dia`, `hora`, `toneladas`, `destino`, `observacion`). El saldo del día pasaría a
  ser *saldo inicial − despachos*, igual que el stock de leche es un saldo y no un acumulado
  (`MODELO_DATOS §2.4`). La Línea Mantequilla, cuando se programe, consumiría de este saldo.

**Recomendación:** entrega la v1 ahora (un campo) y deja `despachoCrema` anotado como extensión.
No bloquees el módulo por la crema.

---

## 4. Reglas de dominio (funciones puras — `Planificador.*`)

Todo esto va en `dominio.js` o en un `js/modelo/planificador.js` nuevo cargado como
`<script>` global. **Sin DOM, sin almacenamiento**: recibe datos, devuelve datos. Es lo que se
prueba en `pruebas.html`.

### 4.1 Consumo del día derivado del programa (EL núcleo)

Réplica de las fórmulas `COUNTIF(rangoEquipoDelDía, código) × rendimiento` del Excel, pero
limpia: en vez de contar celdas, **suma horas de los bloques**.

```
consumoDia(semana, dia) → { prec_nestle, prec_ccaa, secado_ccaa,
                            secado_nestle, secado_colun, trasvasije, total }

// Categorías DERIVADAS: solo bloques en EVAPORADORES (así lo hace el COUNTIF del Excel).
EVAPORADORES = ["scheffers2", "scheffers3", "veb"]

por cada bloque de esa semana y día con tipo = "produccion"
                                     Y bloque.equipo ∈ EVAPORADORES:
    horas   = bloque.horaFin − bloque.horaInicio
    cod     = codigoProduccion(bloque.codigoId)
    litros  = horas × cod.rendimientoLh
    acumular litros en cod.categoria         // prec_* o secado_*

// Categoría MANUAL:
trasvasije = balanceDia(semana, dia).trasvasije   // no sale de ningún bloque

total = prec_nestle + prec_ccaa + secado_ccaa + secado_nestle + secado_colun + trasvasije
```

> **Por qué solo evaporadores:** las Líneas 1/2 y Mantequilla también llevan códigos en la grilla
> (para su propia programación), y un mismo código —p. ej. `LNSH2`— aparece en el evaporador *y*
> en la línea. Si sumaras todos los bloques, contarías la leche dos veces. El Excel lo evita
> sumando solo las filas de evaporadores; el modelo hace lo mismo filtrando por `equipo`.
>
> Esto es lo que hace que el balance sea automático: **cambiar el programa de evaporadores
> recalcula el consumo y, por lo tanto, el stock proyectado.** No dupliques el número a mano.

### 4.2 Arrastre de stock (balance diario)

Réplica de `X15/X16/X17` y `X18 → AO stock siguiente` del Excel:

```
totalDisponible(dia) = stockInicial(dia) + recepcionCCAA + recepcionNestle + recepcionPUnion
totalConsumo(dia)    = consumoDia(dia).total
stockFinal(dia)      = totalDisponible(dia) − totalConsumo(dia)
stockInicial(dia+1)  = stockFinal(dia)          // arrastre

saldo por origen (arrastrado día a día):
  stockCCAA(dia)   = stockCCAA(dia−1)   + recepcionCCAA   − prec_ccaa   − secado_ccaa
  stockNestle(dia) = stockNestle(dia−1) + recepcionNestle − prec_nestle − secado_nestle − trasvasije
  stockPUnion(dia) = stockPUnion(dia−1) + recepcionPUnion − …
```

Un **saldo negativo por origen es una alarma** (falta leche de ese mandante para lo programado):
la vista debe marcarlo, igual que el saldo negativo de silo en Recepción.

### 4.3 Calculadora de tiempos de corrida (hoja `Base`)

```
horasCorrida({ kilosObjetivo, flujo }) → kilosObjetivo / flujo
factorConcentracion(sg, sng)           → (sg + sng) / 100
```

Úsala para **sugerir `horaFin`** cuando el usuario ingresa `cantidadKg` en un bloque
(`horaFin = horaInicio + horasCorrida(...)`), sin obligar.

### 4.4 Validaciones (devuelven `{ permitido, bloqueos[] }`)

- `validarBloque(bloque, bloquesExistentes)`: `horaFin > horaInicio`; coherencia tipo↔código;
  **sin solapamiento** en el mismo `equipo`+`dia`.
- `puedePublicar(semana)`: todos los días con balance, sin saldos negativos sin justificar.

---

## 5. Interfaz (vista `#planificador` en `app.js` + `componentes.js`)

Añade la vista al menú lateral y al router por hash (`index.html#planificador`), igual que las
otras. Selector de **usuario/rol** ya existe: `produccion` y `admin` editan; el resto ve en modo
lectura.

### 5.1 Selector de semana

Barra superior: elegir `semanaPlan` (W6/W7/W8…), botón **«Nueva semana»** (clona la estructura,
arrastra el stock final de la semana anterior como stock inicial del lunes), y estado
(borrador/publicada/cerrada).

### 5.2 Grilla del programa horario (carta Gantt)

- Eje X: **horas 0–24 por día**, 7 días (lun–dom). Encabezado con el nombre del día y su fecha.
- Eje Y: los `equipos` (una fila cada uno) + filas de resumen (Crema, Observaciones).
- Cada `bloquePlan` se dibuja como una barra que ocupa de `horaInicio` a `horaFin`, coloreada
  por **familia de producto** (producción) o por **estado** (aseo/mantención/…). Muestra el
  `codigo` dentro.
- Interacción mínima v1: clic en una celda vacía → alta de bloque (form generado desde el
  esquema); clic en un bloque → editar/eliminar. Arrastrar para redimensionar es un plus de v2.
- **Leyenda visible** de colores (familias y estados), tomada de los catálogos.
- Scroll horizontal para la semana completa; encabezado de equipos y de horas fijos (sticky).

### 5.3 Tabla de balance de leche

Debajo de la grilla, alineada por día. Filas de §1.1. Celdas editables solo en **stock inicial
(día 1)** y **recepciones**; el resto son derivadas y van en gris. Resaltar en rojo los saldos
negativos por origen. Total de la semana en la última columna (como la columna `ES` del Excel).

### 5.4 Mantenedor de códigos (`codigoProduccion`)

En **Administración** (junto a las otras 14 entidades): CRUD del catálogo `BD`, con
`rendimientoLh`, `categoria`, producto y mandante. Formulario generado desde el esquema.

---

## 6. Semilla / datos de ejemplo (`semilla.js`)

Para poder ver algo al abrir la app, carga:

1. El catálogo `codigoProduccion` con las filas de `BD` (los ~21 códigos y sus rendimientos).
2. La `semanaPlan` **W7** (lunes 2026-02-09) con:
   - `balanceDia` de los 6 días con el stock inicial (193.000 L el lunes) y las recepciones
     CCAA/Nestlé reales de la hoja.
   - Un puñado de `bloquePlan` representativos (Scheffers 2 con `RCSH2N`, VEB con estados, etc.)
     para que el consumo derivado cuadre aproximadamente con el balance del Excel.

Mantén el patrón: datos planos → `Semilla` los traduce al modelo con `Repositorio.importar()`
atómico.

---

## 7. Pruebas a agregar (`js/modelo/pruebas.js`, se ven en `pruebas.html`)

Suma casos al banco existente (hoy 58/58). Cubre lo que, si se rompe, entrega un plan falso:

- `consumoDia`: N bloques de un código → litros = horas × rendimiento, clasificados por categoría.
- Arrastre de stock: `stockInicial(dia+1) == stockFinal(dia)`; saldo por origen correcto tras
  recepción + consumo.
- Detección de **solapamiento** de bloques en el mismo equipo/día.
- Coherencia `tipo`↔(`codigoId`/`estadoEquipo`) y `horaFin > horaInicio`.
- `horasCorrida` reproduce un caso de la hoja `Base` (ej. objetivo/flujo → ~5,6 h).
- Saldo negativo por origen dispara bloqueo en `puedePublicar`.

---

## 8. Orden de implementación sugerido

1. **Esquema** (`esquema.js`): catálogos §3.1 + entidades §3.2–3.5. Compila mentalmente que la
   validación genérica ya las cubre.
2. **Dominio** (`planificador.js` nuevo, o dentro de `dominio.js`): funciones §4. Puras.
3. **Pruebas** (`pruebas.js`): §7. Debe quedar todo verde en `pruebas.html` antes de tocar UI.
4. **Semilla** (`semilla.js`): §6.
5. **UI** (`componentes.js` + `app.js`): vista §5, entrada en menú y router, mantenedor en Admin.
6. **Repositorio**: no requiere cambios de lógica; verifica que las entidades nuevas pasan por su
   validación e integridad referencial (`codigoId`, `productoId`, `semanaId`).
7. Actualiza `README.md` y `MODELO_DATOS.md` con el módulo nuevo (mantén la casa ordenada).

**Regla de oro:** primero esquema + dominio + pruebas (todo verde), y solo entonces la interfaz.
Es el orden con que se construyó el resto de la app.

---

## 9. Decisiones pendientes (confirmar con Producción antes o durante)

> Las dos que estaban abiertas ya se resolvieron desde el propio Excel (marcadas ✔). Lo que queda
> es confirmación de rótulos/valores, no lógica.

1. ✔ **Mapeo equipo ↔ proceso — RESUELTO** (§1.1). Los evaporadores (Scheffers 2/3, VEB) consumen
   leche y alimentan el balance; las Líneas 1/2 (secado) y Mantequilla (crema) no. Deriva de las
   fórmulas `COUNTIF`. Solo falta confirmar la **etiqueta visible** de cada equipo.
2. ✔ **Crema y trasvasije — RESUELTO** (§3.5, §3.6). Trasvasije = campo **manual** por día (0 hoy);
   crema = campo `cremaDisponibleTon` por día en v1, con `despachoCrema` como extensión v2.
3. **Rendimientos `rendimientoLh` oficiales.** Los de `BD` (15.900 / 11.000 / 12.400) son los del
   Excel; validar que siguen vigentes. Editable desde Administración de todos modos.
4. **Categorías de consumo por código.** Confirmar el mapeo familia→categoría
   (`RC…`→prec, `LN…`→secado_nestle, `LU…`→secado_colun, `LC…`→secado_ccaa). Es el que usan las
   fórmulas, pero conviene que Producción lo ratifique antes de cargar el catálogo completo.
5. **Plan → real:** ¿cerrar un bloque debe crear el `lote` de Producción, o el planificador es
   solo proyección? Define el gancho aunque no se implemente en v1.
6. **Semana de 6 o 7 días.** El Excel muestra lun–sáb; el modelo admite domingo (día 6). Confirmar.

---

## 10. Lo que NO hay que hacer

- **No** repliques la grilla de columnas del Excel (156 columnas) en el modelo de datos. Un
  bloque con `horaInicio`/`horaFin` es más limpio y evita el infierno de celdas.
- **No** persistas consumos ni stocks finales: son derivados (§4). Guardarlos los congela y
  hacen mentir al plan en cuanto se mueve un bloque.
- **No** uses módulos ES (`import`/`export`) ni dependencias externas: rompe el `file://`.
- **No** metas lógica de negocio en la UI ni acceso a datos en el dominio. Respeta las capas.
- **No** dupliques el catálogo de productos: `codigoProduccion.productoId` referencia `producto`.
```
