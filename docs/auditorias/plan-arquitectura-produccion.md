La auditoría operacional es mayormente correcta, pero el código ya resuelve parcialmente varios puntos. El riesgo principal no está en “falta de módulos”, sino en permisos demasiado amplios, rutas con fallback silencioso, estados duplicados y operaciones que pueden saltarse los servicios especializados.
No modifiqué código ni ejecuté pruebas en esta etapa.
Diagnóstico validado
Hallazgo operacional	Validación técnica
Ruta universal para todos los productos	Parcial. Existen rutas específicas para polvo, mantequilla y precondensado, pero sobrevive una ruta universal antigua y un fallback inseguro.
Producción y Procesos están mezclados	Confirmado. Son dos centros operacionales que se solapan.
Falta corrida especializada de secado	Confirmado. Secado usa ejecución/lote genérico.
Se puede avanzar sin trazabilidad completa	Confirmado. Algunos servicios retornan None si falta configuración y permiten continuar físicamente.
Envasado está limitado a sacos de 25 kg	Parcial. Backend acepta otros pesos; frontend fija 25 kg y 20 unidades.
Torre de secado aparece como equipo de envasado	Confirmado en frontend y backend.
Flujo de mantequilla/calidad es inconsistente	Confirmado. La interfaz exige Calidad antes de Envasado, pero backend permite envasar; además la liberación intermedia solo admite salidas con silo.
Calidad elige análisis manualmente	Confirmado. Las validaciones son buenas, pero falta una solicitud de muestra vinculada a la salida.
FIFO muestra recepciones candidatas	Confirmado en la API de genealogía. El ledger sí conserva atribuciones reales que deberían reutilizarse.
Permisos demasiado generales	Confirmado y crítico. Condensación y Secado pueden escribir sobre rutas, etapas y otros procesos.
Rework sin control	Parcial. Su aprobación y consumo están controlados, pero falta existencia física, ubicación y segregación.
Materiales consumidos al cerrar producción	Confirmado, aunque es una decisión actualmente intencional. Mezcla consumos de proceso y envasado.
Falta optimización general	No se observa un problema generalizado. Hay paginación y cargas bajo demanda; los puntos concretos son Envasado, genealogía y respuestas demasiado amplias.


Lo que ya está bien implementado
Conviene conservar estas piezas:
- Libro de movimientos de silo inmutable, atribución FIFO y bloqueo de filas.
- Idempotencia en movimientos mediante operation_id.
- Continuación entre salidas y entradas usando EntradaProceso.salida_origen.
- Protección contra sobreconsumo de una salida.
- Servicios transaccionales para estandarización, condensación y mantequilla.
- Validaciones de Calidad sobre vigencia, firmas, especificación e inhibidores.
- Consumo FEFO de materiales con bloqueo de stock.
- Límite de 500 kg por pallet.
- Rutas productivas separadas ya sembradas para polvo, mantequilla y precondensado.
- Cargas bajo demanda en varias secciones de Procesos.
Modelos y módulos principales
- Procesos: Proceso, EtapaProceso, RutaProducto, EjecucionProceso, EntradaProceso, SalidaProceso, EventoProceso.
- Especializados: CorridaCondensacion, CorridaDescremacion, CorridaMantequilla.
- Producción: OrdenProduccion, Lote, ControlProceso, Analisis, RegistroEnvase, PalletProducto.
- Calidad: expedientes, liberación final y LiberacionProceso.
- Rework: AutorizacionReproceso.
- Silos: MovimientoSilo, AtribucionRecepcion.
- Inventario: recetas versionadas, existencias, lotes de materiales y ConsumoLoteProduccion.
- Equipos: Equipo, actualmente clasificado en tipos demasiado generales.
Los puntos centrales están en [procesos/models.py](C:\\Users\\EQUIPO\\Documents\\GitHub\\CCAA\\backend\\procesos\\models.py), [procesos/servicios.py](C:\\Users\\EQUIPO\\Documents\\GitHub\\CCAA\\backend\\procesos\\servicios.py), [procesos/views.py](C:\\Users\\EQUIPO\\Documents\\GitHub\\CCAA\\backend\\procesos\\views.py), [produccion/servicios.py](C:\\Users\\EQUIPO\\Documents\\GitHub\\CCAA\\backend\\produccion\\servicios.py) y [usuarios/permisos.py](C:\\Users\\EQUIPO\\Documents\\GitHub\\CCAA\\backend\\usuarios\\permisos.py).
Plan técnico priorizado
CRÍTICO
1. Cerrar las vías que saltan reglas de negocio
- Problema: los endpoints genéricos permiten crear o editar ejecuciones, entradas y salidas directamente. Además, EscribeProduccion autoriza Condensación y Secado sobre prácticamente todo el módulo.
- Solución: convertir los CRUD genéricos operacionales en lectura para operadores. Toda escritura deberá pasar por acciones explícitas: iniciar, transferir, incorporar rework, registrar salida, cerrar y cancelar. Los maestros Proceso, EtapaProceso y RutaProducto deben ser administrables solamente con permiso de configuración.
- Afectados: procesos/views.py, procesos/serializers.py, procesos/servicios.py, usuarios/permisos.py, permisos_industriales.py, servicios frontend.
- Backend: permisos por acción y por etapa; validar que el usuario pueda operar la etapa de la ejecución.
- Frontend: ocultar acciones sin autorización y separar permisos de consultar, operar y configurar.
- Base de datos: inicialmente ninguna. Posteriormente migración de permisos personalizados y asignación compatible según áreas actuales.
- Riesgo: frontend antiguo que todavía use POST genérico.
- Dependencia: inventariar llamadas actuales antes de restringir.
- Orden: primero agregar endpoints explícitos, migrar frontend y finalmente bloquear los CRUD genéricos.
2. Eliminar el fallback silencioso de rutas
- Problema: si un producto no tiene RutaProducto, el sistema toma la última etapa activa compatible de cualquier proceso. Una transferencia o cierre puede continuar aunque registrar_estandarizacion() o registrar_produccion() no consiga crear trazabilidad.
- Solución: exigir ruta activa antes de iniciar una operación nueva. Mantener fallback únicamente para lectura histórica y mostrar “configuración incompleta”; nunca usarlo para nuevas escrituras.
- Afectados: procesos/servicios.py, produccion/servicios.py, estandarizacion/servicios.py, administración de productos y rutas.
- Backend: validación previa obligatoria y error operacional claro.
- Frontend: mostrar producto, ruta, siguiente etapa y configuración faltante antes de transferir.
- Base de datos: migración de datos que asigne ruta a todos los productos activos. No borrar la ruta antigua; dejarla como legado/inactiva cuando los datos estén cubiertos.
- Riesgo: productos creados después de la migración 0011 podrían quedar inicialmente bloqueados.
- Dependencia: reporte previo de productos sin ruta y ejecuciones sin encadenamiento.
- Orden: diagnóstico y backfill → validación al activar producto → eliminación del fallback de escritura.
3. Exclusión real de equipos concurrentes
- Problema: transicionar_ejecucion() consulta si el equipo está ocupado, pero no bloquea la fila de Equipo ni existe una restricción PostgreSQL. Dos solicitudes simultáneas podrían iniciar ejecuciones sobre el mismo equipo.
- Solución: bloquear Equipo con select_for_update() antes de iniciar y agregar restricción única condicional para estados que ocupan el equipo.
- Afectados: servicios de procesos, apertura de lote, inicios de condensación, descremación y mantequilla.
- Backend: una única función para adquirir/liberar equipo dentro de transacción.
- Frontend: mostrar conflicto 409 y refrescar estado del equipo.
- Base de datos: índice/restricción parcial sobre equipo para ejecuciones activas. Antes se debe detectar y resolver cualquier duplicado existente.
- Riesgo: definir incorrectamente si PREPARACION ya ocupa físicamente el equipo.
- Dependencia: acordar los estados ocupantes por proceso.
- Orden: bloqueo transaccional → prueba concurrente → restricción de base de datos.
4. Corregir el control de Calidad de mantequilla
- Problema: la corrida queda PENDIENTE_CALIDAD, pero la liberación intermedia exige un silo. Envasado no verifica esa liberación y permite continuar.
- Solución: conservar el control intermedio propio de mantequilla, pero soportar muestras sobre lote/salida sin silo. Envasado deberá comprobar la aprobación de la etapa cuando EtapaProceso.requiere_calidad sea verdadero.
- Afectados: CorridaMantequilla, SalidaProceso, LiberacionProceso, análisis, servicios de envasado y Centro de Calidad.
- Backend: crear solicitud de muestra al cerrar mantequilla; Calidad aprueba/rechaza; la aprobación habilita Envasado.
- Frontend: bandeja “Mantequilla pendiente de control”, estado claro y acción de toma/análisis.
- Base de datos: SolicitudMuestraProceso vinculada a salida y análisis de lote o silo; campos inicialmente anulables. Backfill para salidas pendientes y liberaciones existentes.
- Riesgo: bloquear lotes históricos ya envasados.
- Dependencia: regla de compatibilidad para registros anteriores.
- Orden: modelo de solicitud → backfill → liberación no-silo → bloqueo de Envasado.
ALTO
5. Implementar una corrida especializada de secado
- Problema: Secado utiliza estructuras genéricas y no representa claramente alimentación, torre, rendimiento, finos, pérdidas y producto polvo generado.
- Solución: agregar CorridaSecado como extensión OneToOne de EjecucionProceso, reutilizando entradas, salidas, eventos y controles existentes.
- Backend: acciones explícitas preparar, iniciar, registrar controles, pausar, reanudar y cerrar.
- Frontend: puesto de Secado independiente, mostrando solo torres y lotes habilitados.
- Base de datos: nueva tabla y backfill de ejecuciones históricas de etapa Secado cuando sea posible.
- Riesgo: duplicar datos del lote o controles. La corrida debe almacenar solamente información específica del secado.
- Dependencias: rutas confiables y exclusión de equipo.
- Orden: después de los cambios críticos.
6. Formatos de envasado configurables
- Problema: el frontend fija 25 kg, llama “sacos” a todo y permite torres como equipo.
- Solución: crear FormatoEnvasado por producto: nombre, unidad, kg netos, unidades máximas por pallet y equipos permitidos.
- Afectados: RegistroEnvase, PalletProducto, FormularioEnvase.tsx, catálogos y servicios.
- Backend: endpoint de opciones de envasado según lote/producto; retirar TORRE de equipos aceptados.
- Frontend: formularios dinámicos para saco de polvo o caja de mantequilla.
- Base de datos: nueva tabla y FK nullable desde registros nuevos; conservar formato_kg histórico.
- Riesgo: productos sin formato.
- Dependencia: datos maestros confiables.
- Orden: catálogo → endpoint de opciones → frontend → restricción backend.
7. Definir autoridad de estados sin crear un megaestado
- Problema: OrdenProduccion, Lote, EjecucionProceso y cada corrida especializada mantienen estados parcialmente duplicados. Algunos servicios asignan estados directamente sin registrar EventoProceso.
- Solución:
  - Ejecución: estado físico de la etapa.
  - Corrida especializada: datos específicos; transición siempre coordinada por servicio.
  - Lote: estado del material.
  - Orden: avance planificado.
  - Liberación: decisión de Calidad.
- Backend: prohibir asignaciones directas fuera de servicios y añadir verificador de consistencia.
- Frontend: mostrar separadamente “Proceso”, “Material” y “Calidad”.
- Base de datos: no eliminar columnas todavía. Una retirada futura necesitaría migración y comprobación histórica.
- Riesgo: romper filtros existentes si se intenta unificar todo inmediatamente.
- Dependencias: corregir mantequilla y crear secado.
- Orden: centralizar servicios ahora; normalizar esquema en una fase posterior.
8. Separar puestos operacionales en frontend
- Problema: Procesos.tsx mezcla rutas, descremación, evaporación, mantequilla, rework y genealogía. Produccion también actúa como centro general.
- Solución: conservar componentes y rutas, pero presentar bandejas por puesto:
  - Estandarización.
  - Evaporación/Precondensado.
  - Descremación.
  - Mantequilla.
  - Secado.
  - Envasado.
  - Supervisión y trazabilidad.
- Backend: endpoints de bandeja por etapa, no nuevos modelos universales.
- Frontend: rutas protegidas y navegación según capacidad.
- Base de datos: ninguna.
- Riesgo: duplicar componentes si no se extraen componentes compartidos.
- Dependencia: permisos por etapa.
- Orden: después del cierre de permisos.
9. Separar consumo de proceso y consumo de envasado
- Problema: al marcar un lote como producido se intenta consumir la receta completa; puede incluir envases y pallets que todavía no fueron utilizados.
- Solución: añadir fase al componente de receta y registrar consumos independientes:
  - proceso;
  - envasado;
  - ajustes autorizados.
- Backend: materiales de proceso al cerrar etapa; envases según unidades realmente envasadas; pallets al formar pallet.
- Frontend: mostrar requerido, consumido, faltante y pendiente por fase.
- Base de datos: fase en componentes y unicidad de consumo por lote/fase. Migrar consumos históricos a “producción” evitando dobles descuentos.
- Riesgo: descontar nuevamente materiales ya consumidos.
- Dependencia: formato de envasado.
- Orden: conciliación histórica → esquema → consumo de nuevos registros.
MEDIO
10. Genealogía FIFO exacta
- Problema: la API devuelve ingresos “candidatos” al silo aunque ya existen AtribucionRecepcion reales.
- Solución: construir genealogía desde las atribuciones y cantidades efectivamente consumidas. Usar candidatos solamente en movimientos históricos sin atribución, etiquetándolos como inferidos.
- Backend: extraer la genealogía a un servicio único y reutilizarlo desde lote y procesos.
- Frontend: diferenciar “confirmado por movimiento” e “inferido”.
- Base de datos: normalmente ninguna; puede requerir backfill e índices.
- Riesgo: datos antiguos incompletos.
- Dependencias: ninguna crítica.
- Orden: después de estabilizar rutas.
11. Existencia física de rework
- Problema: hay autorización y consumo, pero no ubicación, pallet, segregación, caducidad ni movimientos físicos separados.
- Solución: mantener AutorizacionReproceso y agregar unidades/movimientos de rework con cantidad, lote/pallet origen, ubicación y estado.
- Backend: Calidad autoriza; Inventario traslada a zona liberada; Producción consume desde existencia aprobada.
- Frontend: bandejas Bloqueado, Aprobado, Consumido y Destruido.
- Base de datos: tablas de unidad y movimiento de rework. No cambiar inmediatamente el OneToOne histórico.
- Riesgo: contabilizar dos veces producto recuperado.
- Dependencia: inventario y ubicaciones.
- Orden: primero visibilidad; luego bloqueo físico obligatorio.
12. Rendimiento, idempotencia y edición concurrente
- Problemas:
  - Envasado realiza cuatro consultas iniciales y dos listas de lotes.
  - Genealogía puede escanear muchos ingresos históricos.
  - El frontend no envía siempre un operation_id estable.
  - Ediciones de metadatos pueden sobrescribirse entre usuarios.
- Solución:
  - endpoint único envasado/bandeja;
  - genealogía basada en atribuciones;
  - UUID estable por operación generado antes del POST;
  - usar version como control optimista en PATCH/transiciones.
- Backend: respuestas resumidas y error 409 por versión o idempotencia.
- Frontend: reutilizar UUID en reintentos y refrescar solo la entidad afectada.
- Base de datos: índices específicos tras medir consultas; no indexar indiscriminadamente.
- Riesgo: contratos de API.
- Dependencias: ninguna para UUID; bandejas dependen de la nueva separación visual.
- Orden: idempotencia → medición → bandejas → concurrencia optimista.
BAJO
13. Limpieza de legado y observabilidad
- Marcar la ruta universal como legado.
- Añadir chequeos de productos sin ruta, ejecuciones sin entrada/salida, estados contradictorios y equipos duplicados.
- Documentar qué proceso genera cada producto intermedio/final.
- Añadir métricas de conflictos 409, fallos de trazabilidad y operaciones reintentadas.
- Retirar código antiguo solamente cuando no tenga consumidores.
No requiere rediseñar el sistema ni eliminar datos actuales.
Orden global recomendado
1. Permisos y cierre de CRUD genéricos.
2. Inventario de rutas y trazabilidad faltante.
3. Backfill de rutas y eliminación del fallback en escrituras.
4. Bloqueo concurrente de equipos.
5. Solicitudes de muestra y corrección de mantequilla.
6. Corrida especializada de Secado.
7. Formatos configurables de Envasado.
8. Separación de pantallas por puesto.
9. Consumo de materiales por fase.
10. Genealogía FIFO exacta.
11. Inventario físico de rework.
12. Optimizaciones e instrumentación.
Conclusión: no hace falta reconstruir Producción ni crear un flujo universal nuevo. La arquitectura actual tiene buenas bases transaccionales y de trazabilidad, pero necesita asegurar sus límites: rutas obligatorias, acciones explícitas, permisos por etapa, exclusión real de equipos y estados coherentes por proceso. Estas correcciones deben preceder cualquier mejora visual grande.


9:57 AM