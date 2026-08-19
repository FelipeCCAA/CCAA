# Recepción — integrar los parámetros del Instructivo diario

**Fecha:** 2026-08-19
**Origen:** `Gestión TI/General/Fabricación/2026/Instructivo/07 - Julio/` — 26 libros,
uno por día de julio de 2026.

---

## 1. Qué son los archivos de origen

Los 26 archivos son **el mismo libro repetido un día cada uno**: 20 hojas, de las
cuales solo tres están visibles. La captura ocurre en **una sola hoja**; el resto
son vistas por fórmula de esa misma fila.

| Hoja | Código del formato | Qué es |
|---|---|---|
| `Descarga Camiones` | `CCAA.REC.FORM.002.02` | **La captura.** Una fila por camión, 58 columnas, filas 17–68 |
| `Inhibidores` | `CCAA.REC.FORM.002.01` | PPRO N°1. Deriva, salvo tiras / hora de lectura / analista y el escalamiento a proveedor |
| `Rec Silos` | `0082.MAN.FORM.000114` | Deriva — kilos por silo |
| `Diferencia` | `0082.MAN.FORM.000261` | Deriva — guía contra romana. Trae una columna `SAP` **vacía en los 26 archivos** |
| `Perm. Silo 1..8` | `0082.MAN.FORM.000120` | Deriva, más hora de inicio de recolección y de entrada a condensación |
| `Litros-kilos` | `0082.MAN.FORM.000112` | Deriva |
| `Pool Crioscopia` | — | Deriva — M1..M4 al pool |
| `C. P.Recepción` | `CCAA.REC.FORM.002.01` | **Captura propia** — leche con permanencia mayor a 48 h |
| `Control Descr.` | `CCAA.REC.FORM.002.01` | **Captura propia** — control descremada |
| `Delvo Test` | `CCAA.REC.FORM.002.01` | **Captura propia** — Delvo por **silo**, no por camión |

Esto decide la forma del trabajo: integrar no es construir ocho formularios, es
**capturar bien la fila del camión y derivar el resto**.

## 2. Lo que se midió sobre los datos reales

603 filas con patente en los 26 archivos. Llenado por columna:

| Columna | Llenado | Consecuencia |
|---|---|---|
| `AG` Hora Programa | **1 / 603** | Es el minuendo del cálculo de sobreestadía |
| `AP` Hora Salida | **0 / 603** | Por eso «A tiempo/Atrasado» y los deltas contra HS salen vacíos |
| `AQ`…`AT` Horas a pagar | **100 %** | Se calculan igual, contra un cero |
| `W` Crioscopía M4 | 7 % | M1 84 %, M2 84 %, M3 73 % |
| `AA` Antibiótico positivo | 2 / 603 | Dos positivos en todo julio |
| `G` Vuelve a lavarse | 2 / 603 | |
| `AN` Recambio de dilución | 4 % | |

**El cálculo de sobreestadía de la planilla está midiendo otra cosa.** `AQ = AM − AG`
con `AG` vacío es `AM` a secas —la hora del reloj a la que terminó el CIP, como
fracción de día— y `AR = AQ − 2 h`. Un camión que terminó a las 18:00 «paga» 16
horas. El 31-07 el total del día fue **254 horas a pagar**, y no son sobreestadía.
Portar la fórmula tal cual sería portar el error, y este tiene consecuencia en plata.

Valores categóricos observados:

- **Procedencia** — `NESTLE` (305), `CCAA` (243), `COLUN` (5). `P. Unión`, que sí está
  en el modelo actual, **no aparece en julio**.
- **Uso** — 18 valores: `Despacho` (218), `Stock` (41), `Semi - n° 1..7` (194 en total),
  `LE` (34), `Entero - n° 3..5` (35), `Suero` (10), `DESP` (10, variante de `Despacho`),
  `Antibiotico` (2), `RC201` (1).
- **Certificado** — `Certificado` (541) / `No Certificado` (12).

El comentario de la celda `O15` explica para qué existe `Uso`: «a qué n° de
precondensado va ir esta leche, sirve para llevar trazabilidad y desviación de uso».

`RC201` aparece una sola vez y no es un uso: es un valor de RC anotado en la columna
equivocada. No entra al catálogo. Si alguna vez se importan los históricos, va a
`observacion`; inventarle una familia haría que el catálogo describiera un error de tipeo.

## 3. Decisiones tomadas antes de diseñar

1. **PPRO N°1 es el control de inhibidores**, no la higiene del camión. Lo rotulan así
   la hoja `Inhibidores` (`G4`) y el encabezado `AA13` de `Descarga Camiones`, que está
   sobre las columnas de antibiótico.
2. **No entra en `inocuidad.MonitoreoPPRO`**: ese modelo tiene FK obligatoria a `Lote`,
   y el PPRO N°1 cuelga de un camión y una fecha, no de un lote.
3. **La permanencia se cuenta desde el arribo a portería** (`HA`, 86 % de llenado), no
   desde la hora programa. Es lo que físicamente significa «permanencia en planta» y es
   el dato que existe.
4. **La recepción es una fila por camión.** Litros, silo, uso y todo lo demás son del
   camión; **solo la crioscopía se mide por módulo**.
5. **La app captura y calcula; no emite los formatos impresos.** Los derivados se
   exponen como datos. La emisión es una fase aparte.

---

## 4. Arquitectura

### 4.1 Forma del registro

`Recepcion` pasa a ser la fila del formato: **un camión, un registro**. Se agrega un
único hijo:

```
ModuloRecepcion
  recepcion          FK → Recepcion, related_name="modulos"
  numero             PositiveSmallInteger  1..4      (M1..M4 del formato)
  crioscopia         Decimal, nulable                (la única medida por compartimiento)
  carga_recoleccion  FK opcional → recoleccion.CargaModulo, nulable
```

Se retiran de `Recepcion`:

- `modulo` (CharField) — baja al hijo como `numero`.
- `llegada_id` (UUID) — existía para agrupar los módulos hermanos de un camión. Sin
  hermanos es una segunda identidad de la misma fila, y dos identidades para una cosa
  obligan a cada consumidor a elegir cuál usar.
- `carga_recoleccion` (OneToOne) — baja al hijo, porque la carga de recolección **sí** es
  por módulo. `diferencia_recoleccion_litros` pasa a comparar los litros del camión
  contra la **suma** de las cargas de sus módulos, y devuelve `None` si ningún módulo
  tiene carga vinculada.
- la clave `crioscopia` de `controles`, y con ella las constantes `CONTROLES_POR_MODULO`
  y `CONTROLES_POR_CAMION`, que dejan de tener sentido: todo `controles` es del camión.

**La migración de datos no colapsa filas.** Cada `Recepcion` histórica se convierte en sí
misma más un `ModuloRecepcion` que recibe su `modulo` y su `crioscopia`. Colapsar los
hermanos exigiría sumar litros de filas que pueden tener silo, estado o veredicto
distintos, y produciría un registro que nadie hizo. Las filas viejas quedan como están;
las nuevas se capturan de a una.

Si un `Recepcion` histórico no trae `modulo` ni `crioscopia`, se le crea igual un
`ModuloRecepcion` con `numero=1` y `crioscopia=None`: que la relación sea siempre no
vacía evita que cada consumidor tenga que distinguir el caso.

### 4.2 Campos nuevos de la cabecera

**Destino y procedencia**

| Campo | Tipo | Nota |
|---|---|---|
| `certificada` | `BooleanField(null=True)` | Nulo = no se registró, que no es lo mismo que «no certificado» |
| `uso` | `TextChoices` | `despacho`, `stock`, `semi`, `entero`, `le`, `suero`, `antibiotico` |
| `uso_numero` | `PositiveSmallInteger`, nulable | El `n°` de `Semi - n° 2`. Separado para poder preguntar qué entró a un precondensado |
| `Procedencia` | se agregan `CCAA` y `COLUN` | `P. Unión` se conserva por el histórico aunque no aparezca en julio |

`Uso` se parte en familia y número en vez de guardar la etiqueta completa porque la
pregunta que motiva el campo —«qué leche entró al Semi n°2»— no se puede hacer contra un
texto que además tiene variantes de tipeo (`DESP` por `Despacho`).

**Pesajes**

| Campo | Tipo | Nota |
|---|---|---|
| `kg_romana` | `Decimal(12,2)`, nulable | El pesaje real. Es captura |

`kg_guia` y la diferencia **no son campos**: se derivan, por la misma razón que el
veredicto de calidad no se persiste. En el formato `I = H × 1,03` y `M = J − I`.

**Analítica** — claves nuevas del JSONField `controles`:

| Clave | Tipo | Origen |
|---|---|---|
| `grasa` | numérico | Columna `Q` (SG) |
| `sng` | numérico | Columna `R` |
| `sangre`, `pus`, `materias_extranas`, `aroma` | `Conforme` / `No conforme` | Columnas `AC`–`AF`, que la planilla anota `IN`/`OUT` |

`ts` (= grasa + SNG, columna `S`) y `ts_kg` (= romana × ts %, columna `BF`) son derivados.

La clave `organoleptico` deja de escribirse pero **se sigue leyendo**: las filas
históricas la tienen, y el dominio la considera no conforme si vale `No conforme`. Los
cuatro ítems nuevos la reemplazan en la captura, porque el formato pide los cuatro por
separado y un único «no conforme» no dice qué se vio.

**Tiempos** — ocho `TimeField(null=True)` en la cabecera:

`hora_programa`, `hora_arribo_porteria`, `hora_ingreso`, `hora_inicio_descarga`,
`hora_termino_descarga`, `hora_inicio_cip`, `hora_termino_cip`, `hora_salida`.

Son columnas y no un modelo hijo porque son ocho marcas fijas, una sola vez por camión, y
se consultan y se suman. El campo `hora` actual queda como la hora de registro.

**Higiene del camión** — cuatro columnas más:

`lavado_ruedas` (bool nulable), `relavado` (bool nulable), `recambio_dilucion`
(`TextChoices`: `recambio`, `ok`), `ph_camion` (`Decimal(4,2)`, nulable).

`ph_camion` **no va en `controles`**: es el pH del enjuague del camión, con rango 5,5–8,5,
y no el de la leche. Mezclarlo con la clave `ph` haría que el pH del agua retuviera un
camión de leche conforme.

### 4.3 Inhibidores — PPRO N°1 y su escalamiento

```
ControlInhibidores            FK → Recepcion, related_name="controles_inhibidores"
  metodo         TextChoices  (tri_sensor, charm, delvo_sp)
  tiras_usadas   PositiveSmallInteger
  hora_lectura   TimeField
  resultado      TextChoices  (negativo, positivo)
  analista       FK → usuario, nulable

BusquedaProveedor             FK → ControlInhibidores, related_name="busquedas"
  proveedor      CharField
  charm_bet      TextChoices, blank   (negativo, positivo)
  charm_tetra    TextChoices, blank
  delvo_sp       TextChoices, blank
  hora_lectura   TimeField, nulable
  resultado      TextChoices  (negativo, positivo)
```

Regla nueva: **una recepción con inhibidores positivos no se puede cerrar sin al menos
una `BusquedaProveedor`.** Un positivo ya retiene hoy, y ahí termina todo; esto es el paso
siguiente que `REGLAS_DE_PLANTA.md` §1.2 marca como faltante. No sustituye a la cadena
completa del documento —bloqueo de camión, no conformidad, aviso a las dos áreas— pero
registra la búsqueda, que es su primer eslabón.

### 4.4 Dominio

Funciones puras en `recepcion/dominio.py`, cubiertas en `tests_dominio.py`:

| Función | Qué hace |
|---|---|
| `kilos_desde_litros(litros)` | Aplica `FACTOR_LITROS_A_KILOS` |
| `diferencia_pesaje(kg_guia, kg_romana)` | Romana menos guía, con su signo |
| `solidos_totales(grasa, sng)` / `solidos_totales_kg(kg, ts)` | Columnas `S` y `BF` |
| `crioscopia_pool(modulos)` | Promedio de los módulos con lectura. `None` si no hay ninguna |
| `permanencia(arribo, termino_cip, limite)` | Horas por sobre el límite, o `None` con motivo |
| `horas_a_pagar(horas)` | Redondeo comercial: sube si la fracción supera 0,5 |
| `tiempo_en_fabrica`, `tiempo_de_descarga` | Columnas `AW` y `AK − AJ` |
| `resumen_del_dia(recepciones)` | Totales por silo y por procedencia, promedios de SG y SNG, litros/kg del día, total de horas a pagar |

`evaluar_recepcion` se amplía: evalúa los cuatro ítems organolépticos, el `ph_camion`
contra 5,5–8,5, y la crioscopía **de cada módulo** en vez de una sola clave.

Dos reglas nuevas del cálculo de tiempos:

1. **Sin `hora_arribo_porteria` o sin `hora_termino_cip`, `permanencia` devuelve `None`
   con su motivo, nunca cero.** Es la corrección directa del defecto de la planilla: un
   dato ausente salía como un número, y el número se sumaba.
2. **Si el término de CIP es anterior al arribo, se suman 24 horas.** El turno C existe:
   un camión que arriba 23:30 y termina a 01:00 daría −22,5 h. La planilla no lo maneja
   porque opera sobre fracciones de día sin fecha.

Constantes declaradas, cada una en un solo lugar:

```python
FACTOR_LITROS_A_KILOS = 1.03
LIMITE_PERMANENCIA_HORAS = 2.0
LIMITES["ph_camion_min"] = 5.5
LIMITES["ph_camion_max"] = 8.5
```

El factor es `1,03` porque es el que usa la hoja operativa que produjo las cifras reales.
`Litros-kilos` usa `/0,97` (= 1,030928), y la discrepancia queda anotada junto a la
constante, igual que la de crioscopía en `REGLAS_DE_PLANTA.md` §1.3.

### 4.5 API y pantalla

- `RecepcionSerializer` gana los campos nuevos, los `modulos` anidados y los derivados de
  solo lectura (`kg_guia`, `diferencia_kg`, `ts`, `ts_kg`, `crioscopia_pool`,
  `permanencia_horas`, `horas_a_pagar`, `tiempo_en_fabrica`).
- `registrar-llegada/` cambia de contrato: recibe **un camión** con sus litros y su lista
  de módulos, donde cada módulo aporta solo `numero` y `crioscopia`.
- Endpoint nuevo `resumen-diario/?fecha=` con lo que la planilla totaliza abajo.
- Los catálogos de `uso`, `procedencia` y `recambio_dilucion` se sirven desde
  `/api/recepcion/catalogos/`, no se escriben en el frontend. `certificada` es un
  booleano y no necesita catálogo.
- Desaparecen los `SerializerMethodField` `controles_camion` y `controles_modulo`: partían
  los controles entre los que eran del camión y los del módulo, y esa división deja de
  existir. `controles` pasa a ser uno solo.
- La pantalla `/leche` organiza el formulario en los bloques del formato: identificación,
  destino, pesajes, analítica, tiempos, higiene. Los módulos son una tabla corta dentro
  del formulario, no una pantalla aparte.

### 4.6 Pruebas

- `tests_dominio.py` — todas las funciones nuevas. Casos obligatorios: permanencia sin
  arribo devuelve `None`; permanencia cruzando medianoche; redondeo comercial en 0,5
  exacto; `crioscopia_pool` con un solo módulo y con ninguno.
- `tests_hermanos.py` — se reescribe. Lo que fijaba (los módulos comparten los controles
  del camión) deja de existir como problema, porque hay un solo registro. Lo que queda
  vigente y hay que conservar: no se reescriben controles de una recepción ya liberada.
- Prueba de la migración: una `Recepcion` histórica con módulo y crioscopía queda con
  exactamente un `ModuloRecepcion` que los conserva, y una sin ellos queda con uno vacío.
- Prueba de la regla de inhibidores: positivo sin búsqueda a proveedor no cierra.

---

## 5. Qué queda fuera, y por qué

| Fuera | Motivo |
|---|---|
| Emisión de los seis formatos impresos | Decidido: capturar y calcular ahora, emitir después |
| Delvo por silo, permanencia > 48 h, control descremada | Son registros del **silo**, no del camión. Merecen su propio diseño |
| Columna `SAP` de la hoja `Diferencia` | Vacía en los 26 archivos. No hay con qué definir qué guarda |
| Importador de los históricos de julio | No se pidió. El modelo queda listo para recibirlos |
| Cadena completa de antibióticos de §1.2 | Bloqueo de camión, no conformidad y avisos exceden recepción. Se cubre el primer eslabón |
| Hora de inicio de recolección y de entrada a condensación | Están en `Perm. Silo`, y pertenecen a recolección y a condensación |

## 6. Riesgos declarados

1. **Cambio de contrato de `registrar-llegada/`.** El frontend y `tests_hermanos.py`
   dependen de la forma actual. Es un cambio coordinado backend/frontend en el mismo paso.
2. **`llegada_id` desaparece del serializer.** `frontend/src/services/recepcion.service.ts`
   lo tipa; hay que quitarlo de `Recepcion` y de `LlegadaCamionNueva`.
3. **`NESTLE` contra `Nestlé`.** Es el mismo defecto que obligó a la restricción
   `mandante_unico_por_codigo_cliente`. Los valores del modelo mandan; la normalización
   ocurre si alguna vez se importan los históricos, no en el modelo.
4. **`MovimientoSilo` tiene la restricción `una_descarga_por_recepcion`.** Con un registro
   por camión en vez de por módulo, un camión pasa a generar un único asiento. Es correcto
   y más simple, pero cambia el volumen del libro mayor: hay que verificar que
   `tests_movimientos_operacionales.py` siga en verde.
5. **El campo `hora`** convive con las ocho marcas nuevas. Queda como hora de registro; si
   la planta lo usaba como hora de llegada, hay que migrarlo a `hora_arribo_porteria`.
   Se deja como está y se anota, porque decidirlo sin la planta sería inventar.
