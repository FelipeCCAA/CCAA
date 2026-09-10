# Registro de implementación

## Bloque 1 — Auditoría de escrituras masivas críticas

### Implementado

Se incorporaron envolturas auditables para `bulk_create`, `bulk_update` y `QuerySet.update`. Capturan una fila por objeto, diff `[antes, después]`, tenant, actor, IP y origen dentro de la misma transacción.

### Backend

- Calidad: cambios masivos de estado de pallets, silos y corridas.
- Procesos: creación/consumo/liberación de reservas y bloqueo de TK tras Descremación.
- Estandarización: movimientos físicos creados en lote.
- Los timestamps `auto_now` ya no generan falsos cambios: el registro posee su propia `fecha_hora`.

### Frontend

Sin cambios de contrato ni interfaz en este bloque.

### Flujo

Liberar/rechazar/bloquear, cancelar una ejecución, reservar/cerrar Descremado y transferir una mezcla conservan ahora el rastro de cada fila física afectada.

### Pruebas

- `auditoria.tests_registro`: 21/21.
- Permisos/rutas focales previas: 30/30.
- Descremado + bloqueo transversal de Calidad: sin fallos dentro de la ejecución combinada.
- `estandarizacion.tests_vale`: 25 errores de fixture preexistentes (faltan análisis vigentes/rutas); no corresponden al cambio de auditoría.
- Frontend unitario: 22/22; TypeScript limpio.
- Ruff, compileall, `makemigrations --check` y `git diff --check`: limpios.

### Siguiente bloque

Bandeja `Mi Producción` filtrada por etapa/área, con acciones realmente autorizadas y admin global.

## Bloque 2 — Bandeja operacional por área

### Implementado

La bandeja liviana de ejecuciones dejó de ser una consulta transversal para los operadores. El alcance ahora se deriva en backend desde el área del perfil y no desde filtros enviados por el navegador.

### Backend

- Condensación recibe Estandarización, Descremación, Evaporación, Condensación, Mantequilla y Transferencia.
- Secado recibe únicamente Secado.
- Administración conserva el alcance global.
- Áreas no operadoras, incluida Calidad, no reciben tareas accionables desde esta bandeja; sus controles permanecen en sus módulos especializados.
- Los perfiles productivos sin área fallan de forma segura con una bandeja vacía.
- `acciones_permitidas` se calcula además contra la autorización efectiva del usuario.
- Los indicadores de ejecuciones activas, espera de Calidad, equipos ocupados y bloqueos usan el mismo alcance por área. `Materiales listos planta` se mantiene explícitamente transversal.

### Frontend

- Se agregó `Mi trabajo pendiente` al inicio de Producción, antes de navegación secundaria e historial.
- Cada tarjeta muestra proceso, etapa, equipo, estado, entrada y salida.
- La acción principal permite iniciar o reanudar cuando la transición está autorizada.
- `Abrir tarea` conduce al módulo operacional correspondiente.
- Se incorporaron estados de carga, vacío, error y actualización manual.
- El historial de lotes pasó a carga bajo demanda: no solicita catálogo, búsqueda ni tabla hasta que el usuario decide consultarlo.

### Pruebas

- `procesos.tests_permisos_operacionales`: 9/9.
- Caso específico de bandeja: separación Condensación/Secado, Calidad vacía, Administración global y exclusión de cerradas.
- Ruff: limpio en los archivos backend modificados.
- TypeScript: limpio.
- ESLint: los dos archivos de Producción modificados están limpios. La corrida global mantiene tres hallazgos preexistentes en Estandarización.

### Siguiente bloque

Construir bandejas específicas de bloqueos y espera de Calidad sin duplicar la lógica de negocio entre pantallas.

## Bloque 3 — Bloqueos y espera de Calidad

### Implementado

Se separó la cola de resultados productivos que Calidad debe decidir del listado general de expedientes de lotes. Las operaciones de liberar y rechazar siguen usando los servicios y validaciones existentes; no se creó una segunda lógica de decisión.

### Backend

- Nuevo `GET /api/calidad/resultados-proceso/` para la bandeja pendiente de resultados intermedios y productos a granel.
- El límite de 50 se aplica solo a pendientes; las decisiones históricas ya no pueden desplazar trabajo sin resolver.
- El contrato histórico `incluir_procesos=1` se conserva temporalmente para compatibilidad.
- La bandeja de Producción incorpora el motivo del último evento que llevó una ejecución al estado bloqueado y la fecha del cambio de estado.
- El motivo se obtiene con subconsultas, evitando una consulta adicional por tarjeta.

### Frontend

- Centro de Calidad carga expedientes y resultados productivos mediante contratos independientes, con errores y recargas independientes.
- Liberar o rechazar actualiza únicamente la cola productiva afectada.
- En `Mi trabajo pendiente`, las ejecuciones bloqueadas aparecen primero, muestran su causa y usan señalización explícita.
- Las ejecuciones esperando Calidad se distinguen de las tareas operables.
- Bloqueadas y pendientes de Calidad no ofrecen inicio/reanudación directa; el operador debe abrir el flujo correspondiente y resolver la causa.

### Pruebas

- Permisos y bandeja operacional más liberación de precondensado: 10/10.
- Se verifica la exposición del motivo de bloqueo y el nuevo endpoint de Calidad.
- Ruff: limpio.
- TypeScript y ESLint focal: limpios.

### Siguiente bloque

Eliminar progresivamente el contrato legado de procesos dentro de expedientes y mejorar la priorización temporal de Calidad con paginación y antigüedad operacional explícita.

## Bloque 4 — Priorización temporal de Calidad

### Implementado

La cola de resultados productivos de Calidad dejó de depender de un corte fijo. Ahora posee paginación propia y orden FIFO explícito para que una muestra antigua no sea desplazada indefinidamente por corridas nuevas.

### Backend

- `GET /api/calidad/resultados-proceso/` responde con `resultados`, `total`, `pagina`, `limite`, `hay_mas` y `orden`.
- Tamaño predeterminado de 20 y máximo de 50 resultados por página.
- Orden estable por `registrada_en` e identificador, del pendiente más antiguo al más reciente.
- Cada resultado incluye `registrada_en` para explicar su antigüedad operacional.
- La consulta cuenta antes de paginar y carga análisis exclusivamente para las salidas de la página actual.
- El endpoint legado conserva su respuesta anterior y su orden histórico.

### Frontend

- Centro de Calidad consume el contrato paginado y muestra el total real de pendientes productivos.
- Navegación anterior/siguiente accesible y localizada, sin bloquear las demás bandejas de Calidad.
- Se comunica explícitamente que los casos más antiguos aparecen primero.
- Cada tarjeta muestra desde cuándo espera la decisión.

### Pruebas

- Contrato de bandeja verificado con total, página, fin de páginas, orden FIFO y timestamp.
- Flujo de liberación de precondensado: 1/1.
- Ruff: limpio.
- TypeScript y ESLint focal: limpios.

### Siguiente bloque

Agregar indicadores de preparación de análisis —listo para decidir versus esperando muestra— y evitar que el operador de Calidad abra casos que aún no poseen antecedentes suficientes.

## Bloque 5 — Preparación de decisiones de Calidad

### Implementado

La bandeja distingue el estado del proceso productivo de la preparación documental de su decisión. Un resultado puede estar pendiente de Calidad y, al mismo tiempo, seguir esperando un análisis válido.

### Backend

- Cada resultado informa `preparacion`: `listo_liberar`, `requiere_decision` o `esperando_analisis`.
- `habilita_liberacion` se calcula individualmente para cada análisis y es la autoridad de presentación del botón frontend.
- Para análisis de silo se comprueban firma de realización, firma de visualización, fecha posterior al resultado, inhibidores, vigencia y densidad cuando el balance másico la exige.
- La vigencia se obtiene mediante subconsultas agregadas de ingresos posteriores, evitando consultas por análisis.
- Para análisis de lote se reutiliza la evaluación contra la especificación vigente o congelada.
- Django continúa revalidando todo dentro de la operación transaccional de liberación; la clasificación de bandeja no reemplaza la regla de dominio.

### Frontend

- Los casos sin análisis firmado aparecen en `Esperando análisis o firma`, como tarjetas informativas sin formulario de decisión.
- Los casos con antecedentes aparecen en las bandejas de granel o silo.
- Se diferencia visualmente un análisis que habilita liberación de uno que requiere revisar desviaciones o rechazar.
- El botón `Liberar` depende de `habilita_liberacion`, no de una reinterpretación parcial en React.
- La cabecera de paginación informa cuántos casos de la página están listos y cuántos esperan antecedentes.

### Pruebas

- Se verifica el cambio `esperando_analisis` → `listo_liberar` después de registrar un análisis confirmado y firmado.
- Se verifica que el análisis conforme exponga `habilita_liberacion=true`.
- Flujo de liberación de precondensado: 1/1.
- Ruff, TypeScript y ESLint focal: limpios.

### Siguiente bloque

Incorporar filtros de puesto y prioridad en Calidad —tipo de resultado, preparación y búsqueda por lote/corrida— manteniendo el filtrado y la paginación en backend.

## Bloque 6 — Filtros operacionales de Calidad

### Implementado

La cola productiva puede acotarse sin descargar resultados ajenos al trabajo actual. El total y la paginación se calculan sobre el conjunto filtrado dentro del tenant del usuario.

### Backend

- Filtro `tipo` por etapa productiva, validado contra los tipos definidos por `EtapaProceso`.
- Filtro `preparacion=con_analisis|esperando_analisis` basado en existencia de antecedentes confirmados, firmados y posteriores al resultado.
- Búsqueda `buscar` sobre corrida, lote, producto y código de silo, acotada a 80 caracteres.
- Los filtros se aplican antes de `count`, orden y paginación.
- La respuesta devuelve los filtros normalizados realmente aplicados.
- Tipos o estados de preparación desconocidos responden 400 en lugar de producir resultados ambiguos.

### Frontend

- Selector de proceso y selector de disponibilidad de antecedentes.
- Búsqueda explícita por lote, corrida, producto o silo.
- Todo cambio de criterio vuelve a la primera página y recarga únicamente la cola productiva.
- Repetir una búsqueda permite actualizar el resultado sin cambiar el criterio.
- Los controles tienen etiquetas y límites visibles para operación por teclado.

### Pruebas

- Se verifican filtros por Condensación, Secado, búsqueda por corrida y disponibilidad de análisis.
- Se verifica rechazo 400 para un tipo productivo desconocido.
- Flujo completo de precondensado y liberación: 1/1.
- Ruff, TypeScript y ESLint focal: limpios.

### Siguiente bloque

Extraer la construcción de la bandeja de Calidad desde la vista HTTP hacia un servicio de consulta dedicado y cubrir su rendimiento y aislamiento tenant con pruebas específicas.

## Bloque 7 — Servicio de consulta de Calidad

### Implementado

La construcción del modelo de lectura productivo salió de la vista HTTP. La consulta, el alcance tenant, la carga agrupada de análisis, la evaluación contra especificaciones y la serialización de la bandeja viven ahora en un selector dedicado y reutilizable.

### Backend

- Nuevo `calidad.consultas.consultar_resultados_intermedios`, cuyo contexto de seguridad es un usuario explícito y no una petición HTTP.
- El selector aplica internamente el alcance por empresa y sucursal antes de contar, paginar o cargar relaciones.
- Los filtros, el orden FIFO, la preparación, las especificaciones y el contrato de cada resultado se conservan sin cambios.
- La vista `resultados_proceso` queda limitada a validar parámetros, normalizar paginación, invocar la consulta y formar la respuesta HTTP.
- El contrato legado de expedientes reutiliza temporalmente el mismo selector; no mantiene una segunda implementación.
- El filtro que delimita qué salidas requieren decisión y la traducción físico-química del análisis de silo se comparten entre lectura y comandos de liberación.

### Pruebas

- Prueba específica de aislamiento tenant con resultados simultáneos en dos empresas: el selector devuelve únicamente la empresa y planta autorizadas.
- Prueba antirregresión N+1: la cantidad de consultas es idéntica con 1 y con 11 resultados.
- Servicio de consulta: 2/2.
- Flujo real de condensación, consulta, análisis y liberación: 1/1.
- Ruff y `manage.py check`: limpios.

### Siguiente bloque

Retirar de forma controlada el parámetro legado `incluir_procesos` del listado de expedientes, una vez verificados todos sus consumidores, y dejar un único contrato paginado para el trabajo productivo de Calidad.
