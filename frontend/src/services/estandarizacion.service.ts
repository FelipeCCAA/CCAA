import api from "./api";
import type { Silo } from "./recepcion.service";

interface Pagina<T> { results: T[] }

export type EstadoVale =
  | "borrador"
  | "calculado"
  | "transferido"
  | "agitando"
  | "muestreado"
  | "corrigiendo"
  | "liberado"
  | "anulado";

export interface Evaluacion {
  cumple: boolean;
  rc_real: number | null;
  desvio: number | null;
  agregar: string;
  motivo: string;
}

export interface ValeEstandarizacion {
  id: number;
  codigo: string;
  codigo_propuesto: string;
  fecha: string;
  producto: number | null;
  producto_nombre: string | null;
  rc_objetivo: string | null;
  volumen: string | null;
  silo_entera: number | null;
  silo_entera_codigo: string | null;
  silo_descremada: number | null;
  silo_descremada_codigo: string | null;
  silo_destino: number | null;
  silo_destino_codigo: string | null;
  silo_sugerido_fifo: number | null;
  motivo_desvio_fifo: string;
  entera_grasa: string | null;
  entera_sng: string | null;
  descremada_grasa: string | null;
  descremada_sng: string | null;
  litros_entera: string | null;
  litros_descremada: string | null;
  estado: EstadoVale;
  agitacion_desde: string | null;
  muestreado_en: string | null;
  grasa_real: string | null;
  sng_real: string | null;
  rc_real: number | null;
  minutos_agitando: number | null;
  avisos: string[];
  evaluacion: Evaluacion | null;
  observaciones: string;
  responsable_nombre: string | null;
  es_borrador: boolean;
  actualizado_en: string;
}

export interface Mezcla {
  posible: boolean;
  motivo: string;
  entera: number;
  descremada: number;
  rc_esperado: number | null;
  grasa_esperada: number | null;
  sng_esperado: number | null;
  avisos: string[];
}

export interface CatalogosEstandarizacion {
  estados: { valor: string; etiqueta: string }[];
  /*
    Los minutos vienen del backend y no se escriben aquí: la cuenta regresiva
    de la pantalla tiene que medir contra el mismo número con el que el
    servidor evalúa el aviso. Una copia terminaría ofreciendo el botón antes
    de tiempo — y el operador tomando una muestra que el servidor marca con
    aviso sin que la pantalla lo haya anticipado.
  */
  minutos_agitacion: number;
  transiciones: Record<string, string[]>;
  silos: Silo[];
}

export async function obtenerVales(params?: {
  estado?: string;
  abiertos?: boolean;
}): Promise<ValeEstandarizacion[]> {
  const { data } = await api.get<Pagina<ValeEstandarizacion>>(
    "estandarizacion/vales/",
    { params },
  );
  return data.results;
}

export async function obtenerCatalogos(): Promise<CatalogosEstandarizacion> {
  const { data } = await api.get<CatalogosEstandarizacion>(
    "estandarizacion/vales/catalogos/",
  );
  return data;
}

export interface EntradaCalculo {
  entera_grasa: number;
  entera_sng: number;
  entera_disponible?: number;
  descremada_grasa: number;
  descremada_sng: number;
  descremada_disponible?: number;
  rc_objetivo: number;
  volumen: number;
}

/*
  Calcula sin crear. Es el paso que el operador repite variando el volumen
  antes de decidir; guardar cada tanteo llenaría la tabla de vales muertos.
*/
export async function calcularMezcla(datos: EntradaCalculo): Promise<Mezcla> {
  const { data } = await api.post<Mezcla>(
    "estandarizacion/vales/calcular/",
    datos,
  );
  return data;
}

export interface NuevoVale {
  codigo: string;
  fecha: string;
  producto: number;
  rc_objetivo: number;
  volumen: number;
  silo_entera: number;
  silo_descremada: number | null;
  silo_destino: number;
  entera_grasa: number;
  entera_sng: number;
  descremada_grasa: number;
  descremada_sng: number;
  litros_entera: number;
  litros_descremada: number;
  observaciones?: string;
}

export async function crearVale(datos: NuevoVale): Promise<ValeEstandarizacion> {
  const { data } = await api.post<ValeEstandarizacion>(
    "estandarizacion/vales/",
    datos,
  );
  return data;
}

export interface DatosBorradorVale {
  codigo_propuesto: string;
  fecha: string;
  producto: number | null;
  rc_objetivo: number | null;
  volumen: number | null;
  silo_entera: number | null;
  silo_descremada: number | null;
  silo_destino: number | null;
  silo_sugerido_fifo: number | null;
  motivo_desvio_fifo: string;
  entera_grasa: number | null;
  entera_sng: number | null;
  descremada_grasa: number | null;
  descremada_sng: number | null;
  litros_entera: number | null;
  litros_descremada: number | null;
  observaciones: string;
}

export async function obtenerBorradorVale(): Promise<ValeEstandarizacion | null> {
  const respuesta = await api.get<ValeEstandarizacion>(
    "estandarizacion/vales/mi-borrador/",
  );
  return respuesta.status === 204 ? null : respuesta.data;
}

export async function crearBorradorVale(datos: DatosBorradorVale) {
  const { data } = await api.post<ValeEstandarizacion>(
    "estandarizacion/vales/crear-borrador/", datos,
  );
  return data;
}

export async function guardarBorradorVale(id: number, datos: DatosBorradorVale) {
  const { data } = await api.patch<ValeEstandarizacion>(
    `estandarizacion/vales/${id}/guardar-borrador/`, datos,
  );
  return data;
}

export async function confirmarBorradorVale(id: number) {
  const { data } = await api.post<ValeEstandarizacion>(
    `estandarizacion/vales/${id}/confirmar-borrador/`,
  );
  return data;
}

export async function descartarBorradorVale(id: number) {
  await api.post(`estandarizacion/vales/${id}/descartar-borrador/`);
}

/*
  Cada paso del ciclo es su propia acción, no un `PATCH estado=...`. La
  diferencia importa en `decidir`: **no recibe la decisión, la calcula** desde
  el RC medido, así que no hay forma de pedir «liberado» desde aquí.
*/
async function accion(id: number, ruta: string, cuerpo?: unknown) {
  const { data } = await api.post<ValeEstandarizacion>(
    `estandarizacion/vales/${id}/${ruta}/`,
    cuerpo,
  );
  return data;
}

export const transferirVale = (id: number) => accion(id, "transferir");
export const agitarVale = (id: number) => accion(id, "agitar");
export const reagitarVale = (id: number) => accion(id, "reagitar");
export const decidirVale = (id: number) => accion(id, "decidir");

export const muestrearVale = (id: number, grasa: number, sng: number) =>
  accion(id, "muestrear", { grasa, sng });

export async function corregirMuestraVale(
  id: number, grasa: number, sng: number, motivo: string,
) {
  const { data } = await api.patch<ValeEstandarizacion>(
    `estandarizacion/vales/${id}/corregir-muestra/`,
    { grasa, sng, motivo },
  );
  return data;
}

export const anularVale = (id: number, motivo: string) =>
  accion(id, "anular", { motivo });


/*
  La composición de cada silo según su último análisis, para prellenar el
  vale. Un silo sin análisis o con uno vencido no es un error: viene con su
  motivo, y quien compone el vale sigue decidiendo.
*/
export interface ComposicionDeSilo {
  analisis: number | null;
  silo: number | null;
  silo_codigo: string;
  tomado_en: string | null;
  grasa: string | null;
  sng: string | null;
  vigente: boolean;
  motivo: string;
  faltantes: string[];
}

export interface ComposicionSilos {
  entera: ComposicionDeSilo;
  descremada: ComposicionDeSilo;
}

export async function composicionSilos(
  enteraId?: number,
  descremadaId?: number,
): Promise<ComposicionSilos> {
  const { data } = await api.get("/estandarizacion/vales/composicion-silos/", {
    params: { entera: enteraId, descremada: descremadaId },
  });
  return data;
}
