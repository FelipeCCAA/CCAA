# OP-02 — balance, receta y correcciones de estandarización

**Estado: COMPLETADA EN LA RAMA; VALIDADA MEDIANTE PRUEBAS.** Prioridad P0, WP004. La implementación está en `codex/op-02-balance-correcciones`, sobre `c6aba44` de `codex/op-02-plan-y-explicador`; esa base no es la rama OP-00. Los commits de código informados son [`6f8c302`](https://github.com/FelipeCCAA/CCAA/commit/6f8c302) y [`7d36bbe`](https://github.com/FelipeCCAA/CCAA/commit/7d36bbe). El [PR de implementación #9](https://github.com/FelipeCCAA/CCAA/pull/9) está abierto en borrador y apilado sobre el PR documental #8; su [lista de archivos](https://github.com/FelipeCCAA/CCAA/pull/9/files) muestra 46 archivos: 42 de implementación y 4 documentos. La [CI del código `7d36bbe`](https://github.com/FelipeCCAA/CCAA/actions/runs/39469931594) terminó SUCCESS: backend, frontend y production-config aprobados. El commit posterior de entrega solo modifica cuatro documentos. No hay merge ni despliegue.

## Alcance y reglas aprobadas

El flujo cubre la estandarización desde la transferencia hasta agitación, muestreo, análisis de RC, liberación y corrección. Se aprobaron estas reglas para la implementación:

1. El ingreso debe igualar la suma de los componentes debitados. El saldo que ya tenía el silo se contabiliza aparte; el volumen objetivo de receta nunca reemplaza el volumen real.
2. Los litros admiten como máximo dos decimales (0,01 L). Se rechaza mayor precisión; no se redondea silenciosamente.
3. Una diferencia medida se registra y se muestra, sin ajuste automático. La discrepancia activa retención para impedir liberación y despacho, pero permite registrar hechos, investigación y controles.
4. El borrador sigue editable. Antes de confirmar se recalculan y validan saldo, reservas y capacidad.
5. Tras transferir se conservan cantidades, componentes y silos que ocurrieron. Una rectificación documental queda vinculada al vale y registra motivo, responsable y valores antes/después; no reescribe el libro ni el snapshot original.
6. Una corrección física es un movimiento nuevo de adición o retiro, vinculado al acto y con su propio balance y trazabilidad. Si cambia la mezcla, el ciclo exige agitación, nueva muestra, análisis y liberación.
7. Producción autoriza la rectificación física; Calidad debe liberar nuevamente. El consumo posterior y el despacho requieren revisar las áreas afectadas; el sistema no revierte automáticamente consumos anteriores.
8. Cada solicitud se guarda completa o se revierte completa. Repetir una solicitud idempotente no duplica movimientos ni actos.

La identidad de la ejecución original y sus snapshots históricos se mantienen auditables. Las diferencias originales históricas no se reparan automáticamente ni se ocultan mediante actos posteriores. La autorización no extiende OP-02 a la genealogía industrial general de OP-03.

## Contrato de datos y límites operativos

La migración aditiva `0010_actovaleestandarizacion` añade la tabla de actos (`ActoValeEstandarizacion`) para mediciones, rectificaciones documentales, adiciones y retiros. Cada acto conserva vale, clave idempotente, tipo, responsable, motivo, valores aplicables, solicitud y fecha de registro. Los movimientos del libro físico y el snapshot de transferencia se conservan como hechos originales; la cantidad operativa de la salida considera los actos físicos vinculados.

La tabla y sus filas son historia de auditoría. Si se revierte el código de la rama, se conserva la tabla; no se elimina la migración ni los actos si existen, pues la eliminación borraría evidencia. La corrección de balances preexistentes incongruentes queda retenida para investigación. No se hace backfill ni modificación de datos productivos.

Las pruebas autorizadas usan el entorno PostgreSQL aislado establecido por OP-00. Se reactivó exclusivamente ese clúster y se detuvo al terminar; no se creó otra instancia. No se usan credenciales, datos ni servicios productivos.

## Matriz de aceptación

| Requisito | Criterio verificable | Evidencia al corte |
|---|---|---|
| Balance de componentes | suma de débitos igual al ingreso; saldo previo separado | focal limpio 83/83; regresión global CI aprobada |
| Precisión de litros | acepta escala de 0,01 L y rechaza más precisión sin redondear | focal limpio 83/83; regresión global CI aprobada |
| Diferencia medida | registra y muestra diferencia, retiene liberación/despacho y permite documentar investigación | focal limpio 83/83; regresión global CI aprobada |
| Borrador y transferencia | edición antes de confirmar; saldo, reservas y capacidad se validan antes de confirmar | focal limpio 83/83; regresión global CI aprobada |
| Rectificación documental | vínculo, responsable, motivo y antes/después; snapshots/libro originales permanecen | focal limpio 83/83; regresión global CI aprobada |
| Corrección física | acto y movimientos nuevos idempotentes; balance operativo derivado | focal limpio 83/83; regresión global CI aprobada |
| Despacho y reautorización | tras corrección, nueva muestra/liberación, hoja reautorizada y retry no duplica salida | despacho focal 2/2 y suite limpia 83/83; regresión global CI aprobada |
| Atomicidad y concurrencia | rollback total y sin duplicación o saldo negativo bajo repetición/carrera | focal limpio 83/83; regresión global CI aprobada |
| Interfaz operacional | mostrar balance/actos y explicar retención sin perder la referencia al snapshot | frontend 91/91; navegador 1/1 con API mock local; no es validación de API real |

## CI global aprobada del código

[Run 39469931594](https://github.com/FelipeCCAA/CCAA/actions/runs/39469931594), commit `7d36bbe553d1ce941fe9a1942ff07fd62c4c26d0`, terminó SUCCESS el 2026-10-20:

- [Backend](https://github.com/FelipeCCAA/CCAA/actions/runs/39469931594/job/118791012601): `Ran 1635 tests in 535.218s`, `OK (skipped=5)`. Son 1.630 aprobadas, 5 omitidas, cero fallos y cero errores. Ruff, Django check, comprobación de migraciones y migración en PostgreSQL efímero 17.11 aprobados; la base de test se destruyó correctamente.
- [Frontend](https://github.com/FelipeCCAA/CCAA/actions/runs/39469931594/job/118791012831): 91/91, lint, TypeScript y build aprobados.
- [Production-config](https://github.com/FelipeCCAA/CCAA/actions/runs/39469931594/job/118791012797): aprobado con configuración ficticia, sin conexión productiva ni despliegue.

Los avisos preexistentes `W021` (HSTS preload) e `INEFFECTIVE_DYNAMIC_IMPORT` (`FormularioMaestro`) permanecen, sin bloquear los controles. Esta evidencia corresponde al código citado; el commit posterior de cierre actualiza únicamente este expediente, diagnóstico histórico, backlog y progreso. Una nueva CI automática de ese commit documental no se confunde con esta corrida ya verificada.

## Evidencia de pruebas informada

- Suite focal limpia: 83/83 en 41,264 s, código de salida 0, con `--noinput` y base efímera creada desde cero por migraciones y destruida al terminar. Incluyó `tests_op02_balance`, `tests_op02_actos`, `tests_op02_bloqueos`, `tests_op02_despacho`, `tests_op02_muestreo`, `tests_borrador`, `tests_codigo_vale`, correcciones y reset.
- Corrida focal anterior: 70/70 en 95,833 s con `--keepdb`; se conserva como antecedente y no sustituye la ejecución limpia 83/83.
- Despacho focal: 2/2 en 2,686 s. Incluye flujo completo; tras corregir, pide nueva muestra, nueva liberación y reautorización de hoja; reintentar genera una sola salida.
- Frontend: 91/91. Chrome local: 1/1, dos pasos en 6,4 s y 10,3 s total, exclusivamente con API mock local; no accedió a producción.
- La revisión de interfaz detectó el formulario antiguo de corrección de muestra abierto. La API responde 409; el frontend ahora lo cierra. El test de muestreo backend está incluido y aprobado dentro de la suite limpia 83/83.
- Ruff del backend pasó.
- En el entorno focal se usó la base PostgreSQL efímera reconstruida desde migraciones; la suite 83 la destruyó al terminar. El clúster OP-00 local se detuvo con `pg_ctl` apuntando a su carpeta exacta, exit 0, y se confirmó que `postmaster.pid` no existe. Django check y `makemigrations --check --dry-run` frescos terminaron exit 0.
- CI del commit [`6f8c302`](https://github.com/FelipeCCAA/CCAA/commit/6f8c302): 1.635 pruebas, 3 fallos, 2 errores y 5 omitidas. Dos fallos fueron fixtures de muestra sin fecha; en reset hubo un fallo de confirmación y dos errores por la allowlist faltante de `ActoValeEstandarizacion`. El commit [`7d36bbe`](https://github.com/FelipeCCAA/CCAA/commit/7d36bbe) corrige esas causas; la CI siguiente sobre ese código aprobó la regresión completa.
- La suite backend global local con `--keepdb` terminó con 1.634 pruebas, 17 fallos, 68 errores y 5 omitidas. El resultado quedó contaminado por reutilizar la base después de `TransactionTestCase`, que alteró las semillas de migraciones; no es una aprobación global. La CI siguiente usó una base limpia y aprobó; no se atribuye aprobación a esta corrida local fallida.
- Antecedentes: baseline focal de 14 pruebas y 15 fallos de subcasos; focal de 62 con un fallo de fixture de rol; integrada de 151 con cinco fallos de fixtures; y corrida de 153 con dos errores por helpers ausentes. Se conservan como historia y no se presentan como resultado actual.

La evidencia focal limpia y la CI global del código están aprobadas. Calidad conserva la ejecución histórica CERRADA y su fecha de término; no la reabre para el ciclo correctivo. Las listas de consumo e inventario conservan el snapshot original y muestran también la cantidad operativa derivada. Los tres operadores revisaron escenarios de escritorio, no simulación real de planta ni E2E industrial. Se detectó un punto ciego de genealogía inferida, fuera del alcance OP-02 y reservado a OP-03.

## Criterios de cierre verificados en la rama

- Suites focales limpias de balance, actos, retenciones, Calidad, muestreo, despacho, Inventario y reset pasan; regresión backend completa y frontend pasan en CI del head de código `7d36bbe`; la entrega posterior es solo documental.
- Ruff, Django checks, `makemigrations --check --dry-run` y migraciones en base efímera pasan; la migración `0010` coincide con el modelo.
- Los casos negativos, rollback, repetición/idempotencia, confirmación/saldo y carreras relevantes verifican todas las reglas aprobadas.
- Revisión independiente no encuentra bloqueos técnicos y los escenarios de escritorio de los operadores distinguen revisión operacional de E2E.
- QA/PM reconciliaron resultados y matriz: regresión global del código aprobada; cierre técnico de la rama, sujeto a revisión humana del PR.

El cierre de rama no equivale a UAT industrial, merge, despliegue ni autorización para usar datos productivos. Las acciones sobre balances históricos y el recorrido operacional completo quedan fuera de esta implementación.

## Reproducción y recorrido de revisión

Preparar exclusivamente el PostgreSQL efímero descrito en [OP-00_VALIDACION.md](OP-00_VALIDACION.md). La CI crea su propia base; no usar una base existente de planta. Ejecutar desde `backend/` la suite focal sobre una base de test limpia, sin `--keepdb`:

```text
python manage.py test estandarizacion.tests_op02_balance estandarizacion.tests_op02_actos estandarizacion.tests_op02_bloqueos estandarizacion.tests_op02_despacho estandarizacion.tests_op02_muestreo estandarizacion.tests_borrador estandarizacion.tests_codigo_vale estandarizacion.tests_correcciones usuarios.tests_reset_datos_operacionales --noinput --verbosity 1
```

La regresión global corresponde a `python manage.py test --verbosity 1` en ese entorno efímero. Desde `frontend/`, `npm test` ejecuta las 91 pruebas; `npx playwright test --config=playwright.op02.config.ts` usa el Chrome ya instalado y una API simulada local. Este último recorrido no sustituye las pruebas de API y PostgreSQL.

| Caso con datos sintéticos | Resultado que debe revisar el responsable |
|---|---|
| Componentes 4.000 + 6.000 L y volumen declarado 12.000 L | Rechazo sin transferencia ni modificación parcial del libro. |
| Vale ejecutado de 10.000 L, medición de 9.900 L | Diferencia de −100 L visible, sin ajuste de stock; liberación y despacho retenidos. |
| Adición autorizada de 25,25 L a un vale de 10.000 L | Cantidad operativa 10.025,25 L; original de 10.000 L intacto, dos movimientos nuevos y nuevo ciclo de muestra/Calidad. |
| Repetir la misma solicitud de adición | Un solo acto y un solo par de movimientos; otra carga con la misma clave se rechaza. |
| Intentar corregir físicamente después de consumir o despachar | Rechazo y solicitud de revisión de las áreas afectadas; sin reversión automática. |

Estos casos describen la revisión de software. No son instrucciones para accionar equipos ni una prueba ejecutada en planta.

## AVANCE

- **Trabajo realizado:** balance exacto a 0,01 L; confirmación sin consumo; receta ejecutada protegida; mediciones, rectificaciones y movimientos vinculados; retenciones y nuevo ciclo de Calidad; cantidades operativas coherentes entre Producción, Procesos e Inventario; interfaz e historial.
- **Evidencia:** 83/83 focales sobre PostgreSQL limpio, frontend 91/91 y Chrome 1/1 con API simulada; checks y revisión independiente sin nuevos bloqueos. CI global del código `7d36bbe` aprobada: 1.635 pruebas backend (1.630 aprobadas, 5 omitidas, sin fallos ni errores), 91/91 frontend y controles aprobados.
- **Archivos:** módulos de `backend/estandarizacion`, guardas de `calidad`, `inventario`, `procesos`, `produccion` y `recepcion`; integración del nuevo modelo en el reset restringido de pruebas y sus tests; servicio y pantallas de Estandarización del frontend, pruebas y configuración de navegador. El [manifiesto completo del PR](https://github.com/FelipeCCAA/CCAA/pull/9/files) permite revisar cada archivo.
- **Commits y PR:** implementación `6f8c302`, integración de pruebas `7d36bbe`, [PR #9](https://github.com/FelipeCCAA/CCAA/pull/9) en borrador, sobre la rama documental de PR #8. Sin merge ni despliegue.
- **Revisión independiente:** Arquitectura/PM y revisor backend verificaron diseño y diff; los tres operadores hicieron revisión de escritorio de escenarios de recepción, almacenamiento e inventario/despacho. No se atribuyen pruebas de planta a esas revisiones.
- **Riesgos pendientes:** UAT industrial; balances históricos incongruentes retenidos; genealogía general y afectaciones indirectas fuera de los vínculos explícitos; carga y restauración no probadas. Vaciar completamente un vale mediante retiro requiere revisión y no se automatiza.
- **Próxima tarea:** OP-03, saldo, reservas y ubicación; se puede preparar su diagnóstico conforme a la autorización anterior. Su implementación no está autorizada por OP-02.
- **Decisiones humanas posteriores:** revisión y eventual integración del PR, plan de UAT y tratamiento de históricos; cualquier despliegue o acción sobre producción requiere autorización aparte.

## EXPLICADOR

1. **Problema:** los componentes y el volumen de destino podían no cuadrar; editar un vale ejecutado podía separarlo de los movimientos reales.
2. **Causa técnica:** `transferir_vale` en `backend/estandarizacion/servicios.py` contabilizaba cantidades sin conciliación y faltaba un flujo explícito para corregir conservando los hechos originales.
3. **Ejemplo simulado:** 4.000 + 6.000 L descontados frente a 12.000 L declarados. Es ilustrativo, no un incidente real confirmado.
4. **Solución:** conciliar con las ocho reglas aceptadas y registrar cada corrección como otro acto auditable; precisión de 0,01 L sin inventar tolerancias físicas.
5. **Trabajo realizado:** código en rama y PR #9; receta, movimientos y ejecución original permanecen. Un cambio físico exige nueva muestra y Calidad.
6. **Pruebas y resultados:** 83/83 focales limpias, frontend 91/91, Chrome 1/1 con API simulada y checks aprobados. CI global aprobada: 1.635 pruebas backend, 5 omitidas, sin fallos ni errores; revisión de escritorio no equivale a UAT industrial.
7. **Estado final:** VALIDADO MEDIANTE PRUEBAS en la rama; pendiente de revisión humana y UAT industrial, no instalado en producción.
