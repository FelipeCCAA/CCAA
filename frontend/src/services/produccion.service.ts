import api from "./api";


/* Los listados de DRF vienen paginados. */
export interface Pagina<T> {
  count: number;
  next: string | null;
  previous: string | null;
  results: T[];
}


export type ResultadoCalidad =
  | "conforme"
  | "no_conforme"
  | "sin_analisis"
  | "sin_especificacion";


/* Los cuatro veredictos posibles, para poblar filtros. Reflejan las
   constantes de produccion/dominio.py. */
export const RESULTADOS: { valor: ResultadoCalidad; etiqueta: string }[] = [
  { valor: "conforme", etiqueta: "Conforme" },
  { valor: "no_conforme", etiqueta: "No conforme" },
  { valor: "sin_analisis", etiqueta: "Sin análisis" },
  { valor: "sin_especificacion", etiqueta: "Sin especificación" },
];


export interface Desviacion {
  analisis_id: number;
  muestra: string;
  parametro: string;
  valor: number | null;
  min: number | null;
  max: number | null;
  desvio: "bajo" | "alto" | null;
}


export interface CalidadLote {
  resultado: ResultadoCalidad;
  etiqueta: string;
  evaluados: number;
  desviaciones: Desviacion[];
  especificacion_id: number | null;
}


export interface Lote {
  id: number;
  codigo_lote: string;
  op: string;
  producto: number;
  producto_nombre: string;
  mandante_nombre: string;
  fecha: string;
  linea: string;
  turno: string;
  /* Django serializa los decimales como texto, para no perder precisión. */
  kg_producidos: string;
  estado: string;
  estado_etiqueta: string;
  calidad: CalidadLote;
}


export interface Resumen {
  lotes: number;
  kg_producidos: number;
  calidad: {
    conforme: number;
    no_conforme: number;
    sin_analisis: number;
    sin_especificacion: number;
    evaluados: number;
    /* null cuando no hay lotes: el backend no inventa porcentajes. */
    cobertura: number | null;
    cumplimiento: number | null;
  };
  kg_por_producto: { nombre: string; kg: number }[];
  kg_por_mandante: { nombre: string; kg: number }[];
}


export interface Producto {
  id: number;
  codigo: string;
  nombre: string;
  familia: string;
  familia_etiqueta: string;
  mandante: number;
  mandante_nombre: string;
  activo: boolean;
}


export interface Parametro {
  clave: string;
  etiqueta: string;
  unidad: string;
}


export interface FiltrosLotes {
  producto?: string;
  calidad?: string;
  buscar?: string;
  pagina?: number;
}


/** Campos de un lote nuevo. Los opcionales se omiten si van vacíos. */
export interface LoteNuevo {
  codigo_lote: string;
  producto: number;
  fecha: string;
  kg_producidos: string;
  op?: string;
  linea?: string;
  turno?: string;
  bultos?: number;
  observacion?: string;
}


export async function obtenerResumen(): Promise<Resumen> {
  const { data } = await api.get<Resumen>("produccion/resumen/");

  return data;
}


export async function obtenerLotes(limite = 8): Promise<Lote[]> {
  const { data } = await api.get<Pagina<Lote>>("produccion/lotes/");

  return data.results.slice(0, limite);
}


export async function buscarLotes(
  filtros: FiltrosLotes = {},
): Promise<Pagina<Lote>> {

  const { data } = await api.get<Pagina<Lote>>("produccion/lotes/", {
    // axios omite los parámetros en undefined, así que un filtro vacío
    // simplemente no viaja.
    params: {
      producto: filtros.producto || undefined,
      calidad: filtros.calidad || undefined,
      buscar: filtros.buscar || undefined,
      page: filtros.pagina && filtros.pagina > 1 ? filtros.pagina : undefined,
    },
  });

  return data;
}


export async function obtenerProductos(): Promise<Producto[]> {
  const { data } = await api.get<Pagina<Producto>>("maestros/productos/");

  return data.results;
}


export async function obtenerParametros(): Promise<Parametro[]> {
  const { data } = await api.get<Parametro[]>("maestros/parametros/");

  return data;
}


export async function crearLote(lote: LoteNuevo): Promise<Lote> {
  const { data } = await api.post<Lote>("produccion/lotes/", lote);

  return data;
}


export async function crearAnalisis(
  loteId: number,
  fecha: string,
  valores: Record<string, number>,
  muestra = "",
): Promise<void> {
  await api.post("produccion/analisis/", {
    lote: loteId,
    fecha,
    muestra,
    valores,
  });
}


export async function borrarLote(id: number): Promise<void> {
  await api.delete(`produccion/lotes/${id}/`);
}
