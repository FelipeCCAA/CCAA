# Puesto de Mantequilla — plan de implementación

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Un solo puesto, `/produccion/mantequilla`, donde se prepara una corrida de mantequilla sobre una mantequera (que la toma), se inicia cuando el servidor lo permite, se cancela una preparación y se cierra con un balance que decide el servidor, en vez de una sección de `/procesos` con dos modales, un botón «Iniciar» que siempre se ofrece y dos implementaciones del balance.

**Architecture:** La mantequera pasa a ser un tipo de máquina (`Equipo.Tipo.MANTEQUERA`) con una migración de datos que reclasifica las candidatas y las saca de los formatos de envasado. El backend convierte `crear-guiada` en «Preparar»: valida la crema con las mismas funciones que el inicio (`motivos_crema_para_mantequilla`, `kg_crema_disponible`) y toma la mantequera (`borrador → preparacion`) en una transacción. `motivos_tipados_para_iniciar_mantequilla` pasa a ser la única implementación de las reglas de inicio; `iniciar_mantequilla` la usa y ya no prepara. El inicio genérico se cierra para Mantequilla, `preparar-continuacion` deja de crear ejecuciones de Mantequilla sin corrida, se agrega «Cancelar preparación» (corrida `anulada`, lote de salida anulado), el balance del cierre se vuelve una función pura (`balance_mantequilla`) que usan el modelo, el cierre y `revisar-cierre/`, y `mantequillas/puesto/` sirve el estado del puesto en lugar de `opciones-alta/`. El frontend agrega la página del puesto (tarjetas por mantequera que pintan lo que manda el servidor, formulario guiado «Preparar mantequilla» con código sugerido, cierre con el balance del servidor, corridas de hoy e historial con filtros de servidor) y retira la sección, los modales y `balance-mantequilla.ts`.

**Tech Stack:** Django 6 + DRF + PostgreSQL; React 19 + TypeScript + react-router (HashRouter); `node --test`; Playwright.

**Spec:** `docs/superpowers/specs/2026-10-08-puesto-mantequilla-design.md` (con los ajustes de la sección «Desviaciones» de este plan).

## Global Constraints

- Ruta del puesto: **`/produccion/mantequilla`**, bajo el módulo `produccion` (como Evaporación y Descremado). `/procesos?seccion=mantequilla` → `/produccion/mantequilla` (mismo bloque de redirecciones de `Procesos.tsx`). Menú, `rutaDeEtapa("mantequilla")` y `RUTAS_POR_ETAPA["mantequilla"]` apuntan al puesto. La crema llega preelegida con `?crema=<lote_id>`.
- Endpoints (prefijo `/api/procesos/mantequillas/`): `GET puesto/`; `POST crear-guiada/` (prepara; mismo cuerpo de hoy); `POST {id}/iniciar/` (**400** con el primer motivo, como hoy); `POST {id}/cancelar-preparacion/` `{"motivo"}`; `POST {id}/revisar-cierre/` (no escribe); `POST {id}/cerrar/`; `GET ?q=&estado=&desde=&hasta=&page=`. `POST mantequillas/` → 405 (ya lo es). `GET opciones-alta/` **se elimina** (404).
- Estados por mantequera: `"disponible" | "preparada" | "en_curso"`. Ejecución de Mantequilla en `preparacion` → `preparada`; `ejecucion`, `pausada` o `bloqueada` → `en_curso`; sin ejecución en `ESTADOS_QUE_OCUPAN_EQUIPO` → `disponible`. `cerrada`/`cancelada` (`ESTADOS_EJECUCION_TERMINALES`) y `pendiente_control` no ocupan; la última se informa en `en_calidad`.
- Claves JSON del puesto: `mantequeras[].{equipo_id, codigo, nombre, tipo, estado, corrida, motivos_para_tomar, motivos_para_iniciar, resolver_en, avisos, en_calidad}`; `corrida.{id, estado, ejecucion_id, ejecucion_codigo, ejecucion_estado, orden_codigo, producto, lote_mantequilla, lote_crema, kg_crema, lote_suero, iniciada_en}`; `en_calidad.{id, ejecucion_codigo, lote_mantequilla}`; `ordenes[].{id, codigo, producto}`; `cremas[].{id, codigo, producto, disponible_kg, tk}`; `cremas_pendientes_calidad[].{id, codigo, producto, estado_calidad, etapa_origen}`; `sueros[].{id, codigo, producto}`; `corridas_de_hoy[].{id, ejecucion_codigo, equipo, lote_mantequilla, lote_crema, estado, estado_etiqueta, estado_ejecucion, situacion, situacion_etiqueta}`; `estados[].{valor, etiqueta}`. Decimales como **texto**.
- `motivos_tipados_para_iniciar_mantequilla(corrida, *, ejecucion=None)` es **la única implementación** de las reglas de inicio: `iniciar_mantequilla` la usa (vía `motivos_para_iniciar_mantequilla`) y `mantequillas/puesto/` la sirve. `resolver_en`: `RESOLVER_CIP = "/calidad/inocuidad"`, `RESOLVER_CALIDAD = "/calidad"`, `RESOLVER_SILOS = "/silos"`, `RESOLVER_PLANIFICACION = "/planificacion"` (nuevo) o `None`.
- `kg_crema_disponible(lote, *, excluir_corrida_id=None)` es la única cuenta del disponible de una crema: la usan `cremas`, «Preparar» y el inicio.
- `balance_mantequilla(*, kg_crema, kg_mantequilla, kg_suero=0, kg_merma=0, kg_reproceso=0)` (`procesos/dominio.py`) es la única regla del balance: la usan `CorridaMantequilla.clean()`, `cerrar_mantequilla` (antes de escribir) y `revisar-cierre/`. `TOLERANCIA_BALANCE_MANTEQUILLA_KG = Decimal("0")`. El cliente no calcula.
- Mensajes exactos: inicio genérico rechazado «Las corridas de mantequilla se inician desde el puesto de Mantequilla.»; `preparar-continuacion` con la etapa Mantequilla «La mantequilla se prepara en el puesto de Mantequilla.»; balance «El cierre debe clasificar el 100% de la crema: {X} kg faltan por clasificar.» / «… exceden la entrada.»; sin mantequilla «Indica la mantequilla producida.»; suero sin lote «Esta corrida no tiene un lote de suero asociado: registra 0 kg.».
- Situaciones (`SITUACIONES_MANTEQUILLA`, gana la primera): `preparada` (borrador + `preparacion`), `en_curso` «En la mantequera» (`en_proceso`), `esperando_calidad` (`pendiente_calidad`), `terminada` (`cerrada`), `anulada`, `borrador` (heredadas y huérfanos).
- Preparar, iniciar, cancelar, revisar el cierre y cerrar exigen la etapa Mantequilla (`puede_operar_tipo(usuario, EtapaProceso.Tipo.MANTEQUILLA)`: área Condensación o administración) en todos los caminos; Calidad lee el puesto.
- La tarjeta **pinta lo que manda el servidor**; una acción por estado: «Preparar mantequilla», «Iniciar mantequilla», «Registrar balance y cerrar»; «Cancelar preparación» en segundo plano. Línea informativa «{lote} de {EJ-MANT-…} esperando Calidad». Confirmaciones con `ConfirmarAccion`: «Preparar mantequilla», «Cerrar y enviar a Calidad», «Cancelar preparación».
- Etiqueta de la acción de salidas intermedias: código `iniciar_mantequilla` (sin cambio), texto **«Preparar en Mantequilla»**; enlaza a `/produccion/mantequilla?crema=<lote_id>`.
- Trampa de `CLAUDE.md`: dentro de `transaction.atomic()` un `return Response(...)` **confirma**; solo una excepción revierte. Los servicios lanzan `ValidationError`; las vistas responden **fuera** de la transacción.
- Trampa de `CLAUDE.md`: las migraciones siembran equipos (entre ellos `linea_mantequilla`) también en la base de pruebas, y `filtrar_por_scope` ya no aísla por empresa: las pruebas del puesto filtran por **sus** ids, nunca comparan listas completas.
- Trampa de `CLAUDE.md`: el runner migra solo la base de pruebas. **Después de cada `makemigrations` correr `migrate`** contra la base de desarrollo, o el navegador revienta con un `IntegrityError` mientras la suite sigue verde.
- Toda cantidad en pantalla pasa por `cantidad(valor, unidad)`; toda operación irreversible por `ConfirmarAccion`.
- Español en código, comentarios, mensajes y UI. Django 6: `save()` solo por nombre. Archivos en LF.
- Pruebas backend: `cd backend && DJANGO_ENV=test ./.venv/Scripts/python.exe manage.py test <etiquetas> --noinput`, **en serie, nunca `--parallel`**. Frontend (en `frontend/`): `npx tsc -b --pretty false`, `npx eslint .`, `npm test`.
- No reescribir archivos con acentos con PowerShell `Get-Content | Set-Content` (usar Edit). Commits en español, convencionales, sin líneas de atribución, agregando archivos **por nombre**; nunca `frontend/e2e/.auth/estado.json`.

## Desviaciones: lo que el código dice distinto de la spec

1. **`useDatosSeccion` no existe.** La spec §4.5 lo nombra; el hook es `useCarga` (`frontend/src/components/seccion/utilidades.ts:66`), cuyo `recargar` ya llama a `invalidarCacheLecturas` (`:101`). El puesto usa `useCarga`, como Descremado.
2. **La reversa de la migración de datos no puede «anotar».** `Equipo` no tiene una columna donde dejar qué se reclasificó (spec §3.6). La reversa devuelve a `linea` **toda** `mantequera`: antes de `maestros.0039` el tipo no existía, así que toda mantequera viene de este paso o se creó después, y `linea` es el tipo que la etapa Mantequilla aceptaba (una candidata que era `otro` vuelve como `linea`, que la regla vieja `{LINEA, OTRO}` también aceptaba). Los formatos de envasado **no** se restauran: volver a autorizar una máquina es una decisión, no un deshacer.
3. **Esquema y datos en migraciones separadas**: `maestros.0039_equipo_tipo_mantequera` (choices) y `maestros.0040_reclasificar_mantequeras` (datos, depende de `procesos.0023_evento_operacion_id` para leer ejecuciones y corridas), como `0022`/`0023` de mandantes. `procesos.0024_corrida_mantequilla_anulada` agrega `anulada` y `motivo_anulacion`. Solo se reclasifican candidatas de tipo `linea` u `otro` (las que la regla vieja aceptaba): una envasadora usada por error en una corrida no se toca.
4. **«Otra etapa la usó» se mide con `EjecucionProceso`, no con `RegistroEnvase`.** Envasar no crea ejecuciones (`produccion/servicios.py` solo crea `EJ-PROD-…` al abrir desde un vale), y la spec §3.6 dice que los envases históricos conservan su clave foránea sin revalidarse. La `linea_mantequilla` de la base de desarrollo, donde el E2E envasó, se reclasifica igual y sale de los formatos.
5. **«Preparar» no validaba el suero** (la spec §3.2 dice «como hoy»: hoy solo se carga con `select_for_update`). Se agrega `sueros_libres(consulta)`, una regla para la lista `sueros`, «Preparar» y `preparar_circuito_mantequilla` (que filtraba `corridas_como_suero_mantequilla__isnull=True` y retenía el suero de una corrida anulada).
6. **Los textos de `errores` y de `clean()` se unifican.** `clean()` decía «Identifica el lote del suero generado.» bajo la clave `lote_suero`; la spec §3.5 pide en `errores["kg_suero"]` «Esta corrida no tiene un lote de suero asociado: registra 0 kg.» «con el mismo texto». Se toma el de la spec como constante (`MENSAJE_SUERO_SIN_LOTE`) y una función pura, `errores_cierre_mantequilla`, que usan `clean()`, `cerrar_mantequilla` (antes de escribir) y `revisar-cierre/`. Nadie lee la clave `lote_suero` de ese error (búsqueda en `backend/` y `frontend/`).
7. **`cerrar/` que no cuadra ya no dejaba el lote de reproceso**: `clean()` lanzaba dentro de la transacción y la revertía. La prueba «400 sin lote de reproceso» es de caracterización; el cambio real es que el balance se evalúa **antes** de escribir, con la misma función que `revisar-cierre/`.
8. **Cancelar una corrida en curso desde la bandeja también anula el lote de salida.** La spec §3.4 lista «corrida `anulada`» y «el lote de salida se anula» sin separar los casos; un lote `en_proceso` sin kilos sobre una ejecución cancelada no lo cierra nadie. El motivo del lote dice «Preparación de Mantequilla cancelada: …» si la corrida estaba en `borrador` y «Corrida de Mantequilla cancelada: …» si estaba en proceso.
9. **`preparada` exige la ejecución en `preparacion`** (tabla de la spec §3.8), a diferencia de `SITUACIONES_DESCREMACION`, que también llama «Preparada» a una ejecución en `borrador`. Las corridas heredadas `borrador`/`borrador` son «Borrador».
10. **Generalización de situaciones**: `dominio.situacion_de(tabla, estado, estado_ejecucion)`, `servicios.condicion_situacion(tabla, situacion)` y `servicios.catalogo_situaciones(tabla)`. `situacion_descremacion` se conserva como envoltorio (la importa `tests_puesto_descremado`); `condicion_situacion_descremacion` y `catalogo_situaciones_descremacion` se eliminan y sus dos usos pasan a la función general.
11. **«En curso manda sobre preparada» no es alcanzable**: la base impide dos ocupaciones del mismo equipo (`procesos.0015`). El código conserva la regla (espejo de Descremado) y la prueba cubre `ejecucion`/`pausada`/`bloqueada` → `en_curso`.
12. **`opciones-alta/`, `RUTAS_POR_ETAPA["mantequilla"]` y la etiqueta «Preparar en Mantequilla» cambian en la Task 7**, junto con el retiro del modal que lee `opciones-alta/` y el enlace del frontend: hacerlo antes rompería `/procesos` o mandaría la bandeja a una ruta inexistente entre commits. Las pruebas `test_opciones_alta_*` y `test_una_preparacion_cancelada_no_resta_la_crema_ofrecida` de `tests_mantequilla.py` se eliminan en la Task 3 (la fixture pasa a liberar la crema) y sus casos se reescriben contra `puesto/` en la Task 5.
13. **La fixture de `tests_mantequilla.py` nace preparada y con la crema liberada.** Hoy crea la ejecución en `borrador` y la crema sin `LiberacionProceso`; con el inicio nuevo (exige `preparacion` y liberación para toda crema, spec §8.5 y §8.7) ninguna prueba iniciaría. `test_alta_guiada_crea_lote_ejecucion_y_corrida_atomicos` usa otra mantequera: la de la fixture queda tomada.
14. **`preparar_circuito_mantequilla` no crea formatos.** Autoriza la envasadora en los `FormatoEnvasado` activos de cada mantequilla en caja de 20 kg y, si un producto no tiene ninguno, lo **avisa** en la salida (configuración de planta, no sembrado de la prueba). La envasadora nace sin `consume_materiales`: la mantequera lo conserva y marcar las dos haría que el MRP pidiera los envases dos veces.
15. **`corridaCancelable` se reexporta** de `puesto-descremado.ts` (misma regla: corrida `borrador` con la ejecución en `borrador` o `preparacion`) en vez de copiarse; `moduloDeResolver` gana `"/planificacion" → "planificacion"`.
16. **`estadoDelBalance(revision, pendiente, error = false)`**: el tercer parámetro distingue una revisión fallida de una en camino. «Excedido» o «incompleto» se lee del signo de `diferencia_kg` que manda el servidor; no hay aritmética en el cliente.
17. **`CancelarPreparacion` tenía el texto de Descremado fijo.** Al moverlo a `components/operacion/` recibe `advertencia` como prop; Descremado pasa el suyo.
18. **Destinos de los motivos que la spec no tipifica**: densidad inválida del análisis de la crema → `RESOLVER_CALIDAD`; saldo del TK, kg disponibles y lote de crema anulado → `None` (no hay pantalla que los arregle).
19. **Funciones extraídas** para que inicio y puesto lean lo mismo: `fuente_tk_de_crema(lote)` (la salida en TK de la que sale la crema; el puesto la usa para `cremas[].tk`) y `litros_de_crema(kg, densidad)`.
20. **E2E**: la crema se elige entre las que sirve `mantequillas/puesto/` con al menos 60 kg (o `E2E_LOTE_CREMA`), no el `INT-DES-2-CR` fijo de hoy; la entrada es Salidas intermedias de `/produccion` («Consultar disponibles»).
21. **`motivo_anulacion` es `CharField(max_length=250)`** (spec §3.6), no `TextField` como en `CorridaDescremacion`: el motivo se recorta a 250 caracteres al anular.

## Usos a migrar

Búsqueda del 2026-10-08 (`grep` sobre `backend/`, `frontend/src`, `frontend/tests`, `frontend/e2e`).

| Uso | Dónde | Tarea |
|---|---|---|
| `Equipo.Tipo` sin mantequera | `backend/maestros/models.py:365-372`; siembras `backend/maestros/migrations/0010_sembrar_equipos.py:21`, `0031_sembrar_siglas.py:20`, `0025_sembrar_consume_materiales.py:26` (no se editan: reclasifica `0040`) | 1 |
| Listas literales `{LINEA, OTRO}` de la etapa Mantequilla | `backend/procesos/servicios.py:662` (`tipos_equipo_para_etapa`), `:977` (`crear_mantequilla_guiada`); `backend/procesos/views.py:675` (`opciones_alta`) | 1 |
| Máquina de mantequilla buscada como línea | `backend/produccion/management/commands/preparar_circuito_mantequilla.py:64-69` (+ vista previa y OP, `:73-76`, `:144-145`) | 1 |
| Suero libre que retiene anuladas | `preparar_circuito_mantequilla.py:169-174`; `backend/procesos/views.py:665-673` (`opciones_alta`) | 3, 7 |
| Pruebas que crean la máquina como línea | `backend/procesos/tests_mantequilla.py:53-56`; `backend/procesos/tests.py:203` | 1 |
| `CorridaMantequilla` (estados, `clean()` con su aritmética) | `backend/procesos/models.py:552-660` | 1, 2 |
| `CierreMantequillaSerializer.validate` (texto del reproceso) | `backend/procesos/serializers.py:279-306` | 2 |
| `cerrar_mantequilla` (balance tras crear el reproceso) | `backend/procesos/servicios.py:2931-3080` | 2 |
| `crear_mantequilla_guiada` (no toma la máquina, no valida CIP ni liberación) | `backend/procesos/servicios.py:955-1015`; vista `backend/procesos/views.py:737-769` (sin cambio de contrato) | 3 |
| `preparar_continuacion` con la etapa Mantequilla | `backend/procesos/servicios.py:1019` | 3 |
| `iniciar_mantequilla` (pasa `borrador → preparacion → ejecucion`; reglas en línea) | `backend/procesos/servicios.py:2838-2928`; `tests_mantequilla.py:95,123,137,165,188,246,290,423` (inician la fixture `borrador`) | 3 |
| Fixture `borrador` con crema sin liberar; `test_alta_guiada_…` | `tests_mantequilla.py:63-92`, `:307-320` | 3 |
| Pruebas de `opciones-alta/` | `tests_mantequilla.py:322-404` (tres `test_opciones_alta_*`), `:428-450` (`…no_resta_la_crema_ofrecida`) | 3 (se eliminan), 5 (reescritas contra `puesto/`) |
| `MENSAJES_INICIO_EN_PUESTO` sin Mantequilla | `backend/procesos/servicios.py:103-106`; `inicio_reservado_al_puesto` (`:3352`) | 4 |
| `bloquear_para_cancelar` y gancho de cancelación | `backend/procesos/servicios.py:1143-1166`, `:1258-1263` | 4 |
| `condicion_situacion_descremacion` / `catalogo_situaciones_descremacion` | `backend/procesos/servicios.py:2365-2395`, `:2613`; `backend/procesos/views.py:58,341-342` | 5 |
| `situacion_descremacion` (se generaliza) | `backend/procesos/dominio.py:110-136`; `backend/procesos/serializers.py:234-236`; `backend/procesos/tests_puesto_descremado.py:15,970` (sin cambio: el envoltorio se conserva) | 5 |
| `CorridaMantequillaViewSet` sin filtros ni puesto; `CorridaMantequillaSerializer` sin situación | `backend/procesos/views.py:598-792`; `backend/procesos/serializers.py:308-340` | 2, 4, 5 |
| `opciones-alta/` de Mantequilla | `backend/procesos/views.py:625-735`; `frontend/src/services/procesos.service.ts:345-357,623-626`; `frontend/src/pages/Procesos/NuevaMantequilla.tsx` | 7 |
| Etiqueta «Iniciar Mantequilla» | `backend/procesos/views.py:1526`; `frontend/e2e/flujo-descremado.spec.ts:258,306,345` | 7, 8 |
| `RUTAS_POR_ETAPA["mantequilla"]` / `rutaDeEtapa` | `backend/procesos/dominio.py:101`; `backend/procesos/tests_destinos.py:26`; `frontend/src/services/planta-ahora.ts:11`; `frontend/tests/planta-ahora.test.ts:26` | 7 |
| `PUESTOS_QUE_INICIAN` sin Mantequilla | `frontend/src/services/planta-ahora.ts:26-29`; `frontend/tests/planta-ahora.test.ts:31-37` | 6 |
| `moduloDeResolver` sin `/planificacion` | `frontend/src/services/puesto-secado.ts:81-90`; `frontend/tests/puesto-secado.test.ts` | 6 |
| Tipo `CorridaMantequilla` del frontend; servicios viejos | `frontend/src/services/procesos.service.ts:149-170` (gana `ejecucion_estado`, `situacion`, `situacion_etiqueta`, `motivo_anulacion`), `:587-633` (`obtenerMantequillas`, `iniciarMantequilla`, `cerrarMantequilla`, `obtenerOpcionesAltaMantequilla`, `crearMantequillaGuiada` → `mantequilla.service.ts`) | 6, 7 |
| Balance en el cliente | `frontend/src/services/balance-mantequilla.ts`; `frontend/tests/balance-mantequilla.test.ts`; `frontend/src/pages/Procesos/CierreMantequilla.tsx:4,21-27` | 7 |
| Sección y modales de `/procesos` | `frontend/src/pages/Procesos/Procesos.tsx:8,12,14,26-30,82-103,113-119,151-152,162-166`; `NuevaMantequilla.tsx`, `CierreMantequilla.tsx` (se eliminan) | 7 |
| Enlaces a `/procesos?seccion=mantequilla` | `frontend/src/pages/Leche/Silos.tsx:336-337`; `frontend/src/pages/Produccion/SalidasIntermedias.tsx:227-233`; `frontend/src/pages/Produccion/Produccion.tsx:271`; `frontend/src/services/navegacion-operacional.ts:59,155`; `frontend/tests/navegacion-operacional.test.ts:113-131` | 7 |
| `CancelarPreparacion` con el texto de Descremado | `frontend/src/pages/Descremado/CancelarPreparacion.tsx` (se mueve a `frontend/src/components/operacion/`); `frontend/src/pages/Descremado/PuestoDescremado.tsx:17,236-242` | 7 |
| Rutas | `frontend/src/app/routes.tsx:75-76,219-222` | 7 |
| E2E de Mantequilla y auditoría | `frontend/e2e/flujo-mantequilla.spec.ts` (alta en `/procesos`, «Línea de mantequilla» como envasadora, `:30,112`); `frontend/e2e/rutas.ts:59-61`; `frontend/e2e/README.md` (sin sección de Mantequilla) | 8 |
| **Sin uso y sin cambio** | `calidad/views.py:846-884` (cierra la corrida al decidir, filtra `PENDIENTE_CALIDAD`); `procesos/permisos.py` (ya resuelve el tipo de `CorridaMantequilla`); `usuarios/management/commands/reset_datos_operacionales.py:51`; `sembrar_flujo_demo` (no prepara mantequilla); `procesos/tests_permisos_operacionales.py:352` (405 ya vigente); `produccion/tests_envase.py:243` (ejecución sin corrida en `pendiente_control`, no pasa por el puesto); `produccion/tests_cancelar_evaporacion.py:299-303` y `produccion/tests_lote_en_torre.py:124-133` (recorren `Equipo.Tipo.values`: `abre_desde_vale("mantequera")` es falso y el conjunto esperado no cambia); `frontend/src/pages/Maestros/FormularioFormatoEnvasado.tsx` (ya filtra envasadora/línea); `frontend/src/services/equipos-apertura.ts` (la mantequera no abre desde un vale) | — |

## Mapa de archivos

| Archivo | Cambio | Tarea |
|---|---|---|
| `backend/maestros/models.py` | `Equipo.Tipo.MANTEQUERA` | 1 |
| `backend/maestros/migrations/0039_equipo_tipo_mantequera.py`, `0040_reclasificar_mantequeras.py` | nuevas | 1 |
| `backend/maestros/tests_mantequeras.py` | nuevo: migración y tipo | 1 |
| `backend/procesos/models.py` | `CorridaMantequilla.Estado.ANULADA`, `motivo_anulacion` (1); `clean()` con `balance_mantequilla` y `errores_cierre_mantequilla` (2) | 1, 2 |
| `backend/procesos/migrations/0024_corrida_mantequilla_anulada.py` | nueva | 1 |
| `backend/produccion/management/commands/preparar_circuito_mantequilla.py` | mantequera, envasadora autorizada (1); `sueros_libres` (3) | 1, 3 |
| `backend/produccion/tests_preparar_mantequilla.py` | nuevo | 1 |
| `backend/procesos/dominio.py` | balance y errores del cierre (2); situaciones generalizadas (5); `RUTAS_POR_ETAPA` (7) | 2, 5, 7 |
| `backend/procesos/servicios.py` | `tipos_equipo_para_etapa` y literal (1); `revisar_cierre_mantequilla`, `cerrar_mantequilla` (2); `RESOLVER_PLANIFICACION`, `MENSAJE_MANTEQUILLA_EN_PUESTO`, `filtro_crema_liberada`, `sueros_libres`, `kg_crema_disponible`, `motivos_crema_para_mantequilla`, `fuente_tk_de_crema`, `litros_de_crema`, `crear_mantequilla_guiada`, `preparar_continuacion`, `motivos_tipados_para_iniciar_mantequilla`, `motivos_para_iniciar_mantequilla`, `iniciar_mantequilla` (3); `MENSAJES_INICIO_EN_PUESTO`, `bloquear_para_cancelar`, gancho de `transicionar_ejecucion`, `_deshacer_preparacion_mantequilla`, `cancelar_preparacion_mantequilla` (4); `condicion_situacion`, `catalogo_situaciones`, `estado_puesto_mantequilla` (5) | 1-5 |
| `backend/procesos/serializers.py` | `CierreMantequillaSerializer`, `RevisarCierreMantequillaSerializer` (2); `CorridaMantequillaSerializer` (5) | 2, 5 |
| `backend/procesos/views.py` | literal de `opciones_alta` (1); `revisar_cierre` (2); `cancelar_preparacion` (4); mixins, filtros, `puesto`, `condicion_situacion` (5); `opciones_alta` eliminada y etiqueta (7) | 1, 2, 4, 5, 7 |
| `backend/procesos/tests_mantequilla.py` | equipo (1); dominio y revisión del balance (2); fixture preparada y liberada (3) | 1, 2, 3 |
| `backend/procesos/tests_puesto_mantequilla.py` | nuevo | 3, 4, 5, 7 |
| `backend/procesos/tests.py`, `tests_destinos.py` | tipo de máquina (1); ruta (7) | 1, 7 |
| `frontend/src/services/mantequilla.service.ts`, `puesto-mantequilla.ts`, `permisos-mantequilla.ts` + `frontend/tests/puesto-mantequilla.test.ts`, `permisos-mantequilla.test.ts` | nuevos | 6 |
| `frontend/src/services/puesto-secado.ts`, `planta-ahora.ts`, `procesos.service.ts` + `frontend/tests/puesto-secado.test.ts`, `planta-ahora.test.ts` | `/planificacion`, `PUESTOS_QUE_INICIAN`, tipo de la corrida | 6 |
| `frontend/src/components/operacion/CancelarPreparacion.tsx` | movido desde `pages/Descremado/`, con `advertencia` | 7 |
| `frontend/src/pages/Mantequilla/PuestoMantequilla.tsx`, `TarjetaMantequera.tsx`, `PrepararMantequilla.tsx`, `CierreMantequilla.tsx` | nuevos | 7 |
| `frontend/src/pages/Procesos/NuevaMantequilla.tsx`, `CierreMantequilla.tsx`, `frontend/src/services/balance-mantequilla.ts`, `frontend/tests/balance-mantequilla.test.ts` | eliminar | 7 |
| `frontend/src/pages/Procesos/Procesos.tsx`, `frontend/src/pages/Descremado/PuestoDescremado.tsx`, `frontend/src/pages/Produccion/Produccion.tsx`, `SalidasIntermedias.tsx`, `frontend/src/pages/Leche/Silos.tsx`, `frontend/src/app/routes.tsx`, `frontend/src/services/navegacion-operacional.ts`, `planta-ahora.ts`, `procesos.service.ts` + `frontend/tests/navegacion-operacional.test.ts`, `planta-ahora.test.ts` | retiro, rutas, menú | 7 |
| `CLAUDE.md` | decisión nueva y equipo | 7 |
| `frontend/e2e/flujo-mantequilla.spec.ts`, `flujo-descremado.spec.ts`, `rutas.ts`, `README.md` | E2E | 8 |

---

### Task 1: La mantequera es un tipo de máquina (migraciones de esquema y de datos)

**Files:**
- Modify: `backend/maestros/models.py` (`Equipo.Tipo`, ~365)
- Create: `backend/maestros/migrations/0039_equipo_tipo_mantequera.py` (generada), `backend/maestros/migrations/0040_reclasificar_mantequeras.py` (a mano)
- Modify: `backend/procesos/models.py` (`CorridaMantequilla.Estado`, `motivo_anulacion`, ~552)
- Create: `backend/procesos/migrations/0024_corrida_mantequilla_anulada.py` (generada)
- Modify: `backend/procesos/servicios.py` (`tipos_equipo_para_etapa` ~662; literal de `crear_mantequilla_guiada` ~977)
- Modify: `backend/procesos/views.py` (literal de `CorridaMantequillaViewSet.opciones_alta`, ~675)
- Modify: `backend/produccion/management/commands/preparar_circuito_mantequilla.py`
- Create: `backend/maestros/tests_mantequeras.py`, `backend/produccion/tests_preparar_mantequilla.py`
- Modify: `backend/procesos/tests_mantequilla.py` (~53-56), `backend/procesos/tests.py` (~203)

**Interfaces:**
- Produces: `Equipo.Tipo.MANTEQUERA = "mantequera"` («Mantequera»), servido solo por `/api/maestros/catalogos/` (`equipo_tipo`); `tipos_equipo_para_etapa(EtapaProceso.Tipo.MANTEQUILLA) == {Equipo.Tipo.MANTEQUERA}`.
- Produces: `CorridaMantequilla.Estado.ANULADA = "anulada"` («Anulada»); `CorridaMantequilla.motivo_anulacion = CharField(max_length=250, blank=True)`.
- Produces (`maestros/migrations/0040_reclasificar_mantequeras.py`): `reclasificar(apps, schema_editor)` y `restaurar(apps, schema_editor)`; `CODIGO_SEMBRADO = "linea_mantequilla"`, `TIPOS_ANTERIORES = ("linea", "otro")`.
- Produces (comando): `preparar_circuito_mantequilla --aplicar` busca la máquina por `tipo=MANTEQUERA` y asegura `envasadora_mantequilla` («Envasadora de mantequilla», `envasadora`) autorizada en los `FormatoEnvasado` activos de cada mantequilla en caja de 20 kg; `CODIGO_ENVASADORA = "envasadora_mantequilla"`.

- [ ] **Step 1: Pruebas de la migración y del tipo que fallan** — crea `backend/maestros/tests_mantequeras.py`:

```python
import importlib
import io
from contextlib import redirect_stdout
from datetime import date
from decimal import Decimal

from django.apps import apps
from django.test import TestCase

from procesos.models import CorridaMantequilla, EjecucionProceso, EtapaProceso, Proceso
from procesos.servicios import tipos_equipo_para_etapa
from produccion.models import Lote, OrdenProduccion
from produccion.servicios import abre_desde_vale
from usuarios.models import Empresa, Sucursal

from .models import Equipo, FormatoEnvasado, Mandante, Producto

# El nombre del módulo empieza con un dígito: solo se importa así.
reclasificacion = importlib.import_module("maestros.migrations.0040_reclasificar_mantequeras")


class ReclasificarMantequerasTests(TestCase):
    """
    `0040` ya corrió al construir la base de pruebas. Aquí se vuelve a llamar
    con el registro de modelos vivo sobre equipos propios, para fijar qué
    reclasifica, qué deja como está, qué anuncia y qué deshace.
    """

    def setUp(self):
        self.empresa = Empresa.objects.create(rut="MTQ-1", nombre="Empresa mantequeras")
        self.planta = Sucursal.objects.create(
            empresa=self.empresa, codigo="MTQ", nombre="Planta mantequeras"
        )
        mandante = Mandante.objects.create(
            empresa=self.empresa, nombre="Mandante mantequeras", codigo_cliente="mtq"
        )
        self.crema = Producto.objects.create(
            mandante=mandante, nombre="Crema MTQ", familia=Producto.Familia.CREMA
        )
        self.mantequilla = Producto.objects.create(
            mandante=mandante, nombre="Mantequilla MTQ",
            categoria=Producto.Categoria.MANTEQUILLA, naturaleza=Producto.Naturaleza.TERMINADO,
        )
        proceso = Proceso.objects.create(codigo="mtq", nombre="Mantequilla MTQ")
        self.etapa_mantequilla = EtapaProceso.objects.create(
            proceso=proceso, codigo="mtq-batir", nombre="Batido",
            tipo=EtapaProceso.Tipo.MANTEQUILLA, orden=1,
        )
        self.etapa_envasado = EtapaProceso.objects.create(
            proceso=proceso, codigo="mtq-envasar", nombre="Envasado",
            tipo=EtapaProceso.Tipo.ENVASADO, orden=2,
        )
        self.orden = OrdenProduccion.objects.create(
            sucursal=self.planta, codigo="OP-MTQ", producto=self.mantequilla,
            cantidad_planificada=100, unidad="kg",
        )

    def equipo(self, codigo, tipo=Equipo.Tipo.LINEA):
        return Equipo.objects.create(sucursal=self.planta, codigo=codigo, nombre=codigo, tipo=tipo)

    def corrida_en(self, equipo, sufijo):
        """Una corrida de mantequilla que usó `equipo`: lo vuelve candidato."""
        ejecucion = EjecucionProceso.objects.create(
            codigo=f"EJ-MTQ-{sufijo}", etapa=self.etapa_mantequilla,
            sucursal=self.planta, equipo=equipo,
        )
        crema = Lote.objects.create(
            sucursal=self.planta, codigo_lote=f"CR-MTQ-{sufijo}", producto=self.crema,
            fecha=date(2026, 10, 1), estado=Lote.Estado.PRODUCIDO, kg_producidos=Decimal("100"),
        )
        salida = Lote.objects.create(
            sucursal=self.planta, codigo_lote=f"MTQ-{sufijo}", producto=self.mantequilla,
            fecha=date(2026, 10, 1),
        )
        return CorridaMantequilla.objects.create(
            ejecucion=ejecucion, orden=self.orden, lote_crema=crema,
            lote_mantequilla=salida, kg_crema=Decimal("50"),
        )

    def formato_con(self, *equipos, codigo="caja-mtq"):
        formato = FormatoEnvasado.objects.create(
            producto=self.mantequilla, codigo=codigo, nombre=f"Caja {codigo}",
            kg_neto=Decimal("20"), unidades_maximas_pallet=25,
        )
        formato.equipos.add(*equipos)
        return formato

    def reclasificar(self):
        salida = io.StringIO()
        with redirect_stdout(salida):
            reclasificacion.reclasificar(apps, None)
        return salida.getvalue()

    def tipo(self, equipo):
        return Equipo.objects.values_list("tipo", flat=True).get(pk=equipo.pk)

    def test_la_linea_sembrada_es_mantequera_y_conserva_sigla_y_mrp(self):
        # Lo dejó así `0040` al construir la base: la siembra de `0010` no
        # tiene ejecuciones de otra etapa.
        sembradas = Equipo.objects.filter(codigo=reclasificacion.CODIGO_SEMBRADO)
        self.assertTrue(sembradas.exists())
        for equipo in sembradas:
            self.assertEqual(equipo.tipo, Equipo.Tipo.MANTEQUERA)
            self.assertEqual(equipo.sigla, "LM")
            self.assertTrue(equipo.consume_materiales)

    def test_una_linea_usada_solo_por_mantequilla_pasa_a_mantequera_y_sale_de_los_formatos(self):
        linea = self.equipo("mtq-solo")
        envasadora = self.equipo("mtq-envasadora", Equipo.Tipo.ENVASADORA)
        self.corrida_en(linea, "1")
        formato = self.formato_con(linea, envasadora)

        self.reclasificar()

        self.assertEqual(self.tipo(linea), Equipo.Tipo.MANTEQUERA)
        self.assertEqual(list(formato.equipos.values_list("pk", flat=True)), [envasadora.pk])

    def test_una_linea_que_tambien_hizo_otra_etapa_queda_como_esta_y_se_nombra(self):
        linea = self.equipo("mtq-mixta")
        self.corrida_en(linea, "2")
        EjecucionProceso.objects.create(
            codigo="EJ-MTQ-ENV", etapa=self.etapa_envasado, sucursal=self.planta, equipo=linea,
        )
        formato = self.formato_con(linea)

        salida = self.reclasificar()

        self.assertEqual(self.tipo(linea), Equipo.Tipo.LINEA)
        self.assertIn(linea.pk, formato.equipos.values_list("pk", flat=True))
        self.assertIn("mtq-mixta", salida)

    def test_una_linea_ajena_a_la_mantequilla_no_cambia(self):
        linea = self.equipo("mtq-ajena")
        otro = self.equipo("mtq-otro", Equipo.Tipo.OTRO)

        self.reclasificar()

        self.assertEqual(self.tipo(linea), Equipo.Tipo.LINEA)
        self.assertEqual(self.tipo(otro), Equipo.Tipo.OTRO)

    def test_una_envasadora_usada_por_error_no_se_reclasifica(self):
        envasadora = self.equipo("mtq-env-error", Equipo.Tipo.ENVASADORA)
        self.corrida_en(envasadora, "3")

        self.reclasificar()

        self.assertEqual(self.tipo(envasadora), Equipo.Tipo.ENVASADORA)

    def test_un_formato_que_queda_sin_maquinas_se_anuncia(self):
        linea = self.equipo("mtq-unica")
        self.corrida_en(linea, "4")
        formato = self.formato_con(linea)

        salida = self.reclasificar()

        self.assertFalse(formato.equipos.exists())
        self.assertIn(f"«{formato.nombre}» quedó sin máquinas autorizadas", salida)

    def test_reclasificar_dos_veces_no_cambia_nada(self):
        linea = self.equipo("mtq-dos-veces")
        self.corrida_en(linea, "5")

        self.reclasificar()
        segunda = self.reclasificar()

        self.assertEqual(self.tipo(linea), Equipo.Tipo.MANTEQUERA)
        self.assertEqual(segunda, "")

    def test_deshacer_devuelve_las_mantequeras_a_linea(self):
        linea = self.equipo("mtq-deshacer")
        self.corrida_en(linea, "6")
        self.reclasificar()

        reclasificacion.restaurar(apps, None)

        self.assertEqual(self.tipo(linea), Equipo.Tipo.LINEA)
        self.assertFalse(Equipo.objects.filter(tipo=Equipo.Tipo.MANTEQUERA).exists())


class TipoMantequeraTests(TestCase):
    def test_la_etapa_mantequilla_acepta_solo_mantequeras(self):
        self.assertEqual(
            tipos_equipo_para_etapa(EtapaProceso.Tipo.MANTEQUILLA), {Equipo.Tipo.MANTEQUERA},
        )

    def test_el_envasado_no_acepta_una_mantequera(self):
        self.assertNotIn(Equipo.Tipo.MANTEQUERA, tipos_equipo_para_etapa(EtapaProceso.Tipo.ENVASADO))

    def test_una_mantequera_no_abre_lotes_desde_un_vale(self):
        # Cae en el valor por defecto de `tipo_etapa_de_apertura` (Secado), que
        # no abre desde un vale: correcto para una mantequera.
        self.assertFalse(abre_desde_vale(Equipo.Tipo.MANTEQUERA))
```

- [ ] **Step 2: Verificar que fallan**

Run: `cd backend && DJANGO_ENV=test ./.venv/Scripts/python.exe manage.py test maestros.tests_mantequeras --noinput`
Expected: ERROR `ModuleNotFoundError: No module named 'maestros.migrations.0040_reclasificar_mantequeras'`.

- [ ] **Step 3: El tipo** — en `backend/maestros/models.py`, `Equipo.Tipo` queda:

```python
    class Tipo(models.TextChoices):
        DESCREMADORA = "descremadora", "Descremadora"
        EVAPORADOR = "evaporador", "Evaporador"
        TORRE = "torre", "Torre de secado"
        # La máquina de batido de la crema. Tipo propio para que una línea de
        # envasado no aparezca como mantequera ni una mantequera como línea de
        # envasado (`maestros.0040`), por la misma razón que `e1`/`e2` dejaron
        # de ser «líneas».
        MANTEQUERA = "mantequera", "Mantequera"
        ENVASADORA = "envasadora", "Envasadora"
        LINEA = "linea", "Línea"
        CARGA = "carga", "Carga"
        OTRO = "otro", "Otro"
```

Run: `cd backend && ./.venv/Scripts/python.exe manage.py makemigrations maestros --name equipo_tipo_mantequera`
Expected: crea `maestros/migrations/0039_equipo_tipo_mantequera.py` con un solo `AlterField` de `equipo.tipo` (las `choices` con `("mantequera", "Mantequera")` entre `torre` y `envasadora`). Si aparece cualquier otra operación, detente y revisa: no es de esta tarea.

- [ ] **Step 4: La migración de datos** — `cd backend && ./.venv/Scripts/python.exe manage.py makemigrations maestros --empty --name reclasificar_mantequeras` y reemplaza el contenido de `maestros/migrations/0040_reclasificar_mantequeras.py` por:

```python
"""
La mantequera es un tipo de máquina (`Equipo.Tipo.MANTEQUERA`).

Hasta aquí la etapa Mantequilla aceptaba cualquier `linea` u `otro`: una línea
de envasado aparecía como mantequera y la mantequera como línea de envasado.
Se reclasifican las candidatas —la `linea_mantequilla` sembrada en `0010` (el
batido de la crema, `prototipo/PLANIFICADOR.md`) y los equipos que ya usó una
`CorridaMantequilla`— **solo si ninguna ejecución de otra etapa las usó**:
cambiarle el tipo a una máquina que también hizo otra cosa rompería esa otra
etapa. Esas se nombran en la salida y quedan como estaban. Las demás líneas y
«otro» no se tocan, y solo se reclasifican `linea` u `otro`: los tipos que la
regla vieja aceptaba.

Una mantequera reclasificada sale de `FormatoEnvasado.equipos`: el envasado
acepta solo envasadora o línea (`FormatoEnvasado`, `Envase.clean()`). Los
envases históricos conservan su clave foránea; nadie vuelve a validarlos. Si
un formato activo queda sin máquinas, la salida lo dice: hay que autorizar una
envasadora en Maestros antes de envasar ese producto.

`sigla`, `consume_materiales` y `consume_leche` no cambian: el código de lote y
el MRP siguen igual.

La reversa devuelve a `linea` toda mantequera: antes de `0039` el tipo no
existía, así que cada una viene de este paso o se creó después, y `linea` es
el tipo que la etapa aceptaba. Los formatos no se restauran: volver a
autorizar una máquina es una decisión, no un deshacer.
"""

import sys

from django.db import migrations, models

CODIGO_SEMBRADO = "linea_mantequilla"
TIPOS_ANTERIORES = ("linea", "otro")


def _decir(texto):
    sys.stdout.write(f"  {texto}\n")


def reclasificar(apps, schema_editor):
    Equipo = apps.get_model("maestros", "Equipo")
    FormatoEnvasado = apps.get_model("maestros", "FormatoEnvasado")
    EjecucionProceso = apps.get_model("procesos", "EjecucionProceso")
    CorridaMantequilla = apps.get_model("procesos", "CorridaMantequilla")

    candidatas = Equipo.objects.filter(tipo__in=TIPOS_ANTERIORES).filter(
        models.Q(codigo=CODIGO_SEMBRADO)
        | models.Q(pk__in=CorridaMantequilla.objects.values("ejecucion__equipo_id"))
    )
    con_otro_uso = set(
        EjecucionProceso.objects.filter(equipo_id__in=candidatas.values("pk"))
        .exclude(etapa__tipo="mantequilla")
        .values_list("equipo_id", flat=True)
    )
    for equipo in candidatas.filter(pk__in=con_otro_uso).order_by("codigo"):
        _decir(
            f"{equipo.codigo}: queda como «{equipo.tipo}» porque también la usó otra "
            "etapa; reclasifícala a mano en Maestros si es la mantequera."
        )

    ids = list(candidatas.exclude(pk__in=con_otro_uso).values_list("pk", flat=True))
    if not ids:
        return
    Equipo.objects.filter(pk__in=ids).update(tipo="mantequera")

    autorizaciones = FormatoEnvasado.equipos.through.objects.filter(equipo_id__in=ids)
    formatos = set(autorizaciones.values_list("formatoenvasado_id", flat=True))
    autorizaciones.delete()
    for formato in FormatoEnvasado.objects.filter(
        pk__in=formatos, activo=True, equipos__isnull=True,
    ).order_by("pk"):
        _decir(
            f"El formato «{formato.nombre}» quedó sin máquinas autorizadas: autoriza "
            "una envasadora en Maestros antes de envasar ese producto."
        )


def restaurar(apps, schema_editor):
    Equipo = apps.get_model("maestros", "Equipo")
    Equipo.objects.filter(tipo="mantequera").update(tipo="linea")


class Migration(migrations.Migration):
    dependencies = [
        ("maestros", "0039_equipo_tipo_mantequera"),
        ("procesos", "0023_evento_operacion_id"),
    ]

    operations = [
        migrations.RunPython(reclasificar, restaurar),
    ]
```

- [ ] **Step 5: La corrida se puede anular** — en `backend/procesos/models.py`, `CorridaMantequilla`:

```python
    class Estado(models.TextChoices):
        BORRADOR = "borrador", "Borrador"
        EN_PROCESO = "en_proceso", "En proceso"
        PENDIENTE_CALIDAD = "pendiente_calidad", "Pendiente de Calidad"
        CERRADA = "cerrada", "Cerrada"
        # Una preparación cancelada (o una corrida cuya ejecución se canceló):
        # queda como rastro en vez de borrarse, como en Descremado.
        ANULADA = "anulada", "Anulada"
```

y, debajo de `finalizada_en`:

```python
    motivo_anulacion = models.CharField(max_length=250, blank=True)
```

Run: `cd backend && ./.venv/Scripts/python.exe manage.py makemigrations procesos --name corrida_mantequilla_anulada`
Expected: crea `procesos/migrations/0024_corrida_mantequilla_anulada.py` con `AddField motivo_anulacion` y `AlterField estado`.

- [ ] **Step 6: Aplicar las migraciones (trampa de `CLAUDE.md`)**

Run: `cd backend && ./.venv/Scripts/python.exe manage.py makemigrations --check --dry-run`
Expected: `No changes detected`.

Run: `cd backend && ./.venv/Scripts/python.exe manage.py migrate`
Expected: aplica `maestros.0039`, `maestros.0040` y `procesos.0024`. Copia en el informe de la tarea lo que `0040` haya escrito (equipos que quedaron como estaban, formatos sin máquinas).

Run: `cd backend && ./.venv/Scripts/python.exe manage.py migrate maestros 0039 && ./.venv/Scripts/python.exe manage.py migrate`
Expected: la reversa de `0040` corre sin error (las mantequeras vuelven a `linea`) y la segunda pasada las reclasifica de nuevo. Es la ida y vuelta sobre la base de desarrollo; la de pruebas la cubren `test_deshacer_…` y `test_reclasificar_dos_veces_…`.

- [ ] **Step 7: Una sola regla de tipo** — en `backend/procesos/servicios.py`, `tipos_equipo_para_etapa`:

```python
        EtapaProceso.Tipo.MANTEQUILLA: {Equipo.Tipo.MANTEQUERA},
```

En `crear_mantequilla_guiada` reemplaza:

```python
    if equipo.tipo not in {Equipo.Tipo.LINEA, Equipo.Tipo.OTRO}:
        raise ValidationError({"equipo": "El equipo no corresponde a la línea de mantequilla."})
```

por:

```python
    if equipo.tipo not in tipos_equipo_para_etapa(EtapaProceso.Tipo.MANTEQUILLA):
        raise ValidationError({"equipo": f"{equipo.nombre} no es una mantequera."})
```

En `backend/procesos/views.py`, `CorridaMantequillaViewSet.opciones_alta` (vive hasta la Task 7):

```python
        equipos = filtrar_por_scope(
            Equipo.objects.filter(
                activo=True, tipo__in=tipos_equipo_para_etapa(EtapaProceso.Tipo.MANTEQUILLA),
            ),
            request.user, campo_sucursal="sucursal_id", campo_empresa="sucursal__empresa_id",
        )
```

(`tipos_equipo_para_etapa` ya se importa en `views.py`.)

- [ ] **Step 8: Migrar las pruebas que crean la máquina como línea**
  - `backend/procesos/tests_mantequilla.py`, `setUp`: `tipo=Equipo.Tipo.LINEA,` → `tipo=Equipo.Tipo.MANTEQUERA,` y `nombre="Línea mantequilla"` → `nombre="Mantequera"`.
  - `backend/procesos/tests.py:203`: `("man", EtapaProceso.Tipo.MANTEQUILLA, Equipo.Tipo.LINEA),` → `("man", EtapaProceso.Tipo.MANTEQUILLA, Equipo.Tipo.MANTEQUERA),`.

- [ ] **Step 9: Prueba del comando que falla** — crea `backend/produccion/tests_preparar_mantequilla.py`:

```python
from decimal import Decimal
from io import StringIO

from django.contrib.auth.models import User
from django.core.management import CommandError, call_command
from django.test import TestCase

from maestros.models import Equipo, FormatoEnvasado, Mandante, Producto
from procesos.models import Proceso, RutaProducto
from produccion.models import OrdenProduccion
from usuarios.models import Empresa, Sucursal
from usuarios.tenancy import unica_sucursal_activa


class PrepararCircuitoMantequillaTests(TestCase):
    """
    La mantequilla se bate en la mantequera y se envasa en una envasadora: el
    comando busca la primera por su tipo y autoriza la segunda en los formatos
    de la mantequilla. Antes buscaba «una línea que diga mantequilla» y el
    E2E envasaba en esa misma máquina.
    """

    def setUp(self):
        # Compatibilidad de esquema: el comando resuelve este registro técnico
        # sin recibir Empresa/Sucursal como selector funcional.
        self.sucursal = unica_sucursal_activa(None)
        if self.sucursal is None:
            empresa = Empresa.objects.create(rut="PCM-REF", nombre="Configuración técnica")
            self.sucursal = Sucursal.objects.create(
                empresa=empresa, codigo="PCM", nombre="Configuración técnica"
            )
        User.objects.create_superuser("admin-pcm", "admin-pcm@example.com", "clave-pcm")
        mandante, _ = Mandante.objects.get_or_create(
            empresa=self.sucursal.empresa, codigo_cliente=Mandante.Cliente.NO_DEFINIDO,
            defaults={"nombre": "CCAA PCM"},
        )
        self.producto = Producto.objects.create(
            mandante=mandante, nombre="Mantequilla sin sal 20 kg PCM",
            categoria=Producto.Categoria.MANTEQUILLA, formato=Producto.Formato.CAJA_20KG,
            naturaleza=Producto.Naturaleza.TERMINADO, unidad_base=Producto.Unidad.KG,
        )
        proceso, _ = Proceso.objects.update_or_create(
            codigo="ruta-mantequilla", version=1,
            defaults={"nombre": "Ruta mantequilla", "activo": True},
        )
        RutaProducto.objects.create(
            sucursal=self.sucursal, producto=self.producto, proceso=proceso,
            destino_final=RutaProducto.DestinoFinal.ENVASADO,
        )
        self.formato = FormatoEnvasado.objects.create(
            producto=self.producto, codigo="caja-20-pcm", nombre="Caja 20 kg",
            kg_neto=Decimal("20"), unidades_maximas_pallet=25,
        )

    def preparar(self):
        salida = StringIO()
        call_command("preparar_circuito_mantequilla", aplicar=True, stdout=salida)
        return salida.getvalue()

    def test_usa_la_mantequera_y_autoriza_una_envasadora_sin_duplicarla(self):
        self.preparar()
        self.preparar()

        envasadoras = Equipo.objects.filter(codigo="envasadora_mantequilla")
        self.assertEqual(envasadoras.count(), 1)
        envasadora = envasadoras.get()
        self.assertEqual(envasadora.tipo, Equipo.Tipo.ENVASADORA)
        self.assertEqual(envasadora.nombre, "Envasadora de mantequilla")
        self.assertIn(envasadora, self.formato.equipos.all())
        self.assertFalse(self.formato.equipos.filter(tipo=Equipo.Tipo.MANTEQUERA).exists())
        orden = OrdenProduccion.objects.get(producto=self.producto)
        self.assertEqual(orden.equipo.tipo, Equipo.Tipo.MANTEQUERA)

    def test_sin_mantequera_activa_lo_dice(self):
        Equipo.objects.filter(tipo=Equipo.Tipo.MANTEQUERA).update(activo=False)

        with self.assertRaisesMessage(CommandError, "Falta una mantequera activa"):
            self.preparar()

    def test_una_mantequilla_sin_formato_activo_se_avisa(self):
        self.formato.activo = False
        self.formato.save(update_fields=["activo"])

        salida = self.preparar()

        self.assertIn("no tiene un formato de envasado activo", salida)
        self.assertNotIn(
            "envasadora_mantequilla",
            self.formato.equipos.values_list("codigo", flat=True),
        )
```

Run: `cd backend && DJANGO_ENV=test ./.venv/Scripts/python.exe manage.py test produccion.tests_preparar_mantequilla --noinput`
Expected: FAIL — `CommandError: Falta la linea activa de mantequilla.` (la sembrada ya es mantequera).

- [ ] **Step 10: El comando** — en `backend/produccion/management/commands/preparar_circuito_mantequilla.py`:
  - Debajo de `MATERIALES_ENVASE` agrega `CODIGO_ENVASADORA = "envasadora_mantequilla"`.
  - Reemplaza la búsqueda de `linea` (`Equipo.objects.filter(activo=True, tipo=Equipo.Tipo.LINEA, nombre__icontains="mantequilla")` y su `CommandError`) por:

```python
        mantequera = Equipo.objects.filter(
            activo=True, tipo=Equipo.Tipo.MANTEQUERA,
        ).order_by("codigo").first()
        if mantequera is None:
            raise CommandError(
                "Falta una mantequera activa: créala en Maestros › Máquinas con tipo «Mantequera»."
            )
```

  - Vista previa: `f"Vista previa: {producto.nombre}, OP 40 kg, {mantequera.nombre}, envasadora de mantequilla autorizada en sus formatos, especificacion Codex provisional y lote trazable de mazada."`.
  - OP nueva: `equipo=mantequera,` y `linea=mantequera.nombre,`.
  - Después del bucle `for producto_mantequilla in productos_mantequilla:`:

```python
        envasadora, sin_formato = self._autorizar_envasadora(
            planta=planta, productos=productos_mantequilla,
        )
        for nombre in sin_formato:
            self.stdout.write(self.style.WARNING(
                f"{nombre} no tiene un formato de envasado activo: créalo en Maestros "
                "› Formatos de envasado y vuelve a correr el comando."
            ))
```

  - El mensaje final agrega `f"envasadora={envasadora.nombre}; "` antes de `f"receta_envase=…"`.
  - Método nuevo de `Command`:

```python
    def _autorizar_envasadora(self, *, planta, productos):
        """
        La mantequilla se envasa en una envasadora, no en la mantequera: el
        envasado acepta solo envasadora o línea (`FormatoEnvasado`,
        `Envase.clean()`) y `maestros.0040` sacó la mantequera de los
        formatos. Se asegura una y se autoriza en los formatos activos de cada
        mantequilla. Un producto sin formato se avisa, no se inventa: el
        formato es configuración de planta.

        Sin `consume_materiales`: la mantequera ya lo tiene, y marcar las dos
        haría que el MRP pidiera los envases dos veces.
        """
        envasadora, _ = Equipo.objects.get_or_create(
            sucursal=planta, codigo=CODIGO_ENVASADORA,
            defaults={"nombre": "Envasadora de mantequilla", "tipo": Equipo.Tipo.ENVASADORA},
        )
        if envasadora.tipo != Equipo.Tipo.ENVASADORA or not envasadora.activo:
            raise CommandError(
                f"{CODIGO_ENVASADORA} existe pero no es una envasadora activa: "
                "corrígelo en Maestros › Máquinas."
            )
        sin_formato = []
        for producto in productos:
            formatos = list(producto.formatos_envasado.filter(activo=True))
            if not formatos:
                sin_formato.append(producto.nombre)
            for formato in formatos:
                formato.equipos.add(envasadora)
        return envasadora, sin_formato
```

- [ ] **Step 11: Verificar**

Run: `cd backend && DJANGO_ENV=test ./.venv/Scripts/python.exe manage.py test maestros.tests_mantequeras produccion.tests_preparar_mantequilla procesos.tests_mantequilla procesos.tests --noinput`
Expected: OK.

Run: `cd backend && DJANGO_ENV=test ./.venv/Scripts/python.exe manage.py test maestros produccion procesos --noinput`
Expected: OK (`tests_cancelar_evaporacion` y `tests_lote_en_torre` recorren `Equipo.Tipo.values`: la mantequera no abre desde un vale y el conjunto esperado no cambia). Si `_preparar_materiales_envase` falla en la base de pruebas por configuración ajena a esta tarea, informa el error exacto antes de tocar el comando.

- [ ] **Step 12: Commit**

```bash
git add backend/maestros/models.py backend/maestros/migrations/0039_equipo_tipo_mantequera.py backend/maestros/migrations/0040_reclasificar_mantequeras.py backend/maestros/tests_mantequeras.py backend/procesos/models.py backend/procesos/migrations/0024_corrida_mantequilla_anulada.py backend/procesos/servicios.py backend/procesos/views.py backend/procesos/tests_mantequilla.py backend/procesos/tests.py backend/produccion/management/commands/preparar_circuito_mantequilla.py backend/produccion/tests_preparar_mantequilla.py
git commit -m "feat(maestros): la mantequera es un tipo de máquina y la migración reclasifica la de mantequilla"
```

---

### Task 2: El balance del cierre lo decide el servidor, una vez

**Files:**
- Modify: `backend/procesos/dominio.py` (balance y errores del cierre, debajo de `avisos_limites_descremacion`)
- Modify: `backend/procesos/models.py` (`CorridaMantequilla.clean()`, ~620-660)
- Modify: `backend/procesos/servicios.py` (`cerrar_mantequilla` ~2931; `revisar_cierre_mantequilla` nueva, justo antes)
- Modify: `backend/procesos/serializers.py` (`CierreMantequillaSerializer.validate`; `RevisarCierreMantequillaSerializer` nuevo, ~279-306)
- Modify: `backend/procesos/views.py` (`CorridaMantequillaViewSet.revisar_cierre`, imports)
- Modify: `backend/procesos/tests_mantequilla.py`

**Interfaces:**
- Produces (`procesos/dominio.py`):
  - `TOLERANCIA_BALANCE_MANTEQUILLA_KG = Decimal("0")`; `MENSAJE_FALTA_MANTEQUILLA = "Indica la mantequilla producida."`; `MENSAJE_SUERO_SIN_LOTE = "Esta corrida no tiene un lote de suero asociado: registra 0 kg."`; `MENSAJE_REPROCESO_SIN_MOTIVO = "Indica por qué este material requiere reproceso."`
  - `@dataclass(frozen=True) class BalanceMantequilla: entrada_kg: Decimal; clasificado_kg: Decimal; diferencia_kg: Decimal; cuadra: bool; mensaje: str | None`
  - `balance_mantequilla(*, kg_crema, kg_mantequilla, kg_suero=0, kg_merma=0, kg_reproceso=0) -> BalanceMantequilla`
  - `errores_cierre_mantequilla(*, tiene_lote_suero, kg_suero=0, kg_reproceso=0, motivo_reproceso="") -> dict[str, str]`
- Produces (`procesos/servicios.py`): `revisar_cierre_mantequilla(corrida, *, kg_mantequilla=None, kg_suero=None, kg_merma=None, kg_reproceso=None, motivo_reproceso="") -> dict`.
- `POST /api/procesos/mantequillas/{id}/revisar-cierre/` con el cuerpo de `cerrar/`, todo opcional → 200 `{"entrada_kg": "60.000", "clasificado_kg": "59.000", "diferencia_kg": "1.000", "cuadra": false, "mensaje": "El cierre debe clasificar el 100% de la crema: 1.000 kg faltan por clasificar.", "errores": {"kg_suero": "…"}}`; 403 sin la etapa. No escribe.
- `POST /api/procesos/mantequillas/{id}/cerrar/` que no cuadra → 400 `{"balance": ["El cierre debe clasificar…"]}` sin ninguna escritura.

- [ ] **Step 1: Pruebas que fallan** — en `backend/procesos/tests_mantequilla.py`:
  - Imports: `from django.test import SimpleTestCase, TestCase` y

```python
from .dominio import (
    MENSAJE_FALTA_MANTEQUILLA, MENSAJE_REPROCESO_SIN_MOTIVO, MENSAJE_SUERO_SIN_LOTE,
    balance_mantequilla, errores_cierre_mantequilla,
)
```

  - Antes de `class MantequillaTests`:

```python
class BalanceMantequillaDominioTests(SimpleTestCase):
    """
    El balance del cierre, sin ORM: los casos que fijaba
    `frontend/tests/balance-mantequilla.test.ts` (que se elimina en la Task 7)
    más los bordes en milésimas. Es la regla que usan el modelo, el cierre y
    `revisar-cierre/`.
    """

    def test_un_balance_exacto_con_reproceso_cuadra(self):
        balance = balance_mantequilla(
            kg_crema="1000", kg_mantequilla="420.123", kg_suero="559.877",
            kg_merma="10", kg_reproceso="10",
        )

        self.assertTrue(balance.cuadra)
        self.assertIsNone(balance.mensaje)
        self.assertEqual(balance.diferencia_kg, Decimal("0"))

    def test_si_falta_crema_por_clasificar_lo_dice(self):
        balance = balance_mantequilla(
            kg_crema="1000", kg_mantequilla="420", kg_suero="560", kg_merma="10",
        )

        self.assertFalse(balance.cuadra)
        self.assertEqual(balance.diferencia_kg, Decimal("10"))
        self.assertEqual(
            balance.mensaje,
            "El cierre debe clasificar el 100% de la crema: 10.000 kg faltan por clasificar.",
        )

    def test_si_excede_la_entrada_lo_dice(self):
        balance = balance_mantequilla(
            kg_crema="60", kg_mantequilla="31", kg_suero="28", kg_merma="2",
        )

        self.assertEqual(balance.diferencia_kg, Decimal("-1"))
        self.assertEqual(
            balance.mensaje,
            "El cierre debe clasificar el 100% de la crema: 1.000 kg exceden la entrada.",
        )

    def test_compara_en_milesimas_sin_errores_de_punto_flotante(self):
        self.assertTrue(
            balance_mantequilla(kg_crema="0.300", kg_mantequilla="0.100", kg_suero="0.200").cuadra
        )
        # Cada valor se redondea a la milésima, la precisión de las columnas.
        self.assertTrue(balance_mantequilla(kg_crema="1000", kg_mantequilla="999.9995").cuadra)
        borde = balance_mantequilla(kg_crema="1000", kg_mantequilla="999.9994")
        self.assertFalse(borde.cuadra)
        self.assertEqual(borde.diferencia_kg, Decimal("0.001"))

    def test_sin_mantequilla_no_cuadra_y_la_pide(self):
        balance = balance_mantequilla(kg_crema="60", kg_mantequilla=None, kg_suero="60")

        self.assertFalse(balance.cuadra)
        self.assertEqual(balance.mensaje, MENSAJE_FALTA_MANTEQUILLA)

    def test_un_valor_ausente_cuenta_como_cero(self):
        balance = balance_mantequilla(
            kg_crema="60", kg_mantequilla="60", kg_suero=None, kg_merma="", kg_reproceso=None,
        )

        self.assertTrue(balance.cuadra)
        self.assertEqual(balance.clasificado_kg, Decimal("60"))

    def test_las_otras_reglas_de_lo_tecleado(self):
        self.assertEqual(
            errores_cierre_mantequilla(tiene_lote_suero=False, kg_suero="5"),
            {"kg_suero": MENSAJE_SUERO_SIN_LOTE},
        )
        self.assertEqual(
            errores_cierre_mantequilla(
                tiene_lote_suero=True, kg_suero="5", kg_reproceso="2", motivo_reproceso="  ",
            ),
            {"motivo_reproceso": MENSAJE_REPROCESO_SIN_MOTIVO},
        )
        self.assertEqual(errores_cierre_mantequilla(tiene_lote_suero=False, kg_suero="0"), {})
```

  - En `MantequillaTests`, un ayudante y las pruebas de la API:

```python
    def cliente_de_area(self, area=PerfilUsuario.Area.CONDENSACION, nombre="condensador-mantequilla"):
        usuario = User.objects.create_user(nombre)
        PerfilUsuario.objects.create(
            usuario=usuario, empresa=self.empresa, sucursal=self.planta,
            rol=Rol.PRODUCCION, area=area,
        )
        cliente = APIClient()
        cliente.force_authenticate(usuario)
        return cliente

    def revisar(self, cliente, cuerpo):
        return cliente.post(
            f"/api/procesos/mantequillas/{self.corrida.pk}/revisar-cierre/", cuerpo, format="json",
        )

    def test_revisar_cierre_no_escribe_y_dice_lo_que_cerrar_rechazaria(self):
        iniciar_mantequilla(corrida_id=self.corrida.pk, usuario=self.usuario)
        cliente = self.cliente_de_area()
        cuerpo = {"kg_mantequilla": "420", "kg_suero": "500", "kg_merma": "10"}

        revision = self.revisar(cliente, cuerpo)

        self.assertEqual(revision.status_code, 200, revision.data)
        self.assertEqual(revision.data, {
            "entrada_kg": "1000.000", "clasificado_kg": "930.000", "diferencia_kg": "70.000",
            "cuadra": False,
            "mensaje": "El cierre debe clasificar el 100% de la crema: 70.000 kg faltan por clasificar.",
            "errores": {},
        })
        self.corrida.refresh_from_db()
        self.assertEqual(self.corrida.estado, CorridaMantequilla.Estado.EN_PROCESO)
        self.assertEqual(self.corrida.ejecucion.salidas.count(), 0)

        cierre = cliente.post(
            f"/api/procesos/mantequillas/{self.corrida.pk}/cerrar/", cuerpo, format="json",
        )

        self.assertEqual(cierre.status_code, 400, cierre.data)
        self.assertEqual(cierre.data["balance"], [revision.data["mensaje"]])

    def test_revisar_cierre_con_el_formulario_vacio_pide_la_mantequilla(self):
        iniciar_mantequilla(corrida_id=self.corrida.pk, usuario=self.usuario)

        revision = self.revisar(self.cliente_de_area(), {})

        self.assertEqual(revision.status_code, 200, revision.data)
        self.assertFalse(revision.data["cuadra"])
        self.assertEqual(revision.data["mensaje"], MENSAJE_FALTA_MANTEQUILLA)
        self.assertEqual(revision.data["clasificado_kg"], "0.000")

    def test_revisar_cierre_repite_las_reglas_del_suero_y_del_reproceso(self):
        iniciar_mantequilla(corrida_id=self.corrida.pk, usuario=self.usuario)
        self.corrida.lote_suero = None
        self.corrida.save(update_fields=["lote_suero"])

        revision = self.revisar(self.cliente_de_area(), {
            "kg_mantequilla": "420", "kg_suero": "570", "kg_merma": "5", "kg_reproceso": "5",
        })

        self.assertTrue(revision.data["cuadra"])
        self.assertEqual(revision.data["errores"], {
            "kg_suero": MENSAJE_SUERO_SIN_LOTE,
            "motivo_reproceso": MENSAJE_REPROCESO_SIN_MOTIVO,
        })

    def test_no_cierra_sin_cuadrar_y_no_deja_lote_de_reproceso(self):
        # Caracterización: antes la transacción ya revertía el lote creado;
        # ahora el balance se decide antes de escribir.
        iniciar_mantequilla(corrida_id=self.corrida.pk, usuario=self.usuario)

        with self.assertRaisesMessage(ValidationError, "faltan por clasificar"):
            cerrar_mantequilla(
                corrida_id=self.corrida.pk, usuario=self.usuario,
                kg_mantequilla="420", kg_suero="500", kg_merma="10",
                kg_reproceso="20", motivo_reproceso="Textura fuera de objetivo",
            )

        self.assertFalse(Lote.objects.filter(codigo_lote__startswith="RW-MANT-").exists())
        self.assertEqual(AutorizacionReproceso.objects.count(), 0)

    def test_secado_no_revisa_ni_cierra(self):
        iniciar_mantequilla(corrida_id=self.corrida.pk, usuario=self.usuario)
        secado = self.cliente_de_area(PerfilUsuario.Area.SECADO, "secador-mantequilla")
        cuerpo = {"kg_mantequilla": "420", "kg_suero": "570", "kg_merma": "10"}

        self.assertEqual(self.revisar(secado, cuerpo).status_code, 403)
        cierre = secado.post(
            f"/api/procesos/mantequillas/{self.corrida.pk}/cerrar/", cuerpo, format="json",
        )
        self.assertEqual(cierre.status_code, 403)
        self.corrida.refresh_from_db()
        self.assertEqual(self.corrida.estado, CorridaMantequilla.Estado.EN_PROCESO)
```

- [ ] **Step 2: Verificar que fallan**

Run: `cd backend && DJANGO_ENV=test ./.venv/Scripts/python.exe manage.py test procesos.tests_mantequilla --noinput`
Expected: ERROR `ImportError: cannot import name 'MENSAJE_FALTA_MANTEQUILLA' from 'procesos.dominio'`.

- [ ] **Step 3: La regla pura** — en `backend/procesos/dominio.py`, la primera línea pasa a `from decimal import ROUND_HALF_UP, Decimal` y, debajo de `avisos_limites_descremacion`:

```python
# Balance del cierre de Mantequilla. El cliente comparaba en milésimas de kg y
# el modelo exigía diferencia == 0: la misma regla. Tres decimales es la
# precisión de las columnas; cambiar la tolerancia es editar esta constante,
# no buscar dos comparaciones.
TOLERANCIA_BALANCE_MANTEQUILLA_KG = Decimal("0")
_MILESIMA = Decimal("0.001")

MENSAJE_FALTA_MANTEQUILLA = "Indica la mantequilla producida."
MENSAJE_SUERO_SIN_LOTE = "Esta corrida no tiene un lote de suero asociado: registra 0 kg."
MENSAJE_REPROCESO_SIN_MOTIVO = "Indica por qué este material requiere reproceso."


@dataclass(frozen=True)
class BalanceMantequilla:
    entrada_kg: Decimal
    clasificado_kg: Decimal
    diferencia_kg: Decimal  # entrada − clasificado
    cuadra: bool
    mensaje: str | None  # None si cuadra


def _kg(valor):
    """Un valor en kg redondeado a la milésima. Ausente cuenta como cero: se teclea de a poco."""
    if valor is None or valor == "":
        return Decimal("0")
    return Decimal(str(valor)).quantize(_MILESIMA, rounding=ROUND_HALF_UP)


def balance_mantequilla(*, kg_crema, kg_mantequilla, kg_suero=0, kg_merma=0, kg_reproceso=0):
    """
    ¿Clasifica el cierre el 100 % de la crema? Mantequilla, suero, merma y
    reproceso contra los kg de crema que entraron.

    Es la única regla: la usan `CorridaMantequilla.clean()`, `cerrar_mantequilla`
    (antes de escribir) y `revisar-cierre/` mientras se teclea. Antes el
    cliente la calculaba en milésimas y el modelo en `Decimal`; coincidían por
    casualidad de redondeo, no por construcción.
    """
    entrada = _kg(kg_crema)
    clasificado = sum(
        (_kg(valor) for valor in (kg_mantequilla, kg_suero, kg_merma, kg_reproceso)),
        Decimal("0"),
    )
    diferencia = entrada - clasificado
    if kg_mantequilla is None or kg_mantequilla == "":
        return BalanceMantequilla(entrada, clasificado, diferencia, False, MENSAJE_FALTA_MANTEQUILLA)
    if abs(diferencia) <= TOLERANCIA_BALANCE_MANTEQUILLA_KG:
        return BalanceMantequilla(entrada, clasificado, diferencia, True, None)
    sentido = "faltan por clasificar" if diferencia > 0 else "exceden la entrada"
    return BalanceMantequilla(
        entrada, clasificado, diferencia, False,
        f"El cierre debe clasificar el 100% de la crema: {abs(diferencia)} kg {sentido}.",
    )


def errores_cierre_mantequilla(*, tiene_lote_suero, kg_suero=0, kg_reproceso=0, motivo_reproceso=""):
    """
    Las otras reglas del cierre que dependen de lo tecleado, por campo: suero
    sin lote donde registrarlo y reproceso sin motivo. Las mismas para
    `clean()`, el cierre y `revisar-cierre/`, con el mismo texto.
    """
    errores = {}
    if _kg(kg_suero) > 0 and not tiene_lote_suero:
        errores["kg_suero"] = MENSAJE_SUERO_SIN_LOTE
    if _kg(kg_reproceso) > 0 and not (motivo_reproceso or "").strip():
        errores["motivo_reproceso"] = MENSAJE_REPROCESO_SIN_MOTIVO
    return errores
```

- [ ] **Step 4: El modelo usa la regla** — en `backend/procesos/models.py` agrega arriba `from .dominio import balance_mantequilla, errores_cierre_mantequilla` (`dominio.py` no importa modelos: no hay ciclo). En `CorridaMantequilla.clean()`:
  - Reemplaza las dos comprobaciones en línea —`if self.kg_suero and not self.lote_suero_id: …` y `if self.kg_reproceso and not self.motivo_reproceso.strip(): …`— por:

```python
        errores = errores_cierre_mantequilla(
            tiene_lote_suero=bool(self.lote_suero_id), kg_suero=self.kg_suero,
            kg_reproceso=self.kg_reproceso, motivo_reproceso=self.motivo_reproceso,
        )
        if errores:
            raise ValidationError(errores)
```

  (va donde estaba la del suero; la de `lote_reproceso` segregado se queda igual).
  - Reemplaza la aritmética del final (`total = (…)`, `diferencia = …`, `if diferencia != 0: …`) por:

```python
            balance = balance_mantequilla(
                kg_crema=self.kg_crema, kg_mantequilla=self.kg_mantequilla,
                kg_suero=self.kg_suero, kg_merma=self.kg_merma, kg_reproceso=self.kg_reproceso,
            )
            if not balance.cuadra:
                raise ValidationError({"balance": balance.mensaje})
```

  (sigue dentro de `if self.kg_mantequilla is not None:`, después del rechazo de `kg_mantequilla <= 0`).

- [ ] **Step 5: El cierre decide antes de escribir y la revisión no escribe** — en `backend/procesos/servicios.py`, justo antes de `cerrar_mantequilla`:

```python
def revisar_cierre_mantequilla(
    corrida, *, kg_mantequilla=None, kg_suero=None, kg_merma=None,
    kg_reproceso=None, motivo_reproceso="",
):
    """
    Lo que el cierre decidiría con estos valores, sin escribir nada. El
    formulario lo pide mientras se teclea (el patrón de
    `revisar_cierre_descremacion`) y habilita «Cerrar» solo con una revisión
    que cuadra: el cliente no calcula. La misma función que `cerrar_mantequilla`
    y `CorridaMantequilla.clean()`.
    """
    from .dominio import balance_mantequilla, errores_cierre_mantequilla

    balance = balance_mantequilla(
        kg_crema=corrida.kg_crema, kg_mantequilla=kg_mantequilla,
        kg_suero=kg_suero, kg_merma=kg_merma, kg_reproceso=kg_reproceso,
    )
    return {
        # Texto, como en los serializers: el tipo del frontend es `string`.
        "entrada_kg": str(balance.entrada_kg),
        "clasificado_kg": str(balance.clasificado_kg),
        "diferencia_kg": str(balance.diferencia_kg),
        "cuadra": balance.cuadra,
        "mensaje": balance.mensaje,
        "errores": errores_cierre_mantequilla(
            tiene_lote_suero=bool(corrida.lote_suero_id), kg_suero=kg_suero,
            kg_reproceso=kg_reproceso, motivo_reproceso=motivo_reproceso,
        ),
    }
```

En `cerrar_mantequilla`, agrega a los imports de la función `from .dominio import balance_mantequilla, errores_cierre_mantequilla` y, justo después de `corrida.controles = controles or {}` (antes de `if corrida.kg_reproceso:`):

```python
    # El balance y las reglas de lo tecleado se deciden antes de escribir
    # nada —hoy el lote de reproceso se creaba y `clean()` lo revertía—, con
    # las mismas funciones que `revisar-cierre/` y `clean()`.
    errores = errores_cierre_mantequilla(
        tiene_lote_suero=bool(corrida.lote_suero_id), kg_suero=corrida.kg_suero,
        kg_reproceso=corrida.kg_reproceso, motivo_reproceso=corrida.motivo_reproceso,
    )
    if errores:
        raise ValidationError(errores)
    balance = balance_mantequilla(
        kg_crema=corrida.kg_crema, kg_mantequilla=corrida.kg_mantequilla,
        kg_suero=corrida.kg_suero, kg_merma=corrida.kg_merma,
        kg_reproceso=corrida.kg_reproceso,
    )
    if not balance.cuadra:
        raise ValidationError({"balance": balance.mensaje})
```

- [ ] **Step 6: Serializers** — en `backend/procesos/serializers.py`:
  - `CierreMantequillaSerializer.validate`: el texto literal pasa a la constante (`from .dominio import MENSAJE_REPROCESO_SIN_MOTIVO` al inicio del archivo):

```python
    def validate(self, attrs):
        if attrs["kg_reproceso"] > 0 and not attrs["motivo_reproceso"].strip():
            raise serializers.ValidationError({"motivo_reproceso": MENSAJE_REPROCESO_SIN_MOTIVO})
        return attrs
```

  - Debajo, nuevo:

```python
class RevisarCierreMantequillaSerializer(serializers.Serializer):
    """El cuerpo de `cerrar/`, todo opcional: se pide mientras se teclea."""

    kg_mantequilla = serializers.DecimalField(
        max_digits=14, decimal_places=3, min_value=Decimal("0"),
        required=False, allow_null=True, default=None,
    )
    kg_suero = serializers.DecimalField(
        max_digits=14, decimal_places=3, min_value=Decimal("0"),
        required=False, allow_null=True, default=None,
    )
    kg_merma = serializers.DecimalField(
        max_digits=14, decimal_places=3, min_value=Decimal("0"),
        required=False, allow_null=True, default=None,
    )
    kg_reproceso = serializers.DecimalField(
        max_digits=14, decimal_places=3, min_value=Decimal("0"),
        required=False, allow_null=True, default=None,
    )
    motivo_reproceso = serializers.CharField(
        max_length=250, required=False, allow_blank=True, default="",
    )
    # Se acepta para que el formulario mande el mismo cuerpo que a `cerrar/`;
    # no entra al balance.
    controles = serializers.JSONField(required=False, default=dict)
```

- [ ] **Step 7: Vista** — en `backend/procesos/views.py` importa `RevisarCierreMantequillaSerializer` y `revisar_cierre_mantequilla`; en `CorridaMantequillaViewSet`, antes de `cerrar`:

```python
    @action(detail=True, methods=["post"], url_path="revisar-cierre")
    def revisar_cierre(self, request, pk=None):
        """El balance del cierre con lo tecleado hasta ahora; no escribe nada."""
        entrada = RevisarCierreMantequillaSerializer(data=request.data)
        entrada.is_valid(raise_exception=True)
        datos = {
            clave: valor for clave, valor in entrada.validated_data.items()
            if clave != "controles"
        }
        return Response(revisar_cierre_mantequilla(self.get_object(), **datos))
```

  (`OperaProcesoPorEtapa` con `tipo_etapa_operacional = MANTEQUILLA` ya exige la etapa en todo `POST`.)

- [ ] **Step 8: Verificar**

Run: `cd backend && DJANGO_ENV=test ./.venv/Scripts/python.exe manage.py test procesos.tests_mantequilla --noinput`
Expected: OK (incluye `test_no_cierra_si_queda_crema_sin_clasificar`, sin cambios).

Run: `cd backend && DJANGO_ENV=test ./.venv/Scripts/python.exe manage.py test procesos calidad produccion --noinput`
Expected: OK.

- [ ] **Step 9: Commit**

```bash
git add backend/procesos/dominio.py backend/procesos/models.py backend/procesos/servicios.py backend/procesos/serializers.py backend/procesos/views.py backend/procesos/tests_mantequilla.py
git commit -m "feat(procesos): el balance del cierre de mantequilla es una función del servidor que también revisa mientras se teclea"
```

---

### Task 3: «Preparar» toma la mantequera; iniciar tiene una sola regla

**Files:**
- Modify: `backend/procesos/servicios.py` (constantes junto a `MENSAJE_MOTIVO_CANCELACION` ~87; `crear_mantequilla_guiada` ~955; `preparar_continuacion` ~1019; reglas nuevas e `iniciar_mantequilla` ~2838; `RESOLVER_PLANIFICACION` junto a `RESOLVER_SILOS` ~3374)
- Modify: `backend/produccion/management/commands/preparar_circuito_mantequilla.py` (lote de mazada)
- Create: `backend/procesos/tests_puesto_mantequilla.py`
- Modify: `backend/procesos/tests_mantequilla.py`

**Interfaces:**
- Consumes: `Equipo.Tipo.MANTEQUERA`, `tipos_equipo_para_etapa` (Task 1).
- Produces (`procesos/servicios.py`):
  - `MENSAJE_MANTEQUILLA_EN_PUESTO = "La mantequilla se prepara en el puesto de Mantequilla."`; `RESOLVER_PLANIFICACION = "/planificacion"`
  - `filtro_crema_liberada() -> Q` (sobre `Lote`)
  - `sueros_libres(consulta=None) -> QuerySet[Lote]`
  - `kg_crema_disponible(lote, *, excluir_corrida_id=None) -> Decimal`
  - `motivos_crema_para_mantequilla(lote, kg, *, excluir_corrida_id=None) -> list[tuple[str, str | None]]`
  - `fuente_tk_de_crema(lote) -> SalidaProceso | None`; `litros_de_crema(kg, densidad) -> Decimal`
  - `crear_mantequilla_guiada(*, orden_id, lote_crema_id, equipo_id, codigo_lote_mantequilla, kg_crema, usuario, lote_suero_id=None) -> CorridaMantequilla` (misma firma; ahora prepara)
  - `motivos_tipados_para_iniciar_mantequilla(corrida, *, ejecucion=None) -> list[tuple[str, str | None]]`; `motivos_para_iniciar_mantequilla(corrida, *, ejecucion=None) -> list[str]`
  - `iniciar_mantequilla(*, corrida_id, usuario) -> CorridaMantequilla` (misma firma; ya no prepara)
- `POST /api/procesos/mantequillas/crear-guiada/` `{orden, lote_crema, equipo, codigo_lote_mantequilla, kg_crema, lote_suero?}` → 201 `CorridaMantequillaSerializer` (ejecución `EJ-MANT-{lote}` en `preparacion`, mantequera tomada, corrida `borrador`); 400 con el motivo; 403 sin la etapa.
- `POST /api/procesos/mantequillas/{id}/iniciar/` → 200, o 400 con el primer motivo.
- Fixture `BasePuestoMantequilla` en `tests_puesto_mantequilla.py` (la usan las Tasks 4, 5 y 7).

- [ ] **Step 1: Fixture y pruebas que fallan** — crea `backend/procesos/tests_puesto_mantequilla.py`:

```python
from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from calidad.models import LiberacionProceso
from inventario.models import CicloCIP
from maestros.models import Equipo, Mandante, Producto, Silo
from produccion.models import Lote, OrdenProduccion
from recepcion.models import AnalisisSilo, MovimientoSilo
from usuarios.models import Empresa, PerfilUsuario, Rol, Sucursal

from .models import (
    CorridaMantequilla, EjecucionProceso, EntradaProceso, EtapaProceso, Proceso,
    RutaProducto, SalidaProceso,
)
from .servicios import (
    MENSAJE_MANTEQUILLA_EN_PUESTO, MENSAJE_SALIDA_DE_LOTE_ANULADO, RESOLVER_CALIDAD,
    RESOLVER_CIP, RESOLVER_PLANIFICACION, RESOLVER_SILOS, iniciar_mantequilla,
    motivos_para_iniciar_mantequilla, motivos_tipados_para_iniciar_mantequilla,
    preparar_continuacion,
)


class BasePuestoMantequilla(TestCase):
    """
    Una crema liberada de 1.000 kg, una OP programada, un lote de mazada libre
    y dos mantequeras libres: lo que el puesto ve al empezar el turno.

    Las migraciones siembran equipos en la base de pruebas (la
    `linea_mantequilla`, ya mantequera) y `filtrar_por_scope` ya no aísla por
    empresa: las aserciones se hacen sobre los objetos de esta fixture, nunca
    sobre listas completas.
    """

    def setUp(self):
        self.empresa = Empresa.objects.create(rut="PMAN-1", nombre="Empresa puesto mantequilla")
        self.planta = Sucursal.objects.create(
            empresa=self.empresa, codigo="PMAN", nombre="Planta puesto mantequilla"
        )
        self.condensador = self._usuario("condensador-pman", PerfilUsuario.Area.CONDENSACION)
        self.secador = self._usuario("secador-pman", PerfilUsuario.Area.SECADO)
        self.calidad = self._usuario("calidad-pman", PerfilUsuario.Area.CALIDAD, Rol.CALIDAD)
        mandante = Mandante.objects.create(
            empresa=self.empresa, nombre="Mandante puesto mantequilla", codigo_cliente="pmn"
        )
        self.producto_crema = Producto.objects.create(
            mandante=mandante, nombre="Crema PM", familia=Producto.Familia.CREMA,
            naturaleza=Producto.Naturaleza.INTERMEDIO, unidad_base=Producto.Unidad.KG,
        )
        self.producto_mantequilla = Producto.objects.create(
            mandante=mandante, nombre="Mantequilla PM", categoria=Producto.Categoria.MANTEQUILLA,
            naturaleza=Producto.Naturaleza.TERMINADO, unidad_base=Producto.Unidad.KG,
        )
        self.producto_suero = Producto.objects.create(
            mandante=mandante, nombre="Mazada PM", categoria=Producto.Categoria.SUERO,
            naturaleza=Producto.Naturaleza.INTERMEDIO, unidad_base=Producto.Unidad.KG,
        )
        proceso = Proceso.objects.create(codigo="mantequilla-puesto", nombre="Mantequilla del puesto")
        self.etapa = EtapaProceso.objects.create(
            proceso=proceso, codigo="batir-pm", nombre="Batido",
            tipo=EtapaProceso.Tipo.MANTEQUILLA, orden=1, requiere_calidad=True,
        )
        RutaProducto.objects.create(
            sucursal=self.planta, producto=self.producto_mantequilla, proceso=proceso,
            destino_final=RutaProducto.DestinoFinal.ENVASADO,
        )
        origen = Proceso.objects.create(codigo="descremar-pm", nombre="Origen de la crema PM")
        self.etapa_origen = EtapaProceso.objects.create(
            proceso=origen, codigo="descremar-pm", nombre="Descremación",
            tipo=EtapaProceso.Tipo.DESCREMACION, orden=1,
        )
        self.mantequera = self._mantequera("mant-pm1", "Mantequera PM 1", "P1")
        self.otra_mantequera = self._mantequera("mant-pm2", "Mantequera PM 2", "P2")
        self.orden = OrdenProduccion.objects.create(
            sucursal=self.planta, codigo="OP-PM-1", producto=self.producto_mantequilla,
            cantidad_planificada=400, unidad="kg", estado=OrdenProduccion.Estado.PROGRAMADA,
        )
        self.crema = self.lote_crema("CR-PM-1")
        self.suero = Lote.objects.create(
            sucursal=self.planta, codigo_lote="MAZ-PM-1", producto=self.producto_suero,
            fecha=date(2026, 10, 8),
        )
        self._correlativo = 0

    def _usuario(self, nombre, area, rol=Rol.PRODUCCION):
        usuario = User.objects.create_user(nombre)
        PerfilUsuario.objects.create(
            usuario=usuario, empresa=self.empresa, sucursal=self.planta, area=area, rol=rol,
        )
        return usuario

    def _mantequera(self, codigo, nombre, sigla):
        return Equipo.objects.create(
            sucursal=self.planta, codigo=codigo, nombre=nombre, sigla=sigla,
            tipo=Equipo.Tipo.MANTEQUERA,
        )

    def lote_crema(self, codigo, *, kg="1000", liberacion=LiberacionProceso.Estado.LIBERADO,
                   silo=None, analisis=None):
        """
        Un lote de crema producido por Descremación, con su salida. Con
        `liberacion=None` la salida no tiene decisión de Calidad
        («trazabilidad incompleta»).
        """
        lote = Lote.objects.create(
            sucursal=self.planta, codigo_lote=codigo, producto=self.producto_crema,
            fecha=date(2026, 10, 8), estado=Lote.Estado.PRODUCIDO, kg_producidos=Decimal(kg),
        )
        ejecucion = EjecucionProceso.objects.create(
            codigo=f"EJ-ORIGEN-{codigo}", etapa=self.etapa_origen, sucursal=self.planta,
            estado=EjecucionProceso.Estado.CERRADA,
        )
        salida = SalidaProceso.objects.create(
            ejecucion=ejecucion, lote=lote, producto=self.producto_crema, silo=silo,
            naturaleza=SalidaProceso.Naturaleza.COPRODUCTO,
            clasificacion=SalidaProceso.Clasificacion.INTERMEDIO,
            destino=SalidaProceso.Destino.SIGUIENTE_PROCESO,
            cantidad=Decimal(kg), unidad="L" if silo else "kg",
        )
        if liberacion is not None:
            LiberacionProceso.objects.create(salida=salida, analisis_silo=analisis, estado=liberacion)
        return lote

    def crema_en_tk(self, codigo, *, kg="1000", segunda_firma=True, densidad="1000"):
        """Una crema liberada que está en un TK con su análisis (densidad incluida)."""
        tk = Silo.objects.create(
            sucursal=self.planta, codigo=f"TK-{codigo}", tipo=Silo.Tipo.TK_CREMA, capacidad_l=5000,
        )
        MovimientoSilo.objects.create(
            silo=tk, tipo=MovimientoSilo.Tipo.INGRESO, litros=Decimal(kg),
            fecha_hora=timezone.now() - timedelta(hours=2),
            origen_tipo=MovimientoSilo.OrigenTipo.DESCREMACION,
        )
        analisis = AnalisisSilo.objects.create(
            silo=tk, tomado_en=timezone.now() - timedelta(hours=1),
            grasa=Decimal("40"), sng=Decimal("5"), densidad=Decimal(densidad),
            inhibidores_resultado="negativo", metodo="snap",
            hora_lectura=timezone.localtime().time(),
            estado=AnalisisSilo.Estado.CONFIRMADO, analista=self.condensador,
            visualizado_por=self.calidad if segunda_firma else None,
        )
        return self.lote_crema(codigo, kg=kg, silo=tk, analisis=analisis), tk

    def corrida_heredada(self, codigo="EJ-MANT-HEREDADA"):
        """Una corrida del modal anterior: ejecución en `borrador`, sin la mantequera tomada."""
        ejecucion = EjecucionProceso.objects.create(
            codigo=codigo, etapa=self.etapa, sucursal=self.planta,
            equipo=self.mantequera, responsable=self.condensador,
        )
        salida = Lote.objects.create(
            sucursal=self.planta, codigo_lote=f"LOTE-{codigo}", producto=self.producto_mantequilla,
            orden=self.orden, fecha=date(2026, 10, 8), estado=Lote.Estado.EN_PROCESO,
            ejecucion=ejecucion,
        )
        return CorridaMantequilla.objects.create(
            ejecucion=ejecucion, orden=self.orden, lote_crema=self.crema,
            lote_mantequilla=salida, kg_crema=Decimal("60"),
        )

    def cip(self, equipo, estado=CicloCIP.Estado.EN_CURSO, horas=1):
        return CicloCIP.objects.create(
            sucursal=self.planta, area=PerfilUsuario.Area.CONDENSACION, equipo=equipo,
            inicio=timezone.now() - timedelta(hours=horas), estado=estado,
        )

    def cliente(self, usuario=None):
        cliente = APIClient()
        cliente.force_authenticate(usuario or self.condensador)
        return cliente

    def datos_preparar(self, **cambios):
        self._correlativo += 1
        datos = {
            "orden": self.orden.pk, "lote_crema": self.crema.pk, "equipo": self.mantequera.pk,
            "codigo_lote_mantequilla": f"MANT-PM-{self._correlativo}", "kg_crema": "60",
        }
        datos.update(cambios)
        return datos

    def preparar(self, usuario=None, **cambios):
        return self.cliente(usuario).post(
            "/api/procesos/mantequillas/crear-guiada/", self.datos_preparar(**cambios), format="json",
        )

    def preparada(self, **cambios):
        respuesta = self.preparar(**cambios)
        self.assertEqual(respuesta.status_code, 201, respuesta.data)
        return self.recargar(respuesta.data["id"])

    def en_curso(self, **cambios):
        corrida = self.preparada(**cambios)
        iniciar_mantequilla(corrida_id=corrida.pk, usuario=self.condensador)
        return self.recargar(corrida.pk)

    def recargar(self, corrida_id):
        return CorridaMantequilla.objects.select_related(
            "ejecucion__etapa", "ejecucion__equipo", "orden", "lote_crema__producto",
            "lote_mantequilla", "lote_suero",
        ).get(pk=corrida_id)


class PrepararMantequillaTests(BasePuestoMantequilla):
    def test_preparar_crea_lote_ejecucion_preparada_y_corrida_sin_mover_crema(self):
        corrida = self.preparada(lote_suero=self.suero.pk)

        self.assertEqual(corrida.estado, CorridaMantequilla.Estado.BORRADOR)
        self.assertEqual(corrida.ejecucion.estado, EjecucionProceso.Estado.PREPARACION)
        self.assertEqual(corrida.ejecucion.equipo, self.mantequera)
        self.assertEqual(corrida.ejecucion.codigo, f"EJ-MANT-{corrida.lote_mantequilla_id}")
        self.assertEqual(corrida.lote_mantequilla.estado, Lote.Estado.EN_PROCESO)
        self.assertEqual(corrida.lote_suero, self.suero)
        # Hasta iniciar, la crema no entró a la mantequera.
        self.assertFalse(EntradaProceso.objects.filter(lote=self.crema).exists())

    def test_una_mantequera_ocupada_no_se_prepara_y_no_deja_nada(self):
        self.preparada()

        respuesta = self.preparar()

        self.assertEqual(respuesta.status_code, 400, respuesta.data)
        self.assertIn("ocupad", str(respuesta.data))
        self.assertEqual(Lote.objects.filter(producto=self.producto_mantequilla).count(), 1)
        self.assertEqual(EjecucionProceso.objects.filter(equipo=self.mantequera).count(), 1)

    def test_una_mantequera_en_cip_no_se_prepara(self):
        self.cip(self.mantequera)

        respuesta = self.preparar()

        self.assertEqual(respuesta.status_code, 400, respuesta.data)
        self.assertIn("CIP", str(respuesta.data))
        self.assertFalse(Lote.objects.filter(producto=self.producto_mantequilla).exists())

    def test_una_linea_no_es_mantequera(self):
        linea = Equipo.objects.create(
            sucursal=self.planta, codigo="linea-pm", nombre="Línea PM", tipo=Equipo.Tipo.LINEA,
        )

        respuesta = self.preparar(equipo=linea.pk)

        self.assertEqual(respuesta.status_code, 400, respuesta.data)
        self.assertIn("no es una mantequera", str(respuesta.data))

    def test_no_prepara_mas_crema_que_la_disponible_contando_otra_preparada(self):
        self.preparada(kg_crema="600")

        respuesta = self.preparar(equipo=self.otra_mantequera.pk, kg_crema="500")

        self.assertEqual(respuesta.status_code, 400, respuesta.data)
        self.assertIn("400.000 kg disponibles", str(respuesta.data))
        self.assertFalse(EjecucionProceso.objects.filter(equipo=self.otra_mantequera).exists())

    def test_una_crema_pendiente_de_calidad_no_se_prepara(self):
        pendiente = self.lote_crema("CR-PM-PEND", liberacion=LiberacionProceso.Estado.PENDIENTE)

        respuesta = self.preparar(lote_crema=pendiente.pk)

        self.assertEqual(respuesta.status_code, 400, respuesta.data)
        self.assertIn("todavía no está liberado por Calidad", str(respuesta.data))

    def test_las_condiciones_del_tk_no_frenan_la_preparacion(self):
        crema, _tk = self.crema_en_tk("CR-PM-SINFIRMA", segunda_firma=False)

        self.preparada(lote_crema=crema.pk, kg_crema="200")

    def test_un_suero_tomado_por_una_corrida_viva_no_se_prepara(self):
        self.preparada(lote_suero=self.suero.pk)

        respuesta = self.preparar(equipo=self.otra_mantequera.pk, lote_suero=self.suero.pk)

        self.assertEqual(respuesta.status_code, 400, respuesta.data)
        self.assertIn("no puede recibir el suero", str(respuesta.data))

    def test_preparar_continuacion_no_crea_una_mantequilla_sin_corrida(self):
        salida = SalidaProceso.objects.get(lote=self.crema)
        antes = EjecucionProceso.objects.count()

        with self.assertRaisesMessage(ValidationError, MENSAJE_MANTEQUILLA_EN_PUESTO):
            preparar_continuacion(
                salida_id=salida.pk, etapa_id=self.etapa.pk, equipo_id=self.mantequera.pk,
                cantidad="10", usuario=self.condensador,
            )

        self.assertEqual(EjecucionProceso.objects.count(), antes)

    def test_secado_no_prepara(self):
        respuesta = self.preparar(usuario=self.secador)

        self.assertEqual(respuesta.status_code, 403)
        self.assertFalse(Lote.objects.filter(producto=self.producto_mantequilla).exists())


class IniciarMantequillaTests(BasePuestoMantequilla):
    def iniciar(self, corrida, usuario=None):
        return self.cliente(usuario).post(f"/api/procesos/mantequillas/{corrida.pk}/iniciar/")

    def test_sin_motivos_inicia_con_una_entrada(self):
        corrida = self.preparada()
        self.assertEqual(motivos_para_iniciar_mantequilla(corrida), [])

        respuesta = self.iniciar(corrida)

        self.assertEqual(respuesta.status_code, 200, respuesta.data)
        corrida = self.recargar(corrida.pk)
        self.assertEqual(corrida.estado, CorridaMantequilla.Estado.EN_PROCESO)
        self.assertEqual(corrida.ejecucion.estado, EjecucionProceso.Estado.EJECUCION)
        self.assertEqual(corrida.ejecucion.entradas.count(), 1)
        self.assertEqual(corrida.orden.estado, OrdenProduccion.Estado.EN_PROCESO)

    def test_la_crema_del_tk_sale_al_iniciar_y_no_al_preparar(self):
        crema, tk = self.crema_en_tk("CR-PM-TK")
        corrida = self.preparada(lote_crema=crema.pk, kg_crema="200")
        salidas = MovimientoSilo.objects.filter(silo=tk, tipo=MovimientoSilo.Tipo.SALIDA)
        self.assertFalse(salidas.exists())

        iniciar_mantequilla(corrida_id=corrida.pk, usuario=self.condensador)

        self.assertEqual(salidas.get().litros, Decimal("200.00"))

    def test_un_tk_sin_segunda_firma_se_resuelve_en_silos(self):
        crema, _tk = self.crema_en_tk("CR-PM-FIRMA", segunda_firma=False)
        corrida = self.preparada(lote_crema=crema.pk, kg_crema="200")

        motivo, resolver_en = motivos_tipados_para_iniciar_mantequilla(corrida)[0]

        self.assertIn("firma de realización y visualización", motivo)
        self.assertEqual(resolver_en, RESOLVER_SILOS)
        respuesta = self.iniciar(corrida)
        self.assertEqual(respuesta.status_code, 400, respuesta.data)
        self.assertIn(motivo, str(respuesta.data))
        corrida = self.recargar(corrida.pk)
        self.assertEqual(corrida.ejecucion.estado, EjecucionProceso.Estado.PREPARACION)
        self.assertFalse(corrida.ejecucion.entradas.exists())

    def test_una_mantequera_en_cip_se_resuelve_en_inocuidad(self):
        corrida = self.preparada()
        self.cip(self.mantequera)

        motivo, resolver_en = motivos_tipados_para_iniciar_mantequilla(corrida)[0]

        self.assertIn("CIP", motivo)
        self.assertEqual(resolver_en, RESOLVER_CIP)

    def test_una_orden_cancelada_se_resuelve_en_planificacion(self):
        corrida = self.preparada()
        OrdenProduccion.objects.filter(pk=self.orden.pk).update(
            estado=OrdenProduccion.Estado.CANCELADA,
        )

        motivo, resolver_en = motivos_tipados_para_iniciar_mantequilla(self.recargar(corrida.pk))[0]

        self.assertIn("OP-PM-1", motivo)
        self.assertEqual(resolver_en, RESOLVER_PLANIFICACION)

    def test_una_crema_que_perdio_la_liberacion_se_resuelve_en_calidad(self):
        corrida = self.preparada()
        LiberacionProceso.objects.filter(salida__lote=self.crema).update(
            estado=LiberacionProceso.Estado.PENDIENTE,
        )

        motivo, resolver_en = motivos_tipados_para_iniciar_mantequilla(corrida)[0]

        self.assertIn("todavía no está liberado por Calidad", motivo)
        self.assertEqual(resolver_en, RESOLVER_CALIDAD)

    def test_un_lote_de_crema_anulado_no_se_inicia(self):
        corrida = self.preparada()
        Lote.objects.filter(pk=self.crema.pk).update(estado=Lote.Estado.ANULADO)

        self.assertEqual(
            motivos_tipados_para_iniciar_mantequilla(self.recargar(corrida.pk)),
            [(MENSAJE_SALIDA_DE_LOTE_ANULADO.format(codigo=self.crema.codigo_lote), None)],
        )

    def test_los_motivos_son_lo_que_rechaza_iniciar(self):
        corrida = self.preparada()
        OrdenProduccion.objects.filter(pk=self.orden.pk).update(
            estado=OrdenProduccion.Estado.CANCELADA,
        )
        motivos = motivos_para_iniciar_mantequilla(self.recargar(corrida.pk))
        self.assertTrue(motivos)

        with self.assertRaises(ValidationError) as error:
            iniciar_mantequilla(corrida_id=corrida.pk, usuario=self.condensador)

        self.assertEqual(error.exception.messages[0], motivos[0])

    def test_un_aseo_observado_avisa_y_queda_en_el_evento(self):
        corrida = self.preparada()
        self.cip(self.mantequera, estado=CicloCIP.Estado.OBSERVADO, horas=3)
        self.assertEqual(motivos_para_iniciar_mantequilla(corrida), [])

        iniciar_mantequilla(corrida_id=corrida.pk, usuario=self.condensador)

        evento = corrida.ejecucion.eventos.get(estado_nuevo=EjecucionProceso.Estado.EJECUCION)
        self.assertIn("Advertencia no bloqueante de aseo", evento.motivo)

    def test_una_corrida_heredada_en_borrador_no_esta_preparada(self):
        corrida = self.corrida_heredada()

        motivos = motivos_para_iniciar_mantequilla(corrida)

        self.assertEqual(motivos, ["EJ-MANT-HEREDADA no está preparada: está borrador."])

    def test_una_corrida_iniciada_no_vuelve_a_iniciar(self):
        corrida = self.en_curso()

        self.assertEqual(self.iniciar(corrida).status_code, 400)

    def test_secado_no_inicia(self):
        corrida = self.preparada()

        self.assertEqual(self.iniciar(corrida, self.secador).status_code, 403)
        corrida = self.recargar(corrida.pk)
        self.assertEqual(corrida.ejecucion.estado, EjecucionProceso.Estado.PREPARACION)
```

- [ ] **Step 2: Verificar que fallan**

Run: `cd backend && DJANGO_ENV=test ./.venv/Scripts/python.exe manage.py test procesos.tests_puesto_mantequilla --noinput`
Expected: ERROR `ImportError: cannot import name 'MENSAJE_MANTEQUILLA_EN_PUESTO'`.

- [ ] **Step 3: Constantes** — en `backend/procesos/servicios.py`, debajo de `MENSAJE_MOTIVO_CANCELACION`:

```python
# La mantequilla tiene una sola entrada: su puesto. `preparar_continuacion`
# creaba una ejecución de Mantequilla sin `CorridaMantequilla`, sin cierre ni
# balance que ninguna pantalla supiera hacer.
MENSAJE_MANTEQUILLA_EN_PUESTO = "La mantequilla se prepara en el puesto de Mantequilla."
```

y debajo de `RESOLVER_SILOS`:

```python
# Motivos de la orden (cancelada, cerrada): se resuelven donde se programan.
RESOLVER_PLANIFICACION = "/planificacion"
```

- [ ] **Step 4: Las reglas de la crema y del suero, una vez** — en `backend/procesos/servicios.py`, antes de `crear_mantequilla_guiada`:

```python
def filtro_crema_liberada():
    """
    Un lote de crema que Calidad liberó: alguna de sus salidas tiene la
    liberación en `liberado`. Una sola condición para la lista `cremas` del
    puesto, «Preparar» y el inicio: antes el inicio solo la miraba si la crema
    estaba en un TK, y la lista la exigía siempre.
    """
    from calidad.models import LiberacionProceso

    return Q(salidas_proceso__liberacion_calidad__estado=LiberacionProceso.Estado.LIBERADO)


def sueros_libres(consulta=None):
    """
    Los lotes de suero o mazada que una corrida puede tomar: categoría suero,
    en borrador o en proceso, sin kilos y sin una corrida de mantequilla
    **viva** —una `anulada` lo suelta, aunque conserve el rastro—. La usan la
    lista `sueros` del puesto, «Preparar» y `preparar_circuito_mantequilla`.
    """
    from produccion.models import Lote

    consulta = Lote.objects.all() if consulta is None else consulta
    vivas = CorridaMantequilla.objects.filter(lote_suero=OuterRef("pk")).exclude(
        estado=CorridaMantequilla.Estado.ANULADA,
    )
    return consulta.filter(
        producto__categoria="suero",
        estado__in=[Lote.Estado.BORRADOR, Lote.Estado.EN_PROCESO],
        kg_producidos__isnull=True,
    ).exclude(Exists(vivas))


def kg_crema_disponible(lote, *, excluir_corrida_id=None):
    """
    Lo que queda de una crema para una corrida de mantequilla: sus kilos
    producidos menos lo que ya entró a una mantequera (las entradas en kg que
    no son una preparación cancelada) y menos lo que **otras corridas
    preparadas** ya pidieron (corrida `borrador` con su ejecución viva).

    Una cantidad, una consulta: la usan la lista `cremas` del puesto,
    «Preparar» y el inicio. Sin restar las preparadas, el puesto ofrecía una
    crema que el inicio de la segunda corrida rechazaba (caso 1 de «La
    pantalla ofrece lo que el backend va a rechazar», `CLAUDE.md`).
    """
    utilizado = EntradaProceso.objects.filter(
        lote=lote, unidad__iexact="kg",
    ).exclude(PREPARACION_CANCELADA).aggregate(total=Sum("cantidad"))["total"] or Decimal("0")
    preparadas = CorridaMantequilla.objects.filter(
        lote_crema=lote, estado=CorridaMantequilla.Estado.BORRADOR,
    ).exclude(ejecucion__estado__in=ESTADOS_EJECUCION_TERMINALES)
    if excluir_corrida_id is not None:
        preparadas = preparadas.exclude(pk=excluir_corrida_id)
    comprometido = preparadas.aggregate(total=Sum("kg_crema"))["total"] or Decimal("0")
    return Decimal(str(lote.kg_producidos or 0)) - utilizado - comprometido


def motivos_crema_para_mantequilla(lote, kg, *, excluir_corrida_id=None):
    """
    Por qué `kg` de este lote no pueden entrar a una corrida de mantequilla,
    como pares `(motivo, resolver_en)`. Lista vacía: pueden.

    Lo propio de la crema —familia, estado, liberación, disponible—, que no
    cambia entre preparar e iniciar: «Preparar» rechaza con el primero y el
    inicio los incluye en su lista. Las condiciones del TK (análisis, firmas,
    CIP, saldo en litros) no están aquí: cambian entre los dos pasos y son
    solo motivos de inicio.
    """
    from produccion.models import Lote

    if lote.producto.familia != "crema":
        return [(f"El lote {lote.codigo_lote} no es un lote de crema.", None)]
    if lote.estado == Lote.Estado.ANULADO:
        # El material de un lote anulado no se procesa (como en Secado).
        return [(MENSAJE_SALIDA_DE_LOTE_ANULADO.format(codigo=lote.codigo_lote), None)]
    if lote.estado not in {Lote.Estado.PRODUCIDO, Lote.Estado.CERRADO}:
        return [(f"El lote de crema {lote.codigo_lote} todavía no está producido.", None)]
    motivos = []
    if not Lote.objects.filter(pk=lote.pk).filter(filtro_crema_liberada()).exists():
        motivos.append((
            f"El lote de crema {lote.codigo_lote} todavía no está liberado por Calidad.",
            RESOLVER_CALIDAD,
        ))
    pedido = Decimal(str(kg))
    disponible = kg_crema_disponible(lote, excluir_corrida_id=excluir_corrida_id)
    if pedido > disponible:
        motivos.append((
            f"El lote de crema {lote.codigo_lote} tiene {disponible} kg disponibles; "
            f"la corrida pide {pedido} kg.",
            None,
        ))
    return motivos


def fuente_tk_de_crema(lote):
    """
    La salida del lote de crema que está en un TK, si la hay: de ahí sale la
    crema al iniciar (en litros, con la densidad de su liberación). El inicio
    y el puesto (`cremas[].tk`) leen la misma.
    """
    return (
        SalidaProceso.objects.select_related("silo", "liberacion_calidad__analisis_silo")
        .filter(lote=lote, silo__isnull=False)
        .order_by("registrada_en", "pk")
        .first()
    )


def litros_de_crema(kg, densidad):
    """Los litros del TK que corresponden a `kg` de crema con esta densidad (kg/m³)."""
    return (Decimal(str(kg)) * Decimal("1000") / Decimal(str(densidad))).quantize(Decimal("0.01"))
```

- [ ] **Step 5: «Preparar» toma la mantequera** — reemplaza `crear_mantequilla_guiada` completa por:

```python
@transaction.atomic
def crear_mantequilla_guiada(
    *, orden_id, lote_crema_id, equipo_id, codigo_lote_mantequilla,
    kg_crema, usuario, lote_suero_id=None,
):
    """
    Prepara una corrida de mantequilla: lote de salida, ejecución y corrida, y
    toma la mantequera (`borrador → preparacion`), en una sola transacción
    —todo o nada: ni lote, ni ejecución, ni corrida, ni máquina ocupada—.

    La crema se valida con las mismas reglas que el inicio
    (`motivos_crema_para_mantequilla`), pero no se mueve: entra a la
    mantequera al iniciar. Las condiciones del TK cambian entre preparar e
    iniciar y son motivos de inicio, con su enlace.
    """
    from inventario.servicios import motivo_equipo_no_habilitado
    from maestros.models import Equipo
    from produccion.models import Lote, OrdenProduccion

    orden = OrdenProduccion.objects.select_for_update(of=("self",)).select_related(
        "producto", "sucursal"
    ).get(pk=orden_id)
    crema = (
        Lote.objects.select_for_update(of=("self",)).select_related("producto")
        .get(pk=lote_crema_id)
    )
    equipo = Equipo.objects.select_for_update().get(pk=equipo_id)
    suero = (
        Lote.objects.select_for_update(of=("self",)).get(pk=lote_suero_id)
        if lote_suero_id else None
    )
    if orden.producto.categoria != "mantequilla":
        raise ValidationError({"orden": "La orden no corresponde a mantequilla."})
    if orden.estado not in {OrdenProduccion.Estado.PROGRAMADA, OrdenProduccion.Estado.EN_PROCESO}:
        raise ValidationError({"orden": "La orden no está programada o en proceso."})
    if not equipo.activo:
        raise ValidationError({"equipo": f"{equipo.nombre} no está activa."})
    if equipo.tipo not in tipos_equipo_para_etapa(EtapaProceso.Tipo.MANTEQUILLA):
        raise ValidationError({"equipo": f"{equipo.nombre} no es una mantequera."})
    # Hoy una mantequera en CIP se preparaba y el rechazo llegaba al iniciar.
    impedimento = motivo_equipo_no_habilitado(equipo)
    if impedimento:
        raise ValidationError({"equipo": impedimento})
    motivos = motivos_crema_para_mantequilla(crema, kg_crema)
    if motivos:
        raise ValidationError({"lote_crema": motivos[0][0]})
    if suero is not None and not sueros_libres(Lote.objects.filter(pk=suero.pk)).exists():
        raise ValidationError({
            "lote_suero": (
                f"El lote {suero.codigo_lote} no puede recibir el suero: ya lo tomó otra "
                "corrida, ya tiene kilos o no es un lote de suero."
            )
        })
    etapa = etapa_para_producto(
        producto=orden.producto, sucursal=orden.sucursal,
        tipo=EtapaProceso.Tipo.MANTEQUILLA,
    )
    if etapa is None:
        raise ValidationError({"orden": "El producto no tiene una etapa de mantequilla activa."})
    ruta = ruta_para_etapa(producto=orden.producto, sucursal=orden.sucursal, etapa=etapa)
    codigo = str(codigo_lote_mantequilla).strip()
    if not codigo:
        raise ValidationError({"codigo_lote_mantequilla": "Ingresa el código del lote de salida."})
    lote_salida = Lote(
        sucursal=orden.sucursal, codigo_lote=codigo,
        codigo_lote_propuesto=codigo, op=orden.codigo, orden=orden,
        producto=orden.producto, equipo=equipo, fecha=timezone.localdate(),
        estado=Lote.Estado.EN_PROCESO,
    )
    lote_salida.full_clean()
    lote_salida.save()
    ejecucion = EjecucionProceso(
        codigo=f"EJ-MANT-{lote_salida.pk}", etapa=etapa, ruta_producto=ruta,
        sucursal=orden.sucursal, equipo=equipo, responsable=usuario,
    )
    ejecucion.full_clean()
    ejecucion.save()
    lote_salida.ejecucion = ejecucion
    lote_salida.save(update_fields=["ejecucion"])
    corrida = CorridaMantequilla(
        ejecucion=ejecucion, orden=orden, lote_crema=crema,
        lote_mantequilla=lote_salida, lote_suero=suero,
        kg_crema=Decimal(str(kg_crema)),
    )
    corrida.full_clean()
    corrida.save()
    # Toma la mantequera: `adquirir_equipo` rechaza una ocupada, y la
    # excepción revierte todo lo de arriba.
    transicionar_ejecucion(
        ejecucion_id=ejecucion.pk, estado_nuevo=EjecucionProceso.Estado.PREPARACION,
        usuario=usuario, motivo="Preparación desde el puesto de Mantequilla.",
    )
    return CorridaMantequilla.objects.select_related(
        "ejecucion__etapa", "ejecucion__equipo", "orden",
        "lote_crema__producto", "lote_mantequilla__producto", "lote_suero",
    ).get(pk=corrida.pk)
```

- [ ] **Step 6: `preparar_continuacion` no prepara mantequilla** — en `preparar_continuacion`, justo después del `try/except` que carga `etapa`:

```python
    if etapa.tipo == EtapaProceso.Tipo.MANTEQUILLA:
        raise ValidationError(MENSAJE_MANTEQUILLA_EN_PUESTO)
```

- [ ] **Step 7: Una regla de inicio** — reemplaza `iniciar_mantequilla` completa por:

```python
def motivos_tipados_para_iniciar_mantequilla(corrida, *, ejecucion=None):
    """
    Lo que impide iniciar esta corrida de mantequilla, como pares `(motivo,
    resolver_en)`, en el orden en que el inicio lo comprueba. Lista vacía: se
    puede.

    Es la única implementación de esas reglas: `iniciar_mantequilla` lanza el
    primer motivo y el puesto los muestra junto a un botón deshabilitado,
    enlazando a donde se resuelve el primero. Un aseo observado **no** está
    aquí: avisa, no bloquea. El stock de envases tampoco: se descuenta al
    declarar el lote producido y no bloquea (`cerrar_lote_producido`).
    """
    from inventario.servicios import motivo_equipo_no_habilitado
    from produccion.models import OrdenProduccion
    from recepcion.servicios import motivos_silo_no_disponible, saldo_silo

    ejecucion = ejecucion or corrida.ejecucion
    if (
        corrida.estado != CorridaMantequilla.Estado.BORRADOR
        or ejecucion.estado != EjecucionProceso.Estado.PREPARACION
    ):
        # Lo demás no aplica a una corrida que no está preparada.
        return [(
            f"{ejecucion.codigo} no está preparada: está "
            f"{ejecucion.get_estado_display().lower()}.",
            None,
        )]
    motivos = []
    try:
        corrida.clean()
    except ValidationError as error:
        motivos.extend((mensaje, None) for mensaje in error.messages)
    orden = corrida.orden
    if orden.estado not in {OrdenProduccion.Estado.PROGRAMADA, OrdenProduccion.Estado.EN_PROCESO}:
        motivos.append((
            f"La orden {orden.codigo} está {orden.get_estado_display().lower()}: "
            "debe estar programada o en proceso.",
            RESOLVER_PLANIFICACION,
        ))
    if not ejecucion.equipo_id:
        motivos.append(("La corrida requiere una mantequera asignada.", None))
    else:
        impedimento = motivo_equipo_no_habilitado(ejecucion.equipo)
        if impedimento:
            motivos.append((impedimento, RESOLVER_CIP))
    motivos.extend(motivos_crema_para_mantequilla(
        corrida.lote_crema, corrida.kg_crema, excluir_corrida_id=corrida.pk,
    ))
    fuente = fuente_tk_de_crema(corrida.lote_crema)
    if fuente is not None:
        tk = fuente.silo
        liberacion = getattr(fuente, "liberacion_calidad", None)
        densidad = (
            liberacion.analisis_silo.densidad
            if liberacion is not None and liberacion.analisis_silo_id else None
        )
        if densidad is None or densidad <= 0:
            motivos.append((
                f"El análisis de la crema en {tk.codigo} no tiene una densidad válida.",
                RESOLVER_CALIDAD,
            ))
        del_tk = motivos_silo_no_disponible(tk, para="proceso")
        if del_tk:
            motivos.append((f"{tk.codigo}: " + " ".join(del_tk), RESOLVER_SILOS))
        if densidad is not None and densidad > 0:
            litros = litros_de_crema(corrida.kg_crema, densidad)
            if saldo_silo(tk) < litros:
                motivos.append((
                    f"{tk.codigo} no tiene los {litros} L equivalentes a la crema solicitada.",
                    None,
                ))
    return motivos


def motivos_para_iniciar_mantequilla(corrida, *, ejecucion=None):
    """Los textos de `motivos_tipados_para_iniciar_mantequilla`. Lista vacía: se puede."""
    return [
        motivo for motivo, _ in
        motivos_tipados_para_iniciar_mantequilla(corrida, ejecucion=ejecucion)
    ]


@transaction.atomic
def iniciar_mantequilla(*, corrida_id, usuario):
    """
    Pasa una corrida preparada a ejecución. Recalcula los motivos con la
    corrida, la ejecución, la crema y su TK bloqueados —entre que el puesto los
    mostró y el clic pudo entrar un CIP o perderse la liberación— y lanza el
    primero. Sin motivos, saca la crema del TK, registra la entrada y la
    mantequera pasa a `ejecucion`. Ya no pasa por `borrador → preparacion`:
    eso lo hizo «Preparar».
    """
    from inventario.servicios import advertencia_aseo_equipo
    from maestros.models import Silo
    from produccion.models import Lote, OrdenProduccion
    from recepcion.models import MovimientoSilo

    # Orden de candados de `bloquear_para_cancelar`: corrida, luego ejecución.
    corrida = CorridaMantequilla.objects.select_for_update(of=("self",)).select_related(
        "orden", "lote_crema__producto", "lote_mantequilla__producto",
    ).get(pk=corrida_id)
    ejecucion = (
        EjecucionProceso.objects.select_for_update(of=("self",))
        .select_related("etapa", "equipo").get(pk=corrida.ejecucion_id)
    )
    corrida.ejecucion = ejecucion
    # Dos inicios sobre la misma crema se serializan antes de contar su disponible.
    list(
        Lote.objects.select_for_update(of=("self",))
        .filter(pk=corrida.lote_crema_id).values_list("pk", flat=True)
    )
    fuente = fuente_tk_de_crema(corrida.lote_crema)
    tk = Silo.objects.select_for_update().get(pk=fuente.silo_id) if fuente is not None else None
    motivos = motivos_para_iniciar_mantequilla(corrida, ejecucion=ejecucion)
    if motivos:
        raise ValidationError(motivos[0])

    if tk is not None:
        MovimientoSilo.objects.create(
            silo=tk,
            tipo=MovimientoSilo.Tipo.SALIDA,
            litros=litros_de_crema(
                corrida.kg_crema, fuente.liberacion_calidad.analisis_silo.densidad,
            ),
            fecha_hora=timezone.now(),
            origen_tipo=MovimientoSilo.OrigenTipo.PRODUCCION,
            origen_id=corrida.pk,
            operacion_id=corrida.operacion_id,
            lote=corrida.lote_crema,
            producto=corrida.lote_crema.producto,
            equipo=ejecucion.equipo,
            usuario=usuario,
        )
    EntradaProceso.objects.create(
        ejecucion=ejecucion, lote=corrida.lote_crema,
        cantidad=corrida.kg_crema, unidad="kg",
    )
    aseo = advertencia_aseo_equipo(ejecucion.equipo)
    transicionar_ejecucion(
        ejecucion_id=ejecucion.pk, estado_nuevo=EjecucionProceso.Estado.EJECUCION,
        usuario=usuario,
        motivo=(
            f"Advertencia no bloqueante de aseo: {aseo}"
            if aseo else "Inicio desde el puesto de Mantequilla."
        ),
    )
    corrida.estado = CorridaMantequilla.Estado.EN_PROCESO
    corrida.iniciada_por = usuario
    corrida.iniciada_en = timezone.now()
    corrida.save(update_fields=["estado", "iniciada_por", "iniciada_en"])
    if corrida.orden.estado == OrdenProduccion.Estado.PROGRAMADA:
        corrida.orden.estado = OrdenProduccion.Estado.EN_PROCESO
        corrida.orden.save(update_fields=["estado"])
    return CorridaMantequilla.objects.select_related(
        "ejecucion__etapa", "ejecucion__equipo", "orden",
        "lote_crema__producto", "lote_mantequilla__producto", "lote_suero",
        "iniciada_por", "finalizada_por",
    ).get(pk=corrida.pk)
```

(`Exists`, `OuterRef`, `Q` y `Sum` ya se importan a nivel de módulo; `EntradaProceso` y `SalidaProceso` también.)

- [ ] **Step 8: Migrar `tests_mantequilla.py`** — la fixture nace como la deja «Preparar» y con la crema liberada (Desviación 13):
  - Imports: agrega `transicionar_ejecucion` a la importación de `.servicios`.
  - En `setUp`, después de crear `self.lote_crema`:

```python
        # La crema llega liberada por Calidad: el inicio lo exige para toda
        # crema, esté o no en un TK (`motivos_crema_para_mantequilla`).
        proceso_origen = Proceso.objects.create(codigo="origen-crema-mant", nombre="Origen crema")
        etapa_origen = EtapaProceso.objects.create(
            proceso=proceso_origen, codigo="descremar-mant", nombre="Descremación",
            tipo=EtapaProceso.Tipo.DESCREMACION, orden=1,
        )
        origen = EjecucionProceso.objects.create(
            codigo="EJ-ORIGEN-CREMA-1", etapa=etapa_origen, sucursal=planta,
            estado=EjecucionProceso.Estado.CERRADA,
        )
        LiberacionProceso.objects.create(
            salida=SalidaProceso.objects.create(
                ejecucion=origen, lote=self.lote_crema, producto=crema,
                cantidad=Decimal("1000"), unidad="kg",
            ),
            estado=LiberacionProceso.Estado.LIBERADO,
        )
```

  - Al final de `setUp`:

```python
        # Como la deja «Preparar»: la ejecución en `preparacion` con la
        # mantequera tomada. El inicio ya no prepara.
        transicionar_ejecucion(
            ejecucion_id=ejecucion.pk, estado_nuevo=EjecucionProceso.Estado.PREPARACION,
            usuario=self.usuario, motivo="Fixture preparada.",
        )
```

  - `test_alta_guiada_crea_lote_ejecucion_y_corrida_atomicos` → renómbrala y reescríbela:

```python
    def test_alta_guiada_prepara_lote_ejecucion_y_corrida_y_toma_la_mantequera(self):
        orden = self.corrida.orden
        # La de la fixture está tomada; y su corrida compromete los 1.000 kg.
        otra = Equipo.objects.create(
            sucursal=self.planta, codigo="mant-2", nombre="Mantequera 2",
            tipo=Equipo.Tipo.MANTEQUERA,
        )
        self.corrida.delete()

        corrida = crear_mantequilla_guiada(
            orden_id=orden.pk, lote_crema_id=self.lote_crema.pk,
            equipo_id=otra.pk, codigo_lote_mantequilla="MANT-GUIADA-1",
            kg_crema="400", usuario=self.usuario,
        )

        self.assertEqual(corrida.lote_mantequilla.codigo_lote, "MANT-GUIADA-1")
        self.assertEqual(corrida.ejecucion.etapa.tipo, EtapaProceso.Tipo.MANTEQUILLA)
        self.assertEqual(corrida.ejecucion.estado, EjecucionProceso.Estado.PREPARACION)
        self.assertEqual(corrida.ejecucion.codigo, f"EJ-MANT-{corrida.lote_mantequilla_id}")
        self.assertEqual(corrida.kg_crema, Decimal("400"))
```

  - Elimina `test_opciones_alta_muestran_op_crema_y_linea_validas`, `test_opciones_alta_informan_la_reserva_del_equipo`, `test_opciones_alta_separa_crema_pendiente_de_calidad` y `test_una_preparacion_cancelada_no_resta_la_crema_ofrecida`: sus casos pasan a `PuestoMantequillaTests` (Task 5) y `opciones-alta/` se elimina en la Task 7. `_preparacion_cancelada_que_tomo_la_crema` y `test_una_preparacion_cancelada_no_consume_la_crema_al_iniciar` se quedan.

- [ ] **Step 9: El comando usa la misma regla de suero** — en `preparar_circuito_mantequilla.py`, importa `from procesos.servicios import sueros_libres` y reemplaza la consulta de `lote_suero` por:

```python
        lote_suero = sueros_libres(Lote.objects.filter(producto=mazada)).order_by("pk").first()
```

- [ ] **Step 10: Verificar**

Run: `cd backend && DJANGO_ENV=test ./.venv/Scripts/python.exe manage.py test procesos.tests_puesto_mantequilla procesos.tests_mantequilla produccion.tests_preparar_mantequilla --noinput`
Expected: OK.

Run: `cd backend && DJANGO_ENV=test ./.venv/Scripts/python.exe manage.py test procesos --noinput`
Expected: OK.

- [ ] **Step 11: Commit**

```bash
git add backend/procesos/servicios.py backend/procesos/tests_puesto_mantequilla.py backend/procesos/tests_mantequilla.py backend/produccion/management/commands/preparar_circuito_mantequilla.py
git commit -m "feat(procesos): preparar mantequilla toma la mantequera y valida la crema con las reglas del inicio, que son una sola"
```

---

### Task 4: Un solo camino de inicio y «Cancelar preparación»

**Files:**
- Modify: `backend/procesos/servicios.py` (constantes ~95-106; `bloquear_para_cancelar` ~1143; gancho en `transicionar_ejecucion` ~1258; `_deshacer_preparacion_mantequilla` y `cancelar_preparacion_mantequilla` junto a `cancelar_preparacion_descremacion` ~3323; docstring de `inicio_reservado_al_puesto` ~3352)
- Modify: `backend/procesos/views.py` (imports; `CorridaMantequillaViewSet.cancelar_preparacion`)
- Modify: `backend/procesos/tests_puesto_mantequilla.py`

**Interfaces:**
- Consumes: `BasePuestoMantequilla`, `crear_mantequilla_guiada`, `iniciar_mantequilla` (Task 3); `CorridaMantequilla.Estado.ANULADA`, `motivo_anulacion` (Task 1).
- Produces (`procesos/servicios.py`):
  - `MENSAJE_INICIO_MANTEQUILLA_EN_PUESTO = "Las corridas de mantequilla se inician desde el puesto de Mantequilla."`; `MENSAJES_INICIO_EN_PUESTO` gana `EtapaProceso.Tipo.MANTEQUILLA`.
  - `cancelar_preparacion_mantequilla(*, corrida_id, usuario, motivo) -> EjecucionProceso`
  - `_deshacer_preparacion_mantequilla(ejecucion, motivo, usuario) -> None` (privada; la llama `transicionar_ejecucion`)
- `POST /api/procesos/mantequillas/{id}/cancelar-preparacion/` `{"motivo": "…"}` → 200 `{"ejecucion_id", "ejecucion_codigo", "estado": "cancelada"}`; 400 `{"code", "message", "details"}` (`respuesta_error_dominio`); 403 sin la etapa.
- `POST /api/procesos/ejecuciones/{id}/transicionar/ {"estado": "ejecucion"}` sobre una Mantequilla en `preparacion` → 400 con «Las corridas de mantequilla se inician desde el puesto de Mantequilla.». Pausar, bloquear, reanudar y cancelar siguen por ahí.

- [ ] **Step 1: Pruebas que fallan** — en `tests_puesto_mantequilla.py` agrega a la importación de `.servicios`: `MENSAJE_INICIO_MANTEQUILLA_EN_PUESTO, MENSAJE_MOTIVO_CANCELACION, transicionar_ejecucion`, y al final:

```python
class InicioGenericoCerradoMantequillaTests(BasePuestoMantequilla):
    def transicionar(self, ejecucion, estado, motivo=""):
        ejecucion.refresh_from_db()
        return self.cliente().post(
            f"/api/procesos/ejecuciones/{ejecucion.pk}/transicionar/",
            {"estado": estado, "version": ejecucion.version, "motivo": motivo},
            format="json",
        )

    def test_transicionar_no_inicia_una_preparada(self):
        corrida = self.preparada()

        respuesta = self.transicionar(corrida.ejecucion, "ejecucion")

        self.assertEqual(respuesta.status_code, 400, respuesta.data)
        self.assertEqual(respuesta.data["message"], MENSAJE_INICIO_MANTEQUILLA_EN_PUESTO)
        corrida.ejecucion.refresh_from_db()
        self.assertEqual(corrida.ejecucion.estado, EjecucionProceso.Estado.PREPARACION)

    def test_pausar_y_reanudar_siguen_por_transicionar(self):
        corrida = self.en_curso()

        pausa = self.transicionar(corrida.ejecucion, "pausada")
        reanudar = self.transicionar(corrida.ejecucion, "ejecucion")

        self.assertEqual(pausa.status_code, 200, pausa.data)
        self.assertEqual(reanudar.status_code, 200, reanudar.data)

    def test_la_bandeja_no_ofrece_iniciar_una_preparada(self):
        corrida = self.preparada()

        bandeja = self.cliente().get("/api/procesos/ejecuciones/operativas/")

        fila = next(item for item in bandeja.data if item["id"] == corrida.ejecucion_id)
        self.assertNotIn("ejecucion", fila["acciones_permitidas"])
        self.assertIn("cancelada", fila["acciones_permitidas"])

    def test_el_alta_directa_de_corridas_sigue_cerrada(self):
        self.assertEqual(
            self.cliente().post("/api/procesos/mantequillas/", {}, format="json").status_code, 405,
        )


class CancelarPreparacionMantequillaTests(BasePuestoMantequilla):
    def cancelar(self, corrida, motivo="Crema equivocada", usuario=None):
        return self.cliente(usuario).post(
            f"/api/procesos/mantequillas/{corrida.pk}/cancelar-preparacion/",
            {"motivo": motivo}, format="json",
        )

    def test_cancelar_anula_corrida_y_lote_y_suelta_la_mantequera(self):
        corrida = self.preparada(lote_suero=self.suero.pk)

        respuesta = self.cancelar(corrida)

        self.assertEqual(respuesta.status_code, 200, respuesta.data)
        self.assertEqual(respuesta.data, {
            "ejecucion_id": corrida.ejecucion_id,
            "ejecucion_codigo": corrida.ejecucion.codigo,
            "estado": EjecucionProceso.Estado.CANCELADA,
        })
        corrida = self.recargar(corrida.pk)
        self.assertEqual(corrida.estado, CorridaMantequilla.Estado.ANULADA)
        self.assertEqual(corrida.motivo_anulacion, "Crema equivocada.")
        self.assertEqual(corrida.lote_mantequilla.estado, Lote.Estado.ANULADO)
        self.assertIn(
            "[ANULACIÓN] Preparación de Mantequilla cancelada: Crema equivocada.",
            corrida.lote_mantequilla.observacion,
        )
        # El suero conserva el rastro en la corrida anulada, pero queda libre:
        # la misma mantequera, la misma crema y el mismo suero se preparan otra vez.
        self.assertEqual(corrida.lote_suero, self.suero)
        self.preparada(lote_suero=self.suero.pk)

    def test_sin_motivo_no_cancela(self):
        corrida = self.preparada()

        respuesta = self.cancelar(corrida, motivo="  ")

        self.assertEqual(respuesta.status_code, 400, respuesta.data)
        self.assertEqual(respuesta.data["message"], MENSAJE_MOTIVO_CANCELACION)
        corrida.ejecucion.refresh_from_db()
        self.assertEqual(corrida.ejecucion.estado, EjecucionProceso.Estado.PREPARACION)

    def test_una_corrida_en_curso_no_se_cancela_desde_el_puesto(self):
        corrida = self.en_curso()

        respuesta = self.cancelar(corrida)

        self.assertEqual(respuesta.status_code, 400, respuesta.data)
        self.assertIn("se cierra registrando su balance", respuesta.data["message"])

    def test_cancelar_desde_la_bandeja_generica_deja_lo_mismo(self):
        corrida = self.preparada()

        transicionar_ejecucion(
            ejecucion_id=corrida.ejecucion_id, estado_nuevo=EjecucionProceso.Estado.CANCELADA,
            usuario=self.condensador, motivo="Desde la bandeja",
        )

        corrida = self.recargar(corrida.pk)
        self.assertEqual(corrida.estado, CorridaMantequilla.Estado.ANULADA)
        self.assertEqual(corrida.motivo_anulacion, "Desde la bandeja.")
        self.assertEqual(corrida.lote_mantequilla.estado, Lote.Estado.ANULADO)
        self.preparada()

    def test_una_corrida_en_curso_cancelada_por_la_bandeja_queda_anulada(self):
        corrida = self.en_curso()

        transicionar_ejecucion(
            ejecucion_id=corrida.ejecucion_id, estado_nuevo=EjecucionProceso.Estado.CANCELADA,
            usuario=self.condensador, motivo="Falla eléctrica",
        )

        corrida = self.recargar(corrida.pk)
        self.assertEqual(corrida.estado, CorridaMantequilla.Estado.ANULADA)
        self.assertEqual(corrida.lote_mantequilla.estado, Lote.Estado.ANULADO)
        self.assertIn("Corrida de Mantequilla cancelada", corrida.lote_mantequilla.observacion)

    def test_anular_el_lote_por_el_patch_deja_lo_mismo_y_marca_una_vez(self):
        corrida = self.preparada()

        respuesta = self.cliente().patch(
            f"/api/produccion/lotes/{corrida.lote_mantequilla_id}/",
            {"estado": "anulado", "motivo_anulacion": "Lote abierto por error"}, format="json",
        )

        self.assertEqual(respuesta.status_code, 200, respuesta.data)
        corrida = self.recargar(corrida.pk)
        self.assertEqual(corrida.estado, CorridaMantequilla.Estado.ANULADA)
        self.assertEqual(corrida.ejecucion.estado, EjecucionProceso.Estado.CANCELADA)
        self.assertEqual(corrida.lote_mantequilla.estado, Lote.Estado.ANULADO)
        self.assertEqual(corrida.lote_mantequilla.observacion.count("[ANULACIÓN]"), 1)

    def test_una_preparacion_heredada_en_borrador_se_cancela(self):
        corrida = self.corrida_heredada()

        respuesta = self.cancelar(corrida)

        self.assertEqual(respuesta.status_code, 200, respuesta.data)
        corrida = self.recargar(corrida.pk)
        self.assertEqual(corrida.estado, CorridaMantequilla.Estado.ANULADA)
        self.assertEqual(corrida.lote_mantequilla.estado, Lote.Estado.ANULADO)


class PermisosMantequillaTests(BasePuestoMantequilla):
    """Secado escribe lotes, pero no opera la etapa Mantequilla: 403 en cada acción, nada escrito."""

    def test_secado_no_prepara_inicia_cancela_revisa_ni_cierra(self):
        preparada = self.preparada()
        en_curso = self.en_curso(equipo=self.otra_mantequera.pk)
        secado = self.cliente(self.secador)
        cierre = {"kg_mantequilla": "31", "kg_suero": "28", "kg_merma": "1"}

        self.assertEqual(self.preparar(usuario=self.secador).status_code, 403)
        for ruta, cuerpo in (
            (f"/api/procesos/mantequillas/{preparada.pk}/iniciar/", {}),
            (f"/api/procesos/mantequillas/{preparada.pk}/cancelar-preparacion/", {"motivo": "No"}),
            (f"/api/procesos/mantequillas/{en_curso.pk}/revisar-cierre/", cierre),
            (f"/api/procesos/mantequillas/{en_curso.pk}/cerrar/", cierre),
        ):
            with self.subTest(ruta=ruta):
                self.assertEqual(secado.post(ruta, cuerpo, format="json").status_code, 403)

        self.assertEqual(self.recargar(preparada.pk).ejecucion.estado, EjecucionProceso.Estado.PREPARACION)
        self.assertEqual(self.recargar(en_curso.pk).estado, CorridaMantequilla.Estado.EN_PROCESO)
        self.assertEqual(Lote.objects.filter(producto=self.producto_mantequilla).count(), 2)
```

- [ ] **Step 2: Verificar que fallan**

Run: `cd backend && DJANGO_ENV=test ./.venv/Scripts/python.exe manage.py test procesos.tests_puesto_mantequilla --noinput`
Expected: ERROR `ImportError: cannot import name 'MENSAJE_INICIO_MANTEQUILLA_EN_PUESTO'`.

- [ ] **Step 3: El inicio es del puesto** — en `procesos/servicios.py`, debajo de `MENSAJE_INICIO_DESCREMADO_EN_PUESTO`:

```python
MENSAJE_INICIO_MANTEQUILLA_EN_PUESTO = (
    "Las corridas de mantequilla se inician desde el puesto de Mantequilla."
)
```

y en `MENSAJES_INICIO_EN_PUESTO` agrega `EtapaProceso.Tipo.MANTEQUILLA: MENSAJE_INICIO_MANTEQUILLA_EN_PUESTO,`. En el docstring de `inicio_reservado_al_puesto`, «Secado y Descremación» → «Secado, Descremación y Mantequilla». La vista `transicionar` ya responde con `MENSAJES_INICIO_EN_PUESTO[actual.etapa.tipo]` y `operativas` ya filtra con `inicio_reservado_al_puesto`: sin cambio.

- [ ] **Step 4: Cancelar deshace lo propio de Mantequilla** — en `bloquear_para_cancelar` la tupla pasa a `(CorridaSecado, CorridaCondensacion, CorridaDescremacion, CorridaMantequilla)`, y en su docstring agrega «`iniciar_mantequilla`/`cancelar_preparacion_mantequilla`» a la lista de pares con el mismo orden. En `transicionar_ejecucion`, después del bloque de Descremación:

```python
    if (
        estado_nuevo == EjecucionProceso.Estado.CANCELADA
        and ejecucion.etapa.tipo == EtapaProceso.Tipo.MANTEQUILLA
    ):
        # Por el puesto, por la bandeja genérica o al anular el lote,
        # cancelar deja lo mismo.
        _deshacer_preparacion_mantequilla(ejecucion, motivo, usuario)
```

Junto a `cancelar_preparacion_descremacion`:

```python
def _deshacer_preparacion_mantequilla(ejecucion, motivo, usuario):
    """
    Lo propio de Mantequilla al cancelar su ejecución: la corrida queda
    `anulada` con el motivo y el lote de salida se anula con `anular_lote`, la
    misma anulación que el `PATCH`. La mantequera queda libre al salir de
    `ESTADOS_QUE_OCUPAN_EQUIPO`.

    No hay crema que devolver desde una preparación: no se movió, entra al
    iniciar. Desde una corrida en curso, lo que entró a la mantequera no
    vuelve, como en Evaporación; y su lote también se anula, porque un lote
    `en_proceso` sobre una ejecución cancelada no lo cierra nadie. El suero no
    se desvincula —la corrida anulada conserva el rastro—, pero
    `sueros_libres` ignora las anuladas.

    Si se llegó aquí desde el `PATCH`, el lote ya viene anulado y
    `anular_lote` lo deja como está; la ejecución ya está cancelada, así que
    tampoco la vuelve a cancelar (`ejecucion_cancelable`).
    """
    from produccion.models import Lote
    from produccion.servicios import anular_lote

    corrida = (
        CorridaMantequilla.objects.select_for_update(of=("self",))
        .filter(ejecucion=ejecucion).first()
    )
    if corrida is None or corrida.estado not in {
        CorridaMantequilla.Estado.BORRADOR, CorridaMantequilla.Estado.EN_PROCESO,
    }:
        return
    origen = (
        "Preparación de Mantequilla cancelada"
        if corrida.estado == CorridaMantequilla.Estado.BORRADOR
        else "Corrida de Mantequilla cancelada"
    )
    corrida.estado = CorridaMantequilla.Estado.ANULADA
    corrida.motivo_anulacion = _con_punto(motivo)[:250]
    corrida.save(update_fields=["estado", "motivo_anulacion"])
    anular_lote(
        lote=Lote.objects.get(pk=corrida.lote_mantequilla_id),
        motivo=f"{origen}: {_con_punto(motivo)}",
        usuario=usuario,
    )


@transaction.atomic
def cancelar_preparacion_mantequilla(*, corrida_id, usuario, motivo):
    """
    Suelta una mantequera preparada sin iniciarla: la corrida y su lote de
    salida quedan anulados. Acepta la ejecución en `preparacion` y también en
    `borrador` (corridas heredadas del modal anterior, que nunca tomaron la
    máquina). Una corrida iniciada se cierra registrando su balance. Simétrica
    a `cancelar_preparacion_descremacion`; lo que se deshace lo hace la
    transición genérica.
    """
    motivo = (motivo or "").strip()
    if not motivo:
        raise ValidationError(MENSAJE_MOTIVO_CANCELACION)
    corrida = CorridaMantequilla.objects.select_for_update(of=("self",)).get(pk=corrida_id)
    ejecucion = (
        EjecucionProceso.objects.select_for_update(of=("self",)).get(pk=corrida.ejecucion_id)
    )
    if corrida.estado != CorridaMantequilla.Estado.BORRADOR or ejecucion.estado not in {
        EjecucionProceso.Estado.BORRADOR, EjecucionProceso.Estado.PREPARACION,
    }:
        raise ValidationError(
            f"Solo se cancela una mantequera preparada: {ejecucion.codigo} está "
            f"{ejecucion.get_estado_display().lower()}. Una corrida iniciada se cierra "
            "registrando su balance."
        )
    return transicionar_ejecucion(
        ejecucion_id=ejecucion.pk, estado_nuevo=EjecucionProceso.Estado.CANCELADA,
        usuario=usuario, motivo=motivo,
    )
```

- [ ] **Step 5: Vista** — en `backend/procesos/views.py` importa `cancelar_preparacion_mantequilla`; en `CorridaMantequillaViewSet`, junto a `iniciar`:

```python
    @action(detail=True, methods=["post"], url_path="cancelar-preparacion")
    def cancelar_preparacion(self, request, pk=None):
        """Suelta una mantequera preparada: corrida y lote de salida anulados."""
        try:
            ejecucion = cancelar_preparacion_mantequilla(
                corrida_id=self.get_object().pk, usuario=request.user,
                motivo=str(request.data.get("motivo") or ""),
            )
        except DjangoValidationError as error:
            return respuesta_error_dominio(error)
        return Response({
            "ejecucion_id": ejecucion.pk,
            "ejecucion_codigo": ejecucion.codigo,
            "estado": ejecucion.estado,
        })
```

- [ ] **Step 6: Verificar**

Run: `cd backend && DJANGO_ENV=test ./.venv/Scripts/python.exe manage.py test procesos.tests_puesto_mantequilla procesos.tests_mantequilla --noinput`
Expected: OK.

Run: `cd backend && DJANGO_ENV=test ./.venv/Scripts/python.exe manage.py test procesos produccion --noinput`
Expected: OK (`tests_puesto_secado`, `tests_puesto_descremado` y `tests_cancelar_evaporacion` siguen recibiendo sus mensajes y sus anulaciones).

- [ ] **Step 7: Commit**

```bash
git add backend/procesos/servicios.py backend/procesos/views.py backend/procesos/tests_puesto_mantequilla.py
git commit -m "feat(procesos): la mantequilla se inicia solo en su puesto y una preparación se cancela con motivo"
```

---

### Task 5: Estado del puesto, situaciones e historial con filtros de servidor

**Files:**
- Modify: `backend/procesos/dominio.py` (situaciones, ~110-136)
- Modify: `backend/procesos/servicios.py` (`condicion_situacion`, `catalogo_situaciones` en lugar de las de Descremación ~2365-2395; `estado_puesto_descremado` ~2613; `estado_puesto_mantequilla` nueva, después de `iniciar_mantequilla`)
- Modify: `backend/procesos/serializers.py` (`CorridaMantequillaSerializer`, ~308)
- Modify: `backend/procesos/views.py` (imports; `CorridaDescremacionViewSet.condicion_estado` ~339; `CorridaMantequillaViewSet`: mixins, filtros, `puesto`)
- Modify: `backend/procesos/tests_puesto_mantequilla.py`

**Interfaces:**
- Consumes: `motivos_tipados_para_iniciar_mantequilla`, `kg_crema_disponible`, `filtro_crema_liberada`, `sueros_libres`, `fuente_tk_de_crema`, `RESOLVER_CIP` (Task 3); `BasePuestoMantequilla`.
- Produces (`procesos/dominio.py`): `SITUACIONES_MANTEQUILLA`; `situacion_de(tabla, estado, estado_ejecucion) -> tuple[str, str]`; `situacion_mantequilla(estado, estado_ejecucion)`; `situacion_descremacion` se conserva (envoltorio).
- Produces (`procesos/servicios.py`): `condicion_situacion(tabla, situacion) -> Q`; `catalogo_situaciones(tabla) -> list[dict]`; `estado_puesto_mantequilla(usuario) -> dict`. Se eliminan `condicion_situacion_descremacion` y `catalogo_situaciones_descremacion`.
- `GET /api/procesos/mantequillas/puesto/` → el JSON de las Global Constraints. Ejemplo de una mantequera preparada:

```json
{
  "equipo_id": 15, "codigo": "mant-pm1", "nombre": "Mantequera PM 1", "tipo": "mantequera",
  "estado": "preparada",
  "corrida": { "id": 9, "estado": "borrador", "ejecucion_id": 140, "ejecucion_codigo": "EJ-MANT-311",
               "ejecucion_estado": "preparacion", "orden_codigo": "OP-PM-1", "producto": "Mantequilla PM",
               "lote_mantequilla": "MANT-PM-1", "lote_crema": "CR-PM-1", "kg_crema": "60.000",
               "lote_suero": null, "iniciada_en": null },
  "motivos_para_tomar": [], "motivos_para_iniciar": [], "resolver_en": null,
  "avisos": [], "en_calidad": null
}
```

- `GET /api/procesos/mantequillas/?q=&estado=&desde=&hasta=&page=` filtra en el servidor (`q`: código de ejecución, lote de salida, lote de crema u OP; `estado`: situación de `SITUACIONES_MANTEQUILLA`; fechas sobre `ejecucion__creada_en`). Cada fila trae `ejecucion_estado`, `situacion` y `situacion_etiqueta`.

- [ ] **Step 1: Pruebas que fallan** — al final de `tests_puesto_mantequilla.py` (importa además `from .dominio import SITUACIONES_MANTEQUILLA, situacion_mantequilla`):

```python
class SituacionesMantequillaTests(TestCase):
    def test_cada_corrida_tiene_una_situacion_y_gana_la_primera(self):
        casos = {
            ("borrador", "preparacion"): "preparada",
            ("en_proceso", "ejecucion"): "en_curso",
            ("en_proceso", "pausada"): "en_curso",
            ("pendiente_calidad", "pendiente_control"): "esperando_calidad",
            ("cerrada", "cerrada"): "terminada",
            ("anulada", "cancelada"): "anulada",
            # Heredada del modal anterior, o huérfana: no es «Preparada».
            ("borrador", "borrador"): "borrador",
            ("borrador", "cancelada"): "borrador",
        }
        for (estado, ejecucion), esperada in casos.items():
            with self.subTest(estado=estado, ejecucion=ejecucion):
                self.assertEqual(situacion_mantequilla(estado, ejecucion)[0], esperada)

    def test_el_catalogo_es_la_tabla(self):
        self.assertEqual(
            [fila[0] for fila in SITUACIONES_MANTEQUILLA],
            ["preparada", "en_curso", "esperando_calidad", "terminada", "anulada", "borrador"],
        )


class PuestoMantequillaTests(BasePuestoMantequilla):
    def puesto(self, usuario=None):
        respuesta = self.cliente(usuario).get("/api/procesos/mantequillas/puesto/")
        self.assertEqual(respuesta.status_code, 200, respuesta.data)
        return respuesta.data

    def fila(self, datos, equipo):
        return next(item for item in datos["mantequeras"] if item["equipo_id"] == equipo.pk)

    def por_id(self, filas, *objetos):
        propios = {objeto.pk for objeto in objetos}
        return {fila["id"]: fila for fila in filas if fila["id"] in propios}

    def cerrar(self, corrida):
        # Sin lote de suero en la corrida: todo lo que no es mantequilla es merma.
        respuesta = self.cliente().post(
            f"/api/procesos/mantequillas/{corrida.pk}/cerrar/",
            {"kg_mantequilla": "59", "kg_merma": "1"}, format="json",
        )
        self.assertEqual(respuesta.status_code, 200, respuesta.data)

    def test_una_mantequera_sin_ejecucion_esta_disponible(self):
        fila = self.fila(self.puesto(), self.mantequera)

        self.assertEqual(fila["estado"], "disponible")
        self.assertEqual(fila["tipo"], "mantequera")
        self.assertIsNone(fila["corrida"])
        self.assertEqual(fila["motivos_para_tomar"], [])
        self.assertIsNone(fila["en_calidad"])

    def test_una_preparada_trae_su_corrida_y_puede_iniciarse(self):
        corrida = self.preparada(lote_suero=self.suero.pk)

        fila = self.fila(self.puesto(), self.mantequera)

        self.assertEqual(fila["estado"], "preparada")
        self.assertEqual(fila["corrida"], {
            "id": corrida.pk, "estado": "borrador",
            "ejecucion_id": corrida.ejecucion_id, "ejecucion_codigo": corrida.ejecucion.codigo,
            "ejecucion_estado": "preparacion", "orden_codigo": "OP-PM-1",
            "producto": "Mantequilla PM", "lote_mantequilla": corrida.lote_mantequilla.codigo_lote,
            "lote_crema": "CR-PM-1", "kg_crema": "60.000", "lote_suero": "MAZ-PM-1",
            "iniciada_en": None,
        })
        self.assertEqual(fila["motivos_para_iniciar"], [])
        self.assertIsNone(fila["resolver_en"])

    def test_los_motivos_dicen_donde_se_resuelven(self):
        crema, _tk = self.crema_en_tk("CR-PM-FIRMA", segunda_firma=False)
        self.preparada(lote_crema=crema.pk, kg_crema="200")
        self.preparada(equipo=self.otra_mantequera.pk)
        self.cip(self.otra_mantequera)

        datos = self.puesto()

        sin_firma = self.fila(datos, self.mantequera)
        self.assertIn("firma de realización y visualización", sin_firma["motivos_para_iniciar"][0])
        self.assertEqual(sin_firma["resolver_en"], "/silos")
        en_cip = self.fila(datos, self.otra_mantequera)
        self.assertIn("CIP", en_cip["motivos_para_iniciar"][0])
        self.assertEqual(en_cip["resolver_en"], "/calidad/inocuidad")

    def test_una_crema_sin_liberar_y_una_orden_cancelada_dicen_donde(self):
        self.preparada()
        LiberacionProceso.objects.filter(salida__lote=self.crema).update(
            estado=LiberacionProceso.Estado.PENDIENTE,
        )
        self.assertEqual(self.fila(self.puesto(), self.mantequera)["resolver_en"], "/calidad")

        OrdenProduccion.objects.filter(pk=self.orden.pk).update(
            estado=OrdenProduccion.Estado.CANCELADA,
        )
        fila = self.fila(self.puesto(), self.mantequera)
        # La orden se comprueba antes que la crema: es el primer motivo.
        self.assertIn("OP-PM-1", fila["motivos_para_iniciar"][0])
        self.assertEqual(fila["resolver_en"], "/planificacion")

    def test_una_mantequera_en_cip_no_se_toma(self):
        self.cip(self.mantequera)

        fila = self.fila(self.puesto(), self.mantequera)

        self.assertEqual(fila["estado"], "disponible")
        self.assertIn("CIP", fila["motivos_para_tomar"][0])
        self.assertEqual(fila["resolver_en"], "/calidad/inocuidad")

    def test_un_aseo_observado_es_aviso_no_motivo(self):
        self.preparada()
        self.cip(self.mantequera, estado=CicloCIP.Estado.OBSERVADO, horas=3)

        fila = self.fila(self.puesto(), self.mantequera)

        self.assertEqual(fila["motivos_para_iniciar"], [])
        self.assertTrue(fila["avisos"])

    def test_ejecucion_en_curso_pausada_o_bloqueada_esta_en_curso(self):
        # «En curso manda sobre preparada» no se puede sembrar: la base impide
        # dos ocupaciones del mismo equipo (Desviación 11).
        corrida = self.en_curso()
        for estado in ("ejecucion", "pausada", "bloqueada"):
            EjecucionProceso.objects.filter(pk=corrida.ejecucion_id).update(estado=estado)
            with self.subTest(estado=estado):
                fila = self.fila(self.puesto(), self.mantequera)
                self.assertEqual(fila["estado"], "en_curso")
                self.assertEqual(fila["corrida"]["ejecucion_estado"], estado)
                self.assertEqual(fila["motivos_para_iniciar"], [])

    def test_un_huerfano_con_ejecucion_terminada_no_ocupa(self):
        corrida = self.preparada()
        EjecucionProceso.objects.filter(pk=corrida.ejecucion_id).update(
            estado=EjecucionProceso.Estado.CANCELADA,
        )

        datos = self.puesto()

        self.assertEqual(self.fila(datos, self.mantequera)["estado"], "disponible")
        self.assertEqual(self.por_id(datos["corridas_de_hoy"], corrida), {})

    def test_en_calidad_la_mantequera_queda_libre_y_lo_informa(self):
        corrida = self.en_curso()
        self.cerrar(corrida)

        fila = self.fila(self.puesto(), self.mantequera)

        self.assertEqual(fila["estado"], "disponible")
        self.assertEqual(fila["en_calidad"], {
            "id": corrida.pk, "ejecucion_codigo": corrida.ejecucion.codigo,
            "lote_mantequilla": corrida.lote_mantequilla.codigo_lote,
        })

    def test_una_linea_ocupada_por_mantequilla_aparece_y_una_ajena_no(self):
        linea = Equipo.objects.create(
            sucursal=self.planta, codigo="linea-pm-vieja", nombre="Línea vieja", tipo=Equipo.Tipo.LINEA,
        )
        ajena = Equipo.objects.create(
            sucursal=self.planta, codigo="linea-pm-ajena", nombre="Línea ajena", tipo=Equipo.Tipo.LINEA,
        )
        ejecucion = EjecucionProceso.objects.create(
            codigo="EJ-MANT-VIEJA", etapa=self.etapa, sucursal=self.planta, equipo=linea,
            responsable=self.condensador, estado=EjecucionProceso.Estado.PREPARACION,
        )

        datos = self.puesto()

        fila = self.fila(datos, linea)
        self.assertEqual(fila["tipo"], "linea")
        self.assertEqual(fila["estado"], "preparada")
        self.assertIn(f"{ejecucion.codigo} no tiene corrida de mantequilla", fila["motivos_para_iniciar"][0])
        self.assertNotIn(ajena.pk, [item["equipo_id"] for item in datos["mantequeras"]])

    def test_cremas_restan_las_otras_preparadas_y_no_ofrecen_la_agotada(self):
        self.preparada(kg_crema="600")
        crema = self.por_id(self.puesto()["cremas"], self.crema)[self.crema.pk]
        self.assertEqual(crema["disponible_kg"], "400.000")
        self.assertIsNone(crema["tk"])

        self.preparada(equipo=self.otra_mantequera.pk, kg_crema="400")

        self.assertEqual(self.por_id(self.puesto()["cremas"], self.crema), {})

    def test_cremas_traen_su_tk(self):
        crema, tk = self.crema_en_tk("CR-PM-TK")

        fila = self.por_id(self.puesto()["cremas"], crema)[crema.pk]

        self.assertEqual(fila["tk"], tk.codigo)

    def test_cremas_pendientes_de_calidad_explican_por_que_no_aparecen(self):
        pendiente = self.lote_crema("CR-PM-PEND", liberacion=LiberacionProceso.Estado.PENDIENTE)
        sin_decision = self.lote_crema("CR-PM-SIN", liberacion=None)

        datos = self.puesto()

        self.assertEqual(self.por_id(datos["cremas"], pendiente, sin_decision), {})
        explicadas = self.por_id(datos["cremas_pendientes_calidad"], pendiente, sin_decision)
        self.assertEqual(explicadas[pendiente.pk]["estado_calidad"], "pendiente")
        self.assertEqual(explicadas[sin_decision.pk]["estado_calidad"], "trazabilidad_incompleta")
        self.assertEqual(explicadas[pendiente.pk]["etapa_origen"], "Descremación")

    def test_sueros_ofrecen_de_nuevo_el_de_una_corrida_anulada(self):
        corrida = self.preparada(lote_suero=self.suero.pk)
        self.assertEqual(self.por_id(self.puesto()["sueros"], self.suero), {})

        self.cliente().post(
            f"/api/procesos/mantequillas/{corrida.pk}/cancelar-preparacion/",
            {"motivo": "Suero equivocado"}, format="json",
        )

        self.assertIn(self.suero.pk, self.por_id(self.puesto()["sueros"], self.suero))

    def test_ordenes_programadas_o_en_proceso(self):
        cancelada = OrdenProduccion.objects.create(
            sucursal=self.planta, codigo="OP-PM-CAN", producto=self.producto_mantequilla,
            cantidad_planificada=10, unidad="kg", estado=OrdenProduccion.Estado.CANCELADA,
        )

        ordenes = self.por_id(self.puesto()["ordenes"], self.orden, cancelada)

        self.assertEqual(list(ordenes), [self.orden.pk])

    def test_corridas_de_hoy_sin_huerfanos_y_con_su_situacion(self):
        en_curso = self.en_curso()
        huerfana = self.preparada(equipo=self.otra_mantequera.pk)
        EjecucionProceso.objects.filter(pk=huerfana.ejecucion_id).update(
            estado=EjecucionProceso.Estado.CANCELADA,
        )

        propias = self.por_id(self.puesto()["corridas_de_hoy"], en_curso, huerfana)

        self.assertEqual(list(propias), [en_curso.pk])
        self.assertEqual(propias[en_curso.pk]["situacion"], "en_curso")
        self.assertEqual(propias[en_curso.pk]["situacion_etiqueta"], "En la mantequera")
        self.assertEqual(propias[en_curso.pk]["lote_crema"], "CR-PM-1")

    def test_calidad_lee_el_puesto(self):
        datos = self.puesto(self.calidad)

        self.assertIn("mantequeras", datos)
        self.assertEqual(
            [estado["valor"] for estado in datos["estados"]],
            [fila[0] for fila in SITUACIONES_MANTEQUILLA],
        )

    def test_el_historial_filtra_en_el_servidor(self):
        primera = self.en_curso()
        segunda = self.preparada(equipo=self.otra_mantequera.pk)
        url = "/api/procesos/mantequillas/"

        por_lote = self.cliente().get(url, {"q": segunda.lote_mantequilla.codigo_lote})
        en_curso = self.cliente().get(url, {"estado": "en_curso"})
        preparadas = self.cliente().get(url, {"estado": "preparada"})
        manana = (timezone.localdate() + timedelta(days=1)).isoformat()
        futuras = self.cliente().get(url, {"desde": manana})

        self.assertEqual(list(self.por_id(por_lote.data["results"], primera, segunda)), [segunda.pk])
        self.assertEqual(list(self.por_id(en_curso.data["results"], primera, segunda)), [primera.pk])
        self.assertEqual(list(self.por_id(preparadas.data["results"], primera, segunda)), [segunda.pk])
        self.assertEqual(self.por_id(futuras.data["results"], primera, segunda), {})
        fila = self.por_id(en_curso.data["results"], primera)[primera.pk]
        self.assertEqual(fila["ejecucion_estado"], "ejecucion")
        self.assertEqual(fila["situacion_etiqueta"], "En la mantequera")
```

Run: `cd backend && DJANGO_ENV=test ./.venv/Scripts/python.exe manage.py test procesos.tests_puesto_mantequilla --noinput`
Expected: ERROR `ImportError: cannot import name 'SITUACIONES_MANTEQUILLA'`.

- [ ] **Step 2: Situaciones generalizadas** — en `backend/procesos/dominio.py` reemplaza `situacion_descremacion` por:

```python
# Cómo se nombra una corrida de mantequilla en el puesto y en su historial,
# con la forma de `SITUACIONES_DESCREMACION` (gana la primera). A diferencia
# de Descremado, «Preparada» exige la ejecución en `preparacion`: una corrida
# heredada del modal anterior (ejecución en `borrador`) nunca tomó la
# mantequera y es «Borrador».
SITUACIONES_MANTEQUILLA = (
    ("preparada", "Preparada", "borrador", frozenset({"preparacion"})),
    ("en_curso", "En la mantequera", "en_proceso", None),
    ("esperando_calidad", "Esperando Calidad", "pendiente_calidad", None),
    ("terminada", "Terminada", "cerrada", None),
    ("anulada", "Anulada", "anulada", None),
    ("borrador", "Borrador", "borrador", None),
)


def situacion_de(tabla, estado: str, estado_ejecucion: str) -> tuple[str, str]:
    """`(valor, etiqueta)` de la situación de una corrida según `tabla` (gana la primera fila)."""
    for valor, etiqueta, estado_corrida, estados_ejecucion in tabla:
        if estado == estado_corrida and (
            estados_ejecucion is None or estado_ejecucion in estados_ejecucion
        ):
            return valor, etiqueta
    return estado, estado


def situacion_descremacion(estado: str, estado_ejecucion: str) -> tuple[str, str]:
    """`(valor, etiqueta)` de la situación de una corrida de descremado."""
    return situacion_de(SITUACIONES_DESCREMACION, estado, estado_ejecucion)


def situacion_mantequilla(estado: str, estado_ejecucion: str) -> tuple[str, str]:
    """`(valor, etiqueta)` de la situación de una corrida de mantequilla."""
    return situacion_de(SITUACIONES_MANTEQUILLA, estado, estado_ejecucion)
```

(En el comentario de `SITUACIONES_DESCREMACION`, `procesos.servicios.condicion_situacion_descremacion` → `procesos.servicios.condicion_situacion`.)

En `backend/procesos/servicios.py` reemplaza `condicion_situacion_descremacion` y `catalogo_situaciones_descremacion` por:

```python
def condicion_situacion(tabla, situacion):
    """
    El filtro del historial por situación: la misma tabla que nombra cada fila
    (`dominio.SITUACIONES_DESCREMACION`, `dominio.SITUACIONES_MANTEQUILLA`),
    con «gana la primera» traducido a excluir las filas anteriores. Una
    situación desconocida no devuelve nada. Una función para los dos puestos:
    con dos copias, el filtro de un historial y su columna podían dejar de
    coincidir.
    """
    def condicion(estado_corrida, estados_ejecucion):
        resultado = Q(estado=estado_corrida)
        if estados_ejecucion is not None:
            resultado &= Q(ejecucion__estado__in=estados_ejecucion)
        return resultado

    anteriores = Q()
    for valor, _etiqueta, estado_corrida, estados_ejecucion in tabla:
        propia = condicion(estado_corrida, estados_ejecucion)
        if valor == situacion:
            return propia & ~anteriores if anteriores else propia
        anteriores |= propia
    return Q(pk__in=[])


def catalogo_situaciones(tabla):
    """Las opciones del filtro del historial: las mismas situaciones que muestra la columna."""
    return [
        {"valor": valor, "etiqueta": etiqueta}
        for valor, etiqueta, _estado, _ejecucion in tabla
    ]
```

En `estado_puesto_descremado`, `from .dominio import situacion_descremacion` → `from .dominio import SITUACIONES_DESCREMACION, situacion_descremacion` y `"estados": catalogo_situaciones_descremacion(),` → `"estados": catalogo_situaciones(SITUACIONES_DESCREMACION),`.

- [ ] **Step 3: El estado del puesto** — en `backend/procesos/servicios.py`, después de `iniciar_mantequilla`:

```python
def _estado_calidad_de_crema(lote):
    """Por qué una crema no se ofrece: rechazada, pendiente o sin decisión de Calidad."""
    estados = {
        decision.estado
        for decision in (
            getattr(salida, "liberacion_calidad", None) for salida in lote.salidas_proceso.all()
        )
        if decision is not None
    }
    if "rechazado" in estados:
        return "rechazado"
    if "pendiente" in estados:
        return "pendiente"
    return "trazabilidad_incompleta"


def estado_puesto_mantequilla(usuario):
    """
    Lo que el puesto de Mantequilla dibuja: un estado por mantequera
    —derivado de su ejecución de Mantequilla que ocupa el equipo; una en
    curso manda sobre una preparada—, los motivos que impiden iniciar
    calculados por la misma función que decide al iniciar, y las listas que
    «Preparar» vuelve a validar con las mismas reglas: órdenes, cremas con su
    disponible (`kg_crema_disponible`), cremas que esperan a Calidad y sueros
    libres (`sueros_libres`). La pantalla no recalcula nada de esto.

    Se listan las mantequeras activas **y** cualquier equipo que tenga una
    ejecución de Mantequilla que lo ocupe aunque no sea mantequera (un dato de
    antes de `maestros.0040`): sin eso, esa corrida no tendría tarjeta ni cómo
    cerrarse. Una ejecución terminal o en `pendiente_control` no ocupa; la
    segunda se informa en `en_calidad`.
    """
    from inventario.servicios import advertencia_aseo_equipo, motivo_equipo_no_habilitado
    from maestros.models import Equipo
    from produccion.models import Lote, OrdenProduccion
    from usuarios.tenancy import filtrar_por_scope

    from .dominio import SITUACIONES_MANTEQUILLA, situacion_mantequilla

    def texto(valor):
        # Texto, como en los serializers: el tipo del frontend es `string`.
        return None if valor is None else str(valor)

    def acotar(consulta):
        return filtrar_por_scope(
            consulta, usuario, campo_sucursal="sucursal_id", campo_empresa="sucursal__empresa_id",
        )

    ocupantes = EjecucionProceso.objects.filter(
        etapa__tipo=EtapaProceso.Tipo.MANTEQUILLA,
        estado__in=ESTADOS_QUE_OCUPAN_EQUIPO, equipo__isnull=False,
    )
    maquinas = list(acotar(
        Equipo.objects.filter(
            Q(activo=True, tipo=Equipo.Tipo.MANTEQUERA)
            | Q(pk__in=ocupantes.values("equipo_id"))
        ).order_by("codigo")
    ))
    ids = [maquina.pk for maquina in maquinas]

    activas = {}
    for ejecucion in ocupantes.filter(equipo_id__in=ids).select_related(
        "etapa", "equipo", "corrida_mantequilla__orden__producto",
        "corrida_mantequilla__lote_crema__producto",
        "corrida_mantequilla__lote_mantequilla__producto",
        "corrida_mantequilla__lote_suero",
    ).order_by("pk"):
        actual = activas.get(ejecucion.equipo_id)
        if actual is None or (
            actual.estado == EjecucionProceso.Estado.PREPARACION
            and ejecucion.estado != EjecucionProceso.Estado.PREPARACION
        ):
            activas[ejecucion.equipo_id] = ejecucion

    en_calidad = {}
    for corrida in CorridaMantequilla.objects.filter(
        ejecucion__equipo_id__in=ids,
        ejecucion__estado=EjecucionProceso.Estado.PENDIENTE_CONTROL,
    ).select_related("ejecucion", "lote_mantequilla").order_by("pk"):
        en_calidad[corrida.ejecucion.equipo_id] = corrida

    def resumen(ejecucion):
        corrida = getattr(ejecucion, "corrida_mantequilla", None)
        base = {
            "id": None, "estado": None, "ejecucion_id": ejecucion.pk,
            "ejecucion_codigo": ejecucion.codigo, "ejecucion_estado": ejecucion.estado,
            "orden_codigo": None, "producto": None, "lote_mantequilla": None,
            "lote_crema": None, "kg_crema": None, "lote_suero": None,
            "iniciada_en": ejecucion.inicio,
        }
        if corrida is None:
            return base
        return {
            **base,
            "id": corrida.pk, "estado": corrida.estado,
            "orden_codigo": corrida.orden.codigo, "producto": corrida.orden.producto.nombre,
            "lote_mantequilla": corrida.lote_mantequilla.codigo_lote,
            "lote_crema": corrida.lote_crema.codigo_lote,
            "kg_crema": texto(corrida.kg_crema),
            "lote_suero": corrida.lote_suero.codigo_lote if corrida.lote_suero_id else None,
            "iniciada_en": corrida.iniciada_en,
        }

    filas = []
    for maquina in maquinas:
        ejecucion = activas.get(maquina.pk)
        motivos_tomar, motivos_iniciar, resolver_en = [], [], None
        if ejecucion is None:
            estado = "disponible"
            # La misma regla con que «Preparar» rechaza la mantequera.
            impedimento = motivo_equipo_no_habilitado(maquina)
            if impedimento:
                motivos_tomar, resolver_en = [impedimento], RESOLVER_CIP
        elif ejecucion.estado == EjecucionProceso.Estado.PREPARACION:
            estado = "preparada"
            corrida = getattr(ejecucion, "corrida_mantequilla", None)
            if corrida is None:
                # Dato heredado de `preparar-continuacion`, ya cerrado para
                # Mantequilla: sin corrida no hay `cancelar-preparacion/`.
                motivos_iniciar = [
                    f"{ejecucion.codigo} no tiene corrida de mantequilla y no puede "
                    "iniciarse: cancela esa ejecución en Procesos y vuelve a preparar."
                ]
            else:
                tipados = motivos_tipados_para_iniciar_mantequilla(corrida, ejecucion=ejecucion)
                motivos_iniciar = [motivo for motivo, _ in tipados]
                # El enlace es del primer motivo, que es el que la tarjeta muestra.
                resolver_en = tipados[0][1] if tipados else None
        else:
            estado = "en_curso"
        aseo = None if estado == "en_curso" else advertencia_aseo_equipo(maquina)
        pendiente = en_calidad.get(maquina.pk)
        filas.append({
            "equipo_id": maquina.pk, "codigo": maquina.codigo, "nombre": maquina.nombre,
            "tipo": maquina.tipo, "estado": estado,
            "corrida": resumen(ejecucion) if ejecucion is not None else None,
            "motivos_para_tomar": motivos_tomar,
            "motivos_para_iniciar": motivos_iniciar,
            "resolver_en": resolver_en,
            "avisos": [aseo] if aseo else [],
            "en_calidad": (
                {
                    "id": pendiente.pk, "ejecucion_codigo": pendiente.ejecucion.codigo,
                    "lote_mantequilla": pendiente.lote_mantequilla.codigo_lote,
                }
                if pendiente is not None else None
            ),
        })

    ordenes = acotar(
        OrdenProduccion.objects.filter(
            producto__categoria="mantequilla",
            estado__in=[OrdenProduccion.Estado.PROGRAMADA, OrdenProduccion.Estado.EN_PROCESO],
        ).select_related("producto").order_by("codigo")
    )
    cremas_producidas = acotar(
        Lote.objects.filter(
            producto__familia="crema",
            estado__in=[Lote.Estado.PRODUCIDO, Lote.Estado.CERRADO],
            kg_producidos__isnull=False,
        ).select_related("producto")
    )
    liberadas = Lote.objects.filter(filtro_crema_liberada()).values("pk")
    cremas = []
    for lote in cremas_producidas.filter(pk__in=liberadas).order_by("codigo_lote"):
        # La misma cuenta con que «Preparar» y el inicio rechazan.
        disponible = kg_crema_disponible(lote)
        if disponible <= 0:
            continue
        fuente = fuente_tk_de_crema(lote)
        cremas.append({
            "id": lote.pk, "codigo": lote.codigo_lote, "producto": lote.producto.nombre,
            "disponible_kg": texto(disponible),
            "tk": fuente.silo.codigo if fuente is not None else None,
        })
    pendientes = (
        cremas_producidas.filter(salidas_proceso__isnull=False)
        .exclude(pk__in=liberadas)
        .prefetch_related("salidas_proceso__liberacion_calidad", "salidas_proceso__ejecucion__etapa")
        .distinct().order_by("codigo_lote")
    )
    hoy = timezone.localdate()
    corridas_de_hoy = [
        {
            "id": corrida.pk, "ejecucion_codigo": corrida.ejecucion.codigo,
            "equipo": corrida.ejecucion.equipo.codigo if corrida.ejecucion.equipo_id else None,
            "lote_mantequilla": corrida.lote_mantequilla.codigo_lote,
            "lote_crema": corrida.lote_crema.codigo_lote,
            "estado": corrida.estado, "estado_etiqueta": corrida.get_estado_display(),
            "estado_ejecucion": corrida.ejecucion.estado,
            **dict(zip(
                ("situacion", "situacion_etiqueta"),
                situacion_mantequilla(corrida.estado, corrida.ejecucion.estado),
            )),
        }
        for corrida in CorridaMantequilla.objects.filter(ejecucion__equipo_id__in=ids)
        .filter(
            Q(ejecucion__creada_en__date=hoy) | Q(iniciada_en__date=hoy)
            | Q(finalizada_en__date=hoy)
        )
        # Un huérfano cuya ejecución terminó sin iniciarse no es trabajo del día.
        .exclude(iniciada_en__isnull=True, ejecucion__estado__in=ESTADOS_EJECUCION_TERMINALES)
        .select_related("ejecucion__equipo", "lote_mantequilla", "lote_crema")
        .order_by("-pk")
    ]
    return {
        "mantequeras": filas,
        "ordenes": [
            {"id": orden.pk, "codigo": orden.codigo, "producto": orden.producto.nombre}
            for orden in ordenes
        ],
        "cremas": cremas,
        "cremas_pendientes_calidad": [
            {
                "id": lote.pk, "codigo": lote.codigo_lote, "producto": lote.producto.nombre,
                "estado_calidad": _estado_calidad_de_crema(lote),
                "etapa_origen": next(
                    (salida.ejecucion.etapa.get_tipo_display() for salida in lote.salidas_proceso.all()),
                    "Sin proceso de origen",
                ),
            }
            for lote in pendientes
        ],
        "sueros": [
            {"id": lote.pk, "codigo": lote.codigo_lote, "producto": lote.producto.nombre}
            for lote in sueros_libres(acotar(Lote.objects.select_related("producto"))).order_by("codigo_lote")
        ],
        "corridas_de_hoy": corridas_de_hoy,
        # Las opciones del filtro del historial: las mismas situaciones que
        # muestra la columna, no los estados crudos de la corrida.
        "estados": catalogo_situaciones(SITUACIONES_MANTEQUILLA),
    }
```

- [ ] **Step 4: Serializer** — en `CorridaMantequillaSerializer` agrega:

```python
    # El historial distingue «Preparada» de «Borrador» con el estado de la
    # ejecución, no solo con el de la corrida.
    ejecucion_estado = serializers.CharField(source="ejecucion.estado", read_only=True)
    # La columna «Situación» del historial, con la tabla que usa su filtro.
    situacion = serializers.SerializerMethodField()
    situacion_etiqueta = serializers.SerializerMethodField()
```

`"motivo_anulacion"` entra a `read_only_fields`, y:

```python
    @staticmethod
    def _situacion(corrida):
        from .dominio import situacion_mantequilla

        return situacion_mantequilla(corrida.estado, corrida.ejecucion.estado)

    def get_situacion(self, corrida):
        return self._situacion(corrida)[0]

    def get_situacion_etiqueta(self, corrida):
        return self._situacion(corrida)[1]
```

- [ ] **Step 5: Vistas** — en `backend/procesos/views.py`:
  - Imports de `.servicios`: quita `condicion_situacion_descremacion`; agrega `condicion_situacion, estado_puesto_mantequilla`. Agrega `from .dominio import SITUACIONES_DESCREMACION, SITUACIONES_MANTEQUILLA`.
  - `CorridaDescremacionViewSet.condicion_estado`: `return condicion_situacion(SITUACIONES_DESCREMACION, estado)`.
  - `CorridaMantequillaViewSet`: la declaración pasa a `class CorridaMantequillaViewSet(FiltraConsultaMixin, RelacionesTenantMixin, QuerysetTenantMixin, viewsets.ModelViewSet):`, el `queryset` termina en `.order_by("-pk")`, y debajo de `http_method_names`:

```python
    # Historial del puesto: se filtra en el servidor porque la lista está
    # paginada (mismo contrato que Descremado, Secado y Existencias).
    busqueda_en = (
        "ejecucion__codigo", "lote_mantequilla__codigo_lote",
        "lote_crema__codigo_lote", "orden__codigo",
    )
    filtro_estado = "estado"
    filtro_fecha = "ejecucion__creada_en"

    def condicion_estado(self, estado):
        # `?estado=` filtra por la situación que muestra la columna, con las
        # opciones que sirve `puesto/` (`SITUACIONES_MANTEQUILLA`).
        return condicion_situacion(SITUACIONES_MANTEQUILLA, estado)

    @action(detail=False, methods=["get"])
    def puesto(self, request):
        """Estado del puesto de Mantequilla: lo que la pantalla dibuja, sin recalcular."""
        return Response(estado_puesto_mantequilla(request.user))
```

  (`puesto` va antes de `opciones_alta`, que se elimina en la Task 7.)

- [ ] **Step 6: Verificar**

Run: `cd backend && DJANGO_ENV=test ./.venv/Scripts/python.exe manage.py test procesos.tests_puesto_mantequilla procesos.tests_puesto_descremado procesos.tests_mantequilla --noinput`
Expected: OK (el historial y el catálogo de Descremado siguen iguales con la función general).

Run: `cd backend && DJANGO_ENV=test ./.venv/Scripts/python.exe manage.py test procesos --noinput`
Expected: OK.

- [ ] **Step 7: Commit**

```bash
git add backend/procesos/dominio.py backend/procesos/servicios.py backend/procesos/serializers.py backend/procesos/views.py backend/procesos/tests_puesto_mantequilla.py
git commit -m "feat(procesos): estado del puesto de Mantequilla, situaciones compartidas con Descremado e historial con filtros de servidor"
```

---

### Task 6: Servicios del frontend y reglas puras

**Files:**
- Create: `frontend/src/services/mantequilla.service.ts`, `frontend/src/services/puesto-mantequilla.ts`, `frontend/src/services/permisos-mantequilla.ts`
- Create: `frontend/tests/puesto-mantequilla.test.ts`, `frontend/tests/permisos-mantequilla.test.ts`
- Modify: `frontend/src/services/puesto-secado.ts` (`MODULO_POR_RUTA`), `frontend/tests/puesto-secado.test.ts`
- Modify: `frontend/src/services/planta-ahora.ts` (`PUESTOS_QUE_INICIAN`), `frontend/tests/planta-ahora.test.ts`
- Modify: `frontend/src/services/procesos.service.ts` (`CorridaMantequilla`, ~149)

**Interfaces:**
- Consumes: endpoints de las Tasks 2-5.
- Produces (`mantequilla.service.ts`):
  - `export type EstadoMantequera = "disponible" | "preparada" | "en_curso";`
  - `CorridaEnMantequera`, `MantequeraPuesto`, `CremaDisponible`, `CremaPendienteCalidad`, `CorridaDeHoyMantequilla`, `PuestoMantequilla`, `PreparacionMantequilla`, `ValoresCierreMantequilla`, `RevisionCierreMantequilla`, `CierreMantequilla`, `CancelacionPreparacionMantequilla` (abajo, completas).
  - `obtenerPuestoMantequilla(): Promise<PuestoMantequilla>`; `obtenerMantequilla(id): Promise<CorridaMantequilla>`; `prepararMantequilla(datos): Promise<CorridaMantequilla>`; `iniciarMantequilla(id): Promise<CorridaMantequilla>`; `cancelarPreparacionMantequilla(id, motivo): Promise<CancelacionPreparacionMantequilla>`; `revisarCierreMantequilla(id, valores): Promise<RevisionCierreMantequilla>`; `cerrarMantequilla(id, datos: CierreMantequilla): Promise<CorridaMantequilla>`; `buscarMantequillas(filtros?: Filtros): Promise<Pagina<CorridaMantequilla>>`.
- Produces (`puesto-mantequilla.ts`): `accionDeMantequera(fila: MantequeraPuesto): { tipo: "preparar" | "iniciar" | "cerrar" | "ninguna"; habilitada: boolean; motivo: string | null }`; `estadoDelBalance(revision: RevisionCierreMantequilla | null, pendiente: boolean, error?: boolean): EstadoBalance`; reexporta `corridaCancelable` (de `puesto-descremado.ts`) y `moduloDeResolver` (de `puesto-secado.ts`).
- Produces (`permisos-mantequilla.ts`): `puedeOperarMantequilla(usuario): boolean`.
- Produces (`planta-ahora.ts`): `textoIniciarEnPuesto("mantequilla", "preparacion") === "Iniciar en el puesto de Mantequilla"`.
- Produces (`puesto-secado.ts`): `moduloDeResolver("/planificacion") === "planificacion"`.

- [ ] **Step 1: Pruebas que fallan** — `frontend/tests/puesto-mantequilla.test.ts`:

```ts
import assert from "node:assert/strict";
import test from "node:test";

import {
  accionDeMantequera, corridaCancelable, estadoDelBalance, moduloDeResolver,
} from "../src/services/puesto-mantequilla.ts";

const base = {
  equipo_id: 1, codigo: "mant-01", nombre: "Mantequera 1", tipo: "mantequera", corrida: null,
  motivos_para_tomar: [] as string[], motivos_para_iniciar: [] as string[],
  resolver_en: null, avisos: [] as string[], en_calidad: null,
};
const corrida = {
  id: 9, estado: "borrador", ejecucion_id: 140, ejecucion_codigo: "EJ-MANT-311",
  ejecucion_estado: "preparacion", orden_codigo: "OP-0412", producto: "Mantequilla sin sal 20 kg",
  lote_mantequilla: "CCAA6281LM-01", lote_crema: "INT-DES-7-CR", kg_crema: "60.000",
  lote_suero: null, iniciada_en: null,
};
const revision = {
  entrada_kg: "60.000", clasificado_kg: "59.000", diferencia_kg: "1.000", cuadra: false,
  mensaje: "El cierre debe clasificar el 100% de la crema: 1.000 kg faltan por clasificar.",
  errores: {} as Record<string, string>,
};

test("una mantequera disponible ofrece preparar", () => {
  assert.deepEqual(accionDeMantequera({ ...base, estado: "disponible" }), { tipo: "preparar", habilitada: true, motivo: null });
});

test("una mantequera en CIP no se prepara y dice por qué", () => {
  const fila = { ...base, estado: "disponible" as const, motivos_para_tomar: ["Mantequera 1 está en CIP."] };
  assert.deepEqual(accionDeMantequera(fila), { tipo: "preparar", habilitada: false, motivo: "Mantequera 1 está en CIP." });
});

test("una preparada sin motivos se puede iniciar", () => {
  assert.deepEqual(accionDeMantequera({ ...base, estado: "preparada", corrida }), { tipo: "iniciar", habilitada: true, motivo: null });
});

test("una preparada con motivos muestra el primero y no habilita iniciar", () => {
  const fila = { ...base, estado: "preparada" as const, corrida, motivos_para_iniciar: ["El lote de crema INT-DES-7-CR todavía no está liberado por Calidad.", "otro"] };
  assert.deepEqual(accionDeMantequera(fila), { tipo: "iniciar", habilitada: false, motivo: "El lote de crema INT-DES-7-CR todavía no está liberado por Calidad." });
});

test("los avisos no deshabilitan iniciar", () => {
  const fila = { ...base, estado: "preparada" as const, corrida, avisos: ["Último aseo con observación."] };
  assert.equal(accionDeMantequera(fila).habilitada, true);
});

test("una preparación sin corrida no se puede iniciar", () => {
  const fila = { ...base, estado: "preparada" as const, corrida: { ...corrida, id: null } };
  assert.equal(accionDeMantequera(fila).habilitada, false);
});

test("en curso ofrece registrar el balance solo en ejecución, espejo de cerrar_mantequilla", () => {
  const enCurso = { ...base, estado: "en_curso" as const, corrida: { ...corrida, estado: "en_proceso", ejecucion_estado: "ejecucion" } };
  assert.deepEqual(accionDeMantequera(enCurso), { tipo: "cerrar", habilitada: true, motivo: null });
  for (const ejecucion_estado of ["pausada", "bloqueada"]) {
    const fila = { ...enCurso, corrida: { ...enCurso.corrida, ejecucion_estado } };
    assert.equal(accionDeMantequera(fila).habilitada, false);
    assert.match(accionDeMantequera(fila).motivo ?? "", new RegExp(ejecucion_estado));
  }
});

test("se cancela una corrida en borrador con la ejecución preparada o heredada en borrador", () => {
  assert.equal(corridaCancelable(corrida), 9);
  assert.equal(corridaCancelable({ ...corrida, ejecucion_estado: "borrador" }), 9);
  assert.equal(corridaCancelable({ ...corrida, estado: "en_proceso", ejecucion_estado: "ejecucion" }), null);
  assert.equal(corridaCancelable({ ...corrida, estado: "anulada", ejecucion_estado: "cancelada" }), null);
  assert.equal(corridaCancelable(null), null);
});

test("el balance incompleto lo dice el servidor y no deja cerrar", () => {
  const estado = estadoDelBalance(revision, false);
  assert.equal(estado.franja, "incompleto");
  assert.equal(estado.titulo, "Balance incompleto");
  assert.equal(estado.detalle, revision.mensaje);
  assert.equal(estado.puedeCerrar, false);
});

test("el balance excedido se lee del signo que manda el servidor", () => {
  const estado = estadoDelBalance({ ...revision, clasificado_kg: "61.000", diferencia_kg: "-1.000", mensaje: "El cierre debe clasificar el 100% de la crema: 1.000 kg exceden la entrada." }, false);
  assert.equal(estado.franja, "excedido");
  assert.equal(estado.titulo, "Balance excedido");
});

test("un balance completo deja cerrar solo sin errores", () => {
  const completo = { ...revision, clasificado_kg: "60.000", diferencia_kg: "0.000", cuadra: true, mensaje: null };
  const estado = estadoDelBalance(completo, false);
  assert.equal(estado.franja, "completo");
  assert.equal(estado.puedeCerrar, true);
  assert.match(estado.detalle ?? "", /60 kg de 60 kg clasificados/);

  const conError = estadoDelBalance({ ...completo, errores: { kg_suero: "Esta corrida no tiene un lote de suero asociado: registra 0 kg." } }, false);
  assert.equal(conError.puedeCerrar, false);
  assert.deepEqual(conError.errores, ["Esta corrida no tiene un lote de suero asociado: registra 0 kg."]);
});

test("una revisión en camino o fallida no habla de lo que se va a cerrar", () => {
  const completo = { ...revision, cuadra: true, mensaje: null, diferencia_kg: "0.000" };
  assert.equal(estadoDelBalance(completo, true).franja, "revisando");
  assert.equal(estadoDelBalance(completo, true).puedeCerrar, false);
  assert.equal(estadoDelBalance(null, false).franja, "revisando");
  assert.equal(estadoDelBalance(null, false, true).franja, "sin_revision");
  assert.equal(estadoDelBalance(null, false, true).puedeCerrar, false);
});

test("los motivos de la orden se resuelven en Planificación", () => {
  assert.equal(moduloDeResolver("/planificacion"), "planificacion");
  assert.equal(moduloDeResolver("/calidad"), "calidad");
});
```

`frontend/tests/permisos-mantequilla.test.ts`:

```ts
import assert from "node:assert/strict";
import test from "node:test";

import { puedeOperarMantequilla } from "../src/services/permisos-mantequilla.ts";

const conArea = (area: string, rol = "produccion") => ({ rol, perfil: { area } });

test("Condensación opera el puesto de Mantequilla", () => {
  assert.equal(puedeOperarMantequilla(conArea("condensacion")), true);
});

test("Secado no opera la mantequera, como en el servidor", () => {
  assert.equal(puedeOperarMantequilla(conArea("secado")), false);
});

test("Calidad consulta pero no opera", () => {
  assert.equal(puedeOperarMantequilla(conArea("calidad", "calidad")), false);
});

test("Administración y el administrador operan", () => {
  assert.equal(puedeOperarMantequilla(conArea("administracion")), true);
  assert.equal(puedeOperarMantequilla({ rol: "admin", perfil: null }), true);
});

test("sin sesión o sin área no se opera", () => {
  assert.equal(puedeOperarMantequilla(null), false);
  assert.equal(puedeOperarMantequilla({ rol: "produccion", perfil: null }), false);
});
```

En `frontend/tests/planta-ahora.test.ts`, el test «Secado y Descremado se inician en su puesto…» pasa a:

```ts
test("Secado, Descremado y Mantequilla se inician en su puesto, espejo de MENSAJES_INICIO_EN_PUESTO", () => {
  assert.equal(textoIniciarEnPuesto("secado", "preparacion"), "Iniciar en el puesto de Secado");
  assert.equal(textoIniciarEnPuesto("descremacion", "preparacion"), "Iniciar en el puesto de Descremado");
  assert.equal(textoIniciarEnPuesto("mantequilla", "preparacion"), "Iniciar en el puesto de Mantequilla");
  // Reanudar no es iniciar, y las demás etapas siguen en la bandeja.
  assert.equal(textoIniciarEnPuesto("descremacion", "pausada"), null);
  assert.equal(textoIniciarEnPuesto("mantequilla", "pausada"), null);
  assert.equal(textoIniciarEnPuesto("envasado", "preparacion"), null);
});
```

En `frontend/tests/puesto-secado.test.ts`, junto a las aserciones de `moduloDeResolver`: `assert.equal(moduloDeResolver("/planificacion"), "planificacion");`.

Run: `cd frontend && npm test`
Expected: FAIL (módulos `puesto-mantequilla.ts` y `permisos-mantequilla.ts` inexistentes; `textoIniciarEnPuesto("mantequilla", …)` devuelve `null`).

- [ ] **Step 2: Servicio** — `frontend/src/services/mantequilla.service.ts`:

```ts
import api from "./api";
import { conFiltros, type Filtros } from "./paginacion";
import type { CorridaMantequilla, Pagina } from "./procesos.service";

export type EstadoMantequera = "disponible" | "preparada" | "en_curso";

export interface CorridaEnMantequera {
  /* `null` en una ejecución de Mantequilla sin corrida (dato heredado de
     `preparar-continuacion`, ya cerrado). */
  id: number | null;
  estado: string | null;
  ejecucion_id: number;
  ejecucion_codigo: string;
  ejecucion_estado: string;
  orden_codigo: string | null;
  producto: string | null;
  lote_mantequilla: string | null;
  lote_crema: string | null;
  kg_crema: string | null;
  lote_suero: string | null;
  iniciada_en: string | null;
}

export interface MantequeraPuesto {
  equipo_id: number;
  codigo: string;
  nombre: string;
  /* `mantequera`, o el tipo viejo de un equipo con una corrida anterior a `maestros.0040`. */
  tipo: string;
  estado: EstadoMantequera;
  corrida: CorridaEnMantequera | null;
  /* Por qué no se puede preparar una disponible (CIP). */
  motivos_para_tomar: string[];
  motivos_para_iniciar: string[];
  /* Dónde se resuelve el primer motivo; `null` si no hay pantalla que lo arregle. */
  resolver_en: string | null;
  avisos: string[];
  en_calidad: { id: number; ejecucion_codigo: string; lote_mantequilla: string } | null;
}

export interface CremaDisponible {
  id: number;
  codigo: string;
  producto: string;
  /* Kilos producidos menos lo que entró a una mantequera y lo que otras
     corridas preparadas ya pidieron (`kg_crema_disponible`): el tope del formulario. */
  disponible_kg: string;
  /* El TK de donde saldrá al iniciar, si está en uno. */
  tk: string | null;
}

export interface CremaPendienteCalidad {
  id: number;
  codigo: string;
  producto: string;
  estado_calidad: "pendiente" | "rechazado" | "trazabilidad_incompleta";
  etapa_origen: string;
}

export interface CorridaDeHoyMantequilla {
  id: number;
  ejecucion_codigo: string;
  equipo: string | null;
  lote_mantequilla: string;
  lote_crema: string;
  estado: string;
  estado_etiqueta: string;
  estado_ejecucion: string;
  /* Cómo la nombra el puesto; mismas opciones que el filtro del historial. */
  situacion: string;
  situacion_etiqueta: string;
}

export interface PuestoMantequilla {
  mantequeras: MantequeraPuesto[];
  ordenes: { id: number; codigo: string; producto: string }[];
  cremas: CremaDisponible[];
  cremas_pendientes_calidad: CremaPendienteCalidad[];
  sueros: { id: number; codigo: string; producto: string }[];
  corridas_de_hoy: CorridaDeHoyMantequilla[];
  /* Las situaciones del filtro del historial (`SITUACIONES_MANTEQUILLA`). */
  estados: { valor: string; etiqueta: string }[];
}

/* El código del lote de salida se sugiere y queda editable. */
export interface PreparacionMantequilla {
  orden: number;
  lote_crema: number;
  equipo: number;
  codigo_lote_mantequilla: string;
  kg_crema: number;
  lote_suero?: number;
}

export interface ValoresCierreMantequilla {
  kg_mantequilla: number | null;
  kg_suero: number | null;
  kg_merma: number | null;
  kg_reproceso: number | null;
  motivo_reproceso: string;
}

export interface RevisionCierreMantequilla {
  entrada_kg: string;
  clasificado_kg: string;
  /* entrada − clasificado: positiva falta, negativa excede. */
  diferencia_kg: string;
  cuadra: boolean;
  mensaje: string | null;
  /* Las otras reglas de `clean()` que dependen de lo tecleado, por campo. */
  errores: Record<string, string>;
}

export interface CierreMantequilla {
  kg_mantequilla: number;
  kg_suero: number;
  kg_merma: number;
  kg_reproceso: number;
  motivo_reproceso: string;
  controles: Record<string, unknown>;
}

export interface CancelacionPreparacionMantequilla {
  ejecucion_id: number;
  ejecucion_codigo: string;
  estado: string;
}

export async function obtenerPuestoMantequilla(): Promise<PuestoMantequilla> {
  const { data } = await api.get<PuestoMantequilla>("procesos/mantequillas/puesto/");
  return data;
}

export async function obtenerMantequilla(id: number): Promise<CorridaMantequilla> {
  const { data } = await api.get<CorridaMantequilla>(`procesos/mantequillas/${id}/`);
  return data;
}

/* Prepara: lote de salida, ejecución y corrida, y toma la mantequera. No inicia. */
export async function prepararMantequilla(datos: PreparacionMantequilla): Promise<CorridaMantequilla> {
  const { data } = await api.post<CorridaMantequilla>("procesos/mantequillas/crear-guiada/", datos);
  return data;
}

export async function iniciarMantequilla(id: number): Promise<CorridaMantequilla> {
  const { data } = await api.post<CorridaMantequilla>(`procesos/mantequillas/${id}/iniciar/`);
  return data;
}

/* Suelta la mantequera; la corrida y su lote de salida quedan anulados. */
export async function cancelarPreparacionMantequilla(
  id: number, motivo: string,
): Promise<CancelacionPreparacionMantequilla> {
  const { data } = await api.post<CancelacionPreparacionMantequilla>(
    `procesos/mantequillas/${id}/cancelar-preparacion/`, { motivo },
  );
  return data;
}

/* El balance con lo tecleado hasta ahora; el servidor no escribe nada. */
export async function revisarCierreMantequilla(
  id: number, valores: ValoresCierreMantequilla,
): Promise<RevisionCierreMantequilla> {
  const { data } = await api.post<RevisionCierreMantequilla>(
    `procesos/mantequillas/${id}/revisar-cierre/`, valores,
  );
  return data;
}

export async function cerrarMantequilla(id: number, datos: CierreMantequilla): Promise<CorridaMantequilla> {
  const { data } = await api.post<CorridaMantequilla>(`procesos/mantequillas/${id}/cerrar/`, datos);
  return data;
}

/* Historial del puesto: filtros y página viajan al servidor. */
export async function buscarMantequillas(filtros: Filtros = {}): Promise<Pagina<CorridaMantequilla>> {
  const { data } = await api.get<Pagina<CorridaMantequilla>>(conFiltros("procesos/mantequillas/", filtros));
  return data;
}
```

En `frontend/src/services/procesos.service.ts`, `CorridaMantequilla` gana (debajo de `estado_etiqueta`):

```ts
  /* El historial distingue «Preparada» de «Borrador» con el estado de la ejecución. */
  ejecucion_estado: string;
  /* La columna «Situación», con la tabla que usa su filtro (`SITUACIONES_MANTEQUILLA`). */
  situacion: string;
  situacion_etiqueta: string;
  motivo_anulacion: string;
```

- [ ] **Step 3: Reglas puras** — `frontend/src/services/puesto-mantequilla.ts`:

```ts
import { cantidad } from "./formato.ts";
import type { MantequeraPuesto, RevisionCierreMantequilla } from "./mantequilla.service.ts";

/* Un solo mapa de «dónde se resuelve» para los puestos. */
export { moduloDeResolver } from "./puesto-secado.ts";
/* La misma regla que `cancelar_preparacion_mantequilla` y que Descremado:
   corrida `borrador` con la ejecución en `borrador` o `preparacion`. Se
   reexporta en vez de copiarse. */
export { corridaCancelable } from "./puesto-descremado.ts";

export interface AccionMantequera {
  tipo: "preparar" | "iniciar" | "cerrar" | "ninguna";
  habilitada: boolean;
  motivo: string | null;
}

/*
  Qué botón lleva la tarjeta de una mantequera. Solo traduce lo que mandó el
  servidor: estado y motivos los calcula `estado_puesto_mantequilla` con las
  mismas reglas que deciden al preparar (`motivo_equipo_no_habilitado`) y al
  iniciar (`motivos_tipados_para_iniciar_mantequilla`). Los avisos no entran
  aquí a propósito: avisan, no deshabilitan.

  La única regla propia es espejo de `cerrar_mantequilla`: la ejecución pasa
  a `pendiente_control`, y eso solo se permite desde `ejecucion`.
*/
export function accionDeMantequera(fila: MantequeraPuesto): AccionMantequera {
  switch (fila.estado) {
    case "disponible": {
      const motivo = fila.motivos_para_tomar[0] ?? null;
      return { tipo: "preparar", habilitada: motivo === null, motivo };
    }
    case "preparada": {
      const motivo = fila.motivos_para_iniciar[0] ?? null;
      return { tipo: "iniciar", habilitada: motivo === null && fila.corrida?.id != null, motivo };
    }
    case "en_curso": {
      const estado = fila.corrida?.ejecucion_estado;
      if (estado === "pausada") {
        return { tipo: "cerrar", habilitada: false, motivo: "La corrida está pausada: reanúdala antes de registrar el balance." };
      }
      if (estado === "bloqueada") {
        return { tipo: "cerrar", habilitada: false, motivo: "La corrida está bloqueada: resuelve el bloqueo antes de registrar el balance." };
      }
      return { tipo: "cerrar", habilitada: fila.corrida?.id != null, motivo: null };
    }
    default:
      return { tipo: "ninguna", habilitada: false, motivo: null };
  }
}

export type FranjaBalance = "completo" | "incompleto" | "excedido" | "revisando" | "sin_revision";

export interface EstadoBalance {
  franja: FranjaBalance;
  titulo: string;
  detalle: string | null;
  /* Las otras reglas de lo tecleado (suero sin lote, reproceso sin motivo). */
  errores: string[];
  /* «Cerrar y enviar a Calidad» solo con una revisión de lo tecleado que cuadra y sin errores. */
  puedeCerrar: boolean;
}

/*
  Qué franja y qué texto pinta el cierre a partir de la respuesta de
  `revisar-cierre/`. No hay aritmética: el servidor decide si cuadra y cuánto
  falta (`balance_mantequilla`), y el cliente solo lee el signo de la
  diferencia para decir «incompleto» o «excedido». Una revisión en camino o
  fallida no habla de lo que se va a cerrar: no habilita nada.
*/
export function estadoDelBalance(
  revision: RevisionCierreMantequilla | null, pendiente: boolean, error = false,
): EstadoBalance {
  if (pendiente || (!revision && !error)) {
    return { franja: "revisando", titulo: "Revisando el balance…", detalle: null, errores: [], puedeCerrar: false };
  }
  if (!revision) {
    return {
      franja: "sin_revision", titulo: "No se pudo revisar el balance",
      detalle: "El servidor lo vuelve a decidir al cerrar.", errores: [], puedeCerrar: false,
    };
  }
  const errores = Object.values(revision.errores);
  const clasificados = `${cantidad(revision.clasificado_kg, "kg")} de ${cantidad(revision.entrada_kg, "kg")} clasificados.`;
  if (revision.cuadra) {
    return { franja: "completo", titulo: "Balance completo", detalle: clasificados, errores, puedeCerrar: errores.length === 0 };
  }
  const excedido = Number(revision.diferencia_kg) < 0;
  return {
    franja: excedido ? "excedido" : "incompleto",
    titulo: excedido ? "Balance excedido" : "Balance incompleto",
    detalle: revision.mensaje ?? clasificados,
    errores,
    puedeCerrar: false,
  };
}
```

`frontend/src/services/permisos-mantequilla.ts`:

```ts
import { puedeOperarEvaporacion } from "./permisos-evaporacion.ts";

/*
  Quién opera el puesto de Mantequilla. Refleja `procesos.permisos`
  (`TIPOS_OPERABLES_POR_AREA`): la etapa Mantequilla la opera Condensación y
  el administrador, igual que la evaporación y el descremado —por eso es la
  misma regla y no una copia que pueda divergir—. Calidad ve el puesto en
  modo consulta; Secado escribe lotes pero no opera la mantequera.

  Cortesía para no ofrecer botones que el servidor rechaza con 403; el
  permiso se aplica allá.
*/
export const puedeOperarMantequilla = puedeOperarEvaporacion;
```

- [ ] **Step 4: Planificación como destino y el inicio en el puesto**
  - `frontend/src/services/puesto-secado.ts`, `MODULO_POR_RUTA`: agrega `"/planificacion": "planificacion",` y en el comentario de encima suma `RESOLVER_PLANIFICACION` a la lista.
  - `frontend/src/services/planta-ahora.ts`, `PUESTOS_QUE_INICIAN`: agrega `mantequilla: "Mantequilla",`.

- [ ] **Step 5: Verificar**

Run: `cd frontend && npm test`
Expected: PASS.

Run: `cd frontend && npx tsc -b --pretty false && npx eslint .`
Expected: sin errores.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/services/mantequilla.service.ts frontend/src/services/puesto-mantequilla.ts frontend/src/services/permisos-mantequilla.ts frontend/src/services/puesto-secado.ts frontend/src/services/planta-ahora.ts frontend/src/services/procesos.service.ts frontend/tests/puesto-mantequilla.test.ts frontend/tests/permisos-mantequilla.test.ts frontend/tests/puesto-secado.test.ts frontend/tests/planta-ahora.test.ts
git commit -m "feat(frontend): servicios y reglas puras del puesto de Mantequilla"
```

---

### Task 7: El puesto, el retiro de lo viejo y las rutas

**Files:**
- Move: `frontend/src/pages/Descremado/CancelarPreparacion.tsx` → `frontend/src/components/operacion/CancelarPreparacion.tsx` (con `advertencia`)
- Create: `frontend/src/pages/Mantequilla/TarjetaMantequera.tsx`, `PrepararMantequilla.tsx`, `CierreMantequilla.tsx`, `PuestoMantequilla.tsx`
- Delete: `frontend/src/pages/Procesos/NuevaMantequilla.tsx`, `frontend/src/pages/Procesos/CierreMantequilla.tsx`, `frontend/src/services/balance-mantequilla.ts`, `frontend/tests/balance-mantequilla.test.ts`
- Modify: `frontend/src/pages/Descremado/PuestoDescremado.tsx`, `frontend/src/pages/Procesos/Procesos.tsx`, `frontend/src/pages/Produccion/Produccion.tsx`, `frontend/src/pages/Produccion/SalidasIntermedias.tsx`, `frontend/src/pages/Leche/Silos.tsx`
- Modify: `frontend/src/app/routes.tsx`, `frontend/src/services/navegacion-operacional.ts`, `frontend/src/services/planta-ahora.ts`, `frontend/src/services/procesos.service.ts`
- Modify: `frontend/tests/navegacion-operacional.test.ts`, `frontend/tests/planta-ahora.test.ts`
- Modify: `backend/procesos/views.py` (`opciones_alta` eliminada; etiqueta de `acciones_permitidas` ~1526), `backend/procesos/dominio.py` (`RUTAS_POR_ETAPA`), `backend/procesos/tests_destinos.py`, `backend/procesos/tests_puesto_mantequilla.py`
- Modify: `CLAUDE.md`

**Interfaces:**
- Consumes: todo lo de la Task 6; `ConfirmarAccion`; `TablaConsulta` (`pages/Inventario/TablaConsulta`); `useCarga`, `mensajeDe` (`components/seccion/utilidades`); `mensajeErrorProceso`; `cantidad`; `fechaLocalISO` (`services/fechas`); `sugerirCodigoLote` (`services/produccion.service`); `puedeAccederModulo`; `obtenerSesion`.
- Produces: `CancelarPreparacion({ codigo, filas, advertencia, alVolver, alCancelar })` en `components/operacion/`.
- Produces: ruta `/produccion/mantequilla` (módulo `produccion`); `/procesos?seccion=mantequilla` redirige; `GET /api/procesos/mantequillas/opciones-alta/` → 404; la acción `iniciar_mantequilla` de `salidas/disponibles/` se rotula «Preparar en Mantequilla».

- [ ] **Step 1: `CancelarPreparacion` pasa a ser de los dos puestos** — `git mv frontend/src/pages/Descremado/CancelarPreparacion.tsx frontend/src/components/operacion/CancelarPreparacion.tsx` y en el archivo movido:
  - `import ConfirmarAccion from "../../components/operacion/ConfirmarAccion";` → `import ConfirmarAccion from "./ConfirmarAccion";`.
  - Comentario: «Motivo y confirmación para soltar una preparación. Lo abren la tarjeta y el historial de Descremado y de Mantequilla, con la misma regla (`corridaCancelable`); cada puesto dice qué se suelta (`advertencia`).»
  - Props: agrega `advertencia: string;` (entre `filas` y `alVolver`) y en `ConfirmarAccion` usa `advertencia={advertencia}` en vez del texto fijo de Descremado.
  - En `frontend/src/pages/Descremado/PuestoDescremado.tsx`: `import CancelarPreparacion from "./CancelarPreparacion";` → `import CancelarPreparacion from "../../components/operacion/CancelarPreparacion";`, y el modal recibe `advertencia="La descremadora queda disponible y se sueltan las reservas del silo y de los dos TK. No se mueve leche: hasta el cierre no salió nada del silo."`.

- [ ] **Step 2: Tarjeta** — `frontend/src/pages/Mantequilla/TarjetaMantequera.tsx`:

```tsx
import { useId } from "react";
import { Link } from "react-router-dom";

import { puedeAccederModulo } from "../../services/access-control";
import { cantidad } from "../../services/formato";
import type { MantequeraPuesto } from "../../services/mantequilla.service";
import { accionDeMantequera, corridaCancelable, moduloDeResolver } from "../../services/puesto-mantequilla";
import { obtenerSesion } from "../../services/sesion";

/* ¿Lleva el enlace a un módulo en el que el usuario puede entrar? Si no, se
   omite: «Acceso restringido» no resuelve nada. */
function puedeIr(ruta: string): boolean {
  const modulo = moduloDeResolver(ruta);
  return modulo !== null && puedeAccederModulo(obtenerSesion()?.usuario, modulo);
}

const ROTULO = { disponible: "Disponible", preparada: "Preparada", en_curso: "En curso" } as const;

/* Una tarjeta, un estado, una acción. Lo que dice lo decidió el servidor.
   Una mantequera preparada lleva además, en segundo plano, «Cancelar
   preparación», que confirma el puesto en un modal. */
export default function TarjetaMantequera({ fila, ocupado, puedeOperar, onPreparar, onIniciar, onCerrar, onCancelar }: {
  fila: MantequeraPuesto;
  ocupado: boolean;
  /* Quien no opera Mantequilla (Calidad) ve el mismo estado, motivos y
     avisos, sin botones: ninguno le daría otra cosa que un 403. */
  puedeOperar: boolean;
  onPreparar: (equipoId: number) => void;
  onIniciar: (corridaId: number) => void;
  onCerrar: (corridaId: number) => void;
  onCancelar: (fila: MantequeraPuesto) => void;
}) {
  const accion = accionDeMantequera(fila);
  const corrida = fila.corrida;
  const corridaId = corrida?.id ?? null;
  const cancelable = fila.estado === "preparada" ? corridaCancelable(corrida) : null;
  const idMotivo = useId();
  /* El botón deshabilitado anuncia por qué: el motivo visible lo describe. */
  const describe = accion.motivo ? idMotivo : undefined;
  return (
    <article aria-label={fila.nombre} className="flex flex-col gap-3 rounded-2xl border border-slate-200 bg-white p-5">
      <header className="flex items-start justify-between gap-3">
        <div>
          <h3 className="text-lg font-semibold text-slate-900">{fila.nombre}</h3>
          <p className="font-mono text-xs text-slate-600">{fila.codigo}</p>
        </div>
        <span className="rounded-full bg-slate-100 px-3 py-1 text-xs font-semibold text-slate-800">{ROTULO[fila.estado]}</span>
      </header>
      {fila.tipo !== "mantequera" && (
        <p className="text-xs text-amber-800">Equipo de tipo «{fila.tipo}» con una corrida de antes de las mantequeras: ciérrala o cancélala aquí.</p>
      )}
      {corrida && (
        <div className="space-y-1 text-sm text-slate-700">
          <p className="font-mono">{corrida.ejecucion_codigo}</p>
          {corrida.orden_codigo && <p>{corrida.orden_codigo} · {corrida.producto}</p>}
          {corrida.lote_crema && <p>Crema {corrida.lote_crema} · {cantidad(corrida.kg_crema, "kg")} → lote {corrida.lote_mantequilla}</p>}
          {corrida.lote_suero && <p>Mazada → {corrida.lote_suero}</p>}
          {corrida.iniciada_en && <p className="text-slate-600">Inició {new Date(corrida.iniciada_en).toLocaleString("es-CL")}</p>}
        </div>
      )}
      {fila.en_calidad && (
        <p className="text-sm text-violet-800">
          <span className="font-mono">{fila.en_calidad.lote_mantequilla}</span> de{" "}
          <span className="font-mono">{fila.en_calidad.ejecucion_codigo}</span> esperando Calidad
        </p>
      )}
      {accion.tipo === "preparar" && puedeOperar && (
        <button type="button" disabled={!accion.habilitada} aria-describedby={describe} onClick={() => onPreparar(fila.equipo_id)} className="rounded-xl bg-amber-700 px-4 py-3 text-sm font-semibold text-white hover:bg-amber-800 disabled:opacity-40">Preparar mantequilla</button>
      )}
      {accion.tipo === "iniciar" && puedeOperar && corridaId !== null && (
        <button type="button" disabled={!accion.habilitada || ocupado} aria-describedby={describe} onClick={() => onIniciar(corridaId)} className="rounded-xl bg-amber-700 px-4 py-3 text-sm font-semibold text-white hover:bg-amber-800 disabled:opacity-40">
          {ocupado ? "Iniciando…" : "Iniciar mantequilla"}
        </button>
      )}
      {accion.tipo === "cerrar" && puedeOperar && corridaId !== null && (
        <button type="button" disabled={!accion.habilitada} aria-describedby={describe} onClick={() => onCerrar(corridaId)} className="rounded-xl bg-green-700 px-4 py-3 text-sm font-semibold text-white hover:bg-green-800 disabled:opacity-40">Registrar balance y cerrar</button>
      )}
      {accion.motivo && (
        <p id={idMotivo} className="text-sm text-red-800">
          {accion.motivo}
          {fila.resolver_en && puedeIr(fila.resolver_en) && <>{" "}<Link to={fila.resolver_en} className="font-semibold underline">Ver dónde se resuelve</Link></>}
        </p>
      )}
      {fila.avisos.length > 0 && (
        <ul className="space-y-1 rounded-xl bg-amber-50 px-3 py-2 text-sm text-amber-900">
          {fila.avisos.map((aviso) => <li key={aviso}>{aviso}</li>)}
        </ul>
      )}
      {cancelable !== null && puedeOperar && (
        <button type="button" disabled={ocupado} onClick={() => onCancelar(fila)} className="self-start rounded-xl border border-slate-300 bg-white px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-100 disabled:opacity-40">Cancelar preparación</button>
      )}
    </article>
  );
}
```

- [ ] **Step 3: Formulario «Preparar mantequilla»** — `frontend/src/pages/Mantequilla/PrepararMantequilla.tsx`:

```tsx
import { useEffect, useId, useRef, useState, type FormEvent, type ReactNode } from "react";
import { X } from "lucide-react";
import { Link } from "react-router-dom";

import ConfirmarAccion from "../../components/operacion/ConfirmarAccion";
import { puedeAccederModulo } from "../../services/access-control";
import { mensajeErrorProceso } from "../../services/errores-proceso";
import { fechaLocalISO } from "../../services/fechas";
import { cantidad } from "../../services/formato";
import { prepararMantequilla, type PuestoMantequilla } from "../../services/mantequilla.service";
import { sugerirCodigoLote } from "../../services/produccion.service";
import { obtenerSesion } from "../../services/sesion";

const control = "mt-1 w-full rounded-xl border border-slate-300 bg-white px-3 py-2.5 text-sm outline-none focus:border-amber-600";
const ESTADO_CALIDAD = {
  pendiente: "pendiente de liberación",
  rechazado: "rechazada por Calidad",
  trazabilidad_incompleta: "con trazabilidad incompleta",
} as const;

/*
  «Preparar mantequilla»: crema → kg → OP → mantequera → mazada → código del
  lote de salida → confirmación. Cremas, órdenes, mantequeras y sueros vienen
  del puesto (`mantequillas/puesto/`), con las reglas que «Preparar» vuelve a
  aplicar; la ocupación no se calcula aquí. El código se sugiere con
  `codigo-sugerido/` (sigla de la mantequera y fecha de hoy) y queda
  editable. Preparar no inicia: la tarjeta habilita «Iniciar mantequilla»
  cuando el servidor lo permite.
*/
export default function PrepararMantequilla({ puesto, cremaInicial, equipoInicial, alCerrar, alPreparar }: {
  puesto: PuestoMantequilla;
  cremaInicial?: number;
  equipoInicial?: number;
  alCerrar: () => void;
  alPreparar: (codigo: string) => void;
}) {
  const libres = puesto.mantequeras.filter((item) => item.estado === "disponible" && item.motivos_para_tomar.length === 0);
  const [crema, setCrema] = useState(
    cremaInicial !== undefined && puesto.cremas.some((item) => item.id === cremaInicial) ? String(cremaInicial) : "",
  );
  const [kg, setKg] = useState("");
  const [orden, setOrden] = useState(puesto.ordenes.length === 1 ? String(puesto.ordenes[0].id) : "");
  const [equipo, setEquipo] = useState(
    equipoInicial !== undefined ? String(equipoInicial) : libres.length === 1 ? String(libres[0].equipo_id) : "",
  );
  const [suero, setSuero] = useState("");
  const [codigo, setCodigo] = useState("");
  const [notaCodigo, setNotaCodigo] = useState("");
  const codigoEditado = useRef(false);
  const [revisando, setRevisando] = useState(false);
  const [guardando, setGuardando] = useState(false);
  const [error, setError] = useState("");
  const enviando = useRef(false);
  const idTitulo = useId();

  useEffect(() => {
    if (!equipo) return;
    let vigente = true;
    // Diferido: un `setState` en el cuerpo del efecto encadena renders.
    const tarea = window.setTimeout(() => {
      sugerirCodigoLote(Number(equipo), fechaLocalISO())
        .then((sugerencia) => {
          // Una sugerencia tardía no pisa lo que el operador ya escribió.
          if (!vigente || codigoEditado.current) return;
          setCodigo(sugerencia.codigo ?? "");
          setNotaCodigo(sugerencia.motivo ?? "Sugerido por el sistema; puedes cambiarlo.");
        })
        .catch(() => {
          if (vigente) setNotaCodigo("Sin sugerencia: escribe el código del lote.");
        });
    }, 0);
    return () => { vigente = false; window.clearTimeout(tarea); };
  }, [equipo]);

  const elegida = puesto.cremas.find((item) => item.id === Number(crema));
  const pedidaPendiente = cremaInicial !== undefined
    ? puesto.cremas_pendientes_calidad.find((item) => item.id === cremaInicial)
    : undefined;
  const ordenElegida = puesto.ordenes.find((item) => item.id === Number(orden));
  const maquina = libres.find((item) => item.equipo_id === Number(equipo));
  const sueroElegido = puesto.sueros.find((item) => item.id === Number(suero));
  const excede = Boolean(elegida && Number(kg) > Number(elegida.disponible_kg));
  const completo = Boolean(elegida && Number(kg) > 0 && !excede && ordenElegida && maquina && codigo.trim());
  const usuario = obtenerSesion()?.usuario;

  const revisar = (evento: FormEvent) => {
    evento.preventDefault();
    if (completo) setRevisando(true);
  };

  const confirmar = async () => {
    if (enviando.current || !elegida || !ordenElegida || !maquina) return;
    enviando.current = true;
    setGuardando(true);
    setError("");
    try {
      const corrida = await prepararMantequilla({
        orden: ordenElegida.id, lote_crema: elegida.id, equipo: maquina.equipo_id,
        codigo_lote_mantequilla: codigo.trim(), kg_crema: Number(kg),
        ...(sueroElegido ? { lote_suero: sueroElegido.id } : {}),
      });
      alPreparar(corrida.ejecucion_codigo);
    } catch (causa) {
      setError(mensajeErrorProceso(causa, "No se pudo preparar la mantequilla."));
      setRevisando(false);
    } finally {
      enviando.current = false;
      setGuardando(false);
    }
  };

  return (
    <div className="fixed inset-0 z-[70] overflow-y-auto bg-slate-950/45 p-4" role="dialog" aria-modal="true" aria-labelledby={idTitulo}>
      <form onSubmit={revisar} className="mx-auto my-8 max-w-2xl space-y-5 rounded-2xl bg-white p-6 shadow-xl">
        <div className="flex items-start justify-between gap-4">
          <div>
            <p className="text-xs font-bold uppercase tracking-wider text-amber-700">Puesto de Mantequilla</p>
            <h2 id={idTitulo} className="mt-1 text-2xl font-bold text-slate-900">Preparar mantequilla</h2>
            <p className="mt-2 text-sm text-slate-600">Toma la mantequera y abre el lote de salida. La crema sale del TK cuando se inicia, desde la tarjeta.</p>
          </div>
          <button type="button" onClick={alCerrar} disabled={guardando} className="rounded-lg p-2 hover:bg-slate-100" aria-label="Cerrar"><X className="h-5 w-5" /></button>
        </div>

        {pedidaPendiente && (
          <p role="alert" className="rounded-xl bg-violet-50 px-4 py-3 text-sm text-violet-900">
            {pedidaPendiente.codigo} está {ESTADO_CALIDAD[pedidaPendiente.estado_calidad]}
            {pedidaPendiente.estado_calidad === "trazabilidad_incompleta" ? ` (origen ${pedidaPendiente.etapa_origen})` : ""}: no se puede preparar todavía.
            {puedeAccederModulo(usuario, "calidad") && <>{" "}<Link to="/calidad" className="font-semibold underline">Ir a Calidad</Link></>}
          </p>
        )}

        <fieldset className="grid gap-4 sm:grid-cols-2" disabled={revisando}>
          <Campo texto="Crema">
            <select required value={crema} onChange={(e) => setCrema(e.target.value)} className={control}>
              <option value="">Seleccionar…</option>
              {puesto.cremas.map((item) => (
                <option key={item.id} value={item.id}>
                  {item.codigo} · {cantidad(item.disponible_kg, "kg")} disponibles{item.tk ? ` · ${item.tk}` : ""}
                </option>
              ))}
            </select>
          </Campo>
          <Campo texto="Crema a utilizar (kg)">
            <input required type="number" min="0.001" step="0.001" max={elegida?.disponible_kg} value={kg} onChange={(e) => setKg(e.target.value)} className={control} />
          </Campo>
          <Campo texto="Orden de mantequilla">
            <select required value={orden} onChange={(e) => setOrden(e.target.value)} className={control}>
              <option value="">Seleccionar…</option>
              {puesto.ordenes.map((item) => <option key={item.id} value={item.id}>{item.codigo} · {item.producto}</option>)}
            </select>
          </Campo>
          <Campo texto="Mantequera">
            <select required value={equipo} onChange={(e) => setEquipo(e.target.value)} className={control}>
              <option value="">Seleccionar…</option>
              {libres.map((item) => <option key={item.equipo_id} value={item.equipo_id}>{item.codigo} · {item.nombre}</option>)}
            </select>
          </Campo>
          <Campo texto="Lote de suero / mazada (opcional)">
            <select value={suero} onChange={(e) => setSuero(e.target.value)} className={control}>
              <option value="">Sin recuperación de mazada</option>
              {puesto.sueros.map((item) => <option key={item.id} value={item.id}>{item.codigo} · {item.producto}</option>)}
            </select>
          </Campo>
          <Campo texto="Código del lote de mantequilla">
            <input required value={codigo} onChange={(e) => { codigoEditado.current = true; setCodigo(e.target.value.toUpperCase()); }} className={control} />
            {notaCodigo && <span className="mt-1 block text-xs font-normal text-slate-500">{notaCodigo}</span>}
          </Campo>
        </fieldset>
        {excede && elegida && <p className="rounded-xl bg-amber-50 px-4 py-3 text-sm text-amber-900">{elegida.codigo} tiene {cantidad(elegida.disponible_kg, "kg")} disponibles: «Preparar» lo va a rechazar.</p>}
        {libres.length === 0 && <p className="rounded-xl bg-amber-50 p-3 text-sm text-amber-900">No hay mantequeras disponibles: todas están preparadas, en curso o en CIP.</p>}
        {puesto.ordenes.length === 0 && (
          <p className="rounded-xl bg-amber-50 p-3 text-sm text-amber-900">
            No hay una OP de mantequilla programada.
            {puedeAccederModulo(usuario, "planificacion") && <>{" "}<Link to="/planificacion" className="font-semibold underline">Ir a Planificación</Link></>}
          </p>
        )}
        {puesto.cremas.length === 0 && !pedidaPendiente && <p className="rounded-xl bg-amber-50 p-3 text-sm text-amber-900">No hay crema liberada con saldo disponible.</p>}
        {error && !revisando && <p role="alert" className="rounded-xl bg-red-50 px-4 py-3 text-sm text-red-800">{error}</p>}

        {revisando && elegida && ordenElegida && maquina ? (
          <ConfirmarAccion
            titulo="Preparar la mantequilla"
            filas={[
              { etiqueta: "Crema", valor: `${elegida.codigo} · ${cantidad(kg, "kg")}${elegida.tk ? ` desde ${elegida.tk}` : ""}` },
              { etiqueta: "Orden", valor: `${ordenElegida.codigo} · ${ordenElegida.producto}` },
              { etiqueta: "Mantequera", valor: maquina.nombre },
              { etiqueta: "Mazada", valor: sueroElegido ? sueroElegido.codigo : "Sin recuperación" },
              { etiqueta: "Lote de salida", valor: codigo.trim() },
            ]}
            advertencia="La mantequera queda tomada hasta que se inicie o se cancele la preparación."
            textoConfirmar="Preparar mantequilla"
            ocupado={guardando}
            error={error}
            onConfirmar={() => void confirmar()}
            onVolver={() => setRevisando(false)}
          />
        ) : (
          <div className="flex justify-end gap-3">
            <button type="button" onClick={alCerrar} className="rounded-xl border border-slate-300 px-4 py-2.5 text-sm font-semibold text-slate-700">Cancelar</button>
            <button type="submit" disabled={!completo} className="rounded-xl bg-amber-700 px-5 py-2.5 text-sm font-semibold text-white disabled:opacity-40">Revisar y confirmar</button>
          </div>
        )}
      </form>
    </div>
  );
}

function Campo({ texto, children }: { texto: string; children: ReactNode }) {
  return <label className="text-sm font-medium text-slate-700">{texto}{children}</label>;
}
```

- [ ] **Step 4: Cierre con el balance del servidor** — `frontend/src/pages/Mantequilla/CierreMantequilla.tsx`:

```tsx
import { useEffect, useId, useRef, useState, type ChangeEvent, type FormEvent, type ReactNode } from "react";
import { X } from "lucide-react";

import ConfirmarAccion from "../../components/operacion/ConfirmarAccion";
import { mensajeErrorProceso } from "../../services/errores-proceso";
import { cantidad } from "../../services/formato";
import {
  cerrarMantequilla, revisarCierreMantequilla,
  type RevisionCierreMantequilla, type ValoresCierreMantequilla,
} from "../../services/mantequilla.service";
import type { CorridaMantequilla } from "../../services/procesos.service";
import { estadoDelBalance } from "../../services/puesto-mantequilla";

type Campos = {
  mantequilla: string; suero: string; merma: string; reproceso: string;
  motivoReproceso: string; humedad: string;
};
const VACIO: Campos = { mantequilla: "", suero: "", merma: "", reproceso: "", motivoReproceso: "", humedad: "" };
const control = "mt-1 w-full rounded-xl border border-slate-300 bg-white px-3 py-2.5 text-sm outline-none focus:border-amber-600";
const FRANJA = {
  completo: "bg-emerald-50 text-emerald-900",
  incompleto: "bg-amber-50 text-amber-900",
  excedido: "bg-rose-50 text-rose-800",
  revisando: "bg-slate-50 text-slate-600",
  sin_revision: "bg-slate-50 text-slate-600",
} as const;

function aValores(campos: Campos): ValoresCierreMantequilla {
  const numero = (texto: string) => (texto.trim() === "" ? null : Number(texto));
  return {
    kg_mantequilla: numero(campos.mantequilla),
    kg_suero: numero(campos.suero),
    kg_merma: numero(campos.merma),
    kg_reproceso: numero(campos.reproceso),
    motivo_reproceso: campos.motivoReproceso.trim(),
  };
}

/*
  «Registrar balance y cerrar». El balance lo decide el servidor mientras se
  teclea (`revisar-cierre/`, que no escribe) con la misma función que valida
  el cierre (`balance_mantequilla`). El cliente no calcula nada: «Revisar
  cierre» se habilita solo con la última revisión de los valores actuales,
  que cuadra y no trae errores.
*/
export default function CierreMantequilla({ corrida, alCerrar, alCompletarse }: {
  corrida: CorridaMantequilla;
  alCerrar: () => void;
  alCompletarse: (corrida: CorridaMantequilla) => void;
}) {
  const [campos, setCampos] = useState<Campos>(VACIO);
  const [revision, setRevision] = useState<RevisionCierreMantequilla | null>(null);
  // Pendiente desde la tecla hasta que responde la revisión de lo tecleado:
  // mientras tanto, la anterior ya no habla de lo que se va a cerrar.
  const [revisionPendiente, setRevisionPendiente] = useState(true);
  const [errorRevision, setErrorRevision] = useState(false);
  const [revisando, setRevisando] = useState(false);
  const [guardando, setGuardando] = useState(false);
  const [error, setError] = useState("");
  const enviando = useRef(false);
  const idTitulo = useId();

  useEffect(() => {
    let vigente = true;
    // Con retardo: una consulta por pausa al teclear, no una por tecla.
    const tarea = window.setTimeout(() => {
      revisarCierreMantequilla(corrida.id, aValores(campos))
        .then((datos) => {
          if (!vigente) return;
          setRevision(datos);
          setErrorRevision(false);
          setRevisionPendiente(false);
        })
        .catch(() => {
          if (!vigente) return;
          setRevision(null);
          setErrorRevision(true);
          setRevisionPendiente(false);
        });
    }, 400);
    return () => { vigente = false; window.clearTimeout(tarea); };
  }, [corrida.id, campos]);

  const balance = estadoDelBalance(revision, revisionPendiente, errorRevision);
  const conReproceso = Number(campos.reproceso || 0) > 0;
  const cambiar = (clave: keyof Campos) => (evento: ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) => {
    const valor = evento.target.value;
    setRevisionPendiente(true);
    setCampos((actual) => ({ ...actual, [clave]: valor }));
  };

  const revisar = (evento: FormEvent) => {
    evento.preventDefault();
    if (balance.puedeCerrar) setRevisando(true);
  };

  const confirmar = async () => {
    if (enviando.current) return;
    enviando.current = true;
    setGuardando(true);
    setError("");
    try {
      const cerrada = await cerrarMantequilla(corrida.id, {
        kg_mantequilla: Number(campos.mantequilla),
        kg_suero: Number(campos.suero || 0),
        kg_merma: Number(campos.merma || 0),
        kg_reproceso: Number(campos.reproceso || 0),
        motivo_reproceso: campos.motivoReproceso.trim(),
        controles: campos.humedad ? { humedad: Number(campos.humedad) } : {},
      });
      alCompletarse(cerrada);
    } catch (causa) {
      setError(mensajeErrorProceso(causa, "No se pudo cerrar la corrida de mantequilla."));
      setRevisando(false);
    } finally {
      enviando.current = false;
      setGuardando(false);
    }
  };

  return (
    <div className="fixed inset-0 z-[70] overflow-y-auto bg-slate-950/45 p-4" role="dialog" aria-modal="true" aria-labelledby={idTitulo}>
      <form onSubmit={revisar} className="mx-auto my-8 max-w-2xl space-y-5 rounded-2xl bg-white p-6 shadow-xl">
        <div className="flex items-start justify-between gap-4">
          <div>
            <p className="font-mono text-xs font-semibold text-amber-700">{corrida.ejecucion_codigo}</p>
            <h2 id={idTitulo} className="mt-1 text-2xl font-bold text-slate-900">Registrar balance y cerrar</h2>
            <p className="mt-2 text-sm text-slate-600">Crema {corrida.crema_codigo} · {cantidad(corrida.kg_crema, "kg")} → lote {corrida.mantequilla_codigo}.</p>
          </div>
          <button type="button" onClick={alCerrar} disabled={guardando} className="rounded-lg p-2 hover:bg-slate-100" aria-label="Cerrar"><X className="h-5 w-5" /></button>
        </div>
        <fieldset className="grid gap-4 sm:grid-cols-2" disabled={revisando}>
          <Campo texto="Mantequilla producida (kg)"><input required type="number" min="0.001" step="0.001" value={campos.mantequilla} onChange={cambiar("mantequilla")} className={control} /></Campo>
          <Campo texto="Suero / mazada recuperada (kg)">
            <input type="number" min="0" step="0.001" disabled={!corrida.lote_suero} value={campos.suero} onChange={cambiar("suero")} className={`${control} disabled:bg-slate-100 disabled:text-slate-500`} />
            {!corrida.lote_suero && <span className="mt-1 block text-xs font-normal text-slate-600">Esta corrida no tiene un lote de suero asociado: registra 0 kg.</span>}
          </Campo>
          <Campo texto="Merma medida (kg)"><input type="number" min="0" step="0.001" value={campos.merma} onChange={cambiar("merma")} className={control} /></Campo>
          <Campo texto="Material segregado para reproceso (kg)"><input type="number" min="0" step="0.001" value={campos.reproceso} onChange={cambiar("reproceso")} className={control} /></Campo>
          {conReproceso && (
            <label className="text-sm font-medium text-slate-700 sm:col-span-2">
              Motivo del reproceso
              <textarea required maxLength={250} rows={3} value={campos.motivoReproceso} onChange={cambiar("motivoReproceso")} className={control} placeholder="Ej.: textura fuera de objetivo; segregar para evaluación de Calidad" />
              <span className="mt-1 block text-xs font-normal text-slate-500">Se creará un lote separado y pendiente de la decisión de Calidad.</span>
            </label>
          )}
          <Campo texto="Humedad (%)"><input type="number" min="0" max="100" step="0.01" value={campos.humedad} onChange={cambiar("humedad")} className={control} /></Campo>
        </fieldset>

        <section aria-label="Balance del cierre" aria-live="polite" className={`rounded-xl px-4 py-3 text-sm ${FRANJA[balance.franja]}`}>
          <p className="font-semibold">{balance.titulo}</p>
          {balance.detalle && <p className="mt-1">{balance.detalle}</p>}
          {balance.errores.length > 0 && <ul className="mt-1 space-y-1">{balance.errores.map((texto) => <li key={texto}>{texto}</li>)}</ul>}
        </section>

        {error && !revisando && <p role="alert" className="rounded-xl bg-red-50 px-4 py-3 text-sm text-red-800">{error}</p>}
        {revisando ? (
          <ConfirmarAccion
            titulo="Cerrar la corrida de mantequilla"
            filas={[
              { etiqueta: "Crema", valor: `${corrida.crema_codigo} · ${cantidad(corrida.kg_crema, "kg")}` },
              { etiqueta: "Mantequilla", valor: `${corrida.mantequilla_codigo} · ${cantidad(campos.mantequilla, "kg")}` },
              { etiqueta: "Suero / mazada", valor: cantidad(campos.suero || 0, "kg") },
              { etiqueta: "Merma", valor: cantidad(campos.merma || 0, "kg") },
              { etiqueta: "Reproceso", valor: conReproceso ? `${cantidad(campos.reproceso, "kg")} · ${campos.motivoReproceso.trim()}` : "Sin reproceso" },
            ]}
            advertencia="La mantequilla queda pendiente de Calidad y el lote se declara producido: se descuenta su material de envase."
            textoConfirmar="Cerrar y enviar a Calidad"
            ocupado={guardando}
            error={error}
            onConfirmar={() => void confirmar()}
            onVolver={() => setRevisando(false)}
          />
        ) : (
          <div className="flex justify-end gap-3">
            <button type="button" onClick={alCerrar} className="rounded-xl border border-slate-300 px-4 py-2.5 text-sm font-semibold text-slate-700">Cancelar</button>
            <button type="submit" disabled={!balance.puedeCerrar} className="rounded-xl bg-green-700 px-5 py-2.5 text-sm font-semibold text-white disabled:opacity-40">Revisar cierre</button>
          </div>
        )}
      </form>
    </div>
  );
}

function Campo({ texto, children }: { texto: string; children: ReactNode }) {
  return <label className="text-sm font-medium text-slate-700">{texto}{children}</label>;
}
```

- [ ] **Step 5: La página del puesto** — `frontend/src/pages/Mantequilla/PuestoMantequilla.tsx`:

```tsx
import { useState } from "react";
import { useSearchParams } from "react-router-dom";
import { Plus, RefreshCw } from "lucide-react";

import CancelarPreparacion from "../../components/operacion/CancelarPreparacion";
import { mensajeDe, useCarga } from "../../components/seccion/utilidades";
import { mensajeErrorProceso } from "../../services/errores-proceso";
import { cantidad } from "../../services/formato";
import {
  buscarMantequillas, cancelarPreparacionMantequilla, iniciarMantequilla,
  obtenerMantequilla, obtenerPuestoMantequilla, type MantequeraPuesto,
} from "../../services/mantequilla.service";
import { puedeOperarMantequilla } from "../../services/permisos-mantequilla";
import type { CorridaMantequilla } from "../../services/procesos.service";
import { corridaCancelable } from "../../services/puesto-mantequilla";
import { obtenerSesion } from "../../services/sesion";
import TablaConsulta from "../Inventario/TablaConsulta";
import CierreMantequilla from "./CierreMantequilla";
import PrepararMantequilla from "./PrepararMantequilla";
import TarjetaMantequera from "./TarjetaMantequera";

type Cancelando = {
  id: number; codigo: string; advertencia: string; filas: { etiqueta: string; valor: string }[];
} | null;

const fecha = (iso: string | null) => (iso ? new Date(iso).toLocaleString("es-CL") : "—");
const advertenciaDe = (lote: string | null) =>
  `Se anulará el lote ${lote ?? "de salida"} y la mantequera quedará libre. No se mueve crema: entra a la mantequera recién al iniciar.`;

/*
  Puesto de Mantequilla: preparar una corrida sobre una mantequera (que la
  toma), iniciarla cuando el servidor lo permite, cancelar una preparación y
  registrar el balance, en una pantalla. Antes era una sección de /procesos
  con dos modales y un «Iniciar» que siempre se ofrecía.
*/
export default function PuestoMantequilla() {
  const puesto = useCarga(obtenerPuestoMantequilla);
  const [parametros, setParametros] = useSearchParams();
  const cremaPedida = Number(parametros.get("crema"));
  const cremaInicial = Number.isInteger(cremaPedida) && cremaPedida > 0 ? cremaPedida : undefined;
  const [preparando, setPreparando] = useState<{ equipoId?: number } | null>(null);
  const [iniciando, setIniciando] = useState<number | null>(null);
  const [cerrando, setCerrando] = useState<CorridaMantequilla | null>(null);
  const [cancelando, setCancelando] = useState<Cancelando>(null);
  const [versionHistorial, setVersionHistorial] = useState(0);
  const [mensaje, setMensaje] = useState("");
  const [error, setError] = useState("");
  // Mismo criterio que el servidor (`puede_operar_tipo` con la etapa Mantequilla).
  const puedeOperar = puedeOperarMantequilla(obtenerSesion()?.usuario);
  // «Preparar en Mantequilla» llega con `?crema=`: el formulario se abre solo, con esa crema.
  const formulario: { equipoId?: number } | null =
    preparando ?? (cremaInicial !== undefined && puedeOperar ? {} : null);

  const cerrarFormulario = () => {
    setPreparando(null);
    if (cremaInicial !== undefined) setParametros({}, { replace: true });
  };

  const iniciar = async (corridaId: number) => {
    setMensaje("");
    setError("");
    setIniciando(corridaId);
    try {
      const corrida = await iniciarMantequilla(corridaId);
      setMensaje(`Mantequilla ${corrida.ejecucion_codigo} iniciada en ${corrida.equipo_nombre ?? "la mantequera"}.`);
    } catch (causa) {
      setError(mensajeErrorProceso(causa, "No se pudo iniciar la mantequilla."));
    } finally {
      setIniciando(null);
      await puesto.recargar();
    }
  };

  const abrirCierre = async (corridaId: number) => {
    setMensaje("");
    setError("");
    try {
      setCerrando(await obtenerMantequilla(corridaId));
    } catch (causa) {
      setError(mensajeDe(causa, "No se pudo cargar la corrida."));
    }
  };

  const cancelarDesdeTarjeta = (fila: MantequeraPuesto) => {
    const corrida = fila.corrida;
    const id = corridaCancelable(corrida);
    if (!corrida || id === null) return;
    setCancelando({
      id, codigo: corrida.ejecucion_codigo, advertencia: advertenciaDe(corrida.lote_mantequilla),
      filas: [
        { etiqueta: "Mantequera", valor: fila.nombre },
        { etiqueta: "Crema", valor: `${corrida.lote_crema ?? "—"} · ${cantidad(corrida.kg_crema, "kg")}` },
        { etiqueta: "Lote de salida", valor: corrida.lote_mantequilla ?? "—" },
      ],
    });
  };

  const cancelarDesdeHistorial = (corrida: CorridaMantequilla) => {
    const id = corridaCancelable(corrida);
    if (id === null) return;
    setCancelando({
      id, codigo: corrida.ejecucion_codigo, advertencia: advertenciaDe(corrida.mantequilla_codigo),
      filas: [
        { etiqueta: "Mantequera", valor: corrida.equipo_nombre ?? "—" },
        { etiqueta: "Crema", valor: `${corrida.crema_codigo} · ${cantidad(corrida.kg_crema, "kg")}` },
        { etiqueta: "Lote de salida", valor: corrida.mantequilla_codigo },
      ],
    });
  };

  /* El modal muestra el error del servidor: por eso aquí se relanza. */
  const cancelar = async (motivo: string) => {
    if (!cancelando) return;
    const cancelada = await cancelarPreparacionMantequilla(cancelando.id, motivo);
    setCancelando(null);
    setMensaje(`Preparación ${cancelada.ejecucion_codigo} cancelada: el lote de salida quedó anulado y la mantequera libre.`);
    setVersionHistorial((version) => version + 1);
    await puesto.recargar();
  };

  return (
    <main className="px-4 py-8 sm:px-8">
      <div className="mx-auto max-w-6xl space-y-6">
        <header className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <p className="text-sm font-semibold uppercase tracking-wider text-amber-700">Puesto de trabajo</p>
            <h1 className="mt-1 text-3xl font-bold text-slate-900">Mantequilla</h1>
            <p className="mt-2 max-w-2xl text-slate-600">Prepara una corrida con crema liberada; luego inicia y registra el balance desde la tarjeta de la mantequera.</p>
            {!puedeOperar && <p className="mt-2 text-sm font-medium text-slate-600">Vista de consulta: las acciones las registra Condensación.</p>}
          </div>
          <div className="flex items-center gap-2">
            <button type="button" onClick={() => void puesto.recargar()} aria-label="Actualizar" title="Actualizar" className="rounded-xl border border-slate-300 bg-white p-3 text-slate-600 hover:border-amber-400 hover:text-amber-700">
              <RefreshCw className="h-5 w-5" />
            </button>
            {puedeOperar && (
              <button type="button" onClick={() => { setMensaje(""); setPreparando({}); }} className="inline-flex items-center gap-2 rounded-xl bg-amber-700 px-5 py-3 text-sm font-semibold text-white hover:bg-amber-800">
                <Plus className="h-5 w-5" />Preparar mantequilla
              </button>
            )}
          </div>
        </header>

        {mensaje && <p role="status" className="rounded-xl border border-green-200 bg-green-50 px-4 py-3 text-sm text-green-900">{mensaje}</p>}
        {error && <p role="alert" className="rounded-xl bg-red-50 px-4 py-3 text-sm text-red-800">{error}</p>}
        {puesto.error && <p role="alert" className="text-sm text-red-800">{puesto.error}</p>}
        {puesto.cargando && !puesto.datos && <p className="text-sm text-slate-600">Cargando mantequeras…</p>}
        {puesto.datos && puesto.datos.mantequeras.length === 0 && (
          <p className="rounded-xl bg-amber-50 px-4 py-3 text-sm text-amber-900">No hay mantequeras activas: créalas en Maestros › Máquinas con tipo «Mantequera».</p>
        )}

        <section aria-label="Mantequeras" className="grid gap-4 md:grid-cols-2">
          <h2 className="sr-only">Mantequeras</h2>
          {puesto.datos?.mantequeras.map((fila) => (
            <TarjetaMantequera
              key={fila.equipo_id}
              fila={fila}
              ocupado={iniciando !== null && iniciando === fila.corrida?.id}
              puedeOperar={puedeOperar}
              onPreparar={(equipoId) => { setMensaje(""); setPreparando({ equipoId }); }}
              onIniciar={(id) => void iniciar(id)}
              onCerrar={(id) => void abrirCierre(id)}
              onCancelar={cancelarDesdeTarjeta}
            />
          ))}
        </section>

        <section aria-label="Corridas de hoy" className="space-y-2">
          <h2 className="text-lg font-semibold text-slate-900">Corridas de hoy</h2>
          {puesto.datos && puesto.datos.corridas_de_hoy.length === 0 && <p className="text-sm text-slate-600">Hoy no hay corridas de mantequilla.</p>}
          {puesto.datos && puesto.datos.corridas_de_hoy.length > 0 && (
            <ul className="divide-y divide-slate-100 rounded-2xl border border-slate-200 bg-white">
              {puesto.datos.corridas_de_hoy.map((c) => (
                <li key={c.id} className="flex flex-wrap justify-between gap-2 px-5 py-3 text-sm">
                  <span><span className="font-mono">{c.ejecucion_codigo}</span> · {c.equipo ?? "—"} · {c.lote_crema} → {c.lote_mantequilla}</span>
                  <span className="text-slate-700">{c.situacion_etiqueta}</span>
                </li>
              ))}
            </ul>
          )}
        </section>

        <section aria-label="Historial de Mantequilla" className="space-y-3">
          <h2 className="text-lg font-semibold text-slate-900">Historial</h2>
          <TablaConsulta<CorridaMantequilla>
            key={versionHistorial}
            titulo="Historial de corridas de mantequilla"
            cargar={buscarMantequillas}
            clave={(f) => f.id}
            ubicaciones={[]}
            conUbicacion={false}
            conFechas
            etiquetaBusqueda="Corrida, lote u OP"
            vacio="No hay corridas que coincidan."
            estados={(puesto.datos?.estados ?? []).map((o) => ({ valor: o.valor, texto: o.etiqueta }))}
            columnas={[
              { titulo: "Corrida", celda: (f) => <span className="font-mono">{f.ejecucion_codigo}</span> },
              { titulo: "Mantequera", celda: (f) => f.equipo_nombre ?? "—" },
              { titulo: "Crema", celda: (f) => `${f.crema_codigo} · ${cantidad(f.kg_crema, "kg")}` },
              { titulo: "Lote de salida", celda: (f) => f.mantequilla_codigo },
              { titulo: "Inicio", celda: (f) => fecha(f.iniciada_en) },
              { titulo: "Situación", celda: (f) => f.situacion_etiqueta },
              {
                titulo: "Acción",
                celda: (f) => puedeOperar && corridaCancelable(f) !== null
                  ? <button type="button" onClick={() => cancelarDesdeHistorial(f)} className="text-xs font-semibold text-slate-700 underline">Cancelar preparación</button>
                  : null,
              },
            ]}
          />
        </section>
      </div>

      {formulario !== null && puesto.datos && (
        <PrepararMantequilla
          puesto={puesto.datos}
          cremaInicial={cremaInicial}
          equipoInicial={formulario.equipoId}
          alCerrar={cerrarFormulario}
          alPreparar={(codigo) => {
            cerrarFormulario();
            setMensaje(`Mantequilla ${codigo} preparada: la mantequera quedó tomada. Iníciala desde la tarjeta cuando el servidor lo permita.`);
            setVersionHistorial((version) => version + 1);
            void puesto.recargar();
          }}
        />
      )}
      {cerrando && (
        <CierreMantequilla
          corrida={cerrando}
          alCerrar={() => setCerrando(null)}
          alCompletarse={(corrida) => {
            setCerrando(null);
            setMensaje(`Corrida ${corrida.ejecucion_codigo} cerrada; la mantequilla pasa a Calidad.`);
            setVersionHistorial((version) => version + 1);
            void puesto.recargar();
          }}
        />
      )}
      {cancelando && (
        <CancelarPreparacion
          codigo={cancelando.codigo}
          filas={cancelando.filas}
          advertencia={cancelando.advertencia}
          alVolver={() => setCancelando(null)}
          alCancelar={cancelar}
        />
      )}
    </main>
  );
}
```

- [ ] **Step 6: Ruta, menú y destinos**
  - `frontend/src/app/routes.tsx`: `const PuestoMantequilla = lazy(() => import("../pages/Mantequilla/PuestoMantequilla"));` junto a `PuestoDescremado`, y dentro de `<Route element={<RutaModulo modulo="produccion" />}>`, debajo de `/produccion/descremado`: `<Route path="/produccion/mantequilla" element={diferido(<PuestoMantequilla />)} />`.
  - `frontend/src/services/navegacion-operacional.ts`, entrada «Mantequilla»:

```ts
      { etiqueta: "Mantequilla", ruta: "/produccion/mantequilla", modulo: "produccion", icono: "produccion", nivel: "proceso", areas: ["condensacion", "calidad"], alias: ["/procesos?seccion=mantequilla"] },
```

    y en el comentario de `esRutaOperacionalActual` («Mantequilla y Trazabilidad viven en /procesos con…») cambia a «Trazabilidad vive en /procesos con…», y agrega «Mantequilla tampoco, desde su puesto (/produccion/mantequilla)» junto a la mención de Descremado.
  - `frontend/src/services/planta-ahora.ts`, `RUTAS_ETAPA`: `mantequilla: "/produccion/mantequilla",`.
  - Backend `backend/procesos/dominio.py`, `RUTAS_POR_ETAPA`: `"mantequilla": "/produccion/mantequilla",`; `backend/procesos/tests_destinos.py`: el esperado de `"mantequilla"` igual.
  - `frontend/tests/planta-ahora.test.ts`: `assert.equal(rutaDeEtapa("mantequilla"), "/produccion/mantequilla");`.
  - `frontend/tests/navegacion-operacional.test.ts`: reemplaza el cuerpo de `test("la ubicación distingue subprocesos que comparten una URL", …)` por:

```ts
  const usuario = usuarioDeArea("condensacion", "Condensación", "produccion");

  assert.ok(esRutaOperacionalActual(
    "/procesos?seccion=trazabilidad",
    "/procesos",
    "?seccion=trazabilidad",
  ));
  assert.ok(!esRutaOperacionalActual(
    "/procesos?seccion=trazabilidad",
    "/procesos",
    "?seccion=rework",
  ));
  assert.equal(
    contextoOperacionalPara(usuario, "/procesos", "?seccion=trazabilidad").actual.etiqueta,
    "Trazabilidad productiva",
  );
```

    y agrega, después del de Descremado:

```ts
test("Mantequilla tiene su propio puesto; el enlace viejo lo sigue marcando", () => {
  const usuario = usuarioDeArea("condensacion", "Condensación", "produccion");
  const mantequilla = navegacionPara(usuario).grupos
    .flatMap((grupo) => grupo.enlaces)
    .find((enlace) => enlace.etiqueta === "Mantequilla");

  assert.equal(mantequilla?.ruta, "/produccion/mantequilla");
  assert.equal(mantequilla?.modulo, "produccion");
  assert.ok(mantequilla && esEnlaceOperacionalActual(mantequilla, "/produccion/mantequilla"));
  // `/procesos?seccion=mantequilla` redirige al puesto; mientras tanto, el
  // menú marca la misma entrada.
  assert.ok(mantequilla && esEnlaceOperacionalActual(mantequilla, "/procesos", "?seccion=mantequilla"));
  assert.equal(
    contextoOperacionalPara(usuario, "/produccion/mantequilla").actual.etiqueta,
    "Mantequilla",
  );
});
```

- [ ] **Step 7: Retirar lo viejo**
  - `git rm frontend/src/pages/Procesos/NuevaMantequilla.tsx frontend/src/pages/Procesos/CierreMantequilla.tsx frontend/src/services/balance-mantequilla.ts frontend/tests/balance-mantequilla.test.ts` (sus casos de prueba viven en `BalanceMantequillaDominioTests`, Task 2).
  - `frontend/src/pages/Procesos/Procesos.tsx`:
    - En el import de `procesos.service` quita `iniciarMantequilla`, `obtenerMantequillas` y `type CorridaMantequilla`; quita los imports de `CierreMantequilla` y `NuevaMantequilla`.
    - Quita los estados `mantequillas`, `mantequillasCargadas`, `cerrandoMantequilla`, `accionandoCorrida`, `nuevaMantequilla`, y las funciones `actualizarMantequilla`, `iniciarCorrida` y `cargarMantequillas`.
    - En el bloque de redirecciones (después de todos los hooks), debajo del de Descremado:

```tsx
  // Mantequilla también tiene puesto propio: un enlace guardado o una
  // notificación con `?seccion=mantequilla` aterriza en el puesto.
  if (seccionSolicitada === "mantequilla") {
    return <Navigate to="/produccion/mantequilla" replace />;
  }
```

    - Quita las dos líneas de modales (`CierreMantequilla` y `NuevaMantequilla`) y la `<section id="proceso-mantequilla">` completa. «Ejecuciones operativas» ya usa `textoIniciarEnPuesto`: con la Task 6 muestra «Iniciar en el puesto de Mantequilla» sin más cambios.
  - `frontend/src/pages/Produccion/Produccion.tsx:271`: `to="/produccion/mantequilla"`.
  - `frontend/src/pages/Produccion/SalidasIntermedias.tsx:229`: `to={salida.lote_id ? `/produccion/mantequilla?crema=${salida.lote_id}` : "/produccion/mantequilla"}`.
  - `frontend/src/pages/Leche/Silos.tsx:336-337`: `? (material.lote_id ? `/produccion/mantequilla?crema=${material.lote_id}` : "/produccion/mantequilla")`.
  - `frontend/src/services/procesos.service.ts`: elimina `OpcionesAltaMantequilla`, `obtenerMantequillas`, `iniciarMantequilla`, `cerrarMantequilla`, `obtenerOpcionesAltaMantequilla` y `crearMantequillaGuiada` (viven en `mantequilla.service.ts`).
  - Comprueba: `grep -rn "seccion=mantequilla\|NuevaMantequilla\|balance-mantequilla\|calcularBalanceMantequilla\|obtenerOpcionesAltaMantequilla\|crearMantequillaGuiada\|obtenerMantequillas\|pages/Descremado/CancelarPreparacion" frontend/src frontend/tests` → solo el `alias` del menú, el `Navigate` de `Procesos.tsx` y la prueba del menú.

- [ ] **Step 8: Backend: `opciones-alta/` se elimina y la acción se rotula** — en `backend/procesos/views.py`:
  - Borra `CorridaMantequillaViewSet.opciones_alta` completa (y los imports que queden sin uso: comprueba `Coalesce`, `DecimalField`, `Value`, `preparacion_cancelada` con `grep -n` antes de quitarlos; otros viewsets los usan).
  - En `acciones_permitidas` de `SalidaProcesoViewSet.disponibles`: `EtapaProceso.Tipo.MANTEQUILLA: "Iniciar Mantequilla",` → `EtapaProceso.Tipo.MANTEQUILLA: "Preparar en Mantequilla",` (el código `iniciar_mantequilla` no cambia: lo leen `Silos.tsx` y `SalidasIntermedias.tsx`).

  En `tests_puesto_mantequilla.py`, `PuestoMantequillaTests`:

```python
    def test_opciones_alta_ya_no_existe(self):
        # Lo que servía lo sirve `puesto/`, con la regla de ocupación del
        # servidor: una segunda fuente es lo que dejó al cliente decidirla.
        respuesta = self.cliente().get("/api/procesos/mantequillas/opciones-alta/")

        self.assertEqual(respuesta.status_code, 404)
```

  (Sin la acción, el router resuelve `opciones-alta` como un `pk` que no existe: 404.)

- [ ] **Step 9: `CLAUDE.md`** — en «Decisiones vigentes», justo después del punto «Descremado tiene puesto propio», agrega:

```markdown
- **Mantequilla tiene puesto propio** (desde 2026-10-08, `docs/superpowers/specs/2026-10-08-puesto-mantequilla-design.md`): `/produccion/mantequilla`, bajo el módulo `produccion`; «Preparar en Mantequilla» de Silos y de Salidas intermedias lleva ahí con `?crema=<lote>`, y `/procesos?seccion=mantequilla` redirige. **La mantequera es un tipo de máquina** (`Equipo.Tipo.MANTEQUERA`): `maestros.0040` reclasificó la `linea_mantequilla` sembrada y las líneas que solo usó Mantequilla, y las sacó de los formatos de envasado —la mantequilla se envasa en una envasadora (`preparar_circuito_mantequilla` asegura `envasadora_mantequilla`)—. **Preparar e iniciar son dos pasos.** «Preparar mantequilla» (`mantequillas/crear-guiada/`) crea el lote de salida (código sugerido por `codigo-sugerido/`, editable), la ejecución `EJ-MANT-{lote}` y la corrida, y toma la mantequera en una sola transacción —todo o nada—; valida la crema con las mismas funciones que el inicio (`motivos_crema_para_mantequilla`; `kg_crema_disponible` resta lo que pidieron otras corridas preparadas) y no la mueve: la crema sale del TK al iniciar. «Iniciar» lo habilita el servidor: `motivos_tipados_para_iniciar_mantequilla` es la única implementación, la usa `iniciar_mantequilla` y la sirve `mantequillas/puesto/` con dónde se resuelve cada motivo (`/calidad`, `/silos`, `/calidad/inocuidad`, `/planificacion`); la crema tiene que estar liberada por Calidad esté o no en un TK. `ejecuciones/{id}/transicionar/` rechaza iniciar una Mantequilla («Las corridas de mantequilla se inician desde el puesto de Mantequilla.», `MENSAJES_INICIO_EN_PUESTO`) y `preparar-continuacion` ya no crea ejecuciones de Mantequilla sin corrida. **Cancelar preparación** (`mantequillas/{id}/cancelar-preparacion/`, motivo obligatorio) deja la corrida `anulada` y anula su lote de salida con `anular_lote`; cancelar la ejecución por cualquier camino —bandeja o `PATCH` del lote— deja lo mismo (`_deshacer_preparacion_mantequilla`), y el suero de una corrida anulada vuelve a ofrecerse (`sueros_libres`). **El balance del cierre lo decide el servidor, una vez**: `procesos.dominio.balance_mantequilla` lo usan `CorridaMantequilla.clean()`, `cerrar_mantequilla` (antes de escribir) y `revisar-cierre/`, que el formulario pide mientras se teclea; el cliente no calcula. `opciones-alta/` se eliminó: lo sirve `puesto/`. Operar exige la etapa Mantequilla (área Condensación) en todos los caminos; Calidad consulta.
```

  y al final del punto «Una sola representación de «equipo»» agrega: «Desde 2026-10-08 la mantequera es un tipo propio (`mantequera`), por la misma razón: una línea de envasado no debe aparecer como mantequera ni la mantequera como línea de envasado (`maestros.0040`).»

- [ ] **Step 10: Verificar** — frontend: `cd frontend && npx tsc -b --pretty false && npx eslint . && npm test`; backend: `cd backend && DJANGO_ENV=test ./.venv/Scripts/python.exe manage.py test procesos --noinput`.
Expected: sin errores / OK.

- [ ] **Step 11: Commit** (revisa `git status` antes; agrega por nombre; el movimiento y las eliminaciones ya quedaron preparados por `git mv`/`git rm`):

```bash
git add frontend/src/components/operacion/CancelarPreparacion.tsx frontend/src/pages/Mantequilla/PuestoMantequilla.tsx frontend/src/pages/Mantequilla/TarjetaMantequera.tsx frontend/src/pages/Mantequilla/PrepararMantequilla.tsx frontend/src/pages/Mantequilla/CierreMantequilla.tsx frontend/src/pages/Descremado/PuestoDescremado.tsx frontend/src/pages/Procesos/Procesos.tsx frontend/src/pages/Produccion/Produccion.tsx frontend/src/pages/Produccion/SalidasIntermedias.tsx frontend/src/pages/Leche/Silos.tsx frontend/src/app/routes.tsx frontend/src/services/navegacion-operacional.ts frontend/src/services/planta-ahora.ts frontend/src/services/procesos.service.ts frontend/tests/navegacion-operacional.test.ts frontend/tests/planta-ahora.test.ts backend/procesos/views.py backend/procesos/dominio.py backend/procesos/tests_destinos.py backend/procesos/tests_puesto_mantequilla.py CLAUDE.md
git commit -m "feat(mantequilla): puesto de Mantequilla; la mantequilla sale de /procesos"
```

---

### Task 8: E2E y aceptación (controlador + implementador)

**Files:**
- Modify: `frontend/e2e/flujo-mantequilla.spec.ts` (reescritura de la primera prueba, una nueva de cancelación; el envasado elige la envasadora)
- Modify: `frontend/e2e/flujo-descremado.spec.ts` (`:258`, `:306`, `:345`: etiqueta del enlace)
- Modify: `frontend/e2e/rutas.ts`, `frontend/e2e/README.md`

- [ ] **Step 1: Reescribir `frontend/e2e/flujo-mantequilla.spec.ts`** — reemplaza los imports, `HOY` y la primera prueba («crema liberada se transforma en mantequilla y pasa por Calidad») por lo siguiente; las tres pruebas guiadas por variables de entorno («reanuda solamente la Calidad…», «envasa solamente cajas completas…», «Calidad dispone el excedente…») se quedan, con el único cambio del Step 2:

```ts
import { expect, test, type Page } from "@playwright/test";

import {
  campo,
  cerrarSesionesArea,
  elegirOpcion,
  irA,
  trasGuardar,
  usarSesionArea,
  vigilar,
} from "./ayudantes";
import { API } from "./constantes";

const HOY = new Date().toISOString().slice(0, 10);

test.describe.configure({ mode: "serial" });
test.afterAll(cerrarSesionesArea);

/*
  El código de una corrida como texto exacto: `EJ-MANT-31` no debe acertarle
  a `EJ-MANT-311` de una corrida anterior en la misma base. El código lo
  asigna el servidor (`EJ-MANT-{lote}`): no trae caracteres especiales.
*/
function exacto(codigo: string): RegExp {
  return new RegExp(`${codigo}(?!\\d)`);
}

interface PuestoLeido {
  cremas: { id: number; codigo: string; disponible_kg: string }[];
  mantequeras: { equipo_id: number; nombre: string; estado: string; motivos_para_tomar: string[] }[];
}

/* `page.request` no pasa por axios: la cabecera va a mano, con el token de la
   sesión que acaba de quedar en `localStorage`. */
async function leerPuesto(page: Page): Promise<PuestoLeido> {
  const token = await page.evaluate(
    () => JSON.parse(localStorage.getItem("ccaa.sesion") ?? "{}").token,
  );
  const respuesta = await page.request.get(`${API}/api/procesos/mantequillas/puesto/`, {
    headers: { Authorization: `Token ${token}` },
  });
  expect(respuesta.ok(), `No se pudo leer el puesto de Mantequilla (HTTP ${respuesta.status()}).`).toBeTruthy();
  return await respuesta.json() as PuestoLeido;
}

/*
  Elige la crema entre lo que **sirve el puesto** (liberada y con disponible),
  como `flujo-descremado` elige sus TK: un código escrito en la prueba deja de
  existir en cuanto la base usa otros. `E2E_LOTE_CREMA`, si viene, manda.
*/
async function elegirCrema(page: Page, kg: number) {
  await usarSesionArea(page, "e2e_produccion");
  const puesto = await leerPuesto(page);
  const pedida = process.env.E2E_LOTE_CREMA;
  const crema = puesto.cremas
    .filter((item) => (!pedida || item.codigo === pedida) && Number(item.disponible_kg) >= kg)
    .sort((a, b) => Number(b.disponible_kg) - Number(a.disponible_kg))[0];
  expect(
    crema,
    `El puesto no ofrece una crema liberada con ${kg} kg disponibles. Ofrece: ` +
      `${puesto.cremas.map((item) => `${item.codigo} ${item.disponible_kg} kg`).join(" · ") || "ninguna"}. ` +
      "Corre flujo-descremado (deja crema liberada en un TK) o libera una crema en Calidad.",
  ).toBeTruthy();
  expect(
    puesto.mantequeras.some((item) => item.estado === "disponible" && item.motivos_para_tomar.length === 0),
    "No hay una mantequera disponible: cancela desde el puesto la preparación que la retiene.",
  ).toBeTruthy();
  return crema!;
}

/*
  Prepara desde el formulario del puesto, ya abierto. La tarjeta se busca
  después por el `ejecucion_codigo` que devuelve `crear-guiada`, no por un
  código tecleado.
*/
async function preparar(page: Page, crema: { id: number }, { kg, conMazada }: { kg: string; conMazada: boolean }) {
  const dialogo = page.getByRole("dialog", { name: "Preparar mantequilla" });
  await expect(dialogo).toBeVisible({ timeout: 20_000 });
  await expect(campo(dialogo, "Crema")).toHaveValue(String(crema.id));
  await campo(dialogo, "Crema a utilizar (kg)").fill(kg);
  await elegirOpcion(campo(dialogo, "Orden de mantequilla"), /OP-E2E-MANT/);
  await elegirOpcion(campo(dialogo, "Mantequera"), /mantequ/i);
  if (conMazada) {
    await elegirOpcion(campo(dialogo, "Lote de suero / mazada (opcional)"), /MAZ-E2E/);
  }
  // El código lo sugiere el servidor (sigla de la mantequera y fecha de hoy).
  await expect(campo(dialogo, "Código del lote de mantequilla")).not.toHaveValue("", { timeout: 10_000 });
  await dialogo.getByRole("button", { name: "Revisar y confirmar" }).click();
  const respuesta = await trasGuardar(page, "/crear-guiada/", async () => {
    await dialogo.getByRole("button", { name: "Preparar mantequilla" }).click();
  });
  const creada = await respuesta.json();
  return {
    codigo: String(creada.ejecucion_codigo),
    loteId: Number(creada.lote_mantequilla),
    lote: String(creada.mantequilla_codigo),
    mantequera: String(creada.equipo_nombre),
  };
}

test("crema liberada se prepara, se inicia y se cierra en el puesto de Mantequilla", async ({ page }) => {
  test.setTimeout(180_000);
  const erroresJs = vigilar(page);
  let crema = { id: 0, codigo: "" };
  let corrida = { codigo: "", loteId: 0, lote: "", mantequera: "" };

  await test.step("1 · Producción llega desde Salidas intermedias con la crema elegida", async () => {
    crema = await elegirCrema(page, 60);
    await irA(page, "/produccion");
    await page.getByRole("button", { name: "Consultar disponibles" }).click();
    const tarjeta = page.locator("article").filter({ hasText: exacto(crema.codigo) }).first();
    const enlace = tarjeta.getByRole("link", { name: "Preparar en Mantequilla" });
    await expect(enlace).toBeVisible({ timeout: 20_000 });
    await enlace.click();
    await expect(page).toHaveURL(new RegExp(`#/produccion/mantequilla\\?crema=${crema.id}$`));
  });

  await test.step("2 · Prepara con la mazada y el código sugerido", async () => {
    corrida = await preparar(page, crema, { kg: "60", conMazada: true });
  });

  await test.step("3 · «Iniciar mantequilla» habilitado por el servidor; inicia", async () => {
    const tarjeta = page.getByRole("article").filter({ hasText: exacto(corrida.codigo) });
    await expect(tarjeta).toContainText("Preparada", { timeout: 20_000 });
    const iniciar = tarjeta.getByRole("button", { name: "Iniciar mantequilla" });
    await expect(iniciar).toBeEnabled({ timeout: 20_000 });
    await trasGuardar(page, "/iniciar/", async () => iniciar.click());
    await expect(tarjeta).toContainText("En curso", { timeout: 20_000 });
  });

  await test.step("4 · El balance lo dice el servidor mientras se teclea; se cierra", async () => {
    const tarjeta = page.getByRole("article").filter({ hasText: exacto(corrida.codigo) });
    await tarjeta.getByRole("button", { name: "Registrar balance y cerrar" }).click();
    const dialogo = page.getByRole("dialog", { name: "Registrar balance y cerrar" });
    const balance = dialogo.getByRole("region", { name: "Balance del cierre" });
    await campo(dialogo, "Mantequilla producida (kg)").fill("31");
    await campo(dialogo, "Suero / mazada recuperada (kg)").fill("28");
    await expect(balance).toContainText("Balance incompleto", { timeout: 10_000 });
    await expect(balance).toContainText(/1\.000 kg faltan por clasificar/);
    await expect(dialogo.getByRole("button", { name: "Revisar cierre" })).toBeDisabled();

    await campo(dialogo, "Merma medida (kg)").fill("1");
    await campo(dialogo, "Humedad (%)").fill("15.8");
    await expect(balance).toContainText("Balance completo", { timeout: 10_000 });
    await dialogo.getByRole("button", { name: "Revisar cierre" }).click();
    await trasGuardar(page, "/cerrar/", async () => {
      await dialogo.getByRole("button", { name: "Cerrar y enviar a Calidad" }).click();
    });
    const hoy = page.getByRole("region", { name: "Corridas de hoy" });
    await expect(hoy.getByRole("listitem").filter({ hasText: exacto(corrida.codigo) })).toContainText("Esperando Calidad");
  });

  await test.step("5 · Calidad libera la mantequilla", async () => {
    await usarSesionArea(page, "e2e_calidad");
    await irA(page, `/calidad/expedientes?lote=${corrida.loteId}`);
    await page.getByRole("button", { name: "Agregar análisis" }).click();
    await page.getByPlaceholder("M-01").fill(`M-${corrida.lote}`);
    await campo(page, "Materia grasa").fill("82.0");
    await campo(page, "Humedad").fill("15.8");
    await campo(page, "Sólidos no grasos").fill("1.5");
    await trasGuardar(page, "/analisis/", async () => {
      await page.getByRole("button", { name: "Registrar análisis" }).click();
    });
    await irA(page, "/calidad");
    const calidad = page.locator("article").filter({ hasText: corrida.lote });
    await expect(calidad).toBeVisible({ timeout: 20_000 });
    await elegirOpcion(calidad.getByRole("combobox"), /conforme/i);
    await trasGuardar(page, "/liberar/", async () => {
      await calidad.getByRole("button", { name: "Liberar para Envasado" }).click();
    });
  });

  test.info().annotations.push({
    type: "mantequilla",
    description: `E2E_MANTEQUILLA_ID=${corrida.loteId} E2E_MANTEQUILLA_LOTE=${corrida.lote}`,
  });
  expect(erroresJs).toHaveLength(0);
});

test("una preparación cancelada anula su lote y suelta la mantequera", async ({ page }) => {
  test.setTimeout(120_000);
  const erroresJs = vigilar(page);

  const crema = await elegirCrema(page, 10);
  await irA(page, `/produccion/mantequilla?crema=${crema.id}`);
  const corrida = await preparar(page, crema, { kg: "10", conMazada: false });

  const tarjeta = page.getByRole("article").filter({ hasText: exacto(corrida.codigo) });
  await expect(tarjeta).toContainText("Preparada", { timeout: 20_000 });
  await tarjeta.getByRole("button", { name: "Cancelar preparación" }).click();
  const dialogo = page.getByRole("dialog", { name: `Cancelar la preparación ${corrida.codigo}` });
  await dialogo.getByLabel("Motivo de la cancelación").fill("Prueba E2E: se preparó la crema equivocada.");
  await dialogo.getByRole("button", { name: "Revisar cancelación" }).click();
  await expect(dialogo).toContainText(`Se anulará el lote ${corrida.lote}`);
  await trasGuardar(page, "/cancelar-preparacion/", async () => {
    await dialogo.getByRole("button", { name: "Cancelar preparación" }).click();
  });

  await expect(page.getByRole("status").filter({ hasText: corrida.codigo })).toContainText("la mantequera libre");
  await expect(page.getByRole("article").filter({ hasText: exacto(corrida.codigo) })).toHaveCount(0);
  const mantequera = page.getByRole("article", { name: corrida.mantequera });
  await expect(mantequera).toContainText("Disponible");

  const token = await page.evaluate(
    () => JSON.parse(localStorage.getItem("ccaa.sesion") ?? "{}").token,
  );
  const lote = await page.request.get(`${API}/api/produccion/lotes/${corrida.loteId}/`, {
    headers: { Authorization: `Token ${token}` },
  });
  expect(lote.ok()).toBeTruthy();
  expect((await lote.json()).estado).toBe("anulado");
  expect(erroresJs).toHaveLength(0);
});
```

Notas para el implementador:
- `HOY` lo siguen usando las pruebas de Calidad de abajo; no se quita.
- `getByRole("article", { name })` funciona porque la tarjeta lleva `aria-label={fila.nombre}`.
- «Preparar mantequilla» es a la vez el título del diálogo y el botón de `ConfirmarAccion`: dentro del diálogo, `getByRole("button", …)` toma solo el botón.
- «Cancelar preparación» aparece en la tarjeta y como botón de `ConfirmarAccion` dentro del modal: por eso el segundo clic se hace sobre `dialogo`.
- Si el paso 1 no encuentra el enlace, la crema elegida no tiene una salida liberada con saldo en Salidas intermedias (por ejemplo, una crema sin TK): fija `E2E_LOTE_CREMA` a una crema en TK y repite; no cambies la prueba para entrar por la URL.

- [ ] **Step 2: El envasado usa la envasadora** — en la prueba «envasa solamente cajas completas y deja visible el remanente»: `await elegirOpcion(selectorEquipo, /Línea de mantequilla/i);` → `await elegirOpcion(selectorEquipo, /Envasadora de mantequilla/i);`.

- [ ] **Step 3: La etiqueta del enlace en el E2E de Descremado** — en `frontend/e2e/flujo-descremado.spec.ts`, las tres apariciones de `{ name: "Iniciar Mantequilla" }` (`:258`, `:306`, `:345`) pasan a `{ name: "Preparar en Mantequilla" }`.

- [ ] **Step 4: `rutas.ts`** — junto a `/produccion/descremado`: `{ ruta: "/produccion/mantequilla", nombre: "Producción · Mantequilla" },`.

- [ ] **Step 5: `README.md`** — después de «## Descremado con dos ramas» agrega una sección:

````markdown
## Mantequilla desde la crema liberada

```powershell
cd backend
.venv\Scripts\python.exe manage.py preparar_circuito_mantequilla --aplicar
cd ..\frontend
npx playwright test --project=flujo-mantequilla
```

`preparar_circuito_mantequilla` busca la **mantequera** por su tipo (`maestros.0040`
reclasificó la `linea_mantequilla`), deja una OP programada y un lote de mazada libre,
y autoriza la **envasadora de mantequilla** en los formatos activos de la mantequilla:
la mantequera ya no envasa. Si un producto no tiene formato activo, el comando lo dice
y hay que crearlo en Maestros.

La primera prueba elige una crema que el puesto sirve con al menos 60 kg (o la de
`E2E_LOTE_CREMA`) —`flujo-descremado` deja una en un TK—, llega desde Salidas
intermedias con «Preparar en Mantequilla», prepara (código sugerido, mazada), inicia
cuando el servidor lo habilita, ve «Balance incompleto» con 31 + 28 kg, completa la
merma, cierra y Calidad libera. La anotación `mantequilla` trae `E2E_MANTEQUILLA_ID` y
`E2E_MANTEQUILLA_LOTE` para correr las pruebas de envasado y disposición. La segunda
prepara 10 kg y **cancela**: el lote de salida queda anulado y la mantequera libre.

Una corrida preparada y abortada retiene la mantequera y la crema que pidió hasta que
se cancela con «Cancelar preparación» (tarjeta o historial del puesto).
````

- [ ] **Step 6 (controlador): aceptación**
  - Reiniciar el backend (`runserver --noreload`) y `cd backend && .venv\Scripts\python.exe manage.py migrate` (aplica `maestros.0039/0040` y `procesos.0024` si la base de desarrollo no las tiene; anota lo que imprime `0040`).
  - `cd backend && .venv\Scripts\python.exe manage.py preparar_circuito_descremado --aplicar`, `.venv\Scripts\python.exe manage.py preparar_circuito_mantequilla --aplicar` y `.venv\Scripts\python.exe manage.py crear_usuarios_flujo_e2e`.
  - Comprobar en `/produccion/mantequilla` que hay al menos una mantequera **Disponible** (la `linea_mantequilla` reclasificada) y que Maestros › Máquinas la muestra con tipo «Mantequera»; si una corrida preparada de una corrida anterior la retiene, cancelarla desde el puesto. Comprobar en `/procesos?seccion=mantequilla` que redirige al puesto.
  - `cd frontend && E2E_USUARIO=e2e_auditoria E2E_CLAVE=auditoria-e2e-ccaa E2E_CLAVE_AREAS=flujo-e2e-ccaa npx playwright test --project=flujo-descremado` → 3/3 (deja crema liberada en un TK y fija la etiqueta «Preparar en Mantequilla»).
  - `cd frontend && E2E_USUARIO=e2e_auditoria E2E_CLAVE=auditoria-e2e-ccaa E2E_CLAVE_AREAS=flujo-e2e-ccaa npx playwright test --project=flujo-mantequilla` → las dos primeras pasan; luego, con `E2E_MANTEQUILLA_ID`/`E2E_MANTEQUILLA_LOTE` de la anotación, las de envasado y disposición (envasan en la «Envasadora de mantequilla»).
  - Auditoría de accesibilidad (`npm run auditoria`) sin reglas nuevas en `/produccion/mantequilla`.
  - Frontend: `npx tsc -b --pretty false`, `npx eslint .`, `npm test` sin errores.
  - Suite completa del backend: `cd backend && DJANGO_ENV=test ./.venv/Scripts/python.exe manage.py test --noinput` sin rojos.

- [ ] **Step 7: Commit**

```bash
git add frontend/e2e/flujo-mantequilla.spec.ts frontend/e2e/flujo-descremado.spec.ts frontend/e2e/rutas.ts frontend/e2e/README.md
git commit -m "test(e2e): la mantequilla se recorre en su puesto, con el balance del servidor y la cancelación de una preparación"
```

---

## Autorrevisión contra la spec

| Spec | Tarea |
|---|---|
| §1 problema: 3 pasos en `/procesos`, entradas sin la crema elegida | 7 (puesto, `?crema=`, redirecciones), 8 (entrada por Salidas intermedias) |
| §1 una corrida preparada no ocupa la máquina; lote `en_proceso` huérfano sin cancelar | 3 (preparar toma la mantequera), 4 (cancelar anula corrida y lote; bandeja y `PATCH` dejan lo mismo) |
| §1 no hay regla de inicio consultable | 3 (`motivos_tipados_para_iniciar_mantequilla`), 5 (servida en `puesto/`) |
| §1 la pantalla ofrece lo que el servidor rechaza (crema comprometida, ocupación en el cliente) | 3 (`kg_crema_disponible` resta las preparadas), 5 (`cremas`, ocupación servida), 7 (`opciones-alta/` eliminada; el formulario no calcula ocupación) |
| §1 dos implementaciones del balance | 2 (`balance_mantequilla` en modelo, cierre y `revisar-cierre/`), 6 (`estadoDelBalance` sin aritmética), 7 (`balance-mantequilla.ts` eliminado) |
| §1 la máquina no es un tipo; `preparar-continuacion` sin corrida | 1 (`MANTEQUERA`, migraciones, literales), 3 (`MENSAJE_MANTEQUILLA_EN_PUESTO`) |
| §1 permiso de la pantalla ≠ servidor | 6 (`puedeOperarMantequilla`), 2-4 (403 de Secado en preparar, iniciar, cancelar, revisar y cerrar) |
| §2 decisiones (puesto, dos pasos, tipo, balance, una entrada, permiso) | 1-7 |
| §3.1 estado por mantequera; terminales y `pendiente_control` no ocupan; en curso manda; equipos no mantequera con ejecución ocupante | 5 (Desviación 11) |
| §3.1 `motivos_para_iniciar`, `resolver_en` tipado con `RESOLVER_PLANIFICACION`; `motivos_para_tomar`; `avisos`; `en_calidad` | 3 (función, constante), 5 |
| §3.1 `ordenes`, `cremas` (liberadas, `kg_crema_disponible`, `tk`), `cremas_pendientes_calidad`, `sueros` (ignora anuladas), `corridas_de_hoy`, `estados`, decimales como texto, lectura de Calidad | 3 (`filtro_crema_liberada`, `sueros_libres`, `fuente_tk_de_crema`), 5 |
| §3.1 `opciones-alta/` se elimina | 7 (Desviación 12) |
| §3.2 preparar: OP, etapa, suero, mantequera de tipo y habilitada, crema con las funciones del inicio, lote/ejecución/corrida, `borrador → preparacion`, todo o nada, sin mover crema; `preparar_continuacion` rechaza Mantequilla | 3 (Desviación 5 para el suero) |
| §3.3 iniciar: función única, orden de comprobaciones, candados corrida → ejecución, 400, salida del TK y entrada, sin `borrador → preparacion`; `MENSAJES_INICIO_EN_PUESTO`; `PUESTOS_QUE_INICIAN` | 3, 4, 6 (Desviaciones 18, 19) |
| §3.4 cancelar: motivo, `borrador`/`preparacion`, `_deshacer_preparacion_mantequilla` desde la transición, corrida `anulada`, lote anulado una vez, suero libre, `bloquear_para_cancelar`, respuesta | 4 (Desviación 8) |
| §3.5 balance: función pura, tolerancia, mensajes, `clean()`, cierre antes de escribir, `revisar-cierre/` con `errores`, se eliminan `balance-mantequilla.ts` y su prueba | 2 (Desviaciones 6, 7), 7 |
| §3.6 tipo, `tipos_equipo_para_etapa`, `ANULADA` + `motivo_anulacion`, migración de datos idempotente con candidatas, excepción por otra etapa, salida de formatos, siglas y MRP intactos, reversa; `abre_desde_vale` sin cambio con prueba; comando con mantequera y envasadora; `CLAUDE.md` | 1 (Desviaciones 2, 3, 4, 14), 7 (`CLAUDE.md`) |
| §3.7 permisos en todos los caminos; 405; `FiltraConsultaMixin` con búsqueda, situación y fecha | 2-4 (403), 4 (405), 5 (mixins) |
| §3.8 `SITUACIONES_MANTEQUILLA`; `condicion_situacion(tabla, …)` para los dos viewsets | 5 (Desviaciones 9, 10) |
| §3.9 lo que no cambia (coproductos, reproceso, liberación, cola común, `EJ-MANT-{pk}`) | sin cambios en 2 salvo el balance previo; `calidad/views.py` intacto |
| §4.1 tarjetas: una acción por estado, motivo con enlace solo si se puede entrar, cancelar con `ConfirmarAccion` y texto del lote, `en_calidad`, avisos ámbar | 6 (`accionDeMantequera`, `corridaCancelable`), 7 (`TarjetaMantequera`, `CancelarPreparacion`; Desviaciones 15, 17) |
| §4.2 formulario guiado: crema preelegida con `?crema=`, pendiente de Calidad visible con enlace, kg con tope, OP, mantequera, mazada, código sugerido y editable, resumen con `ConfirmarAccion` | 7 (`PrepararMantequilla`) |
| §4.3 cierre en `pages/Mantequilla/` con el balance de `revisar-cierre/` y resumen; habilitado solo con revisión vigente que cuadra | 6 (`estadoDelBalance`, Desviación 16), 7 (`CierreMantequilla`) |
| §4.4 corridas de hoy sin «Cargar» e historial con filtros de servidor; cancelar heredadas desde el historial | 5 (filtros), 7 (`TablaConsulta`) |
| §4.5 acceso: módulo `produccion`, `puedeOperarMantequilla` con prueba, Calidad consulta, «Actualizar» invalida la caché | 6, 7 (Desviación 1) |
| §4.6 funciones puras en `puesto-mantequilla.ts`; `CancelarPreparacion` a `components/operacion/` | 6, 7 |
| §4.1 «Lo que se retira» (sección y modales, redirección, `Silos.tsx`, `SalidasIntermedias.tsx`, etiqueta «Preparar en Mantequilla», menú con alias, `rutaDeEtapa`/`RUTAS_POR_ETAPA`, atajo de `/produccion`, bandejas con «Iniciar en el puesto de Mantequilla», servicios viejos) | 6 (`textoIniciarEnPuesto`), 7 |
| §5 pruebas backend: puesto (estados, huérfanos, `pendiente_control`, línea ocupante y ajena, motivos y destinos, aseo, cremas, sueros), preparar, iniciar, cancelar (incluido `PATCH`), transicionar genérico, `preparar-continuacion`, balance (dominio, cierre sin reproceso, revisar), permisos, historial, migración, ajustes de `tests_mantequilla`, `tests.py`, `test_opciones_alta_*`, `tests_destinos` | 1 (migración, `tests.py`), 2 (balance), 3 (preparar, iniciar, fixture), 4 (inicio genérico, cancelar, permisos), 5 (puesto, historial, situaciones), 7 (`tests_destinos`, `opciones-alta` 404) |
| §5 pruebas frontend (`accionDeMantequera`, `corridaCancelable`, `estadoDelBalance`, `puedeOperarMantequilla`, `rutaDeEtapa`, `textoIniciarEnPuesto`, menú) | 6, 7 |
| §5 E2E reescrito sobre el puesto (entrada por Salidas intermedias, preparar con código sugerido y mazada, iniciar habilitado, «Balance incompleto» con 31 + 28 kg, cierre, Calidad libera, tarjeta por `ejecucion_codigo`; segunda prueba de cancelación; envasadora de mantequilla; etiqueta en `flujo-descremado`); `rutas.ts` | 8 (Desviación 20) |
| §6 riesgos: reclasificar cambia el envasado (salida de la migración, comando), preparar toma la máquina (cancelar en el mismo cambio, heredadas cancelables), cerrar el inicio genérico, usos a migrar | 1, 4, 8; «Usos a migrar» |
| §7 fuera de alcance (motor genérico, límites de mantequilla, código sin edición, stock que bloquee, `/procesos` reducido) | respetado: el código sigue editable, el stock de envases no es motivo, `/procesos` conserva Trazabilidad, Rework y la bandeja |
| §8 desviaciones de la spec | conservadas; las del plan, en «Desviaciones» |
