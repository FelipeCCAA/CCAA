# OP-09 — operación por pantalla, resultados del 23-10-2026

**PARCIAL. Tres hojas de despacho y una salida de leche cruda ejecutadas con datos ficticios. No se aprueba operación industrial ni trazabilidad completa.**

Este corte sustituye como estado vigente al [bloqueo inicial de descarga](OP-09_OPERACIONAL_PARCIAL.md), que se conserva como historial. El usuario resolvió la confirmación nativa y se verificó un único ingreso de 25.000 L; no se volvió a crear la recepción.

## Alcance y aislamiento

Coordinador y un apoyo QA independiente. Misma rama `codex/op09-operacional-trazabilidad`, base `9af5518`, PR19 en borrador. Sólo QA, fixtures y documentación; aplicación sin cambios. Sin producción, despliegues, contratación ni acceso a Supabase. Base nueva vacía `opflow_circuito`, rol `opflow_test`, PG local55479, API8209 y web5209, todos loopback. Extractor de 52 modelos dentro de una transacción READ ONLY / REPEATABLE READ; excluye credenciales, sesiones y archivos privados.

Se prepararon maestros, embalajes iniciales y prerrequisitos ficticios; no se sembraron productos industriales aprobados para fingir recorridos. La orden `OPFLOW-OP-MANT-01`, 40 kg, tuvo autorización expresa después del bloqueo automático por exclusión de Planificación. No se usaron Planificación, Compras ni Mantenimiento para ejecutar operaciones. Una navegación inesperada a Planificación durante una consulta se abandonó sin escribir ni crear semanas; consta como incidencia del control, no prueba de ese módulo.

La preparación de crema sólo enlaza el producto de prueba con la ruta ya existente en migración `procesos.0018`; no crea órdenes, leche ni liberaciones. Especificaciones y medidas son fixtures identificadas, sin validez industrial. Análisis, firmas, transferencias, cierres, envases y despachos se realizaron por pantalla con cuentas por área.

## Recorrido, cantidades y destinos

| Proceso / responsable | Entrada | Resultado y destino comprobado |
| --- | --- | --- |
| Recepción / Recepción + Calidad | Camión QAOP09, OPF-ENT-01, 25.000 L entera | Un ingreso a Silo 3; muestra, decisión de Calidad y segunda firma de análisis de silo |
| Descremado OPF-DES-01 / Producción | 10.000 L de Silo 3 | 9.150,08 L descremada a Tk02; 849,92 L crema a TkC2. Ambas ramas analizadas, firmadas y liberadas |
| Estandarización VE6296-01 / Producción + Calidad | 10.699,47 L Silo 3 + 4.300,53 L Tk02 | 15.000 L Silo 4; transferencia, agitación, muestra y decisión por Calidad |
| Evaporación OPF-POL-01 / Producción | 6.000 L del vale liberado | 1.500 L concentrado a Silo 5, análisis y liberación de etapa |
| Secado / Secado + Calidad | 1.500 L transferidos; ticket ficticio independiente declara 1.500 kg de alimentación | 500 kg polvo + 10 kg finos + 5 kg merma. Diferencia985 kg: **no es agua medida**. Sin conversión automática L=kg |
| Envase polvo / Envase | 500 kg liberados | OPF-PAL-POL-01: 20 sacos×25 kg, un pallet. Cuarentena → Calidad comercial → BPT/PT-DISP |
| Despacho polvo / Despacho | Pallet500 kg disponible | DE6296-01 ejecutado al cliente ficticio; una salida de PT, existencia inactiva |
| Mantequilla OPF-MANT-01 / Producción + Calidad | 36 kg crema42% de INT-DES-1-CR; retiro físico34,88 L con densidad ficticia1032 kg/m³ | 31 kg mantequilla +5 kg merma. Suma de kg cuadra; **balance graso falla**, ver F03 |
| Envase mantequilla / Envase | 31 kg liberados | OPF-PAL-MANT-01: una caja20 kg; remanente11 kg separado. Caja → BPT/PT-DISP → DE6296-02 ejecutado |
| Rework / Calidad + Bodega | Remanente11 kg | RW-000001 segregado en RW-CUAR, luego habilitado en PT-DISP. Disponible11 kg, consumido0; sin ejecución destino compatible abierta |
| Leche cruda / Recepción | 1.000 L Silo 3 con análisis y firma vigentes | OPFLOW-GUIA-FICTICIA-CRUDA-01 al cliente ficticio; un despacho y movimiento12, sin reversa |
| Descremado OPF-DES-02 / Producción | Otros500 L de Silo 3 | 457,50 L descremada a Tk03 +42,50 L crema a TkC3. Ambas con análisis, segundo firmante y decisiones de Calidad distintas |
| Crema comercial / Despacho | 42,50 L INT-DES-2-CR, TkC3, ruta despacho directo | DE6296-03 ejecutado, sin pallets ni conversión a kg; TkC3 queda en cero |

Las tres hojas fueron al cliente **FICTICIO OPFLOW**; no son documentos fiscales ni envíos reales. En PT se probaron creación en cuarentena, traspaso por Calidad y salida; los ingresos en ubicaciones distintas no representan producción duplicada.

Saldos al corte persistido `20261023T151437735213Z`: Silo3 **2.800,53 L**, Silo4 **9.000 L**, Tk02 **4.849,55 L**, Tk03 **457,50 L**, TkC2 **815,04 L**, TkC3/Silo5 **0 L**. No sumar inventarios en litros con productos en kg. La atribución FIFO a recepción1 se conserva; que aparezca por dos ramas del vale no significa dos recepciones.

## Qué se comprobó y qué no

- El polvo no se ofreció a Envase antes de su liberación de Secado; después se ofrecieron500 kg. La crema nueva quedó bloqueada hasta análisis, segunda firma y decisión de Calidad.
- Evaporación, Secado y liberación comercial del polvo conservaron decisiones separadas, UUID distintos y versiones firmadas/evidencia coincidentes. Despachos reales de prueba atravesaron las guardas del servidor. El extractor excluye las instantáneas firmadas: QA no recalculó independientemente sus hashes completos.
- El dossier de polvo21/21 se completó como **SIMULACIÓN**. Equipos no utilizados con piezas N/A y atestaciones explícitamente ficticias. No demuestra PCC, inspección física ni inocuidad real. Mantequilla tomó el checklist genérico de su familia OTRO del catálogo de prueba.
- QA revisó257 inicios de acciones lógicas, con mínimo medible10,007 segundos por usuario y cero infracciones medibles. Los usuarios se intercalan y las consultas automáticas no cuentan como nuevos actos operacionales. No son70 operadores concurrentes ni una prueba de capacidad productiva; dos inicios antiguos carecen de evento terminal, como se detalla abajo.
- Se preservó la advertencia de agitación de0 minutos, sin simular treinta minutos físicos. Se usó MG0,06% en descremada porque el formulario no admite la sugerencia0,055% con su paso0,01. No se cambiaron tolerancias de planta.
- Fechas de Envase conservaron el inicio predeterminado una hora antes: los intentos de rellenar otra hora no quedaron aplicados en pantalla. No se atribuye esto a alteración del backend. Las capturas muestran el valor realmente enviado.

## Hallazgos y corrección mínima propuesta — sin implementar

| ID / prioridad | Evidencia y consecuencia | Ubicación / siguiente comprobación |
| --- | --- | --- |
| F01 P1 | Tk02 queda con4.849,55 L, pero la consulta de materiales de Producción ofrece9.150,08 L y0 consumidos tras el vale. Riesgo de ofrecer material ya utilizado; **no se demostró doble retiro físico** | `backend/procesos/servicios.py:1472`, `views.py:1387` y`:1414`. Vincular el consumo al material original; repetir retiro parcial y comparar ambas pantallas con el libro |
| F02 P1 | Entrada de Estandarización sin `lote_id/salida_origen_id`; genealogía del polvo dice que no hay lotes de origen, aunque sí muestra recepción/vale/pallet. Falta descremada→vale→polvo; FIFO de recepción sigue íntegro | `backend/procesos/servicios.py:1316` y`:1481`; `backend/produccion/servicios.py:240`. Conservar aristas y cantidades; probar mezcla, corrección y consulta hacia ambos sentidos |
| F03 P1 | Crema aporta36×42%=15,12 kg grasa; mantequilla declara31×82%=25,42 kg: **10,30 kg grasa sin origen**. Se permitió liberar y despachar el caso ficticio | `backend/procesos/models.py:650`, `servicios.py:2332`; `frontend/src/services/balance-mantequilla.ts:15`. Validar composición además de kg; acordar incertidumbres/tolerancias con planta antes de programarlas |
| F04 P1 | Checklist por familia exige equipos no usados y lecitina no utilizada; atestaciones pueden completar avance sin prueba física. No existe N/A del documento completo | `backend/calidad/dominio.py:168`; `models.py:55`; `frontend/src/pages/Liberacion/FormularioDinamico.tsx:199`. Definir aplicabilidad por ruta/equipo y evidencia exigida; probar ausente/observado/no aplica |
| F05 P2 | Una unidad logística física de mantequilla descuenta sólo0,040 pallet; faltan0,960 frente a una unidad. Film también0,040, cuya unidad industrial debe aclararse | `backend/inventario/servicios.py:643`; preparador E2E de mantequilla. Separar receta por peso y embalajes por unidad logística; comprobar lotes parciales sin inventar fracciones de pallet |
| F06 P2 | Inicio de Envase anterior al cierre del proceso anterior; sólo se valida fin>inicio | `frontend/src/pages/Produccion/FormularioEnvase.tsx:50` y`:74`; `backend/produccion/models.py:634`. Validar secuencia temporal contra origen, contemplando correcciones auditadas |
| F07 P2 | Después del despacho, trazabilidad dice ubicación actual Silo5 y simultáneamente muestra pallet despachado | `backend/procesos/consultas_trazabilidad.py:226`; `frontend/src/pages/Procesos/TrazabilidadProceso.tsx:69`. Distinguir ubicación histórica, saldo actual y destino de cada fracción; probar despachos parciales/completos |

No hay P0 demostrado en este recorrido. Eso no descarta otros defectos. Estos P1 impiden declarar lista la operación integral. Orden recomendado: F01/F02 juntos, F03 con validación industrial, F04; después F05–F07 y repetición del circuito. Cambios de aplicación requieren autorización separada.

## Cobertura pendiente y decisiones

| Ruta / alcance | Estado y requisito concreto |
| --- | --- |
| Polvo, mantequilla, leche cruda y crema directa | Llegaron a salida por UI; validación integral **parcial/fallida** por hallazgos, no aprobación de planta |
| Descremada | Producida, analizada y consumida en el vale; genealogía/disponible fallan |
| Precondensado directo | Sin ejecutar. Se solicitó autorización para sólo OPFLOW-OP-PRECOND-01 de2.000 L; **pendiente de respuesta**, no creada. Luego vale→evaporación→Calidad→despacho |
| Suero externo | Pantalla103: sin orden de Secado con materia prima externa configurada; sin ingreso/liberación ficticios por UI. Debe acordarse preparación aislada y entrada compatible con exclusión de Compras. No sembrar un lote aprobado para dar el circuito por hecho |
| Rework | Segregación y habilitación probadas. Pantalla102 sin ejecución destino; falta escenario compatible definido y consumo con trazabilidad. No mezclar mantequilla en otro producto arbitrariamente |
| Malta, instantánea, lecitina | Sin variantes ejecutadas. Confirmar rutas realmente aplicables antes de extender cobertura |
| Carga25/50/70 y sostenida | Sin repetir en este ensayo; continúan pendientes del expediente de carga. La cadencia10s no resuelve la limitación de recursos anterior |

## Evidencias y límites del control

[Índice de pantallas y formularios](evidencias/opflow-ejecucion/PANTALLAS.md), ledger final, diarios, correcciones de metadatos, revisión QA y manifiesto SHA256 en `evidencias/opflow-ejecucion/`. Cada captura tiene un significado: formulario, bloqueo, confirmación o estado final. Las050 y092 eran estados prematuros y no se publican como confirmación;007–009 no acreditan Calidad. Originales preservados en el entorno local.

Diario inicial: secuencias11–17 tenían actor mal etiquetado; corrección explícita conservada sin reescribir crudos. Inicios28/33 sin evento terminal: brecha de evidencia. Secuencia219 registra intención Consultar, pero se observó navegación a Planificación sin mutación; consulta real posterior220. No interpretar `fin` del controlador como aprobación del negocio: se contrastó estado visible y persistencia. La sesión de Recepción y del segundo firmante expiró por inactividad y se renovó sin ampliar permisos.

Ruff QA y `git diff --check` ejecutados. No se repiten ni se declaran suites de aplicación, carga o regresión no ejecutadas. El entorno local se conserva para revisión; no hay cambio productivo ni merge con `developmain`.

## AVANCE

Ejecutados: recepción, dos descremados, estandarización, evaporación, Secado, Envase, decisiones de Calidad, Bodega, tres hojas de despacho y una salida de leche cruda. Rework habilitado, no consumido. Modificados: cuatro fixtures QA de preparación, informe, índice/evidencias, `TASK_BACKLOG.md` y `PROGRESS.md`. Riesgos F01–F07 pendientes; PR19 de evidencia en borrador. Próximo circuito: precondensado si se autoriza la orden ficticia solicitada.

## EXPLICADOR — OP-09 operacional

1. **PROBLEMA DETECTADO:** se puede avanzar entre áreas, pero hay diferencias de saldo mostrado, origen de materiales, grasa y embalajes.
2. **CAUSA TÉCNICA:** algunos consumos sólo nombran el silo; mantequilla suma kg sin conservar grasa; documentos y embalajes dependen de configuraciones demasiado generales.
3. **EJEMPLO REAL DE OPERACIÓN:** Tk02 tiene4.849,55 L y otra consulta ofrece9.150,08 L. Una caja20 kg despachada descuenta sólo0,040 pallet.
4. **SOLUCIÓN RECOMENDADA:** enlazar consumos/orígenes y validar balances/aplicabilidad/unidades antes de repetir el circuito; reglas industriales pendientes de validar con planta.
5. **TRABAJO REALIZADO POR LOS AGENTES:** coordinador ejecutó pantallas; QA contrastó archivos, cantidades, código y cadencia. Sólo fixtures/documentación; **solución pendiente de implementación**.
6. **PRUEBAS Y RESULTADOS:**500 kg polvo,20 kg mantequilla,42,50 L crema y1.000 L leche cruda llegaron a salida ficticia;11 kg rework disponibles. No significa que el balance industrial o toda la trazabilidad aprobaran.
7. **ESTADO FINAL:** **PARCIAL, HALLAZGOS DETECTADOS**. Faltan precondensado, suero, consumo del rework y correcciones autorizadas; producción intacta.
