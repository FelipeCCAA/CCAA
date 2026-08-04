import api from "./api";
import type { Pagina } from "./procesos.service";

export interface ResumenMantenimiento {
  ordenes_abiertas: number;
  planes_vencidos: number;
  fallas_criticas_abiertas: number;
}

export interface OrdenTrabajo {
  id: number;
  numero: string;
  tipo: string;
  estado: string;
  estado_etiqueta: string;
  equipo_nombre: string;
  prioridad: number;
  responsable_nombre: string | null;
  programada_para: string | null;
}

export async function obtenerResumenMantenimiento(): Promise<ResumenMantenimiento> {
  const { data } = await api.get<ResumenMantenimiento>("mantenimiento/resumen/");
  return data;
}

export async function obtenerOrdenesTrabajo(): Promise<Pagina<OrdenTrabajo>> {
  const { data } = await api.get<Pagina<OrdenTrabajo>>("mantenimiento/ordenes/");
  return data;
}
