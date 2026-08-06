import api from "./api";


/*
  Recolección de leche en predios.

  Es el primer eslabón de la cadena: lo que se mide frente al estanque del
  predio, antes de que la leche suba al camión.

  La regla que decide es la **prueba de alcohol**: positiva y esa leche no
  sube. Pero se registra igual —como no cargada, con su motivo— porque el
  problema hay que poder reconstruirlo después aunque la leche se haya quedado
  en el campo.
*/

export interface ProveedorLeche {
  id: number;
  rut: string;
  nombre: string;
  activo: boolean;
  /* Un proveedor bloqueado no puede entregar leche. Lo pondrá la cadena de
     antibióticos, que todavía no está implementada. */
  bloqueado: boolean;
  motivo_bloqueo: string;
  predios: number;
}


export interface Predio {
  id: number;
  proveedor: number;
  proveedor_nombre: string;
  proveedor_bloqueado: boolean;
  codigo: string;
  nombre: string;
  comuna: string;
  activo: boolean;
}


export interface Conductor {
  id: number;
  rut: string;
  nombre: string;
  telefono: string;
  activo: boolean;
}


export interface Modulo {
  id: number;
  vehiculo: number;
  vehiculo_placa: string;
  numero: string;
  capacidad_l: string | null;
  activo: boolean;
}


export interface CargaPredio {
  id: number;
  recoleccion: number;
  predio: number;
  predio_nombre: string;
  proveedor_nombre: string;
  modulo: number | null;
  modulo_numero: string | null;
  litros: string;
  temperatura: string;
  alcohol: "negativa" | "positiva";
  alcohol_etiqueta: string;
  visual: "conforme" | "no_conforme";
  muestra_tomada: boolean;
  cargada: boolean;
  observaciones: string;
}


export interface Recoleccion {
  id: number;
  codigo: string;
  fecha: string;
  conductor: number;
  conductor_nombre: string;
  camion: number;
  camion_placa: string;
  carro: number | null;
  carro_placa: string | null;
  estado: string;
  estado_etiqueta: string;
  observaciones: string;
  cargas: CargaPredio[];
  /* Los dos se calculan del detalle: un total guardado se desincroniza en
     cuanto alguien corrige una carga. */
  litros_cargados: string;
  predios_rechazados: string[];
}


async function lista<T>(ruta: string): Promise<T[]> {
  const { data } = await api.get<T[] | { results: T[] }>(ruta);

  return Array.isArray(data) ? data : data.results;
}


export const obtenerProveedoresLeche = () =>
  lista<ProveedorLeche>("recoleccion/proveedores/");
export const obtenerPredios = () => lista<Predio>("recoleccion/predios/");
export const obtenerConductores = () =>
  lista<Conductor>("recoleccion/conductores/");
export const obtenerModulos = () => lista<Modulo>("recoleccion/modulos/");
export const obtenerRecolecciones = () =>
  lista<Recoleccion>("recoleccion/recolecciones/");


export async function crearRecoleccion(datos: {
  codigo: string;
  fecha: string;
  conductor: number;
  camion: number;
  carro?: number | null;
}): Promise<Recoleccion> {
  const { data } = await api.post<Recoleccion>(
    "recoleccion/recolecciones/",
    datos,
  );

  return data;
}


/* Rechaza si la prueba de alcohol salió positiva y se marcó como cargada, si
   la leche no se cargó y no se dijo por qué, o si el proveedor está
   bloqueado. */
export async function registrarCarga(
  datos: Record<string, unknown>,
): Promise<CargaPredio> {
  const { data } = await api.post<CargaPredio>("recoleccion/cargas/", datos);

  return data;
}


export async function crearProveedorLeche(datos: {
  rut: string;
  nombre: string;
}): Promise<ProveedorLeche> {
  const { data } = await api.post<ProveedorLeche>(
    "recoleccion/proveedores/",
    datos,
  );

  return data;
}


export async function crearPredio(datos: {
  proveedor: number;
  codigo: string;
  nombre: string;
  comuna?: string;
}): Promise<Predio> {
  const { data } = await api.post<Predio>("recoleccion/predios/", datos);

  return data;
}


export async function crearConductor(datos: {
  rut: string;
  nombre: string;
  telefono?: string;
}): Promise<Conductor> {
  const { data } = await api.post<Conductor>(
    "recoleccion/conductores/",
    datos,
  );

  return data;
}
