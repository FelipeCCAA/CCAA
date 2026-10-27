# Backlog de mejoras OP

## Estado vigente — F01 silo reutilizado, 26-10-2026

**Implementación validada localmente y en CI global del código; revisión PR pendiente.** Rama `codex/f01-reuso-silo-recepcion`, código1786601, [PR21 borrador](https://github.com/FelipeCCAA/CCAA/pull/21) sobrePR20. Excepción sólo para recepción entera nueva posterior a vaciado físicamente probado y FIFO íntegro, sin salidas de proceso nuevas/ajustes/mezclas ni identidad ambigua. Se conserva historia y se protege el tipo de recepción ya descargada. No se backfillean consumos ni se inventa composición.

423/423 pruebas de Recepción/Estandarización,31 nuevas, sin fallos/omitidas,172,958s; API, Calidad, reintentos y tres carreras PostgreSQL; Ruff/esquema/diff aprobados. **CI global código1786601 APROBADA** en [run40374533419](https://github.com/FelipeCCAA/CCAA/actions/runs/40374533419): cuatro jobs SUCCESS;1.881 backend ejecutadas,1.876 aprobadas,5omitidas,530,676s, cero fallos/errores. Cierre documental posterior no cambia código; su CI propia es separada. [Contrato, límites, archivos y EXPLICADOR](docs/operacion/F01_REUSO_SILO.md). API local8209 aplica la rama para ensayo: comprobación visual elimina bloqueo histórico sin pulsar Transferido. No producción, despliegue, merge ni migraciones.

Siguiente paso operacional: verificar el nuevo vale VE6299-02 de1.000 L contra análisis reales del ensayo antes de transferir; sus valores manuales difieren. Silo5 quedó en5.000 L tras despacho de10.000 L realizado durante el trabajo, por lo que el vale antiguo15.000 L ya no tiene suficiente entera. No sobrescribir ni anular esos registros automáticamente. Persisten mezclas/F02, correcciones, históricos negativos, producto/especificación de polvo descremado, F03–F07, aceptación industrial y pendientes de carga OP09. SQL masivo/directo no está cubierto por la guarda save. Sin Supabase/logs.

---

## Estado vigente — corrección acotada F01/F02, 26-10-2026

Autorización del usuario: continuar el trabajo operacional. Rama `codex/f01-f02-saldos-genealogia` sobre `580f26c`/PR19; entrega para revisión, sin merge ni despliegue. **F01: corregido/validado localmente para casos soportados. F02: cadena nueva de origen único validada; cobertura global sigue PARCIAL.** [Contrato, alcance y evidencia](docs/operacion/F01-F02_VALIDACION.md).

Implementado: vínculo fuenteDescremado→vale→lote, ingreso productor verificable y conciliación, firma vigente, conteo físico/material único, Disponible limitado por libro/reservas, recorrido sin lotes ficticios y cantidades por tramo. Orígenes mezclados se bloquean aunque el cliente elija unID; no hay nueva regla de reparto ni reparación de historia. Correcciones OP02 mantienen su flujo y muestran advertencia de procedencia no atribuida. Actualizar vales recarga también los saldos; actualización automática entre usuarios y offline siguen fuera de alcance.

Verificación local:143 backend únicos,25 casos nuevos, cero omitidas/fallos/errores;111 frontend; carrera real entre dos vales, reintentos y rollback; lint/build/Ruff/esquema/diff aprobados. Un apoyo independiente revisó la implementación principal; coordinador revisó el lector y ejecutó comprobaciones en OP00 efímero. CI global9272269:1.850 ejecutadas,1fallo+1error+5omitidas por dos fixtures sin ingreso físico. Preparación ficticia corregida sin debilitar guardas/aserciones;31/31 locales posteriores aprobadas. [PR20 borrador](https://github.com/FelipeCCAA/CCAA/pull/20), nueva CI pendiente. No navegador, carga ni aprobación de planta.

**Cierre de CI4706bfb:** [run40335053758](https://github.com/FelipeCCAA/CCAA/actions/runs/40335053758) aprobado en los cuatro jobs. Backend1.850 ejecutadas:1.845 aprobadas,5omitidas, cero fallos/errores;418,469s. [Evidencia final independiente](docs/operacion/evidencias/f01-f02/final-ci/summary.json). El cierre documental posterior no cambia aplicación/pruebas; su CI adicional se informa por separado en el PR.

Pendientes: política de composición de TK mezclados y adiciones/retiros, conciliación autorizada de históricos, UAT/circuito por pantalla, costo de lectura en bandejas grandes, F03–F07 y pendientes OP09. F03 es siguiente según el plan, con validación industrial antes de introducir tolerancias. Preparación de sólo lectura confirma que ya existe grasa medida en análisis de silo y parámetros por lote, pero el cierre sólo exige kilos y admite humedad opcional: falta definir muestras representativas, composición de salidas y tratamiento de desviaciones/mazada. No implementado F03. Precondensado OPFLOW conserva500 L bloqueados por falta de especificaciónSILO. Sin producción ni Supabase.

---

## Estado vigente — precondensado, 2026-10-23 13:34 Chile

**PARCIAL, BLOQUEADO EN CALIDAD.** Usuario autorizó únicaOPFLOW-OP-PRECOND-01 de2000L y luego continuar e informar trabas, sin definir límites industriales. Se creó una sola OP; repetición `created=False`. Por UI: VE6296-02 (1426,60L Silo3+573,40L Tk02)→Silo5→OPF-PRE-01/Scheffers2→500L OP09-PRE-BASE. Nuevo análisis y segundo firmante. Calidad impide liberar porque falta especificación vigenteSILO; no se creó ni cambió una para forzar el resultado. Despacho no ofrece la salida; no hay liberación ni despacho de ella.

QA independiente:52modelos/299filas, movimientos17–21 conciliados por FIFO, una salida11 y un ingreso21, sin duplicados.307 inicios revisados hasta corte, mínimo medible10,007s/usuario, brechas históricas conservadas. Otras tres acciones posteriores sólo consulta/enfoque/cierre vacío. Ruff QA, diff-check y hashes de evidencia al cierre. Sin cambios de backend/frontend ni producción. Un fixture QA nuevo y15capturas en [expediente](docs/operacion/OP-09_PRECONDENSADO.md); misma rama/PR19borrador.

Próximo requisito: especificación de Calidad de silo validada para este producto/ruta/fecha; no inferirla de la especificaciónLOTE provisoria. Luego completar liberación y despacho sin repetir ingreso ni cierre. F01–F07, suero externo y consumo de rework mantienen pendientes anteriores. El corte15:14UTC siguiente es historial previo.

---

## Estado vigente OP-09 operacional — 2026-10-23, corte15:14 UTC

**PARCIAL; sin aprobación industrial global.** [Resultados y hallazgos](docs/operacion/OP-09_OPERACIONAL_RESULTADOS.md), [pantallas reales](docs/operacion/evidencias/opflow-ejecucion/PANTALLAS.md), PR19 en borrador, misma rama `codex/op09-operacional-trazabilidad`. El bloqueo inicial de descarga quedó resuelto y su informe se conserva como histórico.

Ejecutados por UI ficticia: recepción25000L, dos descremados, vale15000L, evaporación6000L→1500L, Secado, Envase y despacho500kg polvo/20kg mantequilla/42,50L crema, además de1000L leche cruda. Rework11kg aprobado y habilitado, sin consumo. Calidad y Bodega usan sus cuentas; sin ampliar permisos ni tocar producción. Sólo cuatro fixtures QA nuevos, documentación y evidencias, sin cambios de aplicación.

QA independiente: ledger52modelos/269filas, movimientos únicos y FIFO conciliado;257 inicios, mínimo medible10,007s por usuario, cero infracciones medibles. Brechas de diario28/33 conservadas. Ruff QA y diff-check aprobados; no se declaran suites no ejecutadas ni capacidad70usuarios.

Pendientes: **F01/F02 P1** disponible sobreestimado y genealogía de descremada/vale; **F03 P1** mantequilla acepta10,30kg grasa sin origen; **F04 P1** aplicabilidad/evidencia documental; **F05–F07 P2** pallet0,040un por unidad física, cronología Envase y ubicación histórica tras despacho. Soluciones sin implementar. Siguiente prueba: precondensado, pendiente autorización expresa para sólo OP ficticia2000L; no creada. Suero externo requiere orden/ingreso ficticio y escenario sin Compras; rework requiere ejecución compatible. Carga anterior mantiene pendientes25/50/70/sostenida; este ensayo no los resuelve.

---

Backlog de las diez oportunidades priorizadas: OP-00 a OP-05 completadas en sus ramas; OP-06 implementada y validada localmente en su rama; OP-07 implementada y validada localmente en su rama; OP-08 y OP-09 pendientes. No se calcula porcentaje de capacidad. OP-00 habilita pruebas reproducibles; las ramas no equivalen a producción. Corte 2026-10-21.

## OP-00 — Entorno reproducible de pruebas (WP001, P1 habilitante)

**Estado: COMPLETADA en la rama.** Sin dependencias técnicas. Alcance: PostgreSQL aislado para desarrollo/pruebas, validación de reset acotada y ejecución de `npm test` en CI. PR #6 sigue en borrador; no se ha fusionado ni desplegado.

**Expediente y evidencia:** [guía reproducible OP-00](docs/operacion/OP-00_VALIDACION.md). Commits de código/CI [`1ed4622`](https://github.com/FelipeCCAA/CCAA/commit/1ed4622a7aa8bc5eab0298beadbdc7f9141bc8b8) y código/guía [`4793e33`](https://github.com/FelipeCCAA/CCAA/commit/4793e33b909c2b2a0a29eaf565f2fe3c5711d95d); rama subida y [PR borrador #6](https://github.com/FelipeCCAA/CCAA/pull/6). La guía describe la reproducción canónica en servicio PostgreSQL efímero de CI y la validación local: clúster dedicado `../op00-runtime/pgdata`, PostgreSQL 17.10, rol `op00_test`, escucha `127.0.0.1:55439`, bases `op00_base` y `test_op00_base`; harness sin `.env` ni variables heredadas que comprueba `data_directory`, rol y puerto antes de Django. Virtualenv aislado y `npm ci` sin cambios a lockfiles/manifiestos. El esquema de pruebas se crea solo en la base nueva con migraciones existentes; incluye tablas sintéticas `Notificacion`, `auth_user`, maestros y caché `cache_ccaa`, sin estructura productiva ni migración nueva. CI utilizó PostgreSQL 17.11; la comprobación local fue con 17.10.

Cambios: [CI](.github/workflows/ci.yml) ejecuta `npm test`; [tests del reset](backend/usuarios/tests_reset_datos_operacionales.py) aíslan dos pruebas existentes con `override_settings` y agregan cuatro pruebas nuevas: rechazo por entorno en CI/staging/production aun con confirmación exacta, vista previa que conserva datos, PostgreSQL obligatorio y rechazo de base remota de desarrollo. La prueba de preview verifica conservación, no un borrado. El comando reset, settings y modelos/migraciones permanecen intactos. La suite focalizada conjunta de reset y Resumen pasó 14/14 en 6.920 s (exit 0), incluidos 1.000 kg fuera de ventana, 2.000 kg en la frontera inclusiva y 4.000 kg dentro; total esperado 6.000 kg. La base de test se destruyó al terminar. La validación/reset ejecutados afectaron exclusivamente la base desechable y conservaron maestros; esto documenta el entorno probado, no restringe el comando a un solo entorno permitido.

**Historia de regresión y resolución:** la ejecución backend local inicial reportó 1.528 pruebas, 3 fallos, 1 error y 5 omitidas en 846.339 s. Los cuatro fallos fueron `ResumenAPITests`, con fixtures de julio fuera de la ventana de 90 días al ejecutarse el 20-oct-2026. La primera CI [39428353622](https://github.com/FelipeCCAA/CCAA/actions/runs/39428353622) también falló en backend con los mismos casos: 1.528 pruebas, 3 fallos, 1 error y 5 omitidas en 499.477 s; frontend y production-config pasaron. Se corrigieron solo las pruebas, controlando fecha a 1-ago-2026, controlando `RESUMEN_DIAS=90` dentro de los tests y verificando frontera inclusiva del 3-may. La validación final y la CI siguiente pasaron, según evidencia abajo.

**Cierre COMPLETADA:** suite focalizada conjunta 14/14; backend global CI 1.529 pruebas, sin fallos ni errores (1.524 aprobadas, 5 omitidas); ejecución local de reset solo en base desechable conservó maestros; CI aprobó `npm test`, lint, tipos, build, producción-config, Ruff, Django checks, comprobación de migraciones y migración en base efímera; QA independiente del diff no encontró bloqueos. El merge requiere aprobación humana y es un hito aparte.

**CI final:** [run 39430749532](https://github.com/FelipeCCAA/CCAA/actions/runs/39430749532) terminó SUCCESS en el head `4793e33b909c2b2a0a29eaf565f2fe3c5711d95d`. [Backend](https://github.com/FelipeCCAA/CCAA/actions/runs/39430749532/job/118654869339): `Ran 1529 tests in 466.324s`, `OK (skipped=5)`; Ruff, checks y migraciones aprobados. [Frontend](https://github.com/FelipeCCAA/CCAA/actions/runs/39430749532/job/118654870026): 85/85, lint, TypeScript y build aprobados. [Production config](https://github.com/FelipeCCAA/CCAA/actions/runs/39430749532/job/118654869852): aprobado. PostgreSQL CI 17.11. El aviso HSTS preload `W021` y el aviso `INEFFECTIVE_DYNAMIC_IMPORT` de `FormularioMaestro` son preexistentes y no bloquearon la corrida; no se cambió la política ni el código asociado.

**Riesgos y límites:** no ejecutar contra producción ni datos reales. El resguardo depende de validar la instancia PostgreSQL antes de Django y de que el harness limpie variables heredadas. No se autoriza cambiar el alcance destructivo del reset. Población de 70 usuarios no equivale a concurrencia probada o certificada. No se autoriza prueba de carga ni recorrido operacional en OP-00.

## Catálogo OP-01 a OP-09

Los enlaces siguientes son referencias de requisitos y contexto existentes; no representan aceptación ni evidencia de implementación.

| ID | Prioridad | Tema y referencia existente | Estado / dependencia |
|---|---|---|---|
| OP-01 | P0 | Firma y despacho — [expediente OP-01](docs/operacion/OP-01_VALIDACION.md) y [puestos de bodega y despacho](docs/superpowers/specs/2026-09-24-puestos-bodega-despacho-design.md), WP002/003 | COMPLETADA EN LA RAMA; depende de OP-00. CI global aprobada; PR borrador no fusionado. |
| OP-02 | P0 | Balances y receta — [expediente de validación](docs/operacion/OP-02_VALIDACION.md), WP004 | COMPLETADA EN LA RAMA; CI global del código 7d36bbe aprobada, 1.635 backend (5 omitidas) y 91 frontend. Reglas aprobadas; sin merge ni despliegue. |
| OP-03 | P0 | Saldo, reservas y ubicación — [integración de inventario](docs/INTEGRACION_INVENTARIO.md), WP005/006 | COMPLETADA EN LA RAMA; CI global aprobada, PR #10 borrador sobre OP-02; sin merge/despliegue |
| OP-04 | P0 | Secado y FIFO — [flujo de secado Protomalt](docs/flujos/11-secado-protomalt.md) y [suero](docs/flujos/10-secado-suero.md), WP007/008 | COMPLETADA EN LA RAMA; CI 39637476601 SUCCESS, PR #11 borrador sobre OP-03; sin merge/despliegue |
| OP-05 | P0 | Mantequilla — [flujo productivo](docs/flujos/03-mantequilla.md), WP009 | COMPLETADA EN LA RAMA; CI 39647306726 SUCCESS, PR #12 borrador sobre OP-04; sin merge/despliegue |
| OP-06 | P0 | Identidad — [expediente OP-06](docs/operacion/OP-06_VALIDACION.md), WP013/014 | IMPLEMENTADA Y VALIDADA LOCALMENTE EN LA RAMA; frontend 5bdca62 y backend a62622c, seis reglas aprobadas, revisión/CI del PR separadas; sin merge/despliegue; depende de OP-00 |
| OP-07 | P1 | UUID, auditoría y exportaciones — [expediente OP-07](docs/operacion/OP-07_VALIDACION.md), WP011/015 | IMPLEMENTADA Y VALIDADA LOCALMENTE EN LA RAMA; código 3ad83f3, revisión/CI del PR separadas; depende de OP-00 |
| OP-08 | P1 | Envases, archivos y correo — [expediente OP-08](docs/operacion/OP-08_VALIDACION.md), WP010/012 | IMPLEMENTADA Y VALIDADA LOCALMENTE EN LA RAMA; código e592252; seis reglas aprobadas, CI general/almacenamiento en checks del PR; sin merge/despliegue. |
| OP-09 | P1 | Circuito de 70 usuarios y backup — [arquitectura de escalabilidad](docs/ARQUITECTURA_FLUJOS_BIZAGI_ESCALABILIDAD.md), [despliegue Docker y backup](docs/DESPLIEGUE_DOCKER.md) | PENDIENTE; depende de OP-01 a OP-08 y requiere aprobación específica de pruebas. 70 es población, no concurrencia aprobada/certificada. |

El roadmap previo del repositorio está en [plan incremental](docs/architecture/06-improvement-plan.md). Las prioridades OP reflejan el catálogo de este expediente y no sustituyen ni cierran aquel roadmap.

### OP-03 — saldo, reservas y ubicación

**Estado: COMPLETADA EN LA RAMA** `codex/op-03-saldo-reservas-ubicacion`. [PR #10 borrador](https://github.com/FelipeCCAA/CCAA/pull/10), apilado sobre OP-02 (#9); código/pruebas verificados `ef4cd15d6c65ae69b6713fc88e56c0bc3ecfd4ec`. Commits `6d41690`, `5b5c6c4`, `de920a4`, `548de88`, `ef4cd15`. El cierre posterior sólo modifica tres documentos. Sin merge, despliegue ni datos productivos.

Se implementaron las cinco reglas aprobadas: físico/reservado/libre por ubicación; respeto de reservas en origen/destino; traslado atómico e idempotente del mismo lote; cierre/cancelación de ejecución libera sólo sus pendientes; confirmación revalida stock, capacidad y Calidad sin escrituras parciales. No se creó endpoint de cancelación MRQ. Migración `0032` aditiva UUID nullable/único sin backfill; insumos conservan tres decimales y leche dos. Formularios conservan clave y bloquean edición ante resultado incierto; si se cierra/recarga, consultar historial antes de iniciar otro movimiento.

**Validación:** [CI 39624260452 SUCCESS](https://github.com/FelipeCCAA/CCAA/actions/runs/39624260452) en `ef4cd15`: 1.674 backend (1.669 aprobadas, cinco omitidas, cero fallos/errores) en 244,149 s; frontend 97/97, lint, tipos, build, configuración, Ruff y migraciones efímeras aprobados. Focal local 64/64 (39 nuevas), regresión heredada 58/58 y Chrome 5/5 con API simulada. Historial de fallos, correcciones, archivos, reproducción y límites en [expediente OP-03](docs/operacion/OP-03_VALIDACION.md).

Revisión independiente sin defectos concretos pendientes en el delta final. DESK de Recepción, Producción y Bodega; no UAT, carga de 70 usuarios, restauración de backup ni prueba con datos reales. Clúster local detenido y sin `postmaster.pid`. OP-04 continuó con validación y autorización posterior del usuario, documentadas abajo. La revisión/merge/despliegue son hitos separados; OP-05 a OP-09 no están implementadas.


### OP-04 — Secado y FIFO

**Estado: COMPLETADA EN LA RAMA** `codex/op-04-secado-fifo`, desde OP-03 `5fd3d89`. Código/pruebas `1e2098d89ffc422471b9aa247ccb0b82af82c4bc`; [PR #11 borrador](https://github.com/FelipeCCAA/CCAA/pull/11) sobre OP-03 #10. El cierre posterior sólo actualiza tres documentos. Seis reglas aprobadas: origen y retiro real, unidades explícitas, FIFO del servidor, excepción auditada, consumo atómico/idempotente y cierre trazable. Sin nueva migración, merge, despliegue ni inventario real.

**Evidencia:** [CI 39637476601 SUCCESS](https://github.com/FelipeCCAA/CCAA/actions/runs/39637476601) en `1e2098d`: 1.696 backend (1.691 aprobadas, cinco omitidas), 101/101 frontend, checks/lint/tipos/build/configuración/migración efímera aprobados. Local 68/68 en 158,219 s; Chrome 5/5 con API simulada en 51,7 s. Revisión independiente sin bloqueantes pendientes del delta final. [Expediente, archivos, fallos previos y límites](docs/operacion/OP-04_VALIDACION.md).

Correcciones de revisión: carrera de Calidad, orden de bloqueos, origen físico duplicado y retiro durante CIP. Medición kg declarada con referencia, sin integración de báscula ni conversión L/kg. Registros históricos no se autorreparan; preparación Protomalt no activada. Recorridos DESK de Recepción/Producción/Bodega, sin UAT, carga de 70 usuarios ni restauración. Clúster local detenido y sin postmaster.pid. OP-05 continuó con la aprobación posterior del usuario, según el cierre siguiente.


### OP-05 — Mantequilla

**COMPLETADA EN LA RAMA** `codex/op-05-mantequilla`, desde OP-04 `f00e39a`. Código/pruebas `85b5ad1b8d8134fe1bf97d722ae2ca0fe7b396ff`; [PR #12 borrador](https://github.com/FelipeCCAA/CCAA/pull/12) sobre OP-04 #11. Seis reglas aprobadas: origen explícito y retiro real, firma vigente, saldos/reservas/CIP, conversión con densidad identificada, balance exacto conservado sin mazada nueva y recuperación por UUID. Migración 0024 aditiva nullable sin backfill, sólo en pruebas. Sin producción, merge ni despliegue.

**CI final SUCCESS** [39647306726](https://github.com/FelipeCCAA/CCAA/actions/runs/39647306726): 1.719 backend (1.714 aprobadas, cinco omitidas), 103/103 frontend, estática/checks/migración efímera/lint/tipos/build/configuración aprobados. Local final limpio 34/34, Chrome 5/5 con API simulada. Revisión independiente sin bloqueantes pendientes de las correcciones verificadas. [Archivos, evidencias y fallos previos](docs/operacion/OP-05_VALIDACION.md). Cierre posterior sólo tres documentos y dos valores de fixtures Chrome, probados 5/5; código de funcionamiento y tests backend iguales al head con CI aprobada. Su CI adicional no se anticipa aprobada.

Históricos sin origen no se completan automáticamente. Revisar corridas abiertas antes de cualquier despliegue futuro. Sin UAT, carga de 70 usuarios ni restauración de backup; clúster local detenido y sin postmaster.pid al cierre de OP-05. OP-06 continuó con aprobación posterior del usuario, según el cierre siguiente.

### OP-06 — Identidad, permisos y sesiones

Seis reglas implementadas en `codex/op-06-identidad`, desde OP-05 `c21b1f3`; frontend `5bdca62`, backend `a62622c`. Acceso revalidado bajo bloqueo, contraseña temporal distinta antes de operar, promociones explícitas, delegación por área conservada, revocación transaccional en API/admin/grupos y perfil actualizado al abrir la interfaz. Sin nuevas migraciones, infraestructura o cambios industriales.

Evidencia local: focal 51/51, últimas guardas 2/2 y 1/1; corte final API/rendimiento 17/17; frontend 107/107, Chrome OP-06 7/7 y regresión OP-02 a OP-05 16/16. Ruff, checks, tipos/build y esquema sin cambios aprobados. Cortes solapados, no sumar como casos únicos. Revisión independiente de lectura sin bloqueantes nuevos en el commit revisado. [Archivos, fallos iniciales, reproducción y límites](docs/operacion/OP-06_VALIDACION.md). Los checks y el informe AVANCE del PR conservan la evidencia de CI del commit entregado.

Destino de revisión: PR borrador apilado sobre OP-05 #12; no fusionar directamente con DevelopMain. Clúster local OP-00 detenido, sin postmaster.pid. Sin producción, despliegue, UAT, prueba de carga de 70 usuarios o restauración de backup. OP-07 continuó tras aprobación expresa de sus seis reglas y autorización de implementación, según el cierre siguiente.

### OP-07 — Auditoría masiva y reportes confiables

Seis reglas implementadas en rama codex/op-07-auditoria-exportaciones desde OP-06 4dd3a94. Código/pruebas 3ad83f3: IDs/UUID conservados, helpers atómicos, caminos críticos de pallets/inventario/despacho/CIP/atribuciones/módulos/plan/compras auditados. Historia y secretos protegidos; reportes JSON/CSV/XLSX con texto seguro y tope técnico 1000, exceso rechazado sin truncar. Sin migraciones ni backfill.

Evidencia: integración 58/58 incluida concurrencia PostgreSQL y rollback parcial, historia API 12/12, frontend 111/111, Chrome simulado 2/2. Ruff, lint, tipos/build y ausencia de cambios de esquema aprobados. [Expediente, archivos y límites](docs/operacion/OP-07_VALIDACION.md). CI general y PR definitivo en checks/AVANCE, sin anticipar resultado. Revisión apilada sobre OP-06 #13, sin merge ni despliegue. Clúster local detenido. Próxima OP-08: diagnóstico/preparación; implementar requiere autorización propia.

## OP-08 — Envases, archivos y correo

IMPLEMENTADA Y VALIDADA LOCALMENTE EN LA RAMA `codex/op-08-envases-archivos-correo`, desde OP-07 `e2fb6de`; código/pruebas `e592252`. Seis reglas autorizadas: pedido exacto/UUID y cierre atómico; adjuntos existentes/autorizados/privados e integridad; correo distingue solicitud/aceptación/cambio y acota reintentos. Migración 0017 aditiva nullable sólo en pruebas, sin backfill. Configuración de volumen privado preparada, no aplicada.

Evidencias: integración 40/40, archivos/correo y regresiones 45/45 (solapadas), carrera adicional subida/borrado 1/1; frontend 111/111; Chrome 5/5 con API simulada, incluido lote sin embalajes. Ruff/checks/esquema/lint/tipos/build aprobados. Revisión independiente final sin bloqueantes concretos. [Expediente y límites](docs/operacion/OP-08_VALIDACION.md); CI general y almacenamiento efímero se informan en checks/AVANCE del PR, sin anticipar resultado. PR apilado sobre OP-07 #14. Dos apoyos, no 16 ejecuciones. Clúster local detenido. Sin producción, correo real, merge ni despliegue. Siguiente OP-09: diagnóstico/preparación; carga y restauración necesitan alcance/autorización propios.

## OP-09 — Circuitos completos, carga y restauración

AUTORIZADA Y EJECUTADA CON BLOQUEANTES, cierre en curso. Rama `codex/op-09-circuito-carga-respaldos`, base OP-08 `a564861e`; QA `6773958`. Sólo pruebas/fixtures/documentación; código de aplicación intacto. Un revisor reutilizado. [Expediente verificable](docs/operacion/OP-09_VALIDACION.md).

Circuitos reales principales de precondensado, descremado, mantequilla y suero alcanzados; polvo no completa Envasado por **H09-01 P1**: cambios normales del lote en etapas posteriores invalidan firma anterior, bandeja ofrece material que POST rechaza. Requiere decisión industrial/funcional antes de corregir. Auxiliar de mantequilla fallida sobre lote ya liberado, no toda suite verde. Concurrencia HTTP real 201/409 y replay tras respuesta perdida aprobados; regresión PostgreSQL 77/77. Respaldo coherente 130 tablas+adjunto privado restaurado y probado por API en destino nuevo; no RTO/RPO productivo.

Carga 10 usuarios/10 minutos aprobada; **25 abortado** a 244,726 s por siete respuestas perdidas, tres escrituras inciertas. Tras drenar, 451 UUID únicos y cero diferencias por ubicación; correspondencia exacta de tres claves cliente no persistida. 50/70 no ejecutado. Sostenida independiente a 10 abortada a 631,029/1.800 s por RAM del host 87%: 3.031 peticiones, cero errores, 223 nuevas UUID iguales en API/BD. No aprobada; 674 UUID finales y 36 ubicaciones conciliadas sin diferencias. Sin sobrescribir fallo anterior; ráfaga de intentos fallidos observó 45×401→429 con Retry-After, sin reset de cuota. CI final se informa por SHA en PR. PR #16 borrador apilado sobre OP-08 #15. No certificar capacidad máxima ni listo para planta.

Siguiente: validar corrección H09-01, mejorar observabilidad del generador y diagnosticar transporte en servidor de pruebas equivalente al despliegue previsto. Ninguna corrección productiva, merge o despliegue autorizados. Vista local 5209 y clúster dedicado conservados para revisión; no Supabase/logs.

## H09-01 — Firmas de polvo por etapa (corrección posterior a OP-09)

Usuario validó las seis reglas y autorizó implementación/pruebas/PR, sin producción ni despliegue. Rama `codex/h09-01-firmas-por-etapa`, base OP-09 `fc02030`, código/pruebas `124d56e`; [PR17 borrador](https://github.com/FelipeCCAA/CCAA/pull/17) sobre OP-09 #16. Firmas v2 por salida/etapa/antecedentes; avance normal no caduca Evaporación; corrección material retira firmas de dependencias reales y liberación final, conservando historia/saldos. Bandeja/POST/Despacho verifican vigencia; Calidad renueva explícitamente. V1 permanece estricta, sin backfill ni migración.

Circuito real en cortes completado hasta Inventario: H09-POLVO-195563, pallet500kg/PT-DISP; una firma de Evaporación y una de Secado, ambas versión0 y vigentes.18 regresiones nuevas incluidas en corte final88/88 sin omitidas. CI de implementación124d56e SUCCESS:1.825 backend (1.820 aprobadas, cinco omitidas), frontend/almacenamiento/configuración aprobados. Local completo previo1.823 (1.818 aprobadas, cinco omitidas), no sumar cortes solapados. Cierre posterior sólo documentación/evidencia QA, CI adicional se informa en PR sin anticiparlo. Frontend111/111, lint/tipos/build, Ruff/check/esquema aprobados. Un apoyo QA. [Expediente, fallos y límites](docs/operacion/H09-01_FIRMAS_POR_ETAPA.md). No certificar OP-09 global ni resolver carga/recursos fuera de esta corrección.


## OP-09 — Reejecución de carga autorizada, 2026-10-23

**PARCIAL; CARGA NO APROBADA.** Seis reglas y escalones autorizados. Rama `codex/op09-carga-revalidacion`, base H09-01 `5844447`; sólo QA/fixtures/documentación, sin aplicación, producción, despliegue ni contratación. [Expediente y evidencias](docs/operacion/OP-09_CARGA_REEJECUCION.md).

Clúster nuevo PG55469/API8229 con respaldo ficticio,70 cuentas y18 lotes propios. Docker Linux no disponible: diagnóstico con Django Windows, no capacidad productiva certificada. Calentamiento302,535s:1.406 solicitudes sin errores, aprobado. Escalón10 abortado a597,512/600s por RAM86%:2.831 solicitudes sin errores, p95lectura0,269s/escritura0,372s, **no aprobado**. No25/50/70 ni sostenida. Ingreso independiente4/70 accesos correctos, interrumpido por guardaRAM>85%; no certifica cuota70/IP.

Conciliación304 UUID=304 movimientos,36 ubicaciones/18 lotes sin diferencias;63 reenvíos sin segundo efecto. Diario4.260 intenciones=resultados, ninguna nueva trasSTOP. QA independiente verificó diario/IDs/p95 sin nuevos accesos a BD. Instrumentación mejorada;6/6 comprobaciones QA yRuff aprobados, sin repetir suites de aplicación.22 crudos con hashes y seis resúmenes seleccionados; sin sesiones/credenciales/dump/archivos privados. Nuevas sesiones cerradas y API/PG exclusivos detenidos, evidencias preservadas.

**Pendiente P1 H09-03:** entorno existente con recursos disponibles y servidor representativo. **H09-02 sigue abierto:** las tres respuestas inciertas a25 del ensayo anterior no se reprodujeron ni descartaron; no se alcanzó ese nivel. No afirmar máximo10, no reducir guardas ni cambiar políticas industriales. Próxima decisión: identificar recursos existentes sin costo o acordar liberación del equipo antes de repetir; no implementar cambios productivos ni contratar automáticamente.


## OP-09 — Operación por pantalla, corte parcial2026-10-23

**BLOQUEADA ANTES DE DESCARGAR; ningún circuito completo aprobado.** Rama `codex/op09-operacional-trazabilidad`, base9af5518. Usuario autorizó acción lógica cada10s por usuario, trazabilidad/capturas/cantidades/destinos; excluye Planificación, Compras y Mantenimiento. Nueva base vacía PG55479/opflow_circuito y API8209/web5209, sólo ficticios y maestros/órdenes/embalajes iniciales. Sin aplicación, producción, despliegue, contratación o Supabase/logs.

Hechos: recepción1/OPF-ENT-01 de25.000L, muestraM-OPF-ENT-01, decisión de e2e_calidad y destino Silo3 por e2e_recepcion; responsables distintos. **0 movimientos de silo**, aún `liberada`, no descargada. Timeout de interacciónCDP al pulsar Descargar (confirmación nativa previa al POST); pestaña bloqueada no recuperada mediante APIs documentadas. Sin POSTdescargar observado y sin cambio físico; memoria~57–65%, no guardaRAM. Verificación de sólo lectura preserva la misma recepción para retomar.

23 intervalos registrados mínimo10,007s; autoguardados/consultas no son actos operacionales. Se documentó corrección de metadatos del primer registrador (seq11–17=Calidad) y capturas007–009 inválidas para acreditar Calidad, sin reescribir crudos. Capturas010/011 verificadas, muestran aprobación y destino25k/Silo3. QA independiente confirma cantidades/estado/ritmo y rutas no ejecutadas. ExtractorREADONLY de52 modelos, Ruff aprobado; ninguna suite general repetida sin cambios de aplicación.

[Informe y pendientes](docs/operacion/OP-09_OPERACIONAL_PARCIAL.md). Se mantiene entorno local para revisión y consulta al usuario sobre confirmación pendiente; recuperar navegador antes de continuar. No saltar descarga medianteAPI/ORM, no fabricar lotes/pallets aprobados ni considerar cubiertas rutas pendientes con ensayos anteriores.
# Continuidad de Calidad — decisión posterior, 26-10-2026

**Implementada y validada en rama — cierre27-10-2026.** `codex/calidad-pendiente-continuidad`, base PR21/3b468bb, [PR22 borrador](https://github.com/FelipeCCAA/CCAA/pull/22). Código finalceb3c80: CI40392127340 aprobada,1.924 backend (1.919 aprobadas,5omitidas), cuatro jobs; frontend115/115, lint/build y Chrome6/6 simulado. Regresión local302/302 corresponde al corte anterior31fb6c0. Decisión humana: producción puede continuar con análisis/firmas pendientes; mantener adversos/inocuidad y liberación final. Bandera de servidor apagada por omisión, eventos/intervalos originales, estado de espera distinto de bloqueo y cuarentena final. Migración0039 aditiva sólo ensayada en OP00/OPFLOW ficticios; sin producción, merge o despliegue. No incluye reservas del vale ni reclasificación automática de bloqueos históricos. [Contrato, archivos, pruebas, límites y reversión](docs/operacion/CALIDAD_CONTINUIDAD_PENDIENTE.md). Próximo: revisión humana del PR y UAT de rutas con maestros definidos; carga OP09 sigue pendiente.
