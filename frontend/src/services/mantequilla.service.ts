import api from "./api";
import { conFiltros, type Filtros } from "./paginacion";
import type { CorridaMantequilla, Pagina } from "./procesos.service";

export type EstadoMantequera = "disponible" | "preparada" | "en_curso";

export interface CorridaEnMantequera {
  /* `null` en una ejecución de Mantequilla sin corrida (dato heredado de
     `preparar-continuacion`, ya cerrado). */
  id: number | null;
  estado: string | null;
  ejecucion_id: number;
  ejecucion_codigo: string;
  ejecucion_estado: string;
  orden_codigo: string | null;
  producto: string | null;
  lote_mantequilla: string | null;
  lote_crema: string | null;
  kg_crema: string | null;
  lote_suero: string | null;
  iniciada_en: string | null;
}

export interface MantequeraPuesto {
  equipo_id: number;
  codigo: string;
  nombre: string;
  /* `mantequera`, o el tipo viejo de un equipo con una corrida anterior a `maestros.0040`. */
  tipo: string;
  estado: EstadoMantequera;
  corrida: CorridaEnMantequera | null;
  /* Por qué no se puede preparar una disponible (CIP). */
  motivos_para_tomar: string[];
  motivos_para_iniciar: string[];
  /* Dónde se resuelve el primer motivo; `null` si no hay pantalla que lo arregle. */
  resolver_en: string | null;
  avisos: string[];
  en_calidad: { id: number; ejecucion_codigo: string; lote_mantequilla: string } | null;
}

export interface CremaDisponible {
  id: number;
  codigo: string;
  producto: string;
  /* Kilos producidos menos lo que entró a una mantequera y lo que otras
     corridas preparadas ya pidieron (`kg_crema_disponible`): el tope del formulario. */
  disponible_kg: string;
  /* El TK de donde saldrá al iniciar, si está en uno. */
  tk: string | null;
}

export interface CremaPendienteCalidad {
  id: number;
  codigo: string;
  producto: string;
  estado_calidad: "pendiente" | "rechazado" | "trazabilidad_incompleta";
  etapa_origen: string;
}

export interface CorridaDeHoyMantequilla {
  id: number;
  ejecucion_codigo: string;
  equipo: string | null;
  lote_mantequilla: string;
  lote_crema: string;
  estado: string;
  estado_etiqueta: string;
  estado_ejecucion: string;
  /* Cómo la nombra el puesto; mismas opciones que el filtro del historial. */
  situacion: string;
  situacion_etiqueta: string;
}

export interface PuestoMantequilla {
  mantequeras: MantequeraPuesto[];
  ordenes: { id: number; codigo: string; producto: string }[];
  cremas: CremaDisponible[];
  cremas_pendientes_calidad: CremaPendienteCalidad[];
  sueros: { id: number; codigo: string; producto: string }[];
  corridas_de_hoy: CorridaDeHoyMantequilla[];
  /* Las situaciones del filtro del historial (`SITUACIONES_MANTEQUILLA`). */
  estados: { valor: string; etiqueta: string }[];
}

/* El código del lote de salida se sugiere y queda editable. */
export interface PreparacionMantequilla {
  orden: number;
  lote_crema: number;
  equipo: number;
  codigo_lote_mantequilla: string;
  kg_crema: number;
  lote_suero?: number;
}

export interface ValoresCierreMantequilla {
  kg_mantequilla: number | null;
  kg_suero: number | null;
  kg_merma: number | null;
  kg_reproceso: number | null;
  motivo_reproceso: string;
}

export interface RevisionCierreMantequilla {
  entrada_kg: string;
  clasificado_kg: string;
  /* entrada − clasificado: positiva falta, negativa excede. */
  diferencia_kg: string;
  cuadra: boolean;
  mensaje: string | null;
  /* Las otras reglas de `clean()` que dependen de lo tecleado, por campo. */
  errores: Record<string, string>;
}

export interface CierreMantequilla {
  kg_mantequilla: number;
  kg_suero: number;
  kg_merma: number;
  kg_reproceso: number;
  motivo_reproceso: string;
  controles: Record<string, unknown>;
}

export interface CancelacionPreparacionMantequilla {
  ejecucion_id: number;
  ejecucion_codigo: string;
  estado: string;
}

export async function obtenerPuestoMantequilla(): Promise<PuestoMantequilla> {
  const { data } = await api.get<PuestoMantequilla>("procesos/mantequillas/puesto/");
  return data;
}

export async function obtenerMantequilla(id: number): Promise<CorridaMantequilla> {
  const { data } = await api.get<CorridaMantequilla>(`procesos/mantequillas/${id}/`);
  return data;
}

/* Prepara: lote de salida, ejecución y corrida, y toma la mantequera. No inicia. */
export async function prepararMantequilla(datos: PreparacionMantequilla): Promise<CorridaMantequilla> {
  const { data } = await api.post<CorridaMantequilla>("procesos/mantequillas/crear-guiada/", datos);
  return data;
}

export async function iniciarMantequilla(id: number): Promise<CorridaMantequilla> {
  const { data } = await api.post<CorridaMantequilla>(`procesos/mantequillas/${id}/iniciar/`);
  return data;
}

/* Suelta la mantequera; la corrida y su lote de salida quedan anulados. */
export async function cancelarPreparacionMantequilla(
  id: number, motivo: string,
): Promise<CancelacionPreparacionMantequilla> {
  const { data } = await api.post<CancelacionPreparacionMantequilla>(
    `procesos/mantequillas/${id}/cancelar-preparacion/`, { motivo },
  );
  return data;
}

/* El balance con lo tecleado hasta ahora; el servidor no escribe nada. */
export async function revisarCierreMantequilla(
  id: number, valores: ValoresCierreMantequilla,
): Promise<RevisionCierreMantequilla> {
  const { data } = await api.post<RevisionCierreMantequilla>(
    `procesos/mantequillas/${id}/revisar-cierre/`, valores,
  );
  return data;
}

export async function cerrarMantequilla(id: number, datos: CierreMantequilla): Promise<CorridaMantequilla> {
  const { data } = await api.post<CorridaMantequilla>(`procesos/mantequillas/${id}/cerrar/`, datos);
  return data;
}

/* Historial del puesto: filtros y página viajan al servidor. */
export async function buscarMantequillas(filtros: Filtros = {}): Promise<Pagina<CorridaMantequilla>> {
  const { data } = await api.get<Pagina<CorridaMantequilla>>(conFiltros("procesos/mantequillas/", filtros));
  return data;
}
