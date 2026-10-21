# OP-04 — Secado y FIFO

**COMPLETADA EN LA RAMA.** Código y pruebas validados en `1e2098d`; [PR #11 borrador](https://github.com/FelipeCCAA/CCAA/pull/11), sin fusionar ni desplegar. El commit de cierre posterior modifica sólo este expediente, TASK_BACKLOG.md y PROGRESS.md.

## Alcance autorizado

Implementación en `codex/op-04-secado-fifo`, desde OP-03 `5fd3d89`. El usuario validó las seis reglas y autorizó código, pruebas y PR para revisión. Sin producción, despliegue, merge, inventario real ni contratación. No se utiliza Supabase. Se conserva el esquema existente: no se añade migración ni se hace backfill.

| Regla aprobada | Implementación |
|---|---|
| Origen real y cantidad efectivamente consumida | `crear_secado_desde_inventario` registra entrada y consumo del lote; `cerrar_secado` contrasta entradas con el libro físico. Rechaza entradas sin evidencia o con un mismo silo duplicado. |
| Unidades explícitas | Inventario externo en kg. Los orígenes de silo conservan L; cerrar requiere kg medidos y referencia del registro. No convierte litros ni inventa densidad, rendimiento o tolerancia. |
| FIFO decidido por servidor | Inventario: primer lote compatible utilizable con saldo libre, ordenado por recepción/lote/existencia. Leche entera del vale: silo compatible con capa física más antigua, Calidad/CIP/retención/reservas revalidados. La sugerencia del cliente no autoriza el retiro. |
| Excepción con evidencia | Elegir otro origen exige motivo y registra recomendado/utilizado, actor y fecha. No habilita material rechazado, reservado o insuficiente. |
| Consumo atómico e idempotente | UUID estable por solicitud; bloqueo de operación y filas, comparación de carga y recuperación del resultado. Error revierte lote, consumo, cierre y eventos de esa transacción. |
| Cierre trazable | Conserva alimentación, polvo, finos y merma; exige firma vigente para salida intermedia y mantiene el circuito de Calidad del producto. No inventa consumos históricos. |

## Contrato y archivos

- `backend/procesos/servicios.py`: inicio externo, cierre, evidencia de consumo, retiro físico de continuación, recuperación por UUID y bloqueos compatibles con OP-03.
- `backend/procesos/serializers.py`: UUID obligatorio, referencia kg, metadatos del servidor protegidos y lista de orígenes de alimentación.
- `backend/procesos/views.py`: opciones FIFO utilizables e inicio nuevo 201 / recuperación exacta 200.
- `backend/estandarizacion/servicios.py`: decisión FIFO al ejecutar el vale; evento de confirmación o excepción.
- `backend/calidad/vigencia.py`: corrección de `AnalisisSilo` comparte el bloqueo del silo con los retiros; evita modificar Calidad entre comprobación y confirmación física.
- `frontend/src/pages/Secado/{InicioSecadoExterno,CierreSecado}.tsx`, `frontend/src/services/{secado.service,secado-operacion}.ts`: origen/unidad, motivo, referencia y recuperación de respuesta incierta con misma clave/carga.
- Pruebas nuevas: `backend/procesos/tests_op04_secado.py`, `backend/estandarizacion/tests_op04_fifo.py`, `frontend/tests/op04-secado.test.ts`, `frontend/op04-ui/`. Fixtures heredados de Secado/suero incorporan origen físico y UUID exigidos, sin debilitar verificaciones.

Tablas existentes: `CorridaSecado`, `EjecucionProceso`, `EntradaProceso`, `SalidaProceso`, `EventoProceso`, `ReservaSiloProceso`, `Lote`, `OrdenProduccion`, `LoteInventario`, `Existencia`, `MovimientoInventario`, `Silo`, `MovimientoSilo`, `AnalisisSilo` y liberaciones/firma de Calidad. Sin tabla nueva ni alteración de estructura.

`POST /api/procesos/secados/iniciar-desde-inventario/` añade `operacion_id` UUID y `excepcion_fifo_motivo` opcional. `POST /api/procesos/secados/{id}/cerrar/` añade `operacion_id` y `referencia_medicion_kg` cuando el origen está en L. Una clave reutilizada con distinta carga se rechaza. `_op04` en controles es evidencia reservada del servidor. Repetir una operación confirmada recupera su resultado, sin volver a producir ni consumir; no equivale a una nueva autorización de uso.

FIFO externo se decide en una consulta SQL de candidatos durante la confirmación. El elegido y su stock/Calidad se bloquean; no se impone orden global de commit a reposiciones concurrentes. El evento conserva ganador y saldo libre del snapshot, con `fifo_evaluado_en` como inicio de evaluación inmediatamente anterior a esa consulta. Bloquear todos los lotes fue descartado por invertir el orden de `registrar_entrada` y provocar interbloqueos. En leche se bloquean los silos candidatos en orden común; no se añade FIFO nuevo para todos los componentes de mezcla ni reparto automático entre varios orígenes.

## Evidencias

Antes del cambio se reprodujeron seis fallos: cuatro casos Secado (cierre sin origen, litros sin referencia kg, salto FIFO y reintento rechazado) y dos FIFO del vale (sugerencia omitida o falsificada). Las salidas se conservan localmente en `../op00-runtime/op04-baseline-{secado,fifo}.log`.

Las pruebas de base de datos se ejecutan exclusivamente mediante el harness OP-00: PostgreSQL 17 local, `127.0.0.1:55439`, rol `op00_test`, directorio `../op00-runtime/pgdata`; valida identidad antes de Django y rechaza `.env`. Datos sintéticos y bases desechables. Las pruebas concurrentes usan conexiones independientes y observan bloqueos reales en `pg_blocking_pids`; las pruebas de navegador usan API simulada y bloquean servicios externos.

Código/pruebas: commit `1e2098d89ffc422471b9aa247ccb0b82af82c4bc`. [PR #11 borrador](https://github.com/FelipeCCAA/CCAA/pull/11), apilado sobre OP-03 #10. Revisión independiente final por lectura sin bloqueantes pendientes; no ejecutó BD. Tres subagentes: backend y revisión `gpt-6-sol high`, frontend `gpt-6-luna medium`; PM/AVANCE/EXPLICADOR integrados por el coordinador.

| Comprobación local | Resultado |
|---|---|
| Primera integración Secado/FIFO y heredadas | 35 pruebas, 34 aprobadas y un error de fixture (EtapaProceso sin orden), 56,473 s. Se corrigió únicamente el fixture. |
| Integración limpia: Secado/FIFO, heredadas, vigencia/concurrencia Calidad y FIFO Recepción | 68/68 en 158,219 s, exit 0; base creada desde migraciones y destruida. Log `op04-integracion-final.log`. La última extensión CIP y su guarda son posteriores al arranque/importación de esta ejecución; su validación definitiva corresponde a CI del commit final. |
| Estandarización completa previa | 166/166, 64,529 s; anterior a la última protección de escritura de AnalisisSilo. No sustituye CI final. |
| Frontend | 101/101, 3,458 s; lint y build/TypeScript exit 0. Aviso preexistente `INEFFECTIVE_DYNAMIC_IMPORT` de FormularioMaestro, sin cambiarlo. |
| Chrome final con API simulada | 5/5 en 51,7 s, log `op04-ui-validado.log`. FIFO/unidad, equipo ocupado, respuesta perdida, misma clave y corrección tras rechazo. |
| Estática/configuración | Ruff backend, Django check, `makemigrations --check --dry-run` y diff-check aprobados. Sin cambios de migración. |

Los primeros ensayos Chrome detectaron dos selectores ambiguos y, al corregir fixtures para representar inventario kg/silo L, una comprobación de unidad antes de seleccionar origen. Se corrigieron localizadores/momento de comprobación; la última corrida 5/5 usa los fixtures finales. La prueba se repitió por cambios concretos, no se contó la ejecución fallida como aprobada.

El clúster local quedó detenido mediante `pg_ctl -D` apuntando a su directorio exacto; exit 0 y ausencia de `postmaster.pid` verificada. `DevelopMain` sigue en `d34df44ca30c402e9da34dc7b75f7652c2751fef` al consultar GitHub después de publicar el PR.

**CI final SUCCESS:** [39637476601](https://github.com/FelipeCCAA/CCAA/actions/runs/39637476601), commit `1e2098d89ffc422471b9aa247ccb0b82af82c4bc`. [Backend](https://github.com/FelipeCCAA/CCAA/actions/runs/39637476601/job/119351835884): `Ran 1696 tests in 378.453s`, `OK (skipped=5)`: **1.691 aprobadas, cinco omitidas preexistentes, cero fallos/errores**; incluye los 22 casos nuevos de Secado/FIFO y la extensión CIP final. Ruff, Django checks, migración efímera y comprobación de ausencia de migraciones nuevas aprobados. [Frontend](https://github.com/FelipeCCAA/CCAA/actions/runs/39637476601/job/119351835583): **101/101**, lint, TypeScript y build aprobados. [Configuración](https://github.com/FelipeCCAA/CCAA/actions/runs/39637476601/job/119351836052): aprobada. PostgreSQL 17 en CI efímera. El cierre documental posterior no cambia código ni pruebas; su CI separada no se declara aprobada anticipadamente.

Manifiesto completo: [20 archivos del PR](https://github.com/FelipeCCAA/CCAA/pull/11/files). Los comandos y logs locales se ejecutaron sobre datos sintéticos; el resultado global proviene del head exacto señalado, no de extrapolar pruebas focales.

Reproducción, exclusivamente en PostgreSQL sintético con configuración CI y sin `.env` productivo:

```text
python manage.py test estandarizacion.tests_op04_fifo procesos.tests_op04_secado procesos.tests_secado procesos.tests_flujo_suero calidad.tests_op01_vigencia calidad.tests_op01_concurrencia recepcion.tests_fifo recepcion.tests_sugerencia_fifo --noinput --verbosity 1
python manage.py test --verbosity 1
```

En `frontend`: `npm test`, `npm run lint`, `npm run build`; Chrome instalado: `npx playwright test --config op04-ui/playwright.config.ts`. El harness de navegador levanta sólo localhost:5194 y no envía peticiones a servicios reales.

## Recorridos de operadores (DESK)

Se reutilizaron los agentes necesarios para cubrir perspectivas operacionales; son simulaciones de escritorio sobre código/pruebas, no tres operadores humanos ni UAT de planta.

- **Recepción (coordinador):** silo antiguo utilizable se recomienda; si está retenido, CIP, rechazado o totalmente reservado, se excluye. Omitir/falsificar la sugerencia no evita justificar el silo nuevo. Una corrección concurrente de inhibidores espera el retiro que ya está confirmándose; una corrección confirmada previamente impide el uso. Evidencia: `tests_op04_fifo`, incluidas la API y dos conexiones reales.
- **Producción (backend):** continuación de 600 L conserva esa unidad; 600 kg declarados y ticket son otro registro. Sin firma no retira. Con firma y CIP activo no retira; CIP terminado permite el cierre. Repetir UUID/carga recupera un solo retiro. Evidencia: caso de continuación y cierre desde vale; extensión CIP validada por CI final.
- **Bodega (frontend):** lote externo kg muestra saldo/unidad/FIFO. Elegir uno posterior exige motivo; los reservados o no utilizables se filtran y el servidor revalida. Si se pierde la respuesta, recuperar reenvía la misma carga/UUID. Chrome prueba interfaz/reintento, sin caso de navegador específico para los filtros de Calidad/reservas; sus guardas se verifican en backend.

## Límites operacionales y reversión

La referencia de kg es una declaración identificada por operador; no integra ni certifica una báscula o documento externo. Los finos/merma quedan registrados en el balance, sin crear destinos de inventario no definidos. Preparación Protomalt y genealogía histórica sin respaldo siguen pendientes; no se activan rutas ni se reconstruyen consumos automáticamente. Los registros ambiguos fallan de forma conservadora y necesitan revisión humana.

Los contratos nuevos requieren actualizar conjuntamente interfaz y backend en un futuro despliegue autorizado. Aquí sólo se prepara la rama. Los reintentos se conservan mientras el formulario siga abierto; al recargar o cerrar la sesión debe consultarse el historial antes de iniciar otra operación. No se certifica carga de 70 usuarios, UAT de planta, respaldo/restauración ni ausencia de cualquier fallo ajeno a este alcance.

Para revertir la propuesta no fusionada basta no integrarla. Si posteriormente se autoriza desplegarla, conservar eventos/controles y movimientos confirmados: revertir código no significa borrar consumos ni historia. Sin migración nueva para revertir.

## Continuidad

OP-05 (Mantequilla) tiene dependencia OP-03 satisfecha en rama. Próxima actividad permitida: diagnóstico acotado y propuesta de reglas sobre consumo de crema, cierre, merma y liberaciones. Su implementación requiere autorización específica; no se inicia aquí. Mazada y tolerancias industriales siguen sujetas a definición de planta.

## EXPLICADOR — OP-04

1. **Problema:** Secado podía cerrar sin demostrar de dónde salió la alimentación y algunos reintentos/saltos FIFO no quedaban controlados.
2. **Causa:** inicio, cierre y recomendación no compartían un contrato verificable de origen, unidad y operación única.
3. **Ejemplo:** si se pierde la respuesta al alimentar la torre, repetir no debe descontar otra vez; declarar 600 kg tampoco demuestra por sí solo un retiro del silo.
4. **Solución:** enlazar origen y retiro, conservar unidades y recuperar la misma operación; las excepciones FIFO llevan motivo.
5. **Trabajo real:** backend, interfaz y pruebas coordinadas por PM; revisión independiente; sin nueva estructura de base de datos.
6. **Pruebas:** CI 1.696 backend (1.691 aprobadas, cinco omitidas), 101 frontend y Chrome local 5/5 con API simulada; 68 focales locales y carreras PostgreSQL. Sin UAT industrial.
7. **Estado:** VALIDADO MEDIANTE PRUEBAS EN LA RAMA. CI global aprobada; revisión humana del PR, UAT y eventual despliegue siguen separados. No se modificó producción.


## AVANCE final

- Completado: implementación y validación de las seis reglas OP-04 en rama, sin habilitar producción. Evidencia global CI SUCCESS en `1e2098d`, más Chrome local 5/5 y suite integrada 68/68.
- Entrega: commit `1e2098d`, PR #11 borrador sobre OP-03 #10; cierre posterior sólo documental. Archivos y funciones arriba y manifiesto del PR. TASK_BACKLOG.md y PROGRESS.md actualizados.
- Riesgos pendientes: medición declarada y evidencia histórica necesitan revisión operacional; sin carga certificada, UAT ni prueba de backup/restauración. Las ramas OP anteriores todavía no están fusionadas.
- Próxima tarea: OP-05, diagnóstico/reglas de Mantequilla; no implementada.
- Decisiones: revisión humana de PR y dependencias antes de cualquier integración; autorización aparte para producción/despliegue o para implementar OP-05. No se necesita contratar servicios ni entregar credenciales para completar esta entrega.
