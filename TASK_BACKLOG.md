# Backlog de mejoras OP

Backlog de las diez oportunidades priorizadas: OP-00 completada en la rama y OP-01 a OP-09 pendientes. OP-00 prepara pruebas reproducibles; no autoriza trabajo industrial, operación real ni carga concurrente. Corte 2026-10-20.

## OP-00 — Entorno reproducible de pruebas (WP001, P1 habilitante)

**Estado: COMPLETADA en la rama.** Sin dependencias técnicas. Alcance: PostgreSQL aislado para desarrollo/pruebas, validación de reset acotada y ejecución de `npm test` en CI. PR #6 sigue en borrador; no se ha fusionado ni desplegado.

**Expediente y evidencia:** [guía reproducible OP-00](docs/operacion/OP-00_VALIDACION.md). Commits de código/CI [`1ed4622`](https://github.com/FelipeCCAA/CCAA/commit/1ed4622a7aa8bc5eab0298beadbdc7f9141bc8b8) y código/guía [`4793e33`](https://github.com/FelipeCCAA/CCAA/commit/4793e33b909c2b2a0a29eaf565f2fe3c5711d95d); rama subida y [PR borrador #6](https://github.com/FelipeCCAA/CCAA/pull/6). La guía describe la reproducción canónica en servicio PostgreSQL efímero de CI y la validación local: clúster dedicado `../op00-runtime/pgdata`, PostgreSQL 17.10, rol `op00_test`, escucha `127.0.0.1:55439`, bases `op00_base` y `test_op00_base`; harness sin `.env` ni variables heredadas que comprueba `data_directory`, rol y puerto antes de Django. Virtualenv aislado y `npm ci` sin cambios a lockfiles/manifiestos. El esquema de pruebas se crea solo en la base nueva con migraciones existentes; incluye tablas sintéticas `Notificacion`, `auth_user`, maestros y caché `cache_ccaa`, sin estructura productiva ni migración nueva. CI utilizó PostgreSQL 17.11; la comprobación local fue con 17.10.

Cambios: [CI](.github/workflows/ci.yml) ejecuta `npm test`; [tests del reset](backend/usuarios/tests_reset_datos_operacionales.py) aíslan dos pruebas existentes con `override_settings` y agregan cuatro pruebas nuevas: rechazo por entorno en CI/staging/production aun con confirmación exacta, vista previa que conserva datos, PostgreSQL obligatorio y rechazo de base remota de desarrollo. La prueba de preview verifica conservación, no un borrado. El comando reset, settings y modelos/migraciones permanecen intactos. La suite focalizada conjunta de reset y Resumen pasó 14/14 en 6.920 s (exit 0), incluidos 1.000 kg fuera de ventana, 2.000 kg en la frontera inclusiva y 4.000 kg dentro; total esperado 6.000 kg. La base de test se destruyó al terminar. La validación/reset ejecutados afectaron exclusivamente la base desechable y conservaron maestros; esto documenta el entorno probado, no restringe el comando a un solo entorno permitido.

**Historia de regresión y resolución:** la ejecución backend local inicial reportó 1.528 pruebas, 3 fallos, 1 error y 5 omitidas en 846.339 s. Los cuatro fallos fueron `ResumenAPITests`, con fixtures de julio fuera de la ventana de 90 días al ejecutarse el 20-oct-2026. La primera CI [39428353622](https://github.com/FelipeCCAA/CCAA/actions/runs/39428353622) también falló en backend con los mismos casos: 1.528 pruebas, 3 fallos, 1 error y 5 omitidas en 499.477 s; frontend y production-config pasaron. Se corrigieron solo las pruebas, controlando fecha a 1-ago-2026, controlando `RESUMEN_DIAS=90` dentro de los tests y verificando frontera inclusiva del 3-may. La validación final y la CI siguiente pasaron, según evidencia abajo.

**Cierre COMPLETADA:** suite focalizada conjunta 14/14; backend global CI 1.529 pruebas, sin fallos ni errores (1.524 aprobadas, 5 omitidas); ejecución local de reset solo en base desechable conservó maestros; CI aprobó `npm test`, lint, tipos, build, producción-config, Ruff, Django checks, comprobación de migraciones y migración en base efímera; QA independiente del diff no encontró bloqueos. El merge requiere aprobación humana y es un hito aparte.

**CI final:** [run 39430749532](https://github.com/FelipeCCAA/CCAA/actions/runs/39430749532) terminó SUCCESS en el head `4793e33b909c2b2a0a29eaf565f2fe3c5711d95d`. [Backend](https://github.com/FelipeCCAA/CCAA/actions/runs/39430749532/job/118654869339): `Ran 1529 tests in 466.324s`, `OK (skipped=5)`; Ruff, checks y migraciones aprobados. [Frontend](https://github.com/FelipeCCAA/CCAA/actions/runs/39430749532/job/118654870026): 85/85, lint, TypeScript y build aprobados. [Production config](https://github.com/FelipeCCAA/CCAA/actions/runs/39430749532/job/118654869852): aprobado. PostgreSQL CI 17.11. El aviso HSTS preload `W021` y el aviso `INEFFECTIVE_DYNAMIC_IMPORT` de `FormularioMaestro` son preexistentes y no bloquearon la corrida; no se cambió la política ni el código asociado.

**Riesgos y límites:** no ejecutar contra producción ni datos reales. El resguardo depende de validar la instancia PostgreSQL antes de Django y de que el harness limpie variables heredadas. No se autoriza cambiar el alcance destructivo del reset. Población de 70 usuarios no equivale a concurrencia probada o certificada. No se autoriza prueba de carga ni recorrido operacional en OP-00.

## OP-01 a OP-09 — pendientes

Los enlaces siguientes son referencias de requisitos y contexto existentes; no representan aceptación ni evidencia de implementación.

| ID | Prioridad | Tema y referencia existente | Estado / dependencia |
|---|---|---|---|
| OP-01 | P0 | Firma y despacho — [puestos de bodega y despacho](docs/superpowers/specs/2026-09-24-puestos-bodega-despacho-design.md), WP002/003 | PENDIENTE; depende de OP-00 |
| OP-02 | P0 | Balances y receta — [servicios de estandarización](backend/estandarizacion/servicios.py), WP004 | PENDIENTE; depende de OP-00 |
| OP-03 | P0 | Saldo, reservas y ubicación — [integración de inventario](docs/INTEGRACION_INVENTARIO.md), WP005/006 | PENDIENTE; depende de OP-01 y OP-02 |
| OP-04 | P0 | Secado y FIFO — [flujo de secado Protomalt](docs/flujos/11-secado-protomalt.md) y [suero](docs/flujos/10-secado-suero.md), WP007/008 | PENDIENTE; depende de OP-03 |
| OP-05 | P0 | Mantequilla — [flujo productivo](docs/flujos/03-mantequilla.md), WP009 | PENDIENTE; depende de OP-03 |
| OP-06 | P0 | Identidad — [arquitectura actual](docs/architecture/03-architecture-current.md), WP013/014 | PENDIENTE; depende de OP-00 |
| OP-07 | P1 | UUID, auditoría y exportaciones — [auditoría](docs/architecture/04-architecture-problems.md), WP011/015 | PENDIENTE; depende de OP-00 |
| OP-08 | P1 | Envases, archivos y correo — [mapa del sistema](docs/architecture/01-system-map.md), WP010/012 | PENDIENTE; depende de OP-00 y sujeto a confirmar alcance |
| OP-09 | P1 | Circuito de 70 usuarios y backup — [arquitectura de escalabilidad](docs/ARQUITECTURA_FLUJOS_BIZAGI_ESCALABILIDAD.md), [despliegue Docker y backup](docs/DESPLIEGUE_DOCKER.md) | PENDIENTE; depende de OP-01 a OP-08 y requiere aprobación específica de pruebas. 70 es población, no concurrencia aprobada/certificada. |

El roadmap previo del repositorio está en [plan incremental](docs/architecture/06-improvement-plan.md). Las prioridades OP reflejan el catálogo de este expediente y no sustituyen ni cierran aquel roadmap.

### Preparación de OP-01 (sin implementación autorizada)

Preparación estática de OP-01 lista; implementación aún no autorizada. Objetivo por validar: impedir que una aprobación firmada se reutilice para otro lote; mantener inmutable la identidad del lote asociado a la firma y definir la vigencia de la aprobación cuando cambie la evidencia, permitiendo renovarla según la regla que acuerden Calidad y Bodega. Revalidar ubicación/silo al ejecutar el despacho. La QA de diagnóstico estático señaló [calidad/serializers.py](backend/calidad/serializers.py#L158), [produccion/serializers.py](backend/produccion/serializers.py#L149) e [inventario/servicios.py](backend/inventario/servicios.py#L238) como zonas a revisar al iniciar OP-01; son referencias diagnósticas, no hallazgos validados ni pruebas.

Antes de implementar, Calidad debe definir qué ediciones invalidan firma y cuándo se requiere refirmar; Calidad y Bodega deben acordar estados y ubicaciones aptos, y qué hojas/documentos existentes están autorizados. Diseñar después pruebas de firmar–editar–despachar, cambio de lote, carrera con dos conexiones y permisos por rol. Estas pruebas todavía no se han ejecutado; OP-01 permanece pendiente y requiere autorización independiente para su implementación.
