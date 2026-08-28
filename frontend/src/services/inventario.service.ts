import api from "./api";

export interface Insumo {
  id: number; codigo: string; nombre: string; area: string; area_etiqueta: string;
  unidad: string; contenido_envase: string;
  /* Los tres se calculan desde el libro de existencias; no hay un saldo
     guardado en el material. Un número al lado, editable y sin movimiento que
     lo respalde, se desincroniza y además parece autorizado. */
  stock_fisico: number; stock_disponible: number; stock_bloqueado: number;
  eoq: string | null; punto_reposicion: string;
  categoria: string; requiere_lote: boolean; requiere_vencimiento: boolean; requiere_calidad: boolean;
}

/*
  Dónde vive el material.

  El `tipo` no es una etiqueta: `registrar_entrada` manda a **cuarentena** lo
  que requiere Calidad y a **disponible** lo que no, y rechaza la entrada si
  no coincide. Una bodega sin ubicación de cuarentena no puede recibir nada
  que pase por Calidad.
*/
export interface UbicacionInventario {
  id: number;
  codigo: string;
  bodega: number;
  bodega_nombre: string;
  tipo: "disponible" | "cuarentena" | "rechazado" | "produccion";
  tipo_etiqueta: string;
  descripcion: string;
  activo: boolean;
}

export interface Existencia {
  id: number; lote: number; lote_codigo: string; insumo_nombre: string;
  ubicacion_codigo: string; estado_calidad: string; cantidad_fisica: string;
  cantidad_reservada: string; cantidad_disponible: string;
}

export interface InspeccionMaterial {
  id: number; lote: number; lote_codigo: string; insumo_nombre: string;
  estado: string; prioridad: number; observaciones: string; creada_en: string;
}

export interface SolicitudMaterial {
  id: number; numero: string; area: string; estado: string; fecha_requerida: string;
  prioridad: number; detalles: Array<{ id: number; insumo_nombre: string; cantidad_solicitada: string; cantidad_entregada: string }>;
}

/*
  Una línea de orden de compra.

  Trae **qué exige el material al recibirlo**. `recibir_detalle_compra` rechaza
  la recepción si falta el lote, el vencimiento, la temperatura o el
  certificado que el material declara; descubrirlo al enviar el formulario
  obliga a rehacerlo con el camión esperando en el andén.
*/
export interface DetalleOrdenCompra {
  id: number;
  insumo: number;
  insumo_nombre: string;
  insumo_unidad: string;
  cantidad: string;
  cantidad_recibida: string;
  costo_unitario: string;
  requiere_lote: boolean;
  requiere_vencimiento: boolean;
  requiere_temperatura: boolean;
  requiere_certificado: boolean;
  requiere_calidad: boolean;
}


export interface OrdenCompra {
  id: number;
  numero: string;
  proveedor: number;
  proveedor_nombre: string;
  bodega_entrega: number;
  estado: string;
  fecha_comprometida: string | null;
  detalles: DetalleOrdenCompra[];
}


export interface RecepcionCompra {
  id: number;
  orden: number;
  guia: string;
  factura: string;
  recibida_en: string;
  observaciones: string;
}

/*
  Solicitud de compra: lo que se pide antes de que exista una orden.

  Pasa por `borrador → pendiente → aprobada → convertida`. La aprobación la da
  alguien distinto del solicitante —el backend rechaza que sean el mismo— y
  «convertida» significa que ya se emitieron sus órdenes.
*/
export interface SolicitudCompra {
  id: number;
  numero: string;
  area: string;
  solicitante: number;
  motivo: string;
  estado: string;
  creada_en: string;
}


export interface DetalleSolicitudCompra {
  id: number;
  solicitud: number;
  insumo: number;
  insumo_nombre: string;
  cantidad: string;
  fecha_requerida: string;
  /* Cierto si la línea salió del cálculo del MRP en vez de escribirse a
     mano. Es lo que se pregunta después de un quiebre. */
  origen_mrp: boolean;
}


export interface Proveedor {
  id: number;
  rut: string;
  nombre: string;
  email: string;
  telefono: string;
  activo: boolean;
}


/*
  Condiciones de compra de un material con un proveedor.

  No son datos de referencia: **entran en un cálculo que el sistema presenta
  como autoritativo**. El MRP sube la cantidad sugerida al mínimo, la redondea
  al múltiplo y resta el plazo para decir cuándo emitir la orden. Unas
  condiciones desactualizadas no se ven distintas de unas al día — producen
  cifras que parecen correctas.

  Solo puede haber **un principal por material**: es el que el MRP consulta y
  a quien se le emite la orden.
*/
export interface InsumoProveedor {
  id: number;
  insumo: number;
  insumo_nombre: string;
  insumo_codigo: string;
  insumo_unidad: string;
  proveedor: number;
  proveedor_nombre: string;
  principal: boolean;
  codigo_proveedor: string;
  costo_unitario: string;
  compra_minima: string;
  multiplo_compra: string;
  lead_time_dias: number;
}


export interface Bodega {
  id: number;
  codigo: string;
  nombre: string;
  activo: boolean;
}


export interface Notificacion {
  id: number; tipo: string; titulo: string; mensaje: string; leida_en: string | null; creada_en: string;
}

export interface MovimientoInventario {
  id: number; tipo: string; lote: number; lote_codigo: string; insumo_nombre: string;
  cantidad: string; origen_codigo: string | null; destino_codigo: string | null;
  motivo: string; fecha: string;
  /* El saldo antes y después. Es lo que hace auditable el libro: la cifra de
     existencias se reconstruye recorriendo los movimientos, en vez de haber
     que creerle a un número guardado. */
  saldo_anterior: string; saldo_posterior: string;
  /* Qué lo originó: «produccion.Lote», «inventario.SalidaManual»… */
  documento_tipo: string; documento_id: number;
}

export interface AjusteInventario {
  id: number; existencia: number; tipo: "positivo" | "negativo" | "merma";
  cantidad: string; motivo: string; estado: string; solicitante: number; aprobador: number | null;
}

export interface ResultadoMRP {
  kilos_producir: string;
  materiales: Array<{ insumo: string; unidad: string; requerido: string; stock: string; faltante: string; envases_a_pedir: number; eoq: string | null }>;
  /* Falso cuando la explosión no llegó hasta el final —un intermedio sin
     receta, un ciclo—. La lista está incompleta y hay que decirlo: con ella
     se emite una orden de compra corta. */
  receta_completa: boolean;
}


/*
  Alerta vigente del inventario.

  Las calcula el backend en cada operación de stock (stock mínimo, punto de
  reposición, próximo a vencer, cuarentena atrasada) y **no se cierran a
  mano**: se apagan arreglando lo que las causó. Poder marcarlas como vistas
  dejaría el panel limpio con el problema intacto.
*/
export interface Alerta {
  id: number;
  tipo: string;
  severidad: "info" | "advertencia" | "critica";
  severidad_etiqueta: string;
  insumo: number | null;
  insumo_nombre: string | null;
  insumo_codigo: string | null;
  lote: number | null;
  lote_codigo: string | null;
  mensaje: string;
  activa: boolean;
  creada_en: string;
}


/*
  Una línea del MRP semanal: qué falta de un material y para cuándo.

  La cadena de la resta está entera —bruta, disponible, ya pedido, neta— y no
  solo el resultado, porque un número de compra que no se puede reconstruir no
  se firma. `explicacion` trae además la fórmula y, si hay proveedor
  principal, su mínimo y su múltiplo de compra: son los que hacen que la
  cantidad sugerida no coincida con la neta.
*/
export interface ResultadoMRPSemanal {
  id: number;
  insumo: number;
  insumo_nombre: string;
  fecha_requerida: string;
  necesidad_bruta: string;
  disponible_proyectado: string;
  recepciones_programadas: string;
  necesidad_neta: string;
  compra_sugerida: string;
  /* Cuándo hay que emitir la orden para que llegue a tiempo: la fecha
     requerida menos el plazo de reposición del proveedor. */
  fecha_sugerida_orden: string;
  explicacion: Record<string, string>;
}


export interface EjecucionMRP {
  id: number;
  creada_en: string;
  fecha_corte: string;
  horizonte_hasta: string;
  parametros: Record<string, unknown>;
  resultados: ResultadoMRPSemanal[];
  /* El cálculo ya no ocurre dentro de la petición: ocupaba un worker de
     principio a fin. La ejecución llega en cola y hay que preguntar cómo va. */
  estado: "pendiente" | "en_curso" | "terminada" | "fallida";
  estado_etiqueta: string;
  /* Lo dice el backend y no se deduce de la lista de estados: deducirlo aquí
     obligaría a mantener esa lista en dos sitios. */
  terminada: boolean;
  error: string;
}

export async function obtenerInsumos(): Promise<Insumo[]> {
  const { data } = await api.get<Insumo[] | { results: Insumo[] }>("inventario/insumos/");
  return Array.isArray(data) ? data : data.results;
}

export async function calcularMRP(producto: number, kilos_producir: number): Promise<ResultadoMRP> {
  const { data } = await api.post<ResultadoMRP>("inventario/mrp/", { producto, kilos_producir });
  return data;
}

async function lista<T>(ruta: string): Promise<T[]> {
  const { data } = await api.get<T[] | { results: T[] }>(ruta);
  return Array.isArray(data) ? data : data.results;
}

export const obtenerExistencias = () => lista<Existencia>("inventario/existencias/");
export const obtenerInspecciones = () => lista<InspeccionMaterial>("inventario/inspecciones/");
export const obtenerMRQ = () => lista<SolicitudMaterial>("inventario/mrq/");
export const obtenerOrdenesCompra = () => lista<OrdenCompra>("inventario/ordenes-compra/");
export const obtenerNotificaciones = () => lista<Notificacion>("inventario/notificaciones/");
export const obtenerMovimientos = () => lista<MovimientoInventario>("inventario/movimientos/");
export const obtenerAjustes = () => lista<AjusteInventario>("inventario/ajustes/");
export const obtenerUbicaciones = () => lista<UbicacionInventario>("inventario/ubicaciones/");
export const obtenerAlertas = () => lista<Alerta>("inventario/alertas/");

export interface ExistenciaProductoTerminado {
  id: number; pallet: number; pallet_codigo: string; lote_codigo: string;
  producto_nombre: string; ubicacion: number; ubicacion_codigo: string;
  ubicacion_tipo: "disponible" | "cuarentena" | "rechazado" | "produccion";
  kg_neto: string; activo: boolean; actualizado_en: string;
  estado_inventario: "cuarentena" | "disponible" | "bloqueado" | "despachado" | "anulado";
  kg_disponible: string | number;
}

export interface EstadoOperacionalInventario {
  stock: {
    fisico_kg: string | number; disponible_kg: string | number;
    cuarentena_kg: string | number; bloqueado_kg: string | number; pallets: number;
  };
  actualizado_en: string;
}

export interface MovimientoProductoTerminado {
  id: number; pallet: number; pallet_codigo: string;
  tipo: "ingreso" | "transferencia" | "despacho";
  origen: number | null; destino: number | null; motivo: string;
  registrado_por: number; registrado_en: string;
}

export async function obtenerEstadoOperacionalInventario(refrescar = false) {
  const { data } = await api.get<EstadoOperacionalInventario>(
    "inventario/estado-operacional/",
    refrescar ? { params: { actualizado: Date.now() } } : undefined,
  );
  return data;
}

export const obtenerMovimientosProductoTerminado = () =>
  lista<MovimientoProductoTerminado>("inventario/movimientos-producto-terminado/");

export interface ClienteDespacho {
  id: number; codigo: string; nombre: string; rut: string; direccion: string; activo: boolean;
}

export interface DetalleDespacho {
  id: number; pallet: number; pallet_codigo: string; lote_codigo: string; kg_neto: string;
}

export interface Despacho {
  id: number; numero: string; cliente: number; cliente_nombre: string;
  estado: "borrador" | "autorizado" | "despachado" | "cancelado";
  guia_despacho: string; transportista: string; patente: string;
  creado_en: string; autorizado_en: string | null; despachado_en: string | null;
  detalles: DetalleDespacho[];
}

export const obtenerProductoTerminado = () =>
  lista<ExistenciaProductoTerminado>("inventario/producto-terminado/");
export const obtenerClientesDespacho = () =>
  lista<ClienteDespacho>("inventario/clientes-despacho/");
export const obtenerDespachos = () => lista<Despacho>("inventario/despachos/");

export async function ingresarPallet(pallet: number, ubicacion: number) {
  const { data } = await api.post<ExistenciaProductoTerminado>(
    "inventario/producto-terminado/ingresar/", { pallet, ubicacion },
  );
  return data;
}

export async function transferirPallet(id: number, destino: number, motivo: string) {
  const { data } = await api.post<ExistenciaProductoTerminado>(
    `inventario/producto-terminado/${id}/transferir/`, { destino, motivo },
  );
  return data;
}

export async function crearDespacho(datos: {
  numero: string; cliente: number; pallet_ids: number[]; guia_despacho?: string;
  transportista?: string; patente?: string; observacion?: string;
}) {
  const { data } = await api.post<Despacho>("inventario/despachos/", datos);
  return data;
}

export async function autorizarDespacho(id: number) {
  const { data } = await api.post<Despacho>(`inventario/despachos/${id}/autorizar/`);
  return data;
}

export async function ejecutarDespacho(id: number) {
  const { data } = await api.post<Despacho>(`inventario/despachos/${id}/ejecutar/`);
  return data;
}


/*
  Un lote de proveedor: la unidad de trazabilidad de bodega.

  `utilizable` es lo que decide si puede salir —aprobado por Calidad, vigente
  y no vencido— y lo calcula el backend. Repetir esa condición en el cliente
  daría una segunda definición de «se puede usar», libre de discrepar con la
  que el servicio aplica al descontar.
*/
export interface LoteInventario {
  id: number;
  codigo: string;
  insumo: number;
  insumo_nombre: string;
  insumo_codigo: string;
  insumo_unidad: string;
  proveedor: number | null;
  proveedor_nombre: string | null;
  elaboracion: string | null;
  vencimiento: string | null;
  estado_calidad: string;
  estado_etiqueta: string;
  recibido_en: string;
  activo: boolean;
  vencido: boolean;
  utilizable: boolean;
}


export const obtenerLotesInventario = () =>
  lista<LoteInventario>("inventario/lotes/");

export async function obtenerLoteInventario(id: number): Promise<LoteInventario> {
  const { data } = await api.get<LoteInventario>(`inventario/lotes/${id}/`);

  return data;
}

/* Acotados al lote. El backend filtra: los listados van paginados, así que
   descartar en el cliente dejaría fuera lo que no vino en la primera página. */
export const obtenerExistenciasDeLote = (lote: number) =>
  lista<Existencia>(`inventario/existencias/?lote=${lote}`);

export const obtenerMovimientosDeLote = (lote: number) =>
  lista<MovimientoInventario>(`inventario/movimientos/?lote=${lote}`);
export const obtenerEjecucionesMRP = () => lista<EjecucionMRP>("inventario/ejecuciones-mrp/");
export const obtenerSolicitudesCompra = () =>
  lista<SolicitudCompra>("inventario/solicitudes-compra/");
export const obtenerDetallesSolicitudCompra = () =>
  lista<DetalleSolicitudCompra>("inventario/detalles-solicitud-compra/");
export const obtenerBodegas = () => lista<Bodega>("inventario/bodegas/");


/*
  Opciones de los desplegables del módulo.

  Vienen del backend y no se escriben aquí: una copia en el cliente ofrece
  tarde o temprano un valor que el servidor rechaza. Pasó — la pantalla de
  bodegas llevaba la lista de áreas a mano y se quedó sin «despacho» ni
  «mantenimiento» en cuanto el maestro las incorporó.
*/
export interface CatalogosInventario {
  area: { valor: string; etiqueta: string }[];
  tipo_ubicacion: { valor: string; etiqueta: string }[];
  categoria_insumo: { valor: string; etiqueta: string }[];
  unidad_insumo: { valor: string; etiqueta: string }[];
}


export async function obtenerCatalogosInventario(): Promise<CatalogosInventario> {
  const { data } = await api.get<CatalogosInventario>("inventario/catalogos/");

  return data;
}


export const obtenerRecepcionesCompra = () =>
  lista<RecepcionCompra>("inventario/recepciones-compra/");


/* La orden pasa de borrador a enviada: hasta entonces no compromete a nadie y
   el MRP no la cuenta como recepción programada. */
export async function enviarOrdenCompra(id: number): Promise<OrdenCompra> {
  const { data } = await api.post<OrdenCompra>(
    `inventario/ordenes-compra/${id}/enviar/`,
    {},
  );

  return data;
}


/* La cabecera del documento del proveedor: guía y factura. Las líneas se
   reciben una por una contra su renglón de la orden. */
export async function crearRecepcionCompra(datos: {
  orden: number;
  guia: string;
  factura?: string;
  observaciones?: string;
}): Promise<RecepcionCompra> {
  const { data } = await api.post<RecepcionCompra>(
    "inventario/recepciones-compra/",
    datos,
  );

  return data;
}


/*
  Recibe una línea. Crea el lote de proveedor, lo manda a cuarentena si el
  material pasa por Calidad —y abre su inspección—, registra la entrada y
  suma a lo recibido de la orden.

  Rechaza si supera lo pendiente, si falta un dato que el material exige, o si
  la ubicación no corresponde al tipo que su liberación necesita.
*/
export async function recibirLineaCompra(
  recepcion: number,
  datos: Record<string, unknown>,
): Promise<{ detalle: number; lote: number }> {
  const { data } = await api.post<{ detalle: number; lote: number }>(
    `inventario/recepciones-compra/${recepcion}/recibir/`,
    datos,
  );

  return data;
}


export const obtenerProveedores = () => lista<Proveedor>("inventario/proveedores/");
export const obtenerInsumoProveedores = () =>
  lista<InsumoProveedor>("inventario/insumo-proveedores/");


export async function crearProveedor(datos: {
  rut: string;
  nombre: string;
  email?: string;
  telefono?: string;
}): Promise<Proveedor> {
  const { data } = await api.post<Proveedor>("inventario/proveedores/", datos);

  return data;
}


export async function guardarCondiciones(
  id: number | null,
  datos: Record<string, unknown>,
): Promise<InsumoProveedor> {

  const { data } = id
    ? await api.patch<InsumoProveedor>(`inventario/insumo-proveedores/${id}/`, datos)
    : await api.post<InsumoProveedor>("inventario/insumo-proveedores/", datos);

  return data;
}


export async function crearBodega(datos: {
  codigo: string;
  nombre: string;
  area: string;
}): Promise<Bodega> {
  const { data } = await api.post<Bodega>("inventario/bodegas/", datos);

  return data;
}


export async function crearUbicacion(datos: {
  bodega: number;
  codigo: string;
  tipo: string;
  descripcion?: string;
}): Promise<UbicacionInventario> {
  const { data } = await api.post<UbicacionInventario>(
    "inventario/ubicaciones/",
    datos,
  );

  return data;
}


/*
  Pasa lo que el MRP dice que falta a una solicitud de compra.

  Cierra el circuito: hasta aquí el cálculo terminaba en la pantalla y alguien
  volvía a teclear las cantidades. Responde 409 si esa ejecución ya generó su
  solicitud — duplicar la compra es peor que fallar, porque la segunda orden
  llega igual y hay que devolverla.
*/
export async function solicitarCompraDesdeMRP(
  ejecucion: number,
): Promise<SolicitudCompra> {
  const { data } = await api.post<SolicitudCompra>(
    `inventario/ejecuciones-mrp/${ejecucion}/solicitar-compra/`,
    {},
  );

  return data;
}


export async function enviarSolicitudCompra(id: number): Promise<SolicitudCompra> {
  const { data } = await api.post<SolicitudCompra>(
    `inventario/solicitudes-compra/${id}/enviar/`,
    {},
  );

  return data;
}


/* La decide alguien distinto del solicitante: el backend lo exige y por eso
   la pantalla no ofrece el botón a quien la creó. */
export async function decidirSolicitudCompra(
  id: number,
  decision: "aprobada" | "rechazada",
  comentario = "",
): Promise<SolicitudCompra> {
  const { data } = await api.post<SolicitudCompra>(
    `inventario/solicitudes-compra/${id}/decidir/`,
    { decision, comentario },
  );

  return data;
}


/* Emite las órdenes, **una por proveedor**. Un material sin proveedor
   principal detiene la conversión entera en vez de partir la solicitud. */
export async function convertirSolicitudEnOrdenes(
  id: number,
  bodega: number,
): Promise<OrdenCompra[]> {
  const { data } = await api.post<OrdenCompra[]>(
    `inventario/solicitudes-compra/${id}/convertir/`,
    { bodega },
  );

  return data;
}


/*
  Corre el MRP sobre una semana **publicada** del plan.

  Explota cada bloque de producción a la fecha de ese bloque, así que una
  receta que cambia a mitad de semana se respeta: el martes se planifica con
  la de antes y el jueves con la nueva.

  El backend responde 409 si la semana no está publicada. Es lo correcto: un
  plan en borrador todavía se mueve, y comprar contra él es comprar contra
  algo que nadie firmó.
*/
export async function ejecutarMRPSemana(semana: number): Promise<EjecucionMRP> {
  const { data } = await api.post<EjecucionMRP>(
    "inventario/ejecuciones-mrp/ejecutar/",
    { semana },
  );

  return data;
}


export async function obtenerEjecucionMRP(id: number): Promise<EjecucionMRP> {
  const { data } = await api.get<EjecucionMRP>(`inventario/ejecuciones-mrp/${id}/`);

  return data;
}


/*
  Espera a que el cálculo termine preguntando cada dos segundos.

  Dos segundos y no doscientos milisegundos: el MRP tarda lo que tarda y
  preguntar más seguido solo carga el backend que este cambio existe para
  aliviar.

  El techo de intentos evita que una tarea que murió sin dejar rastro deje a la
  pantalla girando para siempre. Al agotarse **no se inventa un resultado**: se
  devuelve la última ejecución conocida, con su estado real, y la pantalla dice
  que sigue en curso.
*/
export async function esperarEjecucionMRP(
  id: number,
  { intentos = 90, cada = 2000 } = {},
): Promise<EjecucionMRP> {
  let ejecucion = await obtenerEjecucionMRP(id);

  for (let n = 0; n < intentos && !ejecucion.terminada; n++) {
    await new Promise((seguir) => setTimeout(seguir, cada));
    ejecucion = await obtenerEjecucionMRP(id);
  }

  return ejecucion;
}

export async function crearMaterial(datos: {
  codigo: string; nombre: string; categoria: string; area: string; unidad: string;
  requiere_lote: boolean; requiere_vencimiento: boolean; requiere_calidad: boolean;
}) {
  const { data } = await api.post<Insumo>("inventario/insumos/", datos);
  return data;
}

export async function ingresarMaterial(datos: {
  insumo: number; codigo_lote: string; ubicacion: number; cantidad: number;
  elaboracion?: string; vencimiento?: string;
}) {
  const { data } = await api.post<MovimientoInventario>("inventario/movimientos/ingresar-material/", datos);
  return data;
}

export async function consumirRecetaProduccion(lote_produccion: number) {
  const { data } = await api.post<{ consumo: number; movimientos: MovimientoInventario[] }>("inventario/movimientos/consumir-receta/", { lote_produccion });
  return data;
}

export async function registrarSalida(datos: { existencia: number; cantidad: number; tipo: "salida" | "consumo"; motivo: string }) {
  const { data } = await api.post<MovimientoInventario>("inventario/movimientos/salida/", datos);
  return data;
}

export async function trasladarExistencia(datos: { existencia: number; destino: number; cantidad: number; motivo: string }) {
  const { data } = await api.post<MovimientoInventario>("inventario/movimientos/trasladar/", datos);
  return data;
}

export async function crearAjuste(datos: { existencia: number; tipo: "positivo" | "negativo" | "merma"; cantidad: number; motivo: string }) {
  const { data } = await api.post<AjusteInventario>("inventario/ajustes/", datos);
  return data;
}

export async function decidirAjuste(id: number, decision: "aprobar" | "rechazar") {
  const { data } = await api.post<AjusteInventario>(`inventario/ajustes/${id}/decidir/`, { decision });
  return data;
}

export async function decidirInspeccion(id: number, decision: string, observaciones = "") {
  const { data } = await api.post<InspeccionMaterial>(`inventario/inspecciones/${id}/decidir/`, { decision, observaciones, resultados: {} });
  return data;
}

export async function reservarMRQ(id: number) {
  const { data } = await api.post<SolicitudMaterial>(`inventario/mrq/${id}/reservar/`);
  return data;
}

export async function crearMRQ(datos: { numero: string; area: string; fecha_requerida: string; prioridad: number; observaciones?: string }) {
  const { data } = await api.post<SolicitudMaterial>("inventario/mrq/", datos);
  return data;
}

export async function agregarDetalleMRQ(datos: { solicitud: number; insumo: number; cantidad_solicitada: number }) {
  await api.post("inventario/detalles-mrq/", { ...datos, cantidad_aprobada: 0, cantidad_entregada: 0 });
}

export async function enviarMRQ(id: number) {
  const { data } = await api.post<SolicitudMaterial>(`inventario/mrq/${id}/enviar/`);
  return data;
}

export async function entregarMRQ(id: number) {
  const { data } = await api.post<{ entrega: number; estado: string }>(`inventario/mrq/${id}/entregar/`, {});
  return data;
}


/*
  No conformidad de un material inspeccionado.

  `cerrada` sola no dice nada: el cierre exige **qué se hizo**, y si el destino
  es liberación excepcional, la concesión vigente que lo ampara. Por eso esos
  campos son de solo lectura y el cierre tiene su propia acción.
*/
export interface NoConformidad {
  id: number;
  inspeccion: number;
  lote_codigo: string;
  insumo_nombre: string;
  descripcion: string;
  destino: string;
  destino_etiqueta: string;
  cerrada: boolean;
  accion_tomada: string;
  cerrada_por: number | null;
  cerrada_por_nombre: string | null;
  cerrada_en: string | null;
  liberacion: number | null;
  liberacion_vigente: boolean | null;
  creada_en: string;
}


/*
  Concesión: usar una cantidad acotada de un lote que Calidad no aprobó, para
  un uso concreto y con vencimiento.

  `vigente` se calcula desde `vence_en`, que antes se guardaba y nadie miraba —
  una concesión de marzo figuraba igual de válida en agosto.
*/
export interface LiberacionExcepcional {
  id: number;
  lote: number;
  lote_codigo: string;
  insumo_nombre: string;
  cantidad: string;
  uso_especifico: string;
  justificacion: string;
  solicitante: number;
  solicitante_nombre: string;
  calidad_nombre: string;
  jefatura_nombre: string | null;
  autorizada_en: string;
  vence_en: string;
  activa: boolean;
  vigente: boolean;
  /* Cuánto se ha consumido bajo ella y cuánto queda. Se suman del libro de
     movimientos: la concesión ampara una cantidad, no el lote entero. */
  cantidad_usada: string;
  saldo: string;
}


export const obtenerNoConformidades = () =>
  lista<NoConformidad>("inventario/no-conformidades/");

export const obtenerLiberacionesExcepcionales = () =>
  lista<LiberacionExcepcional>("inventario/liberaciones-excepcionales/");


export async function crearNoConformidad(datos: {
  inspeccion: number;
  descripcion: string;
  destino: string;
  liberacion?: number | null;
}): Promise<NoConformidad> {
  const { data } = await api.post<NoConformidad>(
    "inventario/no-conformidades/",
    datos,
  );

  return data;
}


/* No es un PATCH `cerrada=true`: el cierre exige la constancia de qué se hizo
   y, si el destino es concesión, que esa concesión siga vigente. */
export async function cerrarNoConformidad(
  id: number,
  accion_tomada: string,
): Promise<NoConformidad> {
  const { data } = await api.post<NoConformidad>(
    `inventario/no-conformidades/${id}/cerrar/`,
    { accion_tomada },
  );

  return data;
}
