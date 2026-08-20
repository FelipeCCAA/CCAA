# Levantamiento — registros diarios de fabricación 2026

**Fecha:** 2026-08-19
**Origen:** `Gestión TI/General/Fabricación/2026/` — 779 archivos, ocho familias de
registro, uno por día de operación.
**Método:** se abrió un ejemplar representativo de cada familia y se leyó su contenido
real (no el nombre del archivo ni el encabezado impreso). Cada brecha de §4 dice contra
qué archivo del proyecto se contrastó.

Este documento **complementa** a `docs/levantamiento-2026-07/LEVANTAMIENTO_PLANTA.md`,
que levantó el catálogo de formatos del sistema de calidad. Aquel dice qué formatos
existen; este dice **cuáles se llenan todos los días** y qué pasa con ellos.

> **Premisa (2026-08-20): estos archivos son referencia de arquitectura, no datos a
> migrar.** El sistema parte en blanco y Calidad configura los productos, especificaciones,
> recetas y formularios vigentes. Lo que sigue sirve para decidir **qué forma tiene el
> proceso**, no qué filas sembrar. Las variantes que solo viven en libros viejos —crema
> Svelty, crema Champiñones— quedan **fuera**: quien las necesite creará su hoja con el
> mecanismo de plantillas. Esto cambia el peso de varias brechas de §4, y está anotado
> donde corresponde.

---

## 1. Qué hay en la ruta

| Carpeta | Formato QMS | Archivos | Qué captura |
|---|---|---|---|
| `Instructivo` | `CCAA.REC.FORM.002.02` (+ tres hojas con `.002.01`) | 183 | El día de recepción. 20 hojas, **una sola captura** (`Descarga Camiones`); el resto deriva por fórmula |
| `Hojas de Rc` | `CCAA.REC.FORM.003.01` y `.017.01` | 240 | Estandarización de leche por silo: mezcla hasta el RC objetivo, línea destino, kg de precondensado |
| `Trazabilidad de leche` | `CCAA.REC.FORM.005.01` | 184 | Vale por silo: qué camiones entraron, con qué análisis, y a qué destino salió cada porción |
| `Crema` | `CCAA.REC.FORM.004.01` (+ `0082.MAN.FORM.000153/154`) | 111 | Vale de estandarización de crema, test IN/OUT sensorial, y las variantes Svelty / Champiñones / Despacho / Mantequilla |
| `Formularios Desviaciones` | `CCAA.REC.FORM.008.01` y `.009.01` | ~40 | Cuantificación de litros y kilos afectados por módulo y por proveedor |
| `Milkoscan` | Plan de autocontrol (sin código CCAA) | 6 | Verificación diaria de calibración contra patrón, tolerancia ±0,05, y aseo enzimático |
| `Entrega de Turnos` | sin código | **3** | Corte de turno: stock, pH/acidez/T° y línea consumiendo cada silo |
| `z D.Riveras` | trabajo estandarizado | 6 | Borradores (aseo filtros Turbo Mixer, DTP vaciado PPI) |

---

## 2. Cómo se relacionan

La cadena de un día encadena cuatro documentos por **llaves compartidas**, no por
referencia formal:

```
Camión (Instructivo, filas 17-68)
   +- n° camión / patente ----> Trazabilidad de silos (qué camiones llenaron el SILO 6)
   |                               +- silo + grasa/SNG ----> Hoja RC (entera + descremada)
   |                                                            +- línea destino (SCHEFFER 2/3, VEB)
   |                                                            +- Preco N° + Parte ----> producción
   +- la grasa separada -------> Crema (vale propio, cinco destinos)
   +- fuera de rango ----------> Formulario de Desviación (litros/kg por predio)
```

El **Milkoscan es transversal**: la grasa y el ST que deciden el RC, el veredicto del
camión y la conformidad del producto salen todos de ese equipo. La `Entrega de Turnos`
es el corte de inventario entre eslabones.

**Lo que hace frágil el conjunto es que la unión es por transcripción.** El operador
copia grasa `4,35` y SNG `8,9` desde el vale del silo a la Hoja RC a mano, y el número
de camión viaja como texto (`111-111C-118X109`). Ninguna de las dos copias deja rastro
de su origen.

---

## 3. Qué cubre ya el proyecto

| Documento de planta | Dónde vive en el sistema |
|---|---|
| `Descarga Camiones` (la fila del camión) | `recepcion.Recepcion` + `ModuloRecepcion`, según `docs/superpowers/specs/2026-08-19-recepcion-instructivo-design.md` |
| `Inhibidores` (PPRO N°1) | `recepcion.ControlInhibidores` + `BusquedaProveedor` |
| `Rec Silos`, `Litros-kilos`, `Diferencia` | Derivadas: `MovimientoSilo`, `kilos_desde_litros`, `diferencia_pesaje` |
| `Perm. Silo 1..8` | `recepcion.dominio.permanencia` + `horas_a_pagar` |
| `Pool Crioscopia` | `recepcion.dominio.crioscopia_pool` |
| Vale de trazabilidad de silo (parcial) | `MovimientoSilo` como libro mayor; el documento `CCAA.REC.FORM.005` está atado al checklist de liberación |
| Hoja RC (su parte central) | `estandarizacion.ValeEstandarizacion` + `estandarizacion.dominio` |
| `Base DATOS` (maestro de camiones) | `maestros.Vehiculo` |

---

## 4. Brechas

Ordenadas por consecuencia, no por esfuerzo.

### A. La crema no existe en el sistema

111 archivos al año, formato propio `CCAA.REC.FORM.004.01`, con su ciclo
(estandarización → análisis finales → liberación → **reestandarización**), su acción
correctiva declarada por parámetro, y límites en el propio formato —MG 22,5–23,5 %, acidez
10,5–14,5 °Th, T ≤ 8 °C, pH 6,5–6,8, crioscopía 512–540—.

Los **límites y las variantes concretas no se portan**: son referencia. Lo que hay que
construir es el mecanismo —vale con su ciclo, especificación versionada, destino— para que
Calidad configure las cremas vigentes al desplegar.

Hay `Silo.Tipo.TK_CREMA` y `procesos.CorridaMantequilla`, pero **nada entre la
descremadora y esos destinos**.

**Consecuencia dura: el balance de grasa no cierra.** La grasa que se le quita a la leche
entera no tiene dónde quedar registrada, y ningún `MovimientoSilo` de un TK de crema
tiene quién lo escriba.

El mismo vale lleva además la **clasificación de paros** de la descremadora (preparación,
arranque, limpieza, aseo intermedio, cambio Pto/Fto, operacionales; y no planeados con
motivo). `procesos.EventoProceso` registra cambios de estado, no paros con
inicio/término/duración.

### B. Descremación: reglas conocidas, sin dónde vivir

Ya lo dice `docs/REGLAS_DE_PLANTA.md` §2. La captura real es la hoja `Control Descr.` del
Instructivo: %MG por muestra (dos o tres lecturas) más promedio, SNG, estanque, acidez,
pH, T°, test IN/OUT, **aseo de filtros**, operario y destino.
`procesos.EtapaProceso.Tipo.DESCREMACION` existe como etiqueta y nada más.

### C. Los otros dos registros de silo del Instructivo

- **`Delvo Test`** por silo: número de silo, kg, producto, hora de inicio y de lectura,
  resultado, y **doble firma** (quien realiza y quien visualiza el análisis).
- **`C. P.Recepción`** — leche con **permanencia mayor a 48 h**: temperatura, acidez,
  **prueba de alcohol 75°**, **prueba de hervor**, pH, organoléptico IN/OUT, producto,
  parte y operario. Es el control que revalida leche vieja antes de usarla.

Ninguno existe. La antigüedad del contenido de un silo **es derivable** de
`MovimientoSilo`: falta el control y el aviso, no el dato. La spec de recepción los dejó
fuera a propósito («son registros del silo, no del camión»); esa deuda sigue abierta.

### D. Los formularios de desviación no tienen modelo, y la trazabilidad al predio se corta

El sistema tiene el **disparador** (`Recepcion.evaluar`, `bloqueos_de_cierre`,
`BusquedaProveedor`) pero no el **documento**. Faltan:

- **Folio secuencial anual** (`10-2026`).
- **N° de sello** por módulo.
- Decisión **«se puede recepcionar» por módulo**. En el formulario del 28-07-2026:
  módulo 1 NO (sello 3526), módulo 2 SÍ, módulo 3 NO (sello 3527).
- Cuantificación de **litros y kilos afectados** contra recepcionados y contra el total
  del camión.
- En el formato de acidez/crioscopía: resultado **por módulo** y **por proveedor**, con
  sus litros y kilos.

Peor: el proveedor es **texto libre** en `BusquedaProveedor.proveedor` y en
`recoleccion.ParadaRuta.proveedor` / `.predio`. El formato pide agregar por código de
predio (`8253178`, `8401`); con texto libre esa suma anual no se puede hacer. Es lo mismo
que CLAUDE.md ya anota como pendiente en §1.2.

### E. Calibración del Milkoscan

Plan de autocontrol diario: patrón %MG 4,42 y %ST 13,53, tolerancia ±0,05, status
Dentro/Fuera, aseo enzimático IN/OUT, operador, y hojas separadas por matriz (leche
fresca, descremada, Rc 0,201, crema).

Está en el backlog como `CalibracionInstrumento`
(`docs/levantamiento-2026-07/LEVANTAMIENTO_PLANTA.md`) y sigue sin implementarse. Sin él
no hay respuesta a «¿estaba calibrado el equipo el día que se liberó este lote?», y ese
equipo produce el número que decide el RC.

### F. Lo que la Hoja RC tiene y `ValeEstandarizacion` no

1. **Reemplazo de sólidos lácteos** (MSK / polvo a diluir + agua), con códigos SAP
   `41012616` (sólidos grasos) y `41012615` (sólidos no grasos), % ST / % seco / % BH y kg
   a agregar. El encabezado del formato lo dice: «Esta receta puede ser usada con/sin
   reemplazo de sólidos lácteos». El vale solo mezcla entera + descremada: una receta con
   reemplazo **no se puede representar** — y ese polvo debería descontar de bodega.
2. **Confirmación de RC de 1ª y 2ª estandarización.** El formato conserva cada medición
   (calculado 0,201 → confirmado 0,202); el modelo guarda un solo `grasa_real`/`sng_real`
   y `corrigiendo` borra el análisis anterior.
3. **Línea destino** (`SCHEFFER 2` / `SCHEFFER 3` / `VEB`) y **Preco N° / Parte N°** — el
   enlace del vale con el lote y con `Recepcion.uso` / `uso_numero`. El vale tiene silo
   destino, no equipo ni número de precondensado.
4. **Doble visto** (`V.B ESTANDARIZADOR` + `V°B° Analista`) contra un solo `responsable`.
5. **`% ST Silo objetivo` 12,7 % y `% ST Precondensado` 48 %** — el otro objetivo de la
   corrida además del RC, el que se le pasa a condensación.
6. Acidez, temperatura y densidad del silo al momento del vale (15,2 °Th / 6 °C / 1032),
   que hoy no se congelan en el vale. Es el mismo argumento que ya justificó congelar
   grasa y SNG.

### G. Falta el análisis del silo como registro

El vale de trazabilidad lo trae completo —pH, acidez, grasa, SNG, **proteína**, T°,
**densidad**, más hora de inicio de llenado y hora de toma de muestra— y es la **fuente**
de los números que la Hoja RC usa.

Hoy `Recepcion.controles` guarda los del **camión**; los del **silo** el operador los
teclea en el vale sin que quede de dónde salieron. **Proteína y densidad no existen en
ningún control del sistema.** Tampoco existe `LECHE CERTIFICADA` a nivel de silo (está a
nivel de camión, pero el silo mezcla), ni el remolque/«carro», que los formatos de
desviación tratan como unidad con módulos y sellos propios.

### H. Entrega de turno — medir antes de construir

Pide, por silo y TK: producto, cantidad, pH, acidez, T°, **qué línea está consumiendo el
silo** y observaciones; más el estado de la descremadora y el stock de entera/descremada/
estandarizada del turno.

Las cantidades ya se derivan del libro de movimientos. Lo que no existe es el vínculo
silo↔línea ni el acto de entrega con responsable.

**Salvedad: solo hay 3 archivos en todo 2026**, dos de ellos de enero. La práctica parece
abandonada o migrada a otro medio. No conviene modelarlo sin preguntar en planta.

---

## 5. Trampas en los archivos de origen — no portar

- **El Milkoscan marca «Fuera» cuando nadie midió.** En agosto, 13 de 15 días figuran
  fuera de límite solo porque la celda del resultado está vacía. Es exactamente el mismo
  defecto que la permanencia contra cero ya documentado en CLAUDE.md: un registro que
  falta se presenta como un resultado.
- **Las hojas derivadas están rotas en los archivos reales.** `Rec Silos` y `Diferencia`
  de julio traen `#REF!` y `#VALUE!` en la mayoría de sus filas.
- **Los nombres de archivo mienten.** El libro `15-07-2026 - RC` trae `Fecha: 2026-07-17`
  en sus dos hojas activas. Hay un `05-01-2025 Informe Desviacion` dentro de
  `ENERO-2026`, un `26-01-20206`, y un `.xlsx` descomprimido como carpeta. Igual que con
  `Documentos Planta/`: la fecha y el código se leen **de adentro** del archivo.
- **Conviven dos versiones del mismo formato.** El libro de crema repite el bloque con
  `CCAA.REC.FORM.004.01` y con `0082.MAN.FORM.000152 v2 MAYO 2022`.
- **Los archivos están abiertos por OneDrive.** Hay que copiarlos a un directorio
  temporal antes de leerlos, como ya anota CLAUDE.md para el Instructivo.

---

## 6. Decisiones que no son de TI

Ninguna se resuelve leyendo el código; van a Calidad o a planta. Pero **no todas hay que
responderlas ahora**, y confundirlas detiene el desarrollo sin motivo.

### 6.1 La línea entre lo que se difiere y lo que no

El proyecto ya tiene un precedente de cada categoría. La clasificación de §6.2 sale de
aplicar estos tres criterios, no de estimar esfuerzo.

**Configurable, y así debe ser.** `DocumentoLiberacion.frecuencia` es el caso ejemplar:
cambiarla mueve un formulario entre el expediente del lote y `/registros` **sin
desplegar**, y la escribe Calidad. Las especificaciones, igual.

**Deliberadamente NO configurable, aunque parezca un número suelto.**
`estandarizacion.MINUTOS_DE_AGITACION` lo dice literal: «quien lo cambie tiene que saber
qué está cambiando, y no se toca ni se hace configurable». Es un mínimo físico, no una
política. Lo mismo los límites del PCC, que viven en cada `ControlProceso` y no en un
maestro.

**Ni lo uno ni lo otro: es modelado.** Si algo es un producto del maestro o un estado de
un estanque no se resuelve con una pantalla. Cambiarlo después es migración de datos y
renombre de tablas — el mismo argumento por el que la separación `produccion` /
`inocuidad` se decidió con dos modelos y no con seis.

### 6.2 Las seis decisiones

| Decisión | Quién | ¿Se difiere? | Qué implica |
|---|---|---|---|
| ¿Una operación de crema puede repartirse en varios destinos, o siempre va a uno? | Calidad + planta | **Sí**, con reserva | Decide si el destino es un campo del vale o una tabla hija. Con arranque en blanco no hay migración que temer, así que se construye el caso general —varios destinos— y se simplifica si resulta que sobra |
| ¿La permanencia > 48 h **bloquea** el uso del silo o solo avisa? | Calidad | **Sí**, sin costo | Mismo patrón que la agitación de 30 min y que `codigo_lote_valido`: la regla nace como motivo, y que ese motivo entre o no en `bloqueos` es una línea. Se construye avisando |
| ¿Un análisis de silo caduca? ¿Cada cuánto se re-muestrea un silo en reposo? | Calidad | **Sí** | Un umbral en horas, misma forma que `LIMITE_PERMANENCIA_HORAS`. La fase 1 ya lo deja fuera explícitamente |
| ¿El maestro de predios/proveedores lo alimenta Recolección o viene de un sistema externo? | TI + planta | **Sí** el origen, **no** que exista | Que sea maestro y no texto libre es modelado, y ya lo decide la brecha D. De dónde se alimenta se cambia después sin tocar el esquema |
| ¿La `Entrega de Turnos` sigue viva? | Planta | **Sí**, entera | No es configuración: es construir o no construir. Difiere a la fase 6 |
| ¿Qué instrumentos además del Milkoscan entran al plan de autocontrol? | Calidad | **Sí**, y debe ser configurable desde el día uno | Un catálogo con patrón, tolerancia y frecuencia, igual que `DocumentoLiberacion`. Sumar un instrumento no puede pedir un despliegue |

**Solo una bloquea**: los destinos de crema, y bloquea la fase 2. Las fases 1, 3, 4 y 5
arrancan sin respuesta si se construyen avisando en vez de bloqueando y con los umbrales
como constantes con nombre — que es lo que el plan de la fase 1 ya hace.

### 6.3 Dos condiciones que trae la configurabilidad

Hacer algo configurable no es gratis en este código. Las dos reglas valen para cualquier
umbral que se decida exponer:

**1. Configurable exige decidir quién escribe.** El repo ya se tropezó con esto tres
veces: las especificaciones se le sacaron a Administración porque los rangos deciden qué
producto sale conforme; la fórmula se le sacó a Bodega porque el formulario dejaba que
quien descuenta el material redefiniera cuánto material lleva; la frecuencia no la toca
Producción porque podría bajar lo que se le exige. **Un umbral configurable sin el permiso
correcto no es flexibilidad: es un traslado de autoridad.**

**2. Todo lo configurable que afecte registros pasados hay que versionarlo o
congelarlo.** Si el límite de permanencia es editable y un lote de mayo se audita contra
el valor de hoy, cambiar la configuración **reescribe el veredicto de lotes ya liberados**,
en silencio. Las dos salidas que el proyecto ya usa:

- **Versionar** — `Especificacion`, con `es_vigente` calculado por la misma función que
  audita el lote.
- **Congelar en el registro** — los límites del PCC viven en cada `ControlProceso`; la
  composición de las dos leches vive en el vale, no en el silo.

Un umbral configurable que no haga ninguna de las dos es una bomba de tiempo sobre la
trazabilidad, y es preferible dejarlo como constante en el código.

---

## 7. Hoja de ruta

Seis fases. Cada una produce software que funciona y se puede probar sola; cada una lleva
su propio plan en `docs/superpowers/plans/`.

| Fase | Qué | Brechas | Espera a Calidad | Por qué en este orden |
|---|---|---|---|---|
| 1 | ~~**Análisis de silo**~~ — hecho (2026-08-19) | G | No | Es la pieza que ya usan tres documentos y hoy viaja por transcripción. Desbloquea 2, 3 y 6 |
| 2 | **Crema y descremación** | A, B | No — ver §6.2 | El único hueco que rompe un balance físico. Necesita el análisis de silo para la leche de entrada. Se construye el mecanismo; los productos y sus límites son configuración del despliegue |
| 3 | **Registros de silo del Instructivo** | C | No — se construye avisando | Delvo por silo y permanencia > 48 h. Cuelgan del análisis de silo |
| 4 | **Desviaciones + maestro de predios** | D | No | El maestro es prerrequisito y hoy no existe |
| 5 | **Calibración de instrumentos** | E | No — el catálogo es configurable | Independiente. Mejora la defensa ante auditoría sin bloquear operación |
| 6 | **Completar el vale RC** | F, H | No | Reemplazo de sólidos, confirmaciones, línea destino. Lo más invasivo sobre código que ya funciona |

**Ninguna fase espera a Calidad para empezar** (revisado el 2026-08-20). Con arranque
en blanco, lo que Calidad decide es **configuración**, no esquema: qué cremas existen, con
qué límites y a qué destinos. Lo que sí conviene confirmar antes de escribir el modelo de
la fase 2 es la **forma del proceso** —si una operación se reparte en varios destinos, si
la reestandarización es el mismo vale o uno nuevo, y de quién son los paros—, que es lo
que pregunta `docs/CONSULTA_CALIDAD_CREMA_2026-08-19.md`. Si esa respuesta demora, el
orden alternativo sigue siendo 1 → 3 → 4 → 5 → 2 → 6.

**Planes escritos:**

- Fase 1 — `docs/superpowers/plans/2026-08-19-analisis-de-silo.md` — **aplicado**.
  `recepcion.AnalisisSilo` con los siete parámetros del formato, la vigencia derivada
  del libro de movimientos, su API, la captura en la pantalla de silos, y las dos claves
  de procedencia en el vale. **La siguiente es la fase 2**, que espera la decisión de
  Calidad sobre los destinos de crema (§6.2); si demora, el orden alternativo es
  1 → 3 → 4 → 5 → 2 → 6.

Las fases 2 a 6 se planifican cuando la anterior esté en verde: el modelo de la fase 1
decide la forma de las siguientes, y planificarlas antes sería escribir contra un contrato
que todavía puede cambiar.
