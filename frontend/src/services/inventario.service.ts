import api from "./api";

export interface Insumo {
  id: number; codigo: string; nombre: string; area: string; area_etiqueta: string;
  unidad: string; stock_actual: string; contenido_envase: string;
  stock_fisico: number; stock_disponible: number; stock_bloqueado: number;
  eoq: string | null; punto_reposicion: string;
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

export interface OrdenCompra {
  id: number; numero: string; proveedor_nombre: string; estado: string;
  fecha_comprometida: string | null; detalles: Array<{ id: number; insumo_nombre: string; cantidad: string; cantidad_recibida: string }>;
}

export interface Notificacion {
  id: number; tipo: string; titulo: string; mensaje: string; leida_en: string | null; creada_en: string;
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
