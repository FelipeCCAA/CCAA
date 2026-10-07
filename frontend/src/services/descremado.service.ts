import api from "./api";
import { conFiltros, type Filtros } from "./paginacion";
import type { CorridaDescremacion, Pagina } from "./procesos.service";

export type EstadoDescremadora = "disponible" | "preparada" | "en_curso";

export interface CorridaDescremadora {
  /* `null` en una ejecución heredada sin corrida (alta genérica ya cerrada). */
  id: number | null;
  ejecucion_id: number;
  ejecucion_codigo: string;
  ejecucion_estado: string;
  estado: string | null;
  silo_entera: string | null;
  litros_entrada: string | null;
  grasa_entrada: string | null;
  sng_entrada: string | null;
  silo_descremada: string | null;
  litros_descremada_plan: string | null;
  estanque_crema: string | null;
  litros_crema_plan: string | null;
  destino_crema: string | null;
  iniciada_en: string | null;
}

export interface DescremadoraPuesto {
  equipo_id: number;
  codigo: string;
  nombre: string;
  estado: EstadoDescremadora;
  corrida: CorridaDescremadora | null;
  /* Por qué no se puede preparar una disponible (CIP). */
  motivos_para_tomar: string[];
  motivos_para_iniciar: string[];
  /* Dónde se resuelve el primer motivo; `null` si no hay pantalla que lo arregle. */
  resolver_en: string | null;
  avisos: string[];
  en_calidad: { id: number; ejecucion_codigo: string; tanques: string[] } | null;
}

export interface OrigenDescremado {
  id: number;
  codigo: string;
  saldo_l: string;
  /* El análisis que usará «Preparar»: no se elige en la pantalla. */
  analisis: { id: number; grasa: string; sng: string; tomado_en: string } | null;
  motivo: string | null;
}

export interface DestinoDescremado {
  id: number;
  codigo: string;
  libre_l: string;
}

export interface CorridaDeHoyDescremado {
  id: number;
  ejecucion_codigo: string;
  equipo: string | null;
  silo_entera: string;
  estado: string;
  estado_etiqueta: string;
  estado_ejecucion: string;
}

export interface PuestoDescremado {
  descremadoras: DescremadoraPuesto[];
  origenes: OrigenDescremado[];
  destinos_descremada: DestinoDescremado[];
  destinos_crema: DestinoDescremado[];
  corridas_de_hoy: CorridaDeHoyDescremado[];
  estados: { valor: string; etiqueta: string }[];
}

export type DestinoRamaCrema = "siguiente_proceso" | "estandarizacion" | "despacho_directo";

/* Sin código ni análisis: los pone el servidor. */
export interface PreparacionDescremado {
  etapa: number;
  equipo: number;
  silo_entera: number;
  litros_entrada: number;
  silo_descremada: number;
  estanque_crema: number;
  producto_descremada: number;
  producto_crema: number;
  litros_descremada_plan: number;
  litros_crema_plan: number;
  plan_confirmado: true;
  ruta_descremada: number;
  ruta_crema: number;
  destino_descremada: "estandarizacion";
  destino_crema: DestinoRamaCrema;
}

export interface ValoresCierreDescremado {
  litros_descremada: number | null;
  grasa_descremada: number | null;
  litros_crema: number | null;
  grasa_crema: number | null;
}

export interface RevisionCierreDescremado {
  avisos_limites: { codigo: string; mensaje: string }[];
  avisos_balance: string[];
  merma_l: string | null;
  desvio_grasa_kg: string | null;
}

export interface CancelacionPreparacionDescremado {
  ejecucion_id: number;
  ejecucion_codigo: string;
  estado: string;
}

export async function obtenerPuestoDescremado(): Promise<PuestoDescremado> {
  const { data } = await api.get<PuestoDescremado>("procesos/descremaciones/puesto/");
  return data;
}

export async function obtenerDescremacion(id: number): Promise<CorridaDescremacion> {
  const { data } = await api.get<CorridaDescremacion>(`procesos/descremaciones/${id}/`);
  return data;
}

/* Prepara: corrida, reservas de silo y descremadora tomada. No inicia. */
export async function prepararDescremado(datos: PreparacionDescremado): Promise<CorridaDescremacion> {
  const { data } = await api.post<CorridaDescremacion>("procesos/descremaciones/crear-guiada/", datos);
  return data;
}

export async function iniciarDescremado(id: number): Promise<CorridaDescremacion> {
  const { data } = await api.post<CorridaDescremacion>(`procesos/descremaciones/${id}/iniciar/`);
  return data;
}

/* Suelta la descremadora y las reservas; la corrida queda anulada. */
export async function cancelarPreparacionDescremado(
  id: number, motivo: string,
): Promise<CancelacionPreparacionDescremado> {
  const { data } = await api.post<CancelacionPreparacionDescremado>(
    `procesos/descremaciones/${id}/cancelar-preparacion/`, { motivo },
  );
  return data;
}

/* Avisos del cierre con lo tecleado hasta ahora; el servidor no escribe nada. */
export async function revisarCierreDescremado(
  id: number, valores: ValoresCierreDescremado,
): Promise<RevisionCierreDescremado> {
  const { data } = await api.post<RevisionCierreDescremado>(
    `procesos/descremaciones/${id}/revisar-cierre/`, valores,
  );
  return data;
}

/* Historial del puesto: filtros y página viajan al servidor. */
export async function buscarDescremaciones(filtros: Filtros = {}): Promise<Pagina<CorridaDescremacion>> {
  const { data } = await api.get<Pagina<CorridaDescremacion>>(conFiltros("procesos/descremaciones/", filtros));
  return data;
}
