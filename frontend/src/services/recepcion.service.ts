import api from "./api";

import type { Pagina } from "./produccion.service";


export interface Silo {
  id: number;
  codigo: string;
  tipo: string;
  tipo_etiqueta: string;
  capacidad_l: string;
  activo: boolean;
}


export interface Vehiculo {
  id: number;
  placa: string;
  numero: string;
  transportista: string;
}


export interface OcupacionSilo {
  silo_id: number;
  codigo: string;
  litros: number;
  capacidad: number;
  pct: number;
  /* Por encima de la capacidad. */
  excedido: boolean;
  /* Saldo negativo: imposible físicamente, señal de que el registro está
     descuadrado. Se informa, no se oculta. */
  negativo: boolean;
}


export interface Ocupacion {
  silos: OcupacionSilo[];
  litros_totales: number;
  alertas: { excedidos: string[]; negativos: string[] };
}


export interface EvaluacionRecepcion {
  /* Nada de lo medido se salió de rango. NO significa que se pueda liberar:
     para eso hay que haber medido lo decisivo. */
  conforme: boolean;
  estado_sugerido: "liberada" | "retenida" | "sin_analisis";
  motivos: string[];
  /* Controles decisivos sin informar. Con alguno pendiente no se libera. */
  faltantes: string[];
  analizada: boolean;
}


export interface Recepcion {
  id: number;
  fecha: string;
  hora: string | null;
  guia: string;
  vehiculo: number | null;
  vehiculo_placa: string | null;
  procedencia: string;
  tipo_leche: string;
  litros: string;
  silo: number | null;
  silo_codigo: string | null;
  operador_nombre: string;
  turno: string;
  controles: Record<string, number | string>;
  estado: string;
  estado_etiqueta: string;
  motivo: string;
  observacion: string;
  evaluacion: EvaluacionRecepcion;
}


export interface RecepcionNueva {
  fecha: string;
  tipo_leche: string;
  litros: string;
  silo?: number;
  vehiculo?: number;
  procedencia?: string;
  turno?: string;
  guia?: string;
  controles: Record<string, number | string>;
  estado?: string;
  motivo?: string;
  observacion?: string;
}


/* Los controles del camión, tal como los declara el backend. */
export const CONTROLES_NUMERICOS = [
  { clave: "temperatura", etiqueta: "Temperatura", unidad: "°C" },
  { clave: "acidez", etiqueta: "Acidez", unidad: "°D" },
  { clave: "ph", etiqueta: "pH", unidad: "" },
  { clave: "crioscopia", etiqueta: "Crioscopía", unidad: "°C" },
];

export const CONTROLES_OPCION = [
  { clave: "delvo", etiqueta: "Delvo Test", valores: ["Negativo", "Positivo"] },
  { clave: "inhibidores", etiqueta: "Inhibidores", valores: ["Negativo", "Positivo"] },
  {
    clave: "organoleptico",
    etiqueta: "Organoléptico",
    valores: ["Conforme", "No conforme"],
  },
];

export const ESTADOS_RECEPCION = [
  { valor: "registrada", etiqueta: "Registrada" },
  { valor: "muestreada", etiqueta: "Muestreada" },
  { valor: "analizada", etiqueta: "Analizada" },
  { valor: "liberada", etiqueta: "Liberada" },
  { valor: "retenida", etiqueta: "Retenida" },
  { valor: "descargada", etiqueta: "Descargada" },
  { valor: "cerrada", etiqueta: "Cerrada" },
];


export async function obtenerOcupacion(): Promise<Ocupacion> {
  const { data } = await api.get<Ocupacion>("recepcion/ocupacion/");

  return data;
}


export async function buscarRecepciones(
  filtros: { estado?: string; silo?: string; pagina?: number } = {},
): Promise<Pagina<Recepcion>> {

  const { data } = await api.get<Pagina<Recepcion>>("recepcion/recepciones/", {
    params: {
      estado: filtros.estado || undefined,
      silo: filtros.silo || undefined,
      page: filtros.pagina && filtros.pagina > 1 ? filtros.pagina : undefined,
    },
  });

  return data;
}


export async function crearRecepcion(recepcion: RecepcionNueva): Promise<Recepcion> {
  const { data } = await api.post<Recepcion>("recepcion/recepciones/", recepcion);

  return data;
}


/**
 * Descarga la recepción al silo: crea el ingreso en el libro mayor.
 *
 * El backend responde 409 si la recepción no está liberada, que es la regla
 * que impide que entre al silo leche retenida.
 */
export async function descargarRecepcion(id: number): Promise<Recepcion> {
  const { data } = await api.post<Recepcion>(
    `recepcion/recepciones/${id}/descargar/`,
  );

  return data;
}


export async function obtenerSilos(): Promise<Silo[]> {
  const { data } = await api.get<Pagina<Silo>>("maestros/silos/");

  return data.results;
}


export async function obtenerVehiculos(): Promise<Vehiculo[]> {
  const { data } = await api.get<Pagina<Vehiculo>>("maestros/vehiculos/");

  return data.results;
}
