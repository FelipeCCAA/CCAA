# OP-03 — Validación de saldo, reservas y ubicación

**Estado al 2026-10-21: COMPLETADA EN LA RAMA; VALIDADA MEDIANTE PRUEBAS.** Rama `codex/op-03-saldo-reservas-ubicacion`, derivada de `8d0ede7` de OP-02. Sin merge ni despliegue. Las pruebas se ejecutaron en entornos aislados con datos sintéticos; no hay ejecución con datos reales. El cierre de rama no certifica la operación industrial de toda la planta.

## Cierre y evidencia global

La [CI 39624260452](https://github.com/FelipeCCAA/CCAA/actions/runs/39624260452) terminó **SUCCESS** en `ef4cd15d6c65ae69b6713fc88e56c0bc3ecfd4ec`:

- [Backend](https://github.com/FelipeCCAA/CCAA/actions/runs/39624260452/job/119305430219): **1.674 pruebas en 244,149 s**, `OK (skipped=5)`: 1.669 aprobadas, cinco omitidas preexistentes, cero fallos y errores. Ruff, Django check, ausencia de deriva de modelos y migraciones sobre PostgreSQL 17.11 efímero aprobados.
- [Frontend](https://github.com/FelipeCCAA/CCAA/actions/runs/39624260452/job/119305430626): **97/97**, lint, TypeScript y build aprobados. Conserva aviso preexistente `INEFFECTIVE_DYNAMIC_IMPORT` de `FormularioMaestro`.
- [Configuración](https://github.com/FelipeCCAA/CCAA/actions/runs/39624260452/job/119305430618): check aislado aprobado; aviso preexistente HSTS `W021`. Este job no se conecta a producción.
- Local: focal **64/64** (39 nuevas) en 36,924 s, más regresión de los cuatro módulos heredados **58/58** en 45,798 s; bases limpias creadas/destruidas. Chrome **5/5** en 10,4 s con API simulada y frontend **97/97**. No equivale a E2E integrado con BD ni UAT.

La revisión técnica independiente de los cambios y de las correcciones de fixtures no encontró defectos concretos pendientes en el delta final revisado. Sus comprobaciones fueron estáticas; la ejecución de pruebas y CI corresponde a los resultados enlazados. Hubo DESK de Recepción, Producción y Bodega; no aceptación industrial.

El commit documental de cierre posterior modifica únicamente este expediente, `TASK_BACKLOG.md` y `PROGRESS.md`; el código y las pruebas permanecen iguales al head de CI verificado. Su CI separada puede estar pendiente al entregar y no se presenta como aprobada por anticipado. `DevelopMain` se verificó sin cambios en `d34df44ca30c402e9da34dc7b75f7652c2751fef`.

## Reglas aprobadas

1. Mostrar cantidades físicas, reservadas y libres por silo/ubicación.
2. Toda salida, consumo y traslado respeta las reservas del origen y la capacidad reservada del destino.
3. El traslado conserva el lote y se confirma de forma atómica una sola vez.
4. Al terminar o cancelar una operación/ejecución, liberar exclusivamente la reserva propia pendiente; conservar las cantidades ya consumidas. Esto no crea una nueva operación para cancelar una solicitud MRQ.
5. Al confirmar, volver a comprobar stock, capacidad y Calidad. Ante una condición inválida, explicar el motivo y no dejar escrituras parciales.

## Contratos de consulta y traslado

La consulta de ocupación de silos muestra los cinco datos relevantes: `litros` (cantidad física), `litros_reservados`, `litros_libres`, `litros_disponibles` y `capacidad_reservada`. La disponibilidad se limita a cero cuando hay motivos operacionales que impiden usar el silo. El detalle de respuestas se valida en la API y en los consumidores de recepción/inventario.

El traslado manual expone `operacion_id` como UUID obligatorio en la API. La clave hace idempotente la creación: repetir clave y misma carga devuelve el movimiento existente; reutilizarla con otra carga se rechaza. Las cantidades de insumos aceptan hasta tres decimales; la leche mantiene precisión de dos decimales. No se redondea silenciosamente. Se vuelve a leer estado, Calidad, ubicación, stock y reservas tras adquirir los bloqueos relevantes. El movimiento registra origen y destino sin cambiar la identidad del lote. Respuesta esperada: 201 al crear, 200 al repetir exactamente y 409 si la misma clave llega con otra carga o el conflicto de concurrencia impide aceptar el cambio.

La migración `0032` agrega a `MovimientoInventario` el campo UUID nullable con unicidad. Es aditiva, no retroescribe movimientos históricos y no contiene backfill. El despliegue/rollback de migraciones no se ha probado en producción y no está autorizado aquí.

## Matriz de aceptación

| Regla | Evidencia requerida | Estado al corte |
|---|---|---|
| Ocupación física, reservas, libre y capacidad destino | Respuesta API consistente con reservas activas y pantallas que consumen la consulta | Cubierta por la validación focal local 64/64; CI integral aprobada |
| No consumir reserva ajena ni superar stock/capacidad | Negativos por stock insuficiente, Calidad inválida y ubicación/bodega inactiva, relectura después de locks | Cubierta por 64 pruebas focales, incluyendo regresiones afectadas; CI integral aprobada |
| Traslado una vez, mismo lote, idempotencia | Crear, repetir misma carga, payload distinto, clave obligatoria y bloqueo concurrente | Cubierta en focal 64/64; CI integral aprobada |
| Finalizar/cancelar libera solo su reserva | Al terminar/cancelar operación o ejecución, conservar reserva de terceros y consumo parcial propio | Cubierta en focal 64/64; sin endpoint nuevo para cancelar MRQ |
| Confirmación vuelve a validar, sin parcialidad | Cambio concurrente de stock, Calidad, ubicación y capacidad; rollback completo | Cubierta en focal 64/64; CI integral aprobada |
| Interfaz refleja resultado y evita doble envío incierto | Carga, respuesta demorada/reintento y resultado idempotente visible | Frontend 97/97, lint/TypeScript/build pasan; Chrome 5/5 con API mock local |

## Evidencia y estado de las ejecuciones

- Baseline focal: 3/3 fallaron por diferencia de contrato HTTP (esperado 400, observado 201), en 1,314 s. Es antecedente del desarrollo, no resultado actual.
- Historial de desarrollo, ya superado por el focal final: la suite de 24 tuvo 23 aprobadas y un fallo de bodega inactiva en 16,096 s; la integrada de 88 registró dos fallos de fixtures heredados de Calidad y un error por `reserva_id` en 338,185 s. Los fixtures y la guarda se corrigieron; esos runs no cuentan como aprobación.
- Suite focal final local: 64/64 aprobadas en 36,924 s, exit 0, incluyendo 39 pruebas nuevas y regresiones afectadas; registro `op03-focal-cierre.log`. No sustituye la regresión global ni CI.
- Frontend actualizado: 97/97, seis pruebas nuevas; lint global, TypeScript y build terminaron con exit 0. Chrome: 5/5 en 10,4 s con API mock local, sin conexión a una base de datos ni API real.
- En revisión DESK se identificó entrega a un destino explícitamente inactivo. La guarda se agregó y se cubrió en la focal actual. Los DESK de Producción, Recepción y Bodega no equivalen a UAT ni a recorrido real.

## Límites y riesgos

No hacer merge, despliegue ni pruebas con bases productivas. La columna idempotente admite nulos para preservar compatibilidad histórica; los movimientos antiguos no se deduplican retroactivamente. No se afirma prueba de concurrencia global, UAT, restauración de backup ni carga de usuarios. El alcance de genealogía y las reglas de etapas siguientes quedan fuera de OP-03.

## Archivos y funciones afectados

El [manifiesto del PR #10](https://github.com/FelipeCCAA/CCAA/pull/10/files) contiene los 38 archivos de código, pruebas y configuración de pruebas, más este expediente y los dos documentos de seguimiento.

| Área | Archivos / funciones principales | Cambio |
|---|---|---|
| Silos y leche | `backend/recepcion/servicios.py`: `transferir_silo`, `despachar_leche`, `ajustar_silo`, `reversar_despacho_leche`; `views.py`: `ocupacion`, `sugerencia_silos`, descarga | Saldo libre, destino reservado/CIP, payload idempotente y bloqueo por UUID; consulta y sugerencia descuentan compromisos. Se conserva FIFO y la pareja de asientos del traslado. |
| Procesos | `backend/procesos/servicios.py`: `exigir_origen_disponible`, `exigir_destino_sin_reserva`, `consumir_reserva_origen`, `transicionar_ejecucion` y servicios especializados | Respeto de reservas ajenas, consumo de reserva propia y liberación de pendientes al cerrar/cancelar; orden catálogo → ejecución → silos. |
| Producción | `backend/produccion/servicios.py`: `abrir_lote_desde_vale`; `views.py`: `_vales_operativos`, `_crear_asignaciones` | Limita selección y confirmación al físico libre; agrupa cantidades solicitadas por silo antes de escribir. |
| Materiales | `backend/inventario/servicios.py`: `trasladar_existencia`, `entregar_reserva`, `entregar_solicitud_material`, `_bloquear_ubicaciones`; modelos/serializadores/vistas y migración `0032` | Traslado idempotente del mismo lote y entrega que consume exclusivamente su reserva; lotes → ubicaciones → bodegas → existencias, con raíces de todas las líneas MRQ bloqueadas previamente. |
| Retención OP-02 | `backend/estandarizacion/balance.py`, `bloqueos.py` | Consulta por lote de silos y reutilización de actos prefetched; conserva las reglas de balance existentes. |
| Pantallas | `Silos.tsx`, `FormularioDespachoLeche.tsx`, `PanelMovimiento.tsx`, `ConfirmarAccion.tsx`; servicios y helpers `disponibilidad-silo.ts`, `resultado-envio.ts` | Distingue físico/reservado/libre/disponible; refresco explícito sin caché; conserva la clave y bloquea edición ante resultado incierto. |
| Pruebas | Cuatro `tests_op03_*.py`, ocho fixtures heredados, `frontend/tests/op03-silos.test.ts`, `frontend/op03-ui/` y `.gitignore` | Regresiones de stock, reservas, Calidad, CIP, rollback, lotes, payload, tres carreras PostgreSQL y cinco recorridos de interfaz con API simulada. |

La revisión independiente identificó y se corrigió una ventana en la que destino/bodega podían desactivarse tras validar una entrega. La nueva carrera verifica mediante `pg_blocking_pids` que el UPDATE de otra conexión espera desde la validación hasta el commit externo. También se corrigió la sugerencia FIFO que aún ofrecía volumen físico en lugar de libre. La revisión estática final no identificó una nueva inversión entre entrega directa, MRQ y traslado; no es una certificación de ausencia de deadlocks en todo el ERP.

## Reproducción

En una instancia PostgreSQL efímera de desarrollo/CI con configuración aislada (guía OP-00), ejecutar desde `backend`:

```sh
python manage.py check
python manage.py makemigrations --check --dry-run
python manage.py migrate --noinput
python manage.py test --verbosity 1
```

La focal local se ejecuta con las cuatro suites OP-03 más `recepcion.tests_movimientos_operacionales`, `recepcion.tests_fifo`, `inventario.tests.LibroInventarioTests.test_entrega_exige_reserva_y_no_deja_stock_negativo` y `produccion.tests_lote_desde_vale`. El harness OP-00 verifica servidor, rol, puerto y carpeta antes de crear/destruir la base sintética; no lee `.env`. No usar una base que contenga datos reales.

Desde `frontend`, ejecutar `npm test`, `npm run lint`, `npm run build` y, con Chrome instalado, `npx playwright test --config op03-ui/playwright.config.ts`. La configuración abre Vite en `127.0.0.1:5193`, intercepta API y bloquea tráfico externo; el servidor se cierra al finalizar. No habilita un despliegue.

## Límites operacionales adicionales

Los operadores de Recepción, Producción y Bodega hicieron revisión de escritorio; los recorridos Chrome usan API simulada. No hubo aceptación de operadores humanos ni UAT industrial. La clave de reintento del formulario vive en memoria: cerrar/recargar puede perderla, por lo que debe consultarse el historial antes de iniciar otra operación si el resultado fue incierto. La interfaz advierte que cerrar no anula el movimiento.

No se cambia receta, rendimiento, tolerancia industrial ni las reglas de firma OP-01 o balance OP-02. No se autorreparan reservas/historia previas. Revertir código tras uso real debe conservar la columna de claves y el historial de movimientos, no borrarlos para permitir reintentos nuevos. La migración sólo fue aplicada en bases sintéticas.

## Próximo paso

Revisión humana del PR #10, apilado sobre OP-02 (#9). No fusionar ni desplegar sin autorización. OP-04 queda lista para diagnóstico y propuesta de reglas de secado/FIFO; no se autoriza su implementación. No se han ejecutado UAT, carga, restauración de backup ni pruebas con datos productivos.

## Rama, revisión e infraestructura

[PR #10 borrador](https://github.com/FelipeCCAA/CCAA/pull/10), base `codex/op-02-balance-correcciones` (PR #9). Commits de implementación `6d41690`, `5b5c6c4`, `de920a4`; adecuación de pruebas `548de88` y `ef4cd15`. La focal ampliada se inició sobre `5b5c6c4`; `de920a4` sólo hace explícito `order_by("pk")` al bloquear los dos silos y está validado en CI integral. No se ha fusionado con `DevelopMain`.

El clúster local `../op00-runtime/pgdata`, PostgreSQL 17.10 en `127.0.0.1:55439`, se detuvo al terminar todas las validaciones locales (exit 0, `postmaster.pid` ausente). La base de test se destruyó al terminar; los servidores Vite de prueba finalizaron y el puerto 5193 quedó sin listener según el harness. No se contrataron recursos, solicitaron credenciales nuevas ni conectó a producción.

## Regresión global: incidencias detectadas

La primera CI [39621601886](https://github.com/FelipeCCAA/CCAA/actions/runs/39621601886), código `6d41690`, terminó con backend en fallo: 1.672 pruebas en 368,431 s, 18 fallos, 16 errores y cinco omitidas. Frontend y comprobación de configuración pasaron. Los fallos de Producción/Planificación revelaron fixtures que asignaban leche sin muestra vigente o abrían un vale sin ingreso físico al destino; los errores posteriores fueron consecuencia de esas aperturas/asignaciones rechazadas. No se considera una aprobación ni se relajan las guardas para hacer pasar las pruebas. Se adecuaron únicamente los cuatro fixtures heredados afectados, conservando sus verificaciones de consumo, trazabilidad, idempotencia y ausencia de movimientos parciales.

La segunda CI [39622543472](https://github.com/FelipeCCAA/CCAA/actions/runs/39622543472), código `de920a4`, repitió esos fallos heredados: 1.674 pruebas, 248,958 s, 18 fallos, 16 errores y cinco omitidas. Incluyó ya los dos casos focales agregados; no aprobó la regresión global. La revisión independiente del siguiente commit de fixtures detectó importación incorrecta y contadores que confundían ingresos de preparación con salidas. La ejecución local de transición registró 31 casos con un error de importación y un fallo de contador (26,616 s); no es aprobación. Se corrigieron en `ef4cd15`, conservando las recepciones futuras ya registradas antes del POST retrospectivo y comprobando el asiento de salida concreto tras un rechazo.

La validación focal de esos cuatro módulos heredados pasó finalmente **58/58**, 45,798 s, exit 0, base limpia creada y destruida; log `op03-regresion-fixtures-final.log`. La revisión independiente de ese delta no encontró nuevos defectos concretos y fue estática, sin ejecución propia. Código funcional congelado desde `de920a4`; `548de88` y `ef4cd15` sólo cambian pruebas.

La tercera CI [39623653274](https://github.com/FelipeCCAA/CCAA/actions/runs/39623653274), commit de fixtures `548de88`, tuvo los mismos dos defectos detectados por la revisión independiente y la corrida local: 1.647 casos en 238,507 s, un fallo de contador, un error de importación y cinco omitidos. La cifra menor se debe al módulo que no cargó; no se eliminó ni omitió deliberadamente ninguno de sus casos. Esa corrida también permanece como antecedente fallido.
