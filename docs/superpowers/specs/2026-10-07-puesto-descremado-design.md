# Puesto de Descremado

**Fecha:** 2026-10-07
**Origen:** revisión UX industrial de los menús de fabricación (2026-10-02). Tercero de los
puestos por proceso; sigue el patrón de Evaporación
(`docs/superpowers/specs/2026-10-05-puesto-evaporacion-design.md`) y de Secado
(`docs/superpowers/specs/2026-10-06-puesto-secado-design.md`).
**Guía de criterio:** `.agents/skills/disenador-ux-industrial/SKILL.md`.

---

## 1. El problema

Hoy descremar un silo son **3 pasos en 3 pantallas**, y el que reparte la leche junta dos
momentos en un solo botón:

| Paso | Dónde | Qué |
|---|---|---|
| 1 | `/silos` › silo › «Descremar» | enlace a `/procesos?accion=descremar&silo=<id>` |
| 2 | `/procesos` › modal `FormularioDescremacion` | código, etapa, equipo, análisis, litros, dos TK, dos productos, dos rutas, «Calcular sugerencia» (`sugerir-balance`) → «Confirmar reservas e iniciar» = `crear-guiada` **y** `iniciar` |
| 3 | `/procesos` › sección «Descremación» (no autocarga: «Cargar corridas de descremación») › «Registrar salidas y cerrar» | `CierreDescremacion`: litros y grasa reales de las dos salidas |

- **Preparar e iniciar son una sola acción del operador y dos llamadas al servidor.**
  `crear-guiada` deja la ejecución en `borrador`; `iniciar` crea las reservas de silo, la
  entrada y pasa a `ejecucion`. Si `iniciar` falla (silo sin segunda firma, TK sin
  capacidad), queda una corrida `borrador` que ninguna pantalla muestra como tal y que
  nadie cancela.
- **La pantalla ofrece lo que el servidor rechaza.** `opciones-alta` ofrece todos los TK de
  descremada y de crema activos, sin mirar estado, reservas ni capacidad; el rechazo llega
  al iniciar (caso 2 de «La pantalla ofrece lo que el backend va a rechazar» en
  `CLAUDE.md`). El análisis se elige en el cliente entre los que el cliente filtró como
  vigentes, y `crear-guiada` solo exige confirmado y vigente: sin la segunda firma o con
  inhibidores pendientes la corrida se crea y `iniciar` la rechaza.
- **No hay regla que la pantalla pueda consultar antes de intentar.** Las comprobaciones
  de inicio viven en línea dentro de `iniciar_descremacion`, cada una con su
  `raise ValidationError`.
- **El permiso de la pantalla no es el del servidor.** El modal se ofrece con
  `puedeEscribir("produccion")`; el viewset exige la etapa Descremación
  (`OperaProcesoPorEtapa`, área Condensación). Un operador de Secado ve el formulario
  entero y recibe un 403 al final.
- **Los límites físicos del proceso no viven en ninguna parte.** `docs/REGLAS_DE_PLANTA.md`
  §2 da grasa de descremada ≤ 0,1 % y crema para despacho 42–43 %, y todavía dice que el
  proceso no existe en el sistema. Existe desde la migración `procesos.0008`; los límites
  no.

## 2. Decisiones

Tomadas por el controlador con autorización del usuario el 2026-10-07; revisables.

| Decisión | Elegido |
|---|---|
| Lugar | **Puesto propio** en `/produccion/descremado`: una tarjeta por descremadora, una acción servida por estado, «Cancelar preparación», corridas de hoy e historial con filtros de servidor |
| Preparar e iniciar | **Dos pasos**, como Evaporación y Secado: «Preparar descremado» crea la corrida **con sus reservas de silo**; «Iniciar descremado» es otra acción, habilitada solo cuando el servidor lo permitiría |
| Regla de inicio | **Una función**, `motivos_para_iniciar_descremacion`, extraída de `iniciar_descremacion`; la usa `iniciar` y la sirve `puesto/` |
| Entrada | **Una sola**: «Descremar» del silo lleva al puesto con el silo preelegido (`/produccion/descremado?silo=<id>`). El modal y la sección de `/procesos` se retiran; las rutas viejas redirigen |
| Límites físicos | **Avisan, no bloquean.** Una función pura en `procesos/dominio.py`, servida al cierre mientras se teclea y registrada al cerrar. Endurecerlos es decisión de Calidad sobre esa función |
| Cancelar | Una corrida preparada se cancela con motivo: suelta las reservas y la descremadora, nada más (antes del cierre no hay lotes) |
| Permiso | La etapa Descremación (área Condensación) **en todos los caminos** |
| Documentación | `docs/REGLAS_DE_PLANTA.md` §2 se actualiza: el proceso existe y qué límites están implementados como aviso |

## 3. Backend

### 3.1 Estado del puesto

`GET procesos/descremaciones/puesto/` devuelve:

```json
{
  "descremadoras": [{
    "equipo_id": 12, "codigo": "des01", "nombre": "Descremadora DES-01",
    "estado": "disponible | preparada | en_curso",
    "corrida": { "id": 8, "ejecucion_id": 120, "ejecucion_codigo": "EJ-DES-8",
                  "ejecucion_estado": "preparacion",
                  "silo_entera": "Silo 3", "litros_entrada": "1000.00",
                  "grasa_entrada": "2.610", "sng_entrada": "8.700",
                  "silo_descremada": "Tk02", "litros_descremada_plan": "976.40",
                  "estanque_crema": "TkC2", "litros_crema_plan": "23.60",
                  "destino_crema": "siguiente_proceso", "iniciada_en": null },
    "motivos_para_tomar": [],
    "motivos_para_iniciar": ["Silo 3: El análisis requiere firma de realización y visualización."],
    "resolver_en": "/silos | /calidad/inocuidad | null",
    "avisos": ["Último aseo con observación: …"],
    "en_calidad": { "id": 7, "ejecucion_codigo": "EJ-DES-7", "tanques": ["Tk02", "TkC2"] }
  }],
  "origenes": [{ "id": 3, "codigo": "Silo 3", "saldo_l": "24000.00",
                 "analisis": { "id": 55, "grasa": "2.610", "sng": "8.700",
                               "tomado_en": "2026-10-07T08:10:00-03:00" },
                 "motivo": null }],
  "destinos_descremada": [{ "id": 21, "codigo": "Tk02", "libre_l": "30000.00" }],
  "destinos_crema": [{ "id": 31, "codigo": "TkC2", "libre_l": "8000.00" }],
  "corridas_de_hoy": [{ "id": 7, "ejecucion_codigo": "EJ-DES-7", "equipo": "des01",
                        "silo_entera": "Silo 3", "estado": "cerrada",
                        "estado_etiqueta": "Cerrada", "estado_ejecucion": "pendiente_control" }]
}
```

- **Estado por descremadora**, derivado de su `EjecucionProceso` de Descremación que ocupa
  el equipo (`ESTADOS_QUE_OCUPAN_EQUIPO`): `preparacion` → `preparada`; `ejecucion`,
  `pausada` o `bloqueada` → `en_curso`; sin ejecución que la ocupe → `disponible`. Una en
  curso manda sobre una preparada. Una ejecución `cerrada` o `cancelada` no ocupa la
  máquina aunque su corrida haya quedado en `borrador`/`en_curso`
  (`ESTADOS_EJECUCION_TERMINALES`, igual que en los otros puestos).
- **`motivos_para_iniciar`** (solo en `preparada`) los calcula
  `motivos_tipados_para_iniciar_descremacion` (§3.3); `resolver_en` es el destino del
  **primer** motivo, tipado como en Secado (`RESOLVER_CIP`, `RESOLVER_SILOS = "/silos"`
  nuevo, o `null`). La pantalla no lee el texto del motivo para decidir el enlace.
- **`motivos_para_tomar`** (solo en `disponible`): `motivo_equipo_no_habilitado` sobre la
  descremadora, la misma regla con que «Preparar» la rechaza.
- **`avisos`** no bloquean: hoy, el aseo con advertencia (`advertencia_aseo_equipo`, el
  mismo texto que ya va al evento al iniciar).
- **`en_calidad`**: la última corrida de esa descremadora cuya ejecución está en
  `pendiente_control`. Es informativa: esa ejecución ya no ocupa la máquina, pero sus dos
  TK siguen `bloqueado_calidad` hasta que Calidad decida, y eso conviene verlo junto a la
  descremadora que los llenó.
- **`origenes`**: silos de tipo `silo` activos con saldo. `analisis` es **el** análisis que
  usará «Preparar»: el último confirmado y vigente del silo con grasa y SNG —el mismo que
  lee `motivos_silo_no_disponible`—. `motivo` dice por qué no se puede preparar desde ese
  silo (sin análisis vigente, sin composición, fuera de servicio, bloqueado, en CIP); con
  `motivo`, el silo se ofrece deshabilitado con el texto, porque es la entrada que viene
  desde «Descremar» y desaparecer en silencio sería peor.
- **`destinos_descremada` / `destinos_crema`**: TK de tipo `tk_ld` / `tk_crema` que pasan
  la regla de destino de §3.2 —activos, en estado que admite producto, sin reserva activa
  de otra ejecución—, con su capacidad libre. La capacidad y la mezcla de producto
  dependen de los litros planificados y las vuelve a comprobar «Preparar» con el saldo
  bloqueado; el formulario avisa si el plan supera `libre_l`.
- **`corridas_de_hoy`**: corridas creadas, iniciadas o cerradas hoy, sin huérfanos cuya
  ejecución terminó sin iniciarse.
- Montos decimales viajan como **texto**, como en los otros puestos.
- **Lectura**: las áreas que hoy ven Descremado en el menú (Condensación, Calidad) y
  administradores.

### 3.2 Preparar

`POST procesos/descremaciones/crear-guiada/` conserva la URL y cambia su efecto. En una
transacción:

1. Valida etapa, descremadora (activa, de tipo `descremadora`, habilitada:
   `motivo_equipo_no_habilitado`), productos, rutas y destinos de rama, como hoy.
2. **Elige el análisis en el servidor**: el de `origenes[].analisis`. El campo
   `analisis_entrada` deja de recibirse. Preparar exige ese análisis **confirmado, vigente
   y con grasa y SNG** —sin composición no hay plan—; la segunda firma, los inhibidores y
   la revalidación de 48 h **no** frenan la preparación: son motivos de inicio y se ven en
   la tarjeta con su enlace a `/silos`. Es el mismo reparto que en Evaporación, donde el
   origen se analiza después de abrir el lote.
3. Recalcula la sugerencia (`sugerir_plan_descremacion`) y guarda el plan confirmado por
   el operador (`plan_confirmado` sigue siendo obligatorio).
4. Comprueba origen y destinos con **las mismas funciones** que usa el inicio (§3.3):
   `motivos_origen_descremacion` (saldo menos lo reservado por otras ejecuciones) y
   `motivos_destino_descremacion` (estado, reserva de otra ejecución, mezcla de producto,
   capacidad para los litros planificados). Con dos reglas, el puesto prepararía una
   corrida que «Iniciar» rechaza después.
5. Crea la ejecución con **código asignado por el servidor** (`EJ-DES-{pk}`, como
   `EJ-PROD-{pk}` y `EJ-MANT-{pk}`); el campo `codigo` deja de recibirse.
6. Crea las **tres `ReservaSiloProceso`** (origen, TK de descremada, TK de crema), que hoy
   nacen en `iniciar_descremacion`.
7. Transiciona la ejecución `borrador` → `preparacion`, que toma la descremadora
   (`adquirir_equipo`) y rechaza una ocupada.

Cualquier `ValidationError` revierte todo: ni corrida, ni reservas, ni máquina ocupada.

### 3.3 Iniciar

`POST procesos/descremaciones/{id}/iniciar/`:

- `motivos_tipados_para_iniciar_descremacion(corrida, *, ejecucion=None)` en
  `procesos/servicios.py` es **la única implementación** de las reglas de inicio, como
  pares `(motivo, resolver_en)`; `motivos_para_iniciar_descremacion` devuelve los textos.
  Extraída de lo que hoy comprueba `iniciar_descremacion`, en ese orden:
  - la corrida está en `borrador` y su ejecución en `preparacion`;
  - el plan está confirmado (litros planificados de las dos ramas, quién y cuándo) y
    `corrida.clean()` pasa;
  - hay descremadora asignada y está habilitada (`motivo_equipo_no_habilitado`: no en
    CIP) → `RESOLVER_CIP`;
  - el silo de origen está disponible para proceso (`motivos_silo_no_disponible(...,
    para="proceso")`: análisis confirmado y vigente, **dos firmas**, inhibidores, 48 h,
    estado, CIP) → `RESOLVER_SILOS`;
  - **el análisis con que se preparó sigue siendo el vigente del silo** y sigue
    confirmado, con la misma grasa y SNG congeladas → `RESOLVER_SILOS` (nuevo, ver §8);
  - origen y destinos siguen pasando `motivos_origen_descremacion` y
    `motivos_destino_descremacion`, excluyendo las reservas de la propia ejecución;
  - las tres reservas propias siguen activas.

  El aseo observado no está en esta lista: avisa, no bloquea.
- `iniciar` toma la corrida y luego la ejecución con `select_for_update` (orden de
  `bloquear_para_cancelar`), recalcula los motivos, lanza el primero si los hay (409, como
  hoy) y, si no, crea la `EntradaProceso` del origen y transiciona a `ejecucion`. **Ya no
  crea reservas**: nacieron al preparar.
- **Un solo camino de inicio**: `inicio_reservado_al_puesto` cubre también la etapa
  Descremación, y `ejecuciones/{id}/transicionar/` rechaza `preparacion` → `ejecucion` con
  «Las corridas de descremado se inician desde el puesto de Descremado.». Pausar,
  bloquear, reanudar y cancelar siguen por la transición genérica.

### 3.4 Cancelar la preparación

`POST procesos/descremaciones/{id}/cancelar-preparacion/` con `{"motivo": "…"}`:

- `cancelar_preparacion_descremacion(*, corrida_id, usuario, motivo)`, simétrica a
  `cancelar_preparacion_secado`/`_evaporacion`: motivo obligatorio
  (`MENSAJE_MOTIVO_CANCELACION`); solo desde una corrida `borrador` cuya ejecución no es
  terminal. Una corrida iniciada se cierra registrando sus salidas.
- La transición genérica a `cancelada` ya suelta la máquina y libera las reservas activas.
  Lo propio de Descremación va en `_deshacer_preparacion_descremacion`, llamado desde
  `transicionar_ejecucion` como los otros dos —así cancelar desde la bandeja genérica
  deja lo mismo—: la corrida pasa a `anulada` con `motivo_anulacion`. No hay lote que
  anular ni leche que devolver: hasta el cierre no se mueve un litro.
- `bloquear_para_cancelar` agrega `CorridaDescremacion` a los modelos que bloquea antes de
  la ejecución.
- Respuesta: `{"ejecucion_id", "ejecucion_codigo", "estado"}`, como Evaporación.

### 3.5 Límites físicos: avisan

En `procesos/dominio.py`, sin ORM:

```python
LIMITE_GRASA_DESCREMADA = Decimal("0.1")                       # %, REGLAS §2
RANGO_GRASA_CREMA_DESPACHO = (Decimal("42"), Decimal("43"))     # %, REGLAS §2

def avisos_limites_descremacion(
    *, grasa_descremada, grasa_crema, crema_a_despacho,
) -> list[tuple[str, str]]:   # (codigo, mensaje)
```

- `grasa_descremada_alta`: grasa de la descremada **> 0,1 %**.
- `grasa_crema_fuera_de_rango`: grasa de la crema fuera de **[42; 43] %**, solo si
  `destino_crema == despacho_directo` —el límite es «crema para despacho»; la crema que va
  a Mantequilla o a Estandarización no lo tiene en el documento—.
- Un valor ausente no avisa (todavía no se tecleó).

Dónde se usa:

- **Mientras se teclea**: `POST procesos/descremaciones/{id}/revisar-cierre/` con el mismo
  cuerpo que `cerrar/` responde **sin escribir**
  `{"avisos_limites": [{"codigo", "mensaje"}], "avisos_balance": [...], "merma_l": "…",
  "desvio_grasa_kg": "…"}`, combinando esta función con `calcular_balance_descremacion`.
  Es el patrón de `calcular/` del vale: el formulario lo pide con retardo al cambiar un
  campo y pinta los avisos en ámbar. El cliente no calcula nada por su cuenta.
- **Al cerrar**: `cerrar_descremacion` llama a la misma función y guarda el resultado en
  `corrida.controles["avisos_limites"]` (lista de `{codigo, mensaje}`), **después** de
  mezclar los `controles` que mande el cliente, para que el cliente no pueda pisarlos —hoy
  ya pasa así con `avisos_balance`—. Los mensajes van además al `motivo` del
  `EventoProceso` de la transición a `pendiente_control`, que es lo que lee la auditoría
  de la ejecución.
- **Endurecer** (que la grasa alta impida cerrar o retenga el TK) es decisión de Calidad,
  y se hace en esta función y en quien la llama, no en una segunda regla.

Las **RPM** (1.395) no entran: no hay sensor ni campo, y en el documento son una alarma
del arranque («quitar alarma, reintentar, informar a Mantenimiento»), no una medición del
cierre. Siguen «No implementado» en REGLAS §2, con ese motivo.

### 3.6 Permisos

- Preparar, iniciar, cancelar, revisar el cierre y cerrar exigen la etapa Descremación
  (`puede_operar_tipo(usuario, EtapaProceso.Tipo.DESCREMACION)`) **en todos los caminos**:
  `OperaProcesoPorEtapa` con `tipo_etapa_operacional` ya lo hace en el viewset; se fija
  con una prueba con un usuario de Secado (403 en cada acción, nada creado).
- `POST procesos/descremaciones/` (el `create` del `ModelViewSet`) **se cierra** con
  `MethodNotAllowed`, como en Secado: hoy existe y crea una corrida sin reservas, sin plan
  verificado y sin pasar por `crear-guiada`.
- El viewset gana `QuerysetTenantMixin` (acotado por `ejecucion__sucursal`) y
  `FiltraConsultaMixin` para el historial: `busqueda_en = ("ejecucion__codigo",
  "silo_entera__codigo", "silo_descremada__codigo", "estanque_crema__codigo")`,
  `filtro_estado = "estado"`, `filtro_fecha = "ejecucion__creada_en"`.

### 3.7 Lo que no cambia

`sugerir-balance` y `sugerir_plan_descremacion`; `calcular_balance_descremacion`; el
cierre (movimientos de silo, herencia FIFO, reservas consumidas, merma, lotes intermedios
`INT-DES-{id}-LD/CR`, TK bloqueados por Calidad si la etapa lo requiere); la liberación
por rama en `/calidad`. `opciones-alta` conserva etapas, productos, rutas y `bloqueos` de
configuración, y **pierde** `equipos`, `silos_descremada` y `estanques_crema`: las
máquinas y los destinos los sirve `puesto/` con la regla de §3.2, una sola fuente.

## 4. Pantalla — `/produccion/descremado`

1. **Tarjetas por descremadora.** Estado inequívoco y **una sola acción** por estado; la
   tarjeta pinta lo que manda el servidor y no recalcula nada:
   - *Disponible* → «Preparar descremado» (abre el formulario con esa descremadora
     elegida). Con `motivos_para_tomar`: deshabilitado, el motivo y el enlace.
   - *Preparada* (origen → TK descremada + TK crema, litros planificados de cada rama) →
     «Iniciar descremado». Con `motivos_para_iniciar`: botón deshabilitado, el primer
     motivo debajo y un enlace a `resolver_en` (p. ej. «Analizar Silo 3» → `/silos`), solo
     si el usuario puede entrar a ese módulo (`moduloDeResolver`). Al lado,
     «Cancelar preparación»: motivo y `ConfirmarAccion`, como en los otros puestos.
   - *En curso* (inicio, litros de entrada, plan) → «Registrar salidas y cerrar».
   - Con `en_calidad`: una línea «Tk02 y TkC2 de EJ-DES-7 esperando Calidad».
   - Los `avisos` en ámbar, sin deshabilitar nada.
2. **Formulario «Preparar descremado»** (guiado, en el puesto): silo de origen (de
   `origenes`; preelegido con `?silo=`) con la composición que se usará, **sin selector de
   análisis** → descremadora → litros → producto y TK de cada rama (solo destinos de
   `puesto/`) → destino y ruta de la crema → «Calcular sugerencia» → litros planificados
   editables y la casilla «Confirmo…» → **resumen y confirmar** con `ConfirmarAccion`
   («Preparar descremado»). Sin campo de código ni de etapa (la etapa se elige sola si hay
   una activa; si hay varias, se ofrece).
3. **Cierre** («Registrar salidas y cerrar»): el `CierreDescremacion` actual movido al
   puesto, con los avisos de `revisar-cierre/` bajo los campos mientras se teclea y un
   resumen con `ConfirmarAccion` que repite los avisos antes de cerrar.
4. **Corridas de hoy** debajo, cargadas solas —sin «Cargar corridas»—, y un
   **«Historial»** con `q`, `estado`, `desde`/`hasta` del servidor (`TablaConsulta`, como
   Secado y Despacho).
5. **Acceso**: ruta bajo el módulo `produccion`, como Evaporación. Operan Condensación y
   administración (helper `puedeOperarDescremado`, espejo de `TIPOS_OPERABLES_POR_AREA`,
   con prueba unitaria); Calidad ve en modo consulta.

Las funciones puras del frontend van en `services/puesto-descremado.ts`:
`accionDeDescremadora(fila)` (botón, habilitación y motivo; espejo de
`accionDeTorre`), `corridaCancelable(fila)` y la situación de una corrida para la lista.

### 4.1 Lo que se retira

- `/procesos`: la sección `proceso-descremacion`, el estado y efectos de descremación, y
  los modales `FormularioDescremacion` y `CierreDescremacion` (el cierre se mueve a
  `pages/Descremado/`, el formulario se reescribe ahí).
- Redirecciones: `/procesos?seccion=descremacion` → `/produccion/descremado`, y
  `/procesos?accion=descremar&silo=<id>` → `/produccion/descremado?silo=<id>`, en el mismo
  bloque de `Procesos.tsx` que ya redirige `condensacion`/`evaporacion`.
- `Silos.tsx`: «Descremar» enlaza a `/produccion/descremado?silo=<id>`.
- Menú (`navegacion-operacional.ts`): «Descremado» → `/produccion/descremado`, módulo
  `produccion`, con alias `/procesos?seccion=descremacion` para el enlace activo.
- `rutaDeEtapa` (`services/planta-ahora.ts`) y `RUTAS_POR_ETAPA`
  (`procesos/dominio.py`) apuntan al puesto para `descremacion`.
- `/produccion`: el atajo «1. Descremación» enlaza al puesto.
- «Ejecuciones operativas» y «Mi trabajo pendiente» muestran las ejecuciones de
  Descremación sin el botón de iniciar (el servidor ya no lo ofrece en
  `acciones_permitidas`) y con un enlace al puesto, como Secado.
- `procesos.service.ts`: `crearDescremacion` (sin uso, contra el `create` que se cierra);
  `crearDescremacionGuiada` pierde `codigo` y `analisis_entrada`.

## 5. Pruebas

- **Backend** (`procesos/tests_descremacion.py` y un `tests_puesto_descremado.py`):
  - `puesto/`: los tres estados; en curso manda sobre preparada; huérfano con ejecución
    terminal → `disponible`; `motivos_para_iniciar` vacío y con motivo (sin segunda firma
    → `resolver_en = "/silos"`; descremadora en CIP → `"/calidad/inocuidad"`); aseo
    observado: aviso, no motivo; `en_calidad` con la ejecución anterior en
    `pendiente_control`; `destinos_*` sin TK bloqueados, en CIP ni reservados por otra
    ejecución; `origenes` con el análisis que usará preparar y con `motivo` sin análisis.
  - Preparar: crea corrida, **tres reservas activas** y ejecución en `preparacion` con la
    máquina tomada; análisis elegido por el servidor; TK sin capacidad → 400 y nada creado
    (sin corrida, sin reservas, máquina libre); descremadora ocupada → 400; código
    `EJ-DES-{pk}`; un `codigo` o `analisis_entrada` enviado se ignora.
  - Iniciar: con motivos → 409 y la ejecución sigue en `preparacion`; sin motivos →
    `ejecucion`, una entrada, **ninguna reserva nueva**; análisis superado por uno más
    nuevo → motivo; `motivos_para_iniciar_descremacion` coincide con lo que rechaza
    `iniciar`.
  - Cancelar: suelta reservas (`liberada`) y máquina, corrida `anulada` con motivo; sin
    motivo → 400; sobre una en curso → 400; desde la bandeja genérica deja lo mismo.
  - `transicionar` genérico `preparacion` → `ejecucion` de una Descremación → 400; pausar
    una en curso sigue funcionando.
  - `revisar-cierre/` no escribe nada; `cerrar/` guarda `avisos_limites` (descremada 0,15
    % → aviso; 0,10 → sin aviso; crema 41 % a despacho → aviso; 41 % a mantequilla → sin
    aviso) y el cliente no los puede pisar por `controles`.
  - `avisos_limites_descremacion` en pruebas de dominio, bordes incluidos.
  - Usuario de Secado → 403 en preparar, iniciar, cancelar, revisar y cerrar;
    `POST descremaciones/` → 405.
  - Ajustar las cuatro pruebas que hoy esperan las reservas al iniciar
    (`test_inicio_reserva_origen…`, `test_cancelar_libera_las_reservas_de_tk`,
    `test_no_inicia_si_el_plan_supera_capacidad_del_tk`,
    `test_un_tk_con_reserva_activa_no_se_asigna_a_otra_corrida`): las reservas y sus
    rechazos pasan a preparar; el inicio comprueba que siguen.
  - `tests_destinos.py`: `RUTAS_POR_ETAPA["descremacion"]`.
- **Frontend (unitarias)**: `accionDeDescremadora` y `corridaCancelable` derivan botón,
  habilitación y motivo de la respuesta; `puedeOperarDescremado`; `rutaDeEtapa`
  (`tests/planta-ahora.test.ts`) y el enlace activo del menú
  (`tests/navegacion-operacional.test.ts`, que hoy fija `?seccion=descremacion`).
- **E2E**: `frontend/e2e/flujo-descremado.spec.ts` reescrito sobre el puesto. En las dos
  pruebas: Producción entra por «Descremar» del silo y llega al puesto con el silo
  elegido → prepara (sugerencia, confirmación) → ve «Iniciar descremado» **deshabilitado**
  con el motivo de la segunda firma y el enlace a `/silos` → Calidad completa el análisis
  del origen → inicia → registra las salidas viendo el aviso cuando corresponda → Calidad
  libera cada rama. La tarjeta se busca por el `ejecucion_codigo` que devuelve el servidor,
  no por un código tecleado. Se ajusta `e2e/README.md` (§ descremado) si nombra pantallas.
- **Accesibilidad**: `/produccion/descremado` entra a `e2e/rutas.ts`; sin reglas nuevas.

## 6. Riesgos

- **Mover las reservas de `iniciar` a `preparar`** cambia cuándo un TK queda tomado: una
  corrida preparada y olvidada retiene dos TK y litros del silo de origen. Por eso
  «Cancelar preparación» va en el mismo cambio, la tarjeta *Preparada* se ve en el puesto
  y los destinos con reserva no se ofrecen. Las corridas `borrador` heredadas (de un
  `iniciar` que falló en el modal viejo) tienen la ejecución en `borrador`, sin reservas ni
  máquina: no ocupan, se listan en el historial y se cancelan con la misma acción, que
  acepta ejecución `borrador` o `preparacion`.
- **Usos a migrar** (búsqueda del 2026-10-07):
  - `backend/procesos/dominio.py:52` (`RUTAS_POR_ETAPA`) y `backend/procesos/tests_destinos.py:21`.
  - `backend/procesos/servicios.py`: `crear_descremacion_guiada`, `iniciar_descremacion`,
    `cerrar_descremacion`, `bloquear_para_cancelar`, `inicio_reservado_al_puesto`,
    `transicionar_ejecucion` (gancho de cancelación).
  - `backend/procesos/views.py`: `CorridaDescremacionViewSet` (`opciones-alta`,
    `crear-guiada`, `iniciar`, `cerrar`; `create`; mixins) y el mensaje de
    `transicionar`.
  - `backend/procesos/serializers.py`: `CrearDescremacionGuiadaSerializer` (sin `codigo` ni
    `analisis_entrada`).
  - `backend/procesos/tests_descremacion.py` (las cuatro pruebas de §5).
  - `frontend/src/pages/Procesos/Procesos.tsx` (imports, estado, efecto `accion=descremar`,
    modales y sección), `FormularioDescremacion.tsx`, `CierreDescremacion.tsx`.
  - `frontend/src/pages/Leche/Silos.tsx:359`, `frontend/src/pages/Produccion/Produccion.tsx:267`.
  - `frontend/src/services/navegacion-operacional.ts:56`, `frontend/src/services/planta-ahora.ts:6`,
    `frontend/src/services/procesos.service.ts` (descremación), `frontend/src/app/routes.tsx`.
  - `frontend/tests/navegacion-operacional.test.ts:119-132`, `frontend/tests/planta-ahora.test.ts:8,21`.
  - `frontend/e2e/flujo-descremado.spec.ts`, `frontend/e2e/rutas.ts`, `frontend/e2e/README.md:176-186`.
  - Sin uso hoy y sin cambio: `sembrar_flujo_demo` y `preparar_circuito_polvo` no
    descreman; `preparar_circuito_descremado` siembra la máquina y los maestros, no
    corridas; `reset_datos_operacionales` borra corridas y no depende del flujo.
- **Base de la rama**: `main` no tiene los puestos de Evaporación ni Secado; este puesto
  copia su patrón y toca los mismos archivos de menú, rutas y `transicionar_ejecucion`. La
  rama nace de la que los tenga integrados (hoy `feature-detalles-secado`).

## 7. Fuera de alcance

El puesto de Mantequilla; un motor de puesto genérico (con tres puestos ya se ve qué
comparten —tarjeta, acción servida, cancelar, historial—, pero extraerlo es su propio
diseño); que los límites de grasa bloqueen el cierre o retengan el TK (decisión de
Calidad); las RPM de la descremadora; mostrar `avisos_limites` en la tarjeta de liberación
de `/calidad`; el control horario de equipos de §2 de REGLAS (descremadora, pasteurizador,
bombas, válvulas), que es un registro periódico y se cargaría como plantilla de
`RegistroEquipo`, no aquí.

## 8. Desviaciones y supuestos

Lo que el código contradice de las decisiones, o deja abierto, y cómo se resolvió (camino
general, sin detenerse a preguntar):

1. **Las reservas hoy nacen al iniciar, no al preparar.** `crear_descremacion_guiada` no
   reserva nada; `iniciar_descremacion` crea las tres `ReservaSiloProceso`. La decisión
   pide preparar *con* reservas, y en Evaporación las reservas también nacen al iniciar
   (`estado_puesto_evaporacion` lo dice: «Las corridas solo preparadas no reservan»).
   **Resuelto a favor de la decisión**: las reservas pasan a preparar (§3.2), que es lo que
   hace que «cancelar suelta las reservas» signifique algo y que un TK preparado no se
   ofrezca a otra corrida. La diferencia con Evaporación queda anotada; alinear Evaporación
   no entra aquí.
2. **La descremadora hoy no se ocupa hasta iniciar.** La ejecución nace en `borrador`, que
   no está en `ESTADOS_QUE_OCUPAN_EQUIPO`. Preparar la pasa a `preparacion` para que la
   máquina quede tomada, como la torre en Secado.
3. **El análisis lo elige el cliente** (desplegable sobre `listarAnalisisSilo` filtrado en
   el navegador) y `crear-guiada` acepta cualquiera confirmado y vigente aunque no sea el
   último. Como `motivos_silo_no_disponible` evalúa el **último** confirmado, una corrida
   podía prepararse con un análisis viejo y luego iniciar contra uno nuevo con la
   composición congelada del viejo. **Resuelto**: el servidor elige el análisis y el
   inicio exige que siga siendo el vigente (motivo nuevo en §3.3).
4. **Dos firmas al preparar.** La decisión pone «análisis vigente con dos firmas» entre los
   motivos de inicio. Preparar exige solo lo necesario para el plan (confirmado, vigente,
   grasa y SNG) y deja firmas, inhibidores y 48 h como motivos de inicio, para que el
   puesto pueda mostrar «Iniciar» deshabilitado con su enlace, como Evaporación.
5. **El código de ejecución lo teclea el operador** (`DES-<fecha>` sugerido y editable; el
   E2E lo usa para encontrar la tarjeta). Ninguna decisión lo toca; **supuesto**: lo asigna
   el servidor (`EJ-DES-{pk}`), como en los demás caminos que crean ejecuciones, y el E2E
   busca por el código devuelto.
6. **`POST procesos/descremaciones/` está abierto** (el `create` del `ModelViewSet` no se
   anuló) y el servicio del frontend tiene un `crearDescremacion` sin uso. Se cierra con
   405 (§3.6).
7. **El viewset no está acotado por empresa** (sin `QuerysetTenantMixin`, a diferencia de
   Mantequilla y Secado). Se agrega junto con el filtro de historial; el puesto filtra con
   `filtrar_por_scope` como los otros.
8. **`opciones-alta` y el formulario tenían dos fuentes de ocupación** (`ocupado_por` del
   servidor y `ocupacionesPorEquipo` sobre las ejecuciones del cliente) y ofrecían TK sin
   filtrar. Se reemplazan por `puesto/` (§3.7).
9. **Límite de la crema**: el documento dice «crema para despacho». **Supuesto**: el aviso
   42–43 % aplica solo con `destino_crema = despacho_directo`; para Mantequilla o
   Estandarización no hay límite documentado y no se inventa. Los límites son constantes
   de planta en `dominio.py`, no se leen de la `Especificacion` del producto: la
   especificación la decide Calidad al liberar sobre el análisis del TK, y el aviso del
   puesto es la lectura física del cierre. Si Calidad prefiere que el umbral salga de la
   especificación, se cambia en esa función.
10. **RPM** (1.395): sin campo ni sensor; fuera (§3.5).
11. **Cancelar una corrida en curso por la bandeja genérica** libera reservas pero deja la
    corrida en `en_curso`: el puesto la ignora por la ejecución terminal (§3.1), igual que
    los huérfanos de los otros puestos. No se agrega un «anular corrida en curso».
12. **URL de preparar**: se conserva `crear-guiada/` (Evaporación también la conservó); el
    nombre no promete iniciar, a diferencia de `iniciar-desde-inventario` en Secado, que se
    renombró por eso.
