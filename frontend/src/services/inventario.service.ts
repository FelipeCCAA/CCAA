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

export interface UbicacionInventario { id: number; codigo: string; bodega_nombre: string; tipo: string; activo: boolean }

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

export interface OrdenCompra {
  id: number; numero: string; proveedor_nombre: string; estado: string;
  fecha_comprometida: string | null; detalles: Array<{ id: number; insumo_nombre: string; cantidad: string; cantidad_recibida: string }>;
}

export interface Notificacion {
  id: number; tipo: string; titulo: string; mensaje: string; leida_en: string | null; creada_en: string;
}

export interface MovimientoInventario {
  id: number; tipo: string; lote: number; lote_codigo: string; insumo_nombre: string;
  cantidad: string; origen_codigo: string | null; destino_codigo: string | null;
  motivo: string; fecha: string;
}

export interface AjusteInventario {
  id: number; existencia: number; tipo: "positivo" | "negativo" | "merma";
  cantidad: string; motivo: string; estado: string; solicitante: number; aprobador: number | null;
}

export interface ResultadoMRP {
  kilos_producir: string;
  materiales: Array<{ insumo: string; unidad: string; requerido: string; stock: string; faltante: string; envases_a_pedir: number; eoq: string | null }>;
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
