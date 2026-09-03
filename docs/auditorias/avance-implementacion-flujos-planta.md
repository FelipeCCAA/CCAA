# Avance de implementacion de flujos de planta

Fecha: 2026-09-03

Este documento registra el estado real de la primera etapa productiva. No reemplaza las reglas de planta ni declara como confirmados datos fisicos que siguen pendientes.

## Bloque 1 - Maestros fisicos

### Problema

Los ocho silos de Recepcion existian con espacios y mayusculas inconsistentes. Las cantidades y capacidades informadas para TKC y TK de leche/descremada contradicen la base actual y no incluyen codigos fisicos confirmados.

### Cambio realizado

Se normalizaron de forma idempotente, preservando IDs, los codigos confirmados `Silo 1` a `Silo 8`. No se duplicaron silos. Se conservaron los equipos existentes.

### Base de datos

Migracion `maestros.0034_normalizar_codigos_silos_recepcion_confirmados` aplicada.

### Tests

Migracion aplicada correctamente y `makemigrations --check` sin cambios.

### Pendientes

No se agregaron un cuarto TKC ni dos TK de leche/descremada. Faltan codigos fisicos inequívocos y confirmacion de capacidades finales. Tampoco se creo descremadora ni TDC sin identificador confirmado.

## Bloque 2 - Destinos estructurados

### Problema

El cierre de una ruta interpretaba palabras como `despacho` o `inventario` desde texto libre.

### Cambio realizado

`RutaProducto` incorpora `destino_final` con valores estructurados: `siguiente_proceso`, `envasado`, `despacho_directo` e `inventario`. El texto anterior se conserva solo como descripcion historica.

### Backend

`destino_salida_de_ruta()` usa el valor estructurado y ya no busca palabras.

### Base de datos

Migracion `procesos.0017` con backfill demostrable desde los textos existentes.

### Tests

Prueba focalizada demuestra que el codigo estructurado manda aunque el texto diga otro destino.

## Bloque 3 - Persistencia de ruta

### Problema

La ruta se volvia a inferir y podia perderse al continuar una salida.

### Cambio realizado

Se agrego `ruta_producto` a `EjecucionProceso` y `SalidaProceso`, y `producto` explicito a la salida. Apertura de lote, evaporacion, mantequilla, secado/registro final y continuaciones propagan esos IDs.

### Base de datos

Backfill de ejecuciones enlazadas a lote cuando la coincidencia producto/proceso es unica y demostrable. Los historicos ambiguos permanecen nulos.

### Pendientes

Algunos historicos sin lote o con rutas antiguas no pueden reconstruirse automaticamente.

## Bloque 4 - Descremado con dos ramas

### Problema

Crema y leche descremada se generaban como dos salidas, pero ambas quedaban con destino pendiente y sin ruta elegida.

### Cambio realizado

`CorridaDescremacion` guarda por separado `ruta_descremada`, `ruta_crema`, `destino_descremada` y `destino_crema`. El cierre crea cada `SalidaProceso` con su propio producto, lote, silo/TK, ruta y destino.

### Frontend

El formulario muestra ruta de leche descremada y uso/ruta de crema. La creacion usa el endpoint atomico `crear-guiada`, evitando una ejecucion huerfana si falla la corrida.

### Tests

Alta guiada con rutas independientes aprobada.

## Bloque 5 - Calidad despues de Descremado

### Cambio realizado

Se conserva la liberacion independiente existente por `SalidaProceso`. La nueva ruta/destino tambien es independiente. La ejecucion fisica termina y `pendiente_control` no ocupa la descremadora.

### Tests

El cierre de dos salidas y herencia FIFO continua pasando. Existe una prueba antigua de permisos que espera 400 y recibe 403; no se altero el permiso para hacerla pasar artificialmente.

## Bloque 6 - Reserva de silos/TK

### Problema

Descremado verificaba saldo al iniciar, pero descontaba fisicamente al cerrar. Dos corridas podian comprometer la misma leche o el mismo TK durante esa ventana.

### Cambio realizado

El operador solicita una sugerencia calculada con balance de materia grasa y las especificaciones de silo vigentes de crema y descremada. La propuesta no es una orden automatica: puede ajustar los litros y debe confirmarlos explicitamente. Al iniciar se bloquean los tres silos/TK en orden de ID y se crean reservas de origen y capacidad de ambos destinos.

Las reservas impiden comprometer mas leche que el saldo, exceder capacidad, mezclar un producto incompatible o asignar un TK ya reservado. Al cerrar quedan consumidas con cantidad planificada y real; al cancelar se liberan. Todo ocurre dentro de transacciones, de modo que un fallo no deja reservas parciales.

### Backend

Nuevo modelo `ReservaSiloProceso` y endpoint `POST /api/procesos/descremaciones/sugerir-balance/`. La fuente del calculo se reconstruye en Django y guarda IDs/versiones de especificacion; React no puede falsificarla. Django rechaza como salida de descremado los SKU terminados en polvo: exige leche descremada intermedia, liquida y en litros, y crema intermedia.

### Frontend

El formulario incorpora `Calcular sugerencia`, permite ajustar los dos volumenes y exige confirmacion antes de `Confirmar reservas e iniciar`. Los catalogos se filtran con la misma clasificacion fisica del backend y muestran una advertencia explicita cuando faltan el intermedio liquido o su especificacion. Las tarjetas de silos/TK muestran la ejecucion y volumen reservado.

### Tests

Se verificaron sugerencia por especificaciones, confirmacion, tres reservas activas, consumo al cierre, liberacion al cancelar, falta de capacidad y exclusion de un segundo uso del TK.

### Pendientes

La base local todavia no contiene un producto intermedio de leche descremada liquida ni especificaciones de silo apropiadas para ambas ramas; no se inventaron valores maestros. Antes de operar este formulario deben configurarse con valores aprobados por planta.

### Integracion con Estandarizacion y Evaporacion

Estandarizacion ahora descuenta del saldo utilizable las reservas de origen de otras ejecuciones y rechaza cualquier destino reservado. No crea una reserva persistente propia porque la transferencia y los movimientos ocurren inmediatamente bajo los mismos bloqueos de filas: no existe una espera entre compromiso y movimiento.

Evaporacion si reserva al iniciar la capacidad del TK destino por el maximo conservador de litros de entrada. Al cerrar, la reserva queda consumida con el volumen real de precondensado; al cancelar la ejecucion se libera mediante la transicion comun. El inicio tambien respeta leche de origen ya comprometida y destinos reservados por Descremado u otra Evaporacion.

Se verificaron cuatro casos especificos: creacion de reserva al iniciar Evaporacion, consumo con cantidad real al cerrar, rechazo de un segundo uso del mismo TK y rechazo de una transferencia de Estandarizacion hacia un silo reservado.

## Bloque 7 - Estandarizacion

### Cambio realizado

Se conserva el vale y su matematica. La apertura productiva posterior ahora persiste la ruta elegida y mantiene el encadenamiento con el vale y el silo.

### Pendientes

No se modificaron recetas ni se habilito crema automaticamente sin una regla confirmada.

## Bloque 8 - Evaporacion y precondensado

### Cambio realizado

`CorridaCondensacion` se conserva. Su salida ahora guarda producto/ruta y decide Secado versus despacho por `destino_final`, no por texto libre.

## Bloque 9 - Despacho fisico a granel

### Problema

Un despacho podia quedar `despachado` sin descontar litros del libro fisico del silo/TK.

### Cambio realizado

Al ejecutar se bloquean despacho, detalles, salidas y silos; se revalida Calidad y saldo; se crea `MovimientoSilo.SALIDA`; y el movimiento queda enlazado al detalle mediante `movimiento_silo` y un `operacion_id` unico. El segundo intento devuelve el despacho ya ejecutado sin duplicar movimiento. Las continuaciones descuentan volumen ya comprometido en despachos autorizados.

### Tests

Despacho de 8.000 L crea exactamente un movimiento y el reintento no lo duplica.

## Bloque 10 - Secado

### Cambio realizado

Se conserva la corrida especializada y la separacion previa entre cierre fisico, equipo disponible y Calidad intermedia. No se mezclo con la liberacion comercial.

## Bloque 11 - Mantequilla

### Cambio realizado

La salida de mantequilla conserva producto y ruta. `opciones-alta` muestra solamente lotes de crema con una `LiberacionProceso` liberada; la crema pendiente ya no es seleccionable.

### Tests

Prueba focalizada de opciones de alta aprobada.

## Bloque 12 - Naturaleza de productos

### Cambio realizado

Migracion idempotente clasifica crema, precondensado, leche estandarizada, leche descremada liquida y formatos granel de polvo/mantequilla como intermedios. Saco de polvo de 25 kg y caja de mantequilla de 20 kg quedan terminados.

### Base de datos

Migracion `maestros.0033_clasificar_productos_por_etapa_fisica` aplicada.

## Bloque 13 - Lotes envasables

### Cambio realizado

Nuevo contrato `GET /api/produccion/envases/materiales-habilitados/`. Devuelve solo salidas con destino Envasado, Calidad intermedia liberada, saldo positivo y formato valido.

### Frontend

Envasado dejo de consultar dos listados generales de lotes y filtrar en React. Consume una sola bandeja especializada.

## Bloque 14 - Formatos de Envasado

### Cambio realizado

Se elimino el 25 kg fijo del formulario. El backend entrega y valida el formato del producto: saco 25 kg o caja 20 kg. React calcula unidades por peso y usa el maximo de pallet entregado por backend. La torre dejo de aparecer como envasadora.

### Tests

Contrato y registro de pallet focalizados aprobados; TypeScript y ESLint aprobados.

## Bloque 15 - Dos puertas de Calidad

### Cambio realizado

`LiberacionProceso` sigue habilitando material a granel para Envasado. `Liberacion` comercial ahora recibe un bloqueo si un producto con formato final no completo todos sus kg de Envasado.

### Tests

Prueba de dominio confirma que un producto pendiente de Envasado no se libera comercialmente.

## Bloques 16 y 17 - Frontend por puesto y silos

### Cambio realizado

En esta ejecucion se mejoraron los puestos de Descremado y Envasado, sus acciones explicitas y sus consultas acotadas. Las pantallas separadas de Secado, Calidad, Envasado, Inventario y Despacho existentes se conservaron.

Las tarjetas de silos/TK muestran reservas activas sin cargar trazabilidad completa por tarjeta. El detalle identifica ejecucion, tipo de reserva, producto y litros planificados.

### Pendientes

`Procesos.tsx` todavia mezcla supervision con operacion. Falta completar el detalle bajo demanda de cada silo/TK; no se expuso una accion sobre un saldo mezclado porque una tarjeta fisica puede contener mas de una salida trazable.

## Bloque 18 - Acciones permitidas por material en silo/TK

### Problema

La continuidad se calculaba dentro del proceso que genero la salida. Una rama persistida de Descremado hacia otro proceso podia mostrar o aceptar una etapa incorrecta. React ademas solo tenia una accion generica.

### Cambio realizado

El backend resuelve la etapa inmediata desde `SalidaProceso.ruta_producto`. Si la ruta cambia de proceso toma su primera etapa activa; si continua en el mismo, toma la inmediata posterior. `EntradaProceso` valida la misma regla y evita saltos. El contrato de salidas disponibles incluye `acciones_permitidas` con codigo y etiqueta operacional, e incluye materiales liberados para despacho directo.

### Frontend

La bandeja muestra `Enviar a Estandarizacion`, `Iniciar Mantequilla`, `Continuar a Secado` o `Preparar despacho` segun el contrato backend. Estandarizacion, Mantequilla y Despacho abren su puesto especializado; no se crea una corrida paralela desde React.

### Tests

Pruebas focalizadas verifican continuidad entre procesos mediante la ruta persistida y la accion de despacho directo despues de Calidad.

### Pendientes

La tarjeta fisica general no elige una accion unica cuando el silo contiene varias capas/salidas. Esa decision debe mostrarse por material trazable dentro del detalle bajo demanda, no inferirse desde el nombre o el saldo total.

## Bloque 19 - Panel general de Produccion

### Cambio realizado

Produccion muestra cinco indicadores: procesos activos, esperando Calidad, materiales listos, equipos ocupados y bloqueos. Los entrega un unico endpoint liviano; React no descarga ejecuciones, salidas, despachos y envases completos para contarlos.

### Backend

`GET /api/procesos/ejecuciones/resumen-operacional/` calcula estados desde `EjecucionProceso` y saldos disponibles por tipo de destino, descontando consumos, despachos comprometidos o kg ya envasados segun corresponda.

### Frontend

El resumen se carga una vez al entrar a Produccion, sin polling. Despues de cambiar un destino o preparar una continuacion se refrescan solo la bandeja afectada, la disponibilidad de equipos y este resumen. Se conservan los accesos por puesto y las bandejas especializadas.

### Tests

Prueba focalizada del contrato y sus cinco indicadores.

### Pendientes

La lista historica de lotes se conserva debajo del panel por compatibilidad operacional; no se traslado ni elimino.

## Bloque 20 - Procesos simultaneos

### Cambio realizado

Se conserva la exclusion concurrente de equipos por ID y los estados centralizados. Los cierres y despachos bloquean recursos en orden estable. Una prueba focalizada confirma que Estandarizacion, Descremado, Evaporacion, Mantequilla y Secado pueden quedar simultaneamente en preparacion cuando usan cinco equipos diferentes; el conflicto sobre un mismo equipo continua rechazado por las pruebas existentes.

Se agrego ademas una prueba transaccional con dos conexiones PostgreSQL y dos evaporadores distintos que intentan reservar simultaneamente el mismo TK de precondensado. El bloqueo de fila serializa la decision: exactamente una corrida inicia, queda una sola reserva activa y se registra un solo consumo; la segunda operacion es rechazada.

La colision entre modulos queda cubierta por las pruebas focalizadas que demuestran que Estandarizacion respeta una reserva ajena y que Evaporacion no puede duplicar una reserva concurrente. Descremado comparte la misma restriccion de base de datos para destinos activos.

## Bloque 21 - Permisos

### Cambio realizado

Se mantienen los permisos backend existentes para operaciones por etapa, Calidad y Envasado. No se habilito Mantencion.

### Pendientes

La separacion fina de Descremado/Evaporacion/Mantequilla requiere una matriz de roles confirmada antes de endurecer permisos historicos.

## Bloque 22 - Parametros TDC/PCC

### Pendientes

No se cargaron 85, 80, 90 grados ni 18.000 L/h. No existe correspondencia documental inequívoca por equipo. Se conservaron los PCC ya documentados sin inventar valores.

## Bloque 23 - E2E

### Cambio realizado

El circuito de leche en polvo quedo dividido segun los puestos reales, sin saltar
etapas desde un unico formulario:

- Recepcion y Estandarizacion hasta vale liberado;
- apertura de lote, Evaporacion y precondensado pendiente de Calidad;
- liberacion intermedia, Secado, Calidad de lote, Envasado, pallet, liberacion
  comercial y entrega a Bodega/Inventario.

El 3 de septiembre de 2026 se ejecuto la cadena por interfaz sobre el lote
`CCAA-EVA-058849`. Termino con el pallet `PAL-058849`, 20 sacos de 25 kg,
500 kg totales, estado disponible y ubicacion `PT-DISP` en Inventario.

El guion antiguo intentaba saltar desde Estandarizacion directamente a una
torre. Se corrigio para respetar la ruta que el backend ya imponia y para usar
la accion contractual `Continuar a Secado`. Los pasos aprobados pueden
reanudarse mediante variables de entorno para no repetir movimientos reales.

### Verificacion

- Recepcion y Estandarizacion: aprobadas por pantalla.
- Evaporacion y Calidad de precondensado: aprobadas por pantalla.
- Secado, Calidad de polvo, Envasado, liberacion final e Inventario: aprobados
  por pantalla.
- El circuito no produjo errores JavaScript ni reintentos automaticos de
  operaciones POST/PATCH.

### Pendientes

El E2E de leche en polvo y el de precondensado a despacho estan completos. Aun
faltan recorridos equivalentes para crema a despacho, mantequilla y la rama de
descremado destinada nuevamente a Estandarizacion.

## Bloque 24 - Precondensado a despacho directo

### Cambio realizado

El recorrido parametrizado comprobo por pantalla Recepcion, Estandarizacion,
Evaporacion, Calidad y Despacho para `Precondensado Entero NE Granel`. La salida
de 1.500 L fue liberada, incorporada a un despacho, autorizada y ejecutada sin
crear un pallet. El servicio genero el movimiento fisico de salida del silo.

El contrato `GET /api/inventario/despachos/granel-disponible/` ahora entrega de
forma aditiva `producto_id`, `producto_nombre`, `lote_codigo` y `silo_codigo`.
El selector y el historial de Inventario muestran esas identidades reales en
lugar de usar el nombre generico de la etapa.

### Permisos y pruebas

Se agrego una cuenta E2E del area Despacho con las capacidades explicitas de
crear y autorizar. Produccion conserva la consulta transversal administrativa,
mientras Despacho ejecuta solo su operacion. La prueba Playwright termino con
2 pruebas aprobadas y la prueba API focalizada del contrato tambien paso.

## Migraciones aplicadas

- `inventario.0025_detalledespachogranel_movimiento_silo_and_more`
- `maestros.0033_clasificar_productos_por_etapa_fisica`
- `maestros.0034_normalizar_codigos_silos_recepcion_confirmados`
- `maestros.0035_equipo_tipo_descremadora`
- `procesos.0017_corridadescremacion_destino_crema_and_more`
- `procesos.0018_rutas_crema_despacho_directo`
- `procesos.0019_reservas_silo_y_plan_descremacion`

## Estado de esta primera etapa

**PARCIALMENTE CERRADA.** Ya no existe despacho comercial a granel sin movimiento fisico, los destinos y rutas principales quedan estructurados, Descremado conserva dos ramas, reserva origen/destinos, Estandarizacion respeta compromisos ajenos, Evaporacion reserva su TK y Envasado consume un contrato seguro. El circuito completo de polvo y la exclusion concurrente sobre un mismo TK ya fueron comprobados. Quedan por validar por pantalla los otros cuatro circuitos y confirmar los maestros fisicos/PCC que la documentacion de planta no define de forma inequivoca.

## Bloque 25 - Preparacion operacional de Descremado

### Cambio realizado

Descremado ya no acepta cualquier equipo clasificado como `otro`: el maestro
incorpora el tipo explicito `descremadora`, y la migracion reclasifica de forma
compatible equipos antiguos cuyo codigo o nombre ya los identifica como tales.

El formulario obtiene en una sola consulta las etapas, descremadoras, TK,
productos intermedios, rutas y bloqueos aplicables. Dejo de descargar los
catalogos completos de equipos, productos, silos, etapas y rutas. Las rutas se
filtran por el ID del producto de cada rama y Django rechaza una ruta que
pertenezca a otro producto, evitando romper la identidad y trazabilidad de la
leche descremada o la crema.

### Estado real

La instalacion local no tiene una descremadora fisica ni un producto de leche
descremada liquida intermedia en litros. El sistema ahora lo informa como
bloqueo de configuracion y no ofrece equipos ajenos. No se inventaron codigo,
capacidad ni especificaciones; el E2E de esta rama queda pendiente hasta que se
confirmen esos maestros de planta.

## Bloque 26 - Maestros operacionales visibles

El formulario de maquinas dejo de mantener una lista fija de tipos y ahora
consume `equipo_tipo` desde Django. Desde la interfaz se pueden seleccionar
Descremadora, Torre, Envasadora y los demas tipos vigentes sin volver a editar
React cuando cambie el catalogo.

Tambien se expuso y agrego al formulario la regla existente
`consume_materiales`. Maestros muestra por equipo si descuenta leche y si
consume envases; una descremadora debe conservar ambas reglas desactivadas.
Esto permite configurar el maestro faltante desde pantalla sin escribirlo
directamente en la base de datos.

## Bloque 27 - Preparacion visible de Mantequilla

El contrato de opciones de Mantequilla separa ahora la crema liberada y
utilizable de la crema que aun espera una decision de Calidad. La pantalla
muestra por separado la ausencia de OP, la falta real de crema, los lotes sin
control generado, pendientes o rechazados y la ocupacion de la linea informada
por Django.

Los lotes pendientes no ingresan al selector operativo. La vista no libera ni
infiere estados: Calidad sigue siendo la unica autoridad para habilitar el
consumo de crema en una corrida de mantequilla.

La auditoria de los datos locales encontro dos lotes historicos de crema cuya
salida fue registrada desde una etapa de Envasado y sin control intermedio. No
se generaron decisiones de Calidad retroactivas: la pantalla los identifica
como `trazabilidad_incompleta` y muestra su etapa de origen. Los casos realmente
pendientes enlazan a Calidad y la ausencia de OP enlaza a Planificacion.

## Bloque 28 - Alta visual de rutas productivas

Administracion puede crear desde la seccion de rutas la relacion entre un
producto y una secuencia de proceso existente, indicando prioridad y destino
final. El formulario muestra las etapas antes de confirmar y se carga solo al
abrirse. Produccion conserva la consulta de rutas pero no recibe permisos de
configuracion.

El catalogo de procesos ahora incluye aditivamente sus etapas; la vista ya las
prefijaba en Django y no genera consultas por fila. Con esto la ruta faltante
de leche descremada intermedia puede configurarse desde React una vez creado
el producto real, sin usar Django Admin ni codificar la secuencia en frontend.

## Bloque 29 - Especificaciones previas al calculo de Descremado

El endpoint de preparacion de Descremado informa ahora, para cada producto de
leche descremada y crema, si existe una especificacion de analisis de silo
vigente. La vigencia se resuelve en Django para todos los productos en una
consulta adicional y React no intenta reconstruir la regla.

El formulario muestra el producto exacto que necesita configuracion y bloquea
el calculo de la sugerencia antes de enviar un POST que Django rechazaria. El
operador conserva la responsabilidad de revisar y confirmar la receta sugerida;
esta mejora solamente anticipa un faltante de Calidad.

Maestros acepta `?seccion=especificaciones`, por lo que el aviso lleva directo
a la pestaña existente sin cargar previamente las otras secciones.

## Bloque 30 - Idempotencia desde Envasado

React genera una clave `operacion_id` al abrir el formulario y la envia en el
alta de Envasado. Si la respuesta se pierde, un reenvio conserva la misma clave
y Django devuelve el registro existente sin volver a crear pallets ni entradas
de Inventario. La clave cambia solamente despues de confirmar el alta, para que
el siguiente pallet sea una operacion fisica distinta.

## Bloque 31 - Material trazable por silo/TK bajo demanda

Al abrir una tarjeta de silo o TK, React consulta solamente las salidas
intermedias liberadas de esa unidad. El endpoint existente acepta el filtro
`silo` y conserva en Django el calculo de saldo, Calidad, destino y siguiente
etapa. La pantalla muestra lote, producto, corrida, cantidad disponible y la
siguiente accion contractual sin descargar todos los materiales de planta.

Las respuestas obsoletas se descartan cuando el operador cambia rapidamente
de tarjeta. No se agrego polling ni una segunda fuente de saldos en React.

## Bloque 32 - Genealogia FIFO cuantificada

La linea completa del lote usa ahora las atribuciones FIFO persistidas en cada
salida de silo y muestra cuantos litros de cada recepcion fueron realmente
consumidos. Los movimientos historicos sin atribucion conservan el fallback
temporal, pero se etiquetan explicitamente como `inferidos`.

React diferencia `Confirmado FIFO` de `Inferido`; ya no presenta todas las
recepciones anteriores como si tuvieran el mismo nivel de certeza.

## Bloque 33 - Consumo de materiales por etapa física

Las recetas distinguen ahora componentes de `proceso` y de `envasado`. El
cierre productivo descuenta solamente los insumos de proceso; sacos, cajas y
pallets se descuentan cuando Envasado registra físicamente cada pallet, usando
la misma `operacion_id` idempotente del registro.

Un lote puede tener un consumo de proceso y varias operaciones parciales de
Envasado. Los consumos anteriores a este cambio quedan marcados como
`completo_legacy`, porque ya descontaron la receta completa y no deben volver
a consumir envases. La migración clasifica como Envasado los componentes
existentes cuyo insumo pertenece a la categoría `empaque`.

La ficha React diferencia el material de proceso del material de Envasado y
muestra cuántas operaciones y kilos envasados ya descontaron materiales. El
MRP conserva la explosión completa de la receta; el filtro por etapa se aplica
solo al consumo físico.

Migraciones aplicadas localmente:

- `inventario.0026_consumoloteproduccion_fase_and_more`
- `maestros.0036_recetacomponente_fase`

Verificación directa: simulación de un pallet de 500 kg confirmó que el cierre
de proceso no descuenta 20 sacos ni una base pallet y que el registro de
Envasado sí los descuenta una única vez.

## Bloque 34 - Recetas versionadas visibles en React

Calidad y Administración pueden consultar las recetas y crear una nueva
versión desde `Maestros > Recetas`. Cada componente identifica si es producto
o insumo, su cantidad, unidad, merma y el momento físico de consumo: Proceso o
Envasado. La pantalla explica el efecto antes de guardar y no permite editar
silenciosamente una versión histórica.

El endpoint `GET/POST /api/maestros/recetas/` carga producto y componentes con
precarga, aplica scope organizacional y conserva el permiso de Calidad como
autoridad sobre la fórmula aprobada. El alta completa es transaccional: no
puede quedar una receta de cabecera sin sus componentes si una fila falla.

La pestaña se carga solo al abrirla y comparte productos/catálogos ya cargados;
no agrega consultas al resto de Maestros ni a los puestos operacionales.

## Bloque 35 - Referencias provisionales operables para Descremado

Se agregó el comando idempotente `preparar_circuito_descremado`, que primero
permite una vista previa y solo escribe con `--aplicar`. El comando crea la
descremadora DES-01 con capacidad vigente de referencia de 15.000 L/h, el
producto intermedio leche descremada líquida, su especificación de silo y su
ruta hacia Estandarización, Evaporación, Secado y Envasado.

Las cremas intermedias activas reciben una especificación provisional y una
alternativa de ruta hacia Mantequilla, Calidad y Envasado. Las rutas de
despacho directo ya existentes se conservan. Así, el operador puede elegir el
destino real de la crema sin que React lo deduzca ni cree procesos paralelos.

Los valores no se presentan como parámetros certificados de CCAA. La capacidad
se basa en la referencia publicada para GEA CleanSkimmer 100; la grasa residual
de leche descremada se basa en el rango 0,04-0,07% descrito por Tetra Pak. El
objetivo de crema se centra en el 42% que ya declaran los maestros locales. La
fuente y la advertencia de validación quedan guardadas en los maestros.

El comando utiliza `get_or_create`: una repetición no duplica filas ni
sobrescribe cambios posteriores aprobados por Calidad o Producción. En la base
local quedaron una descremadora, una leche descremada con ruta de polvo, dos
rutas de crema hacia Mantequilla y cuatro especificaciones de silo para
intermedios.

### Verificación por interfaz

Playwright ejecutó una corrida real `DES-E2E-65428565`: tomó 1.000 L de Silo 3,
el operador confirmó la sugerencia de 939,09 L de leche descremada y 60,91 L de
crema, se reservaron Tk02 y TkC2, se cerró la descremadora y Calidad analizó y
liberó las dos ramas por separado. La comprobación final mostró `Enviar a
Estandarización` para Tk02 e `Iniciar Mantequilla` para TkC2.

Durante el desarrollo del guion aparecieron bloqueos 409 por sesión única de
las cuentas E2E. Fueron controles de seguridad esperados, no fallos del proceso;
el guion reutiliza ahora la sesión del área y no abre una sesión administrativa
paralela.

## Bloque 36 - Preparación y validación de Mantequilla

La crema liberada por el E2E de Descremado ya aparece como insumo de
Mantequilla. Se corrigió el selector de coproducto: antes buscaba suero dentro
de los lotes de crema y por definición siempre quedaba vacío; ahora ofrece
solamente lotes de suero/mazada aún no usados.

El comando `preparar_circuito_mantequilla --aplicar` dejó una OP local de 40
kg, una especificación de lote v2 y un lote trazable para mazada. Los rangos
provisionales usan las claves fisicoquímicas reales del sistema: materia grasa
(`mg`) mínima 80%, humedad máxima 16% y sólidos no grasos máximos 2%, basados
en Codex CXS 279-1971. Calidad debe reemplazarlos si la ficha aprobada de CCAA
es más estricta.

La corrida `MANT-E2E-66249302` consumió 60 kg del lote de crema
`INT-DES-2-CR` y registró 31 kg de mantequilla, 28 kg de mazada y 1 kg de
merma. Calidad registró el análisis de lote conforme y liberó la salida para
Envasado. El cierre actualiza ahora también cantidad y estado del lote de
mazada; la migración `procesos.0020_reparar_lotes_suero_mantequilla` reparó los
registros anteriores que ya tenían un balance de coproducto demostrable.
