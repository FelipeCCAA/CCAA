import api from "./api";
import { conFiltros, type Filtros } from "./paginacion";
import type { Pagina } from "./procesos.service";

export interface CorridaSecado {
  id: number;
  ejecucion: number;
  ejecucion_codigo: string;
  estado: string;
  estado_etiqueta: string;
  equipo_id: number | null;
  equipo_nombre: string | null;
  iniciada_en: string | null;
  lote: number;
  lote_codigo: string;
  producto_nombre: string;
  orden: number | null;
  orden_codigo: string | null;
  kg_alimentacion: string | null;
  solidos_entrada_pct: string | null;
  kg_polvo: string | null;
  kg_finos: string;
  kg_merma: string;
  controles: Record<string, unknown>;
  rendimiento_recuperacion_pct: string | null;
  finalizada_por: number | null;
  finalizada_en: string | null;
  requiere_calidad: boolean;
  estado_calidad: "no_requerida" | "pendiente" | "liberado" | "rechazado";
  operacion_id: string;
}

export interface CierreSecado {
  kg_alimentacion: number;
  solidos_entrada_pct: number;
  kg_polvo: number;
  kg_finos: number;
  kg_merma: number;
  controles: Record<string, number>;
}

export interface OpcionesSecadoExterno {
  existencias: Array<{
    id: number; lote_id: number; lote_codigo: string;
    insumo_id: number; insumo_nombre: string;
    cantidad_disponible: string; unidad: string; estado_calidad: string;
  }>;
  ordenes: Array<{
    id: number; codigo: string; producto_id: number;
    producto_nombre: string; insumo_origen_id: number;
  }>;
  equipos: Array<{
    id: number; codigo: string; nombre: string; disponible: boolean;
  }>;
}

export interface PreparacionSecadoExterno {
  orden: number;
  existencia: number;
  equipo: number;
  codigo_lote: string;
  cantidad: number;
}

export type EstadoTorre = "disponible" | "preparada" | "en_curso";

export interface CorridaTorre {
  id: number | null;
  ejecucion_id: number;
  ejecucion_codigo: string;
  ejecucion_estado: string;
  lote_codigo: string | null;
  origen: string | null;
  cantidad: string | null;
  unidad: string | null;
  iniciada_en: string | null;
}

export interface TorrePuesto {
  equipo_id: number;
  codigo: string;
  nombre: string;
  estado: EstadoTorre;
  corrida: CorridaTorre | null;
  motivos_para_iniciar: string[];
  resolver_en: string | null;
  avisos: string[];
  falta_inspeccion: boolean;
  en_calidad: { id: number; lote_codigo: string } | null;
}

export interface ConcentradoPuesto {
  salida_id: number;
  etapa_id: number;
  lote_codigo: string;
  producto: string;
  silo: string;
  disponible: string;
  unidad: string;
}

export interface CorridaDeHoySecado {
  id: number;
  equipo: string | null;
  lote_codigo: string;
  estado: string;
  estado_calidad: string;
}

export interface PuestoSecado {
  torres: TorrePuesto[];
  concentrados: ConcentradoPuesto[];
  corridas_de_hoy: CorridaDeHoySecado[];
  estados: { valor: string; etiqueta: string }[];
}

export async function obtenerSecado(id: number, signal?: AbortSignal): Promise<CorridaSecado> {
  const { data } = await api.get<CorridaSecado>(`procesos/secados/${id}/`, { signal });
  return data;
}

export async function cerrarSecado(id: number, datos: CierreSecado): Promise<CorridaSecado> {
  const { data } = await api.post<CorridaSecado>(`procesos/secados/${id}/cerrar/`, datos);
  return data;
}

export async function obtenerOpcionesSecadoExterno(
  signal?: AbortSignal,
): Promise<OpcionesSecadoExterno> {
  const { data } = await api.get<OpcionesSecadoExterno>(
    "procesos/secados/opciones-alimentacion-externa/", { signal },
  );
  return data;
}

export async function obtenerPuestoSecado(): Promise<PuestoSecado> {
  const { data } = await api.get<PuestoSecado>("procesos/secados/puesto/");
  return data;
}

export async function iniciarSecado(id: number): Promise<CorridaSecado> {
  const { data } = await api.post<CorridaSecado>(`procesos/secados/${id}/iniciar/`);
  return data;
}

export async function prepararSecadoExterno(
  datos: PreparacionSecadoExterno,
): Promise<CorridaSecado> {
  const { data } = await api.post<CorridaSecado>(
    "procesos/secados/preparar-desde-inventario/", datos,
  );
  return data;
}

/* Historial del puesto: filtros y página viajan al servidor. */
export async function buscarSecados(filtros: Filtros = {}): Promise<Pagina<CorridaSecado>> {
  const { data } = await api.get<Pagina<CorridaSecado>>(conFiltros("procesos/secados/", filtros));
  return data;
}
