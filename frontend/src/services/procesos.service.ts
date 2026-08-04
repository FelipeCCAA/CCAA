import api from "./api";

export interface Pagina<T> { count: number; next: string | null; previous: string | null; results: T[] }

export interface EjecucionProceso {
  id: number;
  codigo: string;
  estado: string;
  estado_etiqueta: string;
  etapa_nombre: string;
  equipo_nombre: string | null;
  inicio: string | null;
  termino: string | null;
  acciones_permitidas: string[];
  entradas: { id: number; lote: number; lote_codigo: string; cantidad: string; unidad: string }[];
  salidas: { id: number; lote: number | null; lote_codigo: string | null; cantidad: string; unidad: string; naturaleza: string }[];
}

export interface Genealogia {
  nodos: { id: number; codigo: string; producto: string; fecha: string }[];
  enlaces: { origen: number; destino: number }[];
}

export async function obtenerEjecuciones(): Promise<Pagina<EjecucionProceso>> {
  const { data } = await api.get<Pagina<EjecucionProceso>>("procesos/ejecuciones/");
  return data;
}

export async function obtenerGenealogia(loteId: number, direccion: "atras" | "adelante"): Promise<Genealogia> {
  const { data } = await api.get<Genealogia>(
    `procesos/trazabilidad/lotes/${loteId}/`, { params: { direccion } },
  );
  return data;
}
