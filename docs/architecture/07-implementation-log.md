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

Extraer la construcción de la bandeja de Calidad desde la vista HTTP hacia un servicio de consulta dedicado y cubrir su rendimiento con pruebas específicas.

## Bloque 7 — Servicio de consulta de Calidad

### Implementado

La construcción del modelo de lectura productivo salió de la vista HTTP. La consulta, la carga agrupada de análisis, la evaluación contra especificaciones y la serialización de la bandeja viven ahora en un selector dedicado y reutilizable.

### Backend

- Nuevo `calidad.consultas.consultar_resultados_intermedios`, cuyo contexto de seguridad es un usuario explícito y no una petición HTTP.
- Corrección arquitectónica del bloque 23: el selector no aísla por Empresa ni
  Sucursal; el trabajo se selecciona por estado, relaciones productivas,
  responsabilidad operacional y permisos.
- Los filtros, el orden FIFO, la preparación, las especificaciones y el contrato de cada resultado se conservan sin cambios.
- La vista `resultados_proceso` queda limitada a validar parámetros, normalizar paginación, invocar la consulta y formar la respuesta HTTP.
- El contrato legado de expedientes reutiliza temporalmente el mismo selector; no mantiene una segunda implementación.
- El filtro que delimita qué salidas requieren decisión y la traducción físico-química del análisis de silo se comparten entre lectura y comandos de liberación.

### Pruebas

- Prueba específica de lectura con datos históricos organizacionales distintos:
  Empresa/Sucursal no alteran el resultado operacional autorizado.
- Prueba antirregresión N+1: la cantidad de consultas es idéntica con 1 y con 11 resultados.
- Servicio de consulta: 2/2.
- Flujo real de condensación, consulta, análisis y liberación: 1/1.
- Ruff y `manage.py check`: limpios.

### Siguiente bloque

Retirar de forma controlada el parámetro legado `incluir_procesos` del listado de expedientes, una vez verificados todos sus consumidores, y dejar un único contrato paginado para el trabajo productivo de Calidad.

## Bloque 8 — Contrato único para resultados productivos

### Implementado

El listado de expedientes vuelve a representar exclusivamente expedientes de lotes. El trabajo productivo de Calidad dispone de un único contrato especializado, paginado y filtrable.

### Backend

- `GET /api/calidad/expedientes/` dejó de interpretar `incluir_procesos` y ya no devuelve la clave `procesos`.
- `GET /api/calidad/resultados-proceso/` es la única fuente de lectura para resultados intermedios y productos a granel pendientes de decisión.
- Los comandos de liberar y rechazar conservan sus URLs, transacciones, permisos y validaciones de dominio.
- Las integraciones de Condensación y Descremado fueron migradas al contrato especializado.

### Frontend

- `RespuestaExpedientes` ya no declara resultados productivos.
- `buscarExpedientes` eliminó el parámetro `incluir_procesos` y nunca lo envía al backend.
- Centro de Calidad ya estaba desacoplado: expedientes y resultados mantienen cargas, errores y refrescos independientes.

### Pruebas

- El contrato de expedientes se prueba incluso enviando el parámetro antiguo: la respuesta no mezcla resultados productivos.
- Las pruebas de Condensación y Descremado consultan el endpoint especializado.
- No se mantienen consumidores productivos del parámetro legado en backend o frontend; la única referencia ejecutable es la prueba que verifica que se ignore sin mezclar contratos.

### Siguiente bloque

Construir el shell operacional jerárquico y contextual por área, conservando las URLs actuales y usando las bandejas especializadas ya disponibles como punto de entrada de cada puesto.

## Bloque 9 — Shell operacional contextual

### Implementado

La navegación dejó de presentar una lista plana de módulos técnicos. Cada trabajador dispone de una entrada explícita a su puesto, ve únicamente secciones permitidas y puede reconocer en todo momento su área, grupo operacional y proceso actual.

### Navegación

- Acceso destacado `Mi área` calculado desde el mismo `destinoInicial` utilizado después del inicio de sesión.
- Jerarquía visible por Recepción, Producción, Envasado y logística, Calidad y control, y Gestión.
- Producción despliega sus procesos reales: Estandarización, Descremado, Evaporación, Secado y Mantequilla.
- Los accesos de proceso se filtran además por área operacional: Secado no recibe acciones de Condensación y viceversa; Calidad y Administración conservan lectura transversal.
- La entrada del puesto no se duplica dentro del resto del menú.
- Las URLs existentes permanecen intactas, incluidas rutas con `seccion`, anclas y el alias histórico `/liberacion`.

### Contexto y accesibilidad

- Nueva franja persistente con área, grupo y ubicación actual.
- Desde una sección relacionada se puede volver a `Mi área` en una sola acción.
- El menú móvil muestra el área activa, informa `aria-expanded`, conserva cierre por fondo y aumenta la altura mínima de los enlaces táctiles.
- Navegación etiquetada, `aria-current`, foco visible e iconos decorativos fuera del árbol accesible.
- El estado activo distingue correctamente Descremado y Mantequilla aunque compartan `/procesos`.

### Arquitectura frontend

- La configuración y resolución de navegación viven en `services/navegacion-operacional.ts`, separadas del render de React.
- `Navbar` consume esa configuración y mantiene solo responsabilidades de interacción y presentación.
- `MainLayout` incorpora el contexto una sola vez para todas las páginas protegidas.

### Pruebas

- Se verifica el menú de Condensación, Secado, Calidad y Administración.
- Se comprueba filtrado de procesos, ausencia de duplicación del inicio y resolución de query strings, anclas y alias compatibles.
- Navegación operacional: 6/6.
- TypeScript y ESLint focal: limpios.
- Build de producción Vite: correcto.

### Siguiente bloque

Cerrar el balance obligatorio de Mantequilla para que toda la crema utilizada quede clasificada entre mantequilla, suero, merma o reproceso, con validaciones de dominio y una captura operacional específica.

## Bloque 10 — Balance obligatorio de Mantequilla

### Implementado

El cierre de Mantequilla dejó de aceptar diferencias sin explicar. Toda la
crema utilizada debe quedar clasificada exactamente entre mantequilla,
suero/mazada, merma y material segregado para reproceso.

### Dominio y trazabilidad

- Validación exacta del balance en backend, además de cantidades no negativas.
- El reproceso exige motivo y se registra en un lote distinto del producto
  conforme, evitando que Envasado pueda consumir accidentalmente esos kilos.
- Se crea una salida `REPROCESO`, una autorización pendiente de Calidad y un
  evento trazable de la corrida.
- La operación completa permanece atómica: un balance inválido no deja lotes,
  salidas ni autorizaciones parciales.

### Frontend

- Captura específica de mantequilla, suero/mazada, merma y reproceso.
- Balance calculado en milésimas para evitar errores binarios de punto flotante.
- El cierre solo se habilita cuando la diferencia es cero.
- Un reproceso muestra su motivo obligatorio y explica el siguiente paso de
  Calidad.

### Pruebas

- Dominio nuevo de balance y segregación: 3/3.
- Unitarios frontend acumulados: 31/31 al cerrar el bloque.
- Ruff, TypeScript, ESLint, migraciones, `manage.py check` y build Vite: limpios.

### Siguiente bloque

Hacer explícitos los handoffs entre áreas reutilizando estados, bandejas y
notificaciones existentes, sin introducir una segunda cola operacional.

## Bloque 11 — Handoffs explícitos entre áreas

### Implementado

Los estados y salidas siguen siendo la fuente de verdad de las bandejas. Sobre
esa base, cada traspaso crea ahora un aviso navegable para el puesto que quedó
habilitado, sin duplicar el estado operacional en otro modelo.

### Backend

- Las notificaciones se entregan al área principal responsable y a usuarios
  activos. Empresa y Sucursal no participan en la selección.
- Las áreas adicionales no reciben avisos accionables porque el modelo vigente
  no les concede permisos; así se evita conducir al trabajador a un `403`.
- Cada aviso nuevo incluye una URL de acción explícita.
- Cerrar Producción avisa a Calidad; liberar una salida avisa a Envasado,
  Secado, Condensación/Estandarización o Despacho según su destino y ruta.
- Registrar Envasado avisa a Calidad para la liberación final.
- El reproceso segregado de Mantequilla genera su propio aviso de decisión.
- La liberación final continúa avisando a Bodega para la reubicación física.

### Frontend

- El shell muestra `Trabajo recibido` con los avisos no leídos más recientes.
- Cada aviso conduce directamente a la bandeja responsable y se marca como
  leído al abrirlo.
- Las notificaciones históricas sin URL conservan destinos compatibles por
  tipo de aviso.

### Pruebas

- Handoffs por responsabilidad operacional y regresión de Mantequilla, Secado y Envasado:
  37/37.
- Resolución de destinos frontend: 2/2.
- Ruff, TypeScript, ESLint y `makemigrations --check`: limpios.

### Siguiente bloque

Comenzar P2 con un contrato agregado `Planta Ahora`: conteos globales exactos y
resumen operacional sin encadenar múltiples endpoints en React.

## Bloque 12 — Panel agregado Planta Ahora

### Implementado

El panel general dejó de ensamblar información parcial desde siete endpoints.
Un único modelo de lectura calcula en servidor la situación transversal de la
organización y entrega cifras completas, alertas y actividad reciente.

### Backend

- Nuevo `GET /api/procesos/planta-ahora/`, autorizado por rol o responsabilidad
  de jefatura y sin segmentación por Empresa o Sucursal.
- Conteos exactos de procesos activos, espera de Calidad, bloqueos, equipos
  ocupados, recepciones pendientes/retenidas, producto envasado pendiente y
  silos fuera de rango.
- Materiales listos conserva la regla de saldo según destino: siguiente proceso,
  Estandarización, Envasado o Despacho directo.
- Resumen por etapa y seis ejecuciones abiertas recientes sin serializar
  bandejas completas.
- El resumen local de `Mi Producción` reutiliza el mismo selector de indicadores
  y conserva el filtro por puesto.

### Frontend

- `Dashboard` consume una sola fuente y se presenta explícitamente como
  `Planta Ahora`.
- La vista prioriza procesos simultáneos, espera de Calidad, materiales listos,
  bloqueos, flujo físico y alertas con enlace al puesto responsable.
- Incluye carga inicial, actualización manual, error recuperable y estados
  vacíos, sin polling continuo.

### Pruebas

- Se cubren contrato, conteos, alertas, irrelevancia funcional de los campos
  históricos y ausencia de N+1 al aumentar las ejecuciones recientes.
- Las rutas frontend por etapa y la suma explícita del trabajo de Calidad tienen
  pruebas unitarias.

### Siguiente bloque

Continuar P2 con trazabilidad visual: timeline y genealogía cuantificada cargada
bajo demanda desde un lote, corrida o salida seleccionada.

## Decisión arquitectónica obligatoria — Empresa y Sucursal desactivadas

> “CCAA no utiliza Empresa ni Sucursal como dimensiones funcionales, de permisos, aislamiento o navegación.”

### Aplicación desde este bloque

- Los handoffs se distribuyen por área principal responsable, usuario activo y
  relación concreta `documento_tipo`/`documento_id` del trabajo recibido.
- `Planta Ahora` no recibe, consulta ni devuelve Empresa, Sucursal o alcance.
- El acceso al panel se decide por rol administrativo o responsabilidad de
  jefatura; los procesos se agrupan por etapa y estado real.
- Los campos heredados permanecen temporalmente porque varios modelos aún los
  exigen para persistir. Su presencia es compatibilidad técnica y no semántica
  funcional.
- Esta decisión prevalece para los siguientes bloques del roadmap sin cambiar
  sus prioridades, fases ni orden.

## Bloque 13 — P2/8 Trazabilidad visual cuantificada

### Implementado

La trazabilidad dejó de depender solamente de una búsqueda por lote y de
tarjetas relacionadas. Administración y los puestos con lectura transversal
pueden abrir bajo demanda una cadena desde un lote/pallet, una
corrida/ejecución o una salida de proceso.

### Backend

- El contrato existente conserva `GET /api/procesos/trazabilidad/lotes/{ref}/`
  y agrega `GET /api/procesos/trazabilidad/{tipo}/{ref}/` para referencias de
  ejecución o salida.
- Cada enlace identifica lote padre, lote hijo, ejecución, etapa, equipo,
  cantidad/unidad de entrada y cantidad/unidad/naturaleza/destino de salida.
- La respuesta incorpora foco consultado, ubicación física actual y una línea
  temporal formada por entradas, salidas, transiciones, decisiones de Calidad
  y cierres de Envasado realmente persistidos.
- La búsqueda y el recorrido no consultan ni filtran por Empresa o Sucursal.
  Las relaciones entre entradas, salidas, lotes y ejecuciones son la autoridad.
- No se agregaron modelos, estados ni migraciones: es un modelo de lectura
  construido sobre la trazabilidad existente.

### Frontend

- `Trazabilidad visual` permite elegir lote/pallet, corrida/ejecución o salida,
  y solo entonces solicita el detalle.
- La cabecera muestra la referencia, ubicación actual y tamaño de la
  genealogía; los enlaces visualizan cantidades de entrada y salida.
- La línea temporal presenta horas, responsable, equipo, estado, cantidad y
  detalle operacional sin exponer nombres de modelos ni errores técnicos.
- Se conservan búsqueda hacia atrás y hacia adelante y la URL histórica por
  lote.

### Decisiones

- Una referencia de ejecución se centra en su primer lote de salida trazable;
  si todavía no existe, usa un lote de entrada. Una salida en silo puede
  continuar hasta el lote generado por el proceso consumidor.
- No se calculan pérdidas mezclando litros y kilogramos. Las mermas declaradas
  aparecen como salidas propias en el timeline y mantienen su unidad original.
- No se inventan etapas futuras: la línea temporal contiene exclusivamente
  hechos persistidos.

### Siguiente bloque

Continuar P2 con el bloque 9: idempotencia de MRP y destinos frente a doble
envío, reintentos HTTP y carreras concurrentes.

## Bloque 14 — P2/9 Idempotencia MRP y destinos

### Implementado

- Cada petición MRP lleva una `operacion_id` estable. Repetirla devuelve la
  misma ejecución y una restricción de base impide dos ejecuciones activas para
  la misma semana.
- La ejecución se relaciona directamente con `SemanaPlan`; el JSON histórico
  queda solo como fallback de compatibilidad.
- Cálculo, reemplazo de resultados y transición a terminada ocurren bajo un
  bloqueo de fila y una sola transacción. Un fallo revierte todos los
  resultados parciales; un redelivery terminal no vuelve a calcular.
- Existe un único resultado por ejecución e insumo.
- La solicitud de compra tiene relación uno-a-uno con la ejecución MRP. Un
  reintento devuelve la solicitud ya creada sin repetir líneas.
- La definición de destino bloquea la salida, compara el destino observado por
  el cliente y registra un evento inmutable con `operacion_id`. El mismo envío
  es idempotente y una decisión obsoleta recibe conflicto en vez de sobrescribir.
- React conserva la clave mientras una petición tiene resultado incierto y
  bloquea dobles envíos durante la operación.

### Regla arquitectónica obligatoria

> “CCAA no utiliza Empresa ni Sucursal como dimensiones funcionales, de permisos, aislamiento o navegación.”

El MRP calcula sobre la semana, las necesidades, las existencias y las órdenes
reales sin filtros por Empresa/Sucursal. Sus endpoints se autorizan por rol y
permisos. Las salidas disponibles se resuelven por liberación, saldo, ruta,
etapa y compatibilidad del equipo. Los campos antiguos permanecen únicamente
para compatibilidad de persistencia y no se serializan en el contrato MRP.

### Pruebas

- Reenvío de la misma operación y rechazo de una segunda operación activa.
- Redelivery después de terminar y rollback de resultados parciales.
- Conversión repetida a solicitud de compra sin duplicados.
- Destino repetido con un solo evento y conflicto de versión obsoleta.
- Restricciones y migraciones verificadas con `makemigrations --check`.

### Siguiente bloque

Comenzar P3 con el bloque 10: optimización medida de GET auxiliares, N+1
restantes y componentes grandes, sin cambiar el orden del roadmap.

## Bloque 15 — P3/10 Optimización medida

### Implementado

- `Salidas intermedias` dejó de solicitar la bandeja operativa como GET
  auxiliar. El contrato de salidas disponibles ya entrega `ocupado_por` para
  cada equipo compatible, por lo que la carga de la vista bajó de dos GET a uno
  y dejó de mantener dos fuentes de ocupación en React.
- La bandeja `ejecuciones/operativas` precarga entradas y salidas con querysets
  que resuelven sus relaciones inmediatas mediante `select_related`. La prueba
  de rendimiento verifica tres consultas de lectura tanto para una como para
  diez ejecuciones, sin crecimiento N+1.
- La trazabilidad visual se extrajo desde `Procesos.tsx` a un componente con
  responsabilidad propia. La página principal bajó de 371 a 234 líneas y el
  nuevo componente encapsula consulta, estados y presentación de trazabilidad.
- No se agregaron modelos, migraciones ni contratos paralelos.

### Regla arquitectónica obligatoria

> “CCAA no utiliza Empresa ni Sucursal como dimensiones funcionales, de permisos, aislamiento o navegación.”

La bandeja operativa ya no aplica aislamiento por Empresa/Sucursal. La selección
de trabajo se basa en etapas operables para el usuario, roles, permisos, áreas
y relaciones productivas reales. Los campos históricos permanecen únicamente
por compatibilidad de persistencia y no participan en la nueva lógica.

### Archivos principales

- `backend/procesos/views.py`
- `backend/procesos/tests_rendimiento_operativas.py`
- `frontend/src/pages/Produccion/SalidasIntermedias.tsx`
- `frontend/src/pages/Procesos/Procesos.tsx`
- `frontend/src/pages/Procesos/TrazabilidadProceso.tsx`

### Pruebas y métricas

- Bandeja operativa: tres consultas de lectura constantes con una y diez
  ejecuciones, más regresión de exclusión de ejecuciones terminadas.
- Flujo Mantequilla y disponibilidad/ocupación de equipos: 11 pruebas de dominio.
- TypeScript y ESLint focal de los tres componentes modificados.
- Build de producción Vite completado correctamente.
- Ruff, `manage.py check` y `makemigrations --check --dry-run` sin hallazgos.
- Suite unitaria frontend existente: 38 pruebas en 12 archivos ejecutadas
  correctamente.

### Problemas y decisiones

- La primera ejecución agrupada encontró la base de pruebas persistente
  `test_ccaa`; se reutilizó de forma segura con `--keepdb`, sin eliminar datos.
- El build no pudo cargar inicialmente el binario nativo de Tailwind dentro del
  sandbox de Windows (`EPERM`); ejecutado fuera de esa restricción terminó
  correctamente. Vite conserva una advertencia no bloqueante ya existente por
  la importación estática y dinámica simultánea de `FormularioMaestro`.
- El costo inicial del permiso cacheado se calentó antes de medir el queryset;
  la aserción cubre las consultas de datos cuyo crecimiento produciría N+1.
- Se reutilizó `ocupado_por` como única fuente de verdad en lugar de agregar un
  endpoint o estado duplicado.

### Siguiente bloque

Continuar con la Fase 9 — QA operacional definida en el prompt maestro. Primero
se ejecuta la matriz integrada backend y luego los recorridos Playwright por
puestos, sin inventar ni reordenar fases.

## Bloque 16 — Fase 9/QA operacional: matriz integrada backend

### Implementado

- Se inventariaron los seis escenarios obligatorios de QA: polvo,
  mantequilla, precondensado, bloqueo de Calidad, concurrencia y permisos.
- Se ejecutó una matriz integrada de 84 pruebas sobre Producción, Procesos,
  Calidad e Inventario usando la base de pruebas aislada.
- Se corrigió el fixture de `FlujoIntegradoApiTests`: ahora declara de forma
  explícita el proceso, las etapas de Estandarización/Secado y la ruta del
  producto que el dominio exige antes de abrir un lote.
- No se relajaron validaciones, no se cambió código productivo y no se agregaron
  modelos, endpoints ni migraciones.
- Playwright reconoce 13 recorridos visuales en ocho archivos para la siguiente
  parte de la fase.

### Regla arquitectónica obligatoria

> “CCAA no utiliza Empresa ni Sucursal como dimensiones funcionales, de permisos, aislamiento o navegación.”

Los campos históricos obligatorios solo se completan en fixtures para satisfacer
el esquema legado. Los criterios verificados son producto, ruta, etapas,
responsabilidades, permisos, estados, lotes, salidas, Calidad y equipos.

### Archivos principales

- `backend/produccion/tests_flujo_integrado.py`
- `docs/architecture/06-improvement-plan.md`
- `docs/architecture/07-implementation-log.md`

### Pruebas ejecutadas

- Matriz integrada backend: 84/84 correctas.
- Regresión focal del flujo integrado: 7/7 correctas.
- Inventario Playwright: 13 pruebas detectadas en ocho archivos.
- Ruff, `manage.py check` y `makemigrations --check --dry-run`: correctos.

### Problemas encontrados

- La primera corrida produjo un fallo y ocho errores encadenados porque el
  fixture integrado no creaba una ruta productiva. Sin ruta, la lista de
  equipos quedaba vacía; el primer subtest no alcanzaba a limpiar su ejecución
  y los siguientes chocaban con la restricción de equipo ocupado.
- La incompatibilidad estaba en el escenario de prueba. El backend rechazaba
  correctamente abrir un lote sin ruta, por lo que se completó el fixture en
  vez de debilitar la regla de dominio.

### Decisiones tomadas

- La ruta del fixture se declara mediante relaciones productivas explícitas.
- `Sucursal` se informa únicamente porque sigue siendo un campo histórico
  obligatorio del modelo; no se usa como expectativa funcional, permiso ni
  aislamiento de la prueba.
- Los circuitos Playwright escriben datos operacionales y se mantienen como un
  bloque separado, ejecutable sobre el entorno E2E preparado para ese fin.

### Siguiente bloque

Continuar Fase 9 con los recorridos Playwright por pantalla: polvo,
precondensado, descremado/mantequilla y suero; después validar visualmente las
compuertas de Calidad, conflictos de equipo y permisos desde cada puesto.

## Bloque 17 — Fase 9/QA operacional: recorrido visual de polvo

### Implementado

- Se validó por pantalla la ruta de leche en polvo desde la apertura del lote
  y Evaporación hasta el pallet disponible en Inventario: análisis y doble
  firma, liberación de precondensado, continuación a Secado, balance de secado,
  liberación del polvo, envasado, expediente y entrega a Bodega.
- El código manual del lote ya no puede ser sobrescrito por una sugerencia que
  termine después de que el operador escribió. La preferencia manual se
  comprueba de nuevo cuando responde la petición asíncrona.
- La captura de análisis espera a resolver el borrador inicial antes de
  habilitar campos. Así su propio autoguardado no puede reaparecer como un
  supuesto borrador anterior y bloquear la confirmación.
- El circuito dispone de una segunda identidad de Calidad para el control de
  cuatro ojos. `e2e_calidad` opera la pantalla y `e2e_calidad_firma` visualiza;
  ambas se autorizan por rol y área, sin otorgar administración técnica.
- La guía E2E usa el preparador real `crear_usuarios_flujo_e2e` y el recorrido
  de polvo fija explícitamente su producto para no tomar un vale de otra ruta.

### Regla arquitectónica obligatoria

> “CCAA no utiliza Empresa ni Sucursal como dimensiones funcionales, de permisos, aislamiento o navegación.”

La separación de responsabilidades del escenario se basa en usuarios
distintos, rol Calidad, área operacional y relaciones reales entre vale, lote,
ejecución, equipo, salida y etapa. Los campos históricos que el esquema aún
exige al preparar cuentas permanecen solo por compatibilidad de persistencia y
no deciden la autorización ni el resultado del QA.

### Archivos principales

- `frontend/src/pages/Produccion/FormularioLote.tsx`
- `frontend/src/pages/Leche/AnalisisSilo.tsx`
- `frontend/e2e/ayudantes.ts`
- `frontend/e2e/README.md`
- `backend/usuarios/management/commands/crear_usuarios_flujo_e2e.py`
- `backend/usuarios/tests_comando_flujo_e2e.py`

### Pruebas ejecutadas

- Recepción → Estandarización visual: 2/2 correctas durante la preparación del
  escenario.
- Evaporación de polvo: 2/2 correctas.
- Precondensado → Secado → Envasado → Inventario: 1/1 correcta.
- Cuentas E2E por área y segunda persona de Calidad: 2/2 correctas.
- Suite unitaria frontend: 38/38 correctas.
- TypeScript, ESLint focal, `manage.py check` y
  `makemigrations --check --dry-run`: correctos.

### Problemas encontrados

- La base local no tenía aplicadas cuatro migraciones ya existentes; faltaba
  `inventario_notificacion.accion_url`. Se aplicaron antes de repetir el flujo.
- Una respuesta tardía de código sugerido sobrescribía el código manual del
  lote y hacía que Evaporación no encontrara la referencia esperada.
- La consulta inicial de borradores de análisis competía con el autoguardado y
  podía bloquear su propio formulario.
- Reutilizar `e2e_calidad` como segunda firma chocaba con la regla de una sesión
  activa por usuario y no representaba dos personas reales.
- Una ejecución sin producto objetivo tomó válidamente un vale de
  Precondensado; el QA de polvo ahora selecciona explícitamente leche en polvo.
- El runner unitario de Node no pudo crear subprocesos dentro del sandbox de
  Windows (`EPERM`); fuera de esa restricción completó 38/38.

### Decisiones tomadas

- Se corrigieron las carreras en la interfaz, sin relajar el dominio ni agregar
  endpoints.
- Los intentos E2E incompletos creados por estas fallas se anularon de forma
  auditable y sus ejecuciones se cancelaron para liberar los equipos; no se
  borró historial productivo.
- La segunda firma es otra persona de Calidad y no un administrador. La
  compatibilidad histórica de Empresa/Sucursal no participa en su permiso.

### Siguiente bloque

Continuar Fase 9 con los recorridos visuales de precondensado directo,
descremado/mantequilla y suero. Después ejecutar las compuertas transversales de
bloqueo de Calidad, concurrencia de equipos y permisos por puesto.

## Bloque 18 — Fase 9/QA operacional: precondensado a despacho directo

### Implementado

- Se validó por pantalla la ruta completa de Precondensado Entero NE Granel:
  recepción, estandarización, apertura del lote, evaporación, análisis con
  doble firma, liberación de Calidad, preparación del despacho, autorización y
  confirmación de la salida física.
- El producto conserva su ruta específica: una vez liberado desde el silo se
  ofrece `Preparar despacho`; no se deriva a Secado ni se crea un pallet o una
  existencia de producto terminado.
- El coordinador común de borradores ahora serializa correctamente a todos los
  solicitantes que esperan una escritura en curso. `guardarAhora` vuelve a
  comparar la huella después de esperar, y no permite confirmar mientras otro
  guardado con los últimos campos recién comienza.

### Regla arquitectónica obligatoria

> “CCAA no utiliza Empresa ni Sucursal como dimensiones funcionales, de permisos, aislamiento o navegación.”

El recorrido decide su trabajo mediante producto, vale liberado, orden,
ejecución, equipo, salida, especificación de Calidad, cliente y estado del
despacho. La autorización se verificó con usuarios, roles, áreas y permisos
operacionales; Empresa/Sucursal no forman parte de los criterios del flujo.

### Archivos principales

- `frontend/src/hooks/useBorrador.ts`
- `frontend/e2e/flujo-precondensado-despacho.spec.ts`
- `backend/produccion/management/commands/preparar_circuito_precondensado.py`
- `docs/architecture/06-improvement-plan.md`
- `docs/architecture/07-implementation-log.md`

### Pruebas ejecutadas

- Recepción → Estandarización de Precondensado: 2/2 correctas.
- Apertura de lote y Evaporación: 2/2 correctas.
- Calidad → despacho directo desde silo: 2/2 correctas.
- Regresión backend de Condensación y producto terminado/despacho: 20/20.
- Suite unitaria frontend: 38/38 correctas.
- TypeScript, ESLint focal, `manage.py check` y
  `makemigrations --check --dry-run`: correctos.

### Problemas encontrados

- La primera preparación se detuvo antes de escribir datos porque una sesión
  Playwright de `e2e_auditoria` permanecía activa después de restaurar el
  archivo local de autenticación. Se cerró únicamente esa sesión E2E mediante
  el servicio de sesiones existente.
- En el primer intento de Evaporación, Calidad confirmó mientras el último
  autoguardado todavía no persistía `inhibidores_resultado`; el backend lo
  rechazó correctamente con 400.
- La causa era una carrera en `useBorrador`: dos consumidores podían esperar la
  misma petición y uno continuar antes del guardado final iniciado por el otro.

### Decisiones tomadas

- Se corrigió el coordinador común de borradores en lugar de añadir esperas
  artificiales al test o debilitar la obligatoriedad de inhibidores.
- El lote E2E incompleto se anuló con motivo y su ejecución se canceló para
  liberar el evaporador; se preservó el historial.
- La prueba utiliza un archivo de traspaso propio y fija explícitamente
  `Precondensado Entero NE Granel`, evitando contaminar el circuito de polvo.

### Siguiente bloque

Continuar Fase 9 con el recorrido visual de descremado y sus dos salidas reales,
encadenando la crema hacia Mantequilla y la leche descremada hacia su destino.
Luego validar Mantequilla hasta Inventario.

## Bloque 19 — Fase 9/QA operacional: Descremado y Mantequilla

### Implementado

- Se validó por pantalla la separación de leche entera en dos salidas físicas:
  leche descremada y crema, cada una con análisis firmado, liberación de Calidad
  y continuidad independiente.
- La leche descremada conserva su acción hacia Estandarización. La crema
  conserva tanto la ruta a Mantequilla como la alternativa explícita de
  despacho directo, que se verificó hasta la salida física autorizada.
- Se restauró en el alta de Mantequilla la selección opcional del lote de
  suero/mazada que el backend ya soportaba. El cierre vuelve a clasificar el
  coproducto real como mazada trazable, separado de merma y reproceso.
- Se validó Mantequilla desde 60 kg de crema hasta 31 kg de mantequilla, 28 kg
  de mazada y 1 kg de merma; luego análisis, liberación, una caja completa de
  20 kg, segregación de 11 kg de remanente, expediente, liberación comercial y
  entrega del pallet a Bodega.
- Calidad bloquea temporalmente las demás decisiones mientras una liberación o
  rechazo está recargando la bandeja. Ya no muestra un botón accionable cuyo
  clic pueda descartarse silenciosamente por otra decisión en curso.
- El E2E de silos admite varias capas históricas liberadas en un mismo TK y
  verifica una acción contractual visible sin asumir una única salida.

### Regla arquitectónica obligatoria

> “CCAA no utiliza Empresa ni Sucursal como dimensiones funcionales, de permisos, aislamiento o navegación.”

Los recorridos se resolvieron mediante usuarios, roles, áreas operacionales,
permisos, productos, lotes, análisis, salidas, equipos, estados y rutas reales.
Los campos históricos obligatorios no forman parte de las aserciones ni de las
decisiones incorporadas en este bloque.

### Archivos principales

- `frontend/src/pages/Calidad/CentroCalidad.tsx`
- `frontend/src/pages/Calidad/ResultadoProcesoCalidadCard.tsx`
- `frontend/src/pages/Procesos/NuevaMantequilla.tsx`
- `frontend/e2e/flujo-descremado.spec.ts`
- `frontend/e2e/flujo-mantequilla.spec.ts`
- `docs/architecture/06-improvement-plan.md`
- `docs/architecture/07-implementation-log.md`

### Pruebas ejecutadas

- Descremado visual completo: 4/4 correctas, incluida la sesión de auditoría.
- Mantequilla, análisis y liberación de la salida: 2/2 correctas.
- Envasado y comprobación del pallet en cuarentena: 2/2 correctas.
- Disposición del excedente y entrega a Bodega: 2/2 correctas.
- Regresión backend de Descremado y Mantequilla: 26/26 correctas.
- Suite unitaria frontend: 38/38 correctas.
- TypeScript, ESLint focal, `manage.py check` y
  `makemigrations --check --dry-run`: correctos.

### Problemas encontrados

- La primera liberación dejaba brevemente habilitado el botón de otra salida,
  aunque la operación global seguía recargando; el segundo clic se descartaba
  sin enviar petición.
- Una corrida E2E fallida dejó `TkC2` bloqueado por una crema pendiente y otro
  reintento dejó una corrida en borrador. Se completó la decisión pendiente y
  se canceló el reintento con motivo, sin borrar historia.
- Los TK de prueba ya contenían varias capas liberadas, por lo que una aserción
  que esperaba un único enlace fallaba aunque todas las acciones fueran válidas.
- La división previa del formulario de Mantequilla había omitido el selector de
  lote de mazada; el backend seguía ofreciendo y validando ese contrato.
- Dos intentos interrumpidos de Mantequilla se cancelaron mediante la transición
  auditable de la ejecución para liberar el equipo. Sus datos permanecen como
  historial E2E y no fueron eliminados.

### Decisiones tomadas

- Se corrigió la exclusión mutua visible de las decisiones de Calidad, en lugar
  de añadir una espera artificial o permitir doble decisión concurrente.
- Se restauró la asociación de mazada ya existente. No se clasificó un
  coproducto normal como reproceso y no se creó un modelo ni endpoint nuevo.
- Las pruebas seleccionan la capa pertinente por código de lote/corrida y solo
  relajan la unicidad del enlace cuando el mismo TK contiene historia legítima.

### Siguiente bloque

Continuar Fase 9 con el recorrido visual de suero. Después ejecutar las
compuertas transversales de bloqueo de Calidad, concurrencia de equipos y
permisos por puesto, sin alterar el orden del roadmap.

## Bloque 20 — Fase 9/QA operacional: Suero en Big Bag

### Implementado

- Se validó por pantalla la ruta específica de suero recibido externamente:
  materia prima liberada, Secado, decisión intermedia de Calidad, envasado en
  Big Bag, expediente final, entrega a Bodega e Inventario disponible.
- Secado consumió 800 kg de un lote externo de 1.000 kg y registró 700 kg de
  polvo, 10 kg de finos y 5 kg de merma, conservando el balance operacional y
  el remanente de la materia prima.
- Calidad comprobó la humedad contra la especificación E2E, liberó la salida
  para Envasado y volvió a decidir el producto terminado después de completar
  su documentación.
- Envasado creó una unidad logística Big Bag de 700 kg. Inventario confirmó su
  código, lote, tipo de envase, peso y estado disponible.
- No fue necesario modificar código productivo, contratos API, modelos ni
  migraciones para cerrar este recorrido.

### Regla arquitectónica obligatoria

> “CCAA no utiliza Empresa ni Sucursal como dimensiones funcionales, de permisos, aislamiento o navegación.”

Este bloque no incorporó filtros, permisos, navegación, notificaciones ni
contratos nuevos basados en Empresa/Sucursal. Sus criterios de aceptación son
usuario, área, rol, permisos, lote de materia prima, orden, corrida, equipo,
salida, análisis, expediente y unidad logística reales.

### Archivos principales

- `frontend/e2e/flujo-suero.spec.ts`
- `backend/produccion/management/commands/preparar_circuito_suero.py`
- `backend/procesos/tests_flujo_suero.py`
- `docs/architecture/06-improvement-plan.md`
- `docs/architecture/07-implementation-log.md`

### Pruebas ejecutadas

- Recorrido visual Suero → Big Bag → Inventario: 2/2 correctas, incluida la
  preparación de la sesión de auditoría.
- Regresión backend integral de suero: 1/1 correcta.
- Suite unitaria frontend: 38/38 correctas.
- TypeScript, ESLint focal, `manage.py check` y
  `makemigrations --check --dry-run`: correctos.

### Problemas encontrados

- El primer inicio de Playwright recibió HTTP 429 antes de abrir una pantalla:
  `e2e_auditoria` había alcanzado 15/15 intentos por las corridas consecutivas
  de QA. La dirección seguía bajo su límite y las demás cuentas estaban libres.
- Se desbloqueó únicamente la llave de esa cuenta E2E con el comando de
  seguridad existente; no se desactivó ni amplió el límite global.
- El expediente del producto E2E hereda varios documentos aplicables a la
  familia polvo. El circuito los completó por la interfaz y no omitió la
  compuerta documental.

### Decisiones tomadas

- Se mantuvo el flujo de suero separado de leche en polvo y mantequilla: usa
  alimentación externa, torre propia y formato Big Bag.
- Los rangos, equipos y productos con sufijo E2E continúan identificados como
  datos simulados; no se promovieron a parámetros oficiales de planta.
- No se relajaron Calidad, balance, consumo de inventario ni documentación para
  acelerar la prueba.

### Siguiente bloque

Continuar Fase 9 con las compuertas transversales, comenzando por bloqueo y
liberación de Calidad; luego exclusión concurrente de equipos y permisos por
puesto. En la validación de permisos se comprobará expresamente que el criterio
operacional sea área/responsabilidad y no Empresa/Sucursal.

## Bloque 21 — Fase 9/QA operacional: bloqueo y liberación de Calidad

### Implementado

- La bandeja de Envasado distingue ahora el material habilitado del trabajo que
  ya llegó al puesto pero sigue esperando una decisión intermedia de Calidad.
- Cada espera muestra lote, producto, cantidad, origen productivo, estado y el
  motivo operacional que impide envasar. Una salida histórica de una ejecución
  cerrada no se presenta como tarea vigente.
- El backend continúa siendo la autoridad: un POST manual de Envasado sobre un
  lote pendiente es rechazado y no crea registros ni unidades logísticas.
- La frontera REST traduce los bloqueos del servicio de dominio a HTTP 400 con
  su mensaje, en vez de convertir una validación esperada en error interno.
- Al liberar Calidad, el lote desaparece de `bloqueados_calidad` y pasa a
  `materiales`, sin duplicar la regla de autorización en React.
- El recorrido visual de polvo incorpora la comprobación explícita de la espera
  en Envasado antes de la decisión de Calidad.

### Regla arquitectónica obligatoria

> “CCAA no utiliza Empresa ni Sucursal como dimensiones funcionales, de permisos, aislamiento o navegación.”

La nueva lectura de espera se construye exclusivamente desde la relación real
`salida → ejecución → etapa → lote`, sus estados y la decisión de Calidad. No
agrega filtros, permisos, navegación, notificaciones ni contratos basados en
Empresa/Sucursal. Los campos antiguos continúan solo como compatibilidad del
modelo persistido.

### Archivos principales

- `backend/produccion/views.py`
- `backend/produccion/serializers.py`
- `backend/produccion/tests_envase.py`
- `frontend/src/pages/Envasado/Envasado.tsx`
- `frontend/src/services/produccion.service.ts`
- `frontend/e2e/flujo-polvo-continuacion.spec.ts`
- `docs/architecture/06-improvement-plan.md`
- `docs/architecture/07-implementation-log.md`

### Pruebas ejecutadas

- Calidad, Envasado, Secado y Mantequilla: 101/101 pruebas backend correctas.
- Unitarios frontend: 38/38 correctos.
- TypeScript, ESLint focal, compilación Vite, `manage.py check` y
  `makemigrations --check --dry-run`: correctos.
- La comprobación visual nueva alcanzó y verificó la tarjeta de espera de
  Calidad. La corrida integral desde Recepción no pudo regenerarse porque los
  tres TK de leche descremada del entorno E2E conservan saldos históricos y
  ninguno admite otros 8.000 L; no se vaciaron ni borraron datos para forzarla.

### Problemas encontrados

- La UI anterior omitía por completo el material pendiente: el backend lo
  bloqueaba, pero Envase no podía ver la causa.
- Una validación de dominio esperada escapaba del serializer como excepción de
  Django y producía error interno en el endpoint manual.
- La primera lectura de espera incluía tres salidas históricas de ejecuciones
  cerradas. El intento E2E lo detectó y el contrato quedó restringido a
  ejecuciones `pendiente_control` o `bloqueada`.
- El entorno acumulado no dispone hoy de un TK de leche descremada con 8.000 L
  libres. Se conservó esa evidencia productiva en vez de ejecutar limpieza
  destructiva.

### Decisiones tomadas

- Mostrar espera no equivale a habilitar operación: `materiales` sigue
  conteniendo únicamente salidas liberadas y el servicio revalida el POST.
- Se reutilizó el motivo del servicio de dominio y la decisión persistida; no
  se creó una segunda interpretación de Calidad en el frontend.
- El trabajo vigente se delimita por estado del proceso y relaciones reales,
  nunca por Empresa/Sucursal.

### Siguiente bloque

Continuar Fase 9 con exclusión concurrente de equipos. Después quedará el
último bloque: permisos por puesto y verificación expresa de aislamiento por
áreas/responsabilidades sin Empresa/Sucursal.

## Bloque 22 — Fase 9/QA operacional: concurrencia de equipos

### Implementado

- Se agregó la prueba concurrente exacta de dos usuarios que intentan reservar
  simultáneamente la misma torre mediante el endpoint de transición.
- La prueba demuestra que el bloqueo de fila del equipo serializa la carrera:
  una sola ejecución pasa a preparación y la segunda recibe HTTP 400 sin
  alterar su estado.
- La restricción condicional de base de datos sigue actuando como segunda
  barrera: al terminar la carrera existe exactamente una ocupación física para
  el equipo.
- El rechazo identifica la máquina y el código de la ejecución que obtuvo la
  reserva. El frontend conserva ese texto, lo muestra al operador y refresca la
  disponibilidad al reconocer un conflicto de equipo.
- No fue necesario cambiar el servicio productivo, la máquina de estados, el
  endpoint ni la pantalla; la protección existente era correcta y faltaba la
  demostración concurrente integrada.

### Regla arquitectónica obligatoria

> “CCAA no utiliza Empresa ni Sucursal como dimensiones funcionales, de permisos, aislamiento o navegación.”

La exclusión se decide por la identidad física del equipo, los estados que lo
ocupan, la ejecución y el usuario responsable. La prueba nueva no utiliza
Empresa/Sucursal para seleccionar, autorizar ni aislar la operación; los valores
que el esquema histórico complete por compatibilidad no participan en la
decisión concurrente.

### Archivos principales

- `backend/procesos/servicios.py`
- `backend/procesos/models.py`
- `backend/procesos/views.py`
- `backend/procesos/tests_concurrencia_equipo.py`
- `frontend/src/pages/Procesos/Procesos.tsx`
- `frontend/src/services/errores-proceso.ts`
- `frontend/tests/errores-proceso.test.ts`
- `docs/architecture/06-improvement-plan.md`
- `docs/architecture/07-implementation-log.md`

### Pruebas ejecutadas

- Carrera concurrente sobre una misma torre: 1/1 correcta.
- Procesos, concurrencia de versión y reserva concurrente de TK: 56/56
  correctas.
- Unitarios frontend acumulados: 39/39 correctos.
- TypeScript y ESLint focal: correctos.

### Problemas encontrados

- Existían pruebas secuenciales del equipo ocupado, de restricción en base de
  datos y de concurrencia sobre TK, pero no una carrera real de dos solicitudes
  HTTP sobre la misma máquina.
- La primera orden de regresión contenía un nombre de módulo con mayúscula y
  produjo un error de descubrimiento, no del sistema. Se corrigió el comando y
  las 56 pruebas reales pasaron.

### Decisiones tomadas

- Se mantuvo el doble resguardo actual: `select_for_update` ofrece el mensaje
  operacional y la restricción única protege la integridad aun ante una ruta de
  escritura defectuosa.
- La reserva comienza en `preparacion`, porque desde ese momento la máquina ya
  no está físicamente disponible para otra corrida.
- No se añadió un estado ni una tabla de ocupación paralela: la ejecución y su
  estado siguen siendo la fuente de verdad.

### Siguiente bloque

Cerrar Fase 9 con permisos por puesto: frontend bloquea navegación/acciones y
backend responde 403 ante acceso manual. La revisión verificará expresamente
que el alcance funcional se base en área, rol, permiso y responsabilidad real,
sin Empresa/Sucursal.

## Bloque 23 — Fase 9/QA operacional: permisos por puesto

### Implementado

- La autorización compartida del backend quedó basada en autenticación, área,
  rol, nivel y permisos explícitos. Tener o no Empresa/Sucursal ya no concede,
  niega ni recorta acceso.
- El adaptador histórico `filtrar_por_scope` dejó de particionar querysets y
  relaciones. Sus nombres se conservan para no romper imports antiguos, pero
  solo actúan como compatibilidad de persistencia.
- La administración de trabajadores filtra por responsabilidad de área, no por
  Empresa/Sucursal.
- Una persona de Recepción que abre directamente Administración recibe una
  pantalla explícita de acceso restringido; una llamada manual al endpoint de
  trabajadores recibe HTTP 403.
- El contrato de sesión ya no expone `empresa` ni `sucursal`, y el alta de
  trabajadores no acepta esas dimensiones funcionales desde la API.
- Las notificaciones de Recepción, Calidad, Bodega y Compras usan el área
  principal, las áreas adicionales y la relación real del trabajo recibido;
  no filtran destinatarios por Empresa/Sucursal.
- Las claves foráneas históricas aún obligatorias se completan internamente y
  de forma determinista, sin derivar autorización del perfil ni pedir una
  selección funcional al cliente.

### Regla arquitectónica obligatoria

> “CCAA no utiliza Empresa ni Sucursal como dimensiones funcionales, de permisos, aislamiento o navegación.”

Los campos y modelos heredados pueden seguir almacenados para compatibilidad,
pero no participan en permisos, navegación, bandejas, notificaciones ni nuevos
contratos funcionales.

### Archivos principales

- `backend/usuarios/permisos.py`
- `backend/usuarios/tenancy.py`
- `backend/usuarios/areas.py`
- `backend/usuarios/serializers.py`
- `backend/usuarios/views.py`
- `backend/recepcion/views.py`
- `backend/inventario/servicios.py`
- `frontend/src/components/RutaAdmin/RutaAdmin.tsx`
- `frontend/src/services/sesion.ts`
- `frontend/tests/navegacion-operacional.test.ts`

### Pruebas ejecutadas

- Matriz focal de permisos, áreas, administración, compatibilidad histórica,
  notificaciones y procesos: 57/57 correctas.
- Unitarios frontend acumulados: 40/40 correctos.
- Compilación TypeScript/Vite, Ruff focal, ESLint focal, `manage.py check` y
  `makemigrations --check --dry-run`: correctos.

### Problemas encontrados

- Los permisos de lectura y administración aún exigían un scope histórico aun
  cuando el área/rol ya autorizaban la operación.
- La ruta de Administración redirigía a Recepción hacia un Dashboard también
  no autorizado, en vez de explicar el bloqueo.
- Las notificaciones de Inventario omitían áreas adicionales y Recepción las
  recortaba por Empresa.
- Algunas pruebas auxiliares de configuración tenant sembrada y barrido de
  contratos conservan supuestos históricos; quedan identificadas como deuda de
  pruebas fuera de este bloque.
- ESLint global conserva tres hallazgos anteriores en Estandarización; los
  archivos modificados en este bloque pasan el análisis focal.

### Decisiones tomadas

- Se conservaron modelos y claves históricas para evitar una migración
  destructiva, pero se neutralizó su efecto en autorización y selección.
- Las áreas adicionales cuentan para entrega de trabajo y avisos, pero los
  permisos de escritura siguen dependiendo del puesto/área principal y de los
  permisos explícitos.
- El backend sigue siendo la autoridad aunque React oculte o bloquee la ruta.

### Siguiente bloque

No hay siguiente bloque: Fase 9/9 y el roadmap aprobado quedan cerrados.

## Estabilización integral posterior al roadmap — 2026-09-14

Se completó la campaña solicitada de reset seguro, estado QA reproducible,
corrección de errores de Calidad/transiciones y recorridos integrales desde
datos operacionales vacíos. El resultado detallado, inventario de endpoints,
bugs, matriz de equipo, E2E y comandos reproducibles está en
`docs/architecture/08-stabilization-report.md`.

La campaña no crea una fase ni altera el roadmap cerrado. Su siguiente paso es
operación/QA continua sobre la base estabilizada.

> “CCAA no utiliza Empresa ni Sucursal como dimensiones funcionales, de
> permisos, aislamiento o navegación.”

## Cierre residual posterior a estabilización — 2026-09-14

### Implementado

- Se eliminaron filtros directos por Empresa/Sucursal que aún intervenían en
  el contraste semanal, los maestros de planificación y el stock de seguridad.
- La selección de rutas y etapas productivas quedó basada en producto,
  proceso, prioridad y estado activo; la sucursal histórica ya no dirige la
  navegación.
- Calidad evalúa todos los documentos aplicables por familia/evidencia, sin
  aislar el expediente por la empresa histórica del lote.
- Inventario calcula alertas con el saldo operacional completo del insumo y
  Envasado calcula materiales disponibles desde las existencias físicas
  reales, sin agrupar por sucursal.
- Recepción dejó de impedir la relación con un vehículo por diferencias entre
  claves históricas.
- Se añadieron regresiones específicas para planificación, rutas, Calidad e
  Inventario.

### Archivos principales

- `backend/planificacion/views.py`
- `backend/procesos/servicios.py`
- `backend/calidad/views.py`
- `backend/inventario/servicios.py`
- `backend/produccion/views.py`
- `backend/recepcion/serializers.py`
- `backend/planificacion/tests_contraste.py`
- `backend/procesos/tests_rutas.py`
- `backend/inventario/tests_tenancy.py`
- `backend/produccion/tests_tenancy.py`
- `docs/architecture/08-stabilization-report.md`

### Pruebas ejecutadas

- Regresiones dirigidas: 35/35 correctas.
- Suite integral backend: 1.417 correctas, 5 omitidas, 0 fallos.
- Ruff focal, `manage.py check` y `makemigrations --check --dry-run`: correctos.

### Problemas encontrados

- El adaptador de tenancy ya era un no-op, pero había consultas directas que lo
  evitaban y todavía recortaban resultados por claves históricas.
- Dos selectores auxiliares de rutas seguían usando sucursal aunque el listado
  inicial ya había sido corregido.

### Decisiones tomadas

- Se conservaron campos, firmas y relaciones obligatorias únicamente como
  compatibilidad de persistencia; eliminarlos ahora implicaría una migración
  destructiva sin beneficio funcional.
- Las ubicaciones físicas, productos, etapas, fechas, áreas, permisos y
  relaciones de trabajo son las fuentes funcionales de verdad.

### Siguiente bloque

No hay un bloque pendiente del roadmap: Fase 9/9 continúa cerrada. El siguiente
paso es QA/operación continua y corrección de incidencias reales si aparecen.

> “CCAA no utiliza Empresa ni Sucursal como dimensiones funcionales, de
> permisos, aislamiento o navegación.”
