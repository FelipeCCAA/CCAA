import api from "./api";

import type { Pagina } from "./produccion.service";


export interface OpcionAseo {
  valor: string;
  etiqueta: string;
}

export interface CatalogosAseo {
  areas: OpcionAseo[];
  tipos_aseo: OpcionAseo[];
  tipos_objetivo: OpcionAseo[];
  estados: OpcionAseo[];
  verificaciones: OpcionAseo[];
  etapas: OpcionAseo[];
}

export interface EtapaAseo {
  id?: number;
  orden: number;
  tipo: string;
  tipo_etiqueta?: string;
  duracion_min: number | null;
  temperatura_c: string | null;
  caudal: string | null;
  conductividad: string | null;
  concentracion_pct: string | null;
  cumple: boolean | null;
  observaciones: string;
}

export interface AseoCip {
  id: number;
  area: string;
  area_etiqueta: string;
  tipo_aseo: "cip" | "cop" | "general";
  tipo_aseo_etiqueta: string;
  tipo_objetivo: "equipo" | "silo" | "seccion";
  tipo_objetivo_etiqueta: string;
  equipo: number | null;
  equipo_nombre: string | null;
  silo: number | null;
  silo_nombre: string | null;
  seccion: string;
  objetivo_nombre: string;
  documento_codigo: string;
  inicio: string;
  inicio_real: string | null;
  fin: string | null;
  estado: "programado" | "en_curso" | "completado" | "observado";
  estado_etiqueta: string;
  verificacion: "pendiente" | "conforme" | "observado";
  verificacion_etiqueta: string;
  ph_final: string | null;
  responsable: number | null;
  responsable_nombre: string;
  ejecutado_por: number | null;
  ejecutado_por_nombre: string;
  verificado_por: number | null;
  verificado_por_nombre: string;
  observaciones: string;
  etapas: EtapaAseo[];
}

export type AseoEditable = Partial<Omit<AseoCip,
  "id" | "area_etiqueta" | "tipo_aseo_etiqueta" | "tipo_objetivo_etiqueta" |
  "equipo_nombre" | "silo_nombre" | "objetivo_nombre" | "estado_etiqueta" |
  "verificacion_etiqueta" | "responsable" | "responsable_nombre" |
  "ejecutado_por" | "ejecutado_por_nombre" | "verificado_por" | "verificado_por_nombre"
>>;

export async function obtenerAseos(): Promise<AseoCip[]> {
  const { data } = await api.get<Pagina<AseoCip>>("inventario/cip/");
  return data.results;
}

export async function obtenerCatalogosAseo(): Promise<CatalogosAseo> {
  const { data } = await api.get<CatalogosAseo>("inventario/cip/catalogos/");
  return data;
}

export async function crearAseo(datos: AseoEditable): Promise<AseoCip> {
  const { data } = await api.post<AseoCip>("inventario/cip/", datos);
  return data;
}

export async function actualizarAseo(id: number, datos: AseoEditable): Promise<AseoCip> {
  const { data } = await api.patch<AseoCip>(`inventario/cip/${id}/`, datos);
  return data;
}
