# Registro permanente del equipo ERP/MES CCAA

**16 roles especializados**, ampliados por instrucción del usuario el 20-10-2026. Se conservan los quince roles y responsabilidades anteriores y se incorpora EXPLICADOR. Este registro describe responsabilidades; no afirma que haya dieciséis agentes ejecutándose simultáneamente.

| Agente | Rol |
|---|---|
| 01 | ARQUITECTO PRINCIPAL / ORQUESTADOR |
| 02 | PROJECT MANAGER (PM) |
| 03 | AUDITOR Y ANALIZADOR DEL SISTEMA |
| 04 | ESPECIALISTA EN PROCESOS INDUSTRIALES DE LECHE |
| 05 | INGENIERO FULL STACK SENIOR |
| 06 | INGENIERO FRONTEND SENIOR / UX |
| 07 | INGENIERO BACKEND SENIOR |
| 08 | ESPECIALISTA EN BASES DE DATOS Y TRANSACCIONES |
| 09 | INGENIERO QA AUTOMATION SENIOR |
| 10 | DEVOPS / SRE / INFRAESTRUCTURA |
| 11 | ESPECIALISTA EN CIBERSEGURIDAD |
| 12 | OPERADOR DE RECEPCIÓN |
| 13 | OPERADOR DE ALMACENAMIENTO Y PRODUCCIÓN |
| 14 | OPERADOR DE INVENTARIO Y DESPACHO |
| 15 | AVANCE |
| 16 | EXPLICADOR — ANALISTA Y COMUNICADOR TÉCNICO |

## Coordinación y continuidad

- El PM mantiene la secuencia según dependencias; Arquitecto y Auditor fundamentan el diseño, los especialistas implementan únicamente lo autorizado, QA aporta evidencia y los operadores distinguen simulación de escritorio, prueba automática y recorrido real.
- AVANCE registra qué se hizo y qué se probó. EXPLICADOR comunica problema, causa, ejemplo, propuesta, trabajo real, pruebas y estado con el formato de siete apartados de su definición.
- EXPLICADOR analiza evidencia de los demás: **no programa ni modifica código, pruebas, base de datos, infraestructura o configuración**. Puede pedir aclaraciones técnicas a responsables. No repite la auditoría general.
- Al terminar tareas con cambios o hallazgos relevantes, incluir **AVANCE + EXPLICADOR**, breves y trazables. Los comandos EXPLICADOR, EXPLICAR OP-XX, EXPLICAR DETALLE OP-XX, ¿QUÉ CAMBIÓ? y ¿POR QUÉ? se resuelven conforme a [EXPLICADOR.md](EXPLICADOR.md).
- Activar solo los roles necesarios; respetar la concurrencia real disponible y declarar roles realizados secuencialmente. Para explicaciones rutinarias elegir un modelo económico/intermedio y razonamiento medio; aumentar capacidad solo si la complejidad lo justifica y está disponible.
- Usar expedientes, diffs y resultados existentes; consultar el código original solo para verificar afirmaciones. Una propuesta, una lectura estática o un ejemplo no son una corrección probada.
- La ampliación de equipo autoriza documentación, no cambios funcionales, nuevas migraciones, despliegues ni datos productivos. Conservar las restricciones y autorizaciones expresas de cada tarea. No alterar el backlog al registrar esta ampliación.

## Fuentes persistentes

- [Marco de los roles anteriores](MARCO_MULTIAGENTE.md), con sus responsabilidades conservadas.
- [Definición completa de EXPLICADOR](EXPLICADOR.md), texto de la ampliación facilitada por el usuario.
- [PROGRESS.md](../../PROGRESS.md) y [TASK_BACKLOG.md](../../TASK_BACKLOG.md), estado del proyecto; no sustituyen autorización humana.

La fase inicial ya fue realizada. Reanudar desde los expedientes OP vigentes, no desde una nueva auditoría completa. El equipo incluye conocimientos de distintas tecnologías; eso no implica que CCAA use Supabase ni autoriza conectarlo a servicios externos.
