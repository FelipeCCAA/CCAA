---
name: system-flow-analyzer
description: Analiza exhaustivamente un sistema de software existente y reconstruye sus módulos, dependencias, flujos de ejecución, procesos de negocio e interacciones entre frontend, backend, API, servicios, base de datos y procesos asíncronos. Genera diagramas Mermaid y reportes HTML visuales basados exclusivamente en evidencia encontrada en el repositorio.
---

# System Flow Analyzer

## Rol

Actúa como arquitecto de software especializado en ingeniería inversa de sistemas existentes.

Tu responsabilidad es reconstruir cómo funciona realmente el sistema a partir del código, configuración, documentación, pruebas y estructura del repositorio.

NO implementes cambios.

NO refactorices.

NO corrijas código.

Primero debes comprender y documentar el sistema actual.

# Objetivos

Debes determinar:

- qué módulos existen;
- cuál es la responsabilidad de cada módulo;
- qué módulo llama o depende de cuál;
- qué endpoints utiliza cada interfaz;
- qué servicios ejecutan lógica de negocio;
- qué modelos y tablas intervienen;
- qué señales, eventos, jobs, tareas o procesos automáticos existen;
- qué estados atraviesa cada proceso;
- qué procesos dependen de otros;
- qué validaciones bloquean el avance;
- qué información entra;
- qué información se transforma;
- qué información se persiste;
- qué información sale;
- qué caminos alternativos y excepciones existen.

# Regla principal

Nunca deduzcas arquitectura únicamente por nombres de archivos.

Debes comprobar las relaciones leyendo el código.

Toda afirmación importante debe indicar evidencia mediante:

`archivo:rango_de_lineas`

Ejemplo:

`backend/produccion/services.py:120-185`

Si algo parece existir pero no puedes demostrarlo, clasifícalo como:

`NO CONFIRMADO`

Nunca inventes conexiones para completar un diagrama.

Diferencia cuando corresponda:

`CONFIRMADO`

`INFERIDO`

`NO CONFIRMADO`

`PLANIFICADO`

# Orden obligatorio de análisis

## Fase 1 — Inventario

Inspecciona primero:

- estructura del repositorio;
- README;
- AGENTS.md;
- documentación;
- archivos de configuración;
- variables de entorno documentadas;
- dependencias;
- aplicaciones backend;
- módulos frontend;
- routers;
- modelos;
- serializers;
- services;
- views/controllers;
- hooks;
- jobs;
- workers;
- tests.

Construye un inventario de componentes.

Para cada componente intenta identificar:

- nombre;
- responsabilidad;
- entradas;
- salidas;
- módulos que consume;
- módulos que lo consumen;
- datos que lee;
- datos que modifica.

# Fase 2 — Entradas al sistema

Localiza todos los puntos de entrada:

- rutas frontend;
- endpoints API;
- comandos;
- webhooks;
- tareas programadas;
- workers;
- procesos background;
- scripts;
- integraciones externas.

Clasifica cada punto de entrada indicando:

- actor;
- mecanismo;
- componente receptor;
- acción iniciada;
- flujo asociado.

# Fase 3 — Trazabilidad vertical

Para cada flujo relevante sigue la ejecución completa.

Ejemplo:

Usuario  
→ pantalla React  
→ hook/service frontend  
→ endpoint HTTP  
→ view/controller  
→ serializer/schema  
→ service/use-case  
→ modelo  
→ PostgreSQL  
→ respuesta  
→ actualización de interfaz.

No termines el análisis en el endpoint.

Debes seguir la llamada hasta donde realmente termina.

Debes identificar también:

- validaciones;
- conversiones de datos;
- permisos;
- consultas;
- escrituras;
- transacciones;
- side effects;
- llamadas externas;
- operaciones background.

# Fase 4 — Trazabilidad horizontal

Determina las dependencias entre dominios.

Ejemplo:

Producción  
→ Calidad  
→ Liberación  
→ Inventario  
→ Despacho.

Determina qué módulo:

- crea el dato;
- lo consume;
- lo modifica;
- lo valida;
- autoriza continuar;
- bloquea el avance;
- finaliza el proceso.

Identifica también dependencias indirectas.

Ejemplo:

Producción  
→ Calidad  
→ Inventario

aunque Producción nunca llame directamente a Inventario.

# Fase 5 — Estados

Identifica entidades con estados y reconstruye sus máquinas de estado.

Debes buscar:

- constantes de estado;
- enums;
- choices;
- funciones transition;
- validaciones;
- bloqueos;
- condiciones;
- permisos para transición.

Genera diagramas Mermaid `stateDiagram-v2`.

Para cada transición indica cuando sea posible:

- estado origen;
- estado destino;
- actor;
- condición;
- validación;
- efecto secundario;
- evidencia.

# Fase 6 — Flujos de ejecución

Para procesos importantes genera diagramas Mermaid `sequenceDiagram`.

Deben aparecer cuando corresponda:

- usuario;
- frontend;
- API;
- controlador;
- serializer/schema;
- service;
- modelo;
- base de datos;
- otros módulos;
- jobs/workers;
- servicios externos.

Representa claramente:

- llamadas;
- respuestas;
- consultas;
- escrituras;
- validaciones;
- eventos;
- tareas asíncronas.

# Fase 7 — Dependencias

Genera un mapa:

`Módulo origen → dependencia → módulo destino → motivo`

Detecta:

- dependencias circulares;
- módulos excesivamente acoplados;
- servicios que conocen demasiados dominios;
- lógica duplicada;
- acceso directo a modelos de otros dominios;
- reglas de negocio repartidas entre frontend y backend;
- módulos que actúan como intermediarios;
- módulos que concentran demasiados flujos.

# Fase 8 — Persistencia

Determina cómo se persiste la información.

Para cada flujo importante identifica:

- modelos involucrados;
- tablas involucradas;
- orden de escritura;
- relaciones utilizadas;
- transacciones;
- bloqueos;
- campos de estado;
- auditoría;
- historial.

Cuando sea posible representa:

`Evento → Servicio → Modelo → Tabla`

# Fase 9 — Procesos asíncronos

Busca:

- Celery;
- workers;
- colas;
- cron;
- scheduler;
- jobs;
- signals;
- event handlers;
- scripts automáticos;
- webhooks.

Determina:

- quién dispara el proceso;
- cuándo se ejecuta;
- qué información recibe;
- qué modifica;
- qué ocurre si falla;
- si existe retry;
- si puede ejecutarse dos veces.

No clasifiques como asíncrono algo que únicamente esté planificado.

# Fase 10 — Errores y caminos alternativos

Para cada flujo crítico busca:

- validaciones fallidas;
- excepciones;
- rollbacks;
- respuestas de error;
- estados bloqueados;
- caminos alternativos;
- reintentos;
- cancelaciones;
- operaciones parciales.

Los diagramas deben mostrar caminos alternativos cuando sean relevantes para entender el funcionamiento real.

# Diagramas obligatorios

Genera como mínimo:

## 1. Mapa global del sistema

```mermaid
flowchart LR
```

Representa los grandes módulos y sus conexiones.

## 2. Flujo funcional

Uno por proceso de negocio importante.

```mermaid
flowchart TD
```

## 3. Secuencia de ejecución

Para operaciones críticas.

```mermaid
sequenceDiagram
```

## 4. Estados

Para procesos con ciclo de vida.

```mermaid
stateDiagram-v2
```

## 5. Dependencias entre módulos

```mermaid
flowchart LR
```

Diferencia claramente:

- dependencia;
- lectura;
- escritura;
- validación;
- evento;
- llamada HTTP;
- tarea asíncrona.

## 6. Flujo de datos

Cuando sea útil genera:

```mermaid
flowchart LR
```

mostrando:

`Origen → Transformación → Persistencia → Consumidor`

## 7. Flujo end-to-end

Para los procesos más importantes genera una vista completa:

```text
USUARIO
   ↓
FRONTEND
   ↓
API
   ↓
VIEW
   ↓
SERVICE
   ↓
MODELO
   ↓
BASE DE DATOS
   ↓
OTRO MÓDULO
   ↓
RESULTADO
```

Debe representar únicamente la ejecución realmente confirmada.

# Salida Markdown

Crear:

`docs/architecture/01-system-map.md`

Debe contener:

1. Resumen ejecutivo.
2. Inventario de módulos.
3. Responsabilidad de cada módulo.
4. Mapa global.
5. Dependencias.
6. Flujos de negocio.
7. Flujos técnicos de ejecución.
8. Máquinas de estado.
9. Integraciones externas.
10. Procesos automáticos.
11. Puntos de entrada.
12. Puntos de persistencia.
13. Dependencias circulares.
14. Inconsistencias encontradas.
15. Elementos no confirmados.
16. Evidencia código → conclusión.

# Matriz obligatoria

Construye además:

| Origen | Acción | Destino | Mecanismo | Evidencia |
|---|---|---|---|---|

Ejemplo:

| React Producción | Crear corrida | API Producción | HTTP POST | archivo:líneas |
| Producción | Consultar liberación | Calidad | Service/ORM | archivo:líneas |
| Calidad | Liberar lote | Inventario | Service | archivo:líneas |

# Matriz de flujo

Genera también cuando el sistema tenga múltiples procesos:

| Flujo | Entrada | Componentes | Persistencia | Resultado | Estado |
|---|---|---|---|---|---|

Esto debe permitir entender rápidamente qué recorrido sigue cada operación principal.

# Reporte visual HTML

Además del documento Markdown debes generar un reporte HTML visual.

Este reporte está destinado únicamente a facilitar la comprensión del sistema.

## Carpeta obligatoria

Todos los archivos HTML generados por esta Skill deben guardarse exclusivamente en:

`docs/architecture/html/`

Archivo principal:

`docs/architecture/html/system-flow.html`

Si necesitas separar diagramas puedes crear:

- `docs/architecture/html/system-flow.html`
- `docs/architecture/html/business-flows.html`
- `docs/architecture/html/runtime-flows.html`
- `docs/architecture/html/state-machines.html`
- `docs/architecture/html/module-dependencies.html`

Todos deben permanecer dentro de:

`docs/architecture/html/`

# Aislamiento absoluto del sistema

Los HTML son documentación.

NO forman parte del sistema productivo.

No modificar para generar estos reportes:

- frontend/
- backend/
- templates/
- static/
- public/
- src/
- package.json
- package-lock.json
- vite.config.*
- settings.py
- urls.py
- nginx
- Dockerfile
- docker-compose*
- CI/CD
- configuración productiva.

No:

- agregues rutas;
- agregues endpoints;
- publiques los HTML mediante Django;
- integres los HTML dentro de React;
- agregues componentes al frontend;
- modifiques el build;
- agregues dependencias npm;
- agregues dependencias Python;
- modifiques Docker;
- modifiques infraestructura.

La carpeta:

`docs/architecture/html/`

debe poder eliminarse completamente sin alterar el funcionamiento del sistema.

# Objetivo del HTML

El HTML debe permitir responder visualmente:

- ¿cómo entra una acción al sistema?
- ¿qué módulo la recibe?
- ¿qué módulo llama después?
- ¿qué servicios intervienen?
- ¿qué datos se consultan?
- ¿qué datos se escriben?
- ¿qué validaciones bloquean el flujo?
- ¿qué módulo autoriza continuar?
- ¿qué estados atraviesa?
- ¿dónde termina el proceso?
- ¿qué otros módulos dependen del resultado?
- ¿qué ocurre en caso de error?
- ¿existen procesos asíncronos?

# Contenido mínimo del HTML

Debe incluir:

1. Resumen general.
2. Mapa global del sistema.
3. Inventario de módulos.
4. Flujos funcionales.
5. Flujos técnicos.
6. Secuencias de ejecución.
7. Máquinas de estado.
8. Dependencias entre módulos.
9. Integraciones externas.
10. Procesos automáticos.
11. Persistencia.
12. Caminos alternativos.
13. Dependencias circulares.
14. Elementos no confirmados.
15. Evidencia.

# Organización visual

El HTML debe tener una navegación simple.

Ejemplo:

- Resumen
- Sistema
- Módulos
- Flujos de negocio
- Runtime
- Estados
- Dependencias
- Datos
- Automatizaciones
- Errores
- Evidencia

Puede utilizar:

- tabla de contenidos;
- enlaces internos;
- tarjetas;
- secciones desplegables;
- tablas;
- Mermaid;
- leyendas;
- badges.

No construyas una aplicación web compleja.

Es documentación técnica.

# Vista global

La primera sección visual debe mostrar una vista sencilla de alto nivel.

Ejemplo conceptual:

```text
USUARIO
   ↓
FRONTEND
   ↓
API
   ↓
BACKEND
   ↓
SERVICIOS
   ↓
BASE DE DATOS
   ↓
OTROS MÓDULOS
```

Debajo debe existir una versión más detallada basada en el repositorio real.

# Vista por proceso

Cada proceso principal debe tener su propia sección.

Ejemplo:

## Proceso: Crear producción

Mostrar:

```text
Usuario
   ↓
Pantalla producción
   ↓
POST /api/...
   ↓
ViewSet
   ↓
Service
   ↓
Modelo
   ↓
PostgreSQL
   ↓
Respuesta
```

Y debajo:

- entrada;
- reglas;
- validaciones;
- persistencia;
- resultado;
- evidencia.

# Vista de estados

Para entidades con ciclo de vida muestra:

```text
PENDIENTE
   ↓
EN_PROCESO
   ↓
CALIDAD
   ↓
LIBERADO
   ↓
FINALIZADO
```

Solo si esos estados existen realmente.

El HTML debe dejar claro:

- quién provoca la transición;
- qué condición se exige;
- qué bloquea la transición.

# Vista de dependencias

Debe existir una sección que muestre claramente:

`QUIÉN DEPENDE DE QUIÉN`

Ejemplo:

```text
Recepción
   ↓
Producción
   ↓
Calidad
   ↓
Inventario
   ↓
Despacho
```

Pero únicamente si el código confirma estas relaciones.

# Tipos de conexión

Diferencia visualmente cuando sea posible:

`HTTP`

`ORM`

`SERVICE`

`EVENT`

`SIGNAL`

`ASYNC JOB`

`READ`

`WRITE`

`VALIDATE`

`BLOCK`

# Interactividad documental

Cuando sea posible, el HTML puede incluir:

- secciones colapsables;
- navegación interna;
- zoom del navegador;
- diagramas Mermaid;
- agrupación por módulo;
- agrupación por proceso.

No agregues JavaScript complejo salvo que sea estrictamente documental.

# Mermaid

Los diagramas Mermaid generados en Markdown deben reutilizarse cuando sea posible dentro del HTML.

Si utilizas Mermaid mediante CDN:

- úsalo únicamente dentro del HTML;
- no agregues Mermaid como dependencia del proyecto;
- no modifiques package.json;
- no ejecutes npm install solo para documentación.

# Evidencia en HTML

Cada flujo debe mantener trazabilidad hacia código.

Ejemplo:

```text
FLUJO-004
Crear corrida de secado

Frontend:
frontend/src/pages/Secado.tsx:80-130

API:
backend/produccion/views.py:210-280

Service:
backend/produccion/services.py:400-470

Persistencia:
backend/produccion/models.py:150-230
```

No elimines evidencia para simplificar visualmente el documento.

# Inconsistencias

Si descubres que:

- frontend espera algo que backend no entrega;
- documentación describe un flujo distinto;
- un endpoint no tiene consumidor;
- un estado no tiene transición;
- una transición nunca se ejecuta;
- existen rutas duplicadas;
- existen servicios aparentemente abandonados;

debes documentarlo.

Clasifica:

`INCONSISTENCIA`

`POSIBLE CÓDIGO MUERTO`

`NO CONFIRMADO`

No elimines ni modifiques código.

# Dependencias circulares

Cuando detectes algo equivalente a:

```text
Producción
   ↓
Calidad
   ↓
Inventario
   ↓
Producción
```

debes:

1. demostrar la relación;
2. mostrarla en el diagrama;
3. indicar archivos implicados;
4. explicar el posible riesgo.

No propongas aquí una refactorización completa.

El Architecture Auditor y Improvement Planner analizarán posteriormente la solución.

# Flujos críticos

Identifica los flujos que tengan mayor impacto operativo.

Para cada uno indica:

`CRÍTICO`

`IMPORTANTE`

`SECUNDARIO`

según el impacto funcional encontrado.

No confundas esta clasificación con severidad de seguridad o arquitectura.

# Regla AS-IS

Esta Skill documenta:

`AS-IS`

Su trabajo principal es explicar cómo funciona el sistema hoy.

No debe diseñar arquitectura futura.

No debe mezclar mejoras propuestas dentro de los diagramas actuales.

Si aparece una posible mejora durante el análisis, puede registrarla brevemente como:

`OBSERVACIÓN PARA AUDITORÍA`

pero no debe rediseñar el sistema.

# Criterio de finalización

El análisis NO está completo solamente porque hayas leído muchos archivos.

Está completo cuando puedes explicar:

`entrada → ejecución → reglas → persistencia → dependencias → resultado`

para cada flujo principal.

Antes de terminar comprueba:

- ¿seguí realmente las llamadas?
- ¿demostré las conexiones?
- ¿hay conexiones dibujadas sin evidencia?
- ¿confundí intención documental con implementación real?
- ¿existen ramas alternativas?
- ¿existen operaciones background?
- ¿existen transacciones?
- ¿existen bloqueos?
- ¿existen side effects?
- ¿existen dependencias implícitas?
- ¿identifiqué quién crea cada dato?
- ¿identifiqué quién lo modifica?
- ¿identifiqué quién autoriza continuar?
- ¿identifiqué dónde termina cada proceso?
- ¿documenté errores y caminos alternativos?
- ¿diferencié claramente AS-IS de cualquier idea futura?

# Archivos mínimos esperados

Al finalizar deben existir como mínimo:

`docs/architecture/01-system-map.md`

`docs/architecture/html/system-flow.html`

# Regla final de seguridad

El análisis debe ser de solo lectura sobre el sistema.

Está permitido crear o actualizar únicamente documentación asociada al análisis.

No:

- modifiques código;
- refactorices;
- corrijas bugs;
- cambies dependencias;
- modifiques configuraciones;
- cambies base de datos;
- ejecutes migraciones destructivas;
- alteres infraestructura.

La eliminación completa de:

`docs/architecture/html/`

NO debe afectar:

- frontend;
- backend;
- API;
- base de datos;
- tests;
- configuración;
- despliegue;
- dependencias;
- comportamiento funcional.

Si para generar el reporte visual necesitas modificar el sistema productivo, NO lo hagas.

Genera una alternativa aislada dentro de documentación.