# Backlog de mejoras OP

Backlog de las diez oportunidades priorizadas: OP-00, OP-01 y OP-02 completadas en sus ramas; OP-03 completada en su rama; OP-04 en validación; OP-05 a OP-09 pendientes. No se calcula porcentaje de capacidad. OP-00 habilita pruebas reproducibles; las ramas no equivalen a producción. Corte 2026-10-21.

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
| OP-04 | P0 | Secado y FIFO — [flujo de secado Protomalt](docs/flujos/11-secado-protomalt.md) y [suero](docs/flujos/10-secado-suero.md), WP007/008 | IMPLEMENTADA, EN VALIDACIÓN; seis reglas aprobadas. Rama codex/op-04-secado-fifo sobre OP-03; sin producción/despliegue |
| OP-05 | P0 | Mantequilla — [flujo productivo](docs/flujos/03-mantequilla.md), WP009 | PENDIENTE; depende de OP-03 |
| OP-06 | P0 | Identidad — [arquitectura actual](docs/architecture/03-architecture-current.md), WP013/014 | PENDIENTE; depende de OP-00 |
| OP-07 | P1 | UUID, auditoría y exportaciones — [auditoría](docs/architecture/04-architecture-problems.md), WP011/015 | PENDIENTE; depende de OP-00 |
| OP-08 | P1 | Envases, archivos y correo — [mapa del sistema](docs/architecture/01-system-map.md), WP010/012 | PENDIENTE; depende de OP-00 y sujeto a confirmar alcance |
| OP-09 | P1 | Circuito de 70 usuarios y backup — [arquitectura de escalabilidad](docs/ARQUITECTURA_FLUJOS_BIZAGI_ESCALABILIDAD.md), [despliegue Docker y backup](docs/DESPLIEGUE_DOCKER.md) | PENDIENTE; depende de OP-01 a OP-08 y requiere aprobación específica de pruebas. 70 es población, no concurrencia aprobada/certificada. |

El roadmap previo del repositorio está en [plan incremental](docs/architecture/06-improvement-plan.md). Las prioridades OP reflejan el catálogo de este expediente y no sustituyen ni cierran aquel roadmap.

### OP-03 — saldo, reservas y ubicación

**Estado: COMPLETADA EN LA RAMA** `codex/op-03-saldo-reservas-ubicacion`. [PR #10 borrador](https://github.com/FelipeCCAA/CCAA/pull/10), apilado sobre OP-02 (#9); código/pruebas verificados `ef4cd15d6c65ae69b6713fc88e56c0bc3ecfd4ec`. Commits `6d41690`, `5b5c6c4`, `de920a4`, `548de88`, `ef4cd15`. El cierre posterior sólo modifica tres documentos. Sin merge, despliegue ni datos productivos.

Se implementaron las cinco reglas aprobadas: físico/reservado/libre por ubicación; respeto de reservas en origen/destino; traslado atómico e idempotente del mismo lote; cierre/cancelación de ejecución libera sólo sus pendientes; confirmación revalida stock, capacidad y Calidad sin escrituras parciales. No se creó endpoint de cancelación MRQ. Migración `0032` aditiva UUID nullable/único sin backfill; insumos conservan tres decimales y leche dos. Formularios conservan clave y bloquean edición ante resultado incierto; si se cierra/recarga, consultar historial antes de iniciar otro movimiento.

**Validación:** [CI 39624260452 SUCCESS](https://github.com/FelipeCCAA/CCAA/actions/runs/39624260452) en `ef4cd15`: 1.674 backend (1.669 aprobadas, cinco omitidas, cero fallos/errores) en 244,149 s; frontend 97/97, lint, tipos, build, configuración, Ruff y migraciones efímeras aprobados. Focal local 64/64 (39 nuevas), regresión heredada 58/58 y Chrome 5/5 con API simulada. Historial de fallos, correcciones, archivos, reproducción y límites en [expediente OP-03](docs/operacion/OP-03_VALIDACION.md).

Revisión independiente sin defectos concretos pendientes en el delta final. DESK de Recepción, Producción y Bodega; no UAT, carga de 70 usuarios, restauración de backup ni prueba con datos reales. Clúster local detenido y sin `postmaster.pid`. OP-04 es la siguiente por dependencia: sólo diagnóstico/propuesta de reglas; implementar requiere autorización. La revisión/merge/despliegue son hitos separados; OP-04 a OP-09 no están implementadas.


### OP-04 — Secado y FIFO

**Estado: IMPLEMENTADA, EN VALIDACIÓN** en `codex/op-04-secado-fifo`, desde OP-03 `5fd3d89`. Seis reglas validadas y ejecución autorizada por el usuario. Expediente: [OP-04_VALIDACION.md](docs/operacion/OP-04_VALIDACION.md). Inicio/cierre recuperables por UUID; alimentación contrastada con retiro real; litros conservados y kg medidos con referencia; FIFO del servidor con excepción auditada; continuación con firma vigente, sin origen duplicado ni retiro durante CIP. Sin migración nueva.

Revisión independiente corrigió carrera de Calidad, orden de bloqueos, reutilización de retiro por entradas duplicadas y guarda CIP. Primera integración: 35 pruebas, 34 aprobadas y un error de fixture (orden de etapa ausente), corregido; segunda validación y CI pendientes. Frontend 101/101, lint, tipos/build aprobados; pantallas con API simulada en verificación final. No declarar aprobación global hasta recibir evidencia. Sin merge, despliegue ni inventario real. OP-05 siguiente para diagnóstico y reglas; no autorizada su implementación.
