# Modelo de datos — Gestión Productiva Planta CCAA

Modelo funcional del proceso productivo: recepción de leche → producción de lotes →
control de calidad → liberación → despacho.

Está diseñado sobre **el proceso**, no sobre las planillas Excel actuales. La forma de
registrar la información puede cambiar sin que cambie este modelo.

---

## 1. La regla que justifica el sistema

> **Un despacho exige un lote liberado.**
> Un lote se libera si **todos sus formularios de calidad están completos y firmados** *y* su
> **calidad es conforme** contra la especificación vigente a la fecha del lote.
> Si la calidad no es conforme, el lote solo puede salir como **liberación bajo concesión**:
> con motivo escrito, autorizador identificado y marca permanente en el registro.

Todo lo demás en este documento existe para poder aplicar esa regla y demostrar después
que se aplicó.

La concesión no es una puerta trasera: es el reconocimiento de que en planta *sí* se libera
producto fuera de especificación (reproceso, aceptación del mandante). Si el sistema no lo
contempla, la gente lo evade ajustando los parámetros medidos — y ahí se pierde el registro
que justamente se quería conservar.

---

## 2. Decisiones de modelado y por qué

### 2.1 El código de lote no es la identidad del lote

En los datos de planta, `CCAA6140N` corresponde el mismo día a *P. Entero ST 48%* **y** a
*P. Semidescremado ST 45%*; `CCAA6135N` aparece dos veces para el mismo producto. El código
es un **correlativo diario** y el sufijo `N` distingue polvo de crema, no el producto.

Por eso:

- La identidad del lote la asigna el sistema (`id`).
- `codigoLote` es un atributo descriptivo más.
- La clave natural que se controla como única es **`codigoLote`** dentro de la sucursal: identifica una corrida por máquina y día.

> Esto corrige el supuesto de `CONTEXTO_ARCHIVOS_FUENTE.md` §2.1 ("una fila por lote
> producido"). La fila del Excel es un **despacho**; un lote tiene N despachos.

### 2.2 El resultado de calidad nunca se guarda

Se recalcula siempre desde los análisis y la especificación. Consecuencia deseada: al
corregir una especificación, **todo el histórico queda reevaluado con el criterio nuevo**,
sin migraciones ni recálculos manuales. Guardar el veredicto lo congela y hace mentir a los
indicadores en cuanto la spec cambia.

### 2.3 Las especificaciones son versionadas

Un lote de mayo se audita contra la especificación vigente **en mayo**, no contra la actual.
Sin esto no se puede responder a una auditoría que pregunte por qué se liberó un lote.

### 2.4 La ocupación de silo es un saldo, no un acumulado

`movimientoSilo` es el libro mayor de cada silo (ingresos por recepción, salidas por consumo
de lote, ajustes). La ocupación **se calcula sumando**, nunca se edita. Un saldo negativo es
señal automática de descuadre en el registro.

### 2.5 La trazabilidad devuelve un conjunto, no una cadena

La leche se mezcla dentro del silo. Preguntar "¿de qué recepciones salió el lote X?" solo
puede responderse con el conjunto de recepciones que había en ese silo antes del consumo.
Así funciona la trazabilidad en lácteos; prometer un vínculo uno a uno sería falso.

### 2.6 Los formularios de calidad son datos, no código

Cada `documentoLiberacion` lleva una **`plantilla`**: la lista de campos de su formulario
(`clave`, `etiqueta`, `tipo`, `req`, `unidad`, `min`, `max`). La interfaz la dibuja; no hay 19
formularios escritos a mano. Calidad cambia un campo desde Administración y el formulario
cambia, sin tocar código ni volver a desplegar.

Dos atributos hacen el trabajo que el papel no puede:

- **`origen`** (`"lote.codigoLote"`) rellena el campo con lo que el sistema ya sabe. Nadie
  vuelve a teclear el lote, el producto ni la fecha, y por tanto nadie los teclea mal.
- **`parametro`** (`"mg"`) ata el campo a un fisicoquímico. Al escribirlo se coteja **contra el
  análisis del lote y contra la especificación vigente**, y se avisa antes de firmar. Un
  formulario que no cuadra con el laboratorio es exactamente lo que una auditoría busca y lo
  que en papel no aparece nunca.

El mismo mecanismo sirve para cualquier campo de tipo `objeto`: si declara `campos`, la interfaz
dibuja un grupo de campos reales en vez de un cuadro de texto con JSON. Lo usan los controles de
camión de `recepcion`, los parámetros de `analisis`, y los saldos y ajustes por origen de
`balanceDia`. **Un campo `objeto` sin `campos` declarados cae en JSON crudo**, que es inservible
para quien completa el registro en planta: si se agrega uno nuevo, hay que declarar sus campos.

El avance documental **no se persiste**: se deriva de los `registroCalidad` del lote (§2.2).
Un registro en borrador u observado no cuenta como cumplido, y un formulario observado bloquea
la liberación aunque el resto esté completo.

> **Cuidado con el filtro por lote.** `avanceChecklist` acepta un `loteId` y hay que pasarlo:
> sin él, el formulario de otro lote puede dar por cumplido un documento que nadie completó.
> Lo detectó una prueba y hay una de regresión que lo cubre.

### 2.7 Las recetas son multinivel, y por eso el planificador sirve

Una tabla plana "producto → litros de leche" no basta: la mantequilla no se hace con leche,
se hace con crema. El modelo encadena transformaciones y las resuelve recorriendo el árbol:

```
mantequilla 1 kg ──► crema 2 kg ──► leche fresca 8 L
crema       1 kg ──► leche fresca 4 L
```

Para eso `producto` declara su **`naturaleza`** (materia prima / intermedio / terminado) y su
**`unidadBase`** (la leche en litros, el polvo y la crema en kilos). La explosión se detiene en
las materias primas; si llega a un producto sin receta que no es materia prima, lo informa en
vez de devolver un número incompleto.

**Lo que esto le da al planificador.** `codigoProduccion.rendimientoLh` dice cuántos litros por
hora traga el evaporador; la receta dice cuántos litros cuesta un kilo. Dividiendo:

```
kg de producto por hora = rendimientoLh ÷ litros por kilo
```

Un bloque de 8 h de un evaporador de 15.900 L/h haciendo crema (4 L/kg) deja **31.800 kg**. Ese
número no existía antes: el programa solo sabía cuánta leche consumía, no cuánto producto
entregaba. Ahora el balance lleva una fila de **producción estimada según receta** junto a la
de consumo.

Cuando un código no tiene producto asignado o el producto no tiene receta, el planificador
**devuelve `null` en vez de estimar**: mejor no responder que dar una cifra inventada.

Las recetas se versionan como las especificaciones (§2.3) y se validan contra **ciclos**: una
receta que directa o indirectamente vuelve a necesitar su propio producto se rechaza al guardar,
porque colgaría el cálculo. También se exige que la unidad de cada componente sea la suya —
declarar la crema en litros cuando se mide en kilos es un error, no una conversión implícita.

### 2.8 El programa horario genera el consumo del balance

En el planificador los dos bloques están **acoplados**: el consumo de leche de cada día se
deduce de las horas programadas en evaporadores (`horas × rendimientoLh` del código), y ese
consumo arrastra el stock al día siguiente. Consecuencias:

- **Solo los evaporadores** (Scheffers 2/3, VEB) alimentan el balance. Las líneas de secado
  trabajan precondensado y la de mantequilla, crema. Un mismo código aparece en el evaporador
  *y* en la línea; sumar ambos contaría la misma leche dos veces.
- **`trasvasije` es la excepción**: no sale de ningún bloque, se teclea en el balance del día.
- **Nada de esto se persiste.** Igual que el resultado de calidad (§2.2), el consumo y los
  stocks se recalculan siempre. Guardarlos haría mentir al plan en cuanto se mueve un bloque.
- El reparto por origen usa el mapa `categoriasConsumo[…].origen`. El único supuesto pendiente
  de confirmar es que **el secado Colun se abastece de la leche de P. Unión**.

### 2.9 Los colores de la carta Gantt están validados, no elegidos a ojo

Las cuatro familias de código usan una paleta categórica verificada con el validador de la
skill `dataviz` sobre la superficie real de la aplicación (`#ffffff`) y con la lista de pares
**completa** —en una carta Gantt cualquier par puede quedar contiguo—: peor par CVD ΔE 9.2
(objetivo ≥ 8) y visión normal ΔE 16.3 (piso ≥ 15). Las combinaciones con magenta o verde
fueron descartadas por medición, no por gusto.

El aqua queda en 2.82:1 contra el blanco, bajo 3:1, lo que obliga a "relief": **el código va
siempre escrito dentro del bloque**. Los estados de equipo no usan colores de serie —van en
gris con trama las paradas planificadas y en la paleta de estado reservada las anomalías (PNP,
atraso)— para que un estado nunca se confunda con un producto.

**Los colores de marca no entran en la grilla.** La interfaz usa la identidad de
`camposaustrales.cl` (azul `#1d3762`, verde `#65bc7b`), pero medidos contra las series dan
verde↔aqua ΔE 6.3 (4.8 en protanopía) y azul↔violeta ΔE 13.5, ambos bajo el piso de 15. Por eso
el marcador de "evaporador" dentro de la carta es **neutro** y el significado lo carga su
etiqueta. El cromo de marca vive donde no hay series: barra lateral, botones, foco y barras de
avance.

### 2.10 Las decisiones devuelven motivos, no booleanos

`puedeLiberar()` y `puedeDespachar()` devuelven `{ permitido, bloqueos[] }`. La interfaz
puede explicar *por qué* no se puede avanzar, en vez de mostrar un botón gris sin razón.

---

## 3. Entidades

### Maestros

| Entidad | Rol |
|---|---|
| `mandante` | Empresa dueña del producto (incluye la marca propia CCAA) |
| `producto` | Producto terminado. **El mandante es un campo, no se deduce del nombre** |
| `receta` | **Qué se necesita para obtener un producto.** Multinivel y versionada |
| `especificacion` | Rangos por producto, **versionados** (`vigenteDesde` / `vigenteHasta`) |
| `silo` | Silo o estanque, con `capacidadL` para calcular ocupación |
| `vehiculo` | Camiones y transportistas |
| `documentoLiberacion` | Catálogo de documentos, con `aplicaA` por familia y la **`plantilla`** de su formulario |
| `usuario` | Personas y rol (`recepcion`, `produccion`, `calidad`, `admin`, `lectura`) |

### Transaccional

| Entidad | Rol |
|---|---|
| `recepcion` | Llegada de un camión y sus controles |
| `movimientoSilo` | Libro mayor de cada silo (`ingreso` / `salida` / `ajuste`) |
| `lote` | **Unidad de producción y de liberación** |
| `analisis` | Medición fisicoquímica de un lote (puede haber varias) |
| `registroCalidad` | **Un formulario del checklist ya completado** para un lote: sus valores, quién firmó y cuándo |
| `liberacion` | Autorización de Calidad y su firma |
| `despacho` | Salida física. Solo contra lote liberado y kilos disponibles |

### Planificación

| Entidad | Rol |
|---|---|
| `codigoProduccion` | Receta programable: qué se produce, en qué evaporador y cuántos **litros por hora** consume (hoja `BD`) |
| `semanaPlan` | Cabecera de la semana programada (`borrador` → `publicada` → `cerrada`) |
| `bloquePlan` | Un tramo de horas ocupado en un equipo. Sustituye a las celdas pintadas del Excel |
| `balanceDia` | Solo lo que se teclea: stock de apertura, recepciones, trasvasije y crema |

### Sistema

| Entidad | Rol |
|---|---|
| `eventoAuditoria` | Bitácora inmutable. La escribe el repositorio, nunca la interfaz |

### Diagrama

```
recepcion ──► movimientoSilo ──► silo ◄── movimientoSilo ◄── lote ──► analisis
                (ingreso)                    (salida)         │          │
                                                              │          ▼
                                                              │   especificacion
                                                              │     (versionada)
                                                              ▼
                                                        liberacion ──► despacho
                                                     checklist + firma
```

---

## 4. Arquitectura

Tres capas. Cuando se decida la plataforma definitiva, **solo cambia una**.

| Archivo | Capa | Qué contiene | Al migrar |
|---|---|---|---|
| [js/modelo/esquema.js](js/modelo/esquema.js) | Esquema | Entidades, tipos, estados y validación | Se reusa. Genera el DDL o las tablas de Dataverse |
| [js/modelo/dominio.js](js/modelo/dominio.js) | Dominio | Reglas puras: calidad, liberación, despacho, silos | Se reusa entero |
| [js/modelo/repositorio.js](js/modelo/repositorio.js) | Persistencia | CRUD, integridad, auditoría | **Único archivo que se reescribe** |
| [js/modelo/recetas.js](js/modelo/recetas.js) | Dominio | Explosión multinivel, rendimientos, ciclos | Se reusa entero |
| [js/modelo/planificador.js](js/modelo/planificador.js) | Dominio | Consumo derivado, arrastre de stock, solapamientos | Se reusa entero |
| [js/modelo/semilla.js](js/modelo/semilla.js) | Migración | Traduce los datos planos del Excel al modelo | Plantilla del importador real |
| [js/ui/componentes.js](js/ui/componentes.js) | Interfaz | Modales, avisos, tablas y formularios desde el esquema | Se reusa si la interfaz sigue siendo web |
| [js/app.js](js/app.js) | Interfaz | Vistas y flujo | Se reusa si la interfaz sigue siendo web |

### Restricciones de implementación

- **Sin módulos ES.** `file://` los bloquea por CORS. Se usan `<script>` globales con
  espacios de nombre (`Esquema`, `Dominio`, `Repositorio`), igual que el resto del proyecto.
- **El repositorio es asíncrono** aunque `localStorage` sea síncrono. Es deliberado: si la
  API naciera síncrona, migrar a un backend obligaría a reescribir toda la aplicación.
- **El dominio no importa nada.** Sin DOM, sin almacenamiento, sin red. Por eso es testeable.

### Adaptadores de almacenamiento

```js
await Repositorio.iniciar({ adaptador: Repositorio.AdaptadorLocalStorage() });  // hoy
await Repositorio.iniciar({ adaptador: Repositorio.AdaptadorMemoria() });       // pruebas
// mañana: AdaptadorAPI / AdaptadorSharePoint — mismo contrato:
//   leerTodo() -> Promise<objeto|null>
//   escribirTodo(objeto) -> Promise<void>
```

---

## 5. Qué garantiza el repositorio

- **Validación** contra el esquema antes de escribir (tipos, obligatorios, enums, rangos,
  campos no declarados).
- **Integridad referencial**: no se crea un lote apuntando a un producto inexistente.
- **Índices únicos**: no se duplica la clave natural del lote.
- **Transiciones de estado**: un lote `en_proceso` no puede saltar a `cerrado`.
- **Borrado seguro**: no se elimina un producto que tiene lotes.
- **Auditoría automática**: cada alta, cambio y baja queda con usuario, fecha, valor anterior
  y valor nuevo.
- **Importación atómica**: si el archivo tiene un solo error, no se toca ningún dato.

---

## 6. Pruebas

Abrir **[pruebas.html](pruebas.html)** en el navegador. No requiere Node ni instalación.

Cubren 110 casos sobre las reglas que, si se rompen, dejan salir producto que no debería salir
o entregan un plan falso: evaluación de calidad, agregación de muestras, checklist por familia
de producto, las cinco vías de bloqueo de la liberación, concesiones, kilos disponibles,
ocupación y trazabilidad de silos, las garantías del repositorio, la migración de los datos
reales y —en el planificador— el consumo derivado, el arrastre de stock, el saldo por origen,
la detección de solapamientos y la calculadora de tiempos.

Estado actual: **110/110 pasando**.

---

## 7. Lo que este modelo todavía NO resuelve

- **Persistencia compartida.** `localStorage` es por navegador y por equipo. Recepción
  (turnos A/B/C), Producción y Calidad son personas distintas en momentos distintos: el flujo
  completo no puede operar así. La capa de repositorio existe para que esa decisión sea un
  cambio de un archivo, pero **hay que tomarla antes de poner el MVP en producción**.
- **Autenticación.** `usuario` y `rol` existen en el modelo; falta el mecanismo de identidad.
- **Migración del histórico.** Falta el importador de `Produccion.xlsx` (~954 filas → lotes +
  despachos).
- **Conversión litros ↔ kilos** para cerrar el balance recepción/producción (existe la hoja
  `Litros-kilos` en el Instructivo).

## 8. Definiciones pendientes con Calidad y Producción

1. **Especificaciones oficiales por producto y mandante.** Posible fuente: hoja `rc` de
   `Produccion.xlsx` (48 filas con rangos `Inferior`/`Máximo`).
2. **¿Los análisis son por lote o por despacho?** El modelo admite N análisis por lote y
   agrega por el peor caso; hay que confirmar que ese criterio es el correcto.
3. **¿Qué documentos aplican a qué familia de producto?** El campo `aplicaA` está listo.
4. **¿Está poblada la columna `OP` en el Excel real?** Si lo está, la OP puede ser la clave
   natural del lote y el modelo se simplifica.
5. **Límites de control de recepción** (acidez, pH, temperatura, crioscopía). Los valores en
   `Dominio.evaluarRecepcion()` son referenciales y parametrizables.
