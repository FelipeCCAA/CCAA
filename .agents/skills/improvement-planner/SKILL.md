---
name: improvement-planner
description: Convierte análisis funcionales y arquitectónicos de un sistema existente en una arquitectura objetivo y un plan de mejora incremental ejecutable por Codex, con prioridades, dependencias, riesgos, criterios de aceptación, pruebas, prompts de implementación y reportes HTML visuales aislados del sistema productivo.
---

# Improvement Planner

## Rol

Actúa como Principal Architect + Technical Lead responsable de convertir auditorías en un plan de implementación seguro.

No debes proponer una reescritura completa salvo que exista evidencia excepcional que la justifique.

Prefiere evolución incremental.

# Entradas

Antes de trabajar lee:

- AGENTS.md
- docs/architecture/01-system-map.md
- docs/architecture/03-architecture-current.md
- docs/architecture/04-architecture-problems.md
- documentación funcional relevante
- código necesario para verificar hallazgos importantes.

No confíes ciegamente en informes anteriores.

Verifica los hallazgos críticos contra código cuando sea necesario.

# Objetivo

Transforma:

AS-IS  
+  
problemas encontrados  
+  
restricciones reales

en:

TO-BE  
+  
roadmap técnico  
+  
tareas ejecutables por Codex  
+  
representación visual HTML fácil de comprender.

# Prioridad

Clasifica mejoras mediante:

- impacto;
- riesgo;
- severidad;
- esfuerzo;
- dependencia;
- posibilidad de regresión;
- beneficio operativo.

Usa:

P0 = crítico / riesgo inmediato

P1 = necesario antes de escalar

P2 = mejora arquitectónica importante

P3 = optimización

P4 = evolución futura

# Categorías

Clasifica cada mejora en:

- Correctness
- Data Integrity
- Architecture
- Security
- Performance
- Scalability
- Reliability
- Observability
- Maintainability
- UX/API efficiency
- Testing
- Infrastructure

# Para cada mejora

Genera:

## ID

`IMP-001`

## Problema

## Evidencia

## Consecuencia actual

## Solución propuesta

## Arquitectura objetivo

## Archivos/módulos afectados

## Dependencias

## Riesgo de implementación

## Estrategia de migración

## Tests requeridos

## Criterios de aceptación

## Rollback

# Arquitectura objetivo

Crear:

`docs/architecture/05-target-architecture.md`

Debe incluir diagramas Mermaid para:

- arquitectura objetivo;
- comunicación entre módulos;
- capa de servicios;
- procesamiento background;
- cache si corresponde;
- infraestructura;
- observabilidad;
- seguridad;
- deployment.

Nunca introduzcas tecnología solo porque sea popular.

Cada nuevo componente debe responder:

1. ¿qué problema concreto resuelve?
2. ¿por qué la solución actual no basta?
3. ¿qué coste operativo introduce?
4. ¿es necesario ahora o más adelante?

# Reporte visual HTML

Además de la documentación Markdown, genera un reporte HTML visual y fácil de comprender.

## Carpeta obligatoria

Todos los archivos HTML generados por esta Skill deben guardarse exclusivamente en:

`docs/architecture/html/`

Archivo principal:

`docs/architecture/html/improvement-plan.html`

Si necesitas archivos HTML adicionales, deben permanecer dentro de:

`docs/architecture/html/`

Ejemplos permitidos:

- `docs/architecture/html/improvement-plan.html`
- `docs/architecture/html/target-architecture.html`
- `docs/architecture/html/roadmap.html`

## Aislamiento obligatorio

La generación de reportes HTML es únicamente documentación.

NO debe formar parte del sistema ejecutable.

No modificar para generar estos reportes:

- frontend/
- backend/
- templates/
- static/
- public/
- src/
- package.json
- vite.config.*
- configuración Django
- urls.py
- settings.py
- nginx
- Docker
- docker-compose
- pipelines de despliegue
- scripts de producción.

No:

- agregues rutas al sistema;
- publiques estos HTML desde Django;
- incorpores estos HTML al frontend React;
- agregues endpoints para servirlos;
- agregues dependencias al proyecto únicamente para generar los reportes;
- modifiques el build;
- modifiques configuración productiva.

Los reportes deben poder eliminarse completamente sin afectar el funcionamiento del sistema.

# Características del HTML

El HTML debe priorizar comprensión visual.

Debe incluir:

- título del análisis;
- fecha o contexto de generación cuando corresponda;
- resumen ejecutivo;
- arquitectura AS-IS relevante;
- arquitectura TO-BE;
- problemas principales;
- mejoras propuestas;
- roadmap P0-P4;
- dependencias entre mejoras;
- quick wins;
- cambios de alto riesgo;
- diagramas;
- leyenda visual.

Cuando sea útil, utiliza diagramas Mermaid.

Los diagramas deben diferenciar visualmente:

- frontend;
- backend;
- API;
- servicios;
- base de datos;
- caché;
- workers;
- infraestructura;
- sistemas externos;
- problemas;
- mejoras propuestas.

El HTML debe ser entendible por una persona que no necesite leer primero todo el código.

# Reglas técnicas del HTML

Prefiere un HTML autocontenido y simple.

Evita introducir infraestructura innecesaria.

No agregues frameworks frontend al proyecto para generar la documentación.

No ejecutes `npm install` ni agregues paquetes al sistema únicamente para estos reportes.

Si utilizas Mermaid mediante CDN dentro del documento HTML, deja claro que el recurso se utiliza exclusivamente para renderización documental.

Si es posible generar el documento sin nuevas dependencias del proyecto, esa es la opción preferida.

El HTML debe funcionar como documento independiente.

# Navegación visual

Cuando el informe sea grande, incluye navegación interna mediante secciones como:

- Resumen
- Problemas
- Arquitectura actual
- Arquitectura objetivo
- Roadmap
- Dependencias
- Riesgos
- Codex Tasks

Puede utilizar:

- tabla de contenidos;
- enlaces internos;
- secciones desplegables;
- tarjetas;
- tablas;
- Mermaid.

Evita diseño decorativo excesivo.

Prioriza claridad técnica.

# AS-IS vs TO-BE

Nunca mezcles arquitectura actual y arquitectura objetivo sin diferenciarlas.

En el HTML deben existir secciones claramente separadas:

## AS-IS

Cómo funciona actualmente.

## TO-BE

Cómo debería evolucionar.

Cuando sea útil genera un tercer diagrama:

## TRANSITION

Cómo pasar de AS-IS a TO-BE.

# Roadmap

Crear:

`docs/architecture/06-improvement-plan.md`

Ordena los trabajos respetando dependencias.

Ejemplo:

P0  
→ integridad y seguridad

P1  
→ arquitectura y concurrencia

P2  
→ rendimiento

P3  
→ escalabilidad

P4  
→ mejoras futuras.

Representa también este roadmap visualmente en:

`docs/architecture/html/improvement-plan.html`

# Tamaño de tareas

Una tarea para Codex debe ser suficientemente pequeña para:

- comprender el contexto;
- implementar;
- probar;
- revisar;
- revertir.

Evita tareas como:

"Mejora toda la arquitectura."

Prefiere:

"Extrae la transición de estado X del ViewSet Y hacia el servicio Z, manteniendo compatibilidad de API y agregando estas pruebas."

# Generación de prompts para Codex

Para cada tarea genera opcionalmente un prompt listo para ejecutar.

Formato:

## CODEX TASK

### Contexto

### Problema

### Comportamiento actual

### Comportamiento esperado

### Archivos relevantes

### Restricciones

### Implementación requerida

### No modificar

### Tests obligatorios

### Criterios de aceptación

### Validación final

# Reglas para los prompts

Los prompts NO deben decir simplemente:

"revisa y mejora".

Deben indicar qué investigar y qué resultado debe obtenerse.

Sin embargo, tampoco deben obligar a Codex a implementar una solución técnica incorrecta si el código demuestra una mejor alternativa.

Utiliza el patrón:

"Analiza primero la implementación existente. Confirma la causa. Luego implementa la solución de menor riesgo que cumpla estos criterios."

# Dependencias

Construye un DAG conceptual de mejoras.

Ejemplo:

IMP-001  
↓  
IMP-004  
↓  
IMP-007

No permitas que una mejora dependa de otra que todavía no haya sido ejecutada sin declararlo.

Representa también estas dependencias gráficamente en el reporte HTML.

# Control anti-regresión

Antes de recomendar una modificación identifica:

- módulos consumidores;
- endpoints afectados;
- modelos afectados;
- flujos afectados;
- tests existentes;
- posibles side effects.

# Prohibiciones

No:

- propongas microservicios por defecto;
- agregues Redis sin justificarlo;
- agregues Kafka sin justificarlo;
- agregues Kubernetes sin justificarlo;
- cambies frameworks por moda;
- reescribas módulos estables innecesariamente;
- mezcles refactor con nuevas funcionalidades sin necesidad;
- modifiques código productivo únicamente para generar documentación;
- conectes los reportes HTML con el runtime del sistema;
- agregues dependencias al proyecto solo para visualizar diagramas.

# Salida final

Debes entregar:

1. Top 10 problemas.
2. Top 10 mejoras.
3. Arquitectura objetivo.
4. Roadmap P0-P4.
5. Dependencias entre cambios.
6. Quick wins.
7. Cambios de alto riesgo.
8. Deuda técnica aceptable.
9. Deuda técnica que debe eliminarse.
10. Prompts listos para Codex.
11. Reporte HTML visual.
12. Diagramas AS-IS, TO-BE y transición cuando corresponda.

Archivos mínimos esperados:

`docs/architecture/05-target-architecture.md`

`docs/architecture/06-improvement-plan.md`

`docs/architecture/html/improvement-plan.html`

# Regla final de seguridad

La carpeta:

`docs/architecture/html/`

debe considerarse documentación descartable.

Eliminar completamente esa carpeta NO debe cambiar:

- el comportamiento del sistema;
- el frontend;
- el backend;
- las APIs;
- la base de datos;
- el despliegue;
- los tests funcionales;
- las dependencias;
- la configuración.

Si generar el reporte requiere modificar el sistema productivo, NO lo hagas.

Busca una alternativa documental aislada.

La finalidad no es producir la arquitectura teóricamente más sofisticada.

La finalidad es producir la arquitectura adecuada para este sistema, con el mínimo riesgo, una evolución sostenible y una representación visual comprensible.