# Puesto de Evaporación

**Fecha:** 2026-10-05
**Origen:** revisión UX industrial de los menús de fabricación (2026-10-02). Es el primero de
los puestos por proceso; Secado, Mantequilla y Descremado seguirán el patrón que este deja.
**Guía de criterio:** `.agents/skills/disenador-ux-industrial/SKILL.md`.

---

## 1. El problema

Hoy evaporar un lote son **5 pasos en 3 pantallas**:

| Paso | Dónde | Qué |
|---|---|---|
| 1 | `/produccion` › «Abrir lote desde vale» | vale, fecha, evaporador, OP, código, litros |
| 2 | `/procesos` › «Nueva evaporación» (sin entrada en el menú) | lote y **silo de destino** → «Crear corrida preparada» |
| 3 | `/silos` | Calidad analiza el silo de origen (después de abrir el lote) |
| 4 | `/procesos` › «Cargar corridas» › «Iniciar evaporación» | inicio |
| 5 | `/procesos` › «Registrar salida» | precondensado y controles → Calidad |

Además, iniciar una evaporación se puede hacer desde **cuatro** lugares (tarjetas de
evaporadores en `/produccion`, la tabla de `/procesos`, «Ejecuciones operativas» y «Mi trabajo
pendiente»), cada uno con su propio texto de error. Y los pasos 1 y 2 son dos llamadas
separadas: si la segunda falla, queda un lote abierto con el evaporador ocupado y sin
destino.

## 2. Decisiones

Tomadas con el usuario el 2026-10-05.

| Decisión | Elegido |
|---|---|
| Primer puesto | **Evaporación**; los demás siguen el patrón |
| Destino del concentrado | Se decide **al abrir el lote**: abrir y preparar son un solo formulario |
| Inicio | **Botón «Iniciar» aparte**: preparar e iniciar son momentos distintos; «Iniciar» se habilita solo cuando el servidor lo permitiría |
| Alcance | **Todo lo que pasa por evaporador**: polvo y precondensado líquido |
| Enfoque técnico | **Una sola operación en el servidor** (todo o nada) |

## 3. Backend

### 3.1 Abrir y preparar en una transacción

`POST produccion/lotes/{id}/confirmar-borrador/` (ya `@transaction.atomic`) acepta un campo
nuevo `silo_destino`:

- Si la máquina del lote es un **evaporador**, `silo_destino` es **obligatorio**. Sin él → 400
  `{"silo_destino": "Elige el silo de destino del concentrado."}`, y no se crea nada.
- Con él, en la misma transacción: `abrir_lote_desde_vale(...)` (descuenta el silo del vale y
  abre la ejecución de evaporación) y luego `crear_condensacion_guiada(lote_id, silo_destino_id,
  usuario)`. Cualquier `ValidationError` de cualquiera de los dos revierte todo: ni lote, ni
  movimiento de silo, ni corrida, ni evaporador ocupado.
- Si la máquina **no** es un evaporador, `silo_destino` se ignora y todo sigue como hoy (crema
  y demás familias).

### 3.2 Destinos válidos

Los silos de destino que se ofrecen salen del servidor y son solo los que el cierre aceptará:
estado **`disponible`** (no `bloqueado_calidad` ni otro) y con capacidad libre ≥ litros pedidos.
Hoy `procesos.opciones_alta` ofrece todos los silos activos y escribe «Bloqueado por Calidad» en
la etiqueta sin deshabilitarla; el rechazo llega al **cerrar** la corrida (caso 2 de «La
pantalla ofrece lo que el backend va a rechazar» en `CLAUDE.md`). La validación de
`crear_condensacion_guiada` rechaza un destino no disponible con un mensaje que lo nombre.

### 3.3 Estado del puesto

`GET procesos/condensaciones/puesto/` devuelve una fila por evaporador activo:

```json
{
  "evaporadores": [{
    "equipo_id": 3, "codigo": "scheffers3", "nombre": "Evaporador Scheffers 3",
    "estado": "disponible | preparada | en_curso | esperando_calidad",
    "corrida": { "id": 41, "codigo": "EJ-PROD-87", "lote_codigo": "CCAA6278SH3-01",
                  "silo_origen": "TK 3", "silo_destino": "SILO 6",
                  "litros_entrada": "20000.00", "iniciada_en": null },
    "en_calidad": null,
    "motivos_para_iniciar": ["El silo TK 3 no tiene un análisis confirmado y vigente."]
  }],
  "destinos": [{ "id": 6, "codigo": "SILO 6", "libre_l": "48000.00" }],
  "corridas_de_hoy": [{ "id": 40, "codigo": "EJ-PROD-86", "equipo": "veb",
                        "lote_codigo": "CCAA6278VB-01", "estado": "cerrada" }]
}
```

- El estado se deriva de **una sola corrida** por evaporador: la `en_proceso` manda sobre la
  `borrador`; sin corrida activa, `disponible`; con la ejecución en `pendiente_control`,
  `esperando_calidad`. La lógica que hoy vive en `frontend/src/services/estado-evaporador.ts`
  pasa aquí.
- `en_calidad` es un dato aparte de `corrida`: la corrida con ejecución `pendiente_control` en esa
  máquina, aunque la fila ya muestre una `preparada` o `en_curso` nueva. La máquina física puede
  estar libre para empezar mientras el destino de la corrida anterior sigue esperando a Calidad;
  ocultar eso detrás de la corrida nueva escondería que ese silo sigue bloqueado. Cuando la fila
  misma es `esperando_calidad`, `en_calidad` es esa misma corrida.
- `motivos_para_iniciar` (solo para `preparada`) lo calcula una función nueva
  `motivos_para_iniciar_condensacion(corrida)` en `procesos/servicios.py`, extraída de
  `iniciar_condensacion`: estado de la orden, equipo habilitado (`motivo_equipo_no_habilitado`),
  silo de origen disponible para proceso (`motivos_silo_no_disponible(..., para="proceso")`) y
  saldo/capacidad. `iniciar_condensacion` la llama y lanza el primer motivo: **una regla, una
  implementación**, así que la pantalla nunca habilita «Iniciar» cuando el servidor lo
  rechazaría.
- Permiso de lectura: las mismas áreas que hoy ven la evaporación (Condensación, Calidad) y
  administradores.

### 3.4 Lo que no cambia

`condensaciones/{id}/iniciar/` y `condensaciones/{id}/cerrar/` mantienen sus reglas.

## 4. Pantalla — `/produccion/evaporacion`

1. **Tarjetas por evaporador** (arriba). Estado inequívoco y **una sola acción** por estado:
   - *Disponible* → «Abrir lote desde vale» (abre el formulario con ese evaporador elegido).
   - *Preparada* (lote, origen → destino, litros) → «Iniciar evaporación». Con
     `motivos_para_iniciar` no vacío: botón deshabilitado, el motivo debajo y un enlace a donde
     se resuelve (p. ej. «Analizar silo TK 3» → `/silos`).
   - *En curso* (inicio, litros de entrada) → «Registrar salida y cerrar».
   - *Esperando Calidad* → informativa, con el código del lote.
   La tarjeta pinta lo que manda el servidor; no recalcula el estado.
2. **Formulario guiado** (un solo formulario, con borrador y autoguardado como hoy): vale (solo
   productos que van a evaporador y con saldo) → evaporador → orden de producción → silo de
   destino (solo los válidos, §3.2) → código de lote (sugerido) → litros → **resumen y
   confirmar** con `ConfirmarAccion`.
3. **Corridas de hoy** (debajo), cargadas solas —sin el botón «Cargar corridas»—.
4. **Acceso**: entrada «Evaporación» del menú → `/produccion/evaporacion`; áreas Condensación y
   Calidad, y administradores.

### 4.1 Lo que se retira

- `/produccion`: el panel de evaporadores pasa a una línea de resumen con enlace al puesto.
- Formulario de lote en `/produccion`: los productos que van a evaporador se abren en el puesto;
  las demás familias siguen ahí.
- `/procesos`: la sección «Evaporación / precondensado» («Nueva evaporación» y la tabla).
- Redirecciones: `/procesos?seccion=condensacion|evaporacion` y `/produccion?seccion=evaporacion`
  → `/produccion/evaporacion`. `rutaDeEtapa` (frontend) y `ruta_de_etapa` (backend) apuntan al
  puesto para `evaporacion` y `condensacion`.

## 5. Pruebas

- **Backend**: confirmar sobre evaporador sin destino → 400 sin efectos; con destino → lote,
  movimiento y corrida juntos; fallo de `crear_condensacion_guiada` (p. ej. destino bloqueado)
  → nada creado ni descontado; destinos bloqueados no se ofrecen; estado por evaporador (las
  cuatro situaciones y la prioridad `en_proceso` sobre `borrador`); `motivos_para_iniciar`
  coincide con lo que rechaza `iniciar` (sin análisis vigente → motivo; con análisis → vacío e
  `iniciar` pasa).
- **Frontend (unitarias)**: la tarjeta deriva botón y motivo de la respuesta; el formulario
  envía `silo_destino`.
- **E2E**: `evaporacion.spec.ts` reescrito sobre el puesto, de 5 pasos/3 pantallas a 4 pasos
  (abrir y preparar → Calidad analiza el origen, viendo antes «Iniciar» deshabilitado con su
  motivo → iniciar → registrar salida). La cadena `circuito → evaporacion → flujo-polvo` sigue
  4/4; se ajustan `flujo-precondensado-despacho` y `flujo-descremado` si usaban `/procesos` para
  la evaporación.
- **Accesibilidad**: el puesto entra a `e2e/rutas.ts`; sin reglas nuevas.

## 6. Riesgos

- Retirar la evaporación de `/produccion` y `/procesos` en el mismo cambio: antes de borrar se
  busca cada uso de `crear-guiada`, de la sección `proceso-condensacion` y de las rutas viejas;
  las redirecciones cubren enlaces guardados y avisos ya emitidos.

## 7. Fuera de alcance

Puestos de Secado, Mantequilla y Descremado; `/produccion` como panel de supervisor; `/procesos`
reducido a Trazabilidad; el orden del flujo servido por el backend. Cada uno con su diseño.
