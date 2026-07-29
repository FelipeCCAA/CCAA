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


export async function obtenerResumen(): Promise<Resumen> {
  const { data } = await api.get<Resumen>("produccion/resumen/");

  return data;
}


export async function obtenerLotes(limite = 8): Promise<Lote[]> {
  const { data } = await api.get<Pagina<Lote>>("produccion/lotes/");

  return data.results.slice(0, limite);
}
