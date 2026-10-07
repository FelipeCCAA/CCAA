# Puesto de Secado

**Fecha:** 2026-10-06
**Origen:** revisión UX industrial de los menús de fabricación (2026-10-02). Segundo de los
puestos por proceso; sigue el patrón del Puesto de Evaporación
(`docs/superpowers/specs/2026-10-05-puesto-evaporacion-design.md`, PR #2).
**Guía de criterio:** `.agents/skills/disenador-ux-industrial/SKILL.md`.

---

## 1. El problema

Hoy secar un concentrado reparte el trabajo en tres lugares, y uno de ellos no es del
puesto:

| Paso | Dónde | Qué |
|---|---|---|
| 1 | `/produccion` › «Materiales intermedios liberados» (no autocarga: «Consultar disponibles») | elegir etapa Secado, torre y cantidad → `preparar-continuacion` |
| 2 | «Ejecuciones operativas» u otra bandeja genérica | pasar la ejecución de preparación a ejecución con `ejecuciones/{id}/transicionar/` |
| 3 | `/secado` | «Registrar balance y cerrar corrida» |

- **`/secado` no tiene botón para iniciar.** El único camino es la transición genérica, fuera
  del puesto.
- **Las reglas de inicio están dispersas** en `preparar_continuacion`,
  `crear_secado_desde_inventario` y `transicionar_ejecucion`, cada una con su
  `raise ValidationError`. No hay función que la pantalla pueda consultar antes de intentar:
  el rechazo llega con el POST.
- **La alimentación externa** (`iniciar-desde-inventario`) deja la corrida directamente en
  ejecución, mientras que la continuación desde un concentrado la deja en preparación: dos
  comportamientos según la fuente.
- La **inspección pre-operativa E1-E2** (`CCAA.Sec.FORM.003`, plantilla cargada, frecuencia
  `por_ciclo`) se registra en `/registros`, pero ninguna regla de inicio la mira.

Dato de modelo que condiciona el diseño: **en Secado no se abre un lote**.
`preparar_continuacion` toma la `SalidaProceso` liberada y mueve a la torre el **mismo lote**
que salió del evaporador (`lote.ejecucion`, `lote.equipo`). El puesto no «abre lote»: **toma
alimentación y la asigna a una torre**.

## 2. Decisiones

Tomadas con el usuario el 2026-10-06.

| Decisión | Elegido |
|---|---|
| Orden de los puestos | **Secado** primero; después Descremado y Mantequilla, cada uno con su diseño |
| Preparar e iniciar | **Dos pasos**, como Evaporación: «Tomar concentrado» deja la torre preparada; «Iniciar secado» se habilita solo cuando el servidor lo permitiría |
| Alimentación externa | **También en dos pasos**: es otra forma de tomar, con el mismo inicio y las mismas reglas |
| Inspección pre-operativa | **Avisa, no bloquea**. Endurecerla es decisión de Calidad sobre una sola función |
| Enfoque técnico | **Puesto propio** con funciones de reglas de Secado (no un motor genérico, no solo frontend) |

## 3. Backend

### 3.1 Estado del puesto

`GET procesos/secados/puesto/` devuelve:

```json
{
  "torres": [{
    "equipo_id": 7, "codigo": "e1", "nombre": "Torre de secado Egron 1",
    "estado": "disponible | preparada | en_curso",
    "corrida": { "id": 12, "ejecucion_id": 90, "ejecucion_codigo": "CONT-40-AB12CD34",
                  "ejecucion_estado": "preparacion", "lote_codigo": "CCAA6279VB-01",
                  "origen": "SILO 6", "cantidad": "18000.00", "unidad": "L",
                  "iniciada_en": null },
    "motivos_para_iniciar": ["La torre e1 está en CIP."],
    "resolver_en": "/calidad/inocuidad | /calidad | null",
    "avisos": ["Falta la inspección pre-operativa de hoy (CCAA.Sec.FORM.003)."],
    "falta_inspeccion": true,
    "en_calidad": { "id": 11, "lote_codigo": "CCAA6278VB-01" }
  }],
  "concentrados": [{ "salida_id": 40, "etapa_id": 5, "lote_codigo": "CCAA6279VB-01",
                     "producto": "Leche entera en polvo", "silo": "SILO 6",
                     "disponible": "18000.00", "unidad": "L" }],
  "corridas_de_hoy": [{ "id": 11, "equipo": "e1", "lote_codigo": "CCAA6278VB-01",
                        "estado": "cerrada", "estado_calidad": "pendiente" }],
  "estados": [{ "valor": "preparacion", "etiqueta": "Preparación" }]
}
```

Las claves extra existen para no adivinar: `etapa_id` lo exige `preparar-continuacion`; el
enlace y el aviso de inspección viajan tipados.

- **Estado por torre**, derivado de su `EjecucionProceso` de Secado no terminal:
  `preparacion` → `preparada`; `ejecucion`, `pausada` o `bloqueada` → `en_curso`; sin
  ejecución activa → `disponible`. Una ejecución `cerrada` o `cancelada` no ocupa la torre
  (`ESTADOS_EJECUCION_TERMINALES`, igual que en Evaporación).
- **`motivos_para_iniciar`** (solo en `preparada`) lo calcula `motivos_para_iniciar_secado`
  (§3.3).
- **`avisos`** no bloquean. Hoy son dos:
  - el aseo con advertencia (`advertencia_aseo_equipo`, el mismo texto que ya va al evento);
  - la **falta de una inspección pre-operativa completa para esa torre en la fecha de hoy**.
    Se decide con la misma regla que el checklist del lote —`calidad.dominio.cubre_al_lote`
    sobre los `RegistroEquipo` de `CCAA.Sec.FORM.003` de esa torre, con la fecha local de
    hoy— y con `registro_completo`, para que «hay inspección» signifique lo mismo en el
    puesto y en el expediente.
- **`en_calidad`**: la última corrida de esa torre cuyo polvo sigue pendiente en Calidad
  (`LiberacionProceso` pendiente sobre su `SalidaProceso`). Es informativa: al cerrar el
  secado la ejecución pasa a `cerrada` (`registrar_produccion`) y la torre queda libre.
- **`concentrados`**: salidas liberadas cuya siguiente etapa activa
  (`siguiente_etapa_para_salida`) es Secado y con saldo disponible, calculado con la **misma
  función** que usa `preparar_continuacion` para rechazar una cantidad excesiva. Una
  cantidad, una consulta (caso 1 de «La pantalla ofrece lo que el backend va a rechazar» en
  `CLAUDE.md`). Si hoy esa cuenta vive en línea dentro de `preparar_continuacion`, se extrae.
- **`corridas_de_hoy`**: corridas de Secado iniciadas o cerradas hoy, sin huérfanos cuya
  ejecución terminó sin iniciarse.
- Montos decimales viajan como **texto**, como en Evaporación.
- **Lectura**: las áreas que hoy ven `/secado` (Secado, Calidad) y administradores.

### 3.2 Tomar alimentación (preparar)

- **Concentrado liberado**: `POST procesos/salidas/{id}/preparar-continuacion/` existente.
  Ya reserva la torre al pasar a `preparacion` (`adquirir_equipo`) y rechaza una ocupada.
- **Externa**: la acción `secados/iniciar-desde-inventario/` pasa a llamarse
  `secados/preparar-desde-inventario/` y deja la corrida en **`preparacion`**, no en
  ejecución. La acción antigua **se elimina**, no se mantiene como alias: un nombre que dice
  «iniciar» y no inicia invita al error. `crear_secado_desde_inventario` cambia la transición
  final y su nombre si lo lleva.

### 3.3 Iniciar

`POST procesos/secados/{id}/iniciar/`:

- `motivos_para_iniciar_secado(corrida) -> list[str]` en `procesos/servicios.py` es **la
  única implementación** de las reglas de inicio de Secado:
  - la ejecución está en `preparacion`;
  - tiene al menos una entrada;
  - la torre está habilitada (`motivo_equipo_no_habilitado`: no en CIP);
  - la alimentación sigue disponible: la salida de origen no fue rechazada por Calidad ni
    quedó consumida por otra ejecución entre la preparación y el inicio (para la externa, el
    lote de proveedor sigue liberado y con saldo).

  El aseo observado no está en esta lista: avisa (`avisos_de_torre`), no bloquea.
- `iniciar` toma la ejecución con `select_for_update`, recalcula los motivos, lanza el
  primero si los hay (400) y, si no, transiciona a `ejecucion`. Los avisos van al `motivo`
  del `EventoProceso`, como hoy el aseo con advertencia.
- **Un solo camino de inicio**: `ejecuciones/{id}/transicionar/` rechaza pasar de
  `preparacion` a `ejecucion` en una ejecución de etapa Secado con «Las corridas de secado se
  inician desde el puesto de Secado.». Las demás transiciones genéricas (pausar, bloquear,
  cancelar) siguen disponibles, y **reanudar desde `pausada` o `bloqueada` sigue
  disponible**: ese paso no es iniciar (`inicio_reservado_al_puesto`), y una torre pausada
  necesita cómo volver.
- Una salida sin lote o un lote que ya tiene corrida de Secado no se preparan
  (`CorridaSecado.lote` es uno a uno): `preparar_continuacion` los rechaza antes de reservar
  la torre.

### 3.4 Permisos

- Preparar, iniciar y cerrar exigen el permiso de la etapa Secado
  (`procesos.permisos.puede_operar_tipo(usuario, EtapaProceso.Tipo.SECADO)`) **en todos los
  caminos**. `preparar-continuacion` vive en otro viewset: cuando la etapa elegida es Secado
  debe exigir ese permiso (403 en caso contrario). Es el mismo hueco que tenía
  `confirmar-borrador` en Evaporación; se fija con una prueba con un usuario de
  Condensación.

### 3.5 Lo que no cambia

`cerrar_secado`, el balance (`CorridaSecado.clean`, `rendimiento_recuperacion_pct`), la cola
de cierre (`cerrar_lote_producido`) y la liberación del polvo por Calidad.

## 4. Pantalla — `/produccion/secado`

1. **Tarjetas por torre** (E1, E2). Estado inequívoco y **una sola acción** por estado; la
   tarjeta pinta lo que manda el servidor y no recalcula nada:
   - *Disponible* → «Tomar concentrado» (abre el formulario con esa torre elegida).
   - *Preparada* (lote, origen, cantidad) → «Iniciar secado». Con `motivos_para_iniciar`:
     botón deshabilitado, el motivo debajo y un enlace a donde se resuelve. Los `avisos` se
     muestran en ámbar sin deshabilitar nada; el de inspección enlaza a `/registros`.
   - *En curso* → «Registrar balance y cerrar» (el `CierreSecado` actual).
   - Con `en_calidad`: una línea informativa «Polvo de {lote} esperando Calidad».
2. **Formulario «Tomar concentrado»** (guiado): fuente —concentrado liberado (lista del
   servidor, con saldo) o alimentación externa (lote de proveedor liberado)— → torre →
   cantidad → (externa: orden y código de lote de salida, como hoy) → **resumen y
   confirmar** con `ConfirmarAccion` («Preparar torre»).
3. **Corridas de hoy** debajo, cargadas solas. Las bandejas actuales de `/secado`
   (calidad, terminadas, historial) pasan a esta lista y a un **«Historial»** con filtros de
   servidor, como en el puesto de Despacho. `bandejaDeSecado` sigue siendo el único
   clasificador.
4. **Acceso**: operan las áreas Secado y administración (helper `puedeOperarSecado`, espejo
   de `TIPOS_OPERABLES_POR_AREA`, con prueba unitaria); Calidad ve en modo consulta.

### 4.1 Lo que se retira

- `/secado` redirige a `/produccion/secado`; la entrada del menú, `rutaDeEtapa` (frontend) y
  `ruta_de_etapa` (backend) apuntan al puesto para la etapa `secado`.
- «Materiales intermedios liberados» de `/produccion` deja de ofrecer **Secado** como etapa
  siguiente; sigue para las demás (mantequilla, estandarización, despacho a granel).
- Las bandejas genéricas («Ejecuciones operativas», «Mi trabajo pendiente») muestran las
  ejecuciones de Secado con un enlace al puesto en vez del botón de transición a ejecución.
- El modal «Alimentación externa» de `/secado` se integra al formulario «Tomar concentrado» (§4, punto 2).

## 5. Pruebas

- **Backend**:
  - `puesto/`: los tres estados por torre; `motivos_para_iniciar` vacío y con motivo (CIP,
    salida de origen rechazada); aseo observado: aviso, no motivo; aviso de inspección —sin
    registro hoy: aviso; con registro completo hoy: sin aviso; con registro de ayer: aviso;
    con registro incompleto hoy: aviso—; `en_calidad` con polvo pendiente; `concentrados`
    solo con saldo y con Secado como siguiente etapa; huérfanos fuera.
  - `iniciar`: con motivos → 400 y la ejecución sigue en `preparacion`; sin motivos →
    `ejecucion`, con el aviso en el evento; sin permiso de Secado → 403.
  - `preparar-desde-inventario` deja la corrida en `preparacion`; `iniciar-desde-inventario`
    ya no existe (404).
  - `preparar-continuacion` hacia Secado con usuario de Condensación → 403, nada creado.
  - `transicionar` genérico a `ejecucion` de una ejecución de Secado → 400; pausar sigue
    funcionando.
  - `motivos_para_iniciar_secado` coincide con lo que rechaza `iniciar`.
- **Frontend (unitarias)**: `accionDeTorre(fila)` deriva botón, habilitación y motivo de la
  respuesta; `puedeOperarSecado`; `bandejaDeSecado` sin cambios de comportamiento.
- **E2E**: `flujo-polvo-continuacion.spec.ts` reescrito sobre el puesto (tomar concentrado →
  «Iniciar» habilitado → iniciar → registrar balance). La cadena
  `circuito → evaporacion → flujo-polvo` sigue 4/4. `flujo-suero.spec.ts` se ajusta si usa
  `/produccion#continuidad` para Secado.
- **Accesibilidad**: `/produccion/secado` entra a `e2e/rutas.ts`; sin reglas nuevas.

## 6. Riesgos

- **Cerrar el `transicionar` genérico para Secado**: antes se busca cada uso que inicie una
  ejecución de Secado —pantallas, `sembrar_flujo_demo`, `preparar_circuito_polvo`, pruebas
  y E2E— y se pasa al servicio de inicio.
- **Renombrar `iniciar-desde-inventario`**: misma búsqueda en `secado.service.ts`, pantallas
  y E2E.
- **Base de la rama**: el PR #2 (Evaporación) no está integrado y este puesto copia su patrón
  y toca los mismos archivos de menú y rutas. La rama `feature-puesto-secado` nace de
  `feature-puesto-evaporacion` y su PR se integra después del #2.

## 7. Fuera de alcance

Puestos de Descremado y Mantequilla; un motor de puesto genérico (se extrae cuando haya tres
puestos y se vea qué comparten); historial y cancelación de corridas preparadas en
Evaporación; que la inspección pre-operativa bloquee el inicio (decisión de Calidad).
