# Progreso del expediente OP

## AVANCE vigente — F01/F02, 26-10-2026

Usuario autorizó continuar las correcciones operacionales. Primera entrega acotada: rama `codex/f01-f02-saldos-genealogia` desde `580f26c`/PR19. Nuevas transferencias conservan salida real de Descremado→vale→lote cuando existe fuente única, ingreso productor inequívoco y saldo conciliado. No hay segundo descuento físico ni backfill. Varias fuentes, ingreso ajeno o composición no demostrable se bloquean; no se inventa FIFO/prorrateo. El libro físico libre limita Disponibles; Estandarización muestra origen/bloqueo y actualiza catálogo junto a vales. Genealogía atraviesa salidas sin lote y muestra cantidades por tramo; conserva el acto de Calidad del vale. Las correcciones físicas OP02 se advierten como composición aún no atribuida.

**Pruebas locales finales:**143 backend con identidades únicas, cero omitidas/fallos/errores,78,702s;25 casos nuevos, incluida carrera PostgreSQL observada con dos conexiones esperando el mismo origen (uno confirma6.000 L, otro rechaza; quedan3.150,08 L). Frontend111/111, lint y build con TypeScript; Ruff backend, esquema sin cambios y diff-check aprobados. Pruebas y fallos intermedios preservados. Un coordinador y un apoyo; revisión estática independiente sin nuevo bloqueante material en el alcance. [Expediente y EXPLICADOR de siete partes](docs/operacion/F01-F02_VALIDACION.md), [resumen y hashes](docs/operacion/evidencias/f01-f02/summary.json).

**Seguimiento CI:** implementación9272269/40331871048:1.850 backend ejecutadas,1fallo+1error+5omitidas; otros tres jobs aprobados. Dos fixtures de Descremado esperaban disponibles sin ingreso físico; se agregó sólo su preparación ficticia, sin modificar guardas ni aserciones.31/31 locales posteriores aprobadas,14,905s, Ruff/diff aprobados. Evidencia separada en `ci-followup/`; [PR20 borrador](https://github.com/FelipeCCAA/CCAA/pull/20), nueva CI pendiente.

**CI final4706bfb aprobada:** [run40335053758](https://github.com/FelipeCCAA/CCAA/actions/runs/40335053758), cuatro jobs SUCCESS. Backend1.850 ejecutadas en418,469s:1.845 aprobadas,5omitidas, cero fallos/errores. Frontend, almacenamiento privado y configuración aprobados. [Prueba final](docs/operacion/evidencias/f01-f02/final-ci/summary.json), separada de los fallos y cortes locales. Código de aplicación9272269, fixtures4dcc171; cierre posterior sólo documental, su CI propia no se declara anticipadamente. PostgreSQL OP00 detenido y evidencias/versiones verificadas por hash.

**Estado: validado localmente y en CI global para origen único; F02 parcial.** Falta composición de mezclas/correcciones, conciliación de históricos, repetición por navegador, carga y aceptación industrial. No migraciones, producción, despliegues, contratos ni Supabase; no se alteró el ensayo OPFLOW. Próxima tarea del plan: F03 balance graso, preparación de sólo lectura completada; se identificaron campos existentes de análisis, ausencia del balance de composición en cierre y necesidad de definir muestras/mediciones, tolerancias y tratamiento de mazada/desviaciones con planta. No implementado F03 ni inventadas reglas industriales.

---

## AVANCE vigente — precondensado, 2026-10-23 13:34 Chile

**PARCIAL:** únicaOP2000L autorizada creada, valeVE6296-02 liberado por Calidad y loteOPF-PRE-01 evaporado de2000L a500L ficticios en OP09-PRE-BASE. Dos análisis nuevos con analista y visualizador distintos; ingreso nuevo invalidó correctamente análisis anterior de Silo5. La muestra de salida está firmada, pero no hay especificaciónSILO vigente. Liberar etapa deshabilitado, material ausente de cargables; cero liberaciones/despachos de salida11. No se alteraron límites ni permisos. Preparador repetido sin duplicar orden.

QA de archivos concilia52modelos/299filas y movimientos17–21, FIFO íntegro y una sola salida/ingreso. Cadencia medible10,007s por usuario;307 inicios al corte de QA, brechas28/33 preservadas.15capturas nuevas y manifiestoSHA256. Se conservó advertencia de0minagitación; no certifica proceso físico. Interacción de cierre recuperada por recarga antes de un único envío real. Sólo un coordinador y un apoyo QA.

Nuevos archivos: `qa/opflow/seed_precond_order.py`, [expediente](docs/operacion/OP-09_PRECONDENSADO.md) y paquete de evidencia; enlaces/backlog/progreso actualizados. Aplicación intacta, PR19continúa borrador, sin merge/despliegue. Usuario indicó continuar e informar trabas; no suministró rangos de Calidad, requisito industrial todavía pendiente. EXPLICADOR de siete apartados en el expediente. Próximo paso de esta ruta es resolver esa especificación antes de liberar; suero/rework y F01–F07 permanecen pendientes.

---

## AVANCE vigente — OP-09 operacional, 2026-10-23, corte15:14 UTC

**PARCIAL.** Descarga inicial recuperada sin duplicar recepción; circuitos por pantalla llegaron a tres hojas ejecutadas: DE6296-01 polvo500kg, DE6296-02 mantequilla20kg y DE6296-03 crema42,50L. Además, DespachoLeche1 de1000L. RW-00000111kg disponible en PT-DISP, aún sin consumir. Datos ficticios locales; ninguna operación productiva, despliegue o merge.

QA contrastó269filas de52modelos, una salida por despacho y FIFO; ambas salidas del segundo descremado tienen analista y visualizador distintos. Diario257inicios, mínimo medible10,007s por usuario; cero infracciones medibles, brechas28/33 declaradas. Se guardan53capturas seleccionadas, diarios originales, correcciones y manifiestoSHA256. Ruff QA y diff-check ejecutados; ninguna suite de aplicación o carga adicional declarada.

Se añadieron sólo cuatro fixtures de preparación (descremado, cliente ficticio, mantequilla y vínculo de ruta de crema), informe, evidencia, backlog y progreso. Aplicación intacta. OP de mantequilla40kg expresamente autorizada; OP de precondensado2000L aún pendiente y no creada. No se sembraron lotes industriales liberados para simular pruebas.

Hallazgos F01–F07: disponible y genealogía incorrectos en descremada/vale, mantequilla con grasa físicamente incompatible aceptada, checklist por familia, embalajes fraccionados, cronología y ubicación histórica engañosa. **No corregidos.** Precondensado, suero externo y consumo de rework pendientes. [Informe con EXPLICADOR de siete apartados](docs/operacion/OP-09_OPERACIONAL_RESULTADOS.md) y [formularios/pantallas](docs/operacion/evidencias/opflow-ejecucion/PANTALLAS.md). PR19 de evidencias continúa en borrador; no equivale a autorización de operación industrial.

---

**OP-00, OP-01 y OP-02: COMPLETADAS EN SUS RAMAS** · OP-00 [PR #6 borrador](https://github.com/FelipeCCAA/CCAA/pull/6) · OP-01 [PR #7 borrador](https://github.com/FelipeCCAA/CCAA/pull/7) · OP-02 [PR #9 borrador](https://github.com/FelipeCCAA/CCAA/pull/9). **OP-03: COMPLETADA EN LA RAMA**, rama `codex/op-03-saldo-reservas-ubicacion` desde `8d0ede7`. No hay merge ni despliegue; no se calcula porcentaje de capacidad. Corte 2026-10-21.

La entrega afectó seis archivos: [.github/workflows/ci.yml](.github/workflows/ci.yml), [tests del reset](backend/usuarios/tests_reset_datos_operacionales.py), [tests de Resumen](backend/produccion/tests_api.py), [guía OP-00](docs/operacion/OP-00_VALIDACION.md), [TASK_BACKLOG.md](TASK_BACKLOG.md) y este [PROGRESS.md](PROGRESS.md). Código y guía están en los commits [`1ed4622`](https://github.com/FelipeCCAA/CCAA/commit/1ed4622a7aa8bc5eab0298beadbdc7f9141bc8b8) y [`4793e33`](https://github.com/FelipeCCAA/CCAA/commit/4793e33b909c2b2a0a29eaf565f2fe3c5711d95d). Este checkpoint documental es posterior al head verificado y se registra en un commit posterior que modifica únicamente los dos documentos de seguimiento. El PR sigue en borrador; no se ha fusionado ni desplegado.

**CI final aprobada:** [run 39430749532](https://github.com/FelipeCCAA/CCAA/actions/runs/39430749532) terminó SUCCESS en el head `4793e33`. [Backend](https://github.com/FelipeCCAA/CCAA/actions/runs/39430749532/job/118654869339) ejecutó 1.529 pruebas en 466.324 s: `OK (skipped=5)`, equivalente a 1.524 aprobadas, 5 omitidas, sin fallos ni errores. Ruff, Django checks, ausencia de cambios de migración y migraciones en base efímera pasaron. [Frontend](https://github.com/FelipeCCAA/CCAA/actions/runs/39430749532/job/118654870026) pasó 85/85, lint, TypeScript y build. [Production config](https://github.com/FelipeCCAA/CCAA/actions/runs/39430749532/job/118654869852) pasó. La CI usó PostgreSQL 17.11; la prueba local usó PostgreSQL 17.10.

**Evidencia local:** la suite focalizada combinada de reset y Resumen pasó 14/14 en 6.920 s, con 1.000 kg fuera de ventana, 2.000 kg en la frontera inclusiva y 4.000 kg dentro. La base de test se destruyó al terminar. Ruff del backend y `git diff --check` terminaron con exit 0. `check`, `makemigrations --check --dry-run` y `check --deploy` terminaron con exit 0; `check --deploy` mostró el aviso preexistente `W021` de HSTS preload. El build conserva el aviso preexistente `INEFFECTIVE_DYNAMIC_IMPORT` de `FormularioMaestro`; ninguno bloqueó CI y no se cambió política ni código asociado. La revisión QA independiente final no encontró hallazgos bloqueantes y verificó limpieza de `enterContext`; no ejecutó pruebas propias.

**Registro histórico de regresión:** la primera ejecución backend local tuvo 1.528 pruebas, 3 fallos, 1 error y 5 omitidas en 846.339 s. La primera CI [39428353622](https://github.com/FelipeCCAA/CCAA/actions/runs/39428353622) tuvo los mismos cuatro fallos en `ResumenAPITests` por fixtures de julio fuera de la ventana de 90 días al correr el 20-oct-2026; registró 1.528 pruebas, 3 fallos, 1 error y 5 omitidas en 499.477 s. Se corrigieron únicamente las pruebas con fecha controlada, controlando `RESUMEN_DIAS=90` dentro de los tests y la frontera inclusiva del 3-may. La corrida final global aprobada confirma la resolución.

El clúster local aislado `../op00-runtime/pgdata` se detuvo con `pg_ctl` apuntando a su carpeta exacta; comando y sesión 73510 terminaron exit 0 a las 13:30 UTC. Se verificó que `postmaster.pid` no existía. CI utilizó PostgreSQL 17.11 y el perfil local PostgreSQL 17.10; ambos fueron entornos aislados.

No se hicieron pruebas con datos reales, circuito operacional, carga de 70 usuarios ni restauración de backup. Los 70 usuarios describen población, no concurrencia certificada.

## OP-01 — firma y despacho

**Estado: COMPLETADA EN LA RAMA** `codex/op-01-firmas-despacho`, head verificado `479624ae1783b3087cdab4f520ad1f889443214c`, commits `49282a5`, `a976283`, `8af89ca`, `479624a`, apilada sobre OP-00 (`032be18`). La [CI global 39446921296](https://github.com/FelipeCCAA/CCAA/actions/runs/39446921296) terminó SUCCESS en el head. [PR #7](https://github.com/FelipeCCAA/CCAA/pull/7) permanece abierto y en borrador, no fusionado; rama remota `DevelopMain` sigue en `d34df44`. El cierre cubre implementación y validación de rama; revisión/merge/despliegue y aplicación a firmas históricas reales son hitos aparte. El PR contiene 35 archivos de implementación y estos tres documentos; [manifiesto de archivos](https://github.com/FelipeCCAA/CCAA/pull/7/files).

**Validación global:** backend ejecutó 1.586 tests en 516.121 s, `OK (skipped=5)`: 1.581 aprobados, 5 omitidos y cero fallos/errores; PostgreSQL CI 17.11. Ruff, Django checks, dry-run de migraciones y migraciones efímeras pasaron. Frontend pasó 88/88, lint, TypeScript y build. Production-config pasó; mostró solo el aviso preexistente W021. El aviso de import dinámico de `FormularioMaestro` también es preexistente y no bloqueó. Resultados y enlaces de trabajos están en el [expediente OP-01](docs/operacion/OP-01_VALIDACION.md).

**Regresión local focal:** 96/96 pasaron en 33.449 s (Calidad 25, Inventario OP-01 29, heredadas 42, con seis carreras); Producción 16/16 en 33.657 s (3 nuevas, 13 heredadas). Las 57 regresiones nuevas están cubiertas por las suites de Calidad, Inventario y Producción; Ruff, Django check y dry-run de migraciones pasaron. El clúster PostgreSQL 17.10 dedicado se detuvo mediante `pg_ctl`; sesión exit 0 y sin `postmaster.pid`. QA independiente no encontró bloqueos técnicos.

Reglas adoptadas: la aprobación se liga a la identidad exacta del lote. Cambios semánticos de análisis/muestra, especificación, documento, lote o control invalidan la firma aunque el resultado siga conforme; notas libres y no-op no. Firmas históricas sin metadata necesitan firma nueva y reautorización, sin autoaprobación ni backfill. Despacho vuelve a validar origen físico, silo cuando corresponde y disponibilidad al ejecutar. La invalidación es atómica, conserva el acto previo de auditoría y la salida utiliza la misma foto/snapshot y token all-or-nothing. No se amplía OP-01 a genealogía industrial ni a decisiones de otras OP.

Hubo walkthroughs independientes de escritorio de Producción, Calidad y Bodega; no son E2E ni certificación industrial. Queda registrada una limitación UX no bloqueante: Detalle de Lote puede verse verde para una concesión legacy sin metadata, aunque Despacho la rechaza; `liberado` en esa vista funciona como guarda de edición, no habilitación de salida. Las pantallas abiertas no reciben cambios remotos automáticamente y Hoja de Despacho indica actualizar tras rechazo. No se amplió la entrega para corregir UX.

La CI anterior `39444907350` falló con 1.579 pruebas, 4 fallos, 3 errores y 5 omitidas. Se resolvieron en los cuatro commits finales; dos CI intermedias fueron canceladas y no se consideran aprobadas. Un intento local previo con `--keepdb` se interrumpió al vaciarse semilla de test por `TransactionTestCase`; no se modificaron fixtures productivos para ocultarlo. Las pruebas finales usaron bases aisladas y el clúster dedicado OP-00.

No se hicieron pruebas con datos reales, circuito industrial completo, carga de 70 usuarios ni restauración de backup. La población de 70 usuarios no representa concurrencia aprobada/certificada. Revisión/merge/despliegue humanos, UAT industrial y plan para registros históricos quedan fuera de este cierre de rama.

## OP-02 — balance, receta y correcciones

**Estado: COMPLETADA EN LA RAMA.** Código verificado `7d36bbe553d1ce941fe9a1942ff07fd62c4c26d0`, commits `6f8c302` y `7d36bbe`; [PR #9](https://github.com/FelipeCCAA/CCAA/pull/9) en borrador sobre la rama documental de PR #8. El commit de entrega posterior solo modifica cuatro documentos. Sin merge ni despliegue.


El usuario aprobó ocho reglas para el balance, retenciones, correcciones documentales/físicas y liberación de Calidad, con precisión máxima de 0,01 L. El detalle de contrato y aceptación está en [OP-02_VALIDACION.md](docs/operacion/OP-02_VALIDACION.md); [OP-02_DIAGNOSTICO.md](docs/operacion/OP-02_DIAGNOSTICO.md) se conserva como diagnóstico histórico, no como autorización pendiente.

La migración `0010_actovaleestandarizacion` es aditiva. La reversión de código debe conservar la tabla de actos y su evidencia; no eliminar historia si existen actos. No se autoriza producción, despliegue ni datos reales. Balances históricos incongruentes no se autorreparan.

**Evidencia al corte:** suite focal limpia 83/83 en 41,264 s con base efímera reconstruida por migraciones y destruida al terminar; incluyó balance, actos, bloqueos, despacho, muestreo, borrador, código de vale, correcciones y reset. Despacho 2/2; frontend 91/91; Chrome local 1/1 con API mock (dos pasos, 6,4 s; total 10,3 s), sin validación de API real. Ruff, Django check y `makemigrations --check --dry-run` pasaron. El clúster OP-00 local se detuvo con `pg_ctl` sobre su carpeta exacta, exit 0 y sin `postmaster.pid`. CI del commit `6f8c302` reportó 1.635 pruebas, 3 fallos, 2 errores y 5 omitidas: 2 fallos de fixtures de muestra sin fecha, 1 fallo de confirmación del reset y 2 errores del reset por allowlist faltante. El commit [`7d36bbe`](https://github.com/FelipeCCAA/CCAA/commit/7d36bbe) contiene los arreglos; la [CI 39469931594](https://github.com/FelipeCCAA/CCAA/actions/runs/39469931594) terminó SUCCESS en ese código: backend 1.635 tests en 535.218 s, `OK (skipped=5)`, 1.630 aprobadas, cero fallos/errores; frontend 91/91 y controles aprobados. La regresión local global con `--keepdb` terminó con 1.634 pruebas, 17 fallos, 68 errores y 5 omitidas tras contaminar las semillas al reutilizar la base después de `TransactionTestCase`; no es aprobación global. El defecto de formulario antiguo de corrección de muestra queda cerrado al recibir 409; el test backend se incluyó en la suite focal limpia 83/83. Tres revisiones de escritorio de operadores no son simulación real ni E2E; el punto ciego de genealogía inferida queda fuera de OP-02 para OP-03. La CI global sustenta el cierre técnico de la rama. Quedan revisión humana, UAT industrial, tratamiento de históricos y OP-03; su implementación no está autorizada por esta tarea. El [expediente de validación](docs/operacion/OP-02_VALIDACION.md) conserva matriz y detalle.

## OP-03 — saldo, reservas y ubicación

**AVANCE — COMPLETADA EN LA RAMA; VALIDADA MEDIANTE PRUEBAS.** [PR #10 borrador](https://github.com/FelipeCCAA/CCAA/pull/10), rama `codex/op-03-saldo-reservas-ubicacion` desde OP-02 `8d0ede7`. Sin merge ni despliegue.

- **Tarea efectiva:** cinco reglas aprobadas implementadas; consultas de Recepción/Producción distinguen físico, reserva, libre y disponible; retiros respetan compromisos; traslados atómicos/idempotentes conservan lote; entrega consume sólo su reserva; cierre/cancelación de ejecución libera pendientes propios. Revalidación de stock/capacidad/Calidad y bloqueos ordenados. No se cambió tolerancia industrial ni se creó cancelación MRQ.
- **Evidencia:** [CI 39624260452 SUCCESS](https://github.com/FelipeCCAA/CCAA/actions/runs/39624260452), head `ef4cd15d6c65ae69b6713fc88e56c0bc3ecfd4ec`: 1.674 backend en 244,149 s (1.669 aprobadas, cinco omitidas, cero fallos/errores), 97/97 frontend, lint, tipos, build, checks y migraciones efímeras. Local 64/64 focal (39 nuevas, tres carreras PostgreSQL), 58/58 regresiones de fixtures y Chrome 5/5 con API simulada. Avisos W021 y FormularioMaestro preexistentes.
- **Archivos:** 38 de código/pruebas/configuración de pruebas y tres de documentación. Incluye recepción/procesos/producción/inventario, consulta de retenciones OP-02, migración aditiva `0032`, pantallas de silos/despacho/Bodega, ocho fixtures heredados y suites nuevas. [Detalle y reproducción](docs/operacion/OP-03_VALIDACION.md), [manifiesto PR](https://github.com/FelipeCCAA/CCAA/pull/10/files). No se modificaron dependencias ni configuración de despliegue.
- **Commits/PR:** `6d41690`, `5b5c6c4`, `de920a4`, `548de88`, `ef4cd15` subidos. El commit de cierre posterior cambia sólo este documento, backlog y expediente: su CI separada no se declara aprobada por anticipado; código/pruebas iguales al head verificado.
- **Riesgos/límites:** DESK de Recepción, Producción y Bodega y revisión técnica independiente; no UAT, E2E integrado con BD, carga ni restauración. Clave de formulario en memoria: cerrar/recargar puede perderla; recuperar/consultar historial antes de iniciar otra operación si el resultado es incierto. No se autorrepara historia ni se eliminan columnas/evidencias en un rollback. PostgreSQL local detenido, `postmaster.pid` ausente; sin producción. `DevelopMain` permanece en `d34df44`.
- **Próxima tarea:** OP-04 secado/FIFO, lista para diagnóstico y propuesta de reglas. OP-04 a OP-09 siguen sin implementar.
- **Decisiones:** revisión humana del PR y dependencias apiladas; validación/autorización antes de implementar OP-04. Merge, despliegue, UAT industrial o uso de recursos/datos reales no están autorizados por este cierre.

**EXPLICADOR — OP-03**

1. **Problema:** se podía ofrecer o retirar volumen físico ya comprometido por otra operación.
2. **Causa:** algunas rutas comprobaban stock físico sin descontar reservas ni asegurar el destino hasta confirmar.
3. **Ejemplo simulado:** 10.000 L físicos menos 8.000 L reservados dejan 2.000 L libres; intentar retirar 3.000 L se rechaza sin mover producto.
4. **Solución:** respetar las cinco reglas aprobadas y confirmar el movimiento completo una sola vez; repetir la misma clave recupera el resultado sin duplicarlo.
5. **Trabajo realizado:** PM/AVANCE coordinaron expediente y fixtures; especialistas backend/frontend implementaron; QA aportó regresiones; revisión independiente detectó y verificó correcciones; operadores hicieron DESK. Se añadió UUID aditivo sin backfill y se ajustaron pantallas. Sin cambios productivos.
6. **Pruebas y resultados:** CI global aprobada: 1.674 backend (cinco omitidas), 97 frontend; local 64 focales y 58 heredadas, Chrome 5 con API simulada. Los fallos previos y su corrección están registrados; no se presentan como aprobaciones.
7. **Estado final:** VALIDADO MEDIANTE PRUEBAS EN LA RAMA. Pendiente revisión humana y validación industrial; no se afirma que toda la planta esté lista para operar. Siguiente OP-04, primero validar reglas.


## OP-04 — Secado y FIFO

**COMPLETADA EN LA RAMA** `codex/op-04-secado-fifo`, desde OP-03 `5fd3d89`. Usuario validó seis reglas y autorizó rama, pruebas y PR. Código/pruebas `1e2098d89ffc422471b9aa247ccb0b82af82c4bc`; [PR #11 borrador](https://github.com/FelipeCCAA/CCAA/pull/11) apilado sobre OP-03 #10. El cierre posterior sólo modifica este documento, TASK_BACKLOG.md y el [expediente OP-04](docs/operacion/OP-04_VALIDACION.md), sin cambios de código/pruebas. Su CI documental separada no se declara aprobada por anticipado.

Implementado origen/retiro verificable, unidades separadas, FIFO calculado por servidor, excepción auditada, UUID recuperable y cierre trazable con Calidad. Continuación retira el silo dentro del cierre, exige firma vigente y veta CIP antes de un retiro nuevo. Protege correcciones concurrentes de AnalisisSilo, orden de bloqueos y entradas duplicadas. Sin migración nueva, conversión automática ni tolerancia industrial inventada.

**CI final SUCCESS** [39637476601](https://github.com/FelipeCCAA/CCAA/actions/runs/39637476601) en `1e2098d`: backend 1.696 pruebas en 378,453 s, 1.691 aprobadas y cinco omitidas preexistentes, cero fallos/errores. Frontend 101/101; Ruff, Django checks, migración efímera, dry-run, lint, tipos, build y configuración aprobados. Incluye 22 casos nuevos backend y extensión CIP final. Local limpio 68/68 en 158,219 s, Chrome con API simulada 5/5 en 51,7 s y estandarización previa 166/166. Fallo inicial de fixture (35 pruebas, un error) y ajustes de selectores de navegador documentados; no se cuentan como aprobados.

Sólo tres subagentes: backend y revisión independiente `gpt-6-sol high`, frontend `gpt-6-luna medium`; PM/AVANCE/EXPLICADOR integrados por el coordinador. Revisión técnica final sin bloqueantes conocidos por lectura; DB/CI ejecutados por coordinador/GitHub. Recorridos de escritorio de Recepción, Producción y Bodega; no UAT.

Clúster local exacto OP-00 detenido, exit 0 y sin postmaster.pid. DevelopMain verificada sin cambios en `d34df44ca30c402e9da34dc7b75f7652c2751fef`. Sin merge, despliegue, datos productivos, carga de 70 usuarios ni restauración de backup. Medición kg declarada con referencia y antecedentes históricos quedan sujetos a revisión operacional. OP-05 lista para diagnóstico/reglas, sin autorización para implementar. Revisión/merge, UAT y producción requieren sus decisiones posteriores.


## OP-05 — Mantequilla

**COMPLETADA EN LA RAMA** `codex/op-05-mantequilla`, desde OP-04 `f00e39a`. Seis reglas aprobadas y ejecución autorizada. Código/pruebas `85b5ad1b8d8134fe1bf97d722ae2ca0fe7b396ff`; [PR #12 borrador](https://github.com/FelipeCCAA/CCAA/pull/12), sobre OP-04 #11. El cierre posterior actualiza tres documentos y dos valores de fixtures Chrome (origen L y equipo línea), comprobados 5/5. Código de funcionamiento y tests backend idénticos al head con CI aprobada; su CI separada no se anticipa aprobada.

Implementadas las seis reglas de origen físico explícito, firma vigente, saldo de lote/salida/TK, reservas/CIP, unidades/conversión identificada, balance conservado sin nuevas salidas mazada y recuperación UUID. Genealogía y consulta de disponibilidad mantienen vínculo al lote y cuentan una vez el retiro. Orden de bloqueos coordinado con continuación, Secado y Despacho. Cierre conserva firma/análisis/densidad de inicio y registra vigencia al cierre separada. Migración 0024 aditiva nullable sin backfill, aplicada sólo a BD sintéticas.

**CI final SUCCESS** [39647306726](https://github.com/FelipeCCAA/CCAA/actions/runs/39647306726), `85b5ad1`: backend 1.719 tests en 393,864 s, 1.714 aprobadas y cinco omitidas preexistentes, sin fallos/errores. Frontend 103/103; Ruff, checks, dry-run, migración efímera, lint, tipos, build y configuración aprobados. Local final limpio 34/34 en 24,774 s (23 nuevas, once heredadas); Chrome final 5/5 en 15,6 s con API simulada. Historial: seis fallos baseline; primera focal 22/23 por formato de fixture; primera amplia 203/207, cuatro errores de firma fuera de transacción en fixtures corregidos. No se contaron como aprobadas.

Sólo tres subagentes: backend/revisión gpt-6-sol high y frontend gpt-6-luna medium; PM/AVANCE/EXPLICADOR integrados por coordinador. Revisión independiente por lectura sin bloqueantes pendientes de las correcciones revisadas; ejecución real por coordinador/CI. Recorridos DESK de Recepción, Almacenamiento/Producción e Inventario/Despacho, sin UAT.

Archivos, reproducción y límites en [OP-05_VALIDACION.md](docs/operacion/OP-05_VALIDACION.md). Clúster local OP-00 detenido al cierre de OP-05, sin postmaster.pid. DevelopMain verificada sin cambios en `d34df44ca30c402e9da34dc7b75f7652c2751fef`. Sin merge, despliegue, producción, carga certificada o restauración. Antes de despliegue futuro revisar corridas históricas abiertas sin salida_crema. OP-06 continuó con aprobación posterior de sus seis reglas y autorización expresa de implementación, según el cierre siguiente.

## OP-06 — Identidad

**IMPLEMENTADA Y VALIDADA LOCALMENTE EN LA RAMA** `codex/op-06-identidad` desde OP-05 `c21b1f3`. Seis reglas aprobadas; frontend `5bdca62`, backend `a62622c`. Consulta de identidad antes de montar módulos protegidos, sin caché de respuesta, con conservación de Recordarme, rechazo de respuestas antiguas y formulario de alta ajustado a `change_roles`. Acceso revalida contraseña/activo bajo bloqueo; clave inicial exige reemplazo antes de operar; promociones explícitas y delegación propia de área. Cambios efectivos de identidad revocan sesiones en una transacción, también en admin y grupos; no-op conserva sesiones. Altas sin perfil se rechazan sin User parcial. Capacidades de grupo se comunican a pantalla y se precargan en listados.

Evidencia local: focal 51/51 en 108,516 s; dos guardas finales 2/2 en 3,034 s y alta atómica 1/1 en 7,810 s; API/rendimiento final 17/17 en 112,070 s, cuatro consultas constantes con cinco personas/sesiones. Frontend 107/107, lint/tipos/build y Chrome OP-06 7/7; regresiones simuladas OP-02 a OP-05 16/16. Ruff global, checks, comprobación de migraciones sin escritura y configuración ficticia endurecida aprobados. Cortes solapados, no sumar como pruebas únicas. Fallos de baseline, formularios corregidos y expectativas de autorización anteriores documentados en [OP-06_VALIDACION.md](docs/operacion/OP-06_VALIDACION.md).

Dos agentes de apoyo reutilizados (backend y revisor, `gpt-6-sol high`), sin activar los demás; frontend, integración, QA, PM/AVANCE/EXPLICADOR por coordinador. Revisión independiente sobre `a62622c` sin bloqueantes nuevos de las guardas revisadas; pruebas ejecutadas por coordinador. Sin migraciones ni nuevas contrataciones, credenciales o recursos externos.

Entrega de revisión apilada sobre OP-05 #12, con verificación general por CI del PR; el informe AVANCE y sus checks conservan el resultado del commit entregado. Clúster exacto OP-00 detenido, exit 0 y sin postmaster.pid. DevelopMain verificada sin cambios en `d34df44ca30c402e9da34dc7b75f7652c2751fef`. Sin producción, merge, despliegue, UAT, carga certificada o restauración. OP-07 continuó con aprobación expresa posterior, según el cierre siguiente.

## OP-07 — Identificadores, auditoría y exportaciones

IMPLEMENTADA Y VALIDADA LOCALMENTE EN LA RAMA codex/op-07-auditoria-exportaciones desde OP-06 4dd3a94. Seis reglas aprobadas. Código/pruebas 3ad83f3: IDs/UUID intactos; auditoría masiva crítica atómica y fiel; historia/secretos conservados; CSV/XLSX literales y tres formatos limitados a 1000 recepciones con rechazo explicado, sin truncar. Interfaz muestra error JSON/Blob y cancela consultas anteriores.

Integración 58/58, historia API 12/12, frontend 111/111, Chrome 2/2 simulado; Ruff, lint, tipos/build y ausencia de nuevas migraciones aprobados. Dos apoyos reutilizados: backend y revisión independiente sin bloqueos concretos; coordinación integra QA/PM/AVANCE. [Expediente y límites](docs/operacion/OP-07_VALIDACION.md). CI general y PR definitivo en sus checks y AVANCE del commit entregado.

Clúster OP-00 detenido, sin postmaster.pid. Sin producción, datos reales, migraciones nuevas, merge ni despliegue. No UAT, carga certificada ni restauración de backup. PR sobre OP-06 #13. Próxima OP-08: diagnóstico/preparación, implementación requiere autorización propia.

## OP-08 — Envases, archivos y correo

**AVANCE — IMPLEMENTADA Y VALIDADA LOCALMENTE EN LA RAMA**, `codex/op-08-envases-archivos-correo`, desde OP-07 `e2fb6de`; código/pruebas `e592252`. Usuario aprobó seis reglas y ejecución con pruebas/PR. Pedidos completos firmados y recuperables por UUID, sin doble consumo; pendientes separados por cuenta y visibles aun sin embalajes. Adjuntos con documento y permisos heredados, descarga privada/hash, validación de formato y compensación de fallos; bloqueo compartido contra borrado concurrente. Correo indica aceptación/fallo/incertidumbre sin prometer cambio de clave, reintento sólo 401 una vez.

- Evidencia local: 45/45 archivos/correo y regresiones, 40/40 integración backend (solapadas), 1/1 carrera adicional con bloqueo real PostgreSQL; frontend 111/111; Chrome 5/5 en 13,5 s con API simulada. Ruff, diff-check, Django check, esquema, lint, tipos y build aprobados. Revisión independiente final sin defectos materiales pendientes. Detalle de fallos previos y reproducción en [expediente OP-08](docs/operacion/OP-08_VALIDACION.md).
- Archivos/commits: 35 archivos de código/pruebas/configuración en `e592252`; tres documentos de cierre. Manifiesto completo en PR. Migración 0017 aditiva, sin backfill ni cambios productivos. PR preparado sobre OP-07 #14, no DevelopMain. CI general y job de volumen efímero se registran en checks y AVANCE del PR del SHA entregado, sin declararlos aprobados por anticipado.
- Equipo: dos apoyos reutilizados, envasado y revisor (`gpt-6-sol high`); coordinador integra archivos/correo, QA y PM/AVANCE/EXPLICADOR. Sin activar todos los roles.
- Límites: validación de formatos no es antivirus; compensación no asegura atomicidad distribuida ante caída del host. Configuración de volumen privado preparada, no aplicada; archivos históricos/corte/backup pendientes de plan. Respuesta pública de correo genérica, tiempo constante no certificado. Sin UAT, correo real, carga de 70 usuarios ni restauración. Clúster exacto OP-00 detenido, sin postmaster.pid. Sin producción, Supabase/logs, merge ni despliegue.
- Próxima: OP-09 para diagnóstico/preparación no destructiva. Se requiere validar escenario y concurrencia de carga, destino sintético de restauración y autorizar su ejecución; revisión/merge/despliegue son decisiones posteriores.

**EXPLICADOR — OP-08**

1. **Problema:** un reintento de envasado, un archivo o un correo incierto podían interpretarse incorrectamente.
2. **Causa:** no se comprobaba el pedido completo ni se separaban bien documento/permisos y aceptación del correo.
3. **Ejemplo:** si se corta la conexión al crear un pallet, reenviar el mismo pedido recupera ese pallet sin descontar materiales de nuevo.
4. **Solución:** conservar clave y datos; archivo privado autorizado y verificado; correo con estado preciso, sin reenvío automático incierto.
5. **Trabajo:** implementado en rama y revisado por dos apoyos, pruebas sintéticas; configuración preparada sin despliegue.
6. **Pruebas:** backend y navegador aprobados localmente según evidencia arriba; CI general y almacenamiento se informan en el PR cuando terminan.
7. **Estado final:** implementación local lista para revisión; todavía sin fusionar ni desplegar. OP-09 pendiente, no se certifica la planta lista para operar.

## OP-09 — AVANCE de ejecución aislada

1. **Realizado:** usuario autorizó seis reglas y escalones; clúster PG17 nuevo, datos ficticios y browser/API reales. Rama `codex/op-09-circuito-carga-respaldos`, QA `6773958`, desde OP-08 `a564861e`. Sin código de aplicación, producción, despliegue ni Supabase/logs.
2. **Evidencia:** precondensado/descremado/mantequilla/suero principales logrados; carrera HTTP 201/409 y reintento de respuesta descartada sin duplicar; 77/77 regresión PostgreSQL. Respaldo+restauración 130 tablas y adjunto privado iguales; operación en API restaurada aprobada. Lint/tipos/Ruff/diff-check aprobados.
3. **Problemas:** polvo bloqueado al Envasar por firma anterior invalidada tras avance normal de etapas (H09-01 P1). Carga 25 abortada por siete respuestas perdidas, tres POST inciertos; conciliación posterior 451 UUID distintos, stock por ubicación exacto. Correspondencia de claves cliente incompleta en generador. Auxiliar de mantequilla fallida por estado ya liberado, no se declara toda suite verde.
4. **Carga:** 10 usuarios/10 minutos aprobado, p95 lectura 0,325 s y escritura 0,425 s, cero errores. 25 sólo 244,726 s; 50/70 no ejecutado. Sostenida independiente a 10 abortada a 631,029/1.800 s por RAM del host 87%, 3.031 solicitudes sin error; 223 nuevas UUID exactas en API/BD, saldo por ubicación íntegro. No reemplaza fallo25 ni cumple treinta minutos. Límite por IP probado: 45 intentos fallidos 401 y el 46 recibió 429 con Retry-After; ventana compartida con accesos previos, no 70 accesos válidos simultáneos.
5. **Equipo:** coordinador cubre PM/QA/AVANCE/EXPLICADOR, un revisor independiente reutilizado (`op08_revision`, gpt-6-sol high). No se activan 16 roles. PR #16 borrador sobre OP-08 #15, CI final pendiente; diez resúmenes y manifiesto SHA256 de 37 crudos versionados, evidencia completa local conservada.
6. **Decisión pendiente:** validar alcance de firmas por etapa antes de arreglar H09-01; alinear bandeja y confirmación. Diagnóstico posterior de transporte y nueva carga en entorno representativo; no inferir capacidad productiva de Django dev/Windows.
7. **Estado:** comprobaciones ejecutadas con bloqueantes, no aprobación global OP-09 ni habilitación de planta. [Expediente, archivos, fallos y límites](docs/operacion/OP-09_VALIDACION.md). Preview local 5209, API8209 y PG55449 conservados en loopback; API restaurada detenida.

**EXPLICADOR — OP-09**

1. Probamos con leche, lotes y usuarios inventados en una instalación aparte.
2. Recorrimos pantallas reales hasta inventario/despacho y probamos dos personas compitiendo por el mismo saldo.
3. Los reintentos dirigidos recuperaron la misma operación sin descontar dos veces.
4. En polvo apareció un problema real: avanzar de etapa hace vencer una firma anterior y al final impide envasar, aunque la pantalla ofrece hacerlo.
5. Con diez personas la prueba breve funcionó; con veinticinco se perdieron respuestas y paramos. El inventario sí cuadra, pero falta resolver la incertidumbre antes de aumentar usuarios.
6. Restauramos base y archivo privado en otra instalación y pudimos volver a operar con datos ficticios; eso aún no asegura tiempos de recuperación de planta.
7. No cambiamos las reglas para esconder fallos. La sostenida se detuvo por memoria del equipo antes de cumplir treinta minutos; las correcciones nuevas deben validarse antes de programarlas.

## H09-01 — AVANCE

Implementación `124d56e`, rama `codex/h09-01-firmas-por-etapa`, PR17 borrador sobre OP09 #16. Seis reglas autorizadas: evidencia por salida/etapa, avance normal conserva firma previa, correcciones retiran sólo dependientes, historial y saldos conservados, bandeja/POST/Despacho coherentes y refirma autorizada. JSONv2, v1 estricta; sin migraciones/backfill. Un apoyo QA reutilizado, no16 agentes.

Circuito web real sobre copia ficticia H09: Evaporación2/2, continuación reanudada1/1 hasta pallet500kg en Inventario/PT-DISP. Dos firmas de proceso vigentes, versión0, un acto cada una; firma final vigente. Ruff/check/esquema, frontend111/111/lint/tipos/build aprobados. Corte focal final88/88, ninguna omitida, incluye18 nuevas. CI del código124d56e SUCCESS/run39819878080:backend1.825 (1.820 aprobadas, cinco omitidas), frontend/almacenamiento/configuración aprobados. Local completo previo1.823 (1.818 aprobadas, cinco omitidas); no sumar cortes solapados ni atribuir a esa corrida los dos últimos ajustes. Entrega posterior sólo documentos/evidencia QA; CI adicional se consulta en PR sin anticipar resultado. Crudos/fallos preservados y [expediente](docs/operacion/H09-01_FIRMAS_POR_ETAPA.md). Sólo clúster local H09; sin producción, Supabase/logs, merge o despliegue. Carga OP09 y preparación productiva siguen pendientes.

**EXPLICADOR — H09-01**

1. **Problema detectado:** avanzar a Secado hacía vencer la firma de Evaporación y después impedía envasar.
2. **Causa técnica:** la foto firmada incluía equipo, peso y estado actuales del lote completo, que cambian al avanzar.
3. **Ejemplo real de operación:** cerrar Secado ya no obliga a pedir otra firma de Evaporación; el lote ficticio pudo llegar a Inventario.
4. **Solución recomendada:** aprobar datos propios de cada etapa y revisar otra vez las etapas afectadas por una corrección verdadera, conservando los bloqueos.
5. **Trabajo realizado:** coordinador implementó fotos/propagación/guardas y un QA aportó pruebas/revisión independiente. No se cambió esquema ni producción; quedó rama y PR.
6. **Pruebas y resultados:** circuito real completado en cortes con firmas únicas, controles estáticos e interfaz aprobados; corte final88/88 y CI del código aprobados (1.820 backend aprobadas, cinco omitidas). Fallos de fixtures/aserciones se conservan.
7. **Estado final:** implementación validada en circuito ficticio, regresiones y CI de código; lista para revisión humana del PR17. Firmas antiguas vencidas requieren revisión explícita; no se convierten automáticamente. Sin despliegue; no equivale a aprobar la carga de planta.


## OP-09 — AVANCE de reejecución de carga, 2026-10-23

**EJECUTADA HASTA GUARDA; VALIDACIÓN PARCIAL.** Rama `codex/op09-carga-revalidacion`, base5844447; coordinador y un apoyo QA. Sólo QA/docs y nuevos ficticios, sin producción, despliegue, contratación ni Supabase/logs. [Informe completo](docs/operacion/OP-09_CARGA_REEJECUCION.md).

- Calentamiento aprobado302,535s,1.406 solicitudes,0 errores. Escalón10 detenido597,512/600s por RAM86%,2.831 solicitudes,0 errores, p95lectura0,269s/escritura0,372s: NO aprobado.25/50/70 y sostenida no ejecutados. No redondear duración ni reiniciar para forzar verde.
- Conciliación304/304 operaciones exactas,63 reenvíos correctos,36 ubicaciones de18 lotes sin diferencias. Diario8.557 eventos/4.260 intenciones/resultados, ninguna nueva trasSTOP, revisión independiente coherente. Seis pruebas QA yRuff aprobados. No hubo nuevas respuestas inciertas; recuperación real no ejercida.
- Ingreso de turno4/70, cuatro identidades y cierres correctos; guardaRAM>85% detuvo. No cambia cuotas ni certifica70 accesos. Evidencia anterior y scripts exactos ejecutados conservados; mejora posterior exige identidades/cierres completos y tiene regresión sin HTTP real.
- Docker Linux existente no quedó disponible: Django Windows diagnóstico local, NO capacidad productiva. Cero sesiones nuevas abiertas al cierre; API8229 y PG55469 propios detenidos. No otras aplicaciones cerradas ni recursos pagados. Evidencia seleccionada: seis resúmenes y manifiesto22 crudos locales.
- Pendientes: H09-02 antiguo fallo25 sin causal/resolución; H09-03 recursos/entorno representativo;70 accesos por IP incompletos. Necesario entorno existente con memoria disponible antes de repetir, sin bajar guardas ni cambiar reglas de negocio.

**EXPLICADOR — OP-09 carga**

1. **PROBLEMA DETECTADO:** no se completaron los niveles ni el tiempo exigidos.
2. **CAUSA TÉCNICA:** RAM agregada del equipo superó85%; no se probó que CCAA causara el consumo. Servidor Linux representativo no disponible.
3. **EJEMPLO REAL DE OPERACIÓN:** diez usuarios ficticios operaron sin errores, pero el computador obligó a detener antes de diez minutos.
4. **SOLUCIÓN RECOMENDADA:** recursos existentes libres y servidor de pruebas representativo; mantener límites y evidencias.
5. **TRABAJO REALIZADO POR LOS AGENTES:** coordinador aisló/ejecutó; un QA preparó y revisó instrumentación/evidencias. Aplicación intacta.
6. **PRUEBAS Y RESULTADOS:** calentamiento aprobado,10 incompleto,304 movimientos exactos,4/70 accesos;6/6 QA.25/50/70/sostenida sin ejecutar.
7. **ESTADO FINAL:** BLOQUEADO PARA COMPLETAR VALIDACIÓN DE CARGA por entorno, sin habilitación de planta ni certificación productiva.


## OP-09 — Operación por pantalla, corte parcial2026-10-23

**BLOQUEADA ANTES DE DESCARGAR; ningún circuito completo aprobado.** Rama `codex/op09-operacional-trazabilidad`, base9af5518. Usuario autorizó acción lógica cada10s por usuario, trazabilidad/capturas/cantidades/destinos; excluye Planificación, Compras y Mantenimiento. Nueva base vacía PG55479/opflow_circuito y API8209/web5209, sólo ficticios y maestros/órdenes/embalajes iniciales. Sin aplicación, producción, despliegue, contratación o Supabase/logs.

Hechos: recepción1/OPF-ENT-01 de25.000L, muestraM-OPF-ENT-01, decisión de e2e_calidad y destino Silo3 por e2e_recepcion; responsables distintos. **0 movimientos de silo**, aún `liberada`, no descargada. Timeout de interacciónCDP al pulsar Descargar (confirmación nativa previa al POST); pestaña bloqueada no recuperada mediante APIs documentadas. Sin POSTdescargar observado y sin cambio físico; memoria~57–65%, no guardaRAM. Verificación de sólo lectura preserva la misma recepción para retomar.

23 intervalos registrados mínimo10,007s; autoguardados/consultas no son actos operacionales. Se documentó corrección de metadatos del primer registrador (seq11–17=Calidad) y capturas007–009 inválidas para acreditar Calidad, sin reescribir crudos. Capturas010/011 verificadas, muestran aprobación y destino25k/Silo3. QA independiente confirma cantidades/estado/ritmo y rutas no ejecutadas. ExtractorREADONLY de52 modelos, Ruff aprobado; ninguna suite general repetida sin cambios de aplicación.

[Informe y pendientes](docs/operacion/OP-09_OPERACIONAL_PARCIAL.md). Se mantiene entorno local para revisión y consulta al usuario sobre confirmación pendiente; recuperar navegador antes de continuar. No saltar descarga medianteAPI/ORM, no fabricar lotes/pallets aprobados ni considerar cubiertas rutas pendientes con ensayos anteriores.

**EXPLICADOR — operación por pantalla**

1. **PROBLEMA DETECTADO:** no se pudo continuar tras pulsar Descargar.
2. **CAUSA TÉCNICA:** controlCDP sin respuesta; confirmación nativa en el botón, causalidad exacta pendiente. No prueba fallo de inventario.
3. **EJEMPLO REAL DE OPERACIÓN:**25.000L aprobados y asignados a Silo3, pero todavía sin movimiento físico registrado.
4. **SOLUCIÓN RECOMENDADA:** recuperar pestaña/confirmación y continuar sobre recepción1, previa comprobación de estado.
5. **TRABAJO REALIZADO POR LOS AGENTES:** coordinador ejecutó UI; un QA creó extractor y verificó evidencia. Sólo QA/docs.
6. **PRUEBAS Y RESULTADOS:** llegada/muestra/Calidad/asignación;23 intervalos>=10s. Descarga y rutas completas pendientes; sin producción.
7. **ESTADO FINAL:** BLOQUEADO PARA CONTINUAR PRUEBA POR PANTALLA, ninguna aprobación global operacional.
