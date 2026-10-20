## Especialistas disponibles

Las Skills especializadas del proyecto se encuentran en:

`.agents/skills/`

Cuando una tarea coincida con una de las especialidades descritas a
continuación, leer primero el `SKILL.md` correspondiente y seguir sus
instrucciones completas antes de analizar o modificar el sistema.

### Procesos lácteos

Para tareas relacionadas con producción, recepción, calidad, procesos
lácteos, diseño de pantallas operacionales, silos, estanques, lotes,
estandarización, descremado, crema, mantequilla, evaporación, secado,
envasado, inventario o despacho:

Leer:

`.agents/skills/experto-procesos-lacteos/SKILL.md`

El especialista debe analizar primero el proceso productivo real y
posteriormente su implementación informática.


### Análisis de flujo del sistema

Para reconstruir cómo funciona el sistema, qué módulos se comunican,
qué llama a qué, endpoints, servicios, modelos, estados y dependencias:

Leer:

`.agents/skills/system-flow-analyzer/SKILL.md`


### Flujo productivo lácteo

Para reconstruir el funcionamiento de la planta desde la perspectiva
del operador, incluyendo productos, subproductos, procesos,
subprocesos, calidad y trazabilidad:

Leer:

`.agents/skills/dairy-process-runtime-mapper/SKILL.md`

Para este análisis puede utilizar también:

`.agents/skills/experto-procesos-lacteos/SKILL.md`

como conocimiento especialista complementario.


### Auditoría de arquitectura

Para analizar arquitectura, seguridad, rendimiento, concurrencia,
base de datos, API, escalabilidad, disponibilidad y dependencias:

Leer:

`.agents/skills/architecture-auditor/SKILL.md`


### Planificación de mejoras

Para convertir los análisis y auditorías existentes en arquitectura
objetivo, prioridades P0-P4, roadmap y tareas ejecutables por Codex:

Leer:

`.agents/skills/improvement-planner/SKILL.md`

Antes de ejecutarlo debe revisar cuando existan:

- `docs/architecture/01-system-map.md`
- `docs/architecture/02-production-runtime.md`
- `docs/architecture/03-architecture-current.md`
- `docs/architecture/04-architecture-problems.md`


## Orden recomendado de análisis completo

Cuando se solicite una revisión completa del sistema, utilizar este
orden:

1. `system-flow-analyzer`
2. `dairy-process-runtime-mapper`
3. `architecture-auditor`
4. `improvement-planner`

No ejecutar `improvement-planner` antes de disponer de los análisis
anteriores salvo instrucción explícita del usuario.


## Regla de colaboración entre especialistas

Una Skill puede consultar otra Skill cuando necesite conocimiento
especializado adicional.

Ejemplo:

`dairy-process-runtime-mapper`
→ puede leer `experto-procesos-lacteos`

pero la Skill especialista complementaria no reemplaza la
responsabilidad principal de la Skill que está ejecutando la tarea.

Los hallazgos siempre deben verificarse contra el código y la
documentación real del repositorio.

## Equipo permanente ERP/MES — 16 agentes

Se incorpora EXPLICADOR como agente 16, conservando los quince roles, responsabilidades y controles existentes. Consultar el [registro del equipo](docs/equipo/REGISTRO_AGENTES.md) y, al asignar ese rol, la [definición completa de EXPLICADOR](docs/equipo/EXPLICADOR.md).

El PM coordina dependencias y autorizaciones; AVANCE reporta evidencias. EXPLICADOR traduce esas evidencias a lenguaje claro y no modifica código, pruebas, datos, infraestructura ni configuración. Después de diagnósticos o correcciones relevantes, entregar AVANCE y EXPLICADOR breves; el último conserva sus siete apartados obligatorios y distingue propuesta, implementación y validación.

Usar solo los agentes necesarios y las capacidades reales de la sesión, sin afirmar dieciséis ejecuciones simultáneas. No repetir la auditoría inicial: continuar desde los expedientes y el estado persistente. La ampliación documental no autoriza nuevas funcionalidades, migraciones, despliegues ni datos productivos, ni altera el backlog. Las instrucciones y autorizaciones posteriores del usuario prevalecen.
