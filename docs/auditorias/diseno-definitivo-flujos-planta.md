Auditoría real de los cuatro flujos productivos
No modifiqué código. Revisé documentación, backend, frontend, base local, migraciones y pruebas focalizadas.
Conclusión rápida: CCAA tiene una base sólida para Polvo y Precondensado. Mantequilla funciona parcialmente mediante trazabilidad por lote, pero su ruta no incluye Descremado. El flujo de Crema para despacho todavía no puede completarse. El riesgo más serio es que el despacho a granel no descuenta físicamente el producto del silo.
Flujo actual encontrado
1. Leche en polvo
Actualmente existe:
Recepción → análisis de leche → silo → estandarización → evaporación → Calidad del precondensado → Secado → Calidad del polvo a granel → Envasado → pallet en cuarentena → liberación final → Inventario.
Está implementado mediante:
- vales de estandarización;
- rutas obligatorias;
- CorridaCondensacion;
- CorridaSecado;
- LiberacionProceso;
- análisis de silo y análisis de lote separados;
- pallets e inventario de producto terminado;
- trazabilidad hacia atrás.
Es el flujo más completo y existe un E2E que llega hasta el pallet.
2. Precondensado para despacho
Actualmente existe:
Recepción → Calidad → estandarización → evaporación → precondensado en silo → Calidad → salida a granel → solicitud de despacho.
El precondensado:
- no necesita Secado;
- no necesita Envasado;
- se marca como despacho_directo;
- puede agregarse a un despacho sin inventar un pallet.
Problema: cuando el despacho se ejecuta, se registra comercialmente, pero no se genera el movimiento físico de salida del silo.
3. Mantequilla
Actualmente existen las piezas:
Recepción → Calidad → Descremado → crema en TK → Calidad de crema → corrida de Mantequilla → mantequilla a granel → análisis de lote → liberación → Envasado → pallet → Inventario.
La genealogía crema → mantequilla sí se conserva mediante el lote de crema.
Sin embargo, la ruta configurada de mantequilla comienza directamente en:
Mantequilla → Envasado
Descremado y crema quedan conectados por referencias de lote, pero no forman parte de una ruta productiva coherente y seleccionada.
Además, el frontend solamente envasa sacos de 25 kg. Las mantequillas maestras son cajas de 20 kg, por lo que el flujo no puede terminar correctamente desde la interfaz.
4. Crema para despacho
Actualmente funciona:
Recepción → Calidad → Descremado → crema en TK → análisis → liberación individual de Calidad.
Después se detiene.
La salida de Descremado solamente permite:
- siguiente proceso;
- estandarización;
- reproceso.
No permite despacho_directo, y los productos de crema no tienen rutas activas. Por tanto, el flujo completo de crema comercial a granel todavía no existe.
Diferencias respecto del flujo objetivo
Producto	Estado	Diferencia principal
Leche en polvo	Avanzado	Falta asegurar el orden entre liberación final, Envasado y pallet
Precondensado	Parcialmente completo	El despacho no descuenta físicamente el silo
Mantequilla	Parcial	Descremado no pertenece a su ruta y Envasado está fijo en 25 kg
Crema despacho	Incompleto	No hay ruta ni destino de despacho permitido


Problemas backend
CRÍTICO — Despacho a granel sin salida física
ejecutar_despacho() valida Calidad y cambia el estado del despacho, pero no crea un MovimientoSilo de salida.
Consecuencia:
- el despacho dice “despachado”;
- el saldo del silo puede seguir mostrando el producto;
- ese mismo volumen podría volver a utilizarse en Producción;
- la trazabilidad física queda dividida entre Inventario y Recepción.
Afecta principalmente [servicios.py](C:\\Users\\EQUIPO\\Documents\\GitHub\\CCAA\\backend\\inventario\\servicios.py).
CRÍTICO — Crema para despacho no soportada
SalidaProceso.destinos_permitidos() no admite despacho directo para una salida de Descremado.
Afecta [models.py](C:\\Users\\EQUIPO\\Documents\\GitHub\\CCAA\\backend\\procesos\\models.py).
ALTO — Las rutas no representan bien una bifurcación
RutaProducto relaciona un producto con un proceso completo, pero Descremado genera dos productos:
- leche descremada;
- crema.
Cada salida puede tener un destino distinto. Actualmente la ejecución de Descremado no queda asociada a la ruta elegida para cada producto generado.
Por eso la crema puede ser consumida por Mantequilla, pero el sistema no puede explicar formalmente si esa crema se produjo:
- para Mantequilla;
- para despacho;
- para estandarización;
- para otro destino autorizado.
ALTO — Destino final almacenado como texto libre
RutaProducto.destino es texto y el servicio determina el comportamiento buscando palabras como “despacho” o “inventario”.
Eso es frágil: cambiar la redacción puede cambiar la regla operacional.
Debe migrarse a un valor estructurado, por ejemplo:
- siguiente_proceso;
- envasado;
- despacho_directo;
- inventario.
ALTO — Clasificación maestra incorrecta
La carga inicial deja todos los productos como terminado. En la base actual, crema y precondensado aparecen como terminados.
Operacionalmente deberían ser intermedios, aunque puedan venderse a granel. La posibilidad de despacho debe definirla su ruta y liberación, no clasificarlos artificialmente como producto terminado.
El problema nace en [cargar_productos.py](C:\\Users\\EQUIPO\\Documents\\GitHub\\CCAA\\backend\\maestros\\management\\commands\\cargar_productos.py).
ALTO — Orden de liberación final insuficientemente protegido
Al cerrar Secado o Mantequilla:
1. se crea la liberación intermedia;
2. el lote también entra a la bandeja de liberación final;
3. todavía puede no existir ningún envase o pallet.
La liberación comercial final debería exigir el cierre de Envasado cuando el producto tenga formato envasado. De lo contrario, se puede liberar el lote antes de generar sus pallets y los pallets creados posteriormente quedan nuevamente pendientes.
MEDIO — Opciones de Mantequilla muestran crema no habilitada
El endpoint de opciones lista lotes de crema producidos sin filtrar preventivamente la liberación de Calidad. El inicio finalmente los rechaza, por lo que la seguridad existe, pero el operador puede elegir una crema que nunca podrá utilizar.
MEDIO — Identidad pobre en despacho a granel
granel-disponible devuelve como “producto” el nombre de la etapa, no el producto real de la salida.
Cuando convivan crema y precondensado, el operador necesita:
- producto_id;
- producto_nombre;
- lote;
- silo;
- cantidad;
- liberación;
- propietario o mandante cuando corresponda.
Problemas frontend
Envasado fijo en 25 kg
[FormularioEnvase.tsx](C:\\Users\\EQUIPO\\Documents\\GitHub\\CCAA\\frontend\\src\\pages\\Produccion\\FormularioEnvase.tsx) fija:
- formato: 25 kg;
- máximo: 20 sacos;
- total: 500 kg.
Esto funciona para leche en polvo, pero impide envasar mantequilla en cajas de 20 kg.
También permite seleccionar torres como equipos de Envasado, lo que debería eliminarse salvo que exista una justificación operacional explícita.
Bandeja de Envasado demasiado amplia
[Envasado.tsx](C:\\Users\\EQUIPO\\Documents\\GitHub\\CCAA\\frontend\\src\\pages\\Envasado\\Envasado.tsx) carga todos los lotes producidos o cerrados cuya naturaleza sea terminado.
Debido a la clasificación maestra actual, puede mostrar crema y precondensado. El POST posteriormente los rechaza porque su destino no es Envasado.
React debería consumir un endpoint de “lotes envasables”, determinado por Django.
Producción aún presenta una cadena visual casi universal
[Produccion.tsx](C:\\Users\\EQUIPO\\Documents\\GitHub\\CCAA\\frontend\\src\\pages\\Produccion\\Produccion.tsx) muestra:
Descremación → Estandarización → Evaporación → Secado
y Mantequilla como una opción lateral.
Esto puede inducir a pensar que todos los productos deben atravesar la misma secuencia.
La pantalla debería presentar cuatro rutas claramente diferenciadas, reutilizando las pantallas existentes.
Pantalla Procesos demasiado mezclada
[Procesos.tsx](C:\\Users\\EQUIPO\\Documents\\GitHub\\CCAA\\frontend\\src\\pages\\Procesos\\Procesos.tsx) concentra:
- rutas;
- Descremado;
- Evaporación;
- Mantequilla;
- ejecuciones;
- trazabilidad;
- rework.
No es necesario eliminar componentes, pero sí montarlos como puestos o secciones operacionales independientes.
Despacho soporta granel, pero no su operación completa
Inventario permite seleccionar “Precondensado / producto a granel”, pero:
- no existe crema disponible;
- muestra la etapa en vez del producto;
- no muestra claramente el silo físico;
- crear el despacho no lo autoriza ni ejecuta;
- el flujo de autorización no está integrado en ese formulario.
Problemas de arquitectura
1. SalidaProceso es una buena entidad central, pero sus destinos dependen solamente del tipo de etapa, no del producto y ruta seleccionados.
2. RutaProducto no queda persistida en la ejecución. Después resulta difícil demostrar qué alternativa productiva eligió el operador.
3. Descremado es correctamente un proceso con dos salidas, pero el motor lineal de continuación no representa ramas con destinos independientes.
4. Envasado aparece como etapa de las rutas, pero operacionalmente se registra mediante RegistroEnvase, sin una EjecucionProceso de Envasado enlazada explícitamente.
5. Se mezclan parcialmente:
   - estado físico del equipo;
   - estado de la corrida;
   - estado del material;
   - estado de Calidad;
   - estado comercial del lote.
   Secado ya separa bastante bien estos conceptos; el mismo criterio debe mantenerse en los demás flujos.
6. Los permisos de condensacion permiten operar Estandarización, Descremado, Evaporación, Mantequilla y Transferencia. Es funcional, pero demasiado amplio si esos puestos pertenecen a operadores diferentes.
Problemas de proceso lácteo
- La leche de recepción sí queda analizada antes de utilizarse.
- Descremado calcula y registra las dos salidas y la merma.
- La crema y la descremada se liberan por separado, lo cual es correcto.
- Falta declarar el propósito de cada salida antes o durante Descremado.
- La crema comercial no debe ingresar a Mantequilla por error.
- Una crema destinada a Mantequilla necesita liberación previa y saldo disponible.
- El precondensado despachado debe descargar físicamente el silo.
- La liberación intermedia para Envasado no debe confundirse con la liberación comercial del producto ya envasado.
- Los formatos de producto deben venir del maestro, no de constantes React.
Correctamente implementado
Conviene conservar y reutilizar:
- análisis de Recepción y silo;
- movimientos auditables de silo;
- vale y cálculo de Estandarización;
- rutas obligatorias y rollback si falta ruta;
- exclusión concurrente de equipos;
- estados que ocupan físicamente una máquina;
- CorridaCondensacion;
- CorridaDescremacion con dos salidas;
- CorridaSecado;
- CorridaMantequilla;
- EntradaProceso y SalidaProceso;
- análisis de silo separado de análisis de lote;
- LiberacionProceso;
- Calidad posterior a Secado;
- Calidad de mantequilla a granel;
- bloqueo de Envasado antes de la liberación intermedia;
- genealogía por lotes;
- pallets en cuarentena;
- existencias de producto terminado;
- despacho de pallets;
- estructura comercial de despacho a granel;
- carga diferida de pantallas y ausencia de polling continuo.
Qué debe reutilizarse
- SalidaProceso como material producido.
- LiberacionProceso como decisión de Calidad intermedia.
- Liberacion como liberación comercial final.
- MovimientoSilo como libro físico de líquidos.
- DetalleDespachoGranel como detalle comercial del despacho.
- RutaProducto y EtapaProceso, agregando selección y destinos estructurados.
- Componentes actuales de Descremado, Mantequilla, Secado, Calidad e Inventario.
Qué debe modificarse
- rutas de crema y Mantequilla;
- destino de cada salida de Descremado;
- ejecución física de despachos a granel;
- naturaleza de crema y precondensado;
- orden obligatorio Envasado → liberación final → Inventario;
- endpoint de lotes realmente envasables;
- formatos de Envasado configurables;
- identidad del producto en contratos de despacho;
- permisos por puesto;
- navegación por flujo de producto.
Qué eliminar o dejar solo por compatibilidad
No recomiendo eliminar registros históricos.
Sí debería dejarse solamente como compatibilidad:
- proceso universal flujo-lacteo, que ya está desactivado;
- creación genérica de ejecuciones cuando exista un servicio especializado;
- selección de torre como envasadora, después de verificar datos históricos;
- inferencia del destino mediante texto;
- filtros React que intentan determinar reglas de dominio;
- constantes de 25 kg como única alternativa.
Plan de implementación
CRÍTICO 1 — Destinos reales de Descremado
Proceso/producto: crema y leche descremada.
Backend: determinar cada destino según producto y ruta seleccionada; permitir crema → Mantequilla o crema → despacho.
Frontend: al iniciar o cerrar Descremado, mostrar el destino declarado de cada salida por separado.
Base de datos: agregar destino/ruta seleccionada de manera estructurada. Migrar registros existentes sin eliminarlos.
Calidad: mantener una liberación independiente por salida.
Inventario/Despacho: solamente mostrar crema cuyo destino sea despacho directo.
Pruebas: bifurcación, liberación independiente, crema a Mantequilla y crema a despacho.
CRÍTICO 2 — Movimiento físico del despacho a granel
Proceso/producto: precondensado y crema comercial.
Backend: al ejecutar el despacho, bloquear salida y silo, validar saldo y crear MovimientoSilo.SALIDA enlazado al despacho.
Frontend: mostrar estado borrador, autorizado y despachado; actualizar únicamente despacho y silo afectados.
Base de datos: relación trazable entre detalle de despacho y movimiento físico, más identificador idempotente.
Calidad: revalidar liberación al autorizar y al ejecutar.
Inventario/Despacho: impedir doble uso entre Producción y Despacho.
Pruebas: despacho parcial, total, simultáneo, doble clic, liberación revocada y saldo de silo.
ALTO 1 — Clasificación y elegibilidad de Envasado
Proceso/producto: todos.
Backend: corregir crema/precondensado a intermedio; crear endpoint de lotes envasables basado en salida, destino y Calidad.
Frontend: dejar de consultar todos los lotes terminados.
Base de datos: migración de datos, revisada por categoría y formato.
Calidad: conservar la puerta intermedia.
Inventario: no crear pallets para productos a granel.
Pruebas: precondensado y crema no aparecen; polvo y mantequilla liberados sí aparecen.
ALTO 2 — Formatos reales de Envasado
Proceso/producto: polvo 25 kg y mantequilla 20 kg.
Backend: validar formato contra el producto y equipos compatibles.
Frontend: calcular unidades y peso usando el formato recibido del backend.
Base de datos: probablemente no requiere modelo nuevo si Producto.formato basta; si hay múltiples formatos por producto, crear catálogo versionado.
Calidad: checklist y especificación según producto/formato.
Inventario: pallet siempre ≤ 500 kg.
Pruebas: polvo 20 × 25 kg; mantequilla 25 × 20 kg; formato incompatible rechazado.
ALTO 3 — Dos puertas de Calidad explícitas
Proceso/producto: polvo y mantequilla.
Backend: diferenciar claramente:
1. liberación del granel para Envasado;
2. liberación comercial del lote/pallet para Inventario.
Frontend: mostrar ambas como etapas distintas.
Base de datos: reutilizar LiberacionProceso y Liberacion; posiblemente solo agregar fase/condiciones, sin duplicar modelos.
Pruebas: no liberar comercialmente sin Envasado cuando el formato lo exige; pallet nuevo no queda huérfano después de una liberación anticipada.
MEDIO — Pantallas por proceso y producto
Reutilizar componentes actuales para presentar:
- Descremado;
- Evaporación/Precondensado;
- Secado;
- Mantequilla;
- Envasado;
- Despacho de granel.
Producción general queda como panel de seguimiento, no como puesto operacional universal.
BAJO — Compatibilidad y documentación
- actualizar auditorías desfasadas;
- documentar los cuatro flujos;
- etiquetar registros históricos sin ruta;
- retirar opciones legacy únicamente después de verificar que no tengan consumidores.
Migraciones actuales
Las migraciones locales están aplicadas hasta:
- Procesos 0016;
- Inventario 0024;
- Maestros 0032;
- Calidad 0006;
- Producción 0014.
La base tiene 16 rutas activas:
- polvo;
- precondensado;
- mantequilla.
No existen rutas activas para los dos productos de crema.
Pruebas verificadas
Ejecuté seis pruebas focalizadas:
- precondensado → Calidad → despacho;
- Calidad separada para crema y descremada;
- genealogía crema → mantequilla;
- Calidad de mantequilla;
- Secado → Calidad → Envasado;
- despacho a granel sin pallet.
Resultado: 5 pasaron y 1 falló.
La prueba de Descremado esperaba 400 al intentar consumir una salida sin liberar, pero actualmente recibe 403 porque el usuario de Condensación intenta escribir sobre una etapa de Secado. La protección de permisos es correcta; el test quedó desactualizado y debe usar un operador de Secado para comprobar después el bloqueo de Calidad.
No se modificó ningún archivo.


8:51 AM







Usa conjuntamente las skills: - `experto-procesos-lacteos` - `arquitecto-softwa…




Worked for 9m 49s



La revisión conjunta está terminada y no modifiqué código. La conclusión es clara: CCAA tiene una base industrial reutilizable, pero todavía no alcanza un “60 % productivo cerrado” porque cuatro puntos pueden romper el flujo físico o su trazabilidad:
1. Descremado no registra el destino independiente de crema y descremada.
2. El despacho comercial a granel no descuenta físicamente el silo.
3. Los silos/TK no tienen una reserva persistente durante procesos largos.
4. La liberación final puede adelantarse al Envasado.
Las auditorías anteriores siguen siendo útiles, pero algunas quedaron desactualizadas: las migraciones de rutas, ocupación, Calidad de lote y Secado ya están aplicadas en la base local, y Secado ya expone equipo_id, horas y estado de Calidad.
A. Mapa general definitivo
RECEPCIÓN
  → análisis inicial
  → decisión de Calidad
  → descarga
  → movimiento físico a silo
  → origen/FIFO conservado

SILO DE LECHE
  ├── ESTANDARIZACIÓN
  │     → leche estandarizada
  │     → Calidad
  │     → EVAPORACIÓN
  │           → precondensado
  │           → Calidad
  │           ├── despacho a granel
  │           └── SECADO
  │                 → polvo a granel
  │                 → Calidad
  │                 → ENVASADO
  │                 → liberación comercial
  │                 → INVENTARIO
  │
  └── DESCREMADO
        ├── leche descremada
        │     → TK leche descremada
        │     → Calidad
        │     → Estandarización
        │
        └── crema
              → TK crema
              → Calidad
              ├── despacho a granel
              └── MANTEQUILLA
                    → mantequilla a granel
                    → Calidad
                    → Envasado
                    → liberación comercial
                    → Inventario
Calidad no es una etapa física global: son puertas independientes sobre cada material. Mientras un material espera Calidad, el equipo que lo produjo puede quedar disponible.
B. Flujos por producto
Flujo	Secuencia definitiva	Estado actual
Leche en polvo	Recepción → Estandarización → Evaporación → Calidad precondensado → Secado → Calidad polvo → Envasado → liberación final → Inventario	Avanzado
Precondensado a despacho	Recepción → Estandarización → Evaporación → Calidad → despacho físico	Parcial: falta salida física del silo
Mantequilla	Recepción → Descremado → crema → Calidad → Mantequilla → Calidad granel → Envasado → liberación final → Inventario	Parcial: falta formato configurable y ruta completa desde crema
Crema a despacho	Recepción → Descremado → crema → Calidad → despacho físico	Incompleto
Descremada a Estandarización	Recepción → Descremado → descremada → Calidad → TK → Estandarización	Parcial: falta destino/ruta persistente


La clasificación correcta es:
- Leche recibida: materia prima.
- Leche descremada generada internamente: producto intermedio.
- Crema generada internamente: producto intermedio, aunque pueda venderse.
- Leche estandarizada: producto intermedio.
- Precondensado: producto intermedio, aunque su destino sea despacho.
- Polvo a granel: producto intermedio.
- Mantequilla a granel: producto intermedio.
- Polvo envasado y mantequilla en caja: producto final.
- Rework: categoría propia, siempre condicionado por Calidad.
Hoy crema y precondensado están clasificados como terminado; debe corregirse.
C. Procesos intermedios
Descremado
Lo existente está bien encaminado: CorridaDescremacion consume leche, genera dos movimientos físicos, dos lotes intermedios, dos SalidaProceso y conserva la atribución de origen.
Falta que cada salida declare por separado:
- producto;
- ruta seleccionada;
- destino;
- siguiente etapa.
La corrida especializada debería guardar el plan de ambas ramas y copiarlo a sus salidas al cerrar:
Crema → ruta mantequilla o despacho
Descremada → ruta estandarización
Deben conservarse los controles documentados: 1.395 RPM, MG descremada ≤ 0,1 % y crema comercial 42–43 %, todos configurables y versionados.
Estandarización
Debe mantenerse el vale actual y su ciclo:
calcular → transferir → agitar 30 min → muestrear
→ confirmar RC → corregir/reagitar si falla → liberar
La matemática actual es reutilizable. Deben mejorarse:
- conservar cada análisis y corrección, sin sobrescribir el anterior;
- doble responsabilidad: operador y analista;
- producto/ruta destino explícitos;
- vinculación con evaporador o destino posterior;
- crema como tercera entrada solamente cuando la receta vigente lo autorice.
El vale no es un producto terminado.
Evaporación
CorridaCondensacion ya conserva entrada, evaporador, silo destino, balance, precondensado y Calidad.
Debe quedar formada por:
leche estandarizada liberada
→ tratamiento térmico/uperización
→ PCC
→ evaporación
→ precondensado
→ Calidad
→ Secado o despacho
Los límites PCC encontrados son:
- Scheffers 2: temperatura mínima 81,2 °C y caudal máximo 17.100 kg/h.
- VEB: temperatura mínima 80 °C y caudal máximo 14.175 kg/h.
- No encontré un límite equivalente fiable para Scheffers 3.
No deben confundirse con las capacidades de planificación: Scheffers 2 15.900 L/h, Scheffers 3 11.000 L/h y VEB 12.400 L/h.
No encontré en el repositorio una fuente que asigne de manera inequívoca los valores 85/80/90 °C al TDC, ni el flujo de 18.000 L/h. El Excel disponible es un catálogo de documentos, no contiene esos formularios fuente. Por eso esos valores no deben cargarse todavía. Catalogo_Formatos_Procesos_CCAA.xlsx (Catálogo!A12:J52)
D. Concurrencia y recursos
Pueden ejecutarse simultáneamente Descremado, Estandarización, Evaporación, Secado y Mantequilla si utilizan recursos distintos.
La regla de equipos ya está correctamente centralizada:
- preparacion: reservado.
- ejecucion: ocupado.
- pausada: ocupado.
- bloqueada: ocupado.
- pendiente_control: físicamente disponible.
Falta aplicar una protección equivalente a almacenamiento:
- reservar silo/TK origen;
- reservar capacidad del destino;
- impedir consumir más cantidad que la disponible;
- impedir mezclar productos incompatibles;
- liberar la reserva al cerrar o cancelar;
- bloquear filas en orden estable para evitar deadlocks.
Recomiendo una entidad especializada ReservaSiloProceso, no un mega modelo universal. Para la primera etapa conviene asumir reserva exclusiva durante la transferencia; si en planta un silo puede alimentar dos líneas simultáneamente, esa excepción debe confirmarse antes.
E. Equipos y almacenamiento reales
La base local tiene:
Grupo	Maestro actual
Silos de recepción	8 silos de 120.000 L
TK crema	3 TK de 15.000 L
TK leche descremada	3 TK de 15.000 L
Evaporadores	Scheffers 2, Scheffers 3 y VEB
Torres	Egron 1 y Egron 2
Envasadoras	Rovema 3 y Rovema 4
Mantequilla	Línea de mantequilla
Otros	Carga de precondensado


Hay una discrepancia importante:
- Operación informa 4 TK de crema: aproximadamente 10.000 + 3 de 12.500.
- Operación informa 5 TK de leche fresca/descremada de aproximadamente 15.500.
- La base contiene 3 + 3, todos de 15.000.
Además, no existen como equipos maestros explícitos la descremadora, pasteurizador/TDC ni silos de polvo. No corresponde inventarlos: primero debe levantarse código, nombre y capacidad exactos. También conviene normalizar nombres como Silo, silo 2 y códigos con espacios inconsistentes.
F. Puertas de Calidad
Puerta	Qué bloquea
Recepción	Descarga y utilización de la leche
Salida descremada	Uso en Estandarización
Salida crema	Mantequilla o despacho
Estandarización	Alimentación a Evaporación
Precondensado	Secado o despacho
Polvo a granel	Envasado
Mantequilla a granel	Envasado
Producto envasado	Ingreso comercial a Inventario y despacho


Una ejecución física cerrada no significa material liberado. Deben mostrarse siempre tres estados separados:
Proceso: terminado
Equipo: disponible
Material: pendiente de Calidad
LiberacionProceso debe seguir controlando intermedios; Liberacion debe reservarse para la liberación comercial del producto ya envasado.
G. Backend actual vs. objetivo
Se conserva:
- RutaProducto y EtapaProceso;
- EjecucionProceso;
- EntradaProceso y SalidaProceso;
- corridas especializadas;
- LiberacionProceso;
- libro MovimientoSilo;
- FIFO y atribuciones;
- exclusión concurrente de equipos;
- Calidad de mantequilla y Secado;
- pallets e inventario terminado.
Cambios mínimos necesarios:
1. Agregar un destino final estructurado a RutaProducto; dejar destino textual solo para compatibilidad histórica.
2. Persistir la ruta usada en EjecucionProceso.
3. Agregar producto explícito y ruta de continuación a SalidaProceso.
4. Guardar rutas/destinos independientes de crema y descremada en CorridaDescremacion.
5. Permitir despacho_directo para crema cuando su ruta lo autorice.
6. Hacer que preparar_continuacion() resuelva desde la ruta de la salida, no solamente desde el proceso que la originó.
7. Al ejecutar un despacho a granel, crear MovimientoSilo.SALIDA, enlazarlo al detalle y usar una operación idempotente.
8. Crear reservas transaccionales de silos/TK.
9. Exponer una bandeja backend de “lotes envasables”; React no debe inferirlos por naturaleza.
10. Exigir Envasado cerrado antes de la liberación comercial final.
No debe agregarse empresa/sucursal como nueva dimensión funcional; se conserva únicamente el scope interno existente.
H. Frontend actual vs. objetivo
Se conservan:
- Recepción y Silos;
- Estandarización;
- Secado independiente;
- Envasado;
- Centro de Calidad;
- Inventario;
- componentes actuales de Descremado, Evaporación y Mantequilla.
Se reorganiza sin reescribir:
Producción
├── Panel operacional
├── Descremado
├── Evaporación
├── Mantequilla
└── Trazabilidad/Supervisión

Áreas independientes
├── Estandarización
├── Secado
├── Envasado
├── Calidad
├── Inventario
└── Despacho
Procesos.tsx debe dejar de ser el lugar donde se opera todo. Sus componentes se reutilizan en pantallas por puesto. La configuración de rutas y genealogía queda para supervisión/administración.
El panel general debe cargar solo un resumen:
- procesos activos;
- esperando Calidad;
- materiales listos;
- equipos ocupados;
- bloqueos;
- accesos permitidos por usuario.
Las tarjetas de silos ya son una buena base. Deben recibir desde Django las acciones permitidas. Hoy un TK puede mostrar acciones como “Estandarizar” o “Despachar” aunque no correspondan.
El detalle del silo/TK se carga al abrir e incluye movimientos recientes, producto, lote, Calidad, destino y siguiente acción. Sin polling continuo.
Envasado debe dejar de:
- realizar cuatro consultas iniciales;
- consultar todos los lotes “terminados”;
- fijar 25 kg;
- ofrecer torres como envasadoras.
Para el 60 % inicial se pueden reutilizar los formatos maestros existentes: saco_25kg y caja_20kg, con el máximo de 500 kg calculado por Django.
I. Trazabilidad definitiva
Cada transformación debe producir esta cadena:
Recepción/origen
→ MovimientoSilo de entrada
→ material/lote
→ ruta elegida
→ ejecución
→ corrida especializada
→ equipo
→ entradas consumidas
→ salidas generadas
→ movimientos físicos
→ análisis
→ liberación/rechazo
→ siguiente ejecución o destino final
En Descremado debe bifurcarse:
Corrida DSC-018
├── salida crema CR-018
│   → TKC2 → Calidad → ruta Mantequilla o despacho
└── salida descremada LD-018
    → TK02 → Calidad → ruta Estandarización
No basta con que ambas salidas apunten al mismo origen: cada una necesita identidad, cantidad, ubicación, Calidad y destino propios.
J. Plan definitivo de implementación
CRÍTICO
1. Auditar y confirmar maestros físicos: TK, capacidades, códigos y equipos faltantes.
2. Implementar rutas y destinos independientes de Descremado.
3. Ejecutar físicamente el despacho a granel con movimiento, bloqueo e idempotencia.
4. Reservar silos/TK durante operaciones concurrentes.
5. Exigir Envasado antes de liberación comercial final.
6. Corregir pruebas E2E y permisos del escenario Descremado → Calidad.
ALTO
7. Corregir naturaleza de crema y precondensado.
8. Crear bandeja backend de lotes realmente envasables.
9. Soportar polvo 25 kg y mantequilla 20 kg desde maestros.
10. Separar Descremado, Evaporación y Mantequilla en pantallas operacionales.
11. Crear panel resumido de Producción.
12. Configurar parámetros versionados de proceso/PCC/TDC.
13. Reducir permisos amplios del área Condensación a capacidades por puesto.
MEDIO
14. Solicitudes automáticas de muestra.
15. Historial completo de correcciones de RC.
16. Genealogía FIFO cuantificada.
17. Paros, rendimientos y pérdidas por corrida.
18. Mejorar tarjetas y detalle bajo demanda de silos/TK.
19. Alertas por permanencia, espera de Calidad y material bloqueado.
BAJO
20. Retirar gradualmente el flujo universal legado.
21. Normalizar nombres y códigos históricos.
22. Observabilidad de conflictos 409, reintentos y fallos de trazabilidad.
23. Documentar contratos finales y manuales por puesto.
Criterio para declarar cerrado el 60 %
Esta etapa podrá considerarse terminada cuando los cinco flujos E2E funcionen y se cumpla:
- ningún material sin producto, ubicación, cantidad, Calidad y destino;
- ninguna bifurcación sin ruta persistida;
- ningún despacho sin movimiento físico;
- ningún volumen reutilizable después de despacharse;
- ningún equipo o silo usado concurrentemente de forma incompatible;
- ningún producto final liberado antes de Envasado;
- cada puesto ve únicamente sus materiales, equipos y siguiente acción;
- Django decide las reglas y React solo las representa.
Fuentes principales contrastadas: [Flujo Fabrica.md](C:\\Users\\EQUIPO\\Documents\\GitHub\\CCAA\\Flujo Fabrica.md), [REGLAS_DE_PLANTA.md](C:\\Users\\EQUIPO\\Documents\\GitHub\\CCAA\\docs\\REGLAS_DE_PLANTA.md), [auditoría de cuatro flujos](C:\\Users\\EQUIPO\\Documents\\GitHub\\CCAA\\docs\\auditorias\\auditoria-cuatro-flujos-productivos.md), [modelos de procesos](C:\\Users\\EQUIPO\\Documents\\GitHub\\CCAA\\backend\\procesos\\models.py) y [servicios de procesos](C:\\Users\\EQUIPO\\Documents\\GitHub\\CCAA\\backend\\procesos\\servicios.py).
No se modificó código, base de datos ni documentación durante esta revisión.