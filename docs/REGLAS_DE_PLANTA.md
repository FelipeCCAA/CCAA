# Reglas de planta — umbrales, decisiones y fórmulas

**Origen:** `Flujo Fabrica.md` (2026-08-05), secciones 4–20 y 25–27.
**Estado:** extraído y contrastado contra el código el 2026-08-05.

---

## Para qué existe este archivo

`Flujo Fabrica.md` mezcla dos cosas: conocimiento de planta —umbrales reales,
puntos de decisión, fórmulas— y un encargo dirigido a una IA («Actúa como
arquitecto…», §1 y §29). Lo segundo caduca en cuanto se usa; lo primero es lo
que hay que poder citar dentro de cinco años cuando alguien pregunte de dónde
salió un límite.

Este archivo separa lo primero. Cada regla lleva **su umbral, qué dispara, de
dónde sale y si está implementada**. La última columna es la que hace útil el
documento: sin ella es una lista de buenas intenciones.

Lo que **no** va aquí: recomendaciones de arquitectura, listas de tecnología y
fases de implementación. Eso se decide, no se hereda.

---

## 0. Recolección en predios

| Regla | Estado |
|---|---|
| Prueba de alcohol **positiva** → la leche no sube al camión | **Implementado** — `recoleccion.CargaPredio.clean()` |
| Evaluación visual no conforme → no se carga | **Implementado** |
| Leche que no se carga exige decir **por qué** (la desviación que se le informa al proveedor) | **Implementado** |
| Leche cargada exige indicar en **qué módulo** | **Implementado** — `CheckConstraint` |
| A un proveedor **bloqueado** no se le recolecta | **Implementado** — el bloqueo lo pondrá la cadena de antibióticos (§1.2) |

La app `recoleccion` modela **ruta → parada → recolección → carga de módulo**,
con `idempotencia` UUID para la captura sin señal en el predio. Está enlazada a
recepción por `Recepcion.carga_recoleccion` y `Recepcion.modulo`.

**Lo que falta, y es lo que impide la regla de antibióticos:** `proveedor`,
`predio`, `sala` y `modulo` son `CharField` de texto libre, y `conductor`
apunta a `User` cuando la mayoría de los conductores no entra al sistema.
«Bloquear los módulos asociados al proveedor» (§1.2) no se puede expresar
contra un string, y la trazabilidad hacia atrás llega a un texto en vez de a un
proveedor. Convertirlos en referencias a maestros es el mismo trabajo que ya se
hizo con los equipos.

---

## 1. Recepción de leche fresca

### 1.1 Umbrales

| Control | Límite | Qué dispara | Estado |
|---|---|---|---|
| Temperatura | ≤ **8 °C** en recepción (objetivo ~4 °C en predio) | Sobre el límite: retener, informar y evaluar | **Implementado** — `recepcion.dominio.LIMITES["temperatura_max"] = 8.0` |
| Crioscopía | ≥ **−0,512 °C** sugiere agua añadida | Repetir análisis · revisar pool · identificar origen · informar Calidad | **Implementado con otro valor** — ver §1.3 |
| Acidez | ≤ 18,0 | Retiene | Implementado. **No viene de este documento**, viene de `MODELO_DATOS.md` §8.5 |
| pH | 6,5 – 6,9 | Retiene | Implementado. Mismo origen que la acidez |
| pH del camión | 5,5 – 8,5 | Retiene | **Implementado** — `recepcion.dominio.LIMITES["ph_camion_min"/"ph_camion_max"]`, columna AO del formato |
| Permanencia libre | 2 h desde el arribo a portería | Sobre eso, sobreestadía | **Implementado** — `recepcion.dominio.LIMITE_PERMANENCIA_HORAS` |

### 1.2 Antibióticos

El documento describe una cadena completa:

```
POSITIVO → repetir análisis → ¿se confirma?
                                   │
                                  SÍ → bloquear camión
                                     → no descargar
                                     → identificar proveedor
                                     → bloquear módulos asociados
                                     → informar Operaciones
                                     → informar Calidad
                                     → abrir no conformidad
```

**Lo que ya existe:** un `delvo` o `inhibidores` positivo **retiene la
recepción automáticamente**, y `delvo` es control decisivo — sin su resultado
no se puede liberar, porque su ausencia no es «conforme», es que nadie lo
midió (`recepcion/dominio.py`).

**Lo que ya existe además** (desde 2026-08-19): `ControlInhibidores` documenta el PPRO
N°1 —método, tiras usadas, hora de lectura, resultado, analista— y `BusquedaProveedor` el
primer eslabón del escalamiento. Pero el gatillo del bloqueo sigue sin ser el resultado
del control: `dominio.bloqueos_de_cierre` solo mira
`Recepcion.controles["delvo"]`/`["inhibidores"]` y el conteo de `BusquedaProveedor`, y
**nunca lee `ControlInhibidores.resultado`**. `ControlInhibidores` tampoco tiene ViewSet
ni URL propia —se carga por admin o por ORM—, así que hoy se puede registrar un PPRO N°1
positivo sin que el cierre lo sepa: una recepción **no se puede cerrar** solo si
`controles["inhibidores"]` (o `["delvo"]`) dice `"Positivo"` y no hay ninguna
`BusquedaProveedor` registrada. Que el control dispare el bloqueo por sí mismo —cerrando
del todo ese primer tramo de la cadena de arriba— es una decisión de Calidad, no del
código.

**Lo que sigue faltando:** la repetición del análisis y su confirmación, el bloqueo del
camión, la apertura de la no conformidad, los avisos a Operaciones y a Calidad, y el
concepto de **proveedor como entidad** — `BusquedaProveedor.proveedor` sigue siendo un
`CharField` de texto libre, igual que en `recoleccion` (§0), así que «bloquear los
módulos asociados al proveedor» sigue sin poder expresarse.

### 1.3 Discrepancia de crioscopía — pendiente de resolver

| | Valor |
|---|---|
| `Flujo Fabrica.md` §6.3 | **−0,512 °C** |
| `recepcion/dominio.py` | **−0,510 °C** |

No es un error de tipeo indiferente: la crioscopía detecta aguado, y un valor
**menos negativo** que el límite es sospechoso. El código es más estricto
(−0,510 retiene antes que −0,512), así que la diferencia no deja pasar leche
aguada — retiene un poco de leche que el documento aceptaría.

El comentario del código dice que los límites son «REFERENCIALES y están
pendientes de confirmar con Calidad». Este documento parece ser esa
confirmación. **Falta que Calidad diga cuál manda** antes de tocar el número.

### 1.4 Estados del documento

```
REGISTRADO → ESPERANDO MUESTREO → EN ANÁLISIS → ANÁLISIS COMPLETADO
           → APROBADO PARA DESCARGA → DESCARGANDO → DESCARGADO

alterna:  EN ANÁLISIS → RETENIDO → REANÁLISIS → RECHAZADO → BLOQUEADO
                     → DESTINO DEFINIDO
```

**Regla dura (§7.3):** no se puede registrar una descarga si el módulo no está
en `APROBADO PARA DESCARGA`.

El sistema ya impide descargar una recepción retenida, pero con una máquina de
estados más corta que ésta.

La transición a `CERRADA` pasa ahora por la acción `cerrar/`, que consulta
`dominio.bloqueos_de_cierre`. Antes ningún camino del API llevaba a ese estado.

---

## 2. Descremación

| Parámetro | Valor | Estado |
|---|---|---|
| RPM de la descremadora | **1.395 RPM** | No implementado |
| Materia grasa de leche descremada | **≤ 0,1 %** | No implementado |
| Materia grasa de crema para despacho | **42 % – 43 %** | No implementado |

Si no alcanza las RPM: quitar alarma, reintentar, informar a Mantenimiento.

Control cada hora sobre descremadora, pasteurizador, bombas, válvulas,
conexiones, caudalímetros, temperaturas, fugas y obstrucciones.

**No existe el proceso de descremación en el sistema.** Ninguno de estos
valores tiene dónde vivir todavía.

---

## 3. Estandarización — la fórmula RC

```
RC = % materia grasa / % sólidos no grasos
```

Es el cálculo central de la fábrica: decide qué producto sale. Los productos
se nombran por su RC (`RC 0,201`, `RC 0,422`), y el maestro de productos ya usa
esos nombres.

El flujo del documento (§10):

1. Consultar leche entera disponible: cantidad, grasa, SNG.
2. Consultar descremada: cantidad, grasa, SNG.
3. Calcular leche entera requerida, leche a descremar, descremada a agregar,
   crema esperada y producto final esperado.
4. Generar **hoja RC**.
5. Transferir, agitar **30 minutos**, tomar muestra, analizar.
6. Calcular **RC real**.
7. Si cumple: liberar silo y avisar a Condensación. Si no: calcular corrección,
   agregar leche entera o descremada, reagitar y reanalizar.

**La matemática está implementada** en `estandarizacion/dominio.py`, sin ORM y
comprobada recalculando: las pruebas no verifican que la fórmula esté escrita,
sino que la mezcla que devuelve **dé el RC pedido**.

| Función | Qué responde |
|---|---|
| `calcular_mezcla` | cuántos litros de entera y de descremada para un RC y un volumen |
| `evaluar_rc` | si el RC medido después de agitar cumple, y qué agregar si no |
| `litros_a_agregar` | cuántos litros de la leche correctora hacen falta |

Tres decisiones del cálculo:

- **Un objetivo inalcanzable se dice, no se calcula.** La fórmula devolvería un
  volumen negativo o mayor que el total; entregarlo sería darle a alguien un
  número para teclear en una válvula.
- **Que falte leche avisa pero no impide calcular.** El operador puede estar
  planificando contra un silo que se está llenando.
- **La tolerancia del RC es un parámetro.** La define Calidad; el valor por
  omisión (0,005) es referencial.

### 3.1 Un límite físico que el cálculo destapó

**RC 0,422 exige leche entera de al menos ~3,63 % de grasa** (con 8,6 % de SNG).
Mezclar entera con descremada solo **baja** el RC —nunca lo sube por encima del
de la entera—, así que con leche al 3,6 % ese producto no se puede estandarizar:
habría que agregar crema.

No es una limitación del programa. En planta se traduce en «esta leche no da
para el producto de RC 0,422», que es una decisión de qué producir. El sistema
lo dice con el detalle de en cuánto está cada leche.

### 3.2 El vale, con su ciclo (aplicado 2026-08-06)

`estandarizacion.ValeEstandarizacion` es la hoja RC del paso 4, y el eslabón que
la trazabilidad hacia atrás necesita entre el precondensado y los silos de leche
fresca. Su ciclo es el de los pasos 5 a 7:

```
calculado → transferido → agitando → muestreado ┬ conforme    → liberado
                              ↑                 └ no conforme → corrigiendo ┘
```

Cada paso es una acción del servicio y no un `PATCH estado=…`, y hay tres reglas
que solo se sostienen así:

- **Muestrear antes de los 30 minutos avisa, no bloquea** (`MINUTOS_DE_AGITACION`,
  decisión de planta del 2026-08-17). Una muestra tomada antes mide una mezcla
  que todavía no es homogénea, así que el vale queda con el aviso y con la hora
  del muestreo en `muestreado_en` — que es lo que después permite auditar cuánto
  agitó de verdad. Antes la rechazaba, y entonces no quedaba constancia de nada.
  La hora la sigue poniendo el servidor: aceptarla del cliente permitiría
  declarar treinta minutos que no ocurrieron.
- **Liberar no se pide, se calcula.** `decidir` no acepta el destino; lo deduce
  del RC medido.
- **Corregir reinicia el reloj y borra el análisis.** Agregar leche deshace la
  homogeneidad.

La composición de las dos leches se guarda **en el vale**, no se lee del silo al
mirarlo: el silo cambia con cada ingreso y un vale de mayo se audita contra la
leche que había en mayo. `rc_real` se calcula y no se guarda.

`calcular/` responde la mezcla **sin crear el vale** —es el paso que el operador
repite variando el volumen— y la pantalla (`/estandarizacion`) no ofrece crear
hasta que hay una mezcla posible: un vale imposible se descubriría después de
transferir.

**Lo que falta:** la crema como tercera entrada de la mezcla, que es lo que
haría estandarizable un RC 0,422 con leche pobre (§3.1). Pendiente de confirmar
con Fabricación si en planta se hace así.

---

## 4. Condensación y secado

| Regla | Estado |
|---|---|
| PCC de uperización con límite por equipo | **Implementado** — `produccion.ControlProceso`, límites por registro |
| Checklist de cuerpos extraños por evaporador | **Implementado** — tres plantillas distintas (SCH2, SCH3, VEB) |
| Inspección preoperativa E1/E2 | **Implementado** — plantilla cargada |
| Monitoreo PPRO E1-E2 y Rovemas | **Implementado** — `inocuidad.MonitoreoPPRO` |
| Detector de metales (PCC) | **Implementado** |

Los evaporadores son **Scheffers 2, Scheffers 3 y VEB**; las torres, **Egron 1
y 2**; las envasadoras, **Rovema 3 y 4**. Todos existen en `maestros.Equipo`.

---

## 5. Reglas de negocio esenciales (§25)

Las quince del documento, contrastadas:

| # | Regla | Estado |
|---|---|---|
| 1 | No descargar leche sin aprobación de Calidad | Implementado |
| 2 | No utilizar un silo bloqueado | Parcial |
| 3 | No iniciar producción con equipo sin aseo aprobado | **Parcial** — ver §5.1 |
| 4 | No cerrar una etapa con controles obligatorios pendientes | Implementado en `procesos` |
| 5 | No liberar un lote con dossier incompleto | Implementado |
| 6 | No consumir material en cuarentena | Implementado |
| 7 | No agregar rework sin autorización | **Implementado** — ver §5.2 |
| 8 | No modificar registros aprobados sin nueva versión | Parcial |
| 9 | Toda corrección deja auditoría | Implementado — app `auditoria` |
| 10 | Los documentos obsoletos no generan tareas | Implementado — `activo` |
| 11 | Trazabilidad hacia atrás y adelante | Implementado — `procesos.genealogia_lote` |
| 12 | Falla crítica de inocuidad bloquea el lote | Implementado — PCC 1 y PPRO, **sin concesión** |
| 13 | Estados cambian por acciones controladas | Implementado |
| 14 | Aprobaciones registran usuario, fecha y hora | Implementado |
| 15 | Un equipo no puede producir y estar en CIP a la vez | **Implementado** — ver §5.1 |

**Las quince están implementadas.** Lo que sigue faltando del rework no es la
regla sino su ciclo completo — ver §5.2.

### 5.1 Habilitación del equipo por aseo

`inventario.servicios.motivo_equipo_no_habilitado()` y `equipo_produciendo()`,
enganchados en `procesos.transicionar_ejecucion` (al entrar en EJECUCIÓN) y en
`CicloCIPSerializer` (al poner un CIP EN CURSO).

Lo que impide hoy:

- Producir con un CIP **en curso** sobre ese equipo (regla 15).
- Producir cuando el último aseo del equipo quedó **observado** (§18.5: aseo
  crítico rechazado → equipo no habilitado). Un aseo conforme posterior lo
  rehabilita: bloquea hasta que otro lo reemplace, no para siempre.
- Iniciar un CIP sobre un equipo **produciendo** (regla 15 por el otro lado).
  Con una sola dirección, la regla se cumplía o no según cuál de las dos
  acciones llegara primero.

Un CIP **programado** no bloquea: todavía no ocurrió, y tratarlo como resultado
detendría la producción por un aseo futuro.

**Lo que falta y por qué:** la **caducidad** del aseo — «el CIP del martes ya
no sirve el viernes»—. Cuánto dura un aseo lo decide Calidad y no está escrito
en ninguna parte; inventar una ventana sería peor que no tenerla, porque
bloquearía producción con un número que nadie acordó. Es la quinta decisión
pendiente de §8.

### 5.2 Rework autorizado

`EntradaProceso._validar_autorizacion_de_reproceso()`. Una entrada de tipo
**reproceso** exige que su lote tenga liberación de Calidad en `liberado` o
`liberado_concesion`.

La concesión autoriza porque es Calidad diciendo «úsalo bajo estas
condiciones», que es precisamente una autorización. `pendiente`, `en revisión`
y `rechazado` no autorizan, y **la ausencia de liberación tampoco**: un lote
sin expediente tramitado no es uno aprobado, es uno que nadie miró. Es la misma
distinción que hace la recepción con el Delvo.

La regla es solo del reproceso. Exigirla a toda entrada detendría la producción
normal: la leche que entra al evaporador no se libera — se libera lo que sale.

**Lo que falta del ciclo de rework** (§17 del flujo de fábrica): pesar, rotular,
almacenar segregado, la evaluación explícita de Calidad sobre el rework como
tal, el paso a descarte y el `Seguimiento FEFO`. Hoy el reproceso se expresa
con `SalidaProceso.Naturaleza.REPROCESO` y `EntradaProceso.Tipo.REPROCESO`,
que cubren la trazabilidad pero no el circuito de bodega.

---

## 6. Trazabilidad completa (§26)

La cadena hacia atrás que la planta necesita poder recorrer:

```
LOTE TERMINADO → pallets → bolsas → Rovema → silo de polvo → torre Egron
               → precondensado → evaporador → vale de estandarización
               → silos de leche fresca → camiones → módulos → proveedores
```

**Hasta dónde llega hoy:** `procesos.genealogia_lote` recorre lote a lote por
las entradas y salidas de proceso. Cubre desde el precondensado hacia adelante.

**El otro extremo ya existe:** `recoleccion` cubre proveedor → predio → carga →
módulo → camión (§0).

**Dónde se corta:** en el medio. Faltan el **vale de estandarización** —que no
existe— y el **enlace entre recolección y recepción**: hoy las dos puntas de la
cadena están construidas y no se conocen entre sí.

---

## 7. Lo que este documento aporta y no estaba en ninguna parte

1. La cadena de escalamiento de antibióticos (§1.2).
2. La fórmula RC y el procedimiento de estandarización (§3).
3. Los parámetros de descremación (§2).
4. El umbral de crioscopía, que además contradice al código (§1.3).
5. El tiempo de agitación —30 minutos— antes de tomar muestra.

---

## 8. Lo que queda por decidir

| Decisión | Quién |
|---|---|
| Crioscopía: ¿−0,512 o −0,510? | Calidad |
| ¿`OrdenProduccion` sobre `Lote` como unidad central? | TI + planta |
| ¿Dieciocho roles con permisos por acción, o el modelo actual de rol × área? | TI |
| Qué controles de recepción son obligatorios además del Delvo | Calidad |
| ¿Cuánto vale un aseo? Sin ventana de caducidad, un CIP viejo habilita igual | Calidad |

---

## Nota sobre las secciones no extraídas

`Flujo Fabrica.md` §21–24 y §29 recomiendan Redis, Celery, Celery Beat, Docker
y Nginx sin nombrar el problema que resuelven. No se extraen aquí porque no son
reglas de planta.

Dicho eso, hay **un** motivo real para un programador de tareas y conviene
dejarlo anotado: `actualizar_alertas_inventario()` solo corre cuando alguien
mueve stock, así que un lote que entra a cuarentena un viernes no genera la
alerta de «cuarentena atrasada» hasta que alguien toca el inventario el lunes —
justo la alerta que existe para avisar de eso.
