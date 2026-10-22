# H09-01 — Firmas de polvo por etapa

Usuario validó las seis reglas propuestas y autorizó corrección en rama, pruebas y PR, sin producción ni despliegue. Base OP-09 `fc020300`; rama `codex/h09-01-firmas-por-etapa`, implementación `124d56e`. [PR #17 borrador](https://github.com/FelipeCCAA/CCAA/pull/17), apilado sobre OP-09 #16. **IMPLEMENTADA Y VALIDADA PARA REVISIÓN: circuito real, regresiones y CI de implementación aprobados; sin fusionar ni desplegar.**

## Problema reproducido y alcance

La firma v1 de una salida fotografiaba también equipo, kg, bultos y estado globales del lote. Preparar/cerrar Secado cambia esos campos legítimamente; así vencía Evaporación y Envasado rechazaba material ofrecido por la bandeja. Además, corregir un origen no retiraba siempre las firmas consumidoras. Baseline: siete regresiones, seis fallos y un rechazo de firma durante avance normal. Crudo `h09-runtime/regresion-red.log`.

Se conserva recepción/estandarización, balances, unidades, recetas, tolerancias, reservas/FIFO, permisos existentes y contabilidad física. No se cambia inventario real ni se inventan criterios industriales. Sólo dos ejecutores: coordinador desarrolla/integra/AVANCE, un apoyo reutilizado (`op08_revision`, gpt-6-sol high) aporta pruebas y revisión independiente de producción. No dieciséis agentes.

## Contrato y cambios

| Regla validada | Implementación | Evidencia prevista/obtenida |
| --- | --- | --- |
| Firma por salida/etapa | Foto JSON v2 en `calidad/vigencia.py`: material, identidad del lote, etapa/ejecución/equipo propios, entradas, análisis/especificación y antecedentes explícitos | Regresiones por etapa; circuito de polvo real |
| Avance normal conserva etapas anteriores | Foto de proceso excluye equipo/kg/bultos/estado global del lote; estado de ejecución no forma parte de su evidencia material | Evaporación y Secado mantienen versión 0 y un acto de firma cada uno después de Envasado/Bodega |
| Correcciones exigen revisión | `EvidenciaCalidadMixin` cubre ahora Etapa/Ejecución/Entrada; escritura/borrado normal invalidan dentro del commit; relaciones releídas bajo lock | Cantidad, análisis, equipo propio, entrada, maestro/identidad estables; retorno A→B→A no reactiva |
| Sólo dependencias reales y sin revertir stock | Cascada por `EntradaProceso.salida_origen_id → ejecución → salidas`; retira decisiones y liberación final, conserva UUID/foto anterior y auditoría | Origen sin firma, lotes/productos diferentes, hermana independiente, despacho previamente autorizado sin salida física |
| Bandeja y confirmación coherentes | GET y POST usan la misma comprobación de vigencia; bloqueados incluyen ejecuciones cerradas y scope de sucursal; motivo muestra la etapa pendiente, no la nota antigua conforme | Bandeja/POST, proyección sin escribir decisiones, recorrido web |
| Renovación explícita y confirmación protegida | Calidad autorizada emite nuevo UUID; fuentes antes de decisiones, cadenas unidas y ordenadas antes de salidas individuales; relectura de relaciones y evidencia | Rechazo de operador, renovación por API y dos carreras PostgreSQL con bloqueo observado |

Archivos de aplicación: `backend/calidad/{etapas,evidencia,vigencia,views}.py`, `backend/procesos/{models,servicios}.py`, `backend/produccion/{servicios,views}.py`, `backend/inventario/servicios.py`. Pruebas nuevas: `backend/calidad/tests_h09_firmas_etapa.py` (18 casos); fixtures positivas de `backend/produccion/tests_envase.py` ahora incluyen firmas versionadas reales y revalidación explícita tras corregir material.

La jerarquía evita adquirir un lote ancestro después del lote consumidor: sus cambios estables retiran las decisiones dependientes en la misma transacción. Se bloquean las salidas/ejecuciones/entradas/análisis de la unión de cadenas; la foto se vuelve a comprobar bajo la decisión. Calidad, continuación y despacho adquieren la unión antes de su primera salida individual. Un nuevo origen o ciclo detectado durante la espera rechaza la operación.

## Compatibilidad y límites

Sin migraciones de esquema ni backfill. Firmas v1 mantienen **comparación estricta con su algoritmo original**, sin convertir la foto ni adjudicar nueva firma automáticamente. Cuando caduquen, Calidad debe revisar y renovar explícitamente, pasando a v2. Un histórico sin firma verificable sigue bloqueado. No se reconstruyen vínculos históricos faltantes por compartir lote/silo: requiere revisión antes de cualquier despliegue futuro. Las rutas nuevas de continuidad ya registran la arista explícita.

Una consulta de trabajo es informativa: el POST revalida dentro de la transacción. Recuperar un UUID ya confirmado de Envasado conserva la idempotencia OP-08 y no ejecuta una producción nueva. Retirar aprobaciones no borra pallets, movimientos ni despachos ya realizados ni revierte cantidades automáticamente.

## Entorno aislado

Clúster PostgreSQL17 nuevo: `h09-runtime/pgdata`, usuario `h09_test`, loopback55459; base `h09_firmas`, test desechable `test_h09_firmas`. Restaurado exclusivamente el respaldo **ficticio** de OP-09, incluyendo archivo privado; fuente OP-09 conservada. `qa/h09/manage_isolated.py` verifica ruta/rol/host/puerto/catálogo, rechaza `.env` de aplicación y reutiliza entorno test limpio: correo en memoria, tareas eager, sin broker/worker/beat. Sin Supabase/logs, credenciales productivas, contrataciones ni despliegues.

Web5209/API8209 exclusivamente loopback, servidor de desarrollo. El servidor anterior OP-09 fue sustituido sólo después de verificar sus PID; ningún programa ajeno se cerró. La interfaz local queda disponible sobre la copia H09, no sobre datos de planta. No se repiten las cargas de OP-09 ni se certifica su capacidad.

## Circuito real de polvo

Handoff `H09-POLVO-195563`, lote10. Parte de un vale ficticio ya liberado; no se volvió a probar recepción. Evaporación web `web-evaporacion-2.log`: 2/2 incluyendo sesión, paso operativo14,0s; total1,6min. Produce salida13 de1.500L. Continuación conserva ese lote: preparación y cierre real de Secado **sin refirmar Evaporación**. Polvo salida14 de500kg; Calidad de polvo, pallet `PAL-H09-POLVO-195563`, liberación final y entrega a Bodega, observado en Inventario/PT-DISP. Corte final `web-polvo-continuacion-2.log`: 1/1, paso2,1min, total3,0min.

`powder-browser-evidence.json` confirma ambas firmas v2 vigentes, versión0, **un acto de firma cada una**, liberación comercial vigente, pallet500kg en Inventario y existencia activa/PT-DISP. No es una API simulada ni dos lotes distintos presentados como uno. Se documenta el circuito en cortes porque hubo fallos de preparación/selectores antes de completarlo; no se declara una única corrida limpia desde recepción.

Fallos preservados:

- Primera Evaporación: preparador genérico había programado precondensado en vez de polvo. Se creó sólo la orden ficticia faltante mediante `qa/h09/prepare_powder.py`; no material/resultados. `web-evaporacion-1.log`, carpeta `web-fallo-sin-orden`.
- Primera continuación completó Secado, pero esperaba una bandeja global vacía antes de Calidad final. Existía mantequilla habilitada de otro ensayo. Se acotó la aserción al lote y se reanudó desde paso4, sin duplicar Secado ni añadir firma de Evaporación. `web-polvo-completo-1.log`, carpeta `web-fallo-assert-global`.
- Regresión inicial ampliada84: dos fixtures de Envase sólo escribían estado liberado sin firma y una aserción de carrera estaba fuera de `atomic`; corregidas las precondiciones, no debilitados los rechazos.
- Corte30: una fixture cambiaba producto/cantidad y seguía esperando permiso sin refirma; ahora exige bloqueo y representa una nueva firma explícita antes del caso positivo.
- Corte86: única aserción errónea esperaba pallet liberado cuando ya estaba en Inventario. Corregida a conservar su estado físico real. No se declara ese corte86 como aprobado.

Cantidades/análisis del E2E son ficticios y reutilizan sus datos existentes: no son una receta ni una validación de rendimiento físico del polvo.

## Controles y evidencias de cierre

Ruff backend/QA, Django check y esquema sin cambios aprobados. Frontend **111/111**, cero omitidas; lint y build con TypeScript aprobados. Regresión local completa: **1.823 ejecutadas, 1.818 aprobadas y cinco omitidas**, 1.536,216s. Esa corrida comenzó antes de los últimos ajustes de borrado/proyección y dos nuevos casos: no se presenta como verificación integral del código posterior.

Corte focal **fresco sobre la implementación publicada: 88/88, ninguna omitida**, 166,992s. Incluye las 18 nuevas regresiones, Envasado, firmas OP-01, concurrencia y Despacho. Las dos carreras nuevas observan realmente PID bloqueado en PostgreSQL; el despacho autorizado se rechaza tras corrección del ancestro sin movimiento ni baja de stock. No sumar cortes solapados como pruebas únicas.

**CI de `124d56e2a9602641f0d83fd980b245a9de00e8fe`: SUCCESS**, [run39819878080](https://github.com/FelipeCCAA/CCAA/actions/runs/39819878080). Backend final **1.825 ejecutadas, 1.820 aprobadas y cinco omitidas**, 500,647s; frontend, almacenamiento privado efímero y comprobación de configuración también aprobados. Las omitidas no se cuentan como aprobadas. Mismo código de aplicación que la entrega: el cierre posterior sólo añade documentación y herramientas/evidencia QA de lectura; su CI adicional no se anticipa aprobada.

Crudos en `../h09-runtime/`; scripts de prueba en `qa/h09/`, configuración de navegador `frontend/h09-ui/playwright.config.ts`. Resúmenes versionados en `docs/operacion/evidencias/h09-01/`: `validation.json`, `powder-browser-evidence.json`, `ci-implementation.json` y manifiesto SHA256 de **19 archivos crudos**, incluidos fallos previos. `qa/h09/collect_evidence.py` sólo copia la lista permitida; nunca sesiones, credenciales, contenido privado o dump. El informe de OP-09 permanece como diagnóstico histórico; corregir H09-01 no aprueba sus ensayos de carga incompletos ni demuestra preparación productiva.

Revisión independiente de cierre: **19/19 hashes y tamaños coinciden** con los crudos; cuatro JSON sin sesiones, credenciales, dump ni archivos privados. Conteos y evidencias del circuito coherentes con el commit de aplicación, sin defecto material identificado en la lectura focal. No sustituye pruebas no ejecutadas ni una validación industrial de planta.

Reversibilidad del trabajo: rama separada, sin cambios de esquema ni escrituras productivas; conservar datos/evidencias H09. Un despliegue o reversión real requiere su propio plan de revisión de firmas abiertas/históricas; no ejecutar actualización masiva para hacerlas pasar.
