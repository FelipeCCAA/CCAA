# F01/F02 — saldo y origen material de estandarización

Fecha: 26-10-2026, Chile. Rama `codex/f01-f02-saldos-genealogia`, base `580f26c` (expediente OP09/PR19). **Casos de origen único implementados y validados localmente; F02 parcial para mezclas, históricos y composición de correcciones. No cierre general de OP09 ni autorización para planta.**

## Autorización y alcance

El usuario indicó que el equipo continuara después del plan de correcciones operacionales. Se toma primero F01/F02: saldos y vínculo Descremado→vale→lote. Un coordinador desarrolla/integra y un apoyo implementa el lector de tramos y revisa de forma independiente los demás cambios. No se repite la auditoría general. Se usan las guías code-work, code-verification y procesos lácteos, con revisión React.

Sin producción, despliegues, contratación, Supabase, lectura de logs de Supabase, cambio de tolerancias ni reescritura de inventario. No se implementa offline, infraestructura cloud, mantequilla F03, checklist F04 ni F05–F07. No se modifica `sources/`. El libro OPFLOW del ensayo anterior se conserva; no se usa para reparar historia ni fingir un nuevo recorrido por pantalla.

## Contrato de esta entrega

1. Un vale nuevo que retira de una salida identificable de Descremado conserva `EntradaProceso.salida_origen` junto con silo y litros. El movimiento físico existente se ejecuta una sola vez; no se crea otro retiro por añadir el vínculo.
2. La salida productora debe tener corrida real, ingreso único correlacionado por corrida/silo/operación/cantidad, tanque vacío antes de ingresar y ningún ingreso posterior que vuelva ambigua la composición. Su saldo documental debe conciliar con el físico y su aprobación estar vigente. La ruta debe continuar en Estandarización.
3. **Varias fuentes positivas en un TK se bloquean, incluso si el cliente intenta elegir una.** Seleccionar un ID no demuestra composición física. No se introduce FIFO ni prorrateo nuevo para los componentes. Mezclas, salidas no soportadas y discrepancias históricas requieren una definición/reconciliación posterior, no se imputan automáticamente. Las entradas crudas o heredadas sin ninguna `SalidaProceso` mantienen su contrato de entrada por silo, sin inventarles lote: su genealogía industrial sigue incompleta.
4. El lote que toma leche del vale enlaza su entrada a la salida explícita de ese vale. Un ingreso ajeno o saldo previo mezclado impide atribuir la extracción exclusivamente a ese vale. Adiciones propias OP02 conservan su contrato; su atribución industrial detallada sigue requiriendo cobertura específica.
5. Genealogía atraviesa salidas sin lote, conserva lotes reales, cantidades/unidades por tramo, dirección, cota de profundidad y ciclos acotados. No convierte el vale en un lote ficticio ni atribuye los 4.300,53 L de componente íntegros a un lote que toma sólo 6.000 L de una mezcla de 15.000 L. Grafos directos conservan su consulta por nivel.
6. Calidad conserva el acto de decisión del vale; no se inventa una nueva `LiberacionProceso` para Estandarización. Las firmas v2 posteriores capturan ese antecedente y las correcciones del material real retiran las decisiones dependientes. No se convierten firmas históricas ni se hace backfill.
7. Disponibles nunca ofrece más que el físico libre de reservas. Para continuidad a Estandarización, los orígenes ambiguos/no conciliados no se ofrecen como consumibles. Silos conserva el saldo físico, aun cuando ese saldo no sea operable por falta de identidad.
8. La pantalla Estandarización muestra fuente y motivo de bloqueo. `Actualizar vales y saldos` vuelve a consultar el catálogo, sin reutilizar sus diez segundos de caché local. Esto no implementa avisos o actualización automática entre usuarios.

## Evidencia requerida

| Requisito | Comprobación |
| --- | --- |
| Saldo y retiro único | Fuente 9.150,08 L − consumo 4.300,53 L = 4.849,55 L, una entrada material y un retiro físico |
| Reintento/parciales | Mismo vale no duplica; segundo vale consume su parte y ambos saldos concilian |
| Procedencia verificable | Rechazo de varias fuentes, ingresos ajenos, saldo previo y discrepancias aun si el volumen total coincide |
| Transacción | Fallo tardío conserva estado, libro y fuentes sin escrituras parciales |
| Carrera | Dos conexiones esperan realmente el mismo origen; sólo un vale puede consumir 6.000 L de los 9.150,08 L disponibles |
| Genealogía | Atrás/adelante, tramos sin lote, rutas mixtas directas/intermedias, legado sin relación explícita y profundidad |
| Calidad | Fuente obsoleta rechazada; una corrección de análisis retira la firma del producto descendiente; avance normal mantiene contrato |
| Regresión | OP02 actos, reservas OP03, OP05 conteo único, H09 firmas, presupuesto de consultas y frontend |

Entorno: harness OP00, PostgreSQL17, rol `op00_test`, carpeta dedicada `../op00-runtime/pgdata`, loopback55439; bases `op00_base` / `test_op00_base`. Identidad verificada antes de cada llamada, `.env` rechazado, entorno limpio sin credenciales externas; Django crea y elimina la base efímera. No migraciones de esquema en esta entrega.

## Registro de validación

- Baseline: seis regresiones, cinco fallos esperados y un reintento aprobado. Expone falta de vínculo, sobreoferta, firma obsoleta aceptada y ausencia de bloqueo por ambigüedad/legado.
- Primera focal: error de importación de `ReservaSiloProceso`, corregido. No se declara aprobada.
- Integración1: 69 ejecutadas, dos errores de preparación: ciclo rechazado correctamente por H09 y fixture OP05 que esperaba saldo sin ingreso físico. Se usa inserción test-only para legado corrupto; se añade ingreso ficticio a la fixture OP05, sin debilitar producción.
- Integración2: 71 ejecutadas, un error en preparación de carrera al firmar fuera de transacción. La firma se prepara en una transacción confirmada antes de lanzar conexiones competidoras. No se declara aprobada.
- Integración3 y primer corte de cierre:141 ejecuciones aprobadas; se preservan ambas corridas sin sumarlas como cobertura independiente.
- **Corte final por identidad:**143/143, ninguna omitida, en78,702s, exit0. Se verificaron143 identidades distintas en el registro, sin duplicados;25 son casos nuevos de materiales, carrera y genealogía. Incluye saldo9.150,08−4.300,53=4.849,55, segundo retiro parcial, reintento, rollback, firma obsoleta, corrección de ancestro, composición ambigua, ingreso posterior compensado, saldo previo compensado, producto parcialmente consumido, advertencia de correcciones y espera real de ambas conexiones competidoras. La carrera confirma un solo vale de6.000 L y remanente3.150,08 L.
- Frontend111/111, cero omitidas; lint y build con TypeScript aprobados en versión final. Ruff de todo backend y diff-check aprobados. Esquema: `No changes detected`, exit0. Los system checks del runner final reportan cero problemas.
- CI global de implementación `9272269`, [run40331871048](https://github.com/FelipeCCAA/CCAA/actions/runs/40331871048): frontend, almacenamiento privado y configuración aprobados; backend ejecutó1.850, con1fallo,1error y5omitidas. Ambos casos antiguos de `CierreDescremacionTests` creaban salidas documentales sin ingreso físico. Se completaron sólo sus fixtures con ingresos ficticios correlacionados; no se relajó la guarda de disponibilidad ni se cambiaron aserciones. Verificación local posterior:31/31 identidades únicas, cero omitidas/fallos/errores,14,905s; Ruff y diff-check aprobados. [Evidencia separada del seguimiento](evidencias/f01-f02/ci-followup/summary.json); no reemplaza el corte original.
- No se ejecutaron navegador, carga ni un circuito industrial completo en esta corrección. [PR20 en borrador](https://github.com/FelipeCCAA/CCAA/pull/20); nueva CI global pendiente tras el ajuste de fixtures, sin anticipar aprobación.

Los registros crudos están en `../op00-runtime/f01-f02-*.log`. [Resumen, identidades, salidas de validación y manifiesto](evidencias/f01-f02/summary.json), publicados sin credenciales ni datos privados. `manifest.json` conserva bytes/SHA256 de15 archivos y el resumen incluye hashes de17 archivos fuente/pruebas afectados. La RAM del equipo compartido alcanzó87% con controles paralelos; se continuó secuencialmente tras bajar. No se atribuye ese consumo a CCAA ni se usa para certificar carga.

## Cambios y revisión

Backend: `estandarizacion/origenes.py`, transferencia y catálogo; registro de estandarización y consulta de disponibles; enlace del lote al vale; fotos/antecedentes de Calidad; lector de genealogía y timeline. Frontend: fuente/bloqueo y recarga de saldos en Estandarización; tramos materiales en Trazabilidad; contratos de servicio. Pruebas nuevas de materiales, carrera y genealogía, más fixture física OP05 corregida. No cambian modelos, migraciones, dependencias, recetas ni reglas de aprobación industrial.

Revisión independiente detectó y llevó a retirar la propuesta de seleccionar una fuente dentro de un tanque mezclado. También exigió evitar una sobreoferta por aplicar el mismo saldo físico a varias fuentes y verificar IDs bloqueados. El cierre estático no encontró otro bloqueante material en el alcance acotado. Señaló composición de correcciones OP02 y posible costo de releer fuentes/libro por salida en bandejas grandes; no hay medición de rendimiento que cierre ese riesgo. La API y pantalla ahora advierten explícitamente que las correcciones físicas no están atribuidas en estos tramos. La revisión no constituye aceptación industrial.

## Continuidad y reversión

Trabajo en rama separada y PR apilado para revisión; no merge con DevelopMain. Revertir código en desarrollo no autoriza eliminar entradas, movimientos ni evidencia confirmada. No se ejecutan migraciones ni operaciones del ensayo OPFLOW: verificar la coincidencia de versiones UI/API antes de repetirlo.

Pendientes: política de identificación/composición para TK mezclados, conciliación aprobada de históricos, atribución de adiciones/correcciones, recorrido por navegador y repetición operacional integral. F03 balance graso es la siguiente corrección del plan, pero sus tolerancias requieren validación industrial. Precondensado mantiene sus500 L bloqueados por especificaciónSILO faltante en OPFLOW.

## AVANCE

Corrección acotada implementada en rama y validada localmente:143 backend únicos,111 frontend, lint/build/esquema/diff aprobados. Se conserva producción intacta y el ensayo original. No se declara F01/F02 resueltos para todas las mezclas ni OP09 completada. PR apilado para revisión, sin merge ni despliegue; CI separada.

## EXPLICADOR

1. **PROBLEMA DETECTADO:** una consulta ofrecía leche ya usada y faltaba el vínculo del material entre Descremado, vale y producto.
2. **CAUSA TÉCNICA:** ciertas entradas sólo guardaban el silo; la genealogía no recorría salidas sin lote y las consultas sumaban evidencias físicas/materiales parcialmente.
3. **EJEMPLO REAL DE OPERACIÓN:** retirar4.300,53 L de9.150,08 L debe dejar4.849,55 L, no volver a ofrecer9.150,08 L. Un lote parcial conserva cantidades por tramo, sin apropiarse de toda la mezcla.
4. **SOLUCIÓN RECOMENDADA:** enlazar fuentes verificables, conciliar físico y material, respetar firmas y bloquear composiciones que no se pueden demostrar.
5. **TRABAJO REALIZADO POR LOS AGENTES:** un coordinador implementó servicios/contratos/pantallas; un apoyo implementó el lector y revisó el resto. Sin esquema ni datos productivos modificados.
6. **PRUEBAS Y RESULTADOS:**143 backend únicos/111 frontend aprobados, carrera real de dos vales y controles finales. Baseline y fallos intermedios preservados; sin navegador ni aprobación de capacidad.
7. **ESTADO FINAL:** **VALIDADO LOCALMENTE EN ALCANCE ACOTADO; F02 PARCIAL.** Mezclas, históricos y composición de correcciones requieren trabajo posterior definido, no reglas inventadas.
