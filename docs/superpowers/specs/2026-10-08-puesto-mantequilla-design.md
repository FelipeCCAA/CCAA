# Puesto de Mantequilla

**Fecha:** 2026-10-08
**Origen:** revisión UX industrial de los menús de fabricación (2026-10-02). Cuarto y último
de los puestos por proceso; sigue el patrón de Evaporación
(`docs/superpowers/specs/2026-10-05-puesto-evaporacion-design.md`), Secado
(`docs/superpowers/specs/2026-10-06-puesto-secado-design.md`) y Descremado
(`docs/superpowers/specs/2026-10-07-puesto-descremado-design.md`).
**Guía de criterio:** `.agents/skills/disenador-ux-industrial/SKILL.md`.

---

## 1. El problema

Hoy hacer mantequilla son **3 pasos en una sección de `/procesos`**, con dos entradas que
no llevan a ninguna corrida concreta:

| Paso | Dónde | Qué |
|---|---|---|
| 0 | `/silos` › TK › «Iniciar Mantequilla», o `/produccion` › Salidas intermedias › «Iniciar Mantequilla» | enlace a `/procesos?seccion=mantequilla`, sin la crema elegida |
| 1 | `/procesos` › «Línea de mantequilla» › «Nueva corrida» › modal `NuevaMantequilla` | OP, lote de crema con saldo, kg, línea/equipo, suero opcional, **código de lote tecleado** → `crear-guiada` (ejecución `borrador`, lote de salida `en_proceso`, corrida `borrador`) |
| 2 | `/procesos` › sección (no autocarga: «Cargar corridas») › «Iniciar con esta crema» | `iniciar`: pasa la ejecución `borrador` → `preparacion` → `ejecucion` en una sola llamada, descuenta el TK de crema y crea la entrada |
| 3 | misma sección › «Registrar balance y cerrar» › modal `CierreMantequilla` | kg de mantequilla, suero, merma y reproceso; balance calculado en el cliente (`services/balance-mantequilla.ts`) |

- **Una corrida preparada no ocupa la máquina.** La ejecución nace en `borrador`, que no
  está en `ESTADOS_QUE_OCUPAN_EQUIPO`: dos corridas pueden prepararse en la misma línea y la
  segunda recién choca al iniciar. Y una corrida que no se inicia nunca deja un lote de
  salida `en_proceso` que nadie anula: no hay «Cancelar preparación», y cancelar la
  ejecución desde la bandeja genérica deja la corrida en `borrador` y el lote vivo.
- **No hay regla de inicio que la pantalla pueda consultar.** Las comprobaciones viven en
  línea dentro de `iniciar_mantequilla`, cada una con su `raise ValidationError`; el botón
  «Iniciar con esta crema» se ofrece siempre y el rechazo llega con el POST.
- **La pantalla ofrece lo que el servidor rechaza.** `opciones-alta` ofrece la crema con
  saldo sin restar lo que otras corridas preparadas ya pidieron; la segunda corrida sobre
  la misma crema se prepara y su inicio la rechaza. El equipo «ocupado» lo decide el
  cliente cruzando `opciones-alta.equipos[].ocupado_por` con `ocupacionesPorEquipo` sobre
  las ejecuciones que cargó (caso 1 de «La pantalla ofrece lo que el backend va a
  rechazar» en `CLAUDE.md`).
- **Hay dos implementaciones del balance.** `calcularBalanceMantequilla` (cliente, en
  milésimas) decide si se habilita «Cerrar y enviar a Calidad», y `CorridaMantequilla.clean()`
  (servidor) lo vuelve a decidir al cerrar con su propia aritmética. Coinciden hoy por
  casualidad de redondeo, no por construcción.
- **La máquina no es un tipo.** La etapa Mantequilla acepta `{LINEA, OTRO}`
  (`tipos_equipo_para_etapa`, y una copia literal en `crear_mantequilla_guiada` y en
  `opciones-alta`): cualquier línea de envasado o cualquier «otro» aparece como mantequera,
  y `preparar-continuacion` con la etapa Mantequilla crea una ejecución **sin**
  `CorridaMantequilla` que ninguna pantalla sabe cerrar.
- **El permiso de la pantalla no es el del servidor.** La sección ofrece «Nueva corrida»,
  «Iniciar» y «Cerrar» con `puedeEscribir("produccion")`; el viewset exige la etapa
  Mantequilla (`OperaProcesoPorEtapa`, área Condensación). Un operador de Secado ve el
  formulario entero y recibe un 403 al final.

## 2. Decisiones

Tomadas por el controlador con autorización del usuario el 2026-10-08; revisables.

| Decisión | Elegido |
|---|---|
| Lugar | **Puesto propio** en `/produccion/mantequilla`: una tarjeta por mantequera, una acción servida por estado (*disponible* → «Preparar mantequilla»; *preparada* → «Iniciar mantequilla», habilitada solo cuando el servidor lo permitiría, con el motivo y dónde se resuelve; *en curso* → «Registrar balance y cerrar»), «Cancelar preparación» (motivo + `ConfirmarAccion`; suelta la máquina y anula el lote de salida que se abrió), corridas de hoy e historial con filtros de servidor y una tabla de situaciones como Descremado |
| Preparar e iniciar | **Dos pasos**: «Preparar» es el `crear-guiada` de hoy, pero la ejecución pasa a `preparacion` y toma la mantequera (como Descremado); «Iniciar» es otra acción con **una** regla, `motivos_tipados_para_iniciar_mantequilla`, que usa `iniciar` y sirve `GET procesos/mantequillas/puesto/`. La transición genérica rechaza `preparacion` → `ejecucion` para Mantequilla (`MENSAJES_INICIO_EN_PUESTO`) |
| Tipo de máquina | **`Equipo.Tipo.MANTEQUERA`** («Mantequera»); `tipos_equipo_para_etapa(MANTEQUILLA) = {MANTEQUERA}`. Una migración de datos reclasifica los equipos que ya usó `CorridaMantequilla` y deja las demás líneas y «otro» como están. `abre_desde_vale` no cambia: una mantequera no abre lotes desde un vale. Los comandos de preparación de E2E que creaban la máquina de mantequilla crean una mantequera |
| Balance del cierre | **Lo valida el servidor con una sola función pura** en `procesos/dominio.py` (mantequilla + suero + merma + reproceso contra kg de crema, con la misma tolerancia que usa hoy el cliente). La usan `cerrar_mantequilla` (rechaza si no cuadra) y un `revisar-cierre/` nuevo que no escribe y que el formulario pide mientras se teclea. `balance-mantequilla.ts` se elimina |
| Entrada | **Una sola**: el enlace del silo/TK y de Salidas intermedias, y el viejo `/procesos?seccion=mantequilla`, llevan al puesto; el menú, `rutaDeEtapa` y `RUTAS_POR_ETAPA` apuntan a él. La sección de `/procesos` y sus modales se retiran |
| Permiso | La etapa Mantequilla (área Condensación) **en todos los caminos**: preparar, iniciar, cancelar, revisar el cierre y cerrar |

## 3. Backend

### 3.1 Estado del puesto

`GET procesos/mantequillas/puesto/` (el viewset ya está registrado como `mantequillas` en
`procesos/urls.py`) devuelve:

```json
{
  "mantequeras": [{
    "equipo_id": 15, "codigo": "linea_mantequilla", "nombre": "Línea de mantequilla",
    "tipo": "mantequera",
    "estado": "disponible | preparada | en_curso",
    "corrida": { "id": 9, "estado": "borrador", "ejecucion_id": 140,
                  "ejecucion_codigo": "EJ-MANT-311", "ejecucion_estado": "preparacion",
                  "orden_codigo": "OP-0412", "producto": "Mantequilla sin sal 20 kg",
                  "lote_mantequilla": "CCAA6281LM-01", "lote_crema": "INT-DES-7-CR",
                  "kg_crema": "60.000", "lote_suero": "MAZ-E2E-20261008-1",
                  "iniciada_en": null },
    "motivos_para_tomar": [],
    "motivos_para_iniciar": ["TkC2: El análisis requiere firma de realización y visualización."],
    "resolver_en": "/silos | /calidad | /calidad/inocuidad | /planificacion | null",
    "avisos": ["Último aseo con observación: …"],
    "en_calidad": { "id": 8, "ejecucion_codigo": "EJ-MANT-300",
                    "lote_mantequilla": "CCAA6280LM-01" }
  }],
  "ordenes": [{ "id": 412, "codigo": "OP-0412", "producto": "Mantequilla sin sal 20 kg" }],
  "cremas": [{ "id": 77, "codigo": "INT-DES-7-CR", "producto": "Crema intermedia",
               "disponible_kg": "940.000", "tk": "TkC2" }],
  "cremas_pendientes_calidad": [{ "id": 78, "codigo": "INT-DES-8-CR", "producto": "Crema intermedia",
                                  "estado_calidad": "pendiente | rechazado | trazabilidad_incompleta",
                                  "etapa_origen": "Descremación" }],
  "sueros": [{ "id": 90, "codigo": "MAZ-E2E-20261008-1", "producto": "Mazada de mantequilla intermedia CCAA" }],
  "corridas_de_hoy": [{ "id": 8, "ejecucion_codigo": "EJ-MANT-300", "equipo": "linea_mantequilla",
                        "lote_mantequilla": "CCAA6280LM-01", "lote_crema": "INT-DES-6-CR",
                        "estado": "pendiente_calidad", "estado_etiqueta": "Pendiente de Calidad",
                        "estado_ejecucion": "pendiente_control",
                        "situacion": "esperando_calidad", "situacion_etiqueta": "Esperando Calidad" }],
  "estados": [{ "valor": "preparada", "etiqueta": "Preparada" }]
}
```

- **Qué máquinas**: las mantequeras activas (`tipo = mantequera`) **y** cualquier equipo
  que tenga una ejecución de Mantequilla que lo ocupe aunque no sea mantequera (un dato
  heredado de antes de la migración, §3.6). Sin lo segundo, una corrida abierta sobre una
  línea que la migración no reclasificó quedaría sin tarjeta y sin cómo cerrarla.
- **Estado por mantequera**, derivado de su `EjecucionProceso` de Mantequilla que ocupa el
  equipo (`ESTADOS_QUE_OCUPAN_EQUIPO`): `preparacion` → `preparada`; `ejecucion`,
  `pausada` o `bloqueada` → `en_curso`; sin ejecución que la ocupe → `disponible`. Una en
  curso manda sobre una preparada. Una ejecución `cerrada` o `cancelada` no ocupa la
  máquina aunque su corrida haya quedado en `borrador`/`en_proceso`
  (`ESTADOS_EJECUCION_TERMINALES`, igual que en los otros puestos). Una ejecución en
  `pendiente_control` tampoco la ocupa: la mantequera queda `disponible` y la corrida se ve
  en `en_calidad`.
- **`motivos_para_iniciar`** (solo en `preparada`) los calcula
  `motivos_tipados_para_iniciar_mantequilla` (§3.3); `resolver_en` es el destino del
  **primer** motivo, tipado (`RESOLVER_CIP`, `RESOLVER_CALIDAD`, `RESOLVER_SILOS` y un
  `RESOLVER_PLANIFICACION = "/planificacion"` nuevo), o `null`. La pantalla no lee el texto.
- **`motivos_para_tomar`** (solo en `disponible`): `motivo_equipo_no_habilitado` sobre la
  mantequera, la misma regla con que «Preparar» la rechaza (§3.2).
- **`avisos`** no bloquean: el aseo con advertencia (`advertencia_aseo_equipo`, el mismo
  texto que va al evento al iniciar).
- **`en_calidad`**: la última corrida de esa mantequera con la ejecución en
  `pendiente_control`. Informativa: la máquina está libre, pero su mantequilla espera la
  decisión de Calidad.
- **`ordenes`**: OP de categoría mantequilla `programada` o `en_proceso` (lo que hoy sirve
  `opciones-alta`).
- **`cremas`**: lotes de familia crema `producido`/`cerrado`, **liberados** por Calidad y
  con `disponible_kg > 0`. `disponible_kg` sale de **una** función,
  `kg_crema_disponible(lote, *, excluir_corrida_id=None)` en `procesos/servicios.py`:
  `kg_producidos` − entradas en kg que no son preparación cancelada (`PREPARACION_CANCELADA`)
  − `kg_crema` de las **otras** corridas preparadas (corrida `borrador` con ejecución no
  terminal). La usan esta lista, «Preparar» y el inicio: una cantidad, una consulta (caso 1
  de «La pantalla ofrece…»). `tk` es el TK donde está la crema, si lo hay, para que el
  operador sepa de dónde va a salir.
- **`cremas_pendientes_calidad`**: lo mismo que hoy sirve `opciones-alta` (pendiente,
  rechazada o con trazabilidad incompleta), para explicar por qué una crema no aparece.
- **`sueros`**: lotes de categoría suero en `borrador`/`en_proceso`, sin kilos y sin una
  corrida de mantequilla **viva** que ya los tome (las corridas `anulada` no cuentan: §3.4).
- **`corridas_de_hoy`**: corridas creadas, iniciadas o cerradas hoy, sin huérfanos cuya
  ejecución terminó sin iniciarse, con su situación (§3.5).
- **`estados`**: las opciones del filtro del historial, las mismas situaciones que muestra
  la columna (`catalogo_situaciones_mantequilla`).
- Montos decimales viajan como **texto**, como en los otros puestos.
- **Lectura**: las áreas que hoy ven Mantequilla en el menú (Condensación, Calidad) y
  administradores. El `GET` ya pasa por `OperaProcesoPorEtapa` como lectura.

`opciones-alta/` **se elimina**: todo lo que servía lo sirve `puesto/` con la regla de
arriba, y una segunda fuente para las mismas listas es justo lo que dejó al cliente
decidir la ocupación por su cuenta.

### 3.2 Preparar

`POST procesos/mantequillas/crear-guiada/` conserva la URL y el cuerpo (`orden`,
`lote_crema`, `equipo`, `codigo_lote_mantequilla`, `kg_crema`, `lote_suero` opcional) y
cambia su efecto. `crear_mantequilla_guiada`, en una transacción:

1. Valida la OP (categoría mantequilla, `programada`/`en_proceso`), la etapa Mantequilla
   activa de su ruta y el suero, como hoy.
2. Valida la mantequera: activa, de tipo `mantequera` (`tipos_equipo_para_etapa`, no una
   lista literal) y **habilitada** (`motivo_equipo_no_habilitado`: no en CIP). Hoy una
   línea en CIP se prepara y el rechazo llega al iniciar.
3. Valida la crema con **las mismas funciones** que el inicio (§3.3): familia crema, lote
   `producido`/`cerrado`, liberada por Calidad y `kg_crema ≤ kg_crema_disponible(lote)`.
   Las condiciones del TK (análisis, firmas, CIP, saldo en litros) **no** frenan la
   preparación: cambian entre preparar e iniciar y son motivos de inicio, con su enlace.
4. Crea el lote de salida (`en_proceso`, código del operador; §8.6), la ejecución
   `EJ-MANT-{lote.pk}` y la corrida `borrador`, como hoy.
5. **Transiciona la ejecución `borrador` → `preparacion`**, que toma la mantequera
   (`adquirir_equipo`) y rechaza una ocupada.

Cualquier `ValidationError` revierte todo: ni lote, ni ejecución, ni corrida, ni máquina
ocupada. Preparar **no** mueve crema: ni entrada ni salida del TK. Hasta iniciar, la crema
no entró a la mantequera.

`preparar_continuacion` **rechaza** la etapa Mantequilla con «La mantequilla se prepara en
el puesto de Mantequilla.»: hoy crea una ejecución sin `CorridaMantequilla` sobre
cualquier equipo compatible, y esa ejecución no tiene cierre ni balance.

### 3.3 Iniciar

`POST procesos/mantequillas/{id}/iniciar/`:

- `motivos_tipados_para_iniciar_mantequilla(corrida, *, ejecucion=None)` en
  `procesos/servicios.py` es **la única implementación** de las reglas de inicio, como pares
  `(motivo, resolver_en)`; `motivos_para_iniciar_mantequilla` devuelve los textos. Extraída
  de lo que hoy comprueba `iniciar_mantequilla`, en ese orden:
  - la corrida está en `borrador` y su ejecución en `preparacion` → `null`;
  - `corrida.clean()` pasa → `null`;
  - la OP está `programada` o `en_proceso` → `RESOLVER_PLANIFICACION`;
  - la mantequera está habilitada (`motivo_equipo_no_habilitado`: no en CIP) →
    `RESOLVER_CIP`;
  - el lote de crema sigue `producido`/`cerrado` (no anulado) → `null`;
  - la crema está **liberada** por Calidad (una salida suya con `LiberacionProceso`
    `liberado`, la misma condición que `cremas`) → `RESOLVER_CALIDAD`;
  - `kg_crema ≤ kg_crema_disponible(lote, excluir_corrida_id=corrida.pk)` → `null`;
  - si la crema está en un TK: el análisis de su liberación tiene densidad válida →
    `RESOLVER_CALIDAD`; el TK está disponible para proceso (`motivos_silo_no_disponible(...,
    para="proceso")`) → `RESOLVER_SILOS`; y su saldo cubre los litros equivalentes
    (`kg × 1000 / densidad`) → `null`.

  El aseo observado no está en esta lista: avisa, no bloquea. El stock de materiales de
  envase tampoco: el descuento ocurre al declarar el lote producido y **no bloquea**
  (`cerrar_lote_producido`, «Declarar el lote producido descuenta su material» en
  `CLAUDE.md`).
- `iniciar` toma la corrida y luego la ejecución con `select_for_update` (orden de
  `bloquear_para_cancelar`), recalcula los motivos, lanza el primero si los hay (**400**,
  como hoy) y, si no, crea la salida del TK y la `EntradaProceso` como hoy, transiciona
  `preparacion` → `ejecucion` (con la advertencia de aseo como motivo del evento, o «Inicio
  desde el puesto de Mantequilla.»), marca la corrida `en_proceso` y la OP `en_proceso`.
  **Ya no pasa por `borrador` → `preparacion`**: eso lo hizo «Preparar».
- **Un solo camino de inicio**: `MENSAJES_INICIO_EN_PUESTO` gana
  `EtapaProceso.Tipo.MANTEQUILLA: "Las corridas de mantequilla se inician desde el puesto de
  Mantequilla."`, así que `inicio_reservado_al_puesto` la cubre y
  `ejecuciones/{id}/transicionar/` rechaza `preparacion` → `ejecucion`. Pausar, bloquear,
  reanudar y cancelar siguen por la transición genérica. En el frontend,
  `PUESTOS_QUE_INICIAN` (`services/planta-ahora.ts`) gana `mantequilla: "Mantequilla"`.

### 3.4 Cancelar la preparación

`POST procesos/mantequillas/{id}/cancelar-preparacion/` con `{"motivo": "…"}`:

- `cancelar_preparacion_mantequilla(*, corrida_id, usuario, motivo)`, simétrica a
  `cancelar_preparacion_descremacion`: motivo obligatorio (`MENSAJE_MOTIVO_CANCELACION`);
  solo desde una corrida `borrador` cuya ejecución está en `borrador` o `preparacion` (las
  `borrador` son las heredadas del modal anterior, que nunca tomaron la máquina). Una
  corrida iniciada se cierra registrando su balance.
- La transición genérica a `cancelada` ya suelta la máquina. Lo propio de Mantequilla va en
  `_deshacer_preparacion_mantequilla(ejecucion, motivo, usuario)`, llamado desde
  `transicionar_ejecucion` al cancelar una ejecución de etapa Mantequilla —así cancelar
  desde la bandeja genérica o anular el lote deja lo mismo—:
  - la corrida pasa a **`anulada`** (estado nuevo, §3.6) con `motivo_anulacion`, desde
    `borrador` y también desde `en_proceso` (una corrida «en proceso» sobre una ejecución
    cancelada no la hace nadie, como en Evaporación y Descremado);
  - el **lote de salida se anula con `anular_lote`**, la misma anulación que el `PATCH`,
    con el motivo «Preparación de Mantequilla cancelada: …». Si el lote ya venía anulado
    (se llegó aquí desde el `PATCH`), no se vuelve a marcar; `anular_lote` no vuelve a
    cancelar una ejecución que ya está cancelada (`ejecucion_cancelable`). Es el mismo
    encadenamiento que `_deshacer_preparacion_evaporacion`;
  - **no hay crema que devolver** desde una preparación: no se movió. Desde una corrida en
    curso, lo que entró a la mantequera no vuelve, como en Evaporación;
  - el **lote de suero** queda libre para otra corrida: no se desvincula (la corrida
    anulada conserva el rastro), pero `sueros` (§3.1) y la validación de «Preparar» ignoran
    las corridas `anulada`.
- `bloquear_para_cancelar` agrega `CorridaMantequilla` a los modelos que bloquea antes de la
  ejecución.
- Respuesta: `{"ejecucion_id", "ejecucion_codigo", "estado"}`, como los otros puestos.

### 3.5 Balance del cierre: lo decide el servidor, una vez

En `procesos/dominio.py`, sin ORM:

```python
# El cliente comparaba en milésimas de kg y el modelo exigía diferencia == 0:
# la misma regla. Tres decimales es la precisión de las columnas.
TOLERANCIA_BALANCE_MANTEQUILLA_KG = Decimal("0")

@dataclass(frozen=True)
class BalanceMantequilla:
    entrada_kg: Decimal
    clasificado_kg: Decimal
    diferencia_kg: Decimal          # entrada − clasificado
    cuadra: bool
    mensaje: str | None             # None si cuadra

def balance_mantequilla(
    *, kg_crema, kg_mantequilla, kg_suero=0, kg_merma=0, kg_reproceso=0,
) -> BalanceMantequilla:
```

- Redondea cada valor a `0.001` kg y compara `|diferencia| ≤ TOLERANCIA`. Un valor ausente
  cuenta como cero —el formulario lo pide mientras se teclea—, salvo `kg_mantequilla`, que
  sin valor da `cuadra = False` con «Indica la mantequilla producida.».
- `mensaje` conserva el texto de hoy: «El cierre debe clasificar el 100% de la crema: X kg
  faltan por clasificar.» / «… exceden la entrada.».

Dónde se usa —**las tres son la misma función**:

- **`CorridaMantequilla.clean()`** deja su aritmética en línea y llama a
  `balance_mantequilla`, lanzando `{"balance": mensaje}` si no cuadra. Así el admin, el
  serializer y el servicio comparten la regla.
- **`cerrar_mantequilla`** la evalúa **antes** de crear nada (hoy el lote de reproceso se
  crea y luego `clean()` revierte todo con la transacción): si no cuadra, 400 con
  `{"balance": mensaje}` y ninguna escritura.
- **Mientras se teclea**: `POST procesos/mantequillas/{id}/revisar-cierre/`, con el mismo
  cuerpo que `cerrar/` (todos opcionales), responde **sin escribir**:

  ```json
  { "entrada_kg": "60.000", "clasificado_kg": "59.000", "diferencia_kg": "1.000",
    "cuadra": false, "mensaje": "El cierre debe clasificar el 100% de la crema: 1.000 kg faltan por clasificar.",
    "errores": { "kg_suero": "Esta corrida no tiene un lote de suero asociado: registra 0 kg." } }
  ```

  `errores` repite las otras reglas de `clean()` que dependen de lo tecleado (suero sin
  lote, reproceso sin motivo), con el mismo texto. Es el patrón de
  `revisar_cierre_descremacion`: el formulario lo pide con retardo al cambiar un campo y
  habilita «Cerrar» solo con una revisión `cuadra` de los valores actuales. El cliente no
  calcula nada.

`frontend/src/services/balance-mantequilla.ts` y `frontend/tests/balance-mantequilla.test.ts`
**se eliminan**; los casos de su prueba pasan a las pruebas de dominio
(`procesos/tests_dominio.py` o el archivo de pruebas de dominio que corresponda).

### 3.6 Tipo de máquina y migraciones

- **`maestros`**: `Equipo.Tipo.MANTEQUERA = "mantequera", "Mantequera"` (migración de
  esquema por las `choices`). El catálogo `equipo_tipo` de `/api/maestros/catalogos/` lo
  sirve solo; Maestros › Máquinas lo ofrece sin tocar el frontend.
- **`procesos`**: `tipos_equipo_para_etapa(MANTEQUILLA) = {MANTEQUERA}`, y
  `crear_mantequilla_guiada` y el puesto lo leen de ahí (se borran las dos listas literales
  `{LINEA, OTRO}`). `CorridaMantequilla.Estado.ANULADA = "anulada", "Anulada"` y
  `motivo_anulacion = CharField(max_length=250, blank=True)`, como `CorridaDescremacion`.
- **Migración de datos `maestros`** (`reclasificar_mantequeras`), idempotente:
  - **Candidatas**: el equipo sembrado `linea_mantequilla` (migración `0010`; el
    planificador de planta lo describe como el batido de la crema, `prototipo/PLANIFICADOR.md`)
    y los equipos de las ejecuciones de `CorridaMantequilla` (§8.3).
  - Se reclasifica una candidata a `mantequera` **solo si ninguna ejecución de otra etapa
    la usó**. Una que también hizo otra cosa queda como está y la migración la nombra en su
    salida: cambiarle el tipo rompería la otra etapa. Las demás líneas y «otro» no se tocan.
  - Una mantequera reclasificada **sale de `FormatoEnvasado.equipos`** (el envasado acepta
    solo envasadora o línea: `FormatoEnvasado` y `Envase.clean()`). Los `Envase` históricos
    conservan su clave foránea; nadie vuelve a validarlos.
  - Conserva `sigla` (`LM`), `consume_materiales` y `consume_leche`: el código de lote y el
    MRP no cambian.
  - Reversa: devuelve a `linea` lo que la migración reclasificó (lo anota en el propio
    paso, no lo deduce).
- `abre_desde_vale` y `tipo_etapa_de_apertura` **no cambian**: una mantequera cae en el
  valor por defecto, que no abre desde un vale. Se agrega una prueba que lo fija.
  `exigir_apertura_fuera_de_secado` responde para ella con su mensaje genérico («… no abre
  lotes desde un vale…»), que es correcto.
- **Comandos**: `preparar_circuito_mantequilla` busca la máquina por `tipo=MANTEQUERA` (hoy
  `tipo=LINEA, nombre__icontains="mantequilla"`) y, como el envasado de la mantequilla ya no
  puede hacerse en ella, **asegura una envasadora** (`envasadora_mantequilla`, «Envasadora de
  mantequilla», tipo `envasadora`) autorizada en los `FormatoEnvasado` activos de la
  mantequilla. `reset_datos_operacionales` no cambia.
- `CLAUDE.md`, «Una sola representación de "equipo"», gana la mantequera: un tipo propio
  para que una línea de envasado no aparezca como mantequera ni una mantequera como línea
  de envasado, por la misma razón que `e1`/`e2` dejaron de ser «líneas».

### 3.7 Permisos

- Preparar, iniciar, cancelar, revisar el cierre y cerrar exigen la etapa Mantequilla
  (`puede_operar_tipo(usuario, EtapaProceso.Tipo.MANTEQUILLA)`) **en todos los caminos**:
  `OperaProcesoPorEtapa` con `tipo_etapa_operacional` ya lo hace en el viewset para cada
  `POST`; se fija con una prueba con un usuario de Secado (403 en cada acción, nada creado).
- `POST procesos/mantequillas/` sigue en 405 (ya lo está).
- El viewset gana `FiltraConsultaMixin` para el historial: `busqueda_en =
  ("ejecucion__codigo", "lote_mantequilla__codigo_lote", "lote_crema__codigo_lote",
  "orden__codigo")`, `filtro_estado = "estado"` con `condicion_estado` por situación (§3.8),
  `filtro_fecha = "ejecucion__creada_en"`. Ya tiene `QuerysetTenantMixin` y
  `RelacionesTenantMixin`.

### 3.8 Situaciones

`SITUACIONES_MANTEQUILLA` en `procesos/dominio.py`, con la forma de
`SITUACIONES_DESCREMACION` (gana la primera):

| Valor | Etiqueta | Corrida | Ejecución |
|---|---|---|---|
| `preparada` | Preparada | `borrador` | `preparacion` |
| `en_curso` | En la mantequera | `en_proceso` | cualquiera |
| `esperando_calidad` | Esperando Calidad | `pendiente_calidad` | cualquiera |
| `terminada` | Terminada | `cerrada` | cualquiera |
| `anulada` | Anulada | `anulada` | cualquiera |
| `borrador` | Borrador | `borrador` | cualquiera (heredadas y huérfanos) |

`condicion_situacion_descremacion` se generaliza a `condicion_situacion(tabla,
situacion)` y la usan los dos viewsets: con dos copias, el filtro de un historial y su
columna podrían dejar de coincidir.

### 3.9 Lo que no cambia

`cerrar_mantequilla` más allá del balance: coproducto de suero/mazada, merma, reproceso
segregado en `RW-MANT-…` con `AutorizacionReproceso` y aviso a Calidad, salida principal a
envasado con `LiberacionProceso`, ejecución a `pendiente_control`, y la cola común
`cerrar_lote_producido` («Declarar un lote producido es una sola cola»). La liberación de la
mantequilla en `/calidad` y el cierre de la corrida al decidirla
(`calidad/views.py`). El código de ejecución `EJ-MANT-{pk}` ya lo asigna el servidor.

## 4. Pantalla — `/produccion/mantequilla`

1. **Tarjetas por mantequera.** Estado inequívoco y **una sola acción** por estado; la
   tarjeta pinta lo que manda el servidor y no recalcula nada:
   - *Disponible* → «Preparar mantequilla» (abre el formulario con esa mantequera
     elegida). Con `motivos_para_tomar`: deshabilitado, el motivo y el enlace.
   - *Preparada* (OP, crema → lote de salida, kg de crema, suero) → «Iniciar mantequilla».
     Con `motivos_para_iniciar`: botón deshabilitado, el primer motivo debajo y un enlace a
     `resolver_en` (p. ej. «Liberar la crema» → `/calidad`), solo si el usuario puede
     entrar a ese módulo (`moduloDeResolver`). Al lado, «Cancelar preparación»: motivo y
     `ConfirmarAccion` («Se anulará el lote {código} y la mantequera quedará libre»).
   - *En curso* (inicio, kg de crema) → «Registrar balance y cerrar».
   - Con `en_calidad`: una línea «{lote} de EJ-MANT-300 esperando Calidad».
   - Los `avisos` en ámbar, sin deshabilitar nada.
2. **Formulario «Preparar mantequilla»** (guiado, en el puesto): crema (de `cremas`, con su
   disponible y su TK; preelegida con `?crema=<lote_id>`; si la crema pedida está en
   `cremas_pendientes_calidad`, se muestra con su estado y el enlace a `/calidad` en vez de
   desaparecer) → kg de crema (tope `disponible_kg`) → OP (de `ordenes`) → mantequera →
   suero/mazada opcional → código del lote de salida, **sugerido** por
   `produccion/lotes/codigo-sugerido/` con la mantequera y la fecha de hoy y editable →
   **resumen y confirmar** con `ConfirmarAccion` («Preparar mantequilla»). Sin
   `ocupacionesPorEquipo`: la ocupación la sirve `puesto/`.
3. **Cierre** («Registrar balance y cerrar»): el `CierreMantequilla` actual movido a
   `pages/Mantequilla/CierreMantequilla.tsx`, con el balance de `revisar-cierre/` bajo los
   campos mientras se teclea (completo / incompleto / excedido, con la diferencia que
   devuelve el servidor) y un resumen con `ConfirmarAccion` antes de cerrar. «Cerrar y
   enviar a Calidad» se habilita solo con la última revisión `cuadra` de los valores
   actuales y sin revisión pendiente.
4. **Corridas de hoy** debajo, cargadas solas —sin «Cargar corridas»—, y un **«Historial»**
   con `q`, `estado` (situaciones de `estados`), `desde`/`hasta` del servidor
   (`TablaConsulta`, como Descremado). Una fila `borrador` (heredada) ofrece «Cancelar
   preparación» con la misma regla que la tarjeta (`corridaCancelable`).
5. **Acceso**: ruta bajo el módulo `produccion`, como Evaporación y Descremado. Operan
   Condensación y administración (helper `puedeOperarMantequilla`, que reusa la regla de
   evaporación como hace `permisos-descremado.ts`, con prueba unitaria); Calidad ve en modo
   consulta. «Actualizar» y la recarga tras cada acción pasan por `useDatosSeccion`
   (`recargar`, que llama a `invalidarCacheLecturas`): otra sesión pudo liberar la crema.

Las funciones puras del frontend van en `services/puesto-mantequilla.ts`:
`accionDeMantequera(fila)` (botón, habilitación y motivo; espejo de
`accionDeDescremadora`), `corridaCancelable(fila)` y `estadoDelBalance(revision,
pendiente)` (qué franja y qué texto pinta el cierre a partir de la respuesta, sin
aritmética). `CancelarPreparacion` se mueve de `pages/Descremado/` a
`components/operacion/` porque pasa a tener dos usuarios.

### 4.1 Lo que se retira

- `/procesos`: la sección `proceso-mantequilla`, su estado y efectos, `iniciarMantequilla`
  desde ahí, y los modales `NuevaMantequilla` (se reescribe en `pages/Mantequilla/`) y
  `CierreMantequilla` (se mueve).
- Redirecciones en el bloque de `Procesos.tsx` que ya redirige `condensacion`,
  `evaporacion` y `descremacion`: `/procesos?seccion=mantequilla` →
  `/produccion/mantequilla`.
- `Silos.tsx` y `SalidasIntermedias.tsx`: la acción `iniciar_mantequilla` enlaza a
  `/produccion/mantequilla?crema=<lote_id>` (el material ya trae `lote_id`). La etiqueta que
  sirve el backend pasa de «Iniciar Mantequilla» a «Preparar en Mantequilla»: el enlace ya
  no inicia nada.
- Menú (`navegacion-operacional.ts`): «Mantequilla» → `/produccion/mantequilla`, módulo
  `produccion`, con alias `/procesos?seccion=mantequilla`; el comentario sobre «Mantequilla
  y Trazabilidad viven en /procesos» queda solo para Trazabilidad.
- `rutaDeEtapa` (`services/planta-ahora.ts`) y `RUTAS_POR_ETAPA` (`procesos/dominio.py`)
  apuntan al puesto para `mantequilla`.
- `/produccion`: el atajo «Mantequilla» enlaza al puesto.
- «Ejecuciones operativas» y «Mi trabajo pendiente» muestran las ejecuciones de Mantequilla
  sin el botón de iniciar (el servidor ya no lo ofrece) y con «Iniciar en el puesto de
  Mantequilla» (`textoIniciarEnPuesto`).
- `procesos.service.ts`: `obtenerOpcionesAltaMantequilla` y `OpcionesAltaMantequilla`
  (el endpoint se elimina); `obtenerMantequillas` gana los parámetros del historial.
- `services/balance-mantequilla.ts` y su prueba (§3.5).

## 5. Pruebas

- **Backend** (`procesos/tests_mantequilla.py` y un `tests_puesto_mantequilla.py`):
  - `puesto/`: los tres estados; en curso manda sobre preparada; huérfano con ejecución
    terminal → `disponible`; ejecución en `pendiente_control` → `disponible` con
    `en_calidad`; un equipo `linea` con una ejecución de Mantequilla que lo ocupa aparece;
    una `linea` sin ella no aparece; `motivos_para_iniciar` vacío y con motivo (crema
    pendiente de Calidad → `resolver_en = "/calidad"`; TK sin segunda firma → `"/silos"`;
    mantequera en CIP → `"/calidad/inocuidad"`; OP cancelada → `"/planificacion"`); aseo
    observado: aviso, no motivo; `cremas` resta las otras preparadas y no ofrece una
    agotada por ellas; `sueros` ofrece de nuevo el de una corrida anulada.
  - Preparar: crea lote, ejecución en `preparacion` con la máquina tomada y corrida
    `borrador`, **sin entrada ni movimiento de TK**; mantequera ocupada → 400 y nada creado
    (sin lote, sin ejecución); mantequera en CIP → 400; un equipo `linea` → 400; más kg que
    `kg_crema_disponible` contando otra preparada → 400.
  - Iniciar: con motivos → 400 y la ejecución sigue en `preparacion`; sin motivos →
    `ejecucion`, una entrada y la salida del TK; `motivos_para_iniciar_mantequilla`
    coincide con lo que rechaza `iniciar`; una corrida heredada con ejecución `borrador` →
    motivo «no está preparada».
  - Cancelar: corrida `anulada` con motivo, lote de salida `anulado` con la marca, máquina
    libre; sin motivo → 400; sobre una en curso → 400; desde la bandeja genérica deja lo
    mismo; anular el lote por el `PATCH` deja lo mismo y marca el lote una sola vez.
  - `transicionar` genérico `preparacion` → `ejecucion` de una Mantequilla → 400; pausar una
    en curso sigue funcionando.
  - `preparar-continuacion` con la etapa Mantequilla → 400, nada creado.
  - Balance: `balance_mantequilla` en pruebas de dominio (cuadra, falta, excede, bordes en
    milésimas, `kg_mantequilla` ausente); `cerrar/` que no cuadra → 400 **sin** lote de
    reproceso creado; `revisar-cierre/` no escribe nada y devuelve el mismo mensaje que
    rechazaría `cerrar/`; `test_no_cierra_si_queda_crema_sin_clasificar` sigue verde.
  - Usuario de Secado → 403 en preparar, iniciar, cancelar, revisar y cerrar.
  - Historial: `?q=`, `?estado=` por situación y `?desde=/hasta=`.
  - Migración: una `linea` usada solo por Mantequilla pasa a `mantequera` y sale de los
    formatos de envasado; una usada también por Envasado queda `linea`; una `linea` ajena no
    cambia; `abre_desde_vale("mantequera")` es falso.
  - Ajustar: el `setUp` de `tests_mantequilla.py` (crea la máquina como `LINEA`),
    `procesos/tests.py:203` (`("man", MANTEQUILLA, LINEA)`), los tres
    `test_opciones_alta_*` (pasan a `puesto/`) y `tests_destinos.py`
    (`RUTAS_POR_ETAPA["mantequilla"]`).
- **Frontend (unitarias)**: `accionDeMantequera`, `corridaCancelable` y `estadoDelBalance`
  derivan botón, habilitación, motivo y franja de la respuesta; `puedeOperarMantequilla`;
  `rutaDeEtapa("mantequilla")` y `textoIniciarEnPuesto("mantequilla", "preparacion")`
  (`tests/planta-ahora.test.ts`, que hoy fija `/procesos?seccion=mantequilla` y `null`); el
  enlace activo del menú (`tests/navegacion-operacional.test.ts`, que hoy fija
  `?seccion=mantequilla`).
- **E2E**: `frontend/e2e/flujo-mantequilla.spec.ts` reescrito sobre el puesto. Primera
  prueba: Producción llega por «Preparar en Mantequilla» de Salidas intermedias con la crema
  elegida → prepara (código sugerido, mazada) → ve «Iniciar mantequilla» habilitado → inicia
  → en el cierre ve «Balance incompleto» del servidor con 31 + 28 kg, completa la merma y
  cierra → Calidad libera. La tarjeta se busca por el `ejecucion_codigo` que devuelve
  `crear-guiada`, no por un código tecleado. Una segunda prueba prepara y **cancela**: el
  lote de salida queda anulado y la mantequera libre. El paso de envasado elige la
  «Envasadora de mantequilla» que deja `preparar_circuito_mantequilla`, ya no la «Línea de
  mantequilla». `flujo-descremado.spec.ts` (líneas 258, 306 y 345) busca el enlace por su
  nueva etiqueta.
- **Accesibilidad**: `/produccion/mantequilla` entra a `e2e/rutas.ts`; sin reglas nuevas.

## 6. Riesgos

- **Reclasificar la máquina cambia el envasado de la mantequilla.** Si en una base la
  `linea_mantequilla` estaba autorizada en un formato de envasado, después de la migración
  ese formato puede quedar sin equipos y la mantequilla no se envasa hasta que alguien
  autorice una envasadora en Maestros. La migración lo dice en su salida; en una base que
  parte en blanco no hay formatos que tocar, y el comando de preparación asegura la
  envasadora para el circuito.
- **Preparar ahora toma la máquina**: una corrida preparada y olvidada retiene la
  mantequera y la crema que pidió (`kg_crema_disponible` la resta). Por eso «Cancelar
  preparación» va en el mismo cambio y la tarjeta *Preparada* se ve en el puesto. Las
  corridas heredadas en `borrador`/`borrador` no ocupan, se listan en el historial como
  «Borrador» y se cancelan con la misma acción.
- **Cerrar el inicio genérico**: antes de cerrar `transicionar` para Mantequilla se busca
  cada uso que inicie una ejecución de Mantequilla por esa vía (no hay en
  `sembrar_flujo_demo` ni en `preparar_circuito_mantequilla`; la bandeja genérica sí lo
  ofrecía).
- **Usos a migrar** (búsqueda del 2026-10-08):
  - `backend/maestros/models.py:365` (`Equipo.Tipo`) y una migración nueva de esquema y de
    datos; `backend/maestros/migrations/0010_sembrar_equipos.py:21` y `0031_sembrar_siglas.py:20`
    (no se editan: la de datos nueva reclasifica).
  - `backend/procesos/models.py:552` (`CorridaMantequilla`: `Estado.ANULADA`,
    `motivo_anulacion`, `clean()` sobre `balance_mantequilla`) y su migración.
  - `backend/procesos/dominio.py:101` (`RUTAS_POR_ETAPA`), más `balance_mantequilla`,
    `TOLERANCIA_BALANCE_MANTEQUILLA_KG`, `SITUACIONES_MANTEQUILLA`.
  - `backend/procesos/servicios.py`: `MENSAJES_INICIO_EN_PUESTO` (:103),
    `bloquear_para_cancelar` (:1143), `transicionar_ejecucion` (gancho de cancelación),
    `tipos_equipo_para_etapa` (:662), `crear_mantequilla_guiada` (:955, y su lista literal
    en :977), `preparar_continuacion` (:1019), `iniciar_mantequilla` (:2838),
    `cerrar_mantequilla` (:2931), `condicion_situacion_descremacion` (:2365, se
    generaliza), y las nuevas `estado_puesto_mantequilla`,
    `motivos_tipados_para_iniciar_mantequilla`, `kg_crema_disponible`,
    `revisar_cierre_mantequilla`, `cancelar_preparacion_mantequilla`,
    `_deshacer_preparacion_mantequilla`, `RESOLVER_PLANIFICACION`.
  - `backend/procesos/views.py`: `CorridaMantequillaViewSet` (:598; `opciones-alta` se
    elimina con su lista literal en :675; `puesto`, `cancelar-preparacion`,
    `revisar-cierre` nuevos; `FiltraConsultaMixin`), la etiqueta «Iniciar Mantequilla» de
    `acciones_permitidas` (:1526) y el mensaje de `transicionar`.
  - `backend/procesos/serializers.py`: un `RevisarCierreMantequillaSerializer` (los campos
    de `CierreMantequillaSerializer`, opcionales).
  - `backend/produccion/management/commands/preparar_circuito_mantequilla.py:64-69`.
  - Pruebas: `backend/procesos/tests_mantequilla.py`, `backend/procesos/tests.py:203`,
    `backend/procesos/tests_destinos.py:26`.
  - `frontend/src/pages/Procesos/Procesos.tsx` (imports, estado, carga, sección, modales y
    el bloque de redirecciones), `NuevaMantequilla.tsx`, `CierreMantequilla.tsx`.
  - `frontend/src/pages/Leche/Silos.tsx:336-337`,
    `frontend/src/pages/Produccion/SalidasIntermedias.tsx:227-232`,
    `frontend/src/pages/Produccion/Produccion.tsx:271`.
  - `frontend/src/services/navegacion-operacional.ts:59,155`,
    `frontend/src/services/planta-ahora.ts:11` (y `PUESTOS_QUE_INICIAN`),
    `frontend/src/services/procesos.service.ts:345,587-633`,
    `frontend/src/services/balance-mantequilla.ts`, `frontend/src/app/routes.tsx`,
    `frontend/src/pages/Descremado/CancelarPreparacion.tsx` (se mueve).
  - `frontend/tests/balance-mantequilla.test.ts` (se elimina),
    `frontend/tests/planta-ahora.test.ts:26,36`,
    `frontend/tests/navegacion-operacional.test.ts:119-130`.
  - `frontend/e2e/flujo-mantequilla.spec.ts`, `frontend/e2e/flujo-descremado.spec.ts:258,306,345`,
    `frontend/e2e/rutas.ts`.
  - Sin cambio: `calidad/views.py` (cierre de la corrida al decidir), `calidad/consultas.py`,
    `reset_datos_operacionales`, `sembrar_flujo_demo`, `FormularioFormatoEnvasado.tsx` (ya
    filtra envasadora/línea, así que no ofrecerá la mantequera).

## 7. Fuera de alcance

Un motor de puesto genérico (con cuatro puestos ya se ve qué comparten —tarjeta, acción
servida, cancelar, historial, situaciones—; extraerlo es su propio diseño); límites de
proceso de la mantequilla (humedad, grasa) como avisos del cierre: `docs/REGLAS_DE_PLANTA.md`
no trae reglas de mantequilla y no se inventan; asignar el código del lote de salida por el
servidor sin edición; que el stock de envase bloquee el inicio (decisión de Calidad, igual
que en los demás lotes); `/procesos` reducido a Trazabilidad.

## 8. Desviaciones y supuestos

Lo que el código contradice de las decisiones, o deja abierto, y cómo se resolvió (camino
general, sin detenerse a preguntar):

1. **«El backend no revalida el balance» no es exacto.** `cerrar_mantequilla` llama a
   `corrida.clean()`, que exige `kg_crema − (mantequilla + suero + merma + reproceso) == 0`
   y ya rechaza (lo fija `test_no_cierra_si_queda_crema_sin_clasificar`). Lo que sí ocurre
   es que hay **dos** implementaciones —la del cliente en milésimas y la del modelo en
   `Decimal`— y que la del servidor se evalúa después de crear el lote de reproceso.
   **Resuelto** según la decisión: una función pura que usan el modelo, el cierre (antes de
   escribir) y `revisar-cierre/`; el cliente deja de calcular.
2. **La tolerancia** del cliente es cero en milésimas de kg (`diferencia === 0` tras
   redondear a `0.001`), y la del modelo cero en `Decimal` con tres decimales. Se conserva
   como `TOLERANCIA_BALANCE_MANTEQUILLA_KG = Decimal("0")`, explícita, para que cambiarla
   sea editar una constante y no buscar dos comparaciones.
3. **La migración por uso no deja ninguna mantequera en una base en blanco.** La decisión
   reclasifica los equipos que ya usó `CorridaMantequilla`; en producción el sistema parte
   en blanco y no hay ninguno, así que el puesto quedaría sin tarjetas. **Supuesto**: se
   reclasifica también `linea_mantequilla` por su código —es la máquina de batido sembrada
   en `0010`—, con la misma excepción (no si otra etapa la usó). Las demás líneas y «otro»
   quedan como están.
4. **`linea_mantequilla` también envasaba.** El E2E envasa la mantequilla «en la Línea de
   mantequilla», porque el envasado acepta líneas. Reclasificarla lo impide. **Resuelto**:
   la migración la saca de los formatos de envasado y el comando de preparación asegura una
   envasadora propia (§3.6, §6). La alternativa —que el envasado acepte mantequeras—
   devolvería la mezcla que el tipo propio existe para evitar.
5. **El inicio de hoy hace la preparación.** `iniciar_mantequilla` pasa `borrador` →
   `preparacion` → `ejecucion` en una llamada. Preparar pasa ahora la ejecución a
   `preparacion` (como Descremado) y el inicio exige encontrarla ahí. Las corridas heredadas
   con ejecución `borrador` no se inician: se cancelan y se vuelven a preparar (§6).
6. **El código del lote de salida lo teclea el operador** (sin sugerencia; el E2E inventa
   `MANT-E2E-…`). Ninguna decisión lo toca. **Supuesto**: se sugiere con el
   `codigo-sugerido/` existente (sigla de la mantequera, `LM`) y queda editable, como
   cualquier lote («`codigo_lote_valido` avisa, no restringe»); no se agrega un endpoint.
7. **La crema sin TK no exigía liberación al iniciar.** `iniciar_mantequilla` solo mira la
   liberación si la crema tiene una salida en un TK, mientras `opciones-alta` solo ofrece
   cremas liberadas. **Resuelto**: la liberación es un motivo de inicio para toda crema, la
   misma condición que la lista.
8. **Lote de crema anulado** no era un motivo: `iniciar_mantequilla` no lo miraba. Se
   agrega como motivo (sin enlace) por la misma razón que `salida_de_lote_anulado` en
   Secado: el material de un lote anulado no se procesa.
9. **«Stock» en las reglas de inicio**: no hay una comprobación de stock en
   `iniciar_mantequilla` y no se inventa; el saldo que sí se comprueba es el de crema (kg y
   litros del TK). El de materiales se descuenta al declarar el lote y no bloquea.
10. **Crema comprometida por otras preparadas.** Hoy el disponible solo resta entradas
    reales, así que dos preparaciones podían pedir la misma crema. Como preparar ahora es un
    estado que dura, el disponible resta también las otras preparadas (`kg_crema_disponible`,
    §3.1): sin eso el puesto ofrecería crema que el inicio de la segunda rechaza.
11. **`CorridaMantequilla` no tiene estado de anulación.** Se agrega `anulada` con
    `motivo_anulacion`, como `CorridaDescremacion`, en vez de borrar la corrida (Secado) o
    dejarla `borrador` sobre una ejecución cancelada (hoy).
12. **El suero de una corrida anulada quedaba retenido**: `opciones-alta` excluye cualquier
    lote de suero con una corrida, viva o no. Se ignoran las anuladas en la lista y en
    «Preparar».
13. **`preparar-continuacion` con la etapa Mantequilla** era una segunda entrada, sin
    corrida. Se cierra (400) para que la entrada sea una sola (decisión 5).
14. **Código de respuesta del inicio**: Descremado responde 409; Mantequilla responde 400
    hoy y se conserva, como Secado. Unificarlo es parte del motor genérico (§7).
15. **URL de preparar**: se conserva `crear-guiada/`, como Evaporación y Descremado; el
    nombre no promete iniciar.
