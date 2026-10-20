# OP-01 — Firmas de calidad y despacho

**Estado:** COMPLETADA EN LA RAMA · **prioridad:** P0 · **rama:** `codex/op-01-firmas-despacho`, head verificado `479624ae1783b3087cdab4f520ad1f889443214c` (commits `49282a5`, `a976283`, `8af89ca`, `479624a`), apilada sobre OP-00 · [PR borrador #7](https://github.com/FelipeCCAA/CCAA/pull/7), abierto y no fusionado a `DevelopMain` · **base local de pruebas:** PostgreSQL 17.10 aislado de OP-00; CI PostgreSQL 17.11.

Este expediente registra definición, implementación y validación de rama de OP-01. La autorización del usuario cubrió OP-01 después de revisar reglas y riesgos; no extiende la autorización a otros OP ni a producción. La implementación y sus verificaciones de rama concluyeron. Revisión/merge del PR, despliegue, UAT industrial y plan de aplicación a firmas históricas reales son actividades separadas y no se ejecutaron.

## Objetivo

Evitar que una aprobación de Calidad se reutilice para un lote distinto o para una hoja de despacho cuyo lote o disponibilidad ya no corresponden. Mantener inmutable la identidad del lote asociada a la aprobación. Un cambio semántico en análisis/muestra, especificación, documento, lote o control invalida la firma aunque los valores sigan conformes; una nota sin efecto y una escritura no-op no la invalidan. Al ejecutar la salida, volver a validar el origen físico vigente, el saldo y la muestra de silo cuando corresponda.

El proceso conserva la relación entre lote, evidencia, aprobación, hoja de carga y movimiento de salida. Una renovación crea una firma UUID nueva y exige reautorizar la hoja afectada.

## Alcance

- Vinculación de la aprobación al lote exacto y a la evidencia de Calidad.
- Invalidación y renovación tras cambios semánticos de evidencia.
- Revalidación al ejecutar el despacho de identidad del lote, autorización vigente, estado, ubicación/silo y saldo disponible.
- Permisos y estados que gobiernan firma, preparación, autorización y ejecución del despacho.
- Registro auditable del acto original, invalidación, nueva firma, reautorización y salida.

Fuera de alcance: cambios a otras oportunidades OP, ejecución de circuito industrial completo, pruebas de carga para 70 usuarios, despliegue, acceso a Supabase, uso de producción, bases reales o comandos destructivos. La validación automatizada deberá usar el clúster PostgreSQL 17 aislado de OP-00, con la misma identidad/configuración segura y su base desechable; no crear ni contratar instancias nuevas.

## Reglas adoptadas para implementar

1. La firma queda ligada a la identidad exacta del lote. Esa identidad no se puede cambiar ni reutilizar con otro lote.
2. Cambios semánticos de análisis/muestra, especificación, documento, lote o control invalidan la firma aunque el resultado siga conforme. Una nota libre sin efecto y una escritura no-op no la invalidan.
3. La firma histórica sin metadata nueva no se considera vigente automáticamente: exige nueva firma y reautorización. No hay autoaprobación ni backfill de estados productivos.
4. Cada firma o renovación lleva UUID nuevo y evidencia versionada. Reautorizar la hoja registra una nueva autorización. La auditoría inmutable conserva el acto original antes de invalidarlo.
5. En despacho se valida el origen físico actual al autorizar y se vuelve a validar al ejecutar. En los casos de granel que lo requieren, se valida la muestra de silo aplicable. Si origen, silo o estado cambió, se bloquea la salida hasta revisar y reautorizar.
6. Invalidar evidencia y cambiar el estado de aprobación ocurre en una operación atómica. La salida usa la misma foto de evidencia/material/origen que su autorización y un token all-or-nothing. Los reintentos no duplican movimientos.
7. Los cambios semánticos del catálogo toman exclusión; las lecturas de aprobaciones toman bloqueo compartido para permitir procesos independientes concurrentes.

La dirección técnica es aditiva: cuatro campos de firma en cada registro de aprobación existente y una foto JSON server-only en la hoja de despacho. El botón mínimo “Revisar y autorizar nuevamente” permite renovar la hoja sin pedir al operador recrearla.

## Alcance técnico y límites

| Área | Archivos y datos | Propósito |
|---|---|---|
| Evidencia y firma | [calidad/evidencia.py](../../backend/calidad/evidencia.py), [calidad/vigencia.py](../../backend/calidad/vigencia.py), [calidad/senales_vigencia.py](../../backend/calidad/senales_vigencia.py), [calidad/apps.py](../../backend/calidad/apps.py) | Snapshot determinista, versiones/UUID, comparación e invalidación transaccional; señales de borrado, registro de señales y bloqueos del catálogo. |
| Aprobaciones de Calidad | [calidad/models.py](../../backend/calidad/models.py): `Liberacion` para `produccion.Lote` y `LiberacionProceso` para `procesos.SalidaProceso` | Campos `firma_id`, `version_evidencia`, `version_firmada` y `evidencia_firmada` se agregan en ambos registros. El cambio de origen del sujeto se rechaza. |
| Despacho | [inventario/servicios.py](../../backend/inventario/servicios.py), [inventario/models.py](../../backend/inventario/models.py), [HojaDeCarga.tsx](../../frontend/src/pages/Despacho/HojaDeCarga.tsx) | Captura la foto JSON server-only en `Despacho.autorizacion_evidencia`; revalida pallet/ubicación o granel/silo en la ejecución; exige revisar y reautorizar si cambió. |
| Migraciones aditivas | [0007 de Calidad](../../backend/calidad/migrations/0007_firma_evidencia_versionada.py) y [0031 de Inventario](../../backend/inventario/migrations/0031_op01_autorizacion_evidencia.py) | Agregan cuatro campos a cada tabla de aprobación existente y un JSON a `inventario.Despacho`. No cambian modelos de flujo industrial ni hacen backfill de filas históricas. |
| Fuentes comparadas | `produccion.Lote`, `Analisis`, `ControlProceso`, `ControlProcesoLectura`, `RegistroEnvase`; `maestros.Producto`, `Equipo`, `Especificacion`, `DocumentoLiberacion`; `calidad.RegistroCalidad`, `RegistroEquipo`; `inocuidad.MonitoreoPPRO`, `PproLectura`; `recepcion.AnalisisSilo`, `MovimientoSilo`; `procesos.SalidaProceso`, `AutorizacionReproceso` | Solo los campos semánticos incluidos en la foto son evidencia. Una nota o un no-op no cambia la foto; cambios de evidencia relevantes sí invalidan. |
| Pruebas de la rama | [Calidad vigencia](../../backend/calidad/tests_op01_vigencia.py), [Calidad especificación](../../backend/calidad/tests_op01_especificacion.py), [concurrencia de firma](../../backend/calidad/tests_op01_concurrencia.py), [Inventario/Despacho](../../backend/inventario/tests_op01_despacho.py), [concurrencia de despacho](../../backend/inventario/tests_op01_concurrencia_despacho.py), [componente de hoja](../../frontend/tests/op01-hoja-carga.test.ts) | Local: 96/96 (Calidad 25, Inventario OP-01 29 y heredadas 42, seis carreras) más Producción 16/16. CI global: 1.586 backend, frontend 88/88; todo aprobado salvo 5 omisiones backend. |

Las escrituras normales usan `save()` dentro de una transacción y los borrados usan señales que invalidan. `QuerySet.update()`, `bulk_update()`, `bulk_create()` y SQL directo no ejecutan el `save()` del mixin; no se deben usar para modificar fuentes de evidencia sin una ruta explícita que aplique la misma invalidación atómica y tenga cobertura de regresión. Las notas libres excluidas de la foto y los no-op no invalidan; cualquier cambio real en los campos semánticos sí. Las cargas masivas previas no reciben una aprobación implícita.

OP-01 mantiene la identidad entre lote, firma, hoja y salida. No construye genealogía industrial de transformaciones, balances de proceso ni trazabilidad multi-etapa, que pertenecen a otros flujos/OP; tampoco reconstruye en bloque la vigencia histórica.

## Criterios de aceptación adoptados

- La aprobación queda vinculada a un lote y no habilita otro lote, aunque se reutilice el identificador de una hoja o petición.
- Ante cualquier cambio semántico enumerado arriba, la firma se invalida incluso si el resultado sigue conforme; la renovación asigna UUID nuevo y conserva actor, fecha y evidencia en auditoría. Notas sin efecto y no-op no invalidan.
- El despacho no se ejecuta con aprobación vencida/inválida, lote diferente, estado no apto, ubicación/silo no permitido o saldo insuficiente.
- La verificación se repite al ejecutar; no depende solo de los valores que existían cuando la hoja fue creada o autorizada.
- Dos ejecuciones concurrentes no producen doble despacho ni saldo negativo; la segunda obtiene un resultado consistente y comprensible.
- Los permisos del backend aplican en los endpoints de firma, autorización y ejecución; el cliente no puede estampar o modificar campos de firma directamente.
- La auditoría deja reconstruir cambios de evidencia, renovación, autorización y movimiento de salida.

Los criterios traducen las reglas adoptadas a comportamiento verificable. La matriz que sigue vincula cada grupo con las suites focales y la corrida global aprobada.

## Matriz de escenarios para el cierre integrado

| Escenario | Resultado esperado | Estado |
|---|---|---|
| Firmar y despachar con evidencia vigente | salida autorizada; trazabilidad lote-aprobación-despacho | PASS — `inventario/tests_op01_despacho.py`; CI global backend |
| Cambio semántico de evidencia conforme o no conforme; nota/no-op | cambio semántico invalida; nota/no-op conserva vigencia | PASS — `calidad/tests_op01_vigencia.py`, `tests_op01_especificacion.py`; CI global backend |
| Cambiar lote después de firmar o reusar aprobación en otro lote | rechazo; sin movimiento ni cambio de saldo | PASS — `calidad/tests_op01_vigencia.py::test_no_se_puede_reasignar_la_firma_a_otro_lote`, `inventario/tests_op01_despacho.py`; CI global backend |
| Cambiar ubicación/silo o disponibilidad después de autorizar | revalidación al ejecutar; bloquear si la condición dejó de ser apta | PASS — `inventario/tests_op01_despacho.py`; Quality/Inventario desk; CI global backend |
| Ejecutar dos veces o en carrera desde dos conexiones | como máximo una salida efectiva; consistencia de estados y saldos | PASS — concurrencia de Calidad/Despacho; seis carreras focales locales y CI global backend |
| Roles y permisos | backend aplica autorización a firma, autorización y ejecución | PASS — suites focales de Calidad/Inventario y CI global backend; revisión desk independiente de tres roles |
| Renovar aprobación | UUID nuevo, hoja reautorizada, auditoría conserva el acto previo | PASS — `calidad/tests_op01_vigencia.py`, `inventario/tests_op01_despacho.py`; CI global backend |
| Retirar vigencia, editar lote/origen, re-firmar y reautorizar | Calidad retira por POST/revisión; operador corrige; Calidad revisa y firma nueva; Bodega reautoriza antes de salida | Guardas automatizadas PASS (16 de Producción); secuencia completa revisada DESK, sin E2E |

### Evidencia de pruebas y CI final

En PostgreSQL 17.10 aislado con la identidad OP-00 se ejecutaron 18 métodos (7 de Calidad y 11 de Despacho) en 4.432 s. Django informó `failures=21`, correspondientes a 21 subcasos/assertions dentro de esos métodos; no hubo errores de infraestructura. Cuatro métodos pasaron; no significa que todos los reintentos pasaran. Se reprodujeron fallos en cinco grupos de Calidad (identidad de firma, cambio de valores conformes, editar/revertir, documento y especificación nueva) y en Despacho (ubicación/silo, reautorización y rollback). Registro local de corrida: `../op00-runtime/op01-baseline.log`.

La suite focal local final pasó 96/96 en 33.449 s (Calidad 25, Inventario OP-01 29, heredadas 42, con seis carreras); Producción pasó 16/16 en 33.657 s (3 nuevas y 13 heredadas). Las 57 regresiones nuevas se distribuyen entre Calidad (25), Inventario OP-01 (29) y Producción (3). Ruff, Django check y dry-run de migraciones pasaron. El clúster local PostgreSQL 17.10 dedicado se detuvo mediante `pg_ctl`, sesión exit 0 y sin `postmaster.pid`.

**CI final:** [run 39446921296](https://github.com/FelipeCCAA/CCAA/actions/runs/39446921296) terminó SUCCESS en el head `479624ae1783b3087cdab4f520ad1f889443214c`. [Backend job 118711171697](https://github.com/FelipeCCAA/CCAA/actions/runs/39446921296/job/118711171697): 1.586 tests en 516.121 s, `OK (skipped=5)`; 1.581 aprobadas, 5 omitidas, sin fallos/errores. PostgreSQL 17.11; Ruff, checks, dry-run y migraciones aprobaron. [Frontend job 118711171780](https://github.com/FelipeCCAA/CCAA/actions/runs/39446921296/job/118711171780): 88/88, lint, TypeScript y build aprobaron. [Production-config job 118711171493](https://github.com/FelipeCCAA/CCAA/actions/runs/39446921296/job/118711171493): SUCCESS con W021 preexistente. El aviso de import dinámico de `FormularioMaestro` también es preexistente y no bloqueó.

La CI anterior `39444907350` falló con 1.579 pruebas, 4 fallos, 3 errores y 5 omitidas; las causas se corrigieron en los cuatro commits finales. Dos CI intermedias se cancelaron y no cuentan como aprobadas. Un intento local previo con `--keepdb` se interrumpió cerca de 400 casos al vaciarse semilla de test por `TransactionTestCase`; no se modificaron fixtures productivos para ocultarlo. Las pruebas finales se hicieron en bases aisladas.

La API de Calidad incluye snapshot de identidad del lote, orden de bloqueo Lote→Salida, exigencia de nueva muestra al cambiar origen B y guardas para Especificación/Producto congelados. Walkthroughs independientes de Producción, Calidad y Bodega revisaron las secuencias de cada rol, sin base de datos; no son E2E ni certificación industrial. QA independiente de la delta `8af89ca..479624a` no encontró bloqueos técnicos.

### Walkthroughs de escritorio de Producción

Estos recorridos verifican que el flujo documentado sea entendible para el rol de Producción. No usan datos reales ni base de datos, y no sustituyen las suites automatizadas.

1. **Corrección de análisis o inocuidad:** Calidad retira aprobación mediante POST/revisión; el operador corrige el dato; Calidad revisa y firma de nuevo; Bodega reautoriza la hoja antes de salida. Una nota libre o un no-op no retiran vigencia.
2. **Lote LIBERADO/CONCESION con firma histórica sin metadata:** Calidad retira la aprobación; el operador corrige datos del lote u origen; Calidad revisa y emite una firma nueva; Bodega reautoriza la hoja y se realiza la salida. El operador puede retirar vigencia de análisis/inocuidad; el requisito estricto de metadata gobierna despacho, no ese acto de retiro.

Resultado del análisis de escritorio: los dos recorridos dejan explícito cuándo retirar vigencia, revisar y renovar aprobación, y qué condiciones bloquean el despacho. No se interactuó con la interfaz ni se cambiaron datos; por ello no se afirma que el flujo UI esté validado. La revisión de roles/contratos y las pruebas automatizadas siguen siendo evidencia necesaria.

### Walkthroughs independientes de Calidad y Bodega

1. **Calidad — edición que sigue conforme:** al cambiar un resultado firmado, la liberación pasa a `EN REV`; revertir el dato no reactiva la firma anterior. Calidad revisa y emite una nueva firma UUID. En cambio de silo A→B, `POST liberar B` con análisis de A devuelve `404`; con nueva muestra vigente de B, `POST liberar B` devuelve `200`. Una decisión de Calidad `RECHAZADO` o una ejecución de salida `CANCELADA` no habilitan la salida.
2. **Bodega — hoja antigua y cambio de origen:** una hoja antigua se rechaza; tras la nueva firma de Calidad se requiere reautorización de la hoja. Se ejecuta y un reintento no debe duplicar el movimiento. En cambio A→B, la validación de muestra y la reautorización son fronteras separadas.

Son recorridos de mesa independientes, sin interacción con el sistema ni cambios de datos. No verifican el circuito E2E completo ni genealogía industrial.

### Límite de presentación observado

Detalle de Lote en Producción puede presentar en verde una concesión legacy sin metadata de firma. Ese estado no habilita despacho: el endpoint de Despacho exige metadata vigente y rechaza la aprobación legacy. El flag `liberado` de Detalle de Lote funciona como guarda de edición, no como autorización de salida. Una pantalla ya abierta tampoco recibe automáticamente cambios remotos; después de un rechazo, la hoja de despacho sí instruye actualizar. Se registra como limitación UX no bloqueante, sin ampliar el alcance de OP-01. No se afirma certificación industrial ni consistencia visual en tiempo real.

## Referencias de diagnóstico

La revisión estática inicial señaló [calidad/serializers.py](../../backend/calidad/serializers.py#L158), [produccion/serializers.py](../../backend/produccion/serializers.py#L149) e [inventario/servicios.py](../../backend/inventario/servicios.py#L238) para revisar. Estos puntos son referencias diagnósticas y no sustituyen la ejecución de la suite. El diseño existente de [puestos de Bodega y Despacho](../superpowers/specs/2026-09-24-puestos-bodega-despacho-design.md) aporta contexto de estados, capacidades y ejecución.

## Secuencia y riesgos

1. OP-01 queda completada en la rama con CI global, regresión focal y revisión QA aprobadas.
2. Mantener revisión/merge/despliegue humanos y el plan de tratamiento de firmas históricas reales como actividades separadas.

Límites pendientes: el UX de Detalle de Lote puede mostrar verde para concesiones legacy sin metadata aunque Despacho las rechaza; `liberado` en esa vista es guarda de edición, no habilitación de salida. Las pantallas abiertas no reciben cambios remotos automáticamente; Hoja de Despacho indica actualizar tras rechazo. No se corrigió UX dentro de OP-01. No se ejecutaron circuito industrial completo, pruebas de carga para población de 70 usuarios ni restauración de backup; la población no equivale a concurrencia aprobada/certificada. OP-03 y el plan para firmas históricas reales quedan fuera de alcance. No crear genealogía industrial dentro de OP-01.

## Archivos y commits de entrega

Cuatro commits de implementación y regresión: `49282a5`, `a976283`, `8af89ca`, `479624a`. Se modificaron 35 archivos de código/pruebas/migraciones y estos tres documentos de seguimiento (38 en total). El [listado completo del PR #7](https://github.com/FelipeCCAA/CCAA/pull/7/files) es el manifiesto verificable; las áreas y tablas afectadas se describen arriba. El commit documental posterior no altera backend, frontend ni el workflow; la CI aprobada corresponde al código `479624a`.

## Seguimiento posterior — limpieza de CI, 20-10-2026

La [corrida 39449334479](https://github.com/FelipeCCAA/CCAA/actions/runs/39449334479), sobre el cierre documental `60bf962`, terminó **FAIL**. Backend completó 1.586 casos en 520,977 s con `OK (skipped=5)`; después, al eliminar `test_ccaa_ci`, PostgreSQL notificó dos sesiones conectadas y el job salió con código 1. Frontend y comprobación de configuración productiva terminaron aprobados. No hay diferencia de backend/workflow respecto de `479624a`; la CI aprobada anterior no convierte esta corrida en aprobada.

QA contrastó logs y código sin repetir pruebas ni modificar datos. Dos candidatos previos a OP-01, `procesos/tests_concurrencia_version.py:47` y `usuarios/tests_sesiones.py:199`, usan trabajadores y `close_old_connections()`, que puede mantener conexiones sanas recientes con `CONN_MAX_AGE=60`. No se ha demostrado que fueran las dos sesiones retenidas. Los nuevos hilos de OP-01 incluyen cierre incondicional y comprobación de terminación. Para atribuir la causa falta correlacionar PID de trabajadores con `pg_stat_activity` inmediatamente antes de la limpieza. Estado del seguimiento: **EN ANÁLISIS**, sin corrección implementada ni evidencia de un defecto productivo. Se conserva el resultado histórico aprobado de las comprobaciones funcionales y se registra la última CI fallida.
