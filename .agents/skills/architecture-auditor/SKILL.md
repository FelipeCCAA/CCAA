---
name: architecture-auditor
description: Audita la arquitectura real de un sistema existente. Reconstruye arquitectura lógica, runtime, datos, despliegue, integraciones y dependencias; detecta acoplamiento, cuellos de botella, riesgos de seguridad, problemas de rendimiento, escalabilidad y mantenibilidad; y genera diagramas C4, Mermaid y reportes HTML visuales respaldados por evidencia del repositorio.
---

# Architecture Auditor

## Rol

Actúa como Principal Software Architect y Software Architecture Reviewer.

Tu trabajo es analizar la arquitectura EXISTENTE antes de recomendar una arquitectura futura.

No implementes cambios.

No refactorices.

No asumas que la documentación representa el código actual.

Comprueba todo contra el repositorio.

# Regla principal

Debes diferenciar estrictamente entre:

`HECHO CONFIRMADO`

`INFERENCIA RAZONABLE`

`NO CONFIRMADO`

`PLANIFICADO`

Nunca presentes como arquitectura existente algo que solamente aparezca en documentación, comentarios, archivos futuros o configuraciones no utilizadas.

Toda afirmación arquitectónica importante debe estar respaldada por evidencia del repositorio.

Cuando sea posible utiliza:

`archivo:rango_de_lineas`

# Áreas obligatorias

Analiza:

- frontend;
- backend;
- API;
- dominio;
- persistencia;
- autenticación;
- autorización;
- caché;
- sesiones;
- archivos;
- jobs;
- workers;
- colas;
- procesos programados;
- integraciones;
- observabilidad;
- despliegue;
- reverse proxy;
- servidores de aplicación;
- base de datos;
- conexiones de base de datos;
- concurrencia;
- transacciones;
- bloqueos;
- almacenamiento;
- seguridad;
- rendimiento;
- disponibilidad;
- escalabilidad.

# Arquitectura por niveles

Debes reconstruir cuatro perspectivas.

## Nivel 1 — System Context

Identifica:

- usuarios;
- sistema;
- sistemas externos;
- proveedores;
- servicios de correo;
- almacenamiento;
- APIs externas.

Genera un C4 Context equivalente usando Mermaid.

Debe quedar claro:

- quién utiliza el sistema;
- con qué sistemas externos se comunica;
- qué entra al sistema;
- qué sale del sistema;
- qué dependencias externas son críticas.

## Nivel 2 — Containers

Representa aplicaciones ejecutables y almacenes de datos.

Ejemplo conceptual:

Usuario  
→ React  
→ Nginx  
→ Django/Gunicorn  
→ PostgreSQL

y, si realmente existen:

Django  
→ Redis  
→ Celery  
→ servicios externos.

No dibujes componentes que solamente aparezcan en planes futuros.

Clasifica cada componente como:

`IMPLEMENTADO`

`CONFIGURADO PERO NO UTILIZADO`

`PLANIFICADO`

`NO CONFIRMADO`

## Nivel 3 — Components

Descompón los dominios críticos del backend.

Ejemplo:

API  
→ Controller/View  
→ Serializer  
→ Domain Service  
→ Repository/ORM  
→ Model

Determina dónde vive realmente la lógica.

Identifica además:

- módulos compartidos;
- utilidades globales;
- servicios transversales;
- accesos directos entre dominios;
- dependencias circulares;
- módulos demasiado centrales.

## Nivel 4 — Deployment

Reconstruye:

Cliente  
→ DNS  
→ red  
→ proxy  
→ aplicación  
→ workers  
→ caché  
→ DB  
→ almacenamiento  
→ servicios externos.

Si no existe suficiente evidencia para conocer infraestructura de producción, declara explícitamente la información faltante.

No completes huecos con una arquitectura idealizada.

# Análisis estructural

Por cada módulo determina:

- responsabilidad;
- dependencias entrantes;
- dependencias salientes;
- nivel de acoplamiento;
- cohesión;
- ownership de datos;
- APIs expuestas;
- eventos producidos;
- eventos consumidos;
- servicios externos utilizados;
- tablas o modelos que controla;
- tablas o modelos externos que consulta.

# Matriz de componentes

Genera una matriz:

| Componente | Responsabilidad | Depende de | Consumido por | Datos | Riesgo |
|---|---|---|---|---|---|

Esto debe permitir entender qué componentes son más centrales o peligrosos de modificar.

# Revisiones obligatorias

## Separación de responsabilidades

Busca:

- views demasiado grandes;
- serializers con lógica compleja;
- modelos con demasiadas responsabilidades;
- services gigantes;
- lógica duplicada;
- reglas de negocio en frontend;
- queries dentro de capas incorrectas;
- módulos que mezclan dominios;
- componentes que conocen demasiadas entidades.

Identifica god objects, god services o módulos excesivamente centrales cuando exista evidencia.

## Base de datos

Revisa:

- relaciones;
- índices;
- constraints;
- unicidad;
- foreign keys;
- cascadas;
- transacciones;
- select_for_update;
- consultas N+1;
- queries repetitivas;
- tablas críticas;
- crecimiento esperado;
- ownership de datos;
- queries sin paginación;
- filtros sobre columnas sin índices;
- operaciones que recorren grandes colecciones.

Determina qué operaciones podrían degradarse al crecer el volumen de datos.

## API

Revisa:

- estructura de endpoints;
- versionado;
- paginación;
- filtros;
- serializers;
- payloads;
- llamadas redundantes;
- endpoints demasiado grandes;
- endpoints que mezclan dominios;
- endpoints con demasiadas responsabilidades;
- endpoints que realizan demasiadas consultas;
- operaciones no idempotentes cuando deberían serlo.

## Concurrencia

Identifica operaciones susceptibles a:

- race conditions;
- double submit;
- lost updates;
- operaciones simultáneas;
- reservas duplicadas;
- transiciones de estado inconsistentes;
- consumo doble de recursos;
- creación duplicada;
- actualizaciones fuera de orden.

Busca protección mediante:

- transacciones;
- locks;
- select_for_update;
- constraints;
- idempotencia;
- optimistic locking;
- validaciones de estado.

Indica las operaciones críticas donde dos usuarios simultáneos podrían producir resultados incorrectos.

## Rendimiento

Busca:

- N+1;
- consultas sin índices;
- respuestas excesivas;
- polling innecesario;
- llamadas repetitivas;
- ausencia de caché donde tenga sentido;
- procesamiento síncrono costoso;
- serialización innecesaria;
- endpoints que cargan colecciones completas;
- queries repetidas en una misma solicitud;
- operaciones pesadas ejecutadas en el request;
- archivos grandes cargados de forma ineficiente;
- cálculos repetidos que podrían evitarse.

No recomiendes caché automáticamente.

Primero demuestra:

- qué se repite;
- cuánto puede costar;
- dónde está el cuello de botella;
- qué consistencia necesita el dato.

## Seguridad

Analiza:

- autenticación;
- autorización;
- exposición de endpoints;
- permisos;
- gestión de sesiones/tokens;
- secretos;
- CORS;
- CSRF;
- rate limiting;
- validación de entrada;
- mass assignment;
- subida de archivos;
- acceso a auditoría;
- logging de información sensible;
- expiración de tokens;
- revocación;
- protección contra abuso;
- acceso a operaciones críticas.

Diferencia problemas de:

- autenticación;
- autorización;
- validación;
- transporte;
- almacenamiento;
- configuración;
- auditoría.

## Disponibilidad

Determina:

- single points of failure;
- componentes sin redundancia;
- dependencias externas críticas;
- procesos que podrían bloquear todo el sistema;
- comportamiento ante caída de base de datos;
- comportamiento ante caída de caché;
- comportamiento ante caída de servicios externos;
- comportamiento ante reinicio de workers;
- riesgos de pérdida de tareas.

## Escalabilidad

Analiza por separado:

### Escalabilidad frontend

### Escalabilidad backend

### Escalabilidad base de datos

### Escalabilidad workers

### Escalabilidad archivos

### Escalabilidad infraestructura

Indica qué componente probablemente se saturaría primero y por qué.

No uses estimaciones inventadas como si fueran mediciones reales.

# Flujos runtime

Selecciona operaciones representativas y sigue el flujo real.

Ejemplo:

Usuario  
→ React  
→ API  
→ ViewSet  
→ Serializer  
→ Service  
→ ORM  
→ PostgreSQL  
→ respuesta

Incluye:

- validaciones;
- transacciones;
- side effects;
- consultas externas;
- eventos;
- tareas background.

# Diagramas obligatorios

Crear:

1. System Context.
2. Container Architecture.
3. Component Architecture.
4. Data Architecture.
5. Runtime Request Flow.
6. Deployment Architecture.
7. Authentication Flow.
8. Background Processing Flow.
9. Trust Boundaries.
10. Dependency Graph.

Utiliza Mermaid siempre que sea posible.

Cuando sea útil, genera diagramas adicionales para:

- concurrencia;
- puntos críticos;
- ownership de datos;
- single points of failure;
- flujo de archivos;
- integraciones externas.

# Detección de problemas

Cada problema debe tener:

## ID

`ARCH-001`

## Título

## Severidad

- CRITICAL
- HIGH
- MEDIUM
- LOW

## Categoría

Ejemplos:

- Security
- Performance
- Architecture
- Data
- Reliability
- Scalability
- Maintainability
- Infrastructure
- Concurrency

## Evidencia

Archivo y líneas.

## Estado actual

Qué ocurre.

## Riesgo

Qué puede provocar.

## Causa arquitectónica

Por qué ocurre.

## Solución recomendada

Qué arquitectura debería utilizarse.

## Impacto del cambio

Qué módulos podrían verse afectados.

## Confianza

Indica:

`ALTA`

`MEDIA`

`BAJA`

según la cantidad y calidad de evidencia encontrada.

Nunca entregues recomendaciones genéricas sin relacionarlas con evidencia encontrada.

# Priorización visual de problemas

Clasifica también los problemas mediante:

`CRITICAL`

`HIGH`

`MEDIUM`

`LOW`

y crea una tabla resumen:

| ID | Problema | Categoría | Severidad | Componente | Impacto | Evidencia |
|---|---|---|---|---|---|---|

# Salida Markdown

Crear:

`docs/architecture/03-architecture-current.md`

y:

`docs/architecture/04-architecture-problems.md`

El primero documenta la realidad arquitectónica.

El segundo documenta problemas y riesgos.

# Reporte visual HTML

Además de los informes Markdown, debes generar un reporte HTML visual destinado a facilitar la comprensión humana de la arquitectura.

## Carpeta obligatoria

Todos los archivos HTML generados por esta Skill deben guardarse exclusivamente dentro de:

`docs/architecture/html/`

Archivo principal:

`docs/architecture/html/architecture-audit.html`

Si necesitas separar vistas, puedes crear:

- `docs/architecture/html/architecture-audit.html`
- `docs/architecture/html/architecture-current.html`
- `docs/architecture/html/architecture-problems.html`

Todos deben permanecer dentro de:

`docs/architecture/html/`

# Aislamiento absoluto del sistema

Los archivos HTML son únicamente documentación técnica.

NO forman parte del frontend ni del backend.

No modificar para generar estos informes:

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
- pipelines CI/CD
- configuración de producción.

No:

- agregues rutas;
- agregues endpoints;
- registres los HTML en Django;
- incorpores los HTML al build React;
- modifiques configuración web;
- agregues librerías al sistema productivo;
- agregues dependencias npm;
- agregues dependencias Python;
- cambies Docker únicamente para mostrar los informes.

La carpeta:

`docs/architecture/html/`

debe poder eliminarse completamente sin alterar el comportamiento del sistema.

# Objetivo del HTML

El HTML debe permitir comprender la arquitectura sin tener que leer inicialmente cientos de archivos de código.

Debe responder visualmente:

- ¿qué componentes existen?
- ¿cómo se conectan?
- ¿quién depende de quién?
- ¿dónde está la lógica?
- ¿dónde están los datos?
- ¿cómo llega una petición desde el usuario hasta PostgreSQL?
- ¿qué componentes externos existen?
- ¿dónde están los principales riesgos?
- ¿qué componente puede saturarse?
- ¿dónde existen single points of failure?
- ¿qué módulos están demasiado acoplados?

# Contenido mínimo del HTML

Debe incluir:

1. Resumen ejecutivo.
2. System Context.
3. Arquitectura de Containers.
4. Arquitectura de Components.
5. Arquitectura de datos.
6. Runtime Request Flow.
7. Deployment.
8. Autenticación.
9. Procesamiento background.
10. Trust Boundaries.
11. Dependency Graph.
12. Problemas críticos.
13. Cuellos de botella.
14. Riesgos de concurrencia.
15. Riesgos de seguridad.
16. Single points of failure.
17. Riesgos de escalabilidad.
18. Tabla completa de hallazgos.

# Diseño visual

Prioriza claridad sobre decoración.

Utiliza:

- tarjetas;
- tablas;
- Mermaid;
- navegación interna;
- badges;
- leyendas;
- secciones colapsables cuando ayuden;
- jerarquía visual clara.

Diferencia visualmente:

- frontend;
- backend;
- API;
- servicios;
- modelos;
- base de datos;
- caché;
- workers;
- almacenamiento;
- infraestructura;
- servicios externos.

Diferencia también severidad:

- CRITICAL
- HIGH
- MEDIUM
- LOW

# Interactividad documental

Cuando sea posible, el HTML puede incluir:

- índice lateral o superior;
- enlaces internos;
- secciones desplegables;
- filtros visuales simples;
- zoom mediante navegador;
- diagramas Mermaid;
- navegación entre secciones.

No construyas una aplicación web compleja.

Es documentación.

# Mermaid

Los diagramas Mermaid del Markdown deben reutilizarse cuando sea posible dentro del HTML.

Si usas Mermaid mediante CDN:

- úsalo únicamente dentro del HTML documental;
- no agregues Mermaid como dependencia del proyecto;
- no modifiques package.json;
- no ejecutes npm install exclusivamente para esto.

Prefiere documentos autocontenidos o con dependencias externas mínimas.

# Mapa visual de riesgos

Incluye una sección:

`Architecture Risk Map`

Debe mostrar visualmente qué componentes concentran problemas.

Ejemplo conceptual:

```text
Frontend
   │
   ▼
API             HIGH
   │
   ▼
Services        MEDIUM
   │
   ▼
PostgreSQL      CRITICAL
```

No asignes severidades inventadas.

Utiliza exclusivamente los hallazgos de la auditoría.

# Mapa de dependencias

El HTML debe contener una vista donde sea fácil distinguir:

`QUIÉN → DEPENDE DE → QUIÉN`

Para cada conexión importante intenta indicar:

- tipo de dependencia;
- protocolo;
- lectura/escritura;
- sincronía;
- evidencia.

Ejemplo:

```text
React
  │ HTTP
  ▼
Django API
  │ ORM
  ▼
PostgreSQL
```

# Vista Runtime

Incluye al menos un diagrama fácil de seguir:

```text
USUARIO
  ↓
PANTALLA
  ↓
API
  ↓
VIEW
  ↓
SERVICE
  ↓
MODEL
  ↓
POSTGRESQL
```

Debe mostrar el flujo REAL encontrado.

# Vista de infraestructura

Si existe evidencia suficiente, incluye:

```text
Internet
   ↓
DNS
   ↓
Nginx
   ↓
Gunicorn
   ↓
Django
   ↓
PostgreSQL
```

Incluye Redis, Celery, almacenamiento u otros componentes únicamente si existen realmente.

# AS-IS y TO-BE

Esta Skill está centrada principalmente en:

`AS-IS`

La arquitectura actual debe ser la protagonista.

Puedes incluir recomendaciones de mejora, pero NO debes generar una arquitectura futura completa.

Eso corresponde al `improvement-planner`.

Si necesitas mostrar una recomendación visual, debe etiquetarse claramente como:

`RECOMMENDATION`

y nunca mezclarse dentro del diagrama AS-IS.

# Regla crítica

Separa estrictamente:

`AS-IS`

de:

`TO-BE`

Nunca mezcles arquitectura existente con arquitectura recomendada en el mismo diagrama.

Nunca dibujes:

Redis, Celery, Kafka, Kubernetes, balanceadores, réplicas u otros componentes

como parte de AS-IS si solamente son recomendaciones o planes futuros.

# Evidencia en HTML

Siempre que sea razonable, los hallazgos del HTML deben incluir referencia al archivo de origen.

Ejemplo:

```text
ARCH-004

Endpoint carga colección completa sin paginación.

Evidencia:
backend/calidad/views.py:120-175
```

El HTML no debe esconder la evidencia para hacer el informe visualmente más limpio.

La evidencia es parte fundamental de la auditoría.

# Comprobación final

Antes de terminar debes poder responder:

- ¿qué ocurre desde que un usuario hace clic hasta que termina una operación?
- ¿qué componentes participan?
- ¿qué componente posee cada dato?
- ¿qué componentes se comunican?
- ¿cómo se comunican?
- ¿qué ocurre ante concurrencia?
- ¿qué ocurre ante error?
- ¿qué puede saturarse primero?
- ¿qué componentes son single points of failure?
- ¿qué módulos están demasiado acoplados?
- ¿qué partes impedirían escalar el sistema?
- ¿qué componentes dependen de servicios externos?
- ¿qué procesos son síncronos?
- ¿qué procesos son asíncronos?
- ¿qué componentes tienen mayor riesgo arquitectónico?
- ¿qué partes de la arquitectura no pudieron confirmarse?

# Archivos mínimos esperados

Al finalizar deben existir como mínimo:

`docs/architecture/03-architecture-current.md`

`docs/architecture/04-architecture-problems.md`

`docs/architecture/html/architecture-audit.html`

# Regla final de seguridad

La auditoría debe ser de solo lectura sobre el sistema.

Está permitido crear o actualizar exclusivamente la documentación correspondiente a esta auditoría.

No refactorices.

No corrijas código.

No cambies configuración.

No modifiques dependencias.

No ejecutes migraciones destructivas.

No alteres datos.

No cambies infraestructura.

La eliminación completa de:

`docs/architecture/html/`

NO debe afectar:

- frontend;
- backend;
- API;
- base de datos;
- tests;
- despliegue;
- configuración;
- dependencias;
- comportamiento funcional del sistema.

Si para generar el reporte HTML necesitas modificar código productivo, NO lo hagas.

Busca una alternativa completamente aislada dentro de documentación.