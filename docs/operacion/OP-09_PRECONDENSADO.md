# OP-09 — precondensado, corte 23-10-2026 13:34 Chile

**PARCIAL: 2.000 L procesados → 500 L ficticios en OP09-PRE-BASE. Sin liberación ni despacho.** El control de Calidad impidió avanzar porque no existe una especificación vigente de tipo SILO para el producto en este entorno de prueba.

Continúa el [ensayo operacional anterior](OP-09_OPERACIONAL_RESULTADOS.md). El usuario autorizó expresamente sólo `OPFLOW-OP-PRECOND-01`, cantidad planificada2.000 L. Después indicó continuar y explicar las trabas, sin aportar rangos numéricos. No se inventaron límites, no se cambió la especificación de tipo LOTE existente ni se forzó una liberación.

## Operaciones efectivamente ejecutadas

| Área / acto | Entrada y salida | Evidencia |
| --- | --- | --- |
| Preparación QA | Una OP ficticia2.000 L, producto Precondensado Entero NE Granel | Fixture acotado `qa/opflow/seed_precond_order.py`; clúster/tenant verificados, sin stock ni aprobaciones. Segunda ejecución `created=False`, no crea otra orden ni cambia el estado |
| Producción, VE6296-02 | 1.426,60 L Silo3 +573,40 L Tk02 →2.000 L Silo5 | Receta calculada a0,01 L; RC objetivo0,3000. No usa el vale previo de polvo |
| Producción / Calidad | Transferencia, agitación y muestra ficticia2,60% MG/8,67% SNG; RC0,2999, decisión por e2e_calidad | Vale liberado. Advertencia de0 minutos sobre30 conservada: **no prueba agitación física suficiente** |
| Calidad y segundo usuario | Análisis8 de Silo5 confirmado por usuario3, visualizado por usuario4 | El ingreso de2.000 L dejó inválido el análisis antiguo5 del silo. Nueva muestra y firma antes de abrir el lote |
| Producción, OPF-PRE-01 | Lote7, ejecución8/códigoEJ-PROD-7, corrida de evaporación2;2.000 L Silo5→Scheffers2 | Orden3 autorizada; equipo y vale vinculados. Se preparó OP09-PRE-BASE como destino vacío |
| Producción, cierre | 500 L precondensado a OP09-PRE-BASE,45,08% sólidos y62,50°C ficticios | Una SalidaProceso11 y un ingreso físico MovimientoSilo21. Diferencia volumétrica1.500 L: **no es agua medida ni conversión de litros a kg** |
| Calidad | Análisis9: MG10,40/SNG34,68/pH6,65, segundo firmante distinto | Suma MG+SNG45,08, datos de software sin certificación industrial. Otros valores de fixture: acidez15,4, proteína3,44, temperatura de muestra4,2,densidad1032, inhibidores negativos |
| Calidad, decisión | Muestra firmada seleccionada, botón Liberar etapa deshabilitado | Pantallas127/127b: «No existe una especificación vigente para comparar este resultado» |
| Despacho, consulta | El lote pendiente no aparece entre graneles cargables | Pantalla128, consulta renovada con e2e_despacho. Se cerró el formulario vacío, sin guardar una hoja |

La orden queda `pendiente_calidad`; no se declara completada. Cantidad planificada de una orden, litros de leche de entrada y litros de producto obtenido son conceptos distintos; no se ajustó la OP para hacerla coincidir con los500 L del ensayo.

## Conciliación y controles comprobados

Snapshot `operational-ledger-20261023T163432527391Z.json`:52 modelos/299 filas. QA independiente revisó sólo archivos. Movimientos17–21 atribuidos íntegramente por FIFO a recepción1, sin origen desconocido. Una OP, un vale, una corrida, una salida de500 L y un ingreso físico. Cero LiberacionProceso de salida11 y cero DetalleDespachoGranel para ella. No se alteraron los tres despachos anteriores.

Saldos: Silo3 **1.373,93 L**, Tk02 **4.276,15 L**, Silo5 **0 L**, OP09-PRE-BASE **500 L bloqueados**, Silo4 **9.000 L**, Tk03 **457,50 L**, TkC2 **815,04 L**, TkC3 **0 L**. Los500 L tienen destino despacho directo, pero aún no están autorizados ni disponibles para cargar.

QA revisó307 inicios hasta el corte de conciliación, mínimo medible10,007 segundos por usuario y cero infracciones medibles. Las acciones308–310 posteriores fueron enfoque de pantalla y consulta/cierre de formulario vacío, sin nuevas operaciones industriales. Se preservan brechas históricas28/33 y corrección de actor11–17. No es una prueba de capacidad70usuarios.

## Traba concreta y dirección de resolución

En OPFLOW, la consulta de sólo lectura encontró únicamente especificación4 del producto, tipoLOTE/v1, fuente «Configuración inicial provisoria: validar con Calidad antes de operación comercial». No hay especificaciónSILO. La liberación de un intermedio almacenado en silo exige ese tipo: `backend/calidad/views.py:736`, `_bloqueo_especificacion_intermedia`; `backend/calidad/vigencia.py:192`. El listado cargable exige liberación: `backend/inventario/views.py:791`.

**El bloqueo de Calidad funciona en este escenario.** La carencia de configuración corresponde al entorno aislado probado; no demuestra que falte lo mismo en producción. No se hizo POST de liberación con un botón deshabilitado ni se ensayó una evasión directa del servidor. Recomendación: detectar esta carencia antes de iniciar la corrida y registrar la especificación aprobada aplicable al producto/ruta/fecha, con parámetros y límites definidos por Calidad. No reutilizar la especificaciónLOTE ni cambiar la muestra para conseguir un resultado conforme.

Queda pendiente completar liberación→hoja→autorización→salida cuando exista una especificación validada. Los valores de referencia del preparador E2E no se tomaron como reglas industriales aprobadas. Los hallazgos F01–F07 anteriores permanecen abiertos, incluida genealogía material entre descremada, vale y lote; FIFO por recepción no equivale a resolver esa genealogía.

## Incidencias y archivos

Sesiones ficticias expiradas se renovaron por ingreso normal, sin ampliar permisos. Hubo fallos del controlador al leer y al abrir el cierre (dos clics y teclado sin efecto); una recarga y consulta de la corrida recuperaron la interacción. No hubo POST de cierre hasta enviar el formulario real, ni segundo cierre para ocultar una respuesta incierta. Esto no prueba un fallo de inventario ni atribuye el problema al servidor.

[Pantallas, controles y manifiesto](evidencias/opflow-precondensado/PANTALLAS.md). Cambios: un fixture QA nuevo, este expediente, enlaces de estado vigente, `TASK_BACKLOG.md`, `PROGRESS.md` y evidencias seleccionadas. Backend/frontend sin modificaciones. Ruff QA, comprobación de diff y hashes de evidencia ejecutadas al cierre; no suites generales ni CI adicional afirmados. Misma rama y PR19 en borrador; sin merge ni despliegue. Base local/API/web preservadas para continuar.

## AVANCE

Orden autorizada creada una sola vez y preparación repetida sin duplicado. Ejecutados vale, apertura, evaporación y análisis con dos firmantes.500 L bloqueados por requisito real de Calidad, sin despacho. Un coordinador y un apoyo QA; aplicación y producción intactas. Próximo paso de este circuito: disponer de especificación de silo aprobada. Suero y consumo de rework siguen pendientes del expediente anterior.

## EXPLICADOR — precondensado

1. **PROBLEMA DETECTADO:** los500 L están registrados, pero Calidad no tiene una regla aprobada de comparación para liberarlos.
2. **CAUSA TÉCNICA:** existe especificación de lote; para este intermedio el sistema exige una especificación de silo vigente.
3. **EJEMPLO REAL DE OPERACIÓN:** tener muestra y segunda firma no basta; Liberar etapa queda deshabilitado y Despacho no ofrece el producto.
4. **SOLUCIÓN RECOMENDADA:** definir/registrar los parámetros aprobados por Calidad y advertir su ausencia antes de producir; sin inventar tolerancias.
5. **TRABAJO REALIZADO POR LOS AGENTES:** se creó sólo la OP autorizada y se ejecutó el circuito ficticio. QA concilió registros. No se implementó una corrección de aplicación.
6. **PRUEBAS Y RESULTADOS:**2.000 L→500 L una sola vez, FIFO conciliado, análisis nuevo/segunda firma, bloqueo de liberación y ausencia en cargables comprobados.
7. **ESTADO FINAL:** **PARCIAL, BLOQUEADO EN CALIDAD**. El ensayo detectó el requisito faltante y comprobó el freno; liberación y despacho todavía no ejecutados.
