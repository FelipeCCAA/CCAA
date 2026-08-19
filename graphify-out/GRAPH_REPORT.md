# Graph Report - CCAA  (2026-08-17)

## Corpus Check
- cluster-only mode — file stats not available

## Summary
- 3002 nodes · 6315 edges · 278 communities (157 shown, 121 thin omitted)
- Extraction: 90% EXTRACTED · 10% INFERRED · 0% AMBIGUOUS · INFERRED: 642 edges (avg confidence: 0.53)
- Token cost: 163,981 input · 4,080 output

## Graph Freshness
- Built from commit: `9071583a`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- Master Data Models
- Product SKU Model
- Equipment and Silo Masters
- Production Batch Admin
- Stock and Orders UI
- Production Screen
- Inventory API Views
- Milk Reception UI
- Maintenance Work Orders
- Inventory Domain Models
- Shared UI Components
- Product Specifications
- Production Planning UI
- Master Data Forms UI
- Food Safety PPRO Admin
- Milk Quality Screens
- Batch Detail Screen
- Route Management UI
- Milk Collection Routes
- Reception Flow Service
- Navigation and Route Guards
- Release Document Catalog
- Maintenance and Process UI
- Role Permissions
- Planning Models
- Batch Serializers
- Frontend App Routing
- Reception Domain Rules
- Standardization Voucher Model
- Planning Serializers
- Client and Recipe Masters
- Batch API Viewset
- Audit Actor Context
- Purchasing Screen
- Release Signature Serializers
- Milk Assignment Panel
- Planning Views
- User Profile Areas
- Environment Hardening Settings
- Equipment Record Serializers
- User Admin Panel
- Reception Serializers
- Standardization Screen
- Tenant Backfill Migrations
- Production Plan Blocks
- Batch Opening Services
- Master Data Admin
- Standardization Services
- Release Dossier UI
- MRP Screen
- Weekly Milk Balance Rules
- Reception Purchase Screen
- Process Execution Admin
- Tenant Scope Filtering
- Login Attempts and Recovery
- Standardization App
- Recipe Explosion
- CIP Cycle Model
- Procurement Panel
- File Attachment Validation
- Quality Release Rules
- Inventory Movement Services
- Health Check Endpoints
- Standardization Voucher Form
- Suppliers Screen
- Milk Balance Table
- Contrast Delta Component
- Quality Record Views
- Dynamic Form Renderer
- Quality Serializers
- Specification Form UI
- Product Serializer & SKU
- Frontend TS Config
- User Profile Startup Checks
- Silo Occupancy View
- Project Instructions Doc
- Audit Trail Model
- Material Nonconformity Closure
- Daily Milk Balance
- Graph Email Backend
- Equipment Form UI
- Measurable Parameter Catalog
- Generic Master Form
- Food Safety Panel
- Cache Table Migration
- Equipment Records UI
- Node TS Config
- Row-Lock Engine Check
- Quality Release Admin
- Equipment Record Tenant
- Mandatory Execution Scope
- Standardization Endpoints
- Production Domain Rules
- Prototype Design Docs
- Technical Audit Findings
- Exceptional Material Release
- Plant Survey Docs
- Frontend Dependencies
- MRP and Supplies
- Plan vs Actual Contrast
- Deployment and Decisions
- Lint Dev Dependencies
- Planning Admin
- Product Load Command
- Worker Management API
- Redesign Proposal Docs
- Audit Trail UI
- SKU Encoder
- Plant Rules Reference
- Read-Only Inventory Admin
- Prototype Data Storage
- Equipment & Food Safety Models
- RC Standardization Math
- Supply Stock Serializer
- Dossier Template Seeding
- Product SKU & Lot Coding
- Concurrency Lock and MRP
- Specification Versioning API
- CIP Cleaning Screen
- Release Dossier Seeding
- Per-Evaporator Checklist Split
- Pre-Operative Inspection Template
- Unique Client Code Merge
- Token Auth With Tenant
- Email Delivery Check Command
- Transactional Data Cleanup Command
- Unified Audit Change Format
- Checklist Progress Calculation
- PPRO Equipment To Master
- CIP Equipment To Master
- Inventory Purchasing Tenant Fields
- Dossier Evidence Marking
- Tower & Packer Equipment Seed
- Evidence By Equipment Code
- Masters Tenant Migration
- Process Control Equipment Reference
- Administration Company Scope
- Frontend Package Manifest
- Frontend Build Scripts
- Celery Project Setup
- Standardization Voucher Admin
- Equipment Master Seeding
- Checklist Frequency Migration
- Material Consumption Seeding
- Plan Block Equipment FK
- Reception Admin
- Process Role Migration
- Standardization App Config
- Food Safety App Config
- Inventory App Config
- Masters App Config
- Django Management Entrypoint
- Maintenance App Config
- Planning App Config
- Processes App Config
- Dairy Flow Seeding
- Production App Config
- Reception App Config
- Arrival ID Per Reception
- Collection App Config
- Staff Admin Sync
- TypeScript Solution Config
- Audit Initial Migration
- Audit Tenant Migration
- Quality Initial Migration
- Equipment Record Model
- ASGI Server Config
- Gunicorn Server Config
- WSGI Server Config
- Standardization Initial Migration
- Food Safety Initial Migration
- Inventory Initial Migration
- Warehouse Supplier Schema
- Inventory Area Alterations
- Warehouse Branch Approval
- Attachments Alerts Exceptions
- Supply Shelf Life
- Adjustments & Production Returns
- Inventory Movement Types
- Production Lot Consumption
- Inventory Area Realignment
- Product Consumption Removal
- Supply Stock Field Removal
- MRP Execution Ordering
- Single Principal Supplier
- Inventory Branch Merge
- Traceable Nonconformity Closure
- Movements Under Concession
- MRP Execution State
- CIP Cleaning Migration
- Masters Initial Migration
- Vehicle & Silo Models
- Release Document Model
- Release Document Area
- Recipe & Components
- Client Code & Product Attributes
- Product Code Alteration
- Equipment Master Model
- Release Document Evidence
- Document Frequency Migration
- Equipment Type Migration
- Recipe Component Options Migration
- Unique Client Code Constraint
- Equipment Material Consumption Field
- Distinct Null Components Migration
- Maintenance App Schema
- Spare Part Delivery Backing
- Planning App Schema
- Processes App Schema
- Process Execution Voucher Fields
- Production App Schema
- Process Control Migration
- Nullable Batch Kilograms
- Batch Voucher Link
- Batch Equipment Execution Link
- Reception App Schema
- Single Discharge Per Reception
- Reception Quality Fields
- Reception State Change
- Reception Collection Load
- Silo Movement Origin Type
- Reception Arrival Identifier
- Collection App Schema
- Users App Schema
- User Profile Level Field
- Profile Area Options
- Company And Branch Tenancy
- Profile Area Update
- Access Attempt Logging
- Profile Role And Area
- Cleaning Area Addition
- Globals Type Package
- Node Type Definitions
- React Type Definitions
- TypeScript Compiler Dependency
- Vite Build Tool
- Prototype App Entry
- Prototype Domain Rules
- Prototype Data Schema
- Prototype Production Planner
- Prototype Recipe Logic
- Prototype Data Repository
- Prototype Shift Handling
- Prototype UI Components
- Icon Sprite Assets
- Production Batch Model
- Multilevel Recipe Explosion
- Dispatch Requires Released Batch
- User Profile Model
- Dashboard Charts

## God Nodes (most connected - your core abstractions)
1. `QuerysetTenantMixin` - 57 edges
2. `filtrar_por_scope()` - 46 edges
3. `RelacionesTenantMixin` - 39 edges
4. `scope_de()` - 36 edges
5. `Producto` - 32 edges
6. `PerfilUsuario` - 31 edges
7. `obtenerSesion()` - 30 edges
8. `Lote` - 28 edges
9. `Meta` - 28 edges
10. `ValeEstandarizacion` - 27 edges

## Surprising Connections (you probably didn't know these)
- `Foto planta CCAA` --conceptually_related_to--> `Contexto Archivos Fuente`  [AMBIGUOUS]
  frontend/src/assets/images/CCAA.jpg → prototipo/CONTEXTO_ARCHIVOS_FUENTE.md
- `Backlog de Mejoras App CCAA` --conceptually_related_to--> `Receta`  [AMBIGUOUS]
  docs/levantamiento-2026-07/Backlog_Mejoras_App_CCAA.md → maestros/recetas.py
- `Plan Maestro de Rediseño CCAA` --conceptually_related_to--> `DocumentoLiberacion`  [INFERRED]
  docs/PLAN_MAESTRO_REDISENO_CCAA.md → maestros/models.py
- `LIMITES (recepción)` --conceptually_related_to--> `Flujo Fabrica.md (fuente original de planta)`  [AMBIGUOUS]
  recepcion/dominio.py → docs/REGLAS_DE_PLANTA.md
- `Arquitectura evolutiva de abastecimiento` --conceptually_related_to--> `Receta (model)`  [INFERRED]
  docs/ARQUITECTURA_EVOLUTIVA_ABASTECIMIENTO.md → maestros/recetas.py

## Import Cycles
- None detected.

## Hyperedges (group relationships)
- **Dossier de Liberación — 19 registros que forman la regla central de liberación** — concept_dossier_19_registros, maestros_models_documentoliberacion, produccion_models_controlproceso, inocuidad_models_monitoreoppro, docs_levantamiento_2026_07_borrador_p0, docs_levantamiento_2026_07_modelo_datos_flujo_ccaa [EXTRACTED 0.85]
- **SKU de producto y código de lote** — concepto_sku_producto, concepto_codigo_lote, maestros_producto, maestros_catalogos_sku, maestros_dominio [EXTRACTED 0.85]
- **Programa horario y balance de leche acoplados en el Planificador** — prototipo_planificador, concept_planificador_bloqueplan, concept_planificador_balanceDia, concept_planificador_codigoproduccion, concept_planificador_consumodia [EXTRACTED 0.90]
- **Ecosistema del generador de SKU de producto** — docs_levantamiento_2026_07_sku_productos, maestros_dominio_generar_sku, maestros_dominio_sku_valido, maestros_catalogos_sku, maestros_models_producto, maestros_models_mandante, concept_sku_estructura [EXTRACTED 0.90]

## Communities (278 total, 121 thin omitted)

### Community 0 - "Master Data Models"
Cohesion: 0.10
Nodes (26): Catálogos compartidos del proceso productivo. Traducidos de…, Maestros del proceso productivo: mandantes, productos, especificaciones y el…, Registro de producción: lotes y sus análisis de calidad. Traducción de las…, Meta, MovimientoSilo, OrigenTipo, Recepción de leche y libro mayor de los silos. Traducción de las entidades…, Un asiento del libro mayor de un silo. Nunca se edita la ocupación: se agrega… (+18 more)

### Community 1 - "Product SKU Model"
Cohesion: 0.09
Nodes (20): Los componentes se cargan desde su receta: así se lee un escandallo. Cada…, RecetaComponenteInline, Categoria, Familia, Formato, Mercado, Naturaleza, NaturalezaComercial (+12 more)

### Community 2 - "Equipment and Silo Masters"
Cohesion: 0.13
Nodes (25): Equipo, Máquina programable de la planta: evaporadores, líneas de secado, etc. Era una…, Silo o estanque de leche o crema. La capacidad permite avisar cuando la…, Silo, Tipo, EquipoSerializer, MandanteSerializer, Meta (+17 more)

### Community 3 - "Production Batch Admin"
Cohesion: 0.06
Nodes (34): AnalisisAdmin, AnalisisInline, ControlProcesoAdmin, ControlProcesoLecturaInline, LoteAdmin, register, El detalle horario se carga desde su control, como en el formato., Los análisis se cargan desde el lote: es como llegan desde el laboratorio. (+26 more)

### Community 4 - "Stock and Orders UI"
Cohesion: 0.08
Nodes (36): AbastecimientoPedidos, AbastecimientoStock, CERRADAS, Pedidos(), ES_AJUSTE, OPERACIONES, Stock(), agregarDetalleMRQ() (+28 more)

### Community 5 - "Production Screen"
Cohesion: 0.12
Nodes (27): Produccion, FormularioLote(), hoy(), Props, formato, Produccion(), Analisis, borrarLote() (+19 more)

### Community 6 - "Inventory API Views"
Cohesion: 0.08
Nodes (44): Bodega, BodegaSerializer, AccesoAseos, AdjuntoViewSet, AjusteInventarioViewSet, AlertaViewSet, _areas_aseo_del_usuario(), BodegaViewSet (+36 more)

### Community 7 - "Milk Reception UI"
Cohesion: 0.15
Nodes (19): LecheEnCamino, LechePanel, EnCamino(), formato, FormularioRecepcion(), hoy(), ModuloFormulario, nuevoModulo() (+11 more)

### Community 8 - "Maintenance Work Orders"
Cohesion: 0.10
Nodes (29): OrdenTrabajoAdmin, register, RepuestoInline, Estado, FallaEquipo, Meta, OrdenTrabajo, PlanPreventivo (+21 more)

### Community 9 - "Inventory Domain Models"
Cohesion: 0.08
Nodes (66): AjusteInventario, Alerta, Aprobacion, ConsumoLoteProduccion, Decision, DetalleEntregaProduccion, DetalleOrdenCompra, DetalleRecepcionCompra (+58 more)

### Community 10 - "Shared UI Components"
Cohesion: 0.14
Nodes (29): Aviso(), Estado(), Tarjeta(), TONO_ESTADO, Vacio(), claseBoton, claseCampo, claseCelda (+21 more)

### Community 11 - "Product Specifications"
Cohesion: 0.13
Nodes (12): Especificacion, Rangos de calidad aceptables de un producto, versionados en el tiempo. Un lote…, Valida la forma de `rangos`, que por ser JSON la base no valida., _empresa_del_actor(), EspecificacionSerializer, Si esta versión es la que hoy manda para su producto. **La resuelve el backend…, Delega en el `clean()` del modelo para no escribir dos veces las mismas reglas.…, La empresa en la que escribe este actor, o `None` si es ambiguo. (+4 more)

### Community 12 - "Production Planning UI"
Cohesion: 0.09
Nodes (36): Planificacion, FormularioBloque(), Props, esNoche(), Gantt(), Props, ESTILO_ESTADO, lunesDeHoy() (+28 more)

### Community 13 - "Master Data Forms UI"
Cohesion: 0.12
Nodes (37): FormularioMandante(), Props, FormularioProducto(), Props, camposDe(), etiquetaParametro(), Maestros(), Pestana (+29 more)

### Community 14 - "Food Safety PPRO Admin"
Cohesion: 0.08
Nodes (21): MonitoreoPPROAdmin, PproLecturaAdmin, PproLecturaInline, register, Las lecturas se cargan desde su monitoreo: así llegan del formato., Meta, MonitoreoPPRO, PproLectura (+13 more)

### Community 15 - "Milk Quality Screens"
Cohesion: 0.13
Nodes (12): LecheCalidad, LecheDescarga, LecheHistorial, LecheMuestreo, ESTILO_ESTADO, formatearFecha(), formato, TablaRecepciones() (+4 more)

### Community 16 - "Batch Detail Screen"
Cohesion: 0.14
Nodes (17): Borrador, borradorDe(), cambios(), DetalleLote(), ESTILO_ESTADO, Props, FormularioAnalisis(), Props (+9 more)

### Community 17 - "Route Management UI"
Cohesion: 0.18
Nodes (15): LecheRutas, estadoClase, fechaHoraLocal(), hoy(), Rutas(), agregarCarga(), cerrarRuta(), crearParada() (+7 more)

### Community 18 - "Milk Collection Routes"
Cohesion: 0.12
Nodes (24): register, RutaRecoleccionAdmin, Alcohol, CargaModulo, Estado, Meta, ParadaRuta, Recoleccion (+16 more)

### Community 19 - "Reception Flow Service"
Cohesion: 0.17
Nodes (18): AccionFlujo, AccionRecepcion(), detalleError(), Props, asignarSilo(), CatalogosFlujoRecepcion, CONTROLES_NUMERICOS, CONTROLES_OPCION (+10 more)

### Community 20 - "Navigation and Route Guards"
Cohesion: 0.10
Nodes (31): Administracion, Foto planta CCAA, Grupo, gruposBase, Modulo, Navbar(), RutaAdmin(), RutaProtegida() (+23 more)

### Community 21 - "Release Document Catalog"
Cohesion: 0.15
Nodes (10): Area, DocumentoLiberacion, Frecuencia, Un documento del checklist de liberación y, en `plantilla`, los campos de su…, Etapa del flujo que genera el registro. Reproduce el orden del Dossier de…, Cada cuánto se llena el registro. **No es un detalle administrativo:** decide…, Valida `aplica_a` y `plantilla`, que por ser JSON la base no valida. Se valida…, DocumentoLiberacionSerializer (+2 more)

### Community 22 - "Maintenance and Process UI"
Cohesion: 0.14
Nodes (21): Mantenimiento, Procesos, EmptyState(), ErrorState(), PageLoader(), estilos, StatusBadge(), Mantenimiento() (+13 more)

### Community 23 - "Role Permissions"
Cohesion: 0.17
Nodes (13): Los roles del proceso, tal como los define el prototipo…, Rol, EscribeEstandarizacion, EscribePlanta, IsAdminDeArea, PermisoPorRol, PuedeVerAuditoria, BasePermission (+5 more)

### Community 24 - "Planning Models"
Cohesion: 0.12
Nodes (16): catalogos(), api_view, Los valores que admiten los campos de opciones de la planificación., Igual que en maestros: el modelo es la fuente de verdad y la pantalla no lleva…, CategoriaConsumo, CodigoProduccion, Estado, EstadoEquipo (+8 more)

### Community 25 - "Batch Serializers"
Cohesion: 0.13
Nodes (9): LoteDetalleSerializer, LoteSerializer, Aplica las transiciones que el modelo declara. Estaban escritas en…, Dos guardas sobre la edición de un lote ya existente. No son burocracia: un…, Un lote se declara producido con sus kilos, no sin ellos. El lote se abre al…, Las salidas de silo que este lote consumió., Un lote cerrado o anulado es histórico, y el histórico se audita., Evalúa el lote contra la especificación vigente en su fecha. Los análisis y las… (+1 more)

### Community 26 - "Frontend App Routing"
Cohesion: 0.06
Nodes (30): Frontend index.html, Favicon SVG, Frontend README, App(), Abastecimiento, AbastecimientoBodegas, AbastecimientoCalidad, AbastecimientoDetalleLote (+22 more)

### Community 27 - "Reception Domain Rules"
Cohesion: 0.19
Nodes (12): EvaluacionRecepcion, evaluar_recepcion(), _numero(), Ocupacion, ocupacion_silo(), Any, Reglas de recepción y silos. Traducción de `prototipo/js/modelo/dominio.js`.…, Ocupación real de un silo: la suma de su libro de movimientos. No es el… (+4 more)

### Community 28 - "Standardization Voucher Model"
Cohesion: 0.14
Nodes (7): Estado, Meta, El RC que dio el análisis. Se calcula, no se guarda. Un RC almacenado se…, Cuánto lleva agitando. `None` si todavía no empezó., Solo después de los 30 minutos. Antes, la mezcla no es homogénea y la muestra…, Si el RC medido cumple, y qué agregar si no. Delega en el dominio., ValeEstandarizacion

### Community 29 - "Planning Serializers"
Cohesion: 0.18
Nodes (8): BalanceDiaSerializer, CodigoProduccionSerializer, Meta, Una fila del balance con todo lo derivado ya calculado., serializar_balance(), serializar_consumo(), BalanceDiaViewSet, CodigoProduccionViewSet

### Community 30 - "Client and Recipe Masters"
Cohesion: 0.15
Nodes (9): Cliente, Mandante, Meta, Empresa dueña del producto elaborado. Incluye la marca propia CCAA., Segmento «cliente» del SKU. Las claves son las de `catalogos_sku`., Camión de transporte de leche, con sus choferes por turno., Qué se necesita para obtener un producto. Multinivel y versionada. La decisión…, Receta (+1 more)

### Community 31 - "Batch API Viewset"
Cohesion: 0.09
Nodes (15): LoteViewSet, action, Abre una corrida desde un vale liberado de Estandarización. Producción no elige…, Vales liberados con saldo, listos para que Producción los tome., Además de guardar, descuenta de bodega si el lote pasó a producido. Es el…, Intenta el descuento. Devuelve el motivo si no se pudo, o `None`. **No…, El código que le tocaría a un lote nuevo, según el POE.009.02. Se **sugiere**,…, La leche que este lote tomó de los silos. Aquí empieza la trazabilidad. La… (+7 more)

### Community 32 - "Audit Actor Context"
Cohesion: 0.08
Nodes (35): AuditoriaConfig, AppConfig, Actor, actor_actual(), fijar_actor(), Quién está haciendo el cambio. Las señales de Django (`pre_save`, `post_save`,…, Quién está actuando. Fuera de una petición devuelve el actor «sistema»:…, Devuelve el testigo para restaurar el valor anterior. (+27 more)

### Community 33 - "Purchasing Screen"
Cohesion: 0.23
Nodes (12): AbastecimientoCompras, Compras(), PUEDE_CONVERTIRSE, PUEDE_DECIDIRSE, PUEDE_ENVIARSE, convertirSolicitudEnOrdenes(), decidirSolicitudCompra(), enviarSolicitudCompra() (+4 more)

### Community 34 - "Release Signature Serializers"
Cohesion: 0.14
Nodes (7): LiberacionSerializer, Meta, Lo mínimo que el dominio necesita para validar: estado y valores. Existe porque…, El expediente de autorización. Todo lo que constituye la firma es de solo…, Un formulario completado. Los valores viajan como los tecleó quien lo llenó; la…, RegistroCalidadSerializer, _RegistroEnMemoria

### Community 35 - "Milk Assignment Panel"
Cohesion: 0.23
Nodes (11): litros, mensajeDe(), PanelAsignacion(), Props, Asignacion, asignarLeche(), obtenerAsignacion(), obtenerTrazabilidad() (+3 more)

### Community 36 - "Planning Views"
Cohesion: 0.21
Nodes (20): SemanaPlanSerializer, serializar_contraste(), serializar_desviacion(), cerrar(), _contexto(), contraste(), programa(), publicar() (+12 more)

### Community 37 - "User Profile Areas"
Cohesion: 0.11
Nodes (17): areas_fuera_de_catalogo(), condicion_de_area(), perfiles_del_area(), Quién trabaja en cada área. Una sola respuesta, y no dos. La pregunta aparece…, Los roles antiguos que implican trabajar en esta área., La condición «este perfil cubre `area`», reutilizable desde cualquier queryset.…, Los perfiles activos que cubren un área, acotados al tenant que se pida., Igual, pero como `User` — que es lo que necesitan los desplegables. (+9 more)

### Community 38 - "Environment Hardening Settings"
Cohesion: 0.19
Nodes (12): errores_entorno_endurecido(), exigir_postgresql(), normalizar_entorno(), Validación explícita de la configuración que protege producción., Rechaza fallbacks que invalidan bloqueos y constraints del dominio., Devuelve todos los errores para no obligar a corregirlos uno por uno., validar_entorno_endurecido(), env_bool() (+4 more)

### Community 39 - "Equipment Record Serializers"
Cohesion: 0.20
Nodes (4): Meta, Serializers de los registros que pertenecen al equipo y su período., Un registro «según programa» tiene que decir hasta cuándo cubre. Sin eso no…, RegistroEquipoSerializer

### Community 40 - "User Admin Panel"
Cohesion: 0.07
Nodes (31): AreaDePerfilInline, EmpresaAdmin, IntentoAccesoAdmin, PerfilUsuarioAdmin, PerfilUsuarioInline, action, display, register (+23 more)

### Community 41 - "Reception Serializers"
Cohesion: 0.09
Nodes (15): RecepcionSerializer, _notificar_recepcion(), action, Cuántas recepciones hay en cada estado, **sobre el total**. El tablero las…, Registra un camion una sola vez y crea sus modulos atomicamente., Quién puede figurar como responsable de una muestra., Identifica la muestra del módulo y lo entrega a la cola de Calidad., Registra los resultados y deja el módulo aprobado o retenido. (+7 more)

### Community 42 - "Standardization Screen"
Cohesion: 0.16
Nodes (21): Cronometro(), TONOS, Estandarizacion(), rc(), TONO, accion(), agitarVale(), anularVale() (+13 more)

### Community 43 - "Tenant Backfill Migrations"
Cohesion: 0.12
Nodes (4): Migration, Migration, Migration, Migration

### Community 44 - "Production Plan Blocks"
Cohesion: 0.20
Nodes (7): BloquePlan, Una corrida programada: un tramo de horas en un equipo. Sustituye a las celdas…, Solo los evaporadores restan del balance (PLANIFICADOR.md §4.1). Quién es…, Tipo, BloquePlanSerializer, Delega en el dominio, que es quien sabe de solapamientos. La comprobación…, BloquePlanViewSet

### Community 45 - "Batch Opening Services"
Cohesion: 0.21
Nodes (10): abrir_lote_desde_vale(), _encadenar_con_la_estandarizacion(), litros_ya_tomados(), atomic, El paso del vale al lote. **Quien consume la leche de los silos es el vale**:…, Abre la ejecución de la máquina elegida que toma la leche del vale. Es lo que…, Cierra la ejecución productiva con los kilos que salieron. Se llama cuando el…, Cuántos litros de este vale se llevaron ya otros lotes. (+2 more)

### Community 46 - "Master Data Admin"
Cohesion: 0.16
Nodes (15): DocumentoLiberacionAdmin, EquipoAdmin, EspecificacionAdmin, MandanteAdmin, ProductoAdmin, display, register, Máquinas de la planta. `consume_leche` es una regla del balance, no una… (+7 more)

### Community 47 - "Standardization Services"
Cohesion: 0.20
Nodes (16): anular(), decidir(), _exigir_transicion(), iniciar_agitacion(), atomic, El ciclo del vale de estandarización. Cada paso es una acción con su regla, no…, Arranca el reloj de la agitación. La hora se toma del servidor y no se recibe…, Guarda el análisis de la muestra y deja el vale listo para decidir. **Exige los… (+8 more)

### Community 48 - "Release Dossier UI"
Cohesion: 0.12
Nodes (23): Liberacion, ESTILO_CALIDAD, Expediente(), Props, ESTILO_CALIDAD, ESTILO_LIBERACION, Liberacion(), prioridad() (+15 more)

### Community 49 - "MRP Screen"
Cohesion: 0.27
Nodes (11): numero(), Mrp(), TablaSemanal(), calcularMRP(), EjecucionMRP, ejecutarMRPSemana(), esperarEjecucionMRP(), obtenerEjecucionesMRP() (+3 more)

### Community 50 - "Weekly Milk Balance Rules"
Cohesion: 0.15
Nodes (21): balance_semana(), consumo_dia(), ConsumoDia, factor_concentracion(), horas_corrida(), _numero(), puede_publicar(), Any (+13 more)

### Community 51 - "Reception Purchase Screen"
Cohesion: 0.24
Nodes (10): ABIERTAS, Recepcion(), VACIA, crearRecepcionCompra(), DetalleOrdenCompra, enviarOrdenCompra(), obtenerOrdenesCompra(), obtenerUbicaciones() (+2 more)

### Community 52 - "Process Execution Admin"
Cohesion: 0.07
Nodes (46): motivo_equipo_no_habilitado(), Por qué este equipo no puede producir, o `None` si puede. Aplica dos de las…, EjecucionProcesoAdmin, EntradaInline, register, SalidaInline, EjecucionProceso, EntradaProceso (+38 more)

### Community 53 - "Tenant Scope Filtering"
Cohesion: 0.09
Nodes (9): exigir_sucursal_permitida(), filtrar_por_scope(), Filtra un queryset; fuera del scope se comporta como objeto inexistente., La única empresa activa, o `None` si hay cero o varias. Mismo criterio que…, Resuelve la sucursal sin confiar en un tenant enviado por el cliente. **La…, scope_de(), ScopeUsuario, sucursal_para_escritura() (+1 more)

### Community 54 - "Login Attempts and Recovery"
Cohesion: 0.08
Nodes (33): authentication_classes, IntentoAcceso, Cada intento de iniciar sesión, exitoso o no. Antes no quedaba rastro de…, ConfirmacionRecuperacionSerializer, Meta, PerfilUsuarioSerializer, El usuario tal como lo necesita la interfaz. Incluye el perfil, que es de donde…, Valida la dirección a la que se enviarán las instrucciones. (+25 more)

### Community 55 - "Standardization App"
Cohesion: 0.27
Nodes (6): El vale de estandarización: la hoja RC, con su ciclo. Es el documento que dice…, CalculoMezclaSerializer, Meta, MuestraSerializer, Entrada del cálculo previo: no crea nada, solo responde cuánto de cada., ValeEstandarizacionSerializer

### Community 56 - "Recipe Explosion"
Cohesion: 0.13
Nodes (28): _acumular(), _arbol(), Explosion, explosionar(), insumo_por_unidad(), litros_de_leche(), Nodo, NodoInsumo (+20 more)

### Community 57 - "CIP Cycle Model"
Cohesion: 0.13
Nodes (11): CicloCIP, EtapaCIP, Parámetros medidos en cada fase del ciclo, sin fijar una receta única., TipoAseo, TipoObjetivo, Verificacion, CicloCIPSerializer, atomic (+3 more)

### Community 58 - "Procurement Panel"
Cohesion: 0.18
Nodes (16): Indicador(), ESTILO_SEVERIDAD, INSPECCION_CERRADA, MRQ_CERRADA, ORDEN_SEVERIDAD, Panel(), Alerta, lista() (+8 more)

### Community 59 - "File Attachment Validation"
Cohesion: 0.07
Nodes (40): ContenidoNoCorresponde, ValueError, Comprobación del contenido de un archivo adjunto. La extensión y el tamaño ya…, La firma del archivo no coincide con lo que dice su extensión., Lee la cabecera y comprueba que corresponda a la extensión declarada. Deja el…, verificar(), Adjunto, DetalleSolicitudCompra (+32 more)

### Community 60 - "Quality Release Rules"
Cohesion: 0.08
Nodes (47): avance_checklist(), bloqueos_de_inocuidad(), campos_faltantes(), _coincide(), cotejar_con_analisis(), cubre_al_lote(), DecisionLiberacion, Discrepancia (+39 more)

### Community 61 - "Inventory Movement Services"
Cohesion: 0.10
Nodes (8): consumir_receta_produccion(), Descuenta por FEFO los insumos que la receta del lote declara. La receta se…, MovimientoViewSet, NotificacionViewSet, action, Emite las órdenes de compra de esta solicitud, una por proveedor. El estado…, La manda al proveedor. Hasta aquí era un borrador, y el MRP no cuenta un…, _tenant_get()

### Community 62 - "Health Check Endpoints"
Cohesion: 0.31
Nodes (8): URL configuration for config project. The `urlpatterns` list routes URLs to…, comprobar_postgresql(), liveness(), El proceso HTTP está vivo; no consulta dependencias., El proceso está listo únicamente si PostgreSQL responde., readiness(), never_cache, require_GET

### Community 63 - "Standardization Voucher Form"
Cohesion: 0.20
Nodes (5): FormularioVale(), inicial, EntradaCalculo, Mezcla, NuevoVale

### Community 64 - "Suppliers Screen"
Cohesion: 0.31
Nodes (9): AbastecimientoProveedores, mensajeDe(), Proveedores(), VACIO_CONDICION, VACIO_PROVEEDOR, crearProveedor(), guardarCondiciones(), obtenerInsumoProveedores() (+1 more)

### Community 65 - "Milk Balance Table"
Cohesion: 0.24
Nodes (9): BalanceLeche(), Celda(), litros(), miles, Props, CATEGORIAS, DIAS, FilaBalance (+1 more)

### Community 66 - "Contrast Delta Component"
Cohesion: 0.27
Nodes (8): Contraste(), miles, numero(), Props, Tarjeta(), Contraste, Desviacion, obtenerContraste()

### Community 67 - "Quality Record Views"
Cohesion: 0.19
Nodes (5): LiberacionViewSet, Quién completó el registro lo pone el servidor, no el cliente. Es la misma…, Quien completa el formulario queda registrado, con la hora del servidor. Es el…, RegistroCalidadViewSet, RegistroEquipoViewSet

### Community 68 - "Dynamic Form Renderer"
Cohesion: 0.42
Nodes (8): faltantes(), FormularioDinamico(), fueraDeRango(), Props, vacio(), Discrepancia, EstadoDocumento, guardarRegistro()

### Community 69 - "Quality Serializers"
Cohesion: 0.10
Nodes (37): ahora(), ConcesionSerializer, FirmaSerializer, El avance documental de un lote, con el detalle de cada documento., El veredicto de calidad. Recalculado siempre, nunca leído de una tabla., El veredicto de liberación, con sus motivos. Los bloqueos van siempre, incluso…, Lo que se envía al firmar una liberación normal., Lo que se envía al liberar bajo concesión. El motivo es obligatorio aquí y su… (+29 more)

### Community 70 - "Specification Form UI"
Cohesion: 0.28
Nodes (8): CAMPO, FormularioEspecificacion(), hoy(), Modo, motivoDelFallo(), TEXTO, NuevaEspecificacion, Rango

### Community 71 - "Product Serializer & SKU"
Cohesion: 0.29
Nodes (4): ProductoSerializer, El SKU descompuesto en sus valores, para poder contrastarlo con los atributos…, Traduce el rechazo del generador a un error de campo. Sin esto, una combinación…, Lo que ya tiene el producto, para validar un PATCH parcial.

### Community 72 - "Frontend TS Config"
Cohesion: 0.08
Nodes (23): compilerOptions, allowArbitraryExtensions, allowImportingTsExtensions, erasableSyntaxOnly, jsx, lib, module, moduleDetection (+15 more)

### Community 73 - "User Profile Startup Checks"
Cohesion: 0.29
Nodes (5): AppConfig, UsuariosConfig, areas_dentro_del_catalogo(), Comprobaciones de arranque sobre los perfiles., Avisa de los perfiles con un `area` que no está en el catálogo. `choices` **no…

### Community 74 - "Silo Occupancy View"
Cohesion: 0.29
Nodes (6): LecheSilos, formato, Silos(), obtenerOcupacion(), Ocupacion, OcupacionSilo

### Community 75 - "Project Instructions Doc"
Cohesion: 0.10
Nodes (18): Código de lote (esquema), Declarar producido descuenta bodega, no bloquea, Criterios de evidencia comparan código de equipo, Un código de cliente, un mandante, SKU de producto (12 dígitos, 6 segmentos), Una sola receta (maestros.Receta), Veredicto de calidad no persistido, Flujo del sistema (+10 more)

### Community 76 - "Audit Trail Model"
Cohesion: 0.10
Nodes (17): register, Solo lectura, también aquí. Un registro de auditoría que se puede editar no…, RegistroAuditoriaAdmin, Accion, Meta, Registro de auditoría: quién cambió qué, cuándo, y de qué a qué. Es un…, Un cambio sobre un registro del sistema., RegistroAuditoria (+9 more)

### Community 77 - "Material Nonconformity Closure"
Cohesion: 0.29
Nodes (5): Destino, NoConformidadMaterial, cerrar_no_conformidad(), Cierra una no conformidad de material dejando qué se hizo con él. `cerrada` era…, Cierra dejando qué se hizo con el material. No es un `PATCH cerrada=true`: el…

### Community 78 - "Daily Milk Balance"
Cohesion: 0.29
Nodes (3): Una fila del balance, con todo lo derivado ya calculado., Un saldo negativo por origen es una alarma: falta leche de ese mandante para lo…, SaldoDia

### Community 79 - "Graph Email Backend"
Cohesion: 0.15
Nodes (9): MicrosoftGraphEmailBackend, MicrosoftGraphEmailError, RuntimeError, Backend de correo para Microsoft 365 mediante Microsoft Graph y OAuth 2.0. Usa…, Error seguro y sin credenciales devuelto por Microsoft Graph., Envía mensajes de Django usando el endpoint ``sendMail`` de Graph., Envía cada mensaje y devuelve la cantidad aceptada por Graph., Comprueba que las cuatro credenciales obligatorias estén presentes. (+1 more)

### Community 80 - "Equipment Form UI"
Cohesion: 0.43
Nodes (6): codigoDesde(), FormularioEquipo(), Props, TIPOS, crearEquipo(), editarEquipo()

### Community 81 - "Measurable Parameter Catalog"
Cohesion: 0.40
Nodes (5): ParametroSerializer, Catálogo de parámetros medibles, para que el frontend arme formularios., parametros(), api_view, Catálogo de parámetros fisicoquímicos medibles.

### Community 82 - "Generic Master Form"
Cohesion: 0.40
Nodes (4): Campo, FormularioMaestro(), Props, TipoCampo

### Community 83 - "Food Safety Panel"
Cohesion: 0.20
Nodes (19): mensajeDe(), PanelInocuidad(), Props, borrarLecturaControl(), CatalogosInocuidad, ControlProceso, crearControl(), crearLecturaControl() (+11 more)

### Community 86 - "Equipment Records UI"
Cohesion: 0.22
Nodes (15): Registros, CampoDePlantilla(), FormularioRegistro(), hoy(), Props, ESTILO_ESTADO, haceUnMes(), Registros() (+7 more)

### Community 87 - "Node TS Config"
Cohesion: 0.10
Nodes (19): compilerOptions, allowImportingTsExtensions, erasableSyntaxOnly, lib, module, moduleDetection, noEmit, noFallthroughCasesInSwitch (+11 more)

### Community 88 - "Row-Lock Engine Check"
Cohesion: 0.29
Nodes (5): CalidadConfig, AppConfig, motor_soporta_bloqueo(), Comprobación de arranque: que el motor sepa bloquear filas. Existe como defensa…, Registrada en `CalidadConfig.ready()`.

### Community 89 - "Quality Release Admin"
Cohesion: 0.10
Nodes (15): LiberacionAdmin, register, Los valores se ven como JSON crudo a propósito: el formulario dibujado desde la…, RegistroCalidadAdmin, Estado, Liberacion, Meta, Liberación de producto: los formularios completados y la autorización final.… (+7 more)

### Community 93 - "Standardization Endpoints"
Cohesion: 0.26
Nodes (4): _conflicto(), action, Los desplegables y las constantes del ciclo, desde el backend. Los minutos de…, ValeEstandarizacionViewSet

### Community 94 - "Production Domain Rules"
Cohesion: 0.05
Nodes (44): codigo_lote_valido(), consumo_de_inventario_pendiente(), DecisionApertura, DecisionCierre, DetalleParametro, _es_vacio(), especificacion_vigente(), EvaluacionAnalisis (+36 more)

### Community 97 - "Prototype Design Docs"
Cohesion: 0.22
Nodes (13): Password reset email (HTML), Password reset email (text), Password reset subject, especificacion versionada (entidad prototipo), liberacion / puedeLiberar() (entidad prototipo), lote (entidad prototipo), balanceDia (propuesto), bloquePlan (propuesto) (+5 more)

### Community 98 - "Technical Audit Findings"
Cohesion: 0.17
Nodes (10): estandarizacion y recoleccion sin auditar, LOGGING = {} — no hay registro de nada, MEDIA_ROOT vacío, Solo el login tiene límite de peticiones, auditoria/registro.py (APPS_AUDITADAS), Reglas del vale de estandarización, Una sola planta, y no se nota, Auditoría técnica 2026-08-14 (+2 more)

### Community 99 - "Exceptional Material Release"
Cohesion: 0.18
Nodes (5): LiberacionExcepcionalMaterial, Cuánto se ha consumido bajo esta concesión. Se suma del libro de movimientos y…, Lo que todavía ampara., ¿Sigue amparando algo? Se calcula y no se guarda: un booleano almacenado no se…, El modelo valida y aquí se le llama. Antes esto repetía a mano dos de las…

### Community 101 - "Plant Survey Docs"
Cohesion: 0.25
Nodes (13): Codificación de lote POE.009.02, Dossier de Liberación (19 registros, CCAA.Calidad.FORM.023), NoConformidad (propuesto), Backlog de Mejoras App CCAA, Borrador P0, Modelo de Datos y Flujo CCAA, MonitoreoPPRO, PproLectura (+5 more)

### Community 102 - "Frontend Dependencies"
Cohesion: 0.13
Nodes (15): axios, dependencies, axios, lucide-react, react, react-dom, react-router-dom, tailwindcss (+7 more)

### Community 106 - "MRP and Supplies"
Cohesion: 0.11
Nodes (19): Categoria, EjecucionMRP, Insumo, Unidad, catalogos_de_receta(), ejecutar_mrp_semana(), insumos_requeridos(), Productos y recetas cargados una vez, listos para explotar. `explosionar` no… (+11 more)

### Community 107 - "Plan vs Actual Contrast"
Cohesion: 0.17
Nodes (12): contrastar_semana(), ContrasteDia, Desviacion, _numero(), Any, Contraste del plan contra lo que realmente pasó. Es la otra mitad del…, Los totales de la semana, para encabezar la pantalla., Un par plan/real, con su diferencia ya calculada. (+4 more)

### Community 111 - "Deployment and Decisions"
Cohesion: 0.21
Nodes (10): backend requirements.txt, backend requirements-dev.txt, calidad/checks.py (E001), Decisión 001: PostgreSQL, Arquitectura evolutiva de abastecimiento, Arquitectura, flujos BPMN y escalabilidad, Despliegue Docker de CCAA, Resultado Fase 0 (+2 more)

### Community 114 - "Lint Dev Dependencies"
Cohesion: 0.13
Nodes (15): eslint, @eslint/js, eslint-plugin-react-hooks, eslint-plugin-react-refresh, devDependencies, eslint, @eslint/js, eslint-plugin-react-hooks (+7 more)

### Community 116 - "Planning Admin"
Cohesion: 0.19
Nodes (11): BalanceDiaAdmin, BalanceDiaInline, BloquePlanAdmin, BloquePlanInline, CodigoProduccionAdmin, register, Sin columnas de consumo ni de stock final: son derivados que calcula el dominio…, SemanaPlanAdmin (+3 more)

### Community 120 - "Product Load Command"
Cohesion: 0.16
Nodes (9): _clave(), Command, BaseCommand, Carga el maestro de productos desde `Recetas_Cod_Producto.xlsx`. Por qué un…, Corta la transacción de la vista previa. No es un error., El mandante que corresponde a ese código de cliente. Devuelve uno solo sin…, Dos productos con el mismo SKU es lo que decide si hace falta el 7.º segmento…, _Simulacion (+1 more)

### Community 125 - "Worker Management API"
Cohesion: 0.15
Nodes (6): atomic, Deduce empresa/sucursal/alcance cuando el alta no los manda. El formulario de…, Lectura y escritura segura de usuarios junto con su perfil., TrabajadorSerializer, action, TrabajadorViewSet

### Community 127 - "Redesign Proposal Docs"
Cohesion: 0.18
Nodes (12): BloqueoInocuidad (propuesto), EjecucionProceso (propuesto), EventoDominio / Outbox (propuesto), OrdenProduccion (propuesto), Proceso / EtapaProceso (propuesto), Plan Maestro de Rediseño CCAA, Bizagi: buenas prácticas de modelado, Bizagi: múltiples pools e interacciones (+4 more)

### Community 128 - "Audit Trail UI"
Cohesion: 0.27
Nodes (11): Auditoria, Auditoria(), comoTexto(), Diff(), ESTILO_ACCION, par(), buscarAuditoria(), ConsultaAuditoria (+3 more)

### Community 132 - "SKU Encoder"
Cohesion: 0.15
Nodes (15): Catálogos del SKU de producto. Fuente:…, _descomponer(), describir_sku(), generar_sku(), peso_del_formato(), ValueError, Reglas de los maestros. Hoy: el codificador de SKU de producto. Funciones…, ¿El SKU respeta la estructura y sus catálogos? Comprueba además la regla… (+7 more)

### Community 135 - "Plant Rules Reference"
Cohesion: 0.26
Nodes (10): Discrepancia de crioscopía (-0,512 vs -0,510), Fórmula RC = grasa / SNG, Reglas de Planta, calcular_mezcla(), evaluar_rc(), ValeEstandarizacion, Flujo Fabrica.md (fuente original de planta), genealogia_lote() (+2 more)

### Community 144 - "Read-Only Inventory Admin"
Cohesion: 0.20
Nodes (6): CicloCIPAdmin, ExistenciaAdmin, InsumoAdmin, LoteInventarioAdmin, MovimientoInventarioAdmin, register

### Community 149 - "Prototype Data Storage"
Cohesion: 0.31
Nodes (8): cargarDatos(), clonar(), COLECCIONES, DATOS_SEMILLA, guardarDatos(), importarJSON(), obtenerDatos(), restablecerDatos()

### Community 154 - "Equipment & Food Safety Models"
Cohesion: 0.28
Nodes (9): Una sola representación de equipo, Bloqueos de inocuidad no admiten concesión, Separación produccion/inocuidad por app, MonitoreoPPRO (model), PproLectura (model), CicloCIP (model), Equipo (model), ControlProceso (model) (+1 more)

### Community 158 - "RC Standardization Math"
Cohesion: 0.14
Nodes (17): calcular_mezcla(), Correccion, evaluar_rc(), Leche, litros_a_agregar(), Mezcla, La matemática de la estandarización. Sin ORM: reglas puras y comprobables. **RC…, Qué agregar cuando el RC medido no da, y cuánto. `cumple` en verdadero… (+9 more)

### Community 160 - "Dossier Template Seeding"
Cohesion: 0.29
Nodes (5): _checklist(), Migration, _pieza(), Plantillas reales de los documentos del Dossier que son formularios planos.…, Un punto de chequeo: su estado y la observación de su estado.

### Community 164 - "Product SKU & Lot Coding"
Cohesion: 0.39
Nodes (8): codigoProduccion (propuesto), Estructura SKU de 12 dígitos / 6 segmentos, SKU de Productos, generar_sku(), sku_valido(), Mandante, Producto, generar_codigo_lote()

### Community 166 - "Concurrency Lock and MRP"
Cohesion: 0.19
Nodes (10): RuntimeError, Un candado para operaciones caras que no deben solaparse. El MRP semanal…, Otra ejecución de lo mismo está corriendo ahora., Deja pasar una sola ejecución de `clave` a la vez. `segundos` es el plazo tras…, solo_uno(), YaEnCurso, SolicitudCompraSerializer, EjecucionMRPViewSet (+2 more)

### Community 168 - "Specification Versioning API"
Cohesion: 0.20
Nodes (5): EspecificacionViewSet, Cuáles son las versiones vigentes hoy, con la misma función que usa el…, Qué versión de cada especificación manda hoy, resuelto **al usarse**. Se…, Los rangos de calidad de un producto, versionados. **La escribe Calidad, no…, VigentesHoy

### Community 172 - "CIP Cleaning Screen"
Cohesion: 0.14
Nodes (21): Aseos, ahoraLocal(), Aseos(), ControlAseo(), etapasCip, etapasIniciales(), fechaLocal(), FormularioNuevo (+13 more)

### Community 173 - "Release Dossier Seeding"
Cohesion: 0.33
Nodes (4): borrar(), Migration, Siembra los 19 registros del Dossier de Liberación. Origen:…, Deshacer borra solo lo que esta migración sembró. Se filtra además por…

### Community 174 - "Per-Evaporator Checklist Split"
Cohesion: 0.47
Nodes (5): Migration, _plantilla(), Separa el checklist de cuerpos extraños en uno por evaporador. El Dossier lo…, separar(), unir()

### Community 175 - "Pre-Operative Inspection Template"
Cohesion: 0.40
Nodes (4): aplicar(), Migration, _plantilla(), Plantilla de `CCAA.Sec.FORM.003` · Inspección Pre-operativa E1-E2. Transcrita…

### Community 176 - "Unique Client Code Merge"
Cohesion: 0.33
Nodes (4): deshacer(), Migration, Un código de cliente, un mandante. Y la fusión de los que ya se duplicaron. La…, No se pueden desfusionar: al borrar los duplicados se perdió qué producto…

### Community 178 - "Token Auth With Tenant"
Cohesion: 0.40
Nodes (3): Autentica, trae el scope tenant en la misma consulta del token y **le pone…, TokenAuthenticationConScope, TokenAuthentication

### Community 179 - "Email Delivery Check Command"
Cohesion: 0.33
Nodes (3): Command, BaseCommand, Comando operativo para verificar el envío configurado.

### Community 180 - "Transactional Data Cleanup Command"
Cohesion: 0.33
Nodes (3): Command, BaseCommand, Borra los movimientos de planta y deja los maestros en pie. El sistema está en…

### Community 182 - "Unified Audit Change Format"
Cohesion: 0.40
Nodes (3): Migration, Vuelve a la forma plana, por si hay que retroceder la migración., revertir()

### Community 184 - "Checklist Progress Calculation"
Cohesion: 0.40
Nodes (3): AvanceChecklist, Avance documental de un lote. Derivado, nunca persistido (§2.6)., Sin documentos exigibles no hay checklist completo, hay checklist vacío.

### Community 195 - "Frontend Package Manifest"
Cohesion: 0.40
Nodes (4): name, private, type, version

### Community 196 - "Frontend Build Scripts"
Cohesion: 0.40
Nodes (5): scripts, build, dev, lint, preview

### Community 198 - "Standardization Voucher Admin"
Cohesion: 0.40
Nodes (3): display, register, ValeEstandarizacionAdmin

### Community 204 - "Reception Admin"
Cohesion: 0.15
Nodes (9): MovimientoSiloAdmin, register, RecepcionAdmin, Estado, Procedencia, Llegada de un camión. Los controles deciden si la leche se libera al silo o se…, Recepcion, TipoLeche (+1 more)

### Community 343 - "Dashboard Charts"
Cohesion: 0.14
Nodes (15): Dashboard, ESTILO, EtiquetaCalidad(), Dato, formato, GraficoBarras(), Props, Dashboard() (+7 more)

## Ambiguous Edges - Review These
- `Backlog de Mejoras App CCAA` → `Receta`  [AMBIGUOUS]
  docs/levantamiento-2026-07/Backlog_Mejoras_App_CCAA.md · relation: conceptually_related_to
- `LEVANTAMIENTO_PLANTA.md` → `EjecucionProceso (propuesto)`  [AMBIGUOUS]
  docs/levantamiento-2026-07/LEVANTAMIENTO_PLANTA.md · relation: conceptually_related_to
- `Modelo de Datos y Flujo CCAA` → `Contexto Archivos Fuente`  [AMBIGUOUS]
  docs/levantamiento-2026-07/Modelo_Datos_Flujo_CCAA.html · relation: conceptually_related_to
- `Flujo Fabrica.md (fuente original de planta)` → `LIMITES (recepción)`  [AMBIGUOUS]
  docs/REGLAS_DE_PLANTA.md · relation: conceptually_related_to
- `Foto planta CCAA` → `Contexto Archivos Fuente`  [AMBIGUOUS]
  frontend/src/assets/images/CCAA.jpg · relation: conceptually_related_to
- `Frontend index.html` → `Logo Cooperativa Campos Australes`  [AMBIGUOUS]
  frontend/index.html · relation: conceptually_related_to

## Knowledge Gaps
- **368 isolated node(s):** `OrigenTipo`, `Tipo`, `Categoria`, `Familia`, `Formato` (+363 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **121 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **What is the exact relationship between `Backlog de Mejoras App CCAA` and `Receta`?**
  _Edge tagged AMBIGUOUS (relation: conceptually_related_to) - confidence is low._
- **What is the exact relationship between `LEVANTAMIENTO_PLANTA.md` and `EjecucionProceso (propuesto)`?**
  _Edge tagged AMBIGUOUS (relation: conceptually_related_to) - confidence is low._
- **What is the exact relationship between `Modelo de Datos y Flujo CCAA` and `Contexto Archivos Fuente`?**
  _Edge tagged AMBIGUOUS (relation: conceptually_related_to) - confidence is low._
- **What is the exact relationship between `Flujo Fabrica.md (fuente original de planta)` and `LIMITES (recepción)`?**
  _Edge tagged AMBIGUOUS (relation: conceptually_related_to) - confidence is low._
- **What is the exact relationship between `Foto planta CCAA` and `Contexto Archivos Fuente`?**
  _Edge tagged AMBIGUOUS (relation: conceptually_related_to) - confidence is low._
- **What is the exact relationship between `Frontend index.html` and `Logo Cooperativa Campos Australes`?**
  _Edge tagged AMBIGUOUS (relation: conceptually_related_to) - confidence is low._
- **Why does `QuerysetTenantMixin` connect `Inventory API Views` to `Master Data Models`, `Equipment and Silo Masters`, `Production Batch Admin`, `Maintenance Work Orders`, `Food Safety PPRO Admin`, `Milk Collection Routes`, `Planning Serializers`, `Planning Views`, `Concurrency Lock and MRP`, `Specification Versioning API`, `Reception Serializers`, `Production Plan Blocks`, `Process Execution Admin`, `Tenant Scope Filtering`, `Standardization App`, `Inventory Movement Services`, `Quality Record Views`, `Quality Serializers`, `Standardization Endpoints`?**
  _High betweenness centrality (0.033) - this node is a cross-community bridge._