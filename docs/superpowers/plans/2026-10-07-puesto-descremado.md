# Puesto de Descremado — plan de implementación

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Un solo puesto, `/produccion/descremado`, donde se prepara el descremado de un silo (con sus reservas), se inicia cuando el servidor lo permite, se cancela una preparación y se registran las salidas viendo los avisos de grasa, en vez de 3 pasos en 3 pantallas con un botón que junta preparar e iniciar.

**Architecture:** El backend convierte `crear-guiada` en «preparar»: elige el análisis, asigna el código `EJ-DES-{id}`, crea las tres `ReservaSiloProceso` y toma la descremadora (`borrador → preparacion`) en una transacción, con reglas de origen y destino compartidas con el inicio (`motivos_origen_descremacion`, `motivos_destino_descremacion`). `motivos_tipados_para_iniciar_descremacion` pasa a ser la única implementación de las reglas de inicio; `iniciar_descremacion` la usa y ya no reserva. El inicio genérico (`transicionar` de `preparacion` a `ejecucion`) se cierra también para Descremación, se agrega «Cancelar preparación», se cierran las dos altas que creaban corridas sin pasar por el puesto (`POST descremaciones/` y `POST ejecuciones/`), los límites físicos de grasa se vuelven una función pura que avisa mientras se teclea (`revisar-cierre/`) y queda registrada al cerrar, y `descremaciones/puesto/` sirve el estado del puesto. El frontend agrega la página del puesto (tarjetas por descremadora que pintan lo que manda el servidor, formulario guiado «Preparar descremado» sin selector de análisis, cierre con avisos, corridas de hoy e historial con filtros de servidor) y retira la sección y los modales de `/procesos`.

**Tech Stack:** Django 6 + DRF + PostgreSQL; React 19 + TypeScript + react-router (HashRouter); `node --test`; Playwright.

**Spec:** `docs/superpowers/specs/2026-10-07-puesto-descremado-design.md` (con los ajustes de «Desviaciones» y del Step 7 de la Task 4).

## Global Constraints

- Ruta del puesto: **`/produccion/descremado`**, bajo el módulo `produccion` (como Evaporación). `/procesos?seccion=descremacion` → `/produccion/descremado`; `/procesos?accion=descremar&silo=<id>` → `/produccion/descremado?silo=<id>` (mismo bloque de `Procesos.tsx` que redirige `condensacion`/`evaporacion`). Menú, `rutaDeEtapa("descremacion")` y `RUTAS_POR_ETAPA["descremacion"]` apuntan al puesto.
- Endpoints (prefijo `/api/procesos/descremaciones/`): `GET puesto/`; `POST crear-guiada/` (prepara; ignora `codigo` y `analisis_entrada`); `POST {id}/iniciar/` (409 con los motivos, como hoy); `POST {id}/cancelar-preparacion/` `{"motivo"}`; `POST {id}/revisar-cierre/` (no escribe); `POST {id}/cerrar/`; `GET ?q=&estado=&desde=&hasta=&page=`. `POST descremaciones/` → **405**. `POST /api/procesos/ejecuciones/` → **405 para toda etapa**.
- Estados por descremadora: `"disponible" | "preparada" | "en_curso"`. Ejecución de Descremación en `preparacion` → `preparada`; `ejecucion`, `pausada` o `bloqueada` → `en_curso`; sin ejecución en `ESTADOS_QUE_OCUPAN_EQUIPO` → `disponible`. `cerrada`/`cancelada` no ocupan (`ESTADOS_EJECUCION_TERMINALES`).
- Claves JSON del puesto: `descremadoras[].{equipo_id, codigo, nombre, estado, corrida, motivos_para_tomar, motivos_para_iniciar, resolver_en, avisos, en_calidad}`; `corrida.{id, ejecucion_id, ejecucion_codigo, ejecucion_estado, estado, silo_entera, litros_entrada, grasa_entrada, sng_entrada, silo_descremada, litros_descremada_plan, estanque_crema, litros_crema_plan, destino_crema, iniciada_en}`; `en_calidad.{id, ejecucion_codigo, tanques}`; `origenes[].{id, codigo, saldo_l, analisis: {id, grasa, sng, tomado_en} | null, motivo}`; `destinos_descremada[]`/`destinos_crema[]` `{id, codigo, libre_l}`; `corridas_de_hoy[].{id, ejecucion_codigo, equipo, silo_entera, estado, estado_etiqueta, estado_ejecucion}`; `estados[].{valor, etiqueta}`. Decimales como **texto**.
- `motivos_tipados_para_iniciar_descremacion(corrida, *, ejecucion=None)` es **la única implementación** de las reglas de inicio: `iniciar_descremacion` la usa (vía `motivos_para_iniciar_descremacion`) y `descremaciones/puesto/` la sirve. `resolver_en`: `RESOLVER_CIP = "/calidad/inocuidad"`, `RESOLVER_SILOS = "/silos"` (nuevo) o `None`.
- Mensaje exacto del inicio genérico rechazado: «Las corridas de descremado se inician desde el puesto de Descremado.» Solo `preparacion → ejecucion`; pausar, bloquear, reanudar y cancelar siguen por `transicionar`.
- Código de ejecución: **`EJ-DES-{id de la corrida}`**, asignado por el servidor (como `INT-DES-{id}-LD/CR` de los lotes intermedios).
- Límites: `LIMITE_GRASA_DESCREMADA = Decimal("0.1")`, `RANGO_GRASA_CREMA_DESPACHO = (Decimal("42"), Decimal("43"))`; códigos `grasa_descremada_alta`, `grasa_crema_fuera_de_rango`. **Avisan, no bloquean.** El de la crema solo con `destino_crema == "despacho_directo"`.
- Preparar, iniciar, cancelar, revisar el cierre y cerrar exigen la etapa Descremación (`puede_operar_tipo(usuario, EtapaProceso.Tipo.DESCREMACION)`: área Condensación o administración) en todos los caminos; Calidad lee el puesto.
- La tarjeta **pinta lo que manda el servidor**; una acción por estado: «Preparar descremado», «Iniciar descremado», «Registrar salidas y cerrar»; «Cancelar preparación» en segundo plano. Línea informativa «{TK} y {TK} de {código} esperando Calidad». Confirmaciones con `ConfirmarAccion`: «Preparar descremado», «Confirmar salidas y cerrar», «Cancelar preparación».
- Trampa de `CLAUDE.md`: dentro de `transaction.atomic()` un `return Response(...)` **confirma**; solo una excepción revierte. Los servicios lanzan `ValidationError`; las vistas responden **fuera** de la transacción.
- Trampa de `CLAUDE.md`: las migraciones siembran equipos y silos también en la base de pruebas, y `filtrar_por_scope` ya no aísla por empresa: las pruebas del puesto filtran por **sus** ids, nunca comparan listas completas.
- Toda cantidad en pantalla pasa por `cantidad(valor, unidad)`; toda operación irreversible por `ConfirmarAccion`.
- Español en código, comentarios, mensajes y UI. Django 6: `save()` solo por nombre. Archivos en LF.
- Pruebas backend: `cd backend && DJANGO_ENV=test ./.venv/Scripts/python.exe manage.py test <etiquetas> --noinput`, **en serie, nunca `--parallel`**. Frontend (en `frontend/`): `npx tsc -b --pretty false`, `npx eslint .`, `npm test`.
- No reescribir archivos con acentos con PowerShell `Get-Content | Set-Content` (usar Edit). Commits en español, convencionales, sin líneas de atribución, agregando archivos **por nombre**; nunca `frontend/e2e/.auth/estado.json`.

## Desviaciones: lo que el código dice distinto de la spec

1. **`motivos_origen_descremacion` y `motivos_destino_descremacion` no existen.** La spec (§3.2 paso 4, §3.3) las nombra como si estuvieran; hoy son comprobaciones en línea de `iniciar_descremacion` (`backend/procesos/servicios.py:2040-2072`). La Task 1 las **extrae** y las usan preparar, iniciar y el puesto. Se agregan dos más con el mismo criterio de «una regla»: `motivos_para_preparar_desde_silo(silo, analisis)` (silo en servicio + análisis vigente con grasa y SNG: lo que preparar exige y el puesto usa para `origenes[].motivo`) y `recepcion.servicios.ultimo_analisis_confirmado(silo)`, extraída de la consulta en línea de `motivos_silo_no_disponible` (`backend/recepcion/servicios.py:62-68`), para que «el análisis que usará preparar» y «el que lee el inicio» sean la misma consulta.
2. **Las reservas nacen en un paso propio.** `preparar_descremacion(*, corrida_id, usuario)` reserva origen y destinos y pasa la ejecución a `preparacion`; `crear_descremacion_guiada` la llama al final, en la misma transacción. Así las pruebas que siembran una corrida por ORM (`tests_descremacion.CierreDescremacionTests`) la preparan por el mismo camino que la API.
3. **`EJ-DES-{pk}`: pk de la corrida**, no de la ejecución (el ejemplo de la spec dice `"id": 8` / `"EJ-DES-8"` con `ejecucion_id: 120`). La ejecución nace con un código provisional único dentro de la misma transacción y se renombra al tener la corrida. Las dos fixtures que teclean `EJ-DES-1` y `EJ-DES-2` (`tests_descremacion.py:121,488`) se renombran a `EJ-DES-FIJA-1/2` para que no choquen con un código asignado.
4. **Había un tercer camino de alta: `POST ejecuciones/`.** `EjecucionProcesoViewSet.create` (`backend/procesos/views.py:972`) acepta todavía Descremación «por compatibilidad temporal»: crea una ejecución **sin corrida** que `transicionar` puede pasar a `preparacion` y ocupar la descremadora. Se cierra con 405 para **toda** etapa (Task 2); `crearEjecucion` del frontend (sin uso) se elimina y `tests_permisos_operacionales.test_alta_generica_solo_conserva_descremacion_y_su_area` se migra. El puesto tolera una ejecución preparada sin corrida (dato heredado) con un motivo que dice qué hacer, como Secado.
5. **El mensaje del inicio genérico es por etapa.** `inicio_reservado_al_puesto` solo mira Secado y la vista usa `MENSAJE_INICIO_SECADO_EN_PUESTO`. Se generaliza con `MENSAJES_INICIO_EN_PUESTO = {SECADO: …, DESCREMACION: …}`; la constante de Secado se conserva (la importa `tests_puesto_secado`).
6. **«Análisis superado» no se resuelve en `/silos`.** La spec (§3.3) le da `RESOLVER_SILOS`, pero volver a analizar no arregla una corrida congelada con la composición vieja: lo que la arregla es cancelar y volver a preparar, en el mismo puesto. Ese motivo viaja con `resolver_en = None` y su texto lo dice. Los motivos del silo (firmas, inhibidores, 48 h, estado, CIP) sí van a `RESOLVER_SILOS`; saldo, capacidad, reservas y mezcla van con `None` (no hay pantalla que los arregle).
7. **El operador del puesto no entra a `/silos`.** `access-control.ts` da el módulo `recepcion` solo a Recepción y Calidad; Condensación no. `moduloDeResolver` gana `"/silos" → "recepcion"` y la tarjeta enlaza solo si el usuario puede entrar (como Secado): Calidad y administración ven el enlace, Condensación ve el motivo sin enlace. El E2E (con `e2e_produccion`, área Condensación) comprueba el motivo y el botón deshabilitado, no el enlace; el enlace lo fija la prueba unitaria.
8. **«Descremar» del silo hoy se bloquea por el inicio.** `Silos.tsx:359` pasa `bloqueado={bloqueoSeleccionado}`, que es `motivos_no_disponible[0]` (falta de segunda firma incluida) o «Reservado por…». Eso contradice la decisión de que preparar no exige firmas, y además impediría el paso del E2E. «Descremar» deja de recibir `bloqueado`: siempre lleva al puesto, que muestra el silo deshabilitado con su motivo (`origenes[].motivo`), que es lo que la spec §3.1 pide para esa entrada.
9. **Cancelar desde la bandeja genérica anula también una corrida en curso.** La spec §8.11 la dejaba `en_curso`. `_deshacer_preparacion_descremacion` marca `anulada` cualquier corrida `borrador` o `en_curso` de una ejecución cancelada, como `_deshacer_preparacion_evaporacion` con `en_proceso`: una corrida «en curso» sobre una ejecución cancelada no la hace nadie. No se agrega una acción nueva; desde el puesto solo se cancela una preparada.
10. **«En curso manda sobre preparada» no es alcanzable.** La base impide dos ocupaciones del mismo equipo (`procesos.tests.test_la_base_impide_dos_ocupaciones_del_mismo_equipo`). El código conserva la regla (espejo de Secado) y la prueba cubre `ejecucion`/`pausada`/`bloqueada` → `en_curso` en vez de sembrar una situación que la base rechaza.
11. **`QuerysetTenantMixin` ya no aísla.** `filtrar_por_scope` «autentica, pero nunca aísla» (`usuarios/tenancy.py:196`). Se agrega igual (spec §3.6), por consistencia con Secado y Mantequilla; ninguna prueba mide aislamiento por empresa.
12. **`corridaCancelable` recibe la corrida, no la fila**, para que el historial ofrezca cancelar las corridas `borrador` heredadas (spec §6) con la misma regla; la confirmación es un modal compartido (`CancelarPreparacion.tsx`) por la tarjeta y el historial.
13. **Claves extra**: `descremadoras[].corrida.estado` (la necesita `corridaCancelable`), `estados` (catálogo del filtro del historial, servido por el backend) y `ejecucion_estado` en `CorridaDescremacionSerializer` (el historial distingue «Preparada» de «Esperando Calidad»).
14. **`revisar-cierre/` acepta campos vacíos.** Mismas claves que `cerrar/` pero todas opcionales y nulables (`RevisarCierreDescremacionSerializer`): se pide mientras se teclea.
15. **Respuestas de error**: `iniciar` conserva 409 con la lista de motivos (`_error`, como hoy y como dice la spec); `cancelar-preparacion` usa `respuesta_error_dominio` (400), como en los otros puestos.
16. **«Iniciar en el puesto de …» deja de ser una condición escrita a mano.** `Procesos.tsx:210` y `BandejaTrabajoArea.tsx:170` preguntan `etapa_tipo === "secado"`; se reemplaza por `textoIniciarEnPuesto(etapaTipo, estado)` en `planta-ahora.ts`, espejo de `MENSAJES_INICIO_EN_PUESTO`.
17. **`moduloDeResolver` se queda en `puesto-secado.ts`** y `puesto-descremado.ts` lo reexporta: un módulo común de puestos es el «motor de puesto genérico» que la spec deja fuera de alcance.
18. **`opciones-alta` pierde `equipos`/`silos_descremada`/`estanques_crema` en la Task 6, no en la 4**, junto con el retiro del modal que los lee: quitarlos antes rompería `/procesos` entre commits.
19. **Destinos «en estado que admite producto»** se leen con el conjunto que ya usaban `iniciar_descremacion` y `cerrar_descremacion` (`bloqueado_calidad`, `en_cip`, `fuera_servicio`, más inactivo): `pendiente_cip` admite, como hoy.
20. **E2E**: `analizarSilo` gana `{ segundaFirma: false }` y devuelve el id del análisis, para que la prueba vea «Iniciar descremado» deshabilitado y luego firme con `firmarVisualizacion(id)`.

## Usos a migrar

Búsqueda del 2026-10-07 (`grep` sobre `backend/`, `frontend/src`, `frontend/tests`, `frontend/e2e`).

| Uso | Dónde | Tarea |
|---|---|---|
| `crear_descremacion_guiada` (firma con `codigo`, `analisis_entrada_id`; sin reservas) | `backend/procesos/servicios.py:413`; vista `backend/procesos/views.py:489-544`; `backend/procesos/tests_descremacion.py:146-234` (payload con `codigo`/`analisis_entrada`, asserts del código tecleado) | 1 |
| `CrearDescremacionGuiadaSerializer.codigo/analisis_entrada` | `backend/procesos/serializers.py:48,52` | 1 |
| `iniciar_descremacion` (crea reservas; comprobaciones en línea) | `backend/procesos/servicios.py:1993-2111`; `tests_descremacion.py:404-431` (`test_inicio_reserva_origen…`), `:432-455` (`test_cancelar_libera_las_reservas_de_tk`), `:457-467` (`test_no_inicia_si_el_plan_supera_capacidad_del_tk`), `:469-517` (`test_un_tk_con_reserva_activa_no_se_asigna_a_otra_corrida`), `:520` y `:710` (inician la fixture `borrador` sin preparar) | 1 |
| Códigos tecleados `EJ-DES-1`, `EJ-DES-2` | `backend/procesos/tests_descremacion.py:121,488` (`EJ-DES-SIG`, `EJ-DES-NO`, `EJ-DES-PER` no son numéricos: sin cambio) | 1 |
| Consulta en línea del último análisis confirmado | `backend/recepcion/servicios.py:62-68` (`motivos_silo_no_disponible`) y `:510` (despacho de leche a granel) → `ultimo_analisis_confirmado` | 1 |
| `inicio_reservado_al_puesto` / `MENSAJE_INICIO_SECADO_EN_PUESTO` | `backend/procesos/servicios.py:94,2742`; `backend/procesos/views.py:65-66,1114,1159-1162`; `backend/procesos/tests_puesto_secado.py:26,557` (sin cambio: la constante se conserva) | 2 |
| `transicionar_ejecucion` (ganchos de cancelación) y `bloquear_para_cancelar` | `backend/procesos/servicios.py:1102-1124,1202-1215` | 2 |
| `CorridaDescremacionViewSet.create` abierto (`ModelViewSet`) | `backend/procesos/views.py:313`; `frontend/src/services/procesos.service.ts:698` (`crearDescremacion`, sin uso) | 2, 6 |
| `EjecucionProcesoViewSet.create` (alta genérica de Descremación) | `backend/procesos/views.py:972-985,1007-1013`; `backend/procesos/tests_permisos_operacionales.py:81-114`; `frontend/src/services/procesos.service.ts:596` (`crearEjecucion`, sin uso) | 2, 6 |
| `cerrar_descremacion` (`controles`, evento) | `backend/procesos/servicios.py:2254-2268` | 3 |
| `docs/REGLAS_DE_PLANTA.md` §2 («No implementado», «No existe el proceso») | `docs/REGLAS_DE_PLANTA.md:145-161` | 3 |
| `CorridaDescremacionViewSet` sin tenant ni filtros; `CorridaDescremacionSerializer` | `backend/procesos/views.py:313-323`; `backend/procesos/serializers.py:179` | 4 |
| `opciones-alta` (`equipos`, `silos_descremada`, `estanques_crema`, `ocupado_por`) | `backend/procesos/views.py:330-448`; `backend/procesos/tests_descremacion.py:274-306`; `frontend/src/services/procesos.service.ts:355-371`; `frontend/src/pages/Procesos/FormularioDescremacion.tsx` (se elimina) | 6 |
| `RUTAS_POR_ETAPA["descremacion"]` | `backend/procesos/dominio.py:52`; `backend/procesos/tests_destinos.py:21` | 6 |
| Modal y sección de `/procesos` | `frontend/src/pages/Procesos/Procesos.tsx:8,11,14,29-31,38-41,89-105,147-153,175-176,188-191,210`; `frontend/src/pages/Procesos/FormularioDescremacion.tsx`, `CierreDescremacion.tsx` (se eliminan) | 6 |
| Servicios de descremación del frontend | `frontend/src/services/procesos.service.ts`: `CorridaDescremacion` (:217, gana `ejecucion_estado`), `obtenerDescremaciones` (:603, solo `Procesos.tsx`), `crearDescremacionGuiada` (:708 → `prepararDescremado` en `descremado.service.ts`), `iniciarDescremacion` (:748 → `iniciarDescremado`); `sugerirBalanceDescremacion`, `cerrarDescremacion`, `obtenerOpcionesAltaDescremacion` se quedan | 5, 6 |
| Enlaces a `/procesos?seccion=descremacion` y `?accion=descremar` | `frontend/src/pages/Leche/Silos.tsx:359`; `frontend/src/pages/Produccion/Produccion.tsx:267`; `frontend/src/services/navegacion-operacional.ts:56`; `frontend/src/services/planta-ahora.ts:6`; `frontend/tests/navegacion-operacional.test.ts:115-133`; `frontend/tests/planta-ahora.test.ts:8,21` | 6 |
| «Iniciar en el puesto de Secado» escrito a mano | `frontend/src/pages/Procesos/Procesos.tsx:210`; `frontend/src/pages/Produccion/BandejaTrabajoArea.tsx:170` | 5, 6 |
| `moduloDeResolver` (sin `/silos`) | `frontend/src/services/puesto-secado.ts:81-89`; `frontend/tests/puesto-secado.test.ts:84-88` | 5 |
| Rutas | `frontend/src/app/routes.tsx:75-76,217-224` | 6 |
| Etiquetas que usa el E2E: «Iniciar descremación», «Código de ejecución», «Equipo», «Destino leche descremada», «TK fisico para crema», «Confirmar reservas e iniciar», «Cerrar descremación», «Cerrar corrida», `/descremaciones/\d+/iniciar/` | `frontend/e2e/flujo-descremado.spec.ts:40-74,129-163` | 7 |
| `analizarSilo` (siempre firma dos veces, no devuelve el id) | `frontend/e2e/ayudantes.ts:461-547` (los demás llamadores ignoran el retorno: `circuito-polvo.spec.ts:326-327`, `evaporacion.spec.ts:453`, `flujo-polvo-continuacion.spec.ts:39`, `flujo-precondensado-despacho.spec.ts:38`) | 7 |
| Auditoría de rutas y README | `frontend/e2e/rutas.ts:59-60`; `frontend/e2e/README.md:170-191` | 7 |
| **Sin uso y sin cambio** | `sembrar_flujo_demo` y `preparar_circuito_polvo` no descreman; `preparar_circuito_descremado` (+ `produccion/tests_preparar_descremado.py`) siembra máquina y maestros, no corridas; `limpiar_transaccional`/`reset_datos_operacionales` borran corridas sin depender del flujo; `procesos/tests.py` usa la etapa Descremación por servicio y ORM, nunca `preparacion → ejecucion` por la API (su `test_pendiente_control…` sigue en `TRANSICION_NO_PERMITIDA`); `tests_concurrencia_equipo.py` es Secado `borrador → preparacion` | — |

## Mapa de archivos

| Archivo | Cambio | Tarea |
|---|---|---|
| `backend/recepcion/servicios.py` | `ultimo_analisis_confirmado`; `motivos_silo_no_disponible` la usa | 1 |
| `backend/procesos/servicios.py` | `RESOLVER_SILOS`, `ESTADOS_SILO_SIN_PRODUCTO`, `motivos_para_preparar_desde_silo`, `motivos_origen_descremacion`, `motivos_destino_descremacion`, `preparar_descremacion`, `crear_descremacion_guiada` (sin `codigo`/`analisis_entrada_id`), `motivos_tipados_para_iniciar_descremacion`, `motivos_para_iniciar_descremacion`, `iniciar_descremacion` | 1 |
| ídem | `MENSAJE_INICIO_DESCREMADO_EN_PUESTO`, `MENSAJES_INICIO_EN_PUESTO`, `inicio_reservado_al_puesto`, `_deshacer_preparacion_descremacion`, `cancelar_preparacion_descremacion`, `bloquear_para_cancelar`, gancho en `transicionar_ejecucion` | 2 |
| ídem | `revisar_cierre_descremacion`; `cerrar_descremacion` guarda `avisos_limites` | 3 |
| ídem | `estado_puesto_descremado` | 4 |
| `backend/procesos/dominio.py` | límites y `avisos_limites_descremacion` (3); `RUTAS_POR_ETAPA` (6) | 3, 6 |
| `backend/procesos/serializers.py` | `CrearDescremacionGuiadaSerializer` (1); `RevisarCierreDescremacionSerializer` (3); `ejecucion_estado` (4) | 1, 3, 4 |
| `backend/procesos/views.py` | `crear_guiada` (1); `create` 405, `cancelar_preparacion`, `transicionar`, `EjecucionProcesoViewSet.create` (2); `revisar_cierre` (3); mixins, `puesto` (4); `opciones_alta` (6) | 1-4, 6 |
| `backend/procesos/tests_puesto_descremado.py` | nuevo | 1-4, 6 |
| `backend/procesos/tests_descremacion.py` | migrar fixture y pruebas; pruebas de dominio de límites | 1, 2, 3, 6 |
| `backend/procesos/tests_permisos_operacionales.py` | alta genérica cerrada | 2 |
| `backend/procesos/tests_destinos.py` | ruta de la etapa | 6 |
| `docs/REGLAS_DE_PLANTA.md` | §2 | 3 |
| `docs/superpowers/specs/2026-10-07-puesto-descremado-design.md` | §8 con las desviaciones del plan | 4 |
| `frontend/src/services/descremado.service.ts`, `puesto-descremado.ts`, `permisos-descremado.ts` + `frontend/tests/puesto-descremado.test.ts`, `permisos-descremado.test.ts` | nuevos | 5 |
| `frontend/src/services/puesto-secado.ts`, `planta-ahora.ts`, `procesos.service.ts` + `frontend/tests/puesto-secado.test.ts`, `planta-ahora.test.ts` | `/silos`, `textoIniciarEnPuesto`, `ejecucion_estado` | 5 |
| `frontend/src/pages/Descremado/PuestoDescremado.tsx`, `TarjetaDescremadora.tsx`, `PrepararDescremado.tsx`, `CierreDescremado.tsx`, `CancelarPreparacion.tsx` | nuevos | 6 |
| `frontend/src/pages/Procesos/FormularioDescremacion.tsx`, `CierreDescremacion.tsx` | eliminar | 6 |
| `frontend/src/pages/Procesos/Procesos.tsx`, `frontend/src/pages/Produccion/Produccion.tsx`, `BandejaTrabajoArea.tsx`, `frontend/src/pages/Leche/Silos.tsx`, `frontend/src/app/routes.tsx`, `frontend/src/services/navegacion-operacional.ts`, `planta-ahora.ts`, `procesos.service.ts` + `frontend/tests/navegacion-operacional.test.ts`, `planta-ahora.test.ts` | retiro, rutas, menú | 6 |
| `CLAUDE.md` | decisión nueva | 6 |
| `frontend/e2e/flujo-descremado.spec.ts`, `ayudantes.ts`, `rutas.ts`, `README.md` | E2E | 7 |

---

### Task 1: Preparar reserva y toma la máquina; iniciar tiene una sola regla

**Files:**
- Modify: `backend/recepcion/servicios.py` (`ultimo_analisis_confirmado` junto a `motivos_silo_no_disponible`, ~56)
- Modify: `backend/procesos/servicios.py` (`crear_descremacion_guiada` ~413; reglas nuevas e `iniciar_descremacion` ~1992; `RESOLVER_SILOS` junto a `RESOLVER_CIP` ~2759)
- Modify: `backend/procesos/serializers.py` (`CrearDescremacionGuiadaSerializer`, ~47)
- Modify: `backend/procesos/views.py` (`CorridaDescremacionViewSet.crear_guiada`, ~489)
- Create: `backend/procesos/tests_puesto_descremado.py`
- Modify: `backend/procesos/tests_descremacion.py`

**Interfaces:**
- Produces (`recepcion/servicios.py`): `ultimo_analisis_confirmado(silo) -> AnalisisSilo | None` — el último `CONFIRMADO` por `(-tomado_en, -id)`, con `analista` y `visualizado_por`.
- Produces (`procesos/servicios.py`):
  - `RESOLVER_SILOS = "/silos"`; `ESTADOS_SILO_SIN_PRODUCTO = frozenset({"bloqueado_calidad", "en_cip", "fuera_servicio"})`
  - `motivos_para_preparar_desde_silo(silo, analisis) -> list[str]`
  - `motivos_origen_descremacion(origen, litros, *, excluir_ejecucion_id=None) -> list[str]`
  - `motivos_destino_descremacion(destino, *, producto=None, litros=None, excluir_ejecucion_id=None) -> list[str]` (sin `producto`/`litros` comprueba solo estado y reservas: es lo que usa el puesto para ofrecer)
  - `preparar_descremacion(*, corrida_id, usuario) -> CorridaDescremacion` — reserva y pasa la ejecución `borrador → preparacion`.
  - `crear_descremacion_guiada(*, etapa_id, equipo_id, silo_entera_id, litros_entrada, silo_descremada_id, estanque_crema_id, producto_descremada_id, producto_crema_id, usuario, ruta_descremada_id=None, ruta_crema_id=None, destino_descremada=PENDIENTE, destino_crema=PENDIENTE, litros_descremada_plan=None, litros_crema_plan=None) -> CorridaDescremacion`
  - `motivos_tipados_para_iniciar_descremacion(corrida, *, ejecucion=None) -> list[tuple[str, str | None]]`; `motivos_para_iniciar_descremacion(corrida, *, ejecucion=None) -> list[str]`
  - `iniciar_descremacion(*, corrida_id, usuario) -> CorridaDescremacion` (misma firma; ya no reserva).
- `POST /api/procesos/descremaciones/crear-guiada/` `{etapa, equipo, silo_entera, litros_entrada, silo_descremada, estanque_crema, producto_descremada, producto_crema, litros_descremada_plan, litros_crema_plan, plan_confirmado, ruta_descremada?, ruta_crema?, destino_descremada?, destino_crema?}` → 201 `CorridaDescremacionSerializer` (`ejecucion_codigo: "EJ-DES-{id}"`, ejecución en `preparacion`); 400 con el motivo; 403 sin la etapa.
- Fixture `BasePuestoDescremado` en `tests_puesto_descremado.py` (la usan las Tasks 2, 3, 4 y 6).

- [ ] **Step 1: Fixture y pruebas que fallan** — crea `backend/procesos/tests_puesto_descremado.py`:

```python
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from inventario.models import CicloCIP
from maestros.models import Equipo, Especificacion, Mandante, Producto, Silo
from recepcion.models import AnalisisSilo, MovimientoSilo
from usuarios.models import Empresa, PerfilUsuario, Rol, Sucursal

from .models import (
    CorridaDescremacion, EjecucionProceso, EtapaProceso, Proceso, ReservaSiloProceso,
)
from .servicios import (
    RESOLVER_CIP, RESOLVER_SILOS, iniciar_descremacion,
    motivos_para_iniciar_descremacion, motivos_tipados_para_iniciar_descremacion,
)


class BasePuestoDescremado(TestCase):
    """
    Un silo de leche entera con 20.000 L y un análisis confirmado con las dos
    firmas, dos TK de descremada, dos de crema y dos descremadoras libres: lo
    que el puesto ve al empezar el turno.

    Las migraciones siembran equipos y silos en la base de pruebas, y
    `filtrar_por_scope` ya no aísla por empresa: las aserciones se hacen sobre
    los objetos de esta fixture, nunca sobre listas completas.
    """

    def setUp(self):
        self.empresa = Empresa.objects.create(rut="PDES-1", nombre="Empresa puesto descremado")
        self.planta = Sucursal.objects.create(
            empresa=self.empresa, codigo="PDES", nombre="Planta puesto descremado"
        )
        self.condensador = self._usuario("condensador-pdes", PerfilUsuario.Area.CONDENSACION)
        self.secador = self._usuario("secador-pdes", PerfilUsuario.Area.SECADO)
        self.calidad = self._usuario("calidad-pdes", PerfilUsuario.Area.CALIDAD, Rol.CALIDAD)
        mandante = Mandante.objects.create(
            empresa=self.empresa, nombre="Intermedios puesto descremado", codigo_cliente="pdd"
        )
        self.producto_descremada = Producto.objects.create(
            mandante=mandante, nombre="Descremada intermedia PD",
            familia=Producto.Familia.LIQUIDO, naturaleza=Producto.Naturaleza.INTERMEDIO,
            tipo=Producto.TipoProducto.DESCREMADA, unidad_base=Producto.Unidad.L,
        )
        self.producto_crema = Producto.objects.create(
            mandante=mandante, nombre="Crema intermedia PD",
            familia=Producto.Familia.CREMA, naturaleza=Producto.Naturaleza.INTERMEDIO,
            categoria=Producto.Categoria.CREMA, unidad_base=Producto.Unidad.KG,
        )
        for producto, minimo, maximo in (
            (self.producto_descremada, 0, 0.2), (self.producto_crema, 35, 45),
        ):
            Especificacion.objects.create(
                producto=producto, tipo_analisis=Especificacion.TipoAnalisis.SILO,
                version=1, vigente_desde=timezone.localdate(),
                rangos={"mg": {"min": minimo, "max": maximo}},
            )
        proceso = Proceso.objects.create(codigo="descremar-puesto", nombre="Descremado del puesto")
        self.etapa = EtapaProceso.objects.create(
            proceso=proceso, codigo="des-pd", nombre="Descremar",
            tipo=EtapaProceso.Tipo.DESCREMACION, orden=1,
        )
        self.descremadora = self._equipo("des-pd1", "Descremadora PD 1")
        self.otra_descremadora = self._equipo("des-pd2", "Descremadora PD 2")
        self.origen = self._silo("SILO-PD", Silo.Tipo.SILO, 30000)
        self.tk_descremada = self._silo("TK-LD-PD", Silo.Tipo.TK_LD, 30000)
        self.otro_tk_descremada = self._silo("TK-LD-PD2", Silo.Tipo.TK_LD, 30000)
        self.tk_crema = self._silo("TK-CR-PD", Silo.Tipo.TK_CREMA, 5000)
        self.otro_tk_crema = self._silo("TK-CR-PD2", Silo.Tipo.TK_CREMA, 5000)
        MovimientoSilo.objects.create(
            silo=self.origen, tipo=MovimientoSilo.Tipo.INGRESO, litros=20000,
            fecha_hora=timezone.now() - timedelta(hours=3),
            origen_tipo=MovimientoSilo.OrigenTipo.AJUSTE,
        )
        self.analisis = self.analizar(self.origen, minutos=120)

    def _usuario(self, nombre, area, rol=Rol.PRODUCCION):
        usuario = User.objects.create_user(nombre)
        PerfilUsuario.objects.create(
            usuario=usuario, empresa=self.empresa, sucursal=self.planta, area=area, rol=rol,
        )
        return usuario

    def _equipo(self, codigo, nombre):
        return Equipo.objects.create(
            sucursal=self.planta, codigo=codigo, nombre=nombre, tipo=Equipo.Tipo.DESCREMADORA,
        )

    def _silo(self, codigo, tipo, capacidad):
        return Silo.objects.create(
            sucursal=self.planta, codigo=codigo, tipo=tipo, capacidad_l=capacidad,
        )

    def analizar(self, silo, *, minutos=60, grasa="2.61", sng="8.70", segunda_firma=True):
        return AnalisisSilo.objects.create(
            silo=silo, tomado_en=timezone.now() - timedelta(minutes=minutos),
            grasa=None if grasa is None else Decimal(grasa),
            sng=None if sng is None else Decimal(sng),
            inhibidores_resultado="negativo", metodo="snap",
            hora_lectura=timezone.localtime().time(),
            estado=AnalisisSilo.Estado.CONFIRMADO, analista=self.condensador,
            visualizado_por=self.calidad if segunda_firma else None,
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
        datos = {
            "etapa": self.etapa.pk, "equipo": self.descremadora.pk,
            "silo_entera": self.origen.pk, "litros_entrada": "1000",
            "silo_descremada": self.tk_descremada.pk, "estanque_crema": self.tk_crema.pk,
            "producto_descremada": self.producto_descremada.pk,
            "producto_crema": self.producto_crema.pk,
            "litros_descremada_plan": "970", "litros_crema_plan": "25",
            "plan_confirmado": True,
        }
        datos.update(cambios)
        return datos

    def preparar(self, usuario=None, **cambios):
        return self.cliente(usuario).post(
            "/api/procesos/descremaciones/crear-guiada/",
            self.datos_preparar(**cambios), format="json",
        )

    def preparada(self, **cambios):
        respuesta = self.preparar(**cambios)
        self.assertEqual(respuesta.status_code, 201, respuesta.data)
        return CorridaDescremacion.objects.select_related("ejecucion").get(pk=respuesta.data["id"])

    def en_curso(self, **cambios):
        corrida = self.preparada(**cambios)
        iniciar_descremacion(corrida_id=corrida.pk, usuario=self.condensador)
        corrida.refresh_from_db()
        corrida.ejecucion.refresh_from_db()
        return corrida

    def reservas(self, corrida, estado=ReservaSiloProceso.Estado.ACTIVA):
        return ReservaSiloProceso.objects.filter(ejecucion_id=corrida.ejecucion_id, estado=estado)


class PrepararDescremadoTests(BasePuestoDescremado):
    def test_preparar_crea_corrida_tres_reservas_y_toma_la_descremadora(self):
        corrida = self.preparada()

        self.assertEqual(corrida.estado, CorridaDescremacion.Estado.BORRADOR)
        self.assertEqual(corrida.ejecucion.estado, EjecucionProceso.Estado.PREPARACION)
        self.assertEqual(corrida.ejecucion.equipo, self.descremadora)
        self.assertEqual(corrida.ejecucion.codigo, f"EJ-DES-{corrida.pk}")
        self.assertEqual(
            set(self.reservas(corrida).values_list("tipo", "silo_id", "cantidad_planificada")),
            {
                (ReservaSiloProceso.Tipo.ORIGEN, self.origen.pk, Decimal("1000")),
                (ReservaSiloProceso.Tipo.DESTINO, self.tk_descremada.pk, Decimal("970")),
                (ReservaSiloProceso.Tipo.DESTINO, self.tk_crema.pk, Decimal("25")),
            },
        )
        # Preparar no mueve leche ni registra entrada: eso es iniciar.
        self.assertFalse(corrida.ejecucion.entradas.exists())

    def test_el_servidor_elige_el_analisis_y_asigna_el_codigo(self):
        nuevo = self.analizar(self.origen, minutos=30, grasa="2.70")

        corrida = self.preparada(codigo="DES-TECLEADO", analisis_entrada=self.analisis.pk)

        self.assertEqual(corrida.analisis_entrada, nuevo)
        self.assertEqual(corrida.grasa_entrada, Decimal("2.70"))
        self.assertNotEqual(corrida.ejecucion.codigo, "DES-TECLEADO")

    def test_sin_segunda_firma_igual_se_prepara(self):
        # La firma es motivo de inicio, no de preparación (como Evaporación).
        self.analizar(self.origen, minutos=30, segunda_firma=False)

        self.preparada()

    def test_sin_composicion_no_se_prepara(self):
        self.analizar(self.origen, minutos=30, grasa=None)

        respuesta = self.preparar()

        self.assertEqual(respuesta.status_code, 400, respuesta.data)
        self.assertIn("grasa y SNG", str(respuesta.data))
        self.assertFalse(CorridaDescremacion.objects.filter(silo_entera=self.origen).exists())

    def test_un_tk_sin_capacidad_no_deja_nada_escrito(self):
        self.tk_crema.capacidad_l = 10
        self.tk_crema.save(update_fields=["capacidad_l"])

        respuesta = self.preparar()

        self.assertEqual(respuesta.status_code, 400, respuesta.data)
        self.assertIn("no tiene capacidad", str(respuesta.data))
        self.assertFalse(CorridaDescremacion.objects.filter(silo_entera=self.origen).exists())
        self.assertFalse(ReservaSiloProceso.objects.filter(silo=self.tk_crema).exists())
        self.assertFalse(EjecucionProceso.objects.filter(equipo=self.descremadora).exists())

    def test_una_descremadora_ocupada_no_se_prepara(self):
        self.preparada()

        respuesta = self.preparar(
            silo_descremada=self.otro_tk_descremada.pk, estanque_crema=self.otro_tk_crema.pk,
        )

        self.assertEqual(respuesta.status_code, 400, respuesta.data)
        self.assertIn("ocupad", str(respuesta.data))
        self.assertEqual(EjecucionProceso.objects.filter(equipo=self.descremadora).count(), 1)

    def test_un_tk_reservado_por_otra_preparacion_no_se_asigna(self):
        primera = self.preparada()

        respuesta = self.preparar(
            equipo=self.otra_descremadora.pk, estanque_crema=self.otro_tk_crema.pk,
        )

        self.assertEqual(respuesta.status_code, 400, respuesta.data)
        self.assertIn(f"ya está reservado por {primera.ejecucion.codigo}", str(respuesta.data))
        self.assertFalse(EjecucionProceso.objects.filter(equipo=self.otra_descremadora).exists())

    def test_una_descremadora_en_cip_no_se_prepara(self):
        self.cip(self.descremadora)

        respuesta = self.preparar()

        self.assertEqual(respuesta.status_code, 400, respuesta.data)
        self.assertIn("CIP", str(respuesta.data))

    def test_secado_no_prepara(self):
        respuesta = self.preparar(usuario=self.secador)

        self.assertEqual(respuesta.status_code, 403)
        self.assertFalse(EjecucionProceso.objects.filter(equipo=self.descremadora).exists())


class IniciarDescremadoTests(BasePuestoDescremado):
    def iniciar(self, corrida, usuario=None):
        return self.cliente(usuario).post(f"/api/procesos/descremaciones/{corrida.pk}/iniciar/")

    def test_sin_motivos_inicia_con_una_entrada_y_sin_reservas_nuevas(self):
        corrida = self.preparada()
        self.assertEqual(motivos_para_iniciar_descremacion(corrida), [])

        respuesta = self.iniciar(corrida)

        self.assertEqual(respuesta.status_code, 200, respuesta.data)
        corrida.refresh_from_db()
        corrida.ejecucion.refresh_from_db()
        self.assertEqual(corrida.estado, CorridaDescremacion.Estado.EN_CURSO)
        self.assertEqual(corrida.ejecucion.estado, EjecucionProceso.Estado.EJECUCION)
        self.assertEqual(corrida.ejecucion.entradas.count(), 1)
        self.assertEqual(
            ReservaSiloProceso.objects.filter(ejecucion_id=corrida.ejecucion_id).count(), 3,
        )

    def test_sin_segunda_firma_no_inicia_y_se_resuelve_en_silos(self):
        self.analizar(self.origen, minutos=30, segunda_firma=False)
        corrida = self.preparada()

        motivo, resolver_en = motivos_tipados_para_iniciar_descremacion(corrida)[0]

        self.assertIn("firma de realización y visualización", motivo)
        self.assertEqual(resolver_en, RESOLVER_SILOS)
        respuesta = self.iniciar(corrida)
        self.assertEqual(respuesta.status_code, 409, respuesta.data)
        self.assertIn(motivo, str(respuesta.data))
        corrida.ejecucion.refresh_from_db()
        self.assertEqual(corrida.ejecucion.estado, EjecucionProceso.Estado.PREPARACION)
        self.assertFalse(corrida.ejecucion.entradas.exists())

    def test_una_descremadora_en_cip_se_resuelve_en_inocuidad(self):
        corrida = self.preparada()
        self.cip(self.descremadora)

        motivo, resolver_en = motivos_tipados_para_iniciar_descremacion(corrida)[0]

        self.assertIn("CIP", motivo)
        self.assertEqual(resolver_en, RESOLVER_CIP)

    def test_un_analisis_mas_nuevo_impide_iniciar_con_la_composicion_vieja(self):
        corrida = self.preparada()
        self.analizar(self.origen, minutos=10, grasa="2.90")

        self.assertEqual(
            motivos_tipados_para_iniciar_descremacion(corrida),
            [(
                f"El análisis con que se preparó {corrida.ejecucion.codigo} ya no es el "
                f"vigente de {self.origen.codigo}: cancela la preparación y vuelve a "
                "prepararla con la composición actual.",
                None,
            )],
        )

    def test_los_motivos_son_lo_que_rechaza_iniciar(self):
        corrida = self.preparada()
        self.tk_crema.estado = Silo.Estado.EN_CIP
        self.tk_crema.save(update_fields=["estado"])
        motivos = motivos_para_iniciar_descremacion(corrida)
        self.assertTrue(motivos)

        with self.assertRaises(ValidationError) as error:
            iniciar_descremacion(corrida_id=corrida.pk, usuario=self.condensador)

        self.assertEqual(error.exception.messages[0], motivos[0])

    def test_un_aseo_observado_avisa_y_queda_en_el_evento(self):
        corrida = self.preparada()
        self.cip(self.descremadora, estado=CicloCIP.Estado.OBSERVADO, horas=3)
        self.assertEqual(motivos_para_iniciar_descremacion(corrida), [])

        iniciar_descremacion(corrida_id=corrida.pk, usuario=self.condensador)

        evento = corrida.ejecucion.eventos.get(estado_nuevo=EjecucionProceso.Estado.EJECUCION)
        self.assertIn("Advertencia no bloqueante de aseo", evento.motivo)

    def test_una_corrida_iniciada_no_vuelve_a_iniciar(self):
        corrida = self.en_curso()

        self.assertEqual(self.iniciar(corrida).status_code, 409)

    def test_secado_no_inicia(self):
        corrida = self.preparada()

        self.assertEqual(self.iniciar(corrida, self.secador).status_code, 403)
        corrida.ejecucion.refresh_from_db()
        self.assertEqual(corrida.ejecucion.estado, EjecucionProceso.Estado.PREPARACION)
```

- [ ] **Step 2: Verificar que fallan**

Run: `cd backend && DJANGO_ENV=test ./.venv/Scripts/python.exe manage.py test procesos.tests_puesto_descremado --noinput`
Expected: ERROR `ImportError: cannot import name 'RESOLVER_SILOS'`.

- [ ] **Step 3: El último análisis confirmado, una consulta** — en `backend/recepcion/servicios.py`, encima de `motivos_silo_no_disponible`:

```python
def ultimo_analisis_confirmado(silo):
    """
    El análisis que describe hoy el silo: el último confirmado. Es el que lee
    la compuerta de proceso (`motivos_silo_no_disponible`) y el que usa
    Descremado para congelar la composición al preparar: con dos consultas,
    el puesto prepararía con un análisis y el inicio evaluaría otro.
    """
    return (
        AnalisisSilo.objects.filter(silo=silo, estado=AnalisisSilo.Estado.CONFIRMADO)
        .select_related("analista", "visualizado_por")
        .order_by("-tomado_en", "-id")
        .first()
    )
```

(`AnalisisSilo` ya se importa a nivel de módulo, línea 14). Reemplaza las dos consultas en línea del mismo hecho por la función: en `motivos_silo_no_disponible` (`analisis = (AnalisisSilo.objects.filter(…).first())`, ~62-68, y su `from .models import AnalisisSilo` local) y en el despacho de leche a granel (`analisis = AnalisisSilo.objects.filter(…).order_by("-tomado_en", "-id").first()`, ~510) por `analisis = ultimo_analisis_confirmado(silo)`.

- [ ] **Step 4: Reglas de origen y destino** — en `backend/procesos/servicios.py`, junto a `RESOLVER_CIP`/`RESOLVER_CALIDAD`:

```python
# Motivos del silo de origen (análisis, firmas, inhibidores, 48 h, estado):
# se resuelven donde Recepción y Calidad analizan los silos.
RESOLVER_SILOS = "/silos"
```

y antes de `iniciar_descremacion`:

```python
# Estados en que un estanque no recibe producto ni se procesa desde él. Los
# mismos que `iniciar_descremacion` y `cerrar_descremacion` usaban en línea.
ESTADOS_SILO_SIN_PRODUCTO = frozenset({"bloqueado_calidad", "en_cip", "fuera_servicio"})


def motivos_para_preparar_desde_silo(silo, analisis):
    """
    Por qué no se puede preparar un descremado desde `silo` con `analisis` (el
    último confirmado, `ultimo_analisis_confirmado`). Lista vacía: se puede.

    Solo lo que el **plan** necesita: el silo en servicio y una composición
    vigente. Firmas, inhibidores y la revalidación de 48 h no frenan la
    preparación: son motivos de inicio y la tarjeta los muestra con su enlace,
    como en Evaporación. El puesto ofrece los silos con esta función y
    `crear_descremacion_guiada` rechaza con ella.
    """
    if not silo.activo or silo.estado in ESTADOS_SILO_SIN_PRODUCTO:
        estado = "fuera de servicio" if not silo.activo else silo.get_estado_display().lower()
        return [f"{silo.codigo} está {estado}."]
    if analisis is None:
        return [f"{silo.codigo} no tiene un análisis confirmado: Calidad debe analizarlo."]
    motivos = []
    if not analisis.vigente:
        motivos.append(
            f"{silo.codigo}: "
            + (analisis.motivo_vigencia or "el análisis perdió vigencia; vuelve a muestrear.")
        )
    if analisis.grasa is None or analisis.sng is None:
        motivos.append(
            f"{silo.codigo}: el análisis no tiene grasa y SNG, y sin composición no hay plan."
        )
    return motivos


def motivos_origen_descremacion(origen, litros, *, excluir_ejecucion_id=None):
    """
    Si el silo de origen tiene `litros` libres: su saldo menos lo que otras
    ejecuciones reservaron como origen. Una sola regla para preparar y para
    iniciar: con dos, el puesto prepararía una corrida que «Iniciar» rechaza.
    """
    from recepcion.servicios import saldo_silo

    libre = saldo_silo(origen) - litros_origen_reservados(
        silo_id=origen.pk, excluir_ejecucion_id=excluir_ejecucion_id,
    )
    if libre < Decimal(str(litros)):
        return [f"{origen.codigo} tiene {libre} L libres; la corrida requiere {litros} L."]
    return []


def motivos_destino_descremacion(destino, *, producto=None, litros=None, excluir_ejecucion_id=None):
    """
    Por qué `destino` no puede recibir una rama del descremado. Sin `producto`
    ni `litros` comprueba solo estado y reservas —lo que el puesto usa para
    ofrecer el TK—; con ellos, también mezcla y capacidad, que dependen del
    plan. Preparar, iniciar y el puesto llaman a esta misma función.
    """
    from recepcion.servicios import saldo_silo

    motivos = []
    if not destino.activo or destino.estado in ESTADOS_SILO_SIN_PRODUCTO:
        motivos.append(f"{destino.codigo} no admite producto.")
    reserva = (
        reservas_activas_silo(silo_id=destino.pk, excluir_ejecucion_id=excluir_ejecucion_id)
        .select_related("ejecucion").order_by("pk").first()
    )
    if reserva is not None:
        motivos.append(f"{destino.codigo} ya está reservado por {reserva.ejecucion.codigo}.")
    if producto is None and litros is None:
        return motivos
    saldo = saldo_silo(destino)
    if producto is not None and saldo > 0 and destino.producto_actual_id not in {None, producto.pk}:
        motivos.append(f"{destino.codigo} contiene otro producto y no admite la mezcla.")
    if litros is not None and saldo + Decimal(str(litros)) > destino.capacidad_l:
        motivos.append(f"{destino.codigo} no tiene capacidad para los {litros} L planificados.")
    return motivos


@transaction.atomic
def preparar_descremacion(*, corrida_id, usuario):
    """
    Reserva el silo de origen y los dos TK y toma la descremadora
    (`borrador → preparacion`). Lo llama `crear_descremacion_guiada` al final
    de su transacción: si algo falla no queda corrida, ni reservas, ni máquina
    ocupada. Las reglas son las mismas que vuelve a aplicar el inicio.
    """
    from inventario.servicios import motivo_equipo_no_habilitado
    from maestros.models import Silo

    corrida = (
        CorridaDescremacion.objects.select_for_update(of=("self",))
        .select_related("producto_descremada", "producto_crema").get(pk=corrida_id)
    )
    ejecucion = (
        EjecucionProceso.objects.select_for_update(of=("self",))
        .select_related("equipo").get(pk=corrida.ejecucion_id)
    )
    if (
        corrida.estado != CorridaDescremacion.Estado.BORRADOR
        or ejecucion.estado != EjecucionProceso.Estado.BORRADOR
    ):
        raise ValidationError(f"{ejecucion.codigo} ya no está en borrador: no se vuelve a preparar.")
    if not ejecucion.equipo_id:
        raise ValidationError({"equipo": "La descremación requiere una descremadora asignada."})
    impedimento = motivo_equipo_no_habilitado(ejecucion.equipo)
    if impedimento:
        raise ValidationError({"equipo": impedimento})
    silos = {
        silo.pk: silo
        for silo in Silo.objects.select_for_update().filter(pk__in=[
            corrida.silo_entera_id, corrida.silo_descremada_id, corrida.estanque_crema_id,
        ]).order_by("pk")
    }
    origen = silos[corrida.silo_entera_id]
    destino_descremada = silos[corrida.silo_descremada_id]
    destino_crema = silos[corrida.estanque_crema_id]
    motivos = motivos_origen_descremacion(
        origen, corrida.litros_entrada, excluir_ejecucion_id=ejecucion.pk,
    )
    for destino, producto, litros in (
        (destino_descremada, corrida.producto_descremada, corrida.litros_descremada_plan),
        (destino_crema, corrida.producto_crema, corrida.litros_crema_plan),
    ):
        motivos.extend(motivos_destino_descremacion(
            destino, producto=producto, litros=litros, excluir_ejecucion_id=ejecucion.pk,
        ))
    if motivos:
        raise ValidationError(motivos[0])
    crear_en_lote_con_auditoria([
        ReservaSiloProceso(
            ejecucion=ejecucion, silo=origen, producto=origen.producto_actual,
            tipo=ReservaSiloProceso.Tipo.ORIGEN, cantidad_planificada=corrida.litros_entrada,
        ),
        ReservaSiloProceso(
            ejecucion=ejecucion, silo=destino_descremada, producto=corrida.producto_descremada,
            tipo=ReservaSiloProceso.Tipo.DESTINO,
            cantidad_planificada=corrida.litros_descremada_plan,
        ),
        ReservaSiloProceso(
            ejecucion=ejecucion, silo=destino_crema, producto=corrida.producto_crema,
            tipo=ReservaSiloProceso.Tipo.DESTINO, cantidad_planificada=corrida.litros_crema_plan,
        ),
    ])
    transicionar_ejecucion(
        ejecucion_id=ejecucion.pk, estado_nuevo=EjecucionProceso.Estado.PREPARACION,
        usuario=usuario, motivo="Preparación desde el puesto de Descremado.",
    )
    return CorridaDescremacion.objects.select_related(
        "ejecucion__etapa", "ejecucion__equipo", "orden", "analisis_entrada",
        "producto_descremada", "producto_crema",
        "silo_entera", "silo_descremada", "estanque_crema", "iniciada_por", "finalizada_por",
    ).get(pk=corrida.pk)
```

- [ ] **Step 5: Preparar elige el análisis, asigna el código y reserva** — en `crear_descremacion_guiada`:
  - Firma: quita `codigo` y `analisis_entrada_id` (el resto igual).
  - Docstring: «Prepara una descremación: corrida, reservas de silo y descremadora tomada, en una sola transacción —todo o nada—. El análisis y el código los pone el servidor.»
  - Imports de la función: `from inventario.servicios import motivo_equipo_no_habilitado`, `from maestros.models import Equipo, Producto, Silo`, `from recepcion.servicios import ultimo_analisis_confirmado` (quita `from recepcion.models import AnalisisSilo`).
  - Después de comprobar la compatibilidad del equipo, agrega:

```python
    impedimento = motivo_equipo_no_habilitado(equipo)
    if impedimento:
        raise ValidationError({"equipo": impedimento})

    # El análisis lo elige el servidor: el último confirmado del silo, el
    # mismo que lee `motivos_silo_no_disponible` al iniciar. Un análisis
    # elegido en el cliente podía ser uno viejo, y el inicio evaluaba otro.
    analisis = ultimo_analisis_confirmado(origen)
    motivos = motivos_para_preparar_desde_silo(origen, analisis)
    if motivos:
        raise ValidationError({"silo_entera": motivos[0]})
```

  y borra el bloque `try: analisis = AnalisisSilo.objects.get(pk=analisis_entrada_id, …)` con sus dos comprobaciones (confirmado/vigente, grasa/SNG).
  - Reemplaza el final (desde `ejecucion = crear_ejecucion_proceso(datos={` hasta el `return crear_corrida_descremacion(...)`) por:

```python
    ejecucion = crear_ejecucion_proceso(datos={
        # Provisional: el código usa el id de la corrida, que todavía no
        # existe. Todo ocurre en esta transacción: nadie ve este valor.
        "codigo": f"EJ-DES-TMP-{uuid.uuid4().hex}",
        "etapa": etapa,
        "sucursal": origen.sucursal,
        "equipo": equipo,
        "responsable": usuario,
    })
    corrida = crear_corrida_descremacion(datos={
        "ejecucion": ejecucion,
        "silo_entera": origen,
        "analisis_entrada": analisis,
        "litros_entrada": Decimal(str(litros_entrada)),
        "grasa_entrada": analisis.grasa,
        "sng_entrada": analisis.sng,
        "silo_descremada": destinos[silo_descremada_id],
        "estanque_crema": destinos[estanque_crema_id],
        "producto_descremada": productos[producto_descremada_id],
        "producto_crema": productos[producto_crema_id],
        "ruta_descremada": rutas.get(ruta_descremada_id),
        "ruta_crema": rutas.get(ruta_crema_id),
        "destino_descremada": destino_descremada,
        "destino_crema": destino_crema,
        "litros_descremada_plan": Decimal(str(litros_descremada_plan)),
        "litros_crema_plan": Decimal(str(litros_crema_plan)),
        "fuente_plan": sugerencia["fuente_plan"],
        "plan_confirmado_por": usuario,
        "plan_confirmado_en": timezone.now(),
    })
    # Como `EJ-PROD-{lote}` y los lotes `INT-DES-{corrida}-LD/CR`: el código
    # lo pone el servidor, y la tarjeta del puesto se reconoce por él.
    ejecucion.codigo = f"EJ-DES-{corrida.pk}"
    ejecucion.save(update_fields=["codigo"])
    return preparar_descremacion(corrida_id=corrida.pk, usuario=usuario)
```

- [ ] **Step 6: Una regla de inicio** — en `backend/procesos/servicios.py`, antes de `iniciar_descremacion`:

```python
def motivos_tipados_para_iniciar_descremacion(corrida, *, ejecucion=None):
    """
    Lo que impide iniciar esta descremación, como pares `(motivo,
    resolver_en)`, en el orden en que el inicio lo comprueba. Lista vacía: se
    puede.

    Es la única implementación de esas reglas: `iniciar_descremacion` lanza el
    primer motivo y el puesto los muestra junto a un botón deshabilitado,
    enlazando a donde se resuelve el primero. Un aseo observado **no** está
    aquí: avisa, no bloquea.
    """
    from inventario.servicios import motivo_equipo_no_habilitado
    from recepcion.servicios import motivos_silo_no_disponible, ultimo_analisis_confirmado

    ejecucion = ejecucion or corrida.ejecucion
    if (
        corrida.estado != CorridaDescremacion.Estado.BORRADOR
        or ejecucion.estado != EjecucionProceso.Estado.PREPARACION
    ):
        # Lo demás no aplica a una corrida que no está preparada.
        return [(
            f"{ejecucion.codigo} no está preparada: está "
            f"{ejecucion.get_estado_display().lower()}.",
            None,
        )]
    motivos = []
    if not (
        corrida.litros_descremada_plan and corrida.litros_crema_plan
        and corrida.plan_confirmado_por_id and corrida.plan_confirmado_en
    ):
        motivos.append(("Calcula y confirma el reparto planificado antes de iniciar.", None))
    try:
        corrida.clean()
    except ValidationError as error:
        motivos.extend((mensaje, None) for mensaje in error.messages)
    if not ejecucion.equipo_id:
        motivos.append(("La descremación requiere una descremadora asignada.", None))
    else:
        impedimento = motivo_equipo_no_habilitado(ejecucion.equipo)
        if impedimento:
            motivos.append((impedimento, RESOLVER_CIP))
    origen = corrida.silo_entera
    del_silo = motivos_silo_no_disponible(origen, para="proceso")
    if del_silo:
        motivos.append((f"{origen.codigo}: " + " ".join(del_silo), RESOLVER_SILOS))
    vigente = ultimo_analisis_confirmado(origen)
    if vigente is not None and (
        vigente.pk != corrida.analisis_entrada_id
        or (vigente.grasa, vigente.sng) != (corrida.grasa_entrada, corrida.sng_entrada)
    ):
        # Analizar de nuevo no arregla esto: la corrida congeló la composición
        # vieja. Se arregla cancelando y volviendo a preparar, en el puesto.
        motivos.append((
            f"El análisis con que se preparó {ejecucion.codigo} ya no es el vigente de "
            f"{origen.codigo}: cancela la preparación y vuelve a prepararla con la "
            "composición actual.",
            None,
        ))
    motivos.extend(
        (motivo, None) for motivo in motivos_origen_descremacion(
            origen, corrida.litros_entrada, excluir_ejecucion_id=ejecucion.pk,
        )
    )
    for destino, producto, litros in (
        (corrida.silo_descremada, corrida.producto_descremada, corrida.litros_descremada_plan),
        (corrida.estanque_crema, corrida.producto_crema, corrida.litros_crema_plan),
    ):
        motivos.extend(
            (motivo, None) for motivo in motivos_destino_descremacion(
                destino, producto=producto, litros=litros, excluir_ejecucion_id=ejecucion.pk,
            )
        )
    propias = set(
        ReservaSiloProceso.objects.filter(
            ejecucion=ejecucion, estado=ReservaSiloProceso.Estado.ACTIVA,
        ).values_list("tipo", "silo_id")
    )
    esperadas = {
        (ReservaSiloProceso.Tipo.ORIGEN, corrida.silo_entera_id),
        (ReservaSiloProceso.Tipo.DESTINO, corrida.silo_descremada_id),
        (ReservaSiloProceso.Tipo.DESTINO, corrida.estanque_crema_id),
    }
    if not esperadas <= propias:
        motivos.append((
            "Las reservas de origen y destino de la preparación no están completas: "
            "cancela la preparación y vuelve a prepararla.",
            None,
        ))
    return motivos


def motivos_para_iniciar_descremacion(corrida, *, ejecucion=None):
    """Los textos de `motivos_tipados_para_iniciar_descremacion`. Lista vacía: se puede."""
    return [
        motivo for motivo, _ in
        motivos_tipados_para_iniciar_descremacion(corrida, ejecucion=ejecucion)
    ]
```

- [ ] **Step 7: Iniciar ya no reserva** — reemplaza `iniciar_descremacion` completa por:

```python
@transaction.atomic
def iniciar_descremacion(*, corrida_id, usuario):
    """
    Pasa una descremación preparada a ejecución. Recalcula los motivos con la
    corrida, la ejecución y los silos bloqueados —entre que el puesto los
    mostró y el clic pudo perder vigencia el análisis o entrar un CIP— y lanza
    el primero. No crea reservas: nacieron al preparar.
    """
    from inventario.servicios import advertencia_aseo_equipo
    from maestros.models import Silo
    from .models import EntradaProceso

    corrida = (
        CorridaDescremacion.objects.select_for_update(of=("self",))
        .select_related("analisis_entrada", "producto_descremada", "producto_crema")
        .get(pk=corrida_id)
    )
    ejecucion = (
        EjecucionProceso.objects.select_for_update(of=("self",))
        .select_related("etapa", "equipo").get(pk=corrida.ejecucion_id)
    )
    silos = {
        silo.pk: silo
        for silo in Silo.objects.select_for_update().filter(pk__in=[
            corrida.silo_entera_id, corrida.silo_descremada_id, corrida.estanque_crema_id,
        ]).order_by("pk")
    }
    corrida.ejecucion = ejecucion
    corrida.silo_entera = silos[corrida.silo_entera_id]
    corrida.silo_descremada = silos[corrida.silo_descremada_id]
    corrida.estanque_crema = silos[corrida.estanque_crema_id]
    motivos = motivos_para_iniciar_descremacion(corrida, ejecucion=ejecucion)
    if motivos:
        raise ValidationError(motivos[0])

    EntradaProceso.objects.create(
        ejecucion=ejecucion, silo=corrida.silo_entera, tipo=EntradaProceso.Tipo.PRINCIPAL,
        cantidad=corrida.litros_entrada, unidad="L",
    )
    aseo = advertencia_aseo_equipo(ejecucion.equipo)
    transicionar_ejecucion(
        ejecucion_id=ejecucion.pk, estado_nuevo=EjecucionProceso.Estado.EJECUCION,
        usuario=usuario,
        motivo=(
            f"Advertencia no bloqueante de aseo: {aseo}"
            if aseo else "Inicio desde el puesto de Descremado."
        ),
    )
    corrida.estado = CorridaDescremacion.Estado.EN_CURSO
    corrida.iniciada_por = usuario
    corrida.iniciada_en = timezone.now()
    corrida.save(update_fields=["estado", "iniciada_por", "iniciada_en"])
    return CorridaDescremacion.objects.select_related(
        "ejecucion__etapa", "ejecucion__equipo", "orden", "analisis_entrada",
        "producto_descremada", "producto_crema",
        "silo_entera", "silo_descremada", "estanque_crema", "iniciada_por", "finalizada_por",
    ).get(pk=corrida.pk)
```

- [ ] **Step 8: Serializer y vista** — en `CrearDescremacionGuiadaSerializer` borra los campos `codigo` y `analisis_entrada` y agrega el docstring:

```python
    """
    Preparar un descremado. `codigo` y `analisis_entrada` no se reciben: el
    código lo asigna el servidor (`EJ-DES-{id}`) y el análisis es el último
    confirmado del silo. Si llegan, DRF los ignora.
    """
```

En `CorridaDescremacionViewSet.crear_guiada` quita `from recepcion.models import AnalisisSilo`, la variable `analisis` y la línea `and analisis.filter(pk=datos["analisis_entrada"]).exists()` de `ids_validos`, y en la llamada a `crear_descremacion_guiada` quita `codigo=datos["codigo"],` y `analisis_entrada_id=datos["analisis_entrada"],`.

- [ ] **Step 9: Migrar `tests_descremacion.py`**
  - Importa `preparar_descremacion` junto a `iniciar_descremacion`.
  - Fixture (`CierreDescremacionTests.setUp`): `codigo="EJ-DES-1"` → `codigo="EJ-DES-FIJA-1"`; en `test_un_tk_con_reserva_activa_no_se_asigna_a_otra_corrida`, `codigo="EJ-DES-2"` → `codigo="EJ-DES-FIJA-2"`.
  - Agrega a `CierreDescremacionTests`:

```python
    def preparar_fixture(self):
        """La fixture nace `borrador` por ORM; se prepara por el mismo camino que la API."""
        preparar_descremacion(corrida_id=self.corrida.pk, usuario=self.usuario)
```

  - `test_alta_guiada_crea_ejecucion_y_corrida_en_una_operacion`: quita `"codigo": "EJ-DES-GUIADA",` y `"analisis_entrada": self.corrida.analisis_entrada_id,` del payload; reemplaza `self.assertEqual(guiada.ejecucion.codigo, "EJ-DES-GUIADA")` por:

```python
        self.assertEqual(guiada.ejecucion.codigo, f"EJ-DES-{guiada.pk}")
        self.assertEqual(guiada.ejecucion.estado, EjecucionProceso.Estado.PREPARACION)
        self.assertEqual(guiada.analisis_entrada, self.corrida.analisis_entrada)
        self.assertEqual(
            ReservaSiloProceso.objects.filter(
                ejecucion=guiada.ejecucion, estado=ReservaSiloProceso.Estado.ACTIVA,
            ).count(),
            3,
        )
```

  - `test_inicio_reserva_origen_y_capacidad_y_cierre_consume_reservas` → renómbrala `test_preparar_reserva_iniciar_no_agrega_y_cerrar_consume`; reemplaza la primera línea (`iniciar_descremacion(...)`) y el `assertEqual(... count(), 3)` que sigue por:

```python
        self.preparar_fixture()
        self.assertEqual(
            ReservaSiloProceso.objects.filter(
                ejecucion=self.ejecucion, estado=ReservaSiloProceso.Estado.ACTIVA,
            ).count(),
            3,
        )
        iniciar_descremacion(corrida_id=self.corrida.pk, usuario=self.usuario)
        self.assertEqual(ReservaSiloProceso.objects.filter(ejecucion=self.ejecucion).count(), 3)
```

  - `test_cancelar_libera_las_reservas_de_tk`: `iniciar_descremacion(...)` → `self.preparar_fixture()`.
  - `test_no_inicia_si_el_plan_supera_capacidad_del_tk` → renómbrala `test_no_prepara_si_el_plan_supera_capacidad_del_tk`; dentro del `assertRaisesMessage` llama `self.preparar_fixture()`; reemplaza `self.assertFalse(self.ejecucion.entradas.exists())` por:

```python
        self.ejecucion.refresh_from_db()
        self.assertEqual(self.ejecucion.estado, EjecucionProceso.Estado.BORRADOR)
```

  - `test_un_tk_con_reserva_activa_no_se_asigna_a_otra_corrida`: la primera `iniciar_descremacion(corrida_id=self.corrida.pk, …)` → `self.preparar_fixture()`; la del `assertRaisesMessage` → `preparar_descremacion(corrida_id=segunda.pk, usuario=self.usuario)`.
  - `test_cierre_genera_dos_saldos_y_hereda_fifo_en_una_operacion` (:520) y `test_calidad_decide_descremada_y_crema_por_separado` (:710): antes de `iniciar_descremacion(...)` agrega `self.preparar_fixture()`.

- [ ] **Step 10: Verificar**

Run: `cd backend && DJANGO_ENV=test ./.venv/Scripts/python.exe manage.py test procesos.tests_puesto_descremado procesos.tests_descremacion --noinput`
Expected: OK.

Run: `cd backend && DJANGO_ENV=test ./.venv/Scripts/python.exe manage.py test procesos recepcion estandarizacion --noinput`
Expected: OK (`motivos_silo_no_disponible` cambió de consulta, no de regla).

- [ ] **Step 11: Commit**

```bash
git add backend/recepcion/servicios.py backend/procesos/servicios.py backend/procesos/serializers.py backend/procesos/views.py backend/procesos/tests_puesto_descremado.py backend/procesos/tests_descremacion.py
git commit -m "feat(procesos): preparar descremado reserva y toma la máquina; iniciar tiene una sola regla"
```

---

### Task 2: Un solo camino de inicio, cancelar la preparación y altas cerradas

**Files:**
- Modify: `backend/procesos/servicios.py` (constantes ~94; `bloquear_para_cancelar` ~1102; `transicionar_ejecucion` ~1202; `_deshacer_preparacion_descremacion` y `cancelar_preparacion_descremacion` junto a `cancelar_preparacion_evaporacion` ~2709; `inicio_reservado_al_puesto` ~2742)
- Modify: `backend/procesos/views.py` (imports ~53; `CorridaDescremacionViewSet` ~313; `EjecucionProcesoViewSet.create`/`perform_create` ~972-1013 y `transicionar` ~1159)
- Modify: `backend/procesos/tests_puesto_descremado.py`, `backend/procesos/tests_permisos_operacionales.py` (~81-114), `backend/procesos/tests_descremacion.py` (`test_cancelar_libera_las_reservas_de_tk`)

**Interfaces:**
- Consumes: `BasePuestoDescremado`, `preparar_descremacion`, `iniciar_descremacion` (Task 1).
- Produces (`procesos/servicios.py`):
  - `MENSAJE_INICIO_DESCREMADO_EN_PUESTO = "Las corridas de descremado se inician desde el puesto de Descremado."`
  - `MENSAJES_INICIO_EN_PUESTO: dict[str, str]` (`secado`, `descremacion`)
  - `inicio_reservado_al_puesto(ejecucion, estado_nuevo) -> bool` (ahora también Descremación)
  - `cancelar_preparacion_descremacion(*, corrida_id, usuario, motivo) -> EjecucionProceso`
- `POST /api/procesos/descremaciones/{id}/cancelar-preparacion/` `{"motivo": "…"}` → 200 `{"ejecucion_id", "ejecucion_codigo", "estado": "cancelada"}`; 400 `{"code", "message", "details"}`; 403 sin la etapa.
- `POST /api/procesos/ejecuciones/{id}/transicionar/ {"estado": "ejecucion"}` sobre una Descremación en `preparacion` → 400 `{"code": "VALIDACION_DOMINIO", "message": "Las corridas de descremado se inician desde el puesto de Descremado.", …}`.
- `POST /api/procesos/descremaciones/` → 405; `POST /api/procesos/ejecuciones/` → 405 (con permiso de la etapa; sin él, 403 como hoy).

- [ ] **Step 1: Pruebas que fallan** — en `tests_puesto_descremado.py` agrega a la importación de `.servicios`: `MENSAJE_INICIO_DESCREMADO_EN_PUESTO, MENSAJE_MOTIVO_CANCELACION, transicionar_ejecucion`, y al final:

```python
class InicioGenericoCerradoDescremadoTests(BasePuestoDescremado):
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
        self.assertEqual(respuesta.data["message"], MENSAJE_INICIO_DESCREMADO_EN_PUESTO)
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

    def test_el_alta_directa_de_corridas_esta_cerrada(self):
        respuesta = self.cliente().post("/api/procesos/descremaciones/", {}, format="json")

        self.assertEqual(respuesta.status_code, 405)

    def test_el_alta_generica_de_ejecuciones_esta_cerrada(self):
        respuesta = self.cliente().post(
            "/api/procesos/ejecuciones/",
            {"codigo": "EJ-DES-GENERICA", "etapa": self.etapa.pk, "equipo": self.descremadora.pk},
            format="json",
        )

        self.assertEqual(respuesta.status_code, 405)
        self.assertFalse(EjecucionProceso.objects.filter(codigo="EJ-DES-GENERICA").exists())


class CancelarPreparacionDescremadoTests(BasePuestoDescremado):
    def cancelar(self, corrida, motivo="TK equivocado", usuario=None):
        return self.cliente(usuario).post(
            f"/api/procesos/descremaciones/{corrida.pk}/cancelar-preparacion/",
            {"motivo": motivo}, format="json",
        )

    def corrida_heredada(self):
        """Una corrida `borrador` del modal viejo: ejecución en borrador, sin reservas."""
        ejecucion = EjecucionProceso.objects.create(
            codigo="EJ-DES-HEREDADA", etapa=self.etapa, sucursal=self.planta,
            equipo=self.descremadora, responsable=self.condensador,
        )
        return CorridaDescremacion.objects.create(
            ejecucion=ejecucion, silo_entera=self.origen, analisis_entrada=self.analisis,
            litros_entrada=Decimal("1000"), grasa_entrada=Decimal("2.61"),
            sng_entrada=Decimal("8.70"), silo_descremada=self.tk_descremada,
            estanque_crema=self.tk_crema, producto_descremada=self.producto_descremada,
            producto_crema=self.producto_crema, litros_descremada_plan=Decimal("970"),
            litros_crema_plan=Decimal("25"), plan_confirmado_por=self.condensador,
            plan_confirmado_en=timezone.now(),
        )

    def test_cancelar_suelta_reservas_y_maquina_y_anula_la_corrida(self):
        corrida = self.preparada()

        respuesta = self.cancelar(corrida)

        self.assertEqual(respuesta.status_code, 200, respuesta.data)
        self.assertEqual(respuesta.data, {
            "ejecucion_id": corrida.ejecucion_id,
            "ejecucion_codigo": corrida.ejecucion.codigo,
            "estado": EjecucionProceso.Estado.CANCELADA,
        })
        corrida.refresh_from_db()
        self.assertEqual(corrida.estado, CorridaDescremacion.Estado.ANULADA)
        self.assertEqual(corrida.motivo_anulacion, "TK equivocado.")
        self.assertEqual(
            set(ReservaSiloProceso.objects.filter(ejecucion_id=corrida.ejecucion_id)
                .values_list("estado", flat=True)),
            {ReservaSiloProceso.Estado.LIBERADA},
        )
        # La misma descremadora y los mismos TK se vuelven a preparar.
        self.preparada()

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
        self.assertIn("se cierra registrando sus salidas", respuesta.data["message"])

    def test_cancelar_desde_la_bandeja_generica_deja_lo_mismo(self):
        corrida = self.preparada()

        transicionar_ejecucion(
            ejecucion_id=corrida.ejecucion_id, estado_nuevo=EjecucionProceso.Estado.CANCELADA,
            usuario=self.condensador, motivo="Desde la bandeja",
        )

        corrida.refresh_from_db()
        self.assertEqual(corrida.estado, CorridaDescremacion.Estado.ANULADA)
        self.assertEqual(corrida.motivo_anulacion, "Desde la bandeja.")
        self.assertFalse(self.reservas(corrida).exists())

    def test_una_corrida_en_curso_cancelada_por_la_bandeja_queda_anulada(self):
        corrida = self.en_curso()

        transicionar_ejecucion(
            ejecucion_id=corrida.ejecucion_id, estado_nuevo=EjecucionProceso.Estado.CANCELADA,
            usuario=self.condensador, motivo="Falla eléctrica",
        )

        corrida.refresh_from_db()
        self.assertEqual(corrida.estado, CorridaDescremacion.Estado.ANULADA)

    def test_una_preparacion_heredada_en_borrador_se_cancela(self):
        corrida = self.corrida_heredada()

        respuesta = self.cancelar(corrida)

        self.assertEqual(respuesta.status_code, 200, respuesta.data)
        corrida.refresh_from_db()
        self.assertEqual(corrida.estado, CorridaDescremacion.Estado.ANULADA)

    def test_secado_no_cancela(self):
        corrida = self.preparada()

        self.assertEqual(self.cancelar(corrida, usuario=self.secador).status_code, 403)
        corrida.refresh_from_db()
        self.assertEqual(corrida.estado, CorridaDescremacion.Estado.BORRADOR)
```

En `tests_descremacion.py::test_cancelar_libera_las_reservas_de_tk`, al final agrega:

```python
        self.corrida.refresh_from_db()
        self.assertEqual(self.corrida.estado, CorridaDescremacion.Estado.ANULADA)
```

En `tests_permisos_operacionales.py`, reemplaza `test_alta_generica_solo_conserva_descremacion_y_su_area` por:

```python
    def test_alta_generica_de_ejecuciones_esta_cerrada_para_todas_las_etapas(self):
        # Una ejecución nace en la acción especializada de su proceso. El alta
        # genérica de Descremación creaba una ejecución sin corrida que podía
        # ocupar la descremadora sin pasar por el puesto.
        self.assertEqual(
            self._crear_ejecucion(
                self.secado, "EJ-SEC-PER", self.etapa_secado, self.torre
            ).status_code,
            405,
        )
        self.assertEqual(
            self._crear_ejecucion(
                self.condensacion, "EJ-DES-PER", self.etapa_descremacion,
                self.descremadora,
            ).status_code,
            405,
        )
        # Sin el permiso de la etapa sigue respondiendo 403: el permiso se
        # evalúa antes que la acción.
        self.assertEqual(
            self._crear_ejecucion(
                self.secado, "EJ-DES-NO", self.etapa_descremacion,
                self.descremadora,
            ).status_code,
            403,
        )
        self.assertEqual(
            self._crear_ejecucion(
                self.condensacion, "EJ-SEC-NO", self.etapa_secado, self.torre
            ).status_code,
            403,
        )
        self.assertFalse(EjecucionProceso.objects.filter(codigo="EJ-DES-PER").exists())
```

- [ ] **Step 2: Verificar que fallan**

Run: `cd backend && DJANGO_ENV=test ./.venv/Scripts/python.exe manage.py test procesos.tests_puesto_descremado procesos.tests_permisos_operacionales --noinput`
Expected: ERROR `ImportError: cannot import name 'MENSAJE_INICIO_DESCREMADO_EN_PUESTO'`.

- [ ] **Step 3: El inicio es del puesto, por etapa** — en `procesos/servicios.py`, debajo de `MENSAJE_INICIO_SECADO_EN_PUESTO`:

```python
MENSAJE_INICIO_DESCREMADO_EN_PUESTO = (
    "Las corridas de descremado se inician desde el puesto de Descremado."
)
# Etapas cuyo inicio (`preparacion → ejecucion`) es de su puesto: el puesto
# aplica la única función de motivos de esa etapa. La bandeja genérica no lo
# ofrece y `transicionar` lo rechaza con este mensaje. Espejo en el frontend:
# `textoIniciarEnPuesto` (`services/planta-ahora.ts`).
MENSAJES_INICIO_EN_PUESTO = {
    EtapaProceso.Tipo.SECADO: MENSAJE_INICIO_SECADO_EN_PUESTO,
    EtapaProceso.Tipo.DESCREMACION: MENSAJE_INICIO_DESCREMADO_EN_PUESTO,
}
```

y reemplaza `inicio_reservado_al_puesto`:

```python
def inicio_reservado_al_puesto(ejecucion, estado_nuevo):
    """
    ¿Es este paso el inicio de una corrida que solo inicia su puesto?
    (`MENSAJES_INICIO_EN_PUESTO`: Secado y Descremación). Reanudar
    (`pausada`/`bloqueada` → `ejecucion`) no es iniciar: sigue por la
    transición genérica, o una máquina pausada no tendría cómo volver.
    """
    return (
        estado_nuevo == EjecucionProceso.Estado.EJECUCION
        and ejecucion.estado == EjecucionProceso.Estado.PREPARACION
        and ejecucion.etapa.tipo in MENSAJES_INICIO_EN_PUESTO
    )
```

- [ ] **Step 4: Cancelar deshace lo propio de Descremación** — en `bloquear_para_cancelar` cambia la tupla a `(CorridaSecado, CorridaCondensacion, CorridaDescremacion)` y en su docstring agrega «`iniciar_descremacion`/`cancelar_preparacion_descremacion`» a la lista de pares con el mismo orden. En `transicionar_ejecucion`, después del bloque de Evaporación/Condensación:

```python
    if (
        estado_nuevo == EjecucionProceso.Estado.CANCELADA
        and ejecucion.etapa.tipo == EtapaProceso.Tipo.DESCREMACION
    ):
        # Por el puesto o por la bandeja genérica, cancelar deja lo mismo.
        _deshacer_preparacion_descremacion(ejecucion, motivo)
```

Junto a `cancelar_preparacion_evaporacion`:

```python
def _deshacer_preparacion_descremacion(ejecucion, motivo):
    """
    Lo propio de Descremación al cancelar su ejecución: la corrida queda
    `anulada` con el motivo. Las reservas las suelta la transición genérica, y
    la descremadora queda libre al salir de `ESTADOS_QUE_OCUPAN_EQUIPO`. No
    hay lote que anular ni leche que devolver: hasta el cierre no se mueve un
    litro.

    También una corrida ya iniciada, cancelada desde la bandeja: una corrida
    «en curso» sobre una ejecución cancelada no la hace nadie (como
    `_deshacer_preparacion_evaporacion` con la que está en proceso).
    """
    corrida = (
        CorridaDescremacion.objects.select_for_update(of=("self",))
        .filter(ejecucion=ejecucion).first()
    )
    if corrida is None or corrida.estado not in {
        CorridaDescremacion.Estado.BORRADOR, CorridaDescremacion.Estado.EN_CURSO,
    }:
        return
    corrida.estado = CorridaDescremacion.Estado.ANULADA
    corrida.motivo_anulacion = _con_punto(motivo)
    corrida.save(update_fields=["estado", "motivo_anulacion"])


@transaction.atomic
def cancelar_preparacion_descremacion(*, corrida_id, usuario, motivo):
    """
    Suelta una descremadora preparada sin iniciarla. Acepta la ejecución en
    `preparacion` y también en `borrador` (corridas heredadas del modal
    anterior, que nunca llegaron a reservar). Una corrida iniciada se cierra
    registrando sus salidas. Simétrica a `cancelar_preparacion_secado`; lo que
    se deshace lo hace la transición genérica.
    """
    motivo = (motivo or "").strip()
    if not motivo:
        raise ValidationError(MENSAJE_MOTIVO_CANCELACION)
    corrida = CorridaDescremacion.objects.select_for_update(of=("self",)).get(pk=corrida_id)
    ejecucion = (
        EjecucionProceso.objects.select_for_update(of=("self",)).get(pk=corrida.ejecucion_id)
    )
    if corrida.estado != CorridaDescremacion.Estado.BORRADOR or ejecucion.estado not in {
        EjecucionProceso.Estado.BORRADOR, EjecucionProceso.Estado.PREPARACION,
    }:
        raise ValidationError(
            f"Solo se cancela una descremadora preparada: {ejecucion.codigo} está "
            f"{ejecucion.get_estado_display().lower()}. Una corrida iniciada se cierra "
            "registrando sus salidas."
        )
    return transicionar_ejecucion(
        ejecucion_id=ejecucion.pk, estado_nuevo=EjecucionProceso.Estado.CANCELADA,
        usuario=usuario, motivo=motivo,
    )
```

- [ ] **Step 5: Vistas**
  - Importa de `.servicios`: `MENSAJES_INICIO_EN_PUESTO, cancelar_preparacion_descremacion` (quita `MENSAJE_INICIO_SECADO_EN_PUESTO` si queda sin uso en `views.py`).
  - `EjecucionProcesoViewSet.transicionar`: `DjangoValidationError(MENSAJE_INICIO_SECADO_EN_PUESTO)` → `DjangoValidationError(MENSAJES_INICIO_EN_PUESTO[actual.etapa.tipo])`. (`operativas` ya filtra con `inicio_reservado_al_puesto`: deja de ofrecer `ejecucion` a Descremación sin cambio.)
  - `EjecucionProcesoViewSet.create` y `perform_create` se reemplazan por:

```python
    def create(self, request, *args, **kwargs):
        # Una ejecución nace en la acción especializada de su proceso
        # (crear-guiada, preparar-continuacion, abrir un lote…). La excepción
        # de Descremación creaba una ejecución sin corrida que podía ocupar la
        # descremadora sin pasar por el puesto.
        raise MethodNotAllowed(
            "POST",
            detail="La ejecución debe crearse desde la acción especializada del proceso.",
        )
```

  - `CorridaDescremacionViewSet`: agrega, antes de `_error`:

```python
    def create(self, request, *args, **kwargs):
        raise MethodNotAllowed(
            "POST", detail="La corrida de descremado nace en el puesto de Descremado.",
        )
```

  y junto a `iniciar`:

```python
    @action(detail=True, methods=["post"], url_path="cancelar-preparacion")
    def cancelar_preparacion(self, request, pk=None):
        """Suelta una descremadora preparada: reservas liberadas, corrida anulada."""
        try:
            ejecucion = cancelar_preparacion_descremacion(
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

Run: `cd backend && DJANGO_ENV=test ./.venv/Scripts/python.exe manage.py test procesos --noinput`
Expected: OK (incluye `tests_puesto_secado`, que sigue recibiendo el mensaje de Secado, y `tests_concurrencia_equipo`).

- [ ] **Step 7: Commit**

```bash
git add backend/procesos/servicios.py backend/procesos/views.py backend/procesos/tests_puesto_descremado.py backend/procesos/tests_permisos_operacionales.py backend/procesos/tests_descremacion.py
git commit -m "feat(procesos): descremado se inicia solo en su puesto, se cancela con motivo y no nace por las altas genéricas"
```

---

### Task 3: Los límites de grasa avisan mientras se teclea y quedan al cerrar

**Files:**
- Modify: `backend/procesos/dominio.py` (límites y función pura, debajo de `calcular_balance_descremacion`)
- Modify: `backend/procesos/servicios.py` (`revisar_cierre_descremacion` junto a `cerrar_descremacion`; `cerrar_descremacion` ~2254-2268)
- Modify: `backend/procesos/serializers.py` (`RevisarCierreDescremacionSerializer` junto a `CierreDescremacionSerializer`, ~171)
- Modify: `backend/procesos/views.py` (`CorridaDescremacionViewSet.revisar_cierre`)
- Modify: `backend/procesos/tests_descremacion.py` (pruebas de dominio), `backend/procesos/tests_puesto_descremado.py`
- Modify: `docs/REGLAS_DE_PLANTA.md` (§2 y §8)

**Interfaces:**
- Consumes: `BasePuestoDescremado.en_curso` (Task 1).
- Produces (`procesos/dominio.py`): `LIMITE_GRASA_DESCREMADA`, `RANGO_GRASA_CREMA_DESPACHO`, `avisos_limites_descremacion(*, grasa_descremada, grasa_crema, crema_a_despacho) -> list[tuple[str, str]]`.
- Produces (`procesos/servicios.py`): `revisar_cierre_descremacion(corrida, *, litros_descremada=None, grasa_descremada=None, litros_crema=None, grasa_crema=None) -> dict`.
- `POST /api/procesos/descremaciones/{id}/revisar-cierre/` `{litros_descremada?, grasa_descremada?, litros_crema?, grasa_crema?}` (nulos o ausentes permitidos) → 200 `{"avisos_limites": [{"codigo", "mensaje"}], "avisos_balance": [str], "merma_l": str | null, "desvio_grasa_kg": str | null}`; no escribe nada.
- `cerrar/` guarda `controles["avisos_limites"] = [{"codigo", "mensaje"}]` **después** de los `controles` del cliente, y los mensajes van al `motivo` del evento `→ pendiente_control`.
- Mensajes exactos: «Grasa de la descremada 0,15 % sobre el límite de 0,1 %.» y «Grasa de la crema para despacho 41 % fuera del rango 42–43 %.»

- [ ] **Step 1: Pruebas de dominio que fallan** — en `tests_descremacion.py` cambia `from django.test import TestCase` por `from django.test import SimpleTestCase, TestCase`, `from .dominio import calcular_balance_descremacion` por `from .dominio import avisos_limites_descremacion, calcular_balance_descremacion`, y agrega debajo de `BalanceDescremacionTests`:

```python
class LimitesDescremacionTests(SimpleTestCase):
    """REGLAS_DE_PLANTA §2: avisan, no bloquean. Endurecerlos es de Calidad."""

    def codigos(self, **datos):
        base = {"grasa_descremada": None, "grasa_crema": None, "crema_a_despacho": False}
        return [codigo for codigo, _ in avisos_limites_descremacion(**{**base, **datos})]

    def test_descremada_sobre_el_limite_avisa(self):
        self.assertEqual(self.codigos(grasa_descremada="0.15"), ["grasa_descremada_alta"])
        self.assertEqual(self.codigos(grasa_descremada="0.11"), ["grasa_descremada_alta"])

    def test_descremada_en_el_limite_no_avisa(self):
        self.assertEqual(self.codigos(grasa_descremada="0.10"), [])
        self.assertEqual(self.codigos(grasa_descremada="0.05"), [])

    def test_crema_a_despacho_fuera_de_rango_avisa(self):
        for grasa in ("41", "41.99", "43.01"):
            with self.subTest(grasa=grasa):
                self.assertEqual(
                    self.codigos(grasa_crema=grasa, crema_a_despacho=True),
                    ["grasa_crema_fuera_de_rango"],
                )

    def test_crema_a_despacho_en_los_bordes_no_avisa(self):
        for grasa in ("42", "42.5", "43"):
            with self.subTest(grasa=grasa):
                self.assertEqual(self.codigos(grasa_crema=grasa, crema_a_despacho=True), [])

    def test_la_crema_que_no_va_a_despacho_no_tiene_limite(self):
        self.assertEqual(self.codigos(grasa_crema="41", crema_a_despacho=False), [])

    def test_un_valor_ausente_no_avisa(self):
        self.assertEqual(self.codigos(crema_a_despacho=True), [])

    def test_los_mensajes_se_leen_como_en_planta(self):
        self.assertEqual(
            avisos_limites_descremacion(
                grasa_descremada=Decimal("0.150"), grasa_crema=Decimal("41.00"),
                crema_a_despacho=True,
            ),
            [
                ("grasa_descremada_alta", "Grasa de la descremada 0,15 % sobre el límite de 0,1 %."),
                (
                    "grasa_crema_fuera_de_rango",
                    "Grasa de la crema para despacho 41 % fuera del rango 42–43 %.",
                ),
            ],
        )
```

- [ ] **Step 2: Pruebas del cierre que fallan** — al final de `tests_puesto_descremado.py`:

```python
class LimitesDelCierreTests(BasePuestoDescremado):
    def cuerpo(self, **cambios):
        datos = {
            "litros_descremada": "970", "grasa_descremada": "0.06",
            "litros_crema": "25", "grasa_crema": "42",
        }
        datos.update(cambios)
        return datos

    def revisar(self, corrida, datos, usuario=None):
        return self.cliente(usuario).post(
            f"/api/procesos/descremaciones/{corrida.pk}/revisar-cierre/", datos, format="json",
        )

    def cerrar(self, corrida, datos, usuario=None):
        return self.cliente(usuario).post(
            f"/api/procesos/descremaciones/{corrida.pk}/cerrar/", datos, format="json",
        )

    def crema_a(self, corrida, destino):
        CorridaDescremacion.objects.filter(pk=corrida.pk).update(destino_crema=destino)

    def test_revisar_cierre_avisa_y_no_escribe(self):
        corrida = self.en_curso()

        respuesta = self.revisar(corrida, self.cuerpo(grasa_descremada="0.15"))

        self.assertEqual(respuesta.status_code, 200, respuesta.data)
        self.assertEqual(
            [aviso["codigo"] for aviso in respuesta.data["avisos_limites"]],
            ["grasa_descremada_alta"],
        )
        self.assertEqual(respuesta.data["merma_l"], "5.00")
        corrida.refresh_from_db()
        self.assertEqual(corrida.estado, CorridaDescremacion.Estado.EN_CURSO)
        self.assertIsNone(corrida.grasa_descremada)
        self.assertEqual(corrida.controles, {})
        self.assertFalse(MovimientoSilo.objects.filter(operacion_id=corrida.operacion_id).exists())

    def test_revisar_con_campos_vacios_no_avisa(self):
        corrida = self.en_curso()

        respuesta = self.revisar(corrida, {"grasa_descremada": None, "litros_crema": None})

        self.assertEqual(respuesta.status_code, 200, respuesta.data)
        self.assertEqual(respuesta.data, {
            "avisos_limites": [], "avisos_balance": [], "merma_l": None, "desvio_grasa_kg": None,
        })

    def test_la_crema_fuera_de_rango_avisa_solo_si_va_a_despacho(self):
        corrida = self.en_curso()

        self.crema_a(corrida, CorridaDescremacion.DestinoRama.DESPACHO_DIRECTO)
        a_despacho = self.revisar(corrida, self.cuerpo(grasa_crema="41"))
        self.crema_a(corrida, CorridaDescremacion.DestinoRama.SIGUIENTE_PROCESO)
        a_mantequilla = self.revisar(corrida, self.cuerpo(grasa_crema="41"))

        self.assertEqual(
            [aviso["codigo"] for aviso in a_despacho.data["avisos_limites"]],
            ["grasa_crema_fuera_de_rango"],
        )
        self.assertEqual(a_mantequilla.data["avisos_limites"], [])

    def test_cerrar_guarda_los_avisos_y_el_cliente_no_los_pisa(self):
        corrida = self.en_curso()

        respuesta = self.cerrar(corrida, self.cuerpo(
            grasa_descremada="0.15", controles={"avisos_limites": [], "ph_salida": "6.7"},
        ))

        self.assertEqual(respuesta.status_code, 200, respuesta.data)
        corrida.refresh_from_db()
        self.assertEqual(corrida.controles["avisos_limites"], [{
            "codigo": "grasa_descremada_alta",
            "mensaje": "Grasa de la descremada 0,15 % sobre el límite de 0,1 %.",
        }])
        self.assertEqual(corrida.controles["ph_salida"], "6.7")
        evento = corrida.ejecucion.eventos.get(
            estado_nuevo=EjecucionProceso.Estado.PENDIENTE_CONTROL,
        )
        self.assertIn("0,15 %", evento.motivo)

    def test_descremada_en_el_limite_cierra_sin_aviso(self):
        corrida = self.en_curso()

        self.cerrar(corrida, self.cuerpo(grasa_descremada="0.10"))

        corrida.refresh_from_db()
        self.assertEqual(corrida.controles["avisos_limites"], [])

    def test_crema_de_despacho_fuera_de_rango_queda_al_cerrar(self):
        corrida = self.en_curso()
        self.crema_a(corrida, CorridaDescremacion.DestinoRama.DESPACHO_DIRECTO)

        respuesta = self.cerrar(corrida, self.cuerpo(grasa_crema="41"))

        self.assertEqual(respuesta.status_code, 200, respuesta.data)
        corrida.refresh_from_db()
        self.assertEqual(
            [aviso["codigo"] for aviso in corrida.controles["avisos_limites"]],
            ["grasa_crema_fuera_de_rango"],
        )

    def test_secado_no_revisa_ni_cierra(self):
        corrida = self.en_curso()

        self.assertEqual(self.revisar(corrida, self.cuerpo(), self.secador).status_code, 403)
        self.assertEqual(self.cerrar(corrida, self.cuerpo(), self.secador).status_code, 403)
```

Run: `cd backend && DJANGO_ENV=test ./.venv/Scripts/python.exe manage.py test procesos.tests_descremacion procesos.tests_puesto_descremado --noinput`
Expected: ERROR `ImportError: cannot import name 'avisos_limites_descremacion'`.

- [ ] **Step 3: La función pura** — en `procesos/dominio.py`, debajo de `calcular_balance_descremacion`:

```python
# Límites físicos de la descremación (docs/REGLAS_DE_PLANTA.md §2). Avisan,
# no bloquean: endurecerlos —que la grasa alta impida cerrar o retenga el
# TK— es decisión de Calidad y se hace aquí y en quien llama a
# `avisos_limites_descremacion`, no en una segunda regla.
LIMITE_GRASA_DESCREMADA = Decimal("0.1")  # %
RANGO_GRASA_CREMA_DESPACHO = (Decimal("42"), Decimal("43"))  # %


def _porcentaje(valor):
    """`Decimal("0.150")` → «0,15»: como se lee en planta."""
    return f"{valor.normalize():f}".replace(".", ",")


def avisos_limites_descremacion(*, grasa_descremada, grasa_crema, crema_a_despacho):
    """
    Los límites físicos que no cumple el cierre, como `(codigo, mensaje)`.

    Un valor ausente no avisa: todavía no se tecleó. El límite de la crema es
    el de «crema para despacho»: solo aplica si va a despacho directo; para
    Mantequilla o Estandarización el documento no da límite y no se inventa.
    Las RPM no están: no hay sensor ni campo, y en el documento son una
    alarma del arranque, no una medición del cierre.
    """
    avisos = []
    if grasa_descremada is not None:
        grasa = Decimal(str(grasa_descremada))
        if grasa > LIMITE_GRASA_DESCREMADA:
            avisos.append((
                "grasa_descremada_alta",
                f"Grasa de la descremada {_porcentaje(grasa)} % sobre el límite de "
                f"{_porcentaje(LIMITE_GRASA_DESCREMADA)} %.",
            ))
    if grasa_crema is not None and crema_a_despacho:
        grasa = Decimal(str(grasa_crema))
        minimo, maximo = RANGO_GRASA_CREMA_DESPACHO
        if not minimo <= grasa <= maximo:
            avisos.append((
                "grasa_crema_fuera_de_rango",
                f"Grasa de la crema para despacho {_porcentaje(grasa)} % fuera del rango "
                f"{_porcentaje(minimo)}–{_porcentaje(maximo)} %.",
            ))
    return avisos
```

- [ ] **Step 4: Revisar sin escribir y cerrar con los avisos** — en `procesos/servicios.py`, antes de `cerrar_descremacion`:

```python
def revisar_cierre_descremacion(
    corrida, *, litros_descremada=None, grasa_descremada=None,
    litros_crema=None, grasa_crema=None,
):
    """
    Lo que el cierre avisaría con estos valores, sin escribir nada. El
    formulario lo pide mientras se teclea (el patrón de `calcular/` del vale):
    la misma función de límites que `cerrar_descremacion` guarda y el mismo
    balance. El cliente no calcula nada por su cuenta.
    """
    from .dominio import avisos_limites_descremacion, calcular_balance_descremacion

    limites = avisos_limites_descremacion(
        grasa_descremada=grasa_descremada, grasa_crema=grasa_crema,
        crema_a_despacho=(
            corrida.destino_crema == CorridaDescremacion.DestinoRama.DESPACHO_DIRECTO
        ),
    )
    avisos_balance, merma, desvio = [], None, None
    if grasa_descremada is not None and grasa_crema is not None:
        con_litros = litros_descremada is not None and litros_crema is not None
        balance = calcular_balance_descremacion(
            corrida.litros_entrada, corrida.grasa_entrada, corrida.sng_entrada,
            grasa_descremada, grasa_crema,
            litros_descremada=litros_descremada if con_litros else None,
            litros_crema=litros_crema if con_litros else None,
        )
        avisos_balance = list(balance.avisos)
        merma, desvio = balance.merma_declarada_l, balance.desvio_grasa_kg
    return {
        "avisos_limites": [{"codigo": codigo, "mensaje": mensaje} for codigo, mensaje in limites],
        "avisos_balance": avisos_balance,
        # Texto, como en los serializers: el tipo del frontend es `string`.
        "merma_l": None if merma is None else str(merma.quantize(Decimal("0.01"))),
        "desvio_grasa_kg": None if desvio is None else str(desvio.quantize(Decimal("0.001"))),
    }
```

En `cerrar_descremacion`: cambia `from .dominio import calcular_balance_descremacion` por `from .dominio import avisos_limites_descremacion, calcular_balance_descremacion`, y reemplaza desde `corrida.controles = {**(controles or {}), "avisos_balance": list(balance.avisos)}` hasta la primera `transicionar_ejecucion(... PENDIENTE_CONTROL ...)` por:

```python
    limites = avisos_limites_descremacion(
        grasa_descremada=gd, grasa_crema=gc,
        crema_a_despacho=(
            corrida.destino_crema == CorridaDescremacion.DestinoRama.DESPACHO_DIRECTO
        ),
    )
    corrida.litros_descremada, corrida.grasa_descremada = ld, gd
    corrida.litros_crema, corrida.grasa_crema = lc, gc
    corrida.controles = {
        **(controles or {}),
        # Después de lo que manda el cliente: los avisos los escribe el
        # servidor y no se pueden pisar por `controles`.
        "avisos_balance": list(balance.avisos),
        "avisos_limites": [
            {"codigo": codigo, "mensaje": mensaje} for codigo, mensaje in limites
        ],
    }
    corrida.estado = CorridaDescremacion.Estado.CERRADA
    corrida.finalizada_por = usuario
    corrida.finalizada_en = ahora
    corrida.save()
    transicionar_ejecucion(
        ejecucion_id=corrida.ejecucion_id,
        estado_nuevo=EjecucionProceso.Estado.PENDIENTE_CONTROL, usuario=usuario,
        # Lo que lee la auditoría de la ejecución.
        motivo=" ".join(mensaje for _, mensaje in limites),
    )
```

(las dos líneas `corrida.litros_descremada, corrida.grasa_descremada = ld, gd` y `corrida.litros_crema, corrida.grasa_crema = lc, gc` que había antes quedan dentro de este bloque, no duplicadas).

- [ ] **Step 5: Serializer y vista** — en `serializers.py`, debajo de `CierreDescremacionSerializer`:

```python
class RevisarCierreDescremacionSerializer(serializers.Serializer):
    """El cuerpo de `cerrar/`, todo opcional: se pide mientras se teclea."""

    litros_descremada = serializers.DecimalField(
        max_digits=14, decimal_places=2, required=False, allow_null=True, default=None,
    )
    grasa_descremada = serializers.DecimalField(
        max_digits=6, decimal_places=3, required=False, allow_null=True, default=None,
    )
    litros_crema = serializers.DecimalField(
        max_digits=14, decimal_places=2, required=False, allow_null=True, default=None,
    )
    grasa_crema = serializers.DecimalField(
        max_digits=6, decimal_places=3, required=False, allow_null=True, default=None,
    )
```

En `views.py` importa `RevisarCierreDescremacionSerializer` y `revisar_cierre_descremacion`, y en `CorridaDescremacionViewSet`, antes de `cerrar`:

```python
    @action(detail=True, methods=["post"], url_path="revisar-cierre")
    def revisar_cierre(self, request, pk=None):
        """Avisos del cierre con lo tecleado hasta ahora; no escribe nada."""
        entrada = RevisarCierreDescremacionSerializer(data=request.data)
        entrada.is_valid(raise_exception=True)
        return Response(revisar_cierre_descremacion(self.get_object(), **entrada.validated_data))
```

- [ ] **Step 6: `docs/REGLAS_DE_PLANTA.md` §2** — reemplaza la tabla y el párrafo final de §2 (desde `| Parámetro | Valor | Estado |` hasta `valores tiene dónde vivir todavía.`) por:

```markdown
| Parámetro | Valor | Estado |
|---|---|---|
| RPM de la descremadora | **1.395 RPM** | No implementado: no hay sensor ni campo, y en el documento es una alarma del arranque, no una medición del cierre |
| Materia grasa de leche descremada | **≤ 0,1 %** | **Aviso** (desde 2026-10-07): `procesos.dominio.avisos_limites_descremacion` |
| Materia grasa de crema para despacho | **42 % – 43 %** | **Aviso**, solo si la crema va a despacho directo; para Mantequilla o Estandarización el documento no da límite y no se inventa |

Si no alcanza las RPM: quitar alarma, reintentar, informar a Mantenimiento.

Control cada hora sobre descremadora, pasteurizador, bombas, válvulas,
conexiones, caudalímetros, temperaturas, fugas y obstrucciones. No
implementado: es un registro periódico y se cargaría como plantilla de
`RegistroEquipo` (`/registros`), no en el puesto.

**El proceso existe** desde la migración `procesos.0008` (`CorridaDescremacion`)
y se opera en el puesto de Descremado (`/produccion/descremado`). Los dos
límites de grasa **avisan, no bloquean**: el puesto los muestra mientras se
teclea el cierre (`descremaciones/{id}/revisar-cierre/`, que no escribe) y el
cierre los guarda en `controles["avisos_limites"]` y en el motivo del evento
que pasa la ejecución a Calidad. Endurecerlos —que la grasa alta impida cerrar
o retenga el TK— es decisión de Calidad, y se hace en esa función y en quien
la llama, no en una segunda regla. Los límites son constantes de planta, no la
`Especificacion` del producto: la especificación la aplica Calidad al liberar
sobre el análisis del TK.
```

Y en la tabla de §8 agrega la fila:

```markdown
| ¿Los límites de grasa de la descremación bloquean el cierre o retienen el TK, en vez de avisar? | Calidad |
```

- [ ] **Step 7: Verificar**

Run: `cd backend && DJANGO_ENV=test ./.venv/Scripts/python.exe manage.py test procesos --noinput`
Expected: OK.

- [ ] **Step 8: Commit**

```bash
git add backend/procesos/dominio.py backend/procesos/servicios.py backend/procesos/serializers.py backend/procesos/views.py backend/procesos/tests_descremacion.py backend/procesos/tests_puesto_descremado.py docs/REGLAS_DE_PLANTA.md
git commit -m "feat(procesos): los límites de grasa de la descremación avisan mientras se teclea y quedan al cerrar"
```

---

### Task 4: Estado del puesto e historial con filtros de servidor

**Files:**
- Modify: `backend/procesos/servicios.py` (`estado_puesto_descremado`, después de `iniciar_descremacion`)
- Modify: `backend/procesos/views.py` (`CorridaDescremacionViewSet`: mixins, filtros, `puesto`)
- Modify: `backend/procesos/serializers.py` (`CorridaDescremacionSerializer.ejecucion_estado`)
- Modify: `backend/procesos/tests_puesto_descremado.py`
- Modify: `docs/superpowers/specs/2026-10-07-puesto-descremado-design.md` (§8)

**Interfaces:**
- Consumes: `motivos_tipados_para_iniciar_descremacion`, `motivos_para_preparar_desde_silo`, `motivos_destino_descremacion`, `RESOLVER_CIP`, `BasePuestoDescremado` (Tasks 1-3).
- Produces: `estado_puesto_descremado(usuario) -> dict` y `GET /api/procesos/descremaciones/puesto/` →

```json
{
  "descremadoras": [{
    "equipo_id": 12, "codigo": "des-01", "nombre": "Descremadora DES-01",
    "estado": "disponible | preparada | en_curso",
    "corrida": null | { "id": 8, "ejecucion_id": 120, "ejecucion_codigo": "EJ-DES-8",
                        "ejecucion_estado": "preparacion", "estado": "borrador",
                        "silo_entera": "Silo 3", "litros_entrada": "1000.00",
                        "grasa_entrada": "2.610", "sng_entrada": "8.700",
                        "silo_descremada": "Tk02", "litros_descremada_plan": "976.40",
                        "estanque_crema": "TkC2", "litros_crema_plan": "23.60",
                        "destino_crema": "siguiente_proceso", "iniciada_en": null },
    "motivos_para_tomar": [],
    "motivos_para_iniciar": ["Silo 3: El análisis requiere firma de realización y visualización."],
    "resolver_en": "/silos" | "/calidad/inocuidad" | null,
    "avisos": ["…aseo con observación…"],
    "en_calidad": null | { "id": 7, "ejecucion_codigo": "EJ-DES-7", "tanques": ["Tk02", "TkC2"] }
  }],
  "origenes": [{ "id": 3, "codigo": "Silo 3", "saldo_l": "24000.00",
                 "analisis": { "id": 55, "grasa": "2.61", "sng": "8.70",
                               "tomado_en": "2026-10-07T08:10:00-03:00" } | null,
                 "motivo": null | "…" }],
  "destinos_descremada": [{ "id": 21, "codigo": "Tk02", "libre_l": "30000.00" }],
  "destinos_crema": [{ "id": 31, "codigo": "TkC2", "libre_l": "8000.00" }],
  "corridas_de_hoy": [{ "id": 7, "ejecucion_codigo": "EJ-DES-7", "equipo": "des-01",
                        "silo_entera": "Silo 3", "estado": "cerrada", "estado_etiqueta": "Cerrada",
                        "estado_ejecucion": "pendiente_control" }],
  "estados": [{ "valor": "borrador", "etiqueta": "Borrador" }]
}
```

- `GET /api/procesos/descremaciones/?q=&estado=&desde=&hasta=&page=` filtra en el servidor (`q`: código de ejecución, silo de origen o TK; `estado`: estado de la **corrida**; fechas sobre `ejecucion__creada_en`). Cada fila trae `ejecucion_estado`.

- [ ] **Step 1: Pruebas que fallan** — al final de `tests_puesto_descremado.py`:

```python
class PuestoDescremadoTests(BasePuestoDescremado):
    def puesto(self, usuario=None):
        respuesta = self.cliente(usuario).get("/api/procesos/descremaciones/puesto/")
        self.assertEqual(respuesta.status_code, 200, respuesta.data)
        return respuesta.data

    def fila(self, datos, equipo):
        return next(item for item in datos["descremadoras"] if item["equipo_id"] == equipo.pk)

    def ids(self, filas, *objetos):
        propios = {objeto.pk for objeto in objetos}
        return [fila["id"] for fila in filas if fila["id"] in propios]

    def test_una_descremadora_sin_ejecucion_esta_disponible(self):
        fila = self.fila(self.puesto(), self.descremadora)

        self.assertEqual(fila["estado"], "disponible")
        self.assertIsNone(fila["corrida"])
        self.assertEqual(fila["motivos_para_tomar"], [])
        self.assertEqual(fila["motivos_para_iniciar"], [])
        self.assertIsNone(fila["en_calidad"])

    def test_una_preparada_trae_su_plan_y_puede_iniciarse(self):
        corrida = self.preparada()

        fila = self.fila(self.puesto(), self.descremadora)

        self.assertEqual(fila["estado"], "preparada")
        self.assertEqual(fila["corrida"]["id"], corrida.pk)
        self.assertEqual(fila["corrida"]["ejecucion_codigo"], f"EJ-DES-{corrida.pk}")
        self.assertEqual(fila["corrida"]["estado"], "borrador")
        self.assertEqual(fila["corrida"]["silo_entera"], self.origen.codigo)
        self.assertEqual(fila["corrida"]["litros_entrada"], "1000.00")
        self.assertEqual(fila["corrida"]["silo_descremada"], self.tk_descremada.codigo)
        self.assertEqual(fila["corrida"]["litros_descremada_plan"], "970.00")
        self.assertEqual(fila["corrida"]["estanque_crema"], self.tk_crema.codigo)
        self.assertEqual(fila["motivos_para_iniciar"], [])
        self.assertIsNone(fila["resolver_en"])

    def test_una_preparada_sin_segunda_firma_dice_por_que_y_donde(self):
        self.analizar(self.origen, minutos=30, segunda_firma=False)
        self.preparada()

        fila = self.fila(self.puesto(), self.descremadora)

        self.assertIn("firma de realización y visualización", fila["motivos_para_iniciar"][0])
        self.assertEqual(fila["resolver_en"], "/silos")

    def test_una_preparada_en_cip_se_resuelve_en_inocuidad(self):
        self.preparada()
        self.cip(self.descremadora)

        fila = self.fila(self.puesto(), self.descremadora)

        self.assertIn("CIP", fila["motivos_para_iniciar"][0])
        self.assertEqual(fila["resolver_en"], "/calidad/inocuidad")

    def test_una_descremadora_en_cip_no_se_toma(self):
        self.cip(self.descremadora)

        fila = self.fila(self.puesto(), self.descremadora)

        self.assertEqual(fila["estado"], "disponible")
        self.assertIn("CIP", fila["motivos_para_tomar"][0])
        self.assertEqual(fila["resolver_en"], "/calidad/inocuidad")

    def test_un_aseo_observado_es_aviso_no_motivo(self):
        self.preparada()
        self.cip(self.descremadora, estado=CicloCIP.Estado.OBSERVADO, horas=3)

        fila = self.fila(self.puesto(), self.descremadora)

        self.assertEqual(fila["motivos_para_iniciar"], [])
        self.assertTrue(fila["avisos"])

    def test_ejecucion_pausada_o_bloqueada_esta_en_curso(self):
        # «En curso manda sobre preparada» no se puede sembrar: la base impide
        # dos ocupaciones del mismo equipo (Desviación 10).
        corrida = self.en_curso()
        for estado in ("ejecucion", "pausada", "bloqueada"):
            EjecucionProceso.objects.filter(pk=corrida.ejecucion_id).update(estado=estado)
            with self.subTest(estado=estado):
                fila = self.fila(self.puesto(), self.descremadora)
                self.assertEqual(fila["estado"], "en_curso")
                self.assertEqual(fila["corrida"]["ejecucion_estado"], estado)
                self.assertEqual(fila["motivos_para_iniciar"], [])

    def test_un_huerfano_con_ejecucion_terminada_no_ocupa(self):
        corrida = self.preparada()
        EjecucionProceso.objects.filter(pk=corrida.ejecucion_id).update(
            estado=EjecucionProceso.Estado.CANCELADA,
        )

        datos = self.puesto()

        self.assertEqual(self.fila(datos, self.descremadora)["estado"], "disponible")
        self.assertEqual(self.ids(datos["corridas_de_hoy"], corrida), [])

    def test_en_calidad_informa_los_tk_retenidos(self):
        self.etapa.requiere_calidad = True
        self.etapa.save(update_fields=["requiere_calidad"])
        corrida = self.en_curso()
        cierre = self.cliente().post(
            f"/api/procesos/descremaciones/{corrida.pk}/cerrar/",
            {"litros_descremada": "970", "grasa_descremada": "0.06",
             "litros_crema": "25", "grasa_crema": "42"},
            format="json",
        )
        self.assertEqual(cierre.status_code, 200, cierre.data)

        fila = self.fila(self.puesto(), self.descremadora)

        self.assertEqual(fila["estado"], "disponible")
        self.assertEqual(fila["en_calidad"], {
            "id": corrida.pk, "ejecucion_codigo": corrida.ejecucion.codigo,
            "tanques": [self.tk_descremada.codigo, self.tk_crema.codigo],
        })

    def test_destinos_sin_bloqueados_en_cip_ni_reservados(self):
        self.otro_tk_descremada.estado = Silo.Estado.BLOQUEADO_CALIDAD
        self.otro_tk_descremada.save(update_fields=["estado"])
        self.otro_tk_crema.estado = Silo.Estado.EN_CIP
        self.otro_tk_crema.save(update_fields=["estado"])

        datos = self.puesto()

        self.assertEqual(
            self.ids(datos["destinos_descremada"], self.tk_descremada, self.otro_tk_descremada),
            [self.tk_descremada.pk],
        )
        self.assertEqual(
            self.ids(datos["destinos_crema"], self.tk_crema, self.otro_tk_crema),
            [self.tk_crema.pk],
        )
        tk = next(d for d in datos["destinos_descremada"] if d["id"] == self.tk_descremada.pk)
        self.assertEqual(tk["libre_l"], "30000.00")

        self.preparada()
        datos = self.puesto()

        self.assertEqual(self.ids(datos["destinos_descremada"], self.tk_descremada), [])
        self.assertEqual(self.ids(datos["destinos_crema"], self.tk_crema), [])

    def test_origenes_con_el_analisis_que_usara_preparar(self):
        sin_analisis = self._silo("SILO-PD-SIN", Silo.Tipo.SILO, 10000)
        MovimientoSilo.objects.create(
            silo=sin_analisis, tipo=MovimientoSilo.Tipo.INGRESO, litros=500,
            fecha_hora=timezone.now() - timedelta(hours=1),
            origen_tipo=MovimientoSilo.OrigenTipo.AJUSTE,
        )
        vacio = self._silo("SILO-PD-VACIO", Silo.Tipo.SILO, 10000)

        origenes = {item["id"]: item for item in self.puesto()["origenes"]}

        self.assertEqual(origenes[self.origen.pk]["analisis"]["id"], self.analisis.pk)
        self.assertEqual(origenes[self.origen.pk]["saldo_l"], "20000.00")
        self.assertIsNone(origenes[self.origen.pk]["motivo"])
        self.assertIsNone(origenes[sin_analisis.pk]["analisis"])
        self.assertIn("no tiene un análisis confirmado", origenes[sin_analisis.pk]["motivo"])
        self.assertNotIn(vacio.pk, origenes)

    def test_corridas_de_hoy_sin_huerfanos(self):
        en_curso = self.en_curso()
        huerfana = self.preparada(
            equipo=self.otra_descremadora.pk, silo_descremada=self.otro_tk_descremada.pk,
            estanque_crema=self.otro_tk_crema.pk,
        )
        EjecucionProceso.objects.filter(pk=huerfana.ejecucion_id).update(
            estado=EjecucionProceso.Estado.CANCELADA,
        )

        datos = self.puesto()

        propias = [c for c in datos["corridas_de_hoy"] if c["id"] in {en_curso.pk, huerfana.pk}]
        self.assertEqual(
            [(c["id"], c["estado"], c["estado_ejecucion"]) for c in propias],
            [(en_curso.pk, "en_curso", "ejecucion")],
        )
        self.assertEqual(self.fila(datos, self.otra_descremadora)["estado"], "disponible")

    def test_calidad_lee_el_puesto(self):
        datos = self.puesto(self.calidad)

        self.assertIn("descremadoras", datos)
        self.assertIn("borrador", [estado["valor"] for estado in datos["estados"]])

    def test_el_historial_filtra_en_el_servidor(self):
        primera = self.en_curso()
        segunda = self.preparada(
            equipo=self.otra_descremadora.pk, silo_descremada=self.otro_tk_descremada.pk,
            estanque_crema=self.otro_tk_crema.pk,
        )

        por_tk = self.cliente().get(
            "/api/procesos/descremaciones/", {"q": self.otro_tk_descremada.codigo},
        )
        por_estado = self.cliente().get("/api/procesos/descremaciones/", {"estado": "en_curso"})

        self.assertEqual(self.ids(por_tk.data["results"], primera, segunda), [segunda.pk])
        self.assertEqual(self.ids(por_estado.data["results"], primera, segunda), [primera.pk])
        fila = next(c for c in por_estado.data["results"] if c["id"] == primera.pk)
        self.assertEqual(fila["ejecucion_estado"], "ejecucion")
```

Run: `cd backend && DJANGO_ENV=test ./.venv/Scripts/python.exe manage.py test procesos.tests_puesto_descremado --noinput`
Expected: FAIL — `descremaciones/puesto/` responde 404 (lo toma como `pk`); `q` no filtra; falta `ejecucion_estado`.

- [ ] **Step 2: Servicio** — en `procesos/servicios.py`, después de `iniciar_descremacion`:

```python
def estado_puesto_descremado(usuario):
    """
    Lo que el puesto de Descremado dibuja: un estado por descremadora,
    derivado de su ejecución de Descremación que ocupa el equipo (una en curso
    manda sobre una preparada), con los motivos que impiden iniciar
    calculados por la misma función que decide al iniciar; los silos de origen
    con el análisis que usará «Preparar»; los TK que la regla de destino
    acepta; y las corridas de hoy. La pantalla no recalcula nada de esto.

    Una ejecución `cerrada`/`cancelada` no ocupa la máquina aunque su corrida
    haya quedado en `borrador`/`en_curso` (`ESTADOS_QUE_OCUPAN_EQUIPO`).
    `en_calidad` es informativa: esa ejecución ya no ocupa la descremadora,
    pero sus TK siguen bloqueados hasta que Calidad decida.
    """
    from inventario.servicios import advertencia_aseo_equipo, motivo_equipo_no_habilitado
    from maestros.models import Equipo, Silo
    from recepcion.servicios import ultimo_analisis_confirmado
    from usuarios.tenancy import filtrar_por_scope

    def texto(valor):
        # Texto, como en los serializers: el tipo del frontend es `string`.
        return None if valor is None else str(valor)

    descremadoras = list(filtrar_por_scope(
        Equipo.objects.filter(activo=True, tipo=Equipo.Tipo.DESCREMADORA)
        .select_related("sucursal").order_by("codigo"),
        usuario, campo_sucursal="sucursal_id", campo_empresa="sucursal__empresa_id",
    ))
    ids = [equipo.pk for equipo in descremadoras]

    activas = {}
    for ejecucion in (
        EjecucionProceso.objects.filter(
            etapa__tipo=EtapaProceso.Tipo.DESCREMACION, equipo_id__in=ids,
            estado__in=ESTADOS_QUE_OCUPAN_EQUIPO,
        )
        .select_related(
            "etapa", "equipo", "corrida_descremacion__analisis_entrada",
            "corrida_descremacion__silo_entera", "corrida_descremacion__silo_descremada",
            "corrida_descremacion__estanque_crema", "corrida_descremacion__producto_descremada",
            "corrida_descremacion__producto_crema",
        )
        .order_by("pk")
    ):
        actual = activas.get(ejecucion.equipo_id)
        if actual is None or (
            actual.estado == EjecucionProceso.Estado.PREPARACION
            and ejecucion.estado != EjecucionProceso.Estado.PREPARACION
        ):
            activas[ejecucion.equipo_id] = ejecucion

    en_calidad = {}
    for corrida in (
        CorridaDescremacion.objects.filter(
            ejecucion__equipo_id__in=ids,
            ejecucion__estado=EjecucionProceso.Estado.PENDIENTE_CONTROL,
        ).select_related("ejecucion", "silo_descremada", "estanque_crema").order_by("pk")
    ):
        en_calidad[corrida.ejecucion.equipo_id] = corrida

    def resumen(ejecucion):
        corrida = getattr(ejecucion, "corrida_descremacion", None)
        base = {
            "id": None, "ejecucion_id": ejecucion.pk, "ejecucion_codigo": ejecucion.codigo,
            "ejecucion_estado": ejecucion.estado, "estado": None,
            "silo_entera": None, "litros_entrada": None, "grasa_entrada": None,
            "sng_entrada": None, "silo_descremada": None, "litros_descremada_plan": None,
            "estanque_crema": None, "litros_crema_plan": None, "destino_crema": None,
            "iniciada_en": ejecucion.inicio,
        }
        if corrida is None:
            return base
        return {
            **base,
            "id": corrida.pk, "estado": corrida.estado,
            "silo_entera": corrida.silo_entera.codigo,
            "litros_entrada": texto(corrida.litros_entrada),
            "grasa_entrada": texto(corrida.grasa_entrada),
            "sng_entrada": texto(corrida.sng_entrada),
            "silo_descremada": corrida.silo_descremada.codigo,
            "litros_descremada_plan": texto(corrida.litros_descremada_plan),
            "estanque_crema": corrida.estanque_crema.codigo,
            "litros_crema_plan": texto(corrida.litros_crema_plan),
            "destino_crema": corrida.destino_crema,
            "iniciada_en": corrida.iniciada_en,
        }

    filas = []
    for maquina in descremadoras:
        ejecucion = activas.get(maquina.pk)
        motivos_tomar, motivos_iniciar, resolver_en = [], [], None
        if ejecucion is None:
            estado = "disponible"
            # La misma regla con que «Preparar» rechaza la descremadora.
            impedimento = motivo_equipo_no_habilitado(maquina)
            if impedimento:
                motivos_tomar, resolver_en = [impedimento], RESOLVER_CIP
        elif ejecucion.estado == EjecucionProceso.Estado.PREPARACION:
            estado = "preparada"
            corrida = getattr(ejecucion, "corrida_descremacion", None)
            if corrida is None:
                # Dato heredado del alta genérica, ya cerrada: sin corrida no
                # hay `cancelar-preparacion/`.
                motivos_iniciar = [
                    f"{ejecucion.codigo} no tiene corrida de descremado y no puede "
                    "iniciarse: cancela esa ejecución en Procesos y vuelve a preparar."
                ]
            else:
                tipados = motivos_tipados_para_iniciar_descremacion(corrida, ejecucion=ejecucion)
                motivos_iniciar = [motivo for motivo, _ in tipados]
                # El enlace es del primer motivo, que es el que la tarjeta muestra.
                resolver_en = tipados[0][1] if tipados else None
        else:
            estado = "en_curso"
        aseo = None if estado == "en_curso" else advertencia_aseo_equipo(maquina)
        pendiente = en_calidad.get(maquina.pk)
        filas.append({
            "equipo_id": maquina.pk, "codigo": maquina.codigo, "nombre": maquina.nombre,
            "estado": estado,
            "corrida": resumen(ejecucion) if ejecucion is not None else None,
            "motivos_para_tomar": motivos_tomar,
            "motivos_para_iniciar": motivos_iniciar,
            "resolver_en": resolver_en,
            "avisos": [aseo] if aseo else [],
            "en_calidad": (
                {
                    "id": pendiente.pk, "ejecucion_codigo": pendiente.ejecucion.codigo,
                    "tanques": [
                        silo.codigo for silo in (pendiente.silo_descremada, pendiente.estanque_crema)
                        if silo.estado == Silo.Estado.BLOQUEADO_CALIDAD
                    ],
                }
                if pendiente is not None else None
            ),
        })

    origenes = []
    for silo in filtrar_por_scope(
        silos_con_saldo(Silo.objects.filter(activo=True, tipo=Silo.Tipo.SILO))
        .filter(saldo_l__gt=0).order_by("codigo"),
        usuario, campo_sucursal="sucursal_id", campo_empresa="sucursal__empresa_id",
    ):
        analisis = ultimo_analisis_confirmado(silo)
        # La misma regla con que `crear_descremacion_guiada` rechaza el
        # origen. Con motivo, el silo se ofrece deshabilitado con el texto:
        # es la entrada que viene desde «Descremar» del silo.
        motivos = motivos_para_preparar_desde_silo(silo, analisis)
        origenes.append({
            "id": silo.pk, "codigo": silo.codigo, "saldo_l": texto(silo.saldo_l),
            "analisis": (
                {
                    "id": analisis.pk, "grasa": texto(analisis.grasa),
                    "sng": texto(analisis.sng), "tomado_en": analisis.tomado_en,
                }
                if analisis is not None and not motivos else None
            ),
            "motivo": motivos[0] if motivos else None,
        })

    def destinos(tipo):
        # Estado y reservas con la regla de destino; capacidad y mezcla
        # dependen del plan y las vuelve a comprobar «Preparar».
        return [
            {"id": silo.pk, "codigo": silo.codigo, "libre_l": texto(silo.capacidad_l - silo.saldo_l)}
            for silo in filtrar_por_scope(
                silos_con_saldo(Silo.objects.filter(tipo=tipo)).order_by("codigo"),
                usuario, campo_sucursal="sucursal_id", campo_empresa="sucursal__empresa_id",
            )
            if not motivos_destino_descremacion(silo)
        ]

    hoy = timezone.localdate()
    corridas_de_hoy = [
        {
            "id": corrida.pk, "ejecucion_codigo": corrida.ejecucion.codigo,
            "equipo": corrida.ejecucion.equipo.codigo if corrida.ejecucion.equipo_id else None,
            "silo_entera": corrida.silo_entera.codigo,
            "estado": corrida.estado, "estado_etiqueta": corrida.get_estado_display(),
            "estado_ejecucion": corrida.ejecucion.estado,
        }
        for corrida in CorridaDescremacion.objects.filter(ejecucion__equipo_id__in=ids)
        .filter(
            Q(ejecucion__creada_en__date=hoy) | Q(iniciada_en__date=hoy)
            | Q(finalizada_en__date=hoy)
        )
        # Un huérfano cuya ejecución terminó sin iniciarse no es trabajo del día.
        .exclude(iniciada_en__isnull=True, ejecucion__estado__in=ESTADOS_EJECUCION_TERMINALES)
        .select_related("ejecucion__equipo", "silo_entera")
        .order_by("-pk")
    ]
    return {
        "descremadoras": filas,
        "origenes": origenes,
        "destinos_descremada": destinos(Silo.Tipo.TK_LD),
        "destinos_crema": destinos(Silo.Tipo.TK_CREMA),
        "corridas_de_hoy": corridas_de_hoy,
        "estados": [
            {"valor": valor, "etiqueta": etiqueta}
            for valor, etiqueta in CorridaDescremacion.Estado.choices
        ],
    }
```

- [ ] **Step 3: Serializer** — en `CorridaDescremacionSerializer`, junto a `ejecucion_codigo`:

```python
    # El historial distingue «Preparada» de «Esperando Calidad» con el estado
    # de la ejecución, no solo con el de la corrida.
    ejecucion_estado = serializers.CharField(source="ejecucion.estado", read_only=True)
```

- [ ] **Step 4: Vista y filtros** — en `views.py` importa `estado_puesto_descremado` y cambia la cabecera de `CorridaDescremacionViewSet`:

```python
class CorridaDescremacionViewSet(FiltraConsultaMixin, QuerysetTenantMixin, viewsets.ModelViewSet):
    tenant_lookup_sucursal = "ejecucion__sucursal_id"
    tenant_lookup_empresa = "ejecucion__sucursal__empresa_id"
    queryset = CorridaDescremacion.objects.select_related(
        "ejecucion__etapa", "ejecucion__equipo", "orden", "analisis_entrada",
        "producto_descremada", "producto_crema",
        "silo_entera", "silo_descremada", "estanque_crema",
        "iniciada_por", "finalizada_por",
    ).order_by("-pk")
    serializer_class = CorridaDescremacionSerializer
    permission_classes = [OperaProcesoPorEtapa]
    tipo_etapa_operacional = EtapaProceso.Tipo.DESCREMACION
    http_method_names = ["get", "post", "head", "options"]
    # Historial del puesto: se filtra en el servidor porque la lista está
    # paginada (mismo contrato que Secado, Existencias y Despacho).
    busqueda_en = (
        "ejecucion__codigo", "silo_entera__codigo",
        "silo_descremada__codigo", "estanque_crema__codigo",
    )
    filtro_estado = "estado"
    filtro_fecha = "ejecucion__creada_en"
```

y la acción, antes de `opciones_alta`:

```python
    @action(detail=False, methods=["get"])
    def puesto(self, request):
        """Estado del puesto de Descremado: lo que la pantalla dibuja, sin recalcular."""
        return Response(estado_puesto_descremado(request.user))
```

- [ ] **Step 5: Verificar**

Run: `cd backend && DJANGO_ENV=test ./.venv/Scripts/python.exe manage.py test procesos.tests_puesto_descremado procesos.tests_descremacion --noinput`
Expected: OK (`tests_descremacion.test_calidad_decide_…` sigue leyendo `listado.data["results"][0]`: el orden `-pk` deja primero la corrida de la fixture, la única de esa prueba).

- [ ] **Step 6: Suite de procesos**

Run: `cd backend && DJANGO_ENV=test ./.venv/Scripts/python.exe manage.py test procesos inventario --noinput`
Expected: OK (`inventario.views.FiltraConsultaMixin` ya lo importa `procesos.views` para Secado: sin ciclo nuevo).

- [ ] **Step 7: Ajustar la spec** — en `docs/superpowers/specs/2026-10-07-puesto-descremado-design.md`, agrega al final de §8:

```markdown
13. **Ajustes del plan** (`docs/superpowers/plans/2026-10-07-puesto-descremado.md`,
    «Desviaciones»): `motivos_origen_descremacion`/`motivos_destino_descremacion` se
    extrajeron de `iniciar_descremacion` (no existían), junto con
    `motivos_para_preparar_desde_silo` y `recepcion.servicios.ultimo_analisis_confirmado`;
    `EJ-DES-{pk}` usa el id de la corrida; `POST ejecuciones/` también se cerró (405),
    porque creaba ejecuciones de Descremación sin corrida; «Descremar» del silo dejó de
    deshabilitarse por los motivos de inicio y siempre lleva al puesto; el motivo
    «análisis superado» viaja con `resolver_en = null` (se arregla cancelando y volviendo
    a preparar, no analizando); cancelar por la bandeja genérica anula también una corrida
    en curso; `corrida.estado`, `estados` y `ejecucion_estado` son claves extra.
```

y en §3.3, en el punto «el análisis con que se preparó sigue siendo el vigente…», cambia `→ RESOLVER_SILOS (nuevo, ver §8)` por `→ sin enlace: se resuelve cancelando y volviendo a preparar (§8.13)`.

- [ ] **Step 8: Commit**

```bash
git add backend/procesos/servicios.py backend/procesos/serializers.py backend/procesos/views.py backend/procesos/tests_puesto_descremado.py docs/superpowers/specs/2026-10-07-puesto-descremado-design.md
git commit -m "feat(procesos): estado del puesto de Descremado y su historial filtrado en el servidor"
```

---

### Task 5: Servicios del frontend y reglas puras

**Files:**
- Create: `frontend/src/services/descremado.service.ts`, `frontend/src/services/puesto-descremado.ts`, `frontend/src/services/permisos-descremado.ts`
- Create: `frontend/tests/puesto-descremado.test.ts`, `frontend/tests/permisos-descremado.test.ts`
- Modify: `frontend/src/services/puesto-secado.ts` (`MODULO_POR_RUTA`), `frontend/tests/puesto-secado.test.ts`
- Modify: `frontend/src/services/planta-ahora.ts` (`textoIniciarEnPuesto`), `frontend/tests/planta-ahora.test.ts`
- Modify: `frontend/src/services/procesos.service.ts` (`CorridaDescremacion.ejecucion_estado`)

**Interfaces:**
- Consumes: endpoints de las Tasks 1-4.
- Produces (`descremado.service.ts`):
  - `export type EstadoDescremadora = "disponible" | "preparada" | "en_curso";`
  - `export interface CorridaDescremadora { id: number | null; ejecucion_id: number; ejecucion_codigo: string; ejecucion_estado: string; estado: string | null; silo_entera: string | null; litros_entrada: string | null; grasa_entrada: string | null; sng_entrada: string | null; silo_descremada: string | null; litros_descremada_plan: string | null; estanque_crema: string | null; litros_crema_plan: string | null; destino_crema: string | null; iniciada_en: string | null }`
  - `export interface DescremadoraPuesto { equipo_id: number; codigo: string; nombre: string; estado: EstadoDescremadora; corrida: CorridaDescremadora | null; motivos_para_tomar: string[]; motivos_para_iniciar: string[]; resolver_en: string | null; avisos: string[]; en_calidad: { id: number; ejecucion_codigo: string; tanques: string[] } | null }`
  - `export interface OrigenDescremado { id: number; codigo: string; saldo_l: string; analisis: { id: number; grasa: string; sng: string; tomado_en: string } | null; motivo: string | null }`
  - `export interface DestinoDescremado { id: number; codigo: string; libre_l: string }`
  - `export interface CorridaDeHoyDescremado { id: number; ejecucion_codigo: string; equipo: string | null; silo_entera: string; estado: string; estado_etiqueta: string; estado_ejecucion: string }`
  - `export interface PuestoDescremado { descremadoras: DescremadoraPuesto[]; origenes: OrigenDescremado[]; destinos_descremada: DestinoDescremado[]; destinos_crema: DestinoDescremado[]; corridas_de_hoy: CorridaDeHoyDescremado[]; estados: { valor: string; etiqueta: string }[] }`
  - `export type DestinoRamaCrema = "siguiente_proceso" | "estandarizacion" | "despacho_directo";`
  - `export interface PreparacionDescremado { etapa: number; equipo: number; silo_entera: number; litros_entrada: number; silo_descremada: number; estanque_crema: number; producto_descremada: number; producto_crema: number; litros_descremada_plan: number; litros_crema_plan: number; plan_confirmado: true; ruta_descremada: number; ruta_crema: number; destino_descremada: "estandarizacion"; destino_crema: DestinoRamaCrema }`
  - `export interface ValoresCierreDescremado { litros_descremada: number | null; grasa_descremada: number | null; litros_crema: number | null; grasa_crema: number | null }`
  - `export interface RevisionCierreDescremado { avisos_limites: { codigo: string; mensaje: string }[]; avisos_balance: string[]; merma_l: string | null; desvio_grasa_kg: string | null }`
  - `export interface CancelacionPreparacionDescremado { ejecucion_id: number; ejecucion_codigo: string; estado: string }`
  - `obtenerPuestoDescremado(): Promise<PuestoDescremado>`; `obtenerDescremacion(id): Promise<CorridaDescremacion>`; `prepararDescremado(datos: PreparacionDescremado): Promise<CorridaDescremacion>`; `iniciarDescremado(id): Promise<CorridaDescremacion>`; `cancelarPreparacionDescremado(id, motivo): Promise<CancelacionPreparacionDescremado>`; `revisarCierreDescremado(id, valores: ValoresCierreDescremado): Promise<RevisionCierreDescremado>`; `buscarDescremaciones(filtros?: Filtros): Promise<Pagina<CorridaDescremacion>>`.
- Produces (`puesto-descremado.ts`): `accionDeDescremadora(fila: DescremadoraPuesto): { tipo: "preparar" | "iniciar" | "cerrar" | "ninguna"; habilitada: boolean; motivo: string | null }`; `corridaCancelable(corrida: { id: number | null; estado: string | null; ejecucion_estado: string } | null | undefined): number | null`; `situacionDeCorrida(estado: string, estadoEjecucion: string, etiqueta?: string): string`; reexporta `moduloDeResolver`.
- Produces (`permisos-descremado.ts`): `puedeOperarDescremado(usuario): boolean`.
- Produces (`planta-ahora.ts`): `textoIniciarEnPuesto(etapaTipo: string, estado: string): string | null`.

- [ ] **Step 1: Pruebas que fallan** — `frontend/tests/puesto-descremado.test.ts`:

```ts
import assert from "node:assert/strict";
import test from "node:test";

import {
  accionDeDescremadora, corridaCancelable, moduloDeResolver, situacionDeCorrida,
} from "../src/services/puesto-descremado.ts";

const base = {
  equipo_id: 1, codigo: "des-01", nombre: "Descremadora 1", corrida: null,
  motivos_para_tomar: [] as string[], motivos_para_iniciar: [] as string[],
  resolver_en: null, avisos: [] as string[], en_calidad: null,
};
const corrida = {
  id: 8, ejecucion_id: 120, ejecucion_codigo: "EJ-DES-8", ejecucion_estado: "preparacion",
  estado: "borrador", silo_entera: "Silo 3", litros_entrada: "1000.00",
  grasa_entrada: "2.610", sng_entrada: "8.700", silo_descremada: "Tk02",
  litros_descremada_plan: "976.40", estanque_crema: "TkC2", litros_crema_plan: "23.60",
  destino_crema: "siguiente_proceso", iniciada_en: null,
};

test("una descremadora disponible ofrece preparar", () => {
  assert.deepEqual(accionDeDescremadora({ ...base, estado: "disponible" }), { tipo: "preparar", habilitada: true, motivo: null });
});

test("una descremadora en CIP no se prepara y dice por qué", () => {
  const fila = { ...base, estado: "disponible" as const, motivos_para_tomar: ["Descremadora 1 está en CIP."] };
  assert.deepEqual(accionDeDescremadora(fila), { tipo: "preparar", habilitada: false, motivo: "Descremadora 1 está en CIP." });
});

test("una preparada sin motivos se puede iniciar", () => {
  assert.deepEqual(accionDeDescremadora({ ...base, estado: "preparada", corrida }), { tipo: "iniciar", habilitada: true, motivo: null });
});

test("una preparada con motivos muestra el primero y no habilita iniciar", () => {
  const fila = { ...base, estado: "preparada" as const, corrida, motivos_para_iniciar: ["Silo 3: falta la segunda firma.", "otro"] };
  assert.deepEqual(accionDeDescremadora(fila), { tipo: "iniciar", habilitada: false, motivo: "Silo 3: falta la segunda firma." });
});

test("los avisos no deshabilitan iniciar", () => {
  const fila = { ...base, estado: "preparada" as const, corrida, avisos: ["Último aseo con observación."] };
  assert.equal(accionDeDescremadora(fila).habilitada, true);
});

test("una preparación sin corrida no se puede iniciar", () => {
  const fila = { ...base, estado: "preparada" as const, corrida: { ...corrida, id: null } };
  assert.equal(accionDeDescremadora(fila).habilitada, false);
});

test("en curso ofrece cerrar solo en ejecución, espejo de cerrar_descremacion", () => {
  const enCurso = { ...base, estado: "en_curso" as const, corrida: { ...corrida, estado: "en_curso", ejecucion_estado: "ejecucion" } };
  assert.deepEqual(accionDeDescremadora(enCurso), { tipo: "cerrar", habilitada: true, motivo: null });
  for (const ejecucion_estado of ["pausada", "bloqueada"]) {
    const fila = { ...enCurso, corrida: { ...enCurso.corrida, ejecucion_estado } };
    assert.equal(accionDeDescremadora(fila).habilitada, false);
    assert.match(accionDeDescremadora(fila).motivo ?? "", new RegExp(ejecucion_estado));
  }
});

test("se cancela una corrida en borrador con la ejecución preparada o heredada en borrador", () => {
  assert.equal(corridaCancelable(corrida), 8);
  assert.equal(corridaCancelable({ ...corrida, ejecucion_estado: "borrador" }), 8);
  assert.equal(corridaCancelable({ ...corrida, estado: "en_curso", ejecucion_estado: "ejecucion" }), null);
  assert.equal(corridaCancelable({ ...corrida, ejecucion_estado: "cancelada" }), null);
  assert.equal(corridaCancelable({ ...corrida, id: null }), null);
  assert.equal(corridaCancelable(null), null);
});

test("la situación de una corrida para la lista y el historial", () => {
  assert.equal(situacionDeCorrida("borrador", "preparacion"), "Preparada");
  assert.equal(situacionDeCorrida("en_curso", "ejecucion"), "En la descremadora");
  assert.equal(situacionDeCorrida("cerrada", "pendiente_control"), "Esperando Calidad");
  assert.equal(situacionDeCorrida("cerrada", "cerrada"), "Terminada");
  assert.equal(situacionDeCorrida("anulada", "cancelada"), "Anulada");
  assert.equal(situacionDeCorrida("borrador", "cancelada", "Borrador"), "Borrador");
});

test("los motivos del silo se resuelven en Silos, módulo de Recepción", () => {
  assert.equal(moduloDeResolver("/silos"), "recepcion");
  assert.equal(moduloDeResolver("/calidad/inocuidad"), "inocuidad");
});
```

`frontend/tests/permisos-descremado.test.ts`:

```ts
import assert from "node:assert/strict";
import test from "node:test";

import { puedeOperarDescremado } from "../src/services/permisos-descremado.ts";

const conArea = (area: string, rol = "produccion") => ({ rol, perfil: { area } });

test("Condensación opera el puesto de Descremado", () => {
  assert.equal(puedeOperarDescremado(conArea("condensacion")), true);
});

test("Secado no opera la descremadora, como en el servidor", () => {
  assert.equal(puedeOperarDescremado(conArea("secado")), false);
});

test("Calidad consulta pero no opera", () => {
  assert.equal(puedeOperarDescremado(conArea("calidad", "calidad")), false);
});

test("Administración y el administrador operan", () => {
  assert.equal(puedeOperarDescremado(conArea("administracion")), true);
  assert.equal(puedeOperarDescremado({ rol: "admin", perfil: null }), true);
});

test("sin sesión o sin área no se opera", () => {
  assert.equal(puedeOperarDescremado(null), false);
  assert.equal(puedeOperarDescremado({ rol: "produccion", perfil: null }), false);
});
```

En `frontend/tests/planta-ahora.test.ts` importa `textoIniciarEnPuesto` y agrega:

```ts
test("Secado y Descremado se inician en su puesto, espejo de MENSAJES_INICIO_EN_PUESTO", () => {
  assert.equal(textoIniciarEnPuesto("secado", "preparacion"), "Iniciar en el puesto de Secado");
  assert.equal(textoIniciarEnPuesto("descremacion", "preparacion"), "Iniciar en el puesto de Descremado");
  // Reanudar no es iniciar, y las demás etapas siguen en la bandeja.
  assert.equal(textoIniciarEnPuesto("descremacion", "pausada"), null);
  assert.equal(textoIniciarEnPuesto("mantequilla", "preparacion"), null);
});
```

En `frontend/tests/puesto-secado.test.ts`, junto a las aserciones de `moduloDeResolver`: `assert.equal(moduloDeResolver("/silos"), "recepcion");`.

Run: `cd frontend && npm test`
Expected: FAIL (módulos inexistentes).

- [ ] **Step 2: Servicio** — `frontend/src/services/descremado.service.ts`:

```ts
import api from "./api";
import { conFiltros, type Filtros } from "./paginacion";
import type { CorridaDescremacion, Pagina } from "./procesos.service";

export type EstadoDescremadora = "disponible" | "preparada" | "en_curso";

export interface CorridaDescremadora {
  /* `null` en una ejecución heredada sin corrida (alta genérica ya cerrada). */
  id: number | null;
  ejecucion_id: number;
  ejecucion_codigo: string;
  ejecucion_estado: string;
  estado: string | null;
  silo_entera: string | null;
  litros_entrada: string | null;
  grasa_entrada: string | null;
  sng_entrada: string | null;
  silo_descremada: string | null;
  litros_descremada_plan: string | null;
  estanque_crema: string | null;
  litros_crema_plan: string | null;
  destino_crema: string | null;
  iniciada_en: string | null;
}

export interface DescremadoraPuesto {
  equipo_id: number;
  codigo: string;
  nombre: string;
  estado: EstadoDescremadora;
  corrida: CorridaDescremadora | null;
  /* Por qué no se puede preparar una disponible (CIP). */
  motivos_para_tomar: string[];
  motivos_para_iniciar: string[];
  /* Dónde se resuelve el primer motivo; `null` si no hay pantalla que lo arregle. */
  resolver_en: string | null;
  avisos: string[];
  en_calidad: { id: number; ejecucion_codigo: string; tanques: string[] } | null;
}

export interface OrigenDescremado {
  id: number;
  codigo: string;
  saldo_l: string;
  /* El análisis que usará «Preparar»: no se elige en la pantalla. */
  analisis: { id: number; grasa: string; sng: string; tomado_en: string } | null;
  motivo: string | null;
}

export interface DestinoDescremado {
  id: number;
  codigo: string;
  libre_l: string;
}

export interface CorridaDeHoyDescremado {
  id: number;
  ejecucion_codigo: string;
  equipo: string | null;
  silo_entera: string;
  estado: string;
  estado_etiqueta: string;
  estado_ejecucion: string;
}

export interface PuestoDescremado {
  descremadoras: DescremadoraPuesto[];
  origenes: OrigenDescremado[];
  destinos_descremada: DestinoDescremado[];
  destinos_crema: DestinoDescremado[];
  corridas_de_hoy: CorridaDeHoyDescremado[];
  estados: { valor: string; etiqueta: string }[];
}

export type DestinoRamaCrema = "siguiente_proceso" | "estandarizacion" | "despacho_directo";

/* Sin código ni análisis: los pone el servidor. */
export interface PreparacionDescremado {
  etapa: number;
  equipo: number;
  silo_entera: number;
  litros_entrada: number;
  silo_descremada: number;
  estanque_crema: number;
  producto_descremada: number;
  producto_crema: number;
  litros_descremada_plan: number;
  litros_crema_plan: number;
  plan_confirmado: true;
  ruta_descremada: number;
  ruta_crema: number;
  destino_descremada: "estandarizacion";
  destino_crema: DestinoRamaCrema;
}

export interface ValoresCierreDescremado {
  litros_descremada: number | null;
  grasa_descremada: number | null;
  litros_crema: number | null;
  grasa_crema: number | null;
}

export interface RevisionCierreDescremado {
  avisos_limites: { codigo: string; mensaje: string }[];
  avisos_balance: string[];
  merma_l: string | null;
  desvio_grasa_kg: string | null;
}

export interface CancelacionPreparacionDescremado {
  ejecucion_id: number;
  ejecucion_codigo: string;
  estado: string;
}

export async function obtenerPuestoDescremado(): Promise<PuestoDescremado> {
  const { data } = await api.get<PuestoDescremado>("procesos/descremaciones/puesto/");
  return data;
}

export async function obtenerDescremacion(id: number): Promise<CorridaDescremacion> {
  const { data } = await api.get<CorridaDescremacion>(`procesos/descremaciones/${id}/`);
  return data;
}

/* Prepara: corrida, reservas de silo y descremadora tomada. No inicia. */
export async function prepararDescremado(datos: PreparacionDescremado): Promise<CorridaDescremacion> {
  const { data } = await api.post<CorridaDescremacion>("procesos/descremaciones/crear-guiada/", datos);
  return data;
}

export async function iniciarDescremado(id: number): Promise<CorridaDescremacion> {
  const { data } = await api.post<CorridaDescremacion>(`procesos/descremaciones/${id}/iniciar/`);
  return data;
}

/* Suelta la descremadora y las reservas; la corrida queda anulada. */
export async function cancelarPreparacionDescremado(
  id: number, motivo: string,
): Promise<CancelacionPreparacionDescremado> {
  const { data } = await api.post<CancelacionPreparacionDescremado>(
    `procesos/descremaciones/${id}/cancelar-preparacion/`, { motivo },
  );
  return data;
}

/* Avisos del cierre con lo tecleado hasta ahora; el servidor no escribe nada. */
export async function revisarCierreDescremado(
  id: number, valores: ValoresCierreDescremado,
): Promise<RevisionCierreDescremado> {
  const { data } = await api.post<RevisionCierreDescremado>(
    `procesos/descremaciones/${id}/revisar-cierre/`, valores,
  );
  return data;
}

/* Historial del puesto: filtros y página viajan al servidor. */
export async function buscarDescremaciones(filtros: Filtros = {}): Promise<Pagina<CorridaDescremacion>> {
  const { data } = await api.get<Pagina<CorridaDescremacion>>(conFiltros("procesos/descremaciones/", filtros));
  return data;
}
```

En `procesos.service.ts`, en `interface CorridaDescremacion`, debajo de `ejecucion_codigo: string;` agrega `ejecucion_estado: string;`.

- [ ] **Step 3: Reglas puras** — `frontend/src/services/puesto-descremado.ts`:

```ts
import type { DescremadoraPuesto } from "./descremado.service.ts";

/* Un solo mapa de «dónde se resuelve» para los puestos (Desviación 17). */
export { moduloDeResolver } from "./puesto-secado.ts";

export interface AccionDescremadora {
  tipo: "preparar" | "iniciar" | "cerrar" | "ninguna";
  habilitada: boolean;
  motivo: string | null;
}

/*
  Qué botón lleva la tarjeta de una descremadora. Solo traduce lo que mandó
  el servidor: estado y motivos los calcula `estado_puesto_descremado` con
  las mismas reglas que deciden al preparar (`motivo_equipo_no_habilitado`) y
  al iniciar (`motivos_tipados_para_iniciar_descremacion`). Los avisos no
  entran aquí a propósito: avisan, no deshabilitan.

  La única regla propia es espejo de `cerrar_descremacion`: la ejecución
  pasa a `pendiente_control`, y eso solo se permite desde `ejecucion`.
  Ofrecer las salidas sobre una pausada o bloqueada es ofrecer algo que el
  servidor rechaza.
*/
export function accionDeDescremadora(fila: DescremadoraPuesto): AccionDescremadora {
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
        return { tipo: "cerrar", habilitada: false, motivo: "La corrida está pausada: reanúdala antes de registrar las salidas." };
      }
      if (estado === "bloqueada") {
        return { tipo: "cerrar", habilitada: false, motivo: "La corrida está bloqueada: resuelve el bloqueo antes de registrar las salidas." };
      }
      return { tipo: "cerrar", habilitada: fila.corrida?.id != null, motivo: null };
    }
    default:
      return { tipo: "ninguna", habilitada: false, motivo: null };
  }
}

/*
  La corrida que «Cancelar preparación» soltaría, o `null`. Espejo de
  `cancelar_preparacion_descremacion`: corrida en `borrador` con la ejecución
  en `preparacion` —o en `borrador`, las heredadas del modal anterior, que
  solo aparecen en el historial—. Los motivos que impiden iniciar no impiden
  cancelar: suelen ser justo la razón.
*/
export function corridaCancelable(
  corrida: { id: number | null; estado: string | null; ejecucion_estado: string } | null | undefined,
): number | null {
  if (!corrida || corrida.id === null || corrida.estado !== "borrador") return null;
  return ["borrador", "preparacion"].includes(corrida.ejecucion_estado) ? corrida.id : null;
}

/* Cómo se nombra una corrida en «Corridas de hoy» y en el historial. Un
   estado que no se distingue lleva la etiqueta del servidor. */
export function situacionDeCorrida(estado: string, estadoEjecucion: string, etiqueta?: string): string {
  switch (estado) {
    case "borrador":
      return ["borrador", "preparacion"].includes(estadoEjecucion) ? "Preparada" : etiqueta ?? estado;
    case "en_curso":
      return "En la descremadora";
    case "cerrada":
      return estadoEjecucion === "pendiente_control" ? "Esperando Calidad" : "Terminada";
    case "anulada":
      return "Anulada";
    default:
      return etiqueta ?? estado;
  }
}
```

`frontend/src/services/permisos-descremado.ts`:

```ts
import type { Usuario } from "./sesion.ts";

/*
  Quién opera el puesto de Descremado. Refleja `procesos.permisos`
  (`TIPOS_OPERABLES_POR_AREA`): la etapa Descremación la opera Condensación y
  el administrador —rol efectivo `admin`, que el servidor también da al área
  Administración—. Calidad ve el puesto en modo consulta; Secado escribe
  lotes pero no opera la descremadora.

  Cortesía para no ofrecer botones que el servidor rechaza con 403; el
  permiso se aplica allá.
*/
type ConPerfil = (Pick<Usuario, "rol"> & { perfil: Pick<NonNullable<Usuario["perfil"]>, "area"> | null }) | null | undefined;

export function puedeOperarDescremado(usuario: ConPerfil): boolean {
  if (!usuario) return false;
  const area = usuario.perfil?.area;
  return usuario.rol === "admin" || area === "administracion" || area === "condensacion";
}
```

- [ ] **Step 4: Dónde se resuelve y quién inicia en su puesto** — en `frontend/src/services/puesto-secado.ts`, agrega a `MODULO_POR_RUTA` la entrada `"/silos": "recepcion",` y en el comentario encima «`RESOLVER_SILOS`» junto a `RESOLVER_CIP` y `RESOLVER_CALIDAD`.

En `frontend/src/services/planta-ahora.ts`, debajo de `rutaDeEtapa`:

```ts
/*
  Etapas cuyo inicio es de su puesto: espejo de `MENSAJES_INICIO_EN_PUESTO`
  (`backend/procesos/servicios.py`). La bandeja genérica no ofrece iniciarlas
  (`acciones_permitidas`) y enlaza al puesto con este texto. Reanudar una
  pausada sigue en la bandeja: no es iniciar.
*/
const PUESTOS_QUE_INICIAN: Record<string, string> = {
  secado: "Secado",
  descremacion: "Descremado",
};

export function textoIniciarEnPuesto(etapaTipo: string, estado: string): string | null {
  const puesto = PUESTOS_QUE_INICIAN[etapaTipo];
  return puesto && estado === "preparacion" ? `Iniciar en el puesto de ${puesto}` : null;
}
```

- [ ] **Step 5: Verificar**

Run: `cd frontend && npm test && npx tsc -b --pretty false && npx eslint src/services tests`
Expected: PASS / sin errores.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/services/descremado.service.ts frontend/src/services/puesto-descremado.ts frontend/src/services/permisos-descremado.ts frontend/src/services/puesto-secado.ts frontend/src/services/planta-ahora.ts frontend/src/services/procesos.service.ts frontend/tests/puesto-descremado.test.ts frontend/tests/permisos-descremado.test.ts frontend/tests/puesto-secado.test.ts frontend/tests/planta-ahora.test.ts
git commit -m "feat(descremado): servicios y reglas puras del puesto de Descremado"
```

---

### Task 6: El puesto, el retiro de lo viejo y las rutas

**Files:**
- Create: `frontend/src/pages/Descremado/TarjetaDescremadora.tsx`, `CancelarPreparacion.tsx`, `PrepararDescremado.tsx`, `CierreDescremado.tsx`, `PuestoDescremado.tsx`
- Delete: `frontend/src/pages/Procesos/FormularioDescremacion.tsx`, `frontend/src/pages/Procesos/CierreDescremacion.tsx`
- Modify: `frontend/src/pages/Procesos/Procesos.tsx`, `frontend/src/pages/Produccion/Produccion.tsx`, `frontend/src/pages/Produccion/BandejaTrabajoArea.tsx`, `frontend/src/pages/Leche/Silos.tsx`
- Modify: `frontend/src/app/routes.tsx`, `frontend/src/services/navegacion-operacional.ts`, `frontend/src/services/planta-ahora.ts`, `frontend/src/services/procesos.service.ts`
- Modify: `frontend/tests/navegacion-operacional.test.ts`, `frontend/tests/planta-ahora.test.ts`
- Modify: `backend/procesos/views.py` (`opciones_alta`), `backend/procesos/dominio.py` (`RUTAS_POR_ETAPA`), `backend/procesos/tests_destinos.py`, `backend/procesos/tests_descremacion.py` (`test_opciones_alta_entrega_solo_maestros_compatibles`), `backend/procesos/tests_puesto_descremado.py`
- Modify: `CLAUDE.md`

**Interfaces:**
- Consumes: todo lo de la Task 5; `obtenerOpcionesAltaDescremacion`, `sugerirBalanceDescremacion`, `cerrarDescremacion`, `type CorridaDescremacion`, `type SugerenciaDescremacion` (`procesos.service.ts`); `ConfirmarAccion`; `TablaConsulta`; `useCarga`, `mensajeDe`; `mensajeErrorProceso`; `cantidad`; `puedeAccederModulo`; `obtenerSesion`.
- Produces: `GET /api/procesos/descremaciones/opciones-alta/` → `{etapas, productos_descremada, productos_crema, rutas, bloqueos}` (sin `equipos`, `silos_descremada`, `estanques_crema`). `OpcionesAltaDescremacion` del frontend igual.

- [ ] **Step 1: Tarjeta** — `frontend/src/pages/Descremado/TarjetaDescremadora.tsx`:

```tsx
import { useId } from "react";
import { Link } from "react-router-dom";

import { puedeAccederModulo } from "../../services/access-control";
import type { DescremadoraPuesto } from "../../services/descremado.service";
import { cantidad } from "../../services/formato";
import { accionDeDescremadora, corridaCancelable, moduloDeResolver } from "../../services/puesto-descremado";
import { obtenerSesion } from "../../services/sesion";

/* ¿Lleva el enlace a un módulo en el que el usuario puede entrar? Si no, se
   omite: «Acceso restringido» no resuelve nada. Condensación no entra a
   `/silos`; Calidad sí (Desviación 7). */
function puedeIr(ruta: string): boolean {
  const modulo = moduloDeResolver(ruta);
  return modulo !== null && puedeAccederModulo(obtenerSesion()?.usuario, modulo);
}

const ROTULO = { disponible: "Disponible", preparada: "Preparada", en_curso: "En curso" } as const;

/* Una tarjeta, un estado, una acción. Lo que dice lo decidió el servidor.
   Una descremadora preparada lleva además, en segundo plano, «Cancelar
   preparación», que confirma el puesto en un modal. */
export default function TarjetaDescremadora({ fila, ocupado, puedeOperar, onPreparar, onIniciar, onCerrar, onCancelar }: {
  fila: DescremadoraPuesto;
  ocupado: boolean;
  /* Quien no opera Descremación (Calidad) ve el mismo estado, motivos y
     avisos, sin botones: ninguno le daría otra cosa que un 403. */
  puedeOperar: boolean;
  onPreparar: (equipoId: number) => void;
  onIniciar: (corridaId: number) => void;
  onCerrar: (corridaId: number) => void;
  onCancelar: (fila: DescremadoraPuesto) => void;
}) {
  const accion = accionDeDescremadora(fila);
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
      {corrida && (
        <div className="space-y-1 text-sm text-slate-700">
          <p className="font-mono">{corrida.ejecucion_codigo}</p>
          {corrida.silo_entera && <p>Desde {corrida.silo_entera} · {cantidad(corrida.litros_entrada, "L")}</p>}
          {corrida.silo_descremada && <p>Descremada → {corrida.silo_descremada} · {cantidad(corrida.litros_descremada_plan, "L")}</p>}
          {corrida.estanque_crema && <p>Crema → {corrida.estanque_crema} · {cantidad(corrida.litros_crema_plan, "L")}</p>}
          {corrida.iniciada_en && <p className="text-slate-600">Inició {new Date(corrida.iniciada_en).toLocaleString("es-CL")}</p>}
        </div>
      )}
      {fila.en_calidad && (
        <p className="text-sm text-violet-800">
          {fila.en_calidad.tanques.length > 0 ? fila.en_calidad.tanques.join(" y ") : "Las salidas"} de{" "}
          <span className="font-mono">{fila.en_calidad.ejecucion_codigo}</span> esperando Calidad
        </p>
      )}
      {accion.tipo === "preparar" && puedeOperar && (
        <button type="button" disabled={!accion.habilitada} aria-describedby={describe} onClick={() => onPreparar(fila.equipo_id)} className="rounded-xl bg-emerald-700 px-4 py-3 text-sm font-semibold text-white hover:bg-emerald-800 disabled:opacity-40">Preparar descremado</button>
      )}
      {accion.tipo === "iniciar" && puedeOperar && corridaId !== null && (
        <button type="button" disabled={!accion.habilitada || ocupado} aria-describedby={describe} onClick={() => onIniciar(corridaId)} className="rounded-xl bg-emerald-700 px-4 py-3 text-sm font-semibold text-white hover:bg-emerald-800 disabled:opacity-40">
          {ocupado ? "Iniciando…" : "Iniciar descremado"}
        </button>
      )}
      {accion.tipo === "cerrar" && puedeOperar && corridaId !== null && (
        <button type="button" disabled={!accion.habilitada} aria-describedby={describe} onClick={() => onCerrar(corridaId)} className="rounded-xl bg-green-700 px-4 py-3 text-sm font-semibold text-white hover:bg-green-800 disabled:opacity-40">Registrar salidas y cerrar</button>
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

- [ ] **Step 2: Cancelar preparación (modal compartido)** — `frontend/src/pages/Descremado/CancelarPreparacion.tsx`:

```tsx
import { useId, useState, type FormEvent } from "react";

import ConfirmarAccion from "../../components/operacion/ConfirmarAccion";
import { mensajeErrorProceso } from "../../services/errores-proceso";

/*
  Motivo y confirmación para soltar una preparación. Lo abren la tarjeta
  (descremadora preparada) y el historial (corridas `borrador` heredadas del
  modal anterior), con la misma regla: `corridaCancelable`.
*/
export default function CancelarPreparacion({ codigo, filas, alVolver, alCancelar }: {
  codigo: string;
  filas: { etiqueta: string; valor: string }[];
  alVolver: () => void;
  /* Rechaza si el servidor no cancela; el modal muestra el motivo. */
  alCancelar: (motivo: string) => Promise<void>;
}) {
  const [motivo, setMotivo] = useState("");
  const [confirmando, setConfirmando] = useState(false);
  const [enviando, setEnviando] = useState(false);
  const [error, setError] = useState("");
  const idTitulo = useId();
  const idMotivo = useId();

  const revisar = (evento: FormEvent) => {
    evento.preventDefault();
    if (motivo.trim()) setConfirmando(true);
  };

  const confirmar = async () => {
    if (enviando) return;
    setEnviando(true);
    setError("");
    try {
      await alCancelar(motivo.trim());
    } catch (causa) {
      setError(mensajeErrorProceso(causa, "No se pudo cancelar la preparación."));
    } finally {
      setEnviando(false);
    }
  };

  return (
    <div className="fixed inset-0 z-[70] overflow-y-auto bg-slate-950/45 p-4" role="dialog" aria-modal="true" aria-labelledby={idTitulo}>
      <div className="mx-auto my-8 max-w-xl space-y-4 rounded-2xl bg-white p-6 shadow-xl">
        <h2 id={idTitulo} className="text-xl font-bold text-slate-900">Cancelar la preparación {codigo}</h2>
        {confirmando ? (
          <ConfirmarAccion
            titulo="Cancelar la preparación"
            filas={[...filas, { etiqueta: "Motivo", valor: motivo.trim() }]}
            advertencia="La descremadora queda disponible y se sueltan las reservas del silo y de los dos TK. No se mueve leche: hasta el cierre no salió nada del silo."
            textoConfirmar="Cancelar preparación"
            peligro
            ocupado={enviando}
            error={error}
            onConfirmar={() => void confirmar()}
            onVolver={() => { setError(""); setConfirmando(false); }}
          />
        ) : (
          <form onSubmit={revisar} className="space-y-3">
            <label htmlFor={idMotivo} className="block text-sm font-medium text-slate-700">Motivo de la cancelación</label>
            <textarea id={idMotivo} required value={motivo} onChange={(e) => setMotivo(e.target.value)} rows={3} className="w-full rounded-xl border border-slate-300 bg-white px-3 py-2 text-sm outline-none focus:border-emerald-600" />
            <div className="flex flex-wrap justify-end gap-2">
              <button type="button" onClick={alVolver} className="rounded-xl border border-slate-300 bg-white px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-100">Volver</button>
              <button type="submit" disabled={!motivo.trim()} className="rounded-xl bg-slate-800 px-4 py-2 text-sm font-semibold text-white disabled:opacity-40">Revisar cancelación</button>
            </div>
          </form>
        )}
      </div>
    </div>
  );
}
```

- [ ] **Step 3: Formulario guiado** — `frontend/src/pages/Descremado/PrepararDescremado.tsx`:

```tsx
import { useEffect, useId, useRef, useState, type FormEvent, type ReactNode } from "react";
import { X } from "lucide-react";
import { Link } from "react-router-dom";

import ConfirmarAccion from "../../components/operacion/ConfirmarAccion";
import {
  prepararDescremado, type DestinoRamaCrema, type PuestoDescremado,
} from "../../services/descremado.service";
import { mensajeErrorProceso } from "../../services/errores-proceso";
import { cantidad } from "../../services/formato";
import {
  obtenerOpcionesAltaDescremacion, sugerirBalanceDescremacion,
  type OpcionesAltaDescremacion, type SugerenciaDescremacion,
} from "../../services/procesos.service";

const control = "mt-1 w-full rounded-xl border border-slate-300 bg-white px-3 py-2.5 text-sm outline-none focus:border-emerald-600";

/*
  «Preparar descremado»: silo → descremadora → litros → producto y TK de cada
  rama → destino y ruta de la crema → sugerencia → confirmación. Silos,
  descremadoras y TK vienen del puesto (`descremaciones/puesto/`), con la
  regla que «Preparar» vuelve a aplicar: no hay selector de análisis —el
  servidor usa el último confirmado del silo— ni de código. Preparar no
  inicia: la tarjeta habilita «Iniciar descremado» cuando el servidor lo
  permite.
*/
export default function PrepararDescremado({ puesto, siloInicial, equipoInicial, alCerrar, alPreparar }: {
  puesto: PuestoDescremado;
  siloInicial?: number;
  equipoInicial?: number;
  alCerrar: () => void;
  alPreparar: (codigo: string) => void;
}) {
  const [opciones, setOpciones] = useState<OpcionesAltaDescremacion | null>(null);
  const [silo, setSilo] = useState(siloInicial ? String(siloInicial) : "");
  const [equipo, setEquipo] = useState(equipoInicial ? String(equipoInicial) : "");
  const [etapaElegida, setEtapaElegida] = useState("");
  const [litros, setLitros] = useState("");
  const [productoDescremada, setProductoDescremada] = useState("");
  const [productoCrema, setProductoCrema] = useState("");
  const [tkDescremada, setTkDescremada] = useState("");
  const [tkCrema, setTkCrema] = useState("");
  const [ramaCrema, setRamaCrema] = useState<DestinoRamaCrema>("siguiente_proceso");
  const [rutaDescremada, setRutaDescremada] = useState("");
  const [rutaCrema, setRutaCrema] = useState("");
  const [sugerencia, setSugerencia] = useState<SugerenciaDescremacion | null>(null);
  const [planDescremada, setPlanDescremada] = useState("");
  const [planCrema, setPlanCrema] = useState("");
  const [planConfirmado, setPlanConfirmado] = useState(false);
  const [calculando, setCalculando] = useState(false);
  const [revisando, setRevisando] = useState(false);
  const [guardando, setGuardando] = useState(false);
  const [error, setError] = useState("");
  const enviando = useRef(false);
  const idTitulo = useId();

  useEffect(() => {
    let vigente = true;
    obtenerOpcionesAltaDescremacion()
      .then((datos) => {
        if (!vigente) return;
        const descremada = datos.productos_descremada[0];
        const crema = datos.productos_crema[0];
        setOpciones(datos);
        setProductoDescremada(String(descremada?.id ?? ""));
        setProductoCrema(String(crema?.id ?? ""));
        setRutaDescremada(String(datos.rutas.find((ruta) => ruta.producto === descremada?.id
          && ruta.etapas.some((etapa) => etapa.tipo === "estandarizacion"))?.id ?? ""));
        setRutaCrema(String(datos.rutas.find((ruta) => ruta.producto === crema?.id
          && ruta.etapas.some((etapa) => etapa.tipo === "mantequilla"))?.id ?? ""));
      })
      .catch((causa) => {
        if (vigente) setError(mensajeErrorProceso(causa, "No se pudieron cargar productos y rutas de descremado."));
      });
    return () => { vigente = false; };
  }, []);

  const etapas = opciones?.etapas ?? [];
  // Con una sola etapa activa no se pregunta: se elige sola.
  const etapa = etapas.length === 1 ? String(etapas[0].id) : etapaElegida;
  const origen = puesto.origenes.find((item) => item.id === Number(silo));
  const libres = puesto.descremadoras.filter((item) => item.estado === "disponible" && item.motivos_para_tomar.length === 0);
  const maquina = libres.find((item) => item.equipo_id === Number(equipo));
  const destinoDescremada = puesto.destinos_descremada.find((item) => item.id === Number(tkDescremada));
  const destinoCrema = puesto.destinos_crema.find((item) => item.id === Number(tkCrema));
  const rutas = opciones?.rutas ?? [];
  const rutasDescremada = rutas.filter((ruta) => ruta.producto === Number(productoDescremada)
    && ruta.etapas.some((e) => e.tipo === "estandarizacion"));
  const rutasCrema = rutas.filter((ruta) => ramaCrema === "despacho_directo"
    ? ruta.producto === Number(productoCrema) && ruta.destino_final === "despacho_directo"
    : ruta.producto === Number(productoCrema) && ruta.etapas.some((e) => ["mantequilla", "estandarizacion"].includes(e.tipo)));
  const sinEspecificacion = [
    opciones?.productos_descremada.find((item) => item.id === Number(productoDescremada)),
    opciones?.productos_crema.find((item) => item.id === Number(productoCrema)),
  ].filter((item) => item && !item.tiene_especificacion_silo_vigente);
  const bloqueos = opciones?.bloqueos ?? [];
  const excedeDescremada = Boolean(destinoDescremada && Number(planDescremada) > Number(destinoDescremada.libre_l));
  const excedeCrema = Boolean(destinoCrema && Number(planCrema) > Number(destinoCrema.libre_l));
  const completo = Boolean(
    opciones && bloqueos.length === 0 && sinEspecificacion.length === 0 && etapa
    && origen?.analisis && !origen.motivo && maquina && Number(litros) > 0
    && destinoDescremada && destinoCrema && rutaDescremada && rutaCrema
    && sugerencia && planConfirmado && Number(planDescremada) > 0 && Number(planCrema) > 0,
  );

  /* Cambiar litros o productos invalida el reparto: se vuelve a calcular. */
  const invalidarPlan = () => {
    setSugerencia(null);
    setPlanDescremada("");
    setPlanCrema("");
    setPlanConfirmado(false);
  };

  const calcular = async () => {
    if (!origen?.analisis || !(Number(litros) > 0)) {
      setError("Elige el silo de origen y los litros antes de calcular.");
      return;
    }
    setCalculando(true);
    setError("");
    try {
      const propuesta = await sugerirBalanceDescremacion({
        analisis_entrada: origen.analisis.id, litros_entrada: Number(litros),
        producto_descremada: Number(productoDescremada), producto_crema: Number(productoCrema),
      });
      setSugerencia(propuesta);
      setPlanDescremada(propuesta.litros_descremada_sugeridos);
      setPlanCrema(propuesta.litros_crema_sugeridos);
      setPlanConfirmado(false);
    } catch (causa) {
      setError(mensajeErrorProceso(causa, "No se pudo calcular la sugerencia de reparto."));
    } finally {
      setCalculando(false);
    }
  };

  const revisar = (evento: FormEvent) => {
    evento.preventDefault();
    if (completo) setRevisando(true);
  };

  const confirmar = async () => {
    if (enviando.current || !origen || !maquina || !destinoDescremada || !destinoCrema) return;
    enviando.current = true;
    setGuardando(true);
    setError("");
    try {
      const corrida = await prepararDescremado({
        etapa: Number(etapa), equipo: maquina.equipo_id, silo_entera: origen.id,
        litros_entrada: Number(litros),
        silo_descremada: destinoDescremada.id, estanque_crema: destinoCrema.id,
        producto_descremada: Number(productoDescremada), producto_crema: Number(productoCrema),
        litros_descremada_plan: Number(planDescremada), litros_crema_plan: Number(planCrema),
        plan_confirmado: true,
        ruta_descremada: Number(rutaDescremada), ruta_crema: Number(rutaCrema),
        destino_descremada: "estandarizacion", destino_crema: ramaCrema,
      });
      alPreparar(corrida.ejecucion_codigo);
    } catch (causa) {
      setError(mensajeErrorProceso(causa, "No se pudo preparar el descremado."));
      setRevisando(false);
    } finally {
      enviando.current = false;
      setGuardando(false);
    }
  };

  return (
    <div className="fixed inset-0 z-[70] overflow-y-auto bg-slate-950/45 p-4" role="dialog" aria-modal="true" aria-labelledby={idTitulo}>
      <form onSubmit={revisar} className="mx-auto my-8 max-w-3xl space-y-5 rounded-2xl bg-white p-6 shadow-xl">
        <div className="flex items-start justify-between gap-4">
          <div>
            <p className="text-xs font-bold uppercase tracking-wider text-emerald-700">Puesto de Descremado</p>
            <h2 id={idTitulo} className="mt-1 text-2xl font-bold text-slate-900">Preparar descremado</h2>
            <p className="mt-2 text-sm text-slate-600">Reserva el silo y los dos TK y toma la descremadora. El descremado se inicia después, desde la tarjeta.</p>
          </div>
          <button type="button" onClick={alCerrar} disabled={guardando} className="rounded-lg p-2 hover:bg-slate-100" aria-label="Cerrar"><X className="h-5 w-5" /></button>
        </div>

        <fieldset className="grid gap-4 sm:grid-cols-2" disabled={revisando}>
          <Campo texto="Silo de origen">
            <select required value={silo} onChange={(e) => { setSilo(e.target.value); invalidarPlan(); }} className={control}>
              <option value="">Seleccionar…</option>
              {puesto.origenes.map((item) => (
                <option key={item.id} value={item.id} disabled={Boolean(item.motivo)}>
                  {item.codigo} · {cantidad(item.saldo_l, "L")}{item.motivo ? " · no disponible" : ""}
                </option>
              ))}
            </select>
          </Campo>
          <div className="rounded-xl bg-slate-50 px-4 py-3 text-sm text-slate-700">
            <span className="block text-xs text-slate-500">Composición que se usará</span>
            {origen?.analisis
              ? `${origen.analisis.grasa} % MG · ${origen.analisis.sng} % SNG · análisis del ${new Date(origen.analisis.tomado_en).toLocaleString("es-CL")}`
              : "—"}
          </div>
          {origen?.motivo && <p role="alert" className="rounded-xl bg-red-50 px-4 py-3 text-sm text-red-800 sm:col-span-2">{origen.motivo}</p>}
          {siloInicial !== undefined && !puesto.origenes.some((item) => item.id === siloInicial) && (
            <p className="rounded-xl bg-amber-50 px-4 py-3 text-sm text-amber-900 sm:col-span-2">El silo elegido no tiene leche para descremar.</p>
          )}
          {etapas.length > 1 && (
            <Campo texto="Etapa de descremación">
              <select required value={etapaElegida} onChange={(e) => setEtapaElegida(e.target.value)} className={control}>
                <option value="">Seleccionar…</option>
                {etapas.map((item) => <option key={item.id} value={item.id}>{item.nombre}</option>)}
              </select>
            </Campo>
          )}
          <Campo texto="Descremadora">
            <select required value={equipo} onChange={(e) => setEquipo(e.target.value)} className={control}>
              <option value="">Seleccionar…</option>
              {libres.map((item) => <option key={item.equipo_id} value={item.equipo_id}>{item.codigo} · {item.nombre}</option>)}
            </select>
          </Campo>
          <Campo texto="Litros de entrada">
            <input required type="number" min="1" step="0.01" max={origen?.saldo_l} value={litros} onChange={(e) => { setLitros(e.target.value); invalidarPlan(); }} className={control} />
          </Campo>
          <Campo texto="Producto · leche descremada">
            <select required value={productoDescremada} onChange={(e) => { setProductoDescremada(e.target.value); setRutaDescremada(""); invalidarPlan(); }} className={control}>
              <option value="">Seleccionar…</option>
              {(opciones?.productos_descremada ?? []).map((item) => <option key={item.id} value={item.id}>{item.nombre}</option>)}
            </select>
          </Campo>
          <Campo texto="TK de leche descremada">
            <select required value={tkDescremada} onChange={(e) => setTkDescremada(e.target.value)} className={control}>
              <option value="">Seleccionar…</option>
              {puesto.destinos_descremada.map((item) => <option key={item.id} value={item.id}>{item.codigo} · {cantidad(item.libre_l, "L")} libres</option>)}
            </select>
          </Campo>
          <Campo texto="Ruta de la leche descremada">
            <select required value={rutaDescremada} onChange={(e) => setRutaDescremada(e.target.value)} className={control}>
              <option value="">Seleccionar…</option>
              {rutasDescremada.map((ruta) => <option key={ruta.id} value={ruta.id}>{ruta.producto_nombre} · {ruta.proceso_nombre}</option>)}
            </select>
          </Campo>
          <Campo texto="Producto · crema">
            <select required value={productoCrema} onChange={(e) => { setProductoCrema(e.target.value); setRutaCrema(""); invalidarPlan(); }} className={control}>
              <option value="">Seleccionar…</option>
              {(opciones?.productos_crema ?? []).map((item) => <option key={item.id} value={item.id}>{item.nombre}</option>)}
            </select>
          </Campo>
          <Campo texto="TK de crema">
            <select required value={tkCrema} onChange={(e) => setTkCrema(e.target.value)} className={control}>
              <option value="">Seleccionar…</option>
              {puesto.destinos_crema.map((item) => <option key={item.id} value={item.id}>{item.codigo} · {cantidad(item.libre_l, "L")} libres</option>)}
            </select>
          </Campo>
          <Campo texto="Destino de la crema">
            <select required value={ramaCrema} onChange={(e) => { setRamaCrema(e.target.value as DestinoRamaCrema); setRutaCrema(""); }} className={control}>
              <option value="siguiente_proceso">Mantequilla / siguiente proceso</option>
              <option value="estandarizacion">Estandarización</option>
              <option value="despacho_directo">Despacho directo</option>
            </select>
          </Campo>
          <Campo texto="Ruta de la crema">
            <select required value={rutaCrema} onChange={(e) => setRutaCrema(e.target.value)} className={control}>
              <option value="">Seleccionar…</option>
              {rutasCrema.map((ruta) => <option key={ruta.id} value={ruta.id}>{ruta.producto_nombre} · {ruta.proceso_nombre}</option>)}
            </select>
          </Campo>
        </fieldset>
        {libres.length === 0 && <p className="rounded-xl bg-amber-50 p-3 text-sm text-amber-900">No hay descremadoras disponibles: todas están preparadas, en curso o en CIP.</p>}

        <section aria-label="Reparto planificado" className="rounded-2xl border border-sky-200 bg-sky-50 p-4">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <h3 className="font-semibold text-slate-900">Reparto planificado</h3>
              <p className="text-xs text-slate-600">El sistema sugiere por balance de materia grasa; el operador confirma o ajusta. Estos litros se reservan en los TK.</p>
            </div>
            <button type="button" disabled={calculando || revisando || !origen?.analisis} onClick={() => void calcular()} className="rounded-xl border border-sky-700 bg-white px-4 py-2 text-sm font-semibold text-sky-800 disabled:opacity-50">{calculando ? "Calculando…" : "Calcular sugerencia"}</button>
          </div>
          {sugerencia && (
            <fieldset className="mt-4 grid gap-3 sm:grid-cols-2" disabled={revisando}>
              <Campo texto="Descremada planificada (L)">
                <input required type="number" min="0.01" step="0.01" value={planDescremada} onChange={(e) => { setPlanDescremada(e.target.value); setPlanConfirmado(false); }} className={control} />
              </Campo>
              <Campo texto="Crema planificada (L)">
                <input required type="number" min="0.01" step="0.01" value={planCrema} onChange={(e) => { setPlanCrema(e.target.value); setPlanConfirmado(false); }} className={control} />
              </Campo>
              <p className="text-xs text-slate-600">Referencia descremada: {sugerencia.grasa_descremada_objetivo} % MG</p>
              <p className="text-xs text-slate-600">Referencia crema: {sugerencia.grasa_crema_objetivo} % MG</p>
              {(excedeDescremada || excedeCrema) && (
                <p className="rounded-xl bg-amber-50 px-3 py-2 text-sm text-amber-900 sm:col-span-2">El plan supera la capacidad libre de {[excedeDescremada && destinoDescremada?.codigo, excedeCrema && destinoCrema?.codigo].filter(Boolean).join(" y ")}: «Preparar» lo va a rechazar.</p>
              )}
              <label className="flex items-start gap-3 rounded-xl bg-white p-3 text-sm text-slate-700 sm:col-span-2">
                <input type="checkbox" className="mt-1" checked={planConfirmado} onChange={(e) => setPlanConfirmado(e.target.checked)} />
                <span>Confirmo que revisé los volúmenes sugeridos y que estos serán los volúmenes reservados en los TK.</span>
              </label>
            </fieldset>
          )}
        </section>

        {sinEspecificacion.length > 0 && (
          <div className="rounded-xl bg-amber-50 px-4 py-3 text-sm text-amber-900">
            <p>Falta una especificación de silo vigente para: {sinEspecificacion.map((item) => item?.nombre).join(" y ")}.</p>
            <p className="mt-1">Solicita a Calidad configurarla en <Link to="/maestros?seccion=especificaciones" className="font-semibold underline">Maestros · Especificaciones</Link>.</p>
          </div>
        )}
        {bloqueos.map((bloqueo) => <p key={bloqueo.codigo} className="rounded-xl bg-amber-50 px-4 py-3 text-sm text-amber-900">{bloqueo.mensaje}</p>)}
        {error && !revisando && <p role="alert" className="rounded-xl bg-red-50 px-4 py-3 text-sm text-red-800">{error}</p>}

        {revisando && origen && maquina && destinoDescremada && destinoCrema ? (
          <ConfirmarAccion
            titulo="Preparar el descremado"
            filas={[
              { etiqueta: "Origen", valor: `${origen.codigo} · ${cantidad(litros, "L")}` },
              { etiqueta: "Composición", valor: origen.analisis ? `${origen.analisis.grasa} % MG · ${origen.analisis.sng} % SNG` : "—" },
              { etiqueta: "Descremadora", valor: maquina.nombre },
              { etiqueta: "Leche descremada", valor: `${destinoDescremada.codigo} · ${cantidad(planDescremada, "L")}` },
              { etiqueta: "Crema", valor: `${destinoCrema.codigo} · ${cantidad(planCrema, "L")}` },
            ]}
            textoConfirmar="Preparar descremado"
            ocupado={guardando}
            error={error}
            onConfirmar={() => void confirmar()}
            onVolver={() => setRevisando(false)}
          />
        ) : (
          <div className="flex justify-end gap-3">
            <button type="button" onClick={alCerrar} className="rounded-xl border border-slate-300 px-4 py-2.5 text-sm font-semibold text-slate-700">Cancelar</button>
            <button type="submit" disabled={!completo} className="rounded-xl bg-emerald-700 px-5 py-2.5 text-sm font-semibold text-white disabled:opacity-40">Revisar y confirmar</button>
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

- [ ] **Step 4: Cierre con avisos del servidor** — `frontend/src/pages/Descremado/CierreDescremado.tsx`:

```tsx
import { useEffect, useId, useRef, useState, type ChangeEvent, type FormEvent, type ReactNode } from "react";
import { X } from "lucide-react";

import ConfirmarAccion from "../../components/operacion/ConfirmarAccion";
import {
  revisarCierreDescremado, type RevisionCierreDescremado, type ValoresCierreDescremado,
} from "../../services/descremado.service";
import { mensajeErrorProceso } from "../../services/errores-proceso";
import { cantidad } from "../../services/formato";
import { cerrarDescremacion, type CorridaDescremacion } from "../../services/procesos.service";

type Campos = Record<keyof ValoresCierreDescremado, string>;
const VACIO: Campos = { litros_descremada: "", grasa_descremada: "", litros_crema: "", grasa_crema: "" };
const control = "mt-1 w-full rounded-xl border border-slate-300 bg-white px-3 py-2.5 text-sm outline-none focus:border-emerald-600";

function aValores(campos: Campos): ValoresCierreDescremado {
  const numero = (texto: string) => (texto.trim() === "" ? null : Number(texto));
  return {
    litros_descremada: numero(campos.litros_descremada),
    grasa_descremada: numero(campos.grasa_descremada),
    litros_crema: numero(campos.litros_crema),
    grasa_crema: numero(campos.grasa_crema),
  };
}

/*
  «Registrar salidas y cerrar». Los avisos —límites de grasa y balance— los
  calcula el servidor mientras se teclea (`revisar-cierre/`, que no escribe),
  con la misma función que los guarda al cerrar. El cliente no calcula nada.
  Avisan: no deshabilitan el cierre.
*/
export default function CierreDescremado({ corrida, alCerrar, alCompletarse }: {
  corrida: CorridaDescremacion;
  alCerrar: () => void;
  alCompletarse: (corrida: CorridaDescremacion) => void;
}) {
  const [campos, setCampos] = useState<Campos>(VACIO);
  const [revision, setRevision] = useState<RevisionCierreDescremado | null>(null);
  const [revisando, setRevisando] = useState(false);
  const [guardando, setGuardando] = useState(false);
  const [error, setError] = useState("");
  const enviando = useRef(false);
  const idTitulo = useId();

  useEffect(() => {
    let vigente = true;
    // Con retardo: una consulta por pausa al teclear, no una por tecla.
    const tarea = window.setTimeout(() => {
      revisarCierreDescremado(corrida.id, aValores(campos))
        .then((datos) => { if (vigente) setRevision(datos); })
        .catch(() => { if (vigente) setRevision(null); });
    }, 400);
    return () => { vigente = false; window.clearTimeout(tarea); };
  }, [corrida.id, campos]);

  const limites = revision?.avisos_limites.map((aviso) => aviso.mensaje) ?? [];
  const avisos = [...limites, ...(revision?.avisos_balance ?? [])];
  const completo = Object.values(campos).every((valor) => valor.trim() !== "" && Number(valor) >= 0)
    && Number(campos.litros_descremada) > 0 && Number(campos.litros_crema) > 0;
  const cambiar = (clave: keyof Campos) => (evento: ChangeEvent<HTMLInputElement>) => {
    const valor = evento.target.value;
    setCampos((actual) => ({ ...actual, [clave]: valor }));
  };

  const revisar = (evento: FormEvent) => {
    evento.preventDefault();
    if (completo) setRevisando(true);
  };

  const confirmar = async () => {
    if (enviando.current) return;
    enviando.current = true;
    setGuardando(true);
    setError("");
    try {
      const cerrada = await cerrarDescremacion(corrida.id, {
        litros_descremada: Number(campos.litros_descremada),
        grasa_descremada: Number(campos.grasa_descremada),
        litros_crema: Number(campos.litros_crema),
        grasa_crema: Number(campos.grasa_crema),
      });
      alCompletarse(cerrada);
    } catch (causa) {
      setError(mensajeErrorProceso(causa, "No se pudo cerrar la descremación."));
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
            <p className="font-mono text-xs font-semibold text-emerald-700">{corrida.ejecucion_codigo}</p>
            <h2 id={idTitulo} className="mt-1 text-2xl font-bold text-slate-900">Registrar salidas</h2>
            <p className="mt-2 text-sm text-slate-600">Entrada: {cantidad(corrida.litros_entrada, "L")} desde {corrida.silo_entera_codigo} · {corrida.grasa_entrada} % MG.</p>
          </div>
          <button type="button" onClick={alCerrar} disabled={guardando} className="rounded-lg p-2 hover:bg-slate-100" aria-label="Cerrar"><X className="h-5 w-5" /></button>
        </div>
        <fieldset className="grid gap-4 sm:grid-cols-2" disabled={revisando}>
          <Campo texto={`Litros a ${corrida.silo_descremada_codigo}`}><input required type="number" min="0.01" step="0.01" value={campos.litros_descremada} onChange={cambiar("litros_descremada")} className={control} /></Campo>
          <Campo texto="Grasa leche descremada (%)"><input required type="number" min="0" step="0.001" value={campos.grasa_descremada} onChange={cambiar("grasa_descremada")} className={control} /></Campo>
          <Campo texto={`Litros a ${corrida.estanque_crema_codigo}`}><input required type="number" min="0.01" step="0.01" value={campos.litros_crema} onChange={cambiar("litros_crema")} className={control} /></Campo>
          <Campo texto="Grasa crema (%)"><input required type="number" min="0" step="0.001" value={campos.grasa_crema} onChange={cambiar("grasa_crema")} className={control} /></Campo>
        </fieldset>

        <section aria-label="Avisos del cierre" aria-live="polite" className={`rounded-xl px-4 py-3 text-sm ${avisos.length ? "bg-amber-50 text-amber-900" : "bg-slate-50 text-slate-600"}`}>
          {avisos.length > 0
            ? <ul className="space-y-1">{avisos.map((aviso) => <li key={aviso}>{aviso}</li>)}</ul>
            : <p>Sin avisos con lo registrado.</p>}
          {revision?.merma_l && <p className="mt-1">Diferencia volumétrica: {cantidad(revision.merma_l, "L")}</p>}
        </section>

        {error && !revisando && <p role="alert" className="rounded-xl bg-red-50 px-4 py-3 text-sm text-red-800">{error}</p>}
        {revisando ? (
          <ConfirmarAccion
            titulo="Cerrar la descremación"
            filas={[
              { etiqueta: "Entrada", valor: `${corrida.silo_entera_codigo} · ${cantidad(corrida.litros_entrada, "L")}` },
              { etiqueta: "Leche descremada", valor: `${corrida.silo_descremada_codigo} · ${cantidad(campos.litros_descremada, "L")} · ${campos.grasa_descremada} % MG` },
              { etiqueta: "Crema", valor: `${corrida.estanque_crema_codigo} · ${cantidad(campos.litros_crema, "L")} · ${campos.grasa_crema} % MG` },
            ]}
            advertencia={limites.length ? limites.join(" ") : undefined}
            textoConfirmar="Confirmar salidas y cerrar"
            ocupado={guardando}
            error={error}
            onConfirmar={() => void confirmar()}
            onVolver={() => setRevisando(false)}
          />
        ) : (
          <div className="flex justify-end gap-3">
            <button type="button" onClick={alCerrar} className="rounded-xl border border-slate-300 px-4 py-2.5 text-sm font-semibold text-slate-700">Cancelar</button>
            <button type="submit" disabled={!completo} className="rounded-xl bg-green-700 px-5 py-2.5 text-sm font-semibold text-white disabled:opacity-40">Revisar cierre</button>
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

- [ ] **Step 5: Página** — `frontend/src/pages/Descremado/PuestoDescremado.tsx`:

```tsx
import { useState } from "react";
import { useSearchParams } from "react-router-dom";
import { Plus, RefreshCw } from "lucide-react";

import { mensajeDe, useCarga } from "../../components/seccion/utilidades";
import {
  buscarDescremaciones, cancelarPreparacionDescremado, iniciarDescremado,
  obtenerDescremacion, obtenerPuestoDescremado, type DescremadoraPuesto,
} from "../../services/descremado.service";
import { mensajeErrorProceso } from "../../services/errores-proceso";
import { cantidad } from "../../services/formato";
import { puedeOperarDescremado } from "../../services/permisos-descremado";
import type { CorridaDescremacion } from "../../services/procesos.service";
import { corridaCancelable, situacionDeCorrida } from "../../services/puesto-descremado";
import { obtenerSesion } from "../../services/sesion";
import TablaConsulta from "../Inventario/TablaConsulta";
import CancelarPreparacion from "./CancelarPreparacion";
import CierreDescremado from "./CierreDescremado";
import PrepararDescremado from "./PrepararDescremado";
import TarjetaDescremadora from "./TarjetaDescremadora";

type Cancelando = { id: number; codigo: string; filas: { etiqueta: string; valor: string }[] } | null;

const fecha = (iso: string | null) => (iso ? new Date(iso).toLocaleString("es-CL") : "—");

/*
  Puesto de Descremado: preparar el descremado de un silo (con sus reservas),
  iniciarlo cuando el servidor lo permite, cancelar una preparación y
  registrar las salidas, en una pantalla. Antes eran tres pasos en tres
  pantallas y un botón que preparaba e iniciaba a la vez.
*/
export default function PuestoDescremado() {
  const puesto = useCarga(obtenerPuestoDescremado);
  const [parametros, setParametros] = useSearchParams();
  const siloPedido = Number(parametros.get("silo"));
  const siloInicial = Number.isInteger(siloPedido) && siloPedido > 0 ? siloPedido : undefined;
  const [preparando, setPreparando] = useState<{ equipoId?: number } | null>(null);
  const [iniciando, setIniciando] = useState<number | null>(null);
  const [cerrando, setCerrando] = useState<CorridaDescremacion | null>(null);
  const [cancelando, setCancelando] = useState<Cancelando>(null);
  const [versionHistorial, setVersionHistorial] = useState(0);
  const [mensaje, setMensaje] = useState("");
  const [error, setError] = useState("");
  // Mismo criterio que el servidor (`puede_operar_tipo` con la etapa Descremación).
  const puedeOperar = puedeOperarDescremado(obtenerSesion()?.usuario);
  // «Descremar» del silo llega con `?silo=`: el formulario se abre solo, con ese silo.
  const formulario: { equipoId?: number } | null =
    preparando ?? (siloInicial !== undefined && puedeOperar ? {} : null);

  const cerrarFormulario = () => {
    setPreparando(null);
    if (siloInicial !== undefined) setParametros({}, { replace: true });
  };

  const iniciar = async (corridaId: number) => {
    setMensaje("");
    setError("");
    setIniciando(corridaId);
    try {
      const corrida = await iniciarDescremado(corridaId);
      setMensaje(`Descremado ${corrida.ejecucion_codigo} iniciado en ${corrida.equipo_nombre ?? "la descremadora"}.`);
    } catch (causa) {
      setError(mensajeErrorProceso(causa, "No se pudo iniciar el descremado."));
    } finally {
      setIniciando(null);
      await puesto.recargar();
    }
  };

  const abrirCierre = async (corridaId: number) => {
    setMensaje("");
    setError("");
    try {
      setCerrando(await obtenerDescremacion(corridaId));
    } catch (causa) {
      setError(mensajeDe(causa, "No se pudo cargar la corrida."));
    }
  };

  const cancelarDesdeTarjeta = (fila: DescremadoraPuesto) => {
    const corrida = fila.corrida;
    const id = corridaCancelable(corrida);
    if (!corrida || id === null) return;
    setCancelando({
      id, codigo: corrida.ejecucion_codigo,
      filas: [
        { etiqueta: "Descremadora", valor: fila.nombre },
        { etiqueta: "Origen", valor: `${corrida.silo_entera ?? "—"} · ${cantidad(corrida.litros_entrada, "L")}` },
        { etiqueta: "TK", valor: `${corrida.silo_descremada ?? "—"} y ${corrida.estanque_crema ?? "—"}` },
      ],
    });
  };

  const cancelarDesdeHistorial = (corrida: CorridaDescremacion) => {
    const id = corridaCancelable(corrida);
    if (id === null) return;
    setCancelando({
      id, codigo: corrida.ejecucion_codigo,
      filas: [
        { etiqueta: "Descremadora", valor: corrida.equipo_nombre ?? "—" },
        { etiqueta: "Origen", valor: `${corrida.silo_entera_codigo} · ${cantidad(corrida.litros_entrada, "L")}` },
      ],
    });
  };

  /* El modal muestra el error del servidor: por eso aquí se relanza. */
  const cancelar = async (motivo: string) => {
    if (!cancelando) return;
    const cancelada = await cancelarPreparacionDescremado(cancelando.id, motivo);
    setCancelando(null);
    setMensaje(`Preparación ${cancelada.ejecucion_codigo} cancelada; la descremadora y los TK quedan libres.`);
    setVersionHistorial((version) => version + 1);
    await puesto.recargar();
  };

  return (
    <main className="px-4 py-8 sm:px-8">
      <div className="mx-auto max-w-6xl space-y-6">
        <header className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <p className="text-sm font-semibold uppercase tracking-wider text-emerald-700">Puesto de trabajo</p>
            <h1 className="mt-1 text-3xl font-bold text-slate-900">Descremado</h1>
            <p className="mt-2 max-w-2xl text-slate-600">Prepara el descremado de un silo; luego inicia y registra las salidas desde la tarjeta de la descremadora.</p>
            {!puedeOperar && <p className="mt-2 text-sm font-medium text-slate-600">Vista de consulta: las acciones las registra Condensación.</p>}
          </div>
          <div className="flex items-center gap-2">
            <button type="button" onClick={() => void puesto.recargar()} aria-label="Actualizar" title="Actualizar" className="rounded-xl border border-slate-300 bg-white p-3 text-slate-600 hover:border-emerald-400 hover:text-emerald-700">
              <RefreshCw className="h-5 w-5" />
            </button>
            {puedeOperar && (
              <button type="button" onClick={() => { setMensaje(""); setPreparando({}); }} className="inline-flex items-center gap-2 rounded-xl bg-emerald-700 px-5 py-3 text-sm font-semibold text-white hover:bg-emerald-800">
                <Plus className="h-5 w-5" />Preparar descremado
              </button>
            )}
          </div>
        </header>

        {mensaje && <p role="status" className="rounded-xl border border-green-200 bg-green-50 px-4 py-3 text-sm text-green-900">{mensaje}</p>}
        {error && <p role="alert" className="rounded-xl bg-red-50 px-4 py-3 text-sm text-red-800">{error}</p>}
        {puesto.error && <p role="alert" className="text-sm text-red-800">{puesto.error}</p>}
        {puesto.cargando && !puesto.datos && <p className="text-sm text-slate-600">Cargando descremadoras…</p>}

        <section aria-label="Descremadoras" className="grid gap-4 md:grid-cols-2">
          <h2 className="sr-only">Descremadoras</h2>
          {puesto.datos?.descremadoras.map((fila) => (
            <TarjetaDescremadora
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
          {puesto.datos && puesto.datos.corridas_de_hoy.length === 0 && <p className="text-sm text-slate-600">Hoy no hay corridas de descremado.</p>}
          {puesto.datos && puesto.datos.corridas_de_hoy.length > 0 && (
            <ul className="divide-y divide-slate-100 rounded-2xl border border-slate-200 bg-white">
              {puesto.datos.corridas_de_hoy.map((c) => (
                <li key={c.id} className="flex flex-wrap justify-between gap-2 px-5 py-3 text-sm">
                  <span><span className="font-mono">{c.ejecucion_codigo}</span> · {c.equipo ?? "—"} · {c.silo_entera}</span>
                  <span className="text-slate-700">{situacionDeCorrida(c.estado, c.estado_ejecucion, c.estado_etiqueta)}</span>
                </li>
              ))}
            </ul>
          )}
        </section>

        <section aria-label="Historial de Descremado" className="space-y-3">
          <h2 className="text-lg font-semibold text-slate-900">Historial</h2>
          <TablaConsulta<CorridaDescremacion>
            key={versionHistorial}
            titulo="Historial de corridas de descremado"
            cargar={buscarDescremaciones}
            clave={(f) => f.id}
            ubicaciones={[]}
            conUbicacion={false}
            conFechas
            etiquetaBusqueda="Corrida, silo o TK"
            vacio="No hay corridas que coincidan."
            estados={(puesto.datos?.estados ?? []).map((o) => ({ valor: o.valor, texto: o.etiqueta }))}
            columnas={[
              { titulo: "Corrida", celda: (f) => <span className="font-mono">{f.ejecucion_codigo}</span> },
              { titulo: "Descremadora", celda: (f) => f.equipo_nombre ?? "—" },
              { titulo: "Origen", celda: (f) => `${f.silo_entera_codigo} · ${cantidad(f.litros_entrada, "L")}` },
              { titulo: "Destinos", celda: (f) => `${f.silo_descremada_codigo} + ${f.estanque_crema_codigo}` },
              { titulo: "Inicio", celda: (f) => fecha(f.iniciada_en) },
              { titulo: "Situación", celda: (f) => situacionDeCorrida(f.estado, f.ejecucion_estado, f.estado_etiqueta) },
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
        <PrepararDescremado
          puesto={puesto.datos}
          siloInicial={siloInicial}
          equipoInicial={formulario.equipoId}
          alCerrar={cerrarFormulario}
          alPreparar={(codigo) => {
            cerrarFormulario();
            setMensaje(`Descremado ${codigo} preparado: las reservas quedaron tomadas. Inícialo desde la tarjeta cuando el servidor lo permita.`);
            setVersionHistorial((version) => version + 1);
            void puesto.recargar();
          }}
        />
      )}
      {cerrando && (
        <CierreDescremado
          corrida={cerrando}
          alCerrar={() => setCerrando(null)}
          alCompletarse={(corrida) => {
            setCerrando(null);
            setMensaje(`Corrida ${corrida.ejecucion_codigo} cerrada; las dos ramas pasan a Calidad si la etapa lo exige.`);
            setVersionHistorial((version) => version + 1);
            void puesto.recargar();
          }}
        />
      )}
      {cancelando && (
        <CancelarPreparacion
          codigo={cancelando.codigo}
          filas={cancelando.filas}
          alVolver={() => setCancelando(null)}
          alCancelar={cancelar}
        />
      )}
    </main>
  );
}
```

- [ ] **Step 6: Ruta, menú y destinos**
  - `routes.tsx`: `const PuestoDescremado = lazy(() => import("../pages/Descremado/PuestoDescremado"));` junto a `PuestoEvaporacion`, y dentro de `<Route element={<RutaModulo modulo="produccion" />}>`, debajo de `/produccion/evaporacion`: `<Route path="/produccion/descremado" element={diferido(<PuestoDescremado />)} />`.
  - `navegacion-operacional.ts`, entrada «Descremado»:

```ts
      { etiqueta: "Descremado", ruta: "/produccion/descremado", modulo: "produccion", icono: "produccion", nivel: "proceso", areas: ["condensacion", "calidad"], alias: ["/procesos?seccion=descremacion"] },
```

    y en el comentario de `esRutaOperacionalActual` («Descremación, Mantequilla y Trazabilidad viven en /procesos…») cambia a «Mantequilla y Trazabilidad viven en /procesos…», y agrega «Descremado tampoco, desde su puesto (/produccion/descremado)» junto a la mención de Evaporación.
  - `planta-ahora.ts`: `descremacion: "/produccion/descremado",`.
  - Backend `procesos/dominio.py`: `"descremacion": "/produccion/descremado",`; `procesos/tests_destinos.py:21` igual.
  - `tests/planta-ahora.test.ts:8,21`: `"/produccion/descremado"`.
  - `tests/navegacion-operacional.test.ts`: reemplaza el cuerpo de `test("la ubicación distingue subprocesos que comparten una URL", …)` por:

```ts
  const usuario = usuarioDeArea("condensacion", "Condensación", "produccion");

  assert.ok(esRutaOperacionalActual(
    "/procesos?seccion=mantequilla",
    "/procesos",
    "?seccion=mantequilla",
  ));
  assert.ok(!esRutaOperacionalActual(
    "/procesos?seccion=trazabilidad",
    "/procesos",
    "?seccion=mantequilla",
  ));
  assert.equal(
    contextoOperacionalPara(usuario, "/procesos", "?seccion=mantequilla").actual.etiqueta,
    "Mantequilla",
  );
```

    y agrega:

```ts
test("Descremado tiene su propio puesto; el enlace viejo lo sigue marcando", () => {
  const usuario = usuarioDeArea("condensacion", "Condensación", "produccion");
  const descremado = navegacionPara(usuario).grupos
    .flatMap((grupo) => grupo.enlaces)
    .find((enlace) => enlace.etiqueta === "Descremado");

  assert.equal(descremado?.ruta, "/produccion/descremado");
  assert.equal(descremado?.modulo, "produccion");
  assert.ok(descremado && esEnlaceOperacionalActual(descremado, "/produccion/descremado"));
  // `/procesos?seccion=descremacion` redirige al puesto; mientras tanto, el
  // menú marca la misma entrada.
  assert.ok(descremado && esEnlaceOperacionalActual(descremado, "/procesos", "?seccion=descremacion"));
  assert.equal(
    contextoOperacionalPara(usuario, "/produccion/descremado").actual.etiqueta,
    "Descremado",
  );
});
```

- [ ] **Step 7: Retirar lo viejo**
  - `git rm frontend/src/pages/Procesos/FormularioDescremacion.tsx frontend/src/pages/Procesos/CierreDescremacion.tsx`.
  - `Procesos.tsx`:
    - En el import de `procesos.service` quita `obtenerDescremaciones` y `type CorridaDescremacion`; quita los imports de `CierreDescremacion` y `FormularioDescremacion`; agrega `import { rutaDeEtapa, textoIniciarEnPuesto } from "../../services/planta-ahora";`.
    - Quita los estados `descremaciones`, `descremacionesCargadas`, `cerrandoDescremacion`; las constantes `siloParametro` y `siloDescremacion`; el `useEffect` de `siloDescremacion`; `cerrarFormularioDescremacion`, `actualizarDescremacion` y `cargarDescremaciones`. `const [parametros, setParametros] = useSearchParams();` → `const [parametros] = useSearchParams();`.
    - En el bloque de redirecciones (después de todos los hooks), debajo del de `condensacion`/`evaporacion`:

```tsx
  // Descremado también tiene puesto propio. La acción «Descremar» del silo
  // llegaba aquí con `?accion=descremar&silo=`: un enlace guardado sigue
  // aterrizando en el puesto con el silo elegido.
  if (seccionSolicitada === "descremacion") {
    return <Navigate to="/produccion/descremado" replace />;
  }
  if (parametros.get("accion") === "descremar") {
    const silo = parametros.get("silo");
    return <Navigate to={silo ? `/produccion/descremado?silo=${encodeURIComponent(silo)}` : "/produccion/descremado"} replace />;
  }
```

    - Quita las dos líneas de modales (`FormularioDescremacion` y `CierreDescremacion`) y la `<section id="proceso-descremacion">` completa.
    - En la celda «Acción» de «Ejecuciones operativas», reemplaza la rama `item.etapa_tipo === "secado" && item.estado === "preparacion" ? <Link to="/produccion/secado" …>Iniciar en el puesto de Secado</Link>` por `textoIniciarEnPuesto(item.etapa_tipo, item.estado) ? <Link to={rutaDeEtapa(item.etapa_tipo)} className="text-xs font-semibold text-amber-800 underline">{textoIniciarEnPuesto(item.etapa_tipo, item.estado)}</Link>`.
  - `BandejaTrabajoArea.tsx:170`: el texto del enlace pasa a `{textoIniciarEnPuesto(ejecucion.etapa_tipo, ejecucion.estado) ?? "Abrir tarea"}` (importa `textoIniciarEnPuesto` junto a `rutaDeEtapa`; el destino ya es `rutaDeEtapa`).
  - `Produccion.tsx:267`: `to="/produccion/descremado"`.
  - `Silos.tsx:359`: `<AccionSilo texto="Descremar" icono={GitBranch} destino={`/produccion/descremado?silo=${seleccionado.silo_id}`} />` — **sin** `bloqueado`: el puesto muestra el silo deshabilitado con su motivo (Desviación 8). Agrega encima el comentario `{/* Sin «bloqueado»: preparar no exige firmas ni análisis vigente para entrar; el puesto lo dice con `origenes[].motivo`. */}`.
  - `procesos.service.ts`: elimina `crearEjecucion`, `obtenerDescremaciones`, `crearDescremacion`, `crearDescremacionGuiada` e `iniciarDescremacion`; en `OpcionesAltaDescremacion` quita `equipos`, `silos_descremada` y `estanques_crema`.
  - Comprueba: `grep -rn "seccion=descremacion\|accion=descremar\|FormularioDescremacion\|CierreDescremacion\|crearDescremacion\|iniciarDescremacion\|obtenerDescremaciones\|crearEjecucion\b" frontend/src frontend/tests` → solo el `alias` del menú, el `Navigate` de `Procesos.tsx` y la prueba del menú.

- [ ] **Step 8: `opciones-alta` sin máquinas ni destinos** — en `CorridaDescremacionViewSet.opciones_alta` borra el diccionario `ocupaciones` y las claves `"equipos"`, `"silos_descremada"` y `"estanques_crema"` de la respuesta (los querysets `equipos`, `silos_descremada` y `estanques_crema` se quedan: los usan los `bloqueos` de configuración). Agrega al docstring: «Máquinas y destinos los sirve `puesto/` con la regla de destino: una sola fuente.» Luego quita `ESTADOS_QUE_OCUPAN_EQUIPO` de los imports de `views.py` si queda sin uso.

En `tests_descremacion.py`, `test_opciones_alta_entrega_solo_maestros_compatibles` → renómbrala `test_opciones_alta_entrega_solo_productos_compatibles`; borra la creación de `EQ-NO-DES` y las aserciones sobre `equipos` y `silos_descremada` (quedan `productos_descremada` y `bloqueos`).

En `tests_puesto_descremado.py`, agrega a `PuestoDescremadoTests`:

```python
    def test_opciones_alta_ya_no_sirve_maquinas_ni_destinos(self):
        respuesta = self.cliente().get("/api/procesos/descremaciones/opciones-alta/")

        self.assertEqual(respuesta.status_code, 200, respuesta.data)
        for clave in ("equipos", "silos_descremada", "estanques_crema"):
            self.assertNotIn(clave, respuesta.data)
        for clave in ("etapas", "productos_descremada", "productos_crema", "rutas", "bloqueos"):
            self.assertIn(clave, respuesta.data)
```

- [ ] **Step 9: `CLAUDE.md`** — en «Decisiones vigentes», justo después del punto «Secado tiene puesto propio», agrega:

```markdown
- **Descremado tiene puesto propio** (desde 2026-10-07, `docs/superpowers/specs/2026-10-07-puesto-descremado-design.md`): `/produccion/descremado`, bajo el módulo `produccion`; «Descremar» del silo lleva ahí con `?silo=` (sin deshabilitarse por los motivos de inicio: el puesto muestra el silo con su motivo), y `/procesos?seccion=descremacion` y `/procesos?accion=descremar` redirigen. **Preparar e iniciar son dos pasos.** «Preparar descremado» (`descremaciones/crear-guiada/`) crea la corrida, sus **tres reservas de silo** (origen, TK de descremada, TK de crema) y toma la descremadora en una sola transacción —todo o nada—; el servidor elige el análisis (el último confirmado del silo, `recepcion.servicios.ultimo_analisis_confirmado`, la misma consulta que la compuerta de proceso) y asigna el código `EJ-DES-{id de la corrida}`. Preparar exige solo lo que el plan necesita (`motivos_para_preparar_desde_silo`: silo en servicio, análisis vigente con grasa y SNG); firmas, inhibidores y 48 h son motivos de inicio. «Iniciar» lo habilita el servidor: `motivos_tipados_para_iniciar_descremacion` es la única implementación, la usa `iniciar_descremacion` (que ya no reserva) y la sirve `descremaciones/puesto/`; exige además que el análisis con que se preparó siga siendo el vigente. Origen y destinos se comprueban con las mismas funciones al preparar, al iniciar y al ofrecer (`motivos_origen_descremacion`, `motivos_destino_descremacion`). `ejecuciones/{id}/transicionar/` rechaza iniciar una Descremación («Las corridas de descremado se inician desde el puesto de Descremado.», `MENSAJES_INICIO_EN_PUESTO`, espejo de `textoIniciarEnPuesto` en el frontend); reanudar sigue por ahí. **Cancelar preparación** (`descremaciones/{id}/cancelar-preparacion/`, motivo obligatorio) suelta reservas y descremadora y deja la corrida `anulada`; cancelar la ejecución por cualquier camino deja lo mismo (`_deshacer_preparacion_descremacion`). Los **límites de grasa avisan, no bloquean** (`procesos.dominio.avisos_limites_descremacion`: descremada ≤ 0,1 %; crema para despacho 42–43 %, solo si va a despacho directo): se sirven mientras se teclea (`revisar-cierre/`, que no escribe) y quedan en `controles["avisos_limites"]` y en el evento al cerrar; endurecerlos es decisión de Calidad sobre esa función. `POST descremaciones/` y `POST ejecuciones/` responden 405: una corrida de descremado nace solo en el puesto. Operar exige la etapa Descremación (área Condensación) en todos los caminos; Calidad consulta.
```

- [ ] **Step 10: Verificar** — frontend: `cd frontend && npx tsc -b --pretty false && npx eslint . && npm test`; backend: `cd backend && DJANGO_ENV=test ./.venv/Scripts/python.exe manage.py test procesos --noinput`.
Expected: sin errores / OK.

- [ ] **Step 11: Commit** (revisa `git status` antes; agrega por nombre; las dos eliminaciones ya quedaron preparadas por `git rm`):

```bash
git add frontend/src/pages/Descremado/PuestoDescremado.tsx frontend/src/pages/Descremado/TarjetaDescremadora.tsx frontend/src/pages/Descremado/PrepararDescremado.tsx frontend/src/pages/Descremado/CierreDescremado.tsx frontend/src/pages/Descremado/CancelarPreparacion.tsx frontend/src/pages/Procesos/Procesos.tsx frontend/src/pages/Produccion/Produccion.tsx frontend/src/pages/Produccion/BandejaTrabajoArea.tsx frontend/src/pages/Leche/Silos.tsx frontend/src/app/routes.tsx frontend/src/services/navegacion-operacional.ts frontend/src/services/planta-ahora.ts frontend/src/services/procesos.service.ts frontend/tests/navegacion-operacional.test.ts frontend/tests/planta-ahora.test.ts backend/procesos/views.py backend/procesos/dominio.py backend/procesos/tests_destinos.py backend/procesos/tests_descremacion.py backend/procesos/tests_puesto_descremado.py CLAUDE.md
git commit -m "feat(descremado): puesto de Descremado; la descremación sale de /procesos"
```

---

### Task 7: E2E y aceptación (controlador + implementador)

**Files:**
- Modify: `frontend/e2e/ayudantes.ts` (`analizarSilo`)
- Modify: `frontend/e2e/flujo-descremado.spec.ts` (reescritura de las dos pruebas sobre el puesto; la tercera, «ramas liberadas…», sin cambio)
- Modify: `frontend/e2e/rutas.ts`, `frontend/e2e/README.md` (§ «Descremado con dos ramas»)

- [ ] **Step 1: `analizarSilo` sin segunda firma** — en `frontend/e2e/ayudantes.ts` cambia la firma y el final de `analizarSilo`:

```ts
export async function analizarSilo(
  pagina: Page, estanque: string, leche: { grasa: string; sng: string },
  { segundaFirma = true }: { segundaFirma?: boolean } = {},
): Promise<number> {
```

y, después de `const { id } = await respuesta.json();`:

```ts
  /* Sin segunda firma el análisis queda confirmado pero no habilita procesar:
     es el motivo de inicio que muestra el puesto de Descremado. Quien llama
     firma después con `firmarVisualizacion(id)`. */
  if (!segundaFirma) return id;
  await firmarVisualizacion(id);
```

(reemplaza la llamada `await firmarVisualizacion(id);` que había) y al final de la función, después de `await actualizado.click();`, agrega `return id;`. Los demás llamadores ignoran el retorno: sin cambio.

- [ ] **Step 2: Reescribir `frontend/e2e/flujo-descremado.spec.ts`** — reemplaza los imports y las dos primeras pruebas (la tercera, «ramas liberadas muestran Estandarización y Mantequilla», queda igual):

```ts
import { expect, test, type Page } from "@playwright/test";

import {
  analizarSilo,
  campo,
  cerrarSegundaFirma,
  cerrarSesionesArea,
  elegirOpcion,
  firmarVisualizacion,
  irA,
  trasGuardar,
  usarSesionArea,
  vigilar,
} from "./ayudantes";

test.describe.configure({ mode: "serial" });
test.afterAll(async () => {
  await cerrarSegundaFirma();
  await cerrarSesionesArea();
});

interface Preparado {
  codigo: string;
  litrosDescremada: string;
  litrosCrema: string;
}

/*
  Calidad analiza el origen **sin** la segunda firma y entrega el enlace
  «Descremar» del silo: preparar no exige firmas, iniciar sí. Devuelve la ruta
  del enlace y el id del análisis, para firmarlo después.
*/
async function analizarOrigenSinFirma(page: Page, siloOrigen: string) {
  await usarSesionArea(page, "e2e_calidad");
  const analisisId = await analizarSilo(page, siloOrigen, { grasa: "2.61", sng: "8.70" }, { segundaFirma: false });
  const href = await page.getByRole("link", { name: "Descremar" }).getAttribute("href");
  const rutaDescremar = new URL(href!, page.url()).hash.replace(/^#/, "");
  expect(rutaDescremar).toMatch(/^\/produccion\/descremado\?silo=\d+$/);
  return { analisisId, rutaDescremar };
}

/*
  Producción llega al puesto por «Descremar» con el silo elegido y prepara.
  La tarjeta se busca por el código que asignó el servidor, no por uno
  tecleado.
*/
async function preparar(page: Page, rutaDescremar: string, opciones: {
  litros: string; tkDescremada: string; tkCrema: string; cremaADespacho?: boolean;
}): Promise<Preparado> {
  await usarSesionArea(page, "e2e_produccion");
  await irA(page, rutaDescremar);
  const dialogo = page.getByRole("dialog", { name: "Preparar descremado" });
  await expect(dialogo).toBeVisible({ timeout: 20_000 });
  await elegirOpcion(campo(dialogo, "Descremadora"), /DES-01/i);
  await campo(dialogo, "Litros de entrada").fill(opciones.litros);
  await elegirOpcion(campo(dialogo, "TK de leche descremada"), new RegExp(opciones.tkDescremada, "i"));
  await elegirOpcion(campo(dialogo, "TK de crema"), new RegExp(opciones.tkCrema, "i"));
  if (opciones.cremaADespacho) {
    await campo(dialogo, "Destino de la crema").selectOption("despacho_directo");
    await elegirOpcion(campo(dialogo, "Ruta de la crema"), /despacho directo/i);
  }
  await trasGuardar(page, "/sugerir-balance/", async () => {
    await dialogo.getByRole("button", { name: "Calcular sugerencia" }).click();
  });
  const litrosDescremada = await campo(dialogo, "Descremada planificada (L)").inputValue();
  const litrosCrema = await campo(dialogo, "Crema planificada (L)").inputValue();
  expect(Number(litrosDescremada)).toBeGreaterThan(Number(opciones.litros) * 0.9);
  expect(Number(litrosCrema)).toBeGreaterThan(0);
  await dialogo.getByRole("checkbox", { name: /Confirmo que revisé/ }).check();
  await dialogo.getByRole("button", { name: "Revisar y confirmar" }).click();
  const respuesta = await trasGuardar(page, "/crear-guiada/", async () => {
    await dialogo.getByRole("button", { name: "Preparar descremado" }).click();
  });
  const { ejecucion_codigo: codigo } = await respuesta.json();
  return { codigo: String(codigo), litrosDescremada, litrosCrema };
}

/*
  «Iniciar descremado» está deshabilitado con el motivo de la segunda firma
  hasta que Calidad completa el análisis del origen; entonces el servidor lo
  habilita. La segunda firma es de otra persona (`e2e_calidad_firma`). El
  enlace a /silos no se comprueba: Condensación no entra a Recepción
  (Desviación 7 del plan); lo fija la prueba unitaria.
*/
async function iniciarTrasLaFirma(page: Page, codigo: string, analisisId: number) {
  const tarjeta = page.getByRole("article").filter({ hasText: codigo });
  await expect(tarjeta).toContainText("Preparada", { timeout: 20_000 });
  const iniciar = tarjeta.getByRole("button", { name: "Iniciar descremado" });
  await expect(iniciar).toBeDisabled();
  await expect(tarjeta).toContainText("firma de realización y visualización");

  await firmarVisualizacion(analisisId);
  await page.getByRole("button", { name: "Actualizar" }).click();
  await expect(iniciar).toBeEnabled({ timeout: 20_000 });
  await trasGuardar(page, "/iniciar/", async () => iniciar.click());
  await expect(tarjeta).toContainText("En curso", { timeout: 20_000 });
}

/*
  Registra las dos salidas viendo el aviso de grasa que calcula el servidor
  mientras se teclea (`revisar-cierre/`): primero un valor fuera del límite,
  luego el corregido.
*/
async function registrarSalidas(page: Page, codigo: string, datos: Preparado & {
  tkDescremada: string; tkCrema: string;
  aviso: { campo: string; fuera: string; dentro: string; texto: RegExp };
}) {
  const tarjeta = page.getByRole("article").filter({ hasText: codigo });
  await tarjeta.getByRole("button", { name: "Registrar salidas y cerrar" }).click();
  const dialogo = page.getByRole("dialog", { name: "Registrar salidas" });
  await campo(dialogo, `Litros a ${datos.tkDescremada}`).fill(datos.litrosDescremada);
  await campo(dialogo, "Grasa leche descremada (%)").fill("0.06");
  await campo(dialogo, `Litros a ${datos.tkCrema}`).fill(datos.litrosCrema);
  await campo(dialogo, "Grasa crema (%)").fill("42.00");

  const avisos = dialogo.getByRole("region", { name: "Avisos del cierre" });
  await campo(dialogo, datos.aviso.campo).fill(datos.aviso.fuera);
  await expect(avisos).toContainText(datos.aviso.texto, { timeout: 10_000 });
  await campo(dialogo, datos.aviso.campo).fill(datos.aviso.dentro);
  await expect(avisos).not.toContainText(datos.aviso.texto, { timeout: 10_000 });

  await dialogo.getByRole("button", { name: "Revisar cierre" }).click();
  await trasGuardar(page, "/cerrar/", async () => {
    await dialogo.getByRole("button", { name: "Confirmar salidas y cerrar" }).click();
  });
  const hoy = page.getByRole("region", { name: "Corridas de hoy" });
  await expect(hoy.getByRole("listitem").filter({ hasText: codigo })).toContainText(/Esperando Calidad|Terminada/);
}

async function liberarRamas(page: Page, codigo: string, tkDescremada: string, tkCrema: string) {
  await usarSesionArea(page, "e2e_calidad");
  await analizarSilo(page, tkDescremada, { grasa: "0.06", sng: "8.80" });
  await analizarSilo(page, tkCrema, { grasa: "42.00", sng: "8.80" });
  await irA(page, "/calidad");
  for (const tk of [tkDescremada, tkCrema]) {
    const tarjeta = page.locator("article").filter({ hasText: codigo }).filter({ hasText: tk });
    await expect(tarjeta).toBeVisible({ timeout: 20_000 });
    await elegirOpcion(tarjeta.getByRole("combobox"), /conforme/i);
    await trasGuardar(page, "/liberar/", async () => {
      await tarjeta.getByRole("button", { name: "Liberar etapa" }).click();
    });
  }
}

test("descremado separa, Calidad libera y conserva ambas rutas", async ({ page }) => {
  test.setTimeout(180_000);
  const erroresJs = vigilar(page);
  const siloOrigen = process.env.E2E_SILO_ENTERA ?? "Silo 3";
  const tkDescremada = process.env.E2E_TK_DESCREMADA ?? "Tk02";
  const tkCrema = process.env.E2E_TK_CREMA ?? "TkC2";
  let origen = { analisisId: 0, rutaDescremar: "" };
  let preparado: Preparado = { codigo: "", litrosDescremada: "", litrosCrema: "" };

  await test.step("1 · Calidad analiza el origen sin la segunda firma", async () => {
    origen = await analizarOrigenSinFirma(page, siloOrigen);
  });

  await test.step("2 · Producción prepara desde «Descremar» del silo", async () => {
    preparado = await preparar(page, origen.rutaDescremar, { litros: "1000", tkDescremada, tkCrema });
  });

  await test.step("3 · Iniciar espera la segunda firma; con ella, inicia", async () => {
    await iniciarTrasLaFirma(page, preparado.codigo, origen.analisisId);
  });

  await test.step("4 · Producción registra las salidas viendo el aviso de la descremada", async () => {
    await registrarSalidas(page, preparado.codigo, {
      ...preparado, tkDescremada, tkCrema,
      aviso: { campo: "Grasa leche descremada (%)", fuera: "0.15", dentro: "0.06", texto: /sobre el límite/ },
    });
  });

  await test.step("5 · Calidad analiza y libera cada rama por separado", async () => {
    await liberarRamas(page, preparado.codigo, tkDescremada, tkCrema);
  });

  await test.step("6 · Las ramas muestran su siguiente acción contractual", async () => {
    await irA(page, "/leche/silos");
    await page.getByRole("button", { name: new RegExp(tkDescremada, "i") }).first().click();
    await expect(page.getByRole("link", { name: /Enviar a Estandarizaci[oó]n/ }).first()).toBeVisible();
    await page.getByRole("button", { name: new RegExp(tkCrema, "i") }).first().click();
    await expect(page.getByRole("link", { name: "Iniciar Mantequilla" }).first()).toBeVisible();
  });

  expect(erroresJs).toHaveLength(0);
});

test("crema liberada sigue su ruta comercial hasta despacho directo", async ({ page }) => {
  test.setTimeout(180_000);
  const erroresJs = vigilar(page);
  const siloOrigen = process.env.E2E_SILO_ENTERA ?? "Silo 3";
  const tkDescremada = process.env.E2E_TK_DESCREMADA_DIRECTA ?? "Tk03";
  const tkCrema = process.env.E2E_TK_CREMA_DIRECTA ?? "TkC3";
  let origen = { analisisId: 0, rutaDescremar: "" };
  let preparado: Preparado = { codigo: "", litrosDescremada: "", litrosCrema: "" };

  await test.step("1 · Calidad analiza el origen sin la segunda firma", async () => {
    origen = await analizarOrigenSinFirma(page, siloOrigen);
  });

  await test.step("2 · Producción prepara con la crema a despacho directo", async () => {
    preparado = await preparar(page, origen.rutaDescremar, {
      litros: "500", tkDescremada, tkCrema, cremaADespacho: true,
    });
  });

  await test.step("3 · Iniciar espera la segunda firma; con ella, inicia", async () => {
    await iniciarTrasLaFirma(page, preparado.codigo, origen.analisisId);
  });

  await test.step("4 · Producción registra las salidas viendo el aviso de la crema para despacho", async () => {
    await registrarSalidas(page, preparado.codigo, {
      ...preparado, tkDescremada, tkCrema,
      aviso: { campo: "Grasa crema (%)", fuera: "41", dentro: "42.00", texto: /fuera del rango/ },
    });
  });

  await test.step("5 · Calidad libera por separado descremada y crema", async () => {
    await liberarRamas(page, preparado.codigo, tkDescremada, tkCrema);
  });

  await test.step("6 · Producción expone la crema como despacho, no como mantequilla", async () => {
    await usarSesionArea(page, "e2e_produccion");
    await irA(page, "/produccion");
    await page.getByRole("button", { name: "Consultar disponibles" }).click();
    const tarjeta = page.locator("article").filter({ hasText: preparado.codigo }).filter({ hasText: tkCrema });
    await expect(tarjeta.getByRole("link", { name: "Preparar despacho" })).toBeVisible({ timeout: 20_000 });
    await expect(tarjeta.getByRole("link", { name: "Iniciar Mantequilla" })).toHaveCount(0);
  });

  await test.step("7 · Despacho arma, autoriza y ejecuta la hoja de carga de la crema", async () => {
    await usarSesionArea(page, "e2e_despacho");
    await irA(page, "/despacho");
    await page.getByRole("button", { name: "Nueva hoja de carga" }).click();
    await page.getByRole("region", { name: "Nueva hoja de carga" }).getByLabel("Cliente").selectOption({ index: 1 });
    const graneles = page.getByRole("group", { name: "Graneles liberados" });
    await graneles.getByRole("listitem").filter({ hasText: new RegExp(preparado.codigo) }).getByRole("checkbox").check();
    await page.getByRole("button", { name: "Revisar hoja" }).click();
    await trasGuardar(page, "/api/inventario/despachos/", async () => {
      await page.getByRole("button", { name: "Guardar hoja" }).click();
    });
    const tarjeta = page.locator("article").filter({ hasText: preparado.codigo });
    await expect(tarjeta).toBeVisible({ timeout: 20_000 });
    await trasGuardar(page, "/autorizar/", async () => {
      await tarjeta.getByRole("button", { name: "Autorizar" }).click();
    });
    await tarjeta.getByRole("button", { name: "Ejecutar salida" }).click();
    await trasGuardar(page, "/ejecutar/", async () => {
      await tarjeta.getByRole("button", { name: "Confirmar salida" }).click();
    });
    await expect(page.getByRole("region", { name: "Despachadas hoy" })).toContainText(preparado.codigo);
  });

  expect(erroresJs).toHaveLength(0);
});
```

Notas para el implementador:
- `campo()` lee la etiqueta por su texto; los campos del formulario y del cierre llevan la etiqueta como primer nodo de texto del `<label>` (patrón de `Campo`), así que `Litros a Tk02` se encuentra igual que antes.
- `Iniciar descremado` comparte nombre con nada más dentro de la tarjeta; «Preparar descremado» aparece como título del diálogo y como botón de `ConfirmarAccion`: el localizador `getByRole("button", …)` dentro del diálogo toma solo el botón.
- Si la región «Avisos del cierre» no se expone como `region` (una `section` con `aria-label` lo es), usa `dialogo.locator("section[aria-label='Avisos del cierre']")`.

- [ ] **Step 3: `rutas.ts`** — junto a `/produccion/evaporacion` y `/produccion/secado`: `{ ruta: "/produccion/descremado", nombre: "Producción · Descremado" },`.

- [ ] **Step 4: `README.md`** — en «Descremado con dos ramas», después del bloque de comandos, describe el recorrido: «Calidad analiza el silo de entrada **sin** la segunda firma → Producción entra por «Descremar» y prepara en el puesto (`/produccion/descremado`): reservas tomadas, «Iniciar descremado» deshabilitado con el motivo de la firma → la segunda firma (`e2e_calidad_firma`) lo habilita → inicia → registra las salidas viendo el aviso de grasa (`revisar-cierre/`) → Calidad libera cada rama». Agrega que una corrida preparada y abortada retiene la descremadora y los dos TK hasta que se cancela con «Cancelar preparación» (tarjeta o historial del puesto).

- [ ] **Step 5 (controlador): aceptación**
  - Reiniciar el backend (`runserver --noreload`) y `manage.py migrate`.
  - `cd backend && .venv\Scripts\python.exe manage.py preparar_circuito_descremado --aplicar` y `.venv\Scripts\python.exe manage.py crear_usuarios_flujo_e2e`.
  - Comprobar en `/produccion/descremado` que `des-01` está **Disponible** y que `Tk02`, `TkC2`, `Tk03`, `TkC3` aparecen como destinos (sin reservas ni bloqueo de Calidad de corridas anteriores). Si una corrida preparada de una corrida anterior los retiene, cancelarla desde el puesto; no tocar corridas ajenas.
  - `cd frontend && E2E_USUARIO=e2e_auditoria E2E_CLAVE=auditoria-e2e-ccaa E2E_CLAVE_AREAS=flujo-e2e-ccaa npx playwright test --project=flujo-descremado` → 3/3.
  - Auditoría de accesibilidad (`npm run auditoria`) sin reglas nuevas en `/produccion/descremado`.
  - Frontend: `npx tsc -b --pretty false`, `npx eslint .`, `npm test` sin errores.
  - Suite completa del backend: `cd backend && DJANGO_ENV=test ./.venv/Scripts/python.exe manage.py test --noinput` sin rojos.

- [ ] **Step 6: Commit**

```bash
git add frontend/e2e/ayudantes.ts frontend/e2e/flujo-descremado.spec.ts frontend/e2e/rutas.ts frontend/e2e/README.md
git commit -m "test(e2e): el descremado se recorre en su puesto, con la firma que habilita iniciar y los avisos de grasa"
```

---

## Autorrevisión contra la spec

| Spec | Tarea |
|---|---|
| §1 problema: 3 pasos en 3 pantallas; preparar+iniciar en un botón y dos llamadas; corrida `borrador` huérfana | 1 (preparar en una transacción, inicio separado), 2 (cancelar acepta heredadas), 6 (un puesto) |
| §1 «la pantalla ofrece lo que el servidor rechaza» (TK sin filtrar, análisis elegido en el cliente) | 1 (análisis del servidor; reglas de destino compartidas), 4 (`destinos_*` con la misma regla), 6 (`opciones-alta` sin máquinas ni destinos) |
| §1 «no hay regla que la pantalla pueda consultar» | 1 (`motivos_tipados_para_iniciar_descremacion`), 4 (servida en `puesto/`) |
| §1 permiso de la pantalla ≠ servidor | 5 (`puedeOperarDescremado`), 1-3 (403 de Secado en cada acción) |
| §1 límites físicos sin lugar; REGLAS §2 desactualizado | 3 |
| §2 decisiones: puesto propio, dos pasos, una función de inicio, una entrada, límites avisan, cancelar, permiso, documentación | 1, 2, 3, 4, 6 (Desviación 8 para la entrada desde el silo) |
| §3.1 estado por descremadora; terminales no ocupan; en curso manda | 4 (Desviación 10) |
| §3.1 `motivos_para_iniciar`, `resolver_en` tipado (`RESOLVER_CIP`, `RESOLVER_SILOS`) | 1 (función), 4 (servida; Desviación 6 para «análisis superado») |
| §3.1 `motivos_para_tomar`, `avisos` (aseo), `en_calidad` con TK | 4 |
| §3.1 `origenes` con el análisis que usará preparar y `motivo`; `destinos_*` con `libre_l` | 1 (`ultimo_analisis_confirmado`, `motivos_para_preparar_desde_silo`), 4 |
| §3.1 `corridas_de_hoy` sin huérfanos; decimales como texto; lectura Condensación/Calidad/admin | 4 |
| §3.2 preparar: validaciones, análisis del servidor, sugerencia, mismas funciones que el inicio, `EJ-DES-{pk}`, tres reservas, `borrador → preparacion`, todo o nada | 1 (Desviaciones 1, 2, 3) |
| §3.3 iniciar: función única, orden de comprobaciones, análisis vigente, reservas propias, `select_for_update` corrida → ejecución, 409, sin reservas nuevas | 1 |
| §3.3 un solo camino de inicio: `inicio_reservado_al_puesto` + mensaje exacto; pausar/reanudar siguen | 2 (Desviación 5) |
| §3.4 cancelar: motivo, solo `borrador`, `_deshacer_preparacion_descremacion` desde `transicionar_ejecucion`, `bloquear_para_cancelar`, respuesta | 2 (Desviación 9) |
| §3.5 límites: función pura, `revisar-cierre/` sin escribir, `cerrar` guarda después de `controles` del cliente y los lleva al evento; RPM fuera | 3 |
| §3.6 permisos en todos los caminos; `POST descremaciones/` 405; `QuerysetTenantMixin` + `FiltraConsultaMixin` | 1-3 (403), 2 (405; además `POST ejecuciones/`, Desviación 4), 4 (mixins; Desviación 11) |
| §3.7 lo que no cambia (`sugerir-balance`, balance, cierre, liberación por rama); `opciones-alta` pierde máquinas y destinos | sin cambios en 1-4; 6 (Desviación 18) |
| §4.1 tarjetas: una acción por estado, motivo con enlace solo si se puede entrar, cancelar con `ConfirmarAccion`, `en_calidad`, avisos ámbar | 5 (`accionDeDescremadora`, `corridaCancelable`), 6 (`TarjetaDescremadora`, `CancelarPreparacion`; Desviaciones 7, 12) |
| §4.2 formulario guiado sin selector de análisis ni código, etapa sola, `?silo=` preelegido, sugerencia, confirmación «Preparar descremado» | 6 (`PrepararDescremado`) |
| §4.3 cierre movido al puesto con avisos de `revisar-cierre/` y resumen | 6 (`CierreDescremado`) |
| §4.4 corridas de hoy sin «Cargar» + historial con filtros de servidor | 4 (filtros), 6 (`TablaConsulta`) |
| §4.5 acceso: módulo `produccion`, `puedeOperarDescremado` con prueba, Calidad consulta | 5, 6 |
| §4.1 «Lo que se retira»: sección y modales de `/procesos`, redirecciones, `Silos.tsx`, menú con alias, `rutaDeEtapa`/`RUTAS_POR_ETAPA`, atajo de `/produccion`, bandejas sin iniciar y con enlace, `crearDescremacion`/`crearDescremacionGuiada` | 2 (servidor deja de ofrecer `ejecucion`), 5 (`textoIniciarEnPuesto`, Desviación 16), 6 |
| §5 pruebas backend (todas las listadas, incluidas las cuatro que esperaban reservas al iniciar y `tests_destinos`) | 1 (preparar, iniciar, migración de las cuatro), 2 (transicionar, cancelar, 405), 3 (límites y dominio), 4 (puesto, historial), 6 (`tests_destinos`, `opciones-alta`) |
| §5 pruebas frontend (`accionDeDescremadora`, `corridaCancelable`, `puedeOperarDescremado`, `rutaDeEtapa`, menú) | 5, 6 |
| §5 E2E reescrito sobre el puesto (entrada por «Descremar», preparar, iniciar deshabilitado con la firma, Calidad completa el análisis, inicia, salidas con aviso, liberación por rama, tarjeta por el código del servidor); `rutas.ts`; README | 7 (Desviaciones 7, 20) |
| §6 riesgos: reservas al preparar → cancelar en el mismo cambio, tarjeta *Preparada* visible, destinos reservados no ofrecidos; heredadas `borrador` cancelables; usos a migrar | 1, 2, 4, 6; «Usos a migrar» |
| §7 fuera de alcance (Mantequilla, motor genérico, bloquear por grasa, RPM, avisos en `/calidad`, control horario) | respetado (Desviación 17; REGLAS §2 lo deja dicho) |
| §8 desviaciones de la spec | conservadas; las del plan quedan en la spec por la Task 4, Step 7 |
| `CLAUDE.md` «Descremado tiene puesto propio» junto al de Secado; `docs/REGLAS_DE_PLANTA.md` §2 | 6 (Step 9); 3 (Step 6) |

Tipos y nombres cruzados verificados: `ultimo_analisis_confirmado` (recepción); `RESOLVER_SILOS`, `ESTADOS_SILO_SIN_PRODUCTO`, `motivos_para_preparar_desde_silo`, `motivos_origen_descremacion`, `motivos_destino_descremacion`, `preparar_descremacion`, `crear_descremacion_guiada`, `motivos_tipados_para_iniciar_descremacion`, `motivos_para_iniciar_descremacion`, `iniciar_descremacion`, `MENSAJE_INICIO_DESCREMADO_EN_PUESTO`, `MENSAJES_INICIO_EN_PUESTO`, `inicio_reservado_al_puesto`, `cancelar_preparacion_descremacion`, `revisar_cierre_descremacion`, `estado_puesto_descremado`, `avisos_limites_descremacion` (backend) y `DescremadoraPuesto`, `CorridaDescremadora`, `PuestoDescremado`, `PreparacionDescremado`, `ValoresCierreDescremado`, `RevisionCierreDescremado`, `accionDeDescremadora`, `corridaCancelable`, `situacionDeCorrida`, `puedeOperarDescremado`, `textoIniciarEnPuesto`, `obtenerPuestoDescremado`, `prepararDescremado`, `iniciarDescremado`, `cancelarPreparacionDescremado`, `revisarCierreDescremado`, `buscarDescremaciones`, `obtenerDescremacion` (frontend) se usan con la misma firma en todas las tareas. Las etiquetas que lee el E2E («Preparar descremado», «Descremadora», «Litros de entrada», «TK de leche descremada», «TK de crema», «Destino de la crema», «Ruta de la crema», «Calcular sugerencia», «Descremada planificada (L)», «Crema planificada (L)», «Revisar y confirmar», «Iniciar descremado», «Registrar salidas y cerrar», «Registrar salidas», «Grasa leche descremada (%)», «Grasa crema (%)», «Avisos del cierre», «Revisar cierre», «Confirmar salidas y cerrar», «Corridas de hoy», «Actualizar») son las de los componentes de la Task 6.
