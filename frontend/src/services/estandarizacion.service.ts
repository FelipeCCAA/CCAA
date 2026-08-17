import api from "./api";
import type { Silo } from "./recepcion.service";

interface Pagina<T> { results: T[] }

export type EstadoVale =
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
  fecha: string;
  producto: number;
  producto_nombre: string;
  rc_objetivo: string;
  volumen: string;
  silo_entera: number;
  silo_entera_codigo: string;
  silo_descremada: number | null;
  silo_descremada_codigo: string | null;
  silo_destino: number;
  silo_destino_codigo: string;
  entera_grasa: string;
  entera_sng: string;
  descremada_grasa: string;
  descremada_sng: string;
  litros_entera: string;
  litros_descremada: string;
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
    servidor acepta la muestra. Una copia terminaría ofreciendo el botón antes
    de tiempo — y el operador tomando una muestra que el servidor rechaza.
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

export const anularVale = (id: number, motivo: string) =>
  accion(id, "anular", { motivo });
