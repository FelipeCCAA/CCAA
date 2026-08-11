# Hardening y optimización para producción

Este documento convierte la auditoría técnica del 11 de agosto de 2026 en un
plan ejecutable. Las fases son deliberadamente secuenciales: no se inicia una
fase si la anterior deja fallos en sus controles de salida.

## Línea base comprobada

- `main` parte del commit `7f52d07`.
- Django detecta 805 pruebas, pero la configuración local con SQLite falla en
  una restricción de unicidad de inocuidad y no puede validar bloqueos reales.
- No existen Dockerfiles, Compose ni pipeline de CI versionados.
- PostgreSQL es el valor predeterminado, pero `DB_ENGINE=sqlite` continúa
  habilitando un modo operativo incompatible con las reglas transaccionales.
- `/api/salud/` solo prueba que el proceso HTTP responde; no comprueba la base.
- La configuración permite valores de desarrollo inseguros sin distinguir de
  forma explícita desarrollo, CI, staging y producción.
- ESLint y TypeScript pasan en la línea base del frontend.

## Fase 0 — Base segura y reproducible

Objetivo: que la aplicación arranque y se pruebe siempre sobre PostgreSQL, y
que una configuración insegura de producción falle antes de servir tráfico.

Cambios:

1. Eliminar el backend SQLite de `settings.py` y rechazar `DB_ENGINE` distinto
   de PostgreSQL con un error descriptivo.
2. Introducir `DJANGO_ENV` (`development`, `test`, `ci`, `staging`,
   `production`) y validación *fail-fast* de producción: `DEBUG`, clave,
   hosts, HTTPS, cookies, HSTS, orígenes CSRF y base PostgreSQL.
3. Separar liveness de readiness. Readiness ejecutará una consulta mínima a
   PostgreSQL y responderá 503 si la dependencia no está disponible.
4. Versionar imágenes reproducibles para frontend y backend, Compose con
   Nginx, Gunicorn y PostgreSQL en red interna, healthchecks y persistencia.
   Redis, PgBouncer y Celery no se incorporan todavía: pertenecen a las fases
   4 y 5 y requieren decisiones respaldadas por mediciones.
5. Crear CI con PostgreSQL que ejecute checks, migraciones pendientes, suite
   backend, TypeScript, ESLint y build.
6. Documentar variables, despliegue Ubuntu, backup y rollback.

Controles de salida:

- `manage.py check` y `check --deploy` pasan con configuración de producción.
- `makemigrations --check --dry-run` no detecta migraciones omitidas.
- suite completa sobre PostgreSQL sin pruebas de concurrencia saltadas.
- imágenes construyen, servicios internos no publican puertos y readiness
  cambia a 503 al perder PostgreSQL.
- TypeScript, ESLint y build pasan.

## Fase 1 — Tenancy, permisos y campos sensibles

Objetivo: separar rol (acción) de scope (empresa/sucursal) y eliminar accesos
cruzados o transiciones administrativas por asignación masiva.

Estrategia de migración:

1. Inventariar propiedad de tenant por modelo y relaciones heredables.
2. Añadir columnas inicialmente anulables e índices, sin reescribir tablas en
   una migración bloqueante.
3. Ejecutar un backfill auditable y detectar registros ambiguos.
4. Añadir servicios reutilizables de scope y aplicarlos a querysets, acciones,
   servicios y PK relacionadas.
5. Hacer las columnas obligatorias solo tras validar el backfill.
6. Separar serializers de lectura, escritura y acciones de dominio; asignar
   actor, estado y tenant desde el backend.

Controles de salida: pruebas negativas GET/PATCH/POST con IDs de otro tenant
en producción, recepción, calidad, inocuidad, inventario, compras,
planificación, procesos, maestros, usuarios y auditoría; las respuestas serán
404 para objetos fuera del scope y 403 para acciones sin rol.

## Fase 2 — Corrección funcional de paginación

Objetivo: que ningún registro desaparezca al superar la primera página.

- Clasificar cada endpoint como catálogo acotado o listado potencialmente
  grande.
- Para catálogos, usar un cliente común con límite total, detección de ciclos,
  cancelación y tipado de errores.
- Para listados, conservar paginación del servidor, búsqueda remota, filtros y
  debounce; no descargar el histórico.
- Añadir pruebas con 51 y más registros en todos los módulos consumidores.

## Fase 3 — Rendimiento medido

Objetivo: remover trabajo proporcional al histórico de las requests comunes.

Orden:

1. Paginar expedientes antes de ensamblar datos relacionados y mover filtros
   y agregaciones a PostgreSQL.
2. Recalcular alertas solo para insumos/bodegas afectados mediante agregación.
3. Calcular especificaciones vigentes en una pasada o consulta indexada.
4. Aplicar un rango temporal sensato al resumen de producción.
5. Consultar trazabilidad únicamente para lote, silos y ventana involucrada.
6. Recorrer genealogía por niveles con `deque`, límites de nodos/relaciones y
   señal explícita de truncamiento.
7. Añadir índices solo después de capturar consultas y `EXPLAIN ANALYZE`.

Controles de salida: escenarios reproducibles con 100, 1.000 y 10.000 lotes,
100.000 movimientos y 1.000 productos. Se registrarán hardware, queries,
latencia, memoria y comparación antes/después; no se fijarán SLO finales sin
medir el servidor objetivo.

## Fase 4 — Resistencia y control de conexiones

Objetivo: rechazar abuso antes del trabajo costoso y limitar recursos.

- Redis privado con healthcheck, timeouts, memoria acotada y política explícita
  ante caída.
- Throttling distribuido; login 15 intentos/cuenta/hora y 60/IP/hora antes de
  `authenticate()`, con pruebas que demuestren cero consultas de autenticación
  después del 429.
- Límites Nginx diferenciados para login, contraseña, uploads y endpoints
  pesados, preservando usuarios detrás de NAT.
- PgBouncer privado; seleccionar pool mode tras comprobar transacciones,
  prepared statements y persistencia de sesión usados por Django.
- Dimensionar workers/threads/timeouts de Gunicorn según CPU, RAM, latencia y
  conexiones reales, no mediante números genéricos.

## Fase 5 — Trabajo asíncrono

Objetivo: sacar de la request solo tareas que no requieren respuesta inmediata.

- Incorporar Celery para correo, MRP pesado, reportes/exportaciones y
  procesamiento de archivos que las mediciones justifiquen.
- Cada tarea tendrá idempotencia, timeout, reintentos limitados con backoff,
  registro de error y estado consultable.
- PostgreSQL continuará como fuente de verdad; Redis será broker/caché.

## Fase 6 — Operación, observabilidad y capacidad

Objetivo: operar, detectar degradación y recuperar el sistema.

- Logs estructurados con filtrado de credenciales y correlación de requests.
- Métricas HTTP, PostgreSQL/PgBouncer, Redis, Gunicorn, Celery y recursos.
- Readiness/liveness de todos los servicios, alertas y rotación de logs.
- Backups verificados mediante restauración y runbooks de incidente.
- Pruebas de carga no destructivas con 5, 10, 20 y 50 usuarios y presupuestos
  acordados a partir del hardware objetivo.
- Pipeline de despliegue con migraciones controladas, smoke tests y rollback.

## Regla de entrega

Cada fase termina con archivos modificados, evidencia de pruebas, comparación
de seguridad/rendimiento cuando corresponda, migraciones y su riesgo,
variables nuevas, comandos para Ubuntu, rollback y pendientes. Un control no
ejecutado se registra como pendiente; nunca se declara aprobado por inferencia.
