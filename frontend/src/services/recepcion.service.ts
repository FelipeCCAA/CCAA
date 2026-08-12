import api from "./api";

import type { Pagina } from "./produccion.service";


export interface Silo {
  id: number;
  codigo: string;
  tipo: string;
  tipo_etiqueta: string;
  capacidad_l: string;
  litros_disponibles?: string;
  capacidad_disponible?: string;
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
  carga_recoleccion: number | null;
  fecha: string;
  hora: string | null;
  guia: string;
  vehiculo: number | null;
  vehiculo_placa: string | null;
  modulo: string;
  procedencia: string;
  tipo_leche: string;
  litros: string;
  silo: number | null;
  silo_codigo: string | null;
  operador_nombre: string;
  turno: string;
  controles: Record<string, number | string>;
  controles_camion: Record<string, number | string>;
  controles_modulo: Record<string, number | string>;
  estado: string;
  estado_etiqueta: string;
  motivo: string;
  observacion: string;
  codigo_muestra: string;
  muestreado_por: number | null;
  muestreado_por_nombre: string;
  muestreado_en: string | null;
  calidad_por: number | null;
  calidad_por_nombre: string;
  calidad_en: string | null;
  silo_asignado_por: number | null;
  silo_asignado_por_nombre: string;
  silo_asignado_en: string | null;
  evaluacion: EvaluacionRecepcion;
}

export interface ResponsableRecepcion {
  id: number;
  nombre: string;
  turno: string;
}

export interface CatalogosFlujoRecepcion {
  responsables_recepcion: ResponsableRecepcion[];
  controles_camion: string[];
  controles_modulo: string[];
}


export interface RecepcionNueva {
  fecha: string;
  carga_recoleccion?: number;
  hora?: string;
  tipo_leche: string;
  litros: string;
  silo?: number;
  vehiculo?: number;
  procedencia?: string;
  turno?: string;
  guia?: string;
  modulo?: string;
  controles?: Record<string, number | string>;
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
  { valor: "registrada", etiqueta: "En espera de muestra" },
  { valor: "muestreada", etiqueta: "Muestra tomada" },
  { valor: "analizada", etiqueta: "Analizada" },
  { valor: "liberada", etiqueta: "Aprobada por Calidad" },
  { valor: "retenida", etiqueta: "Retenida" },
  { valor: "descargada", etiqueta: "Descargada" },
  { valor: "cerrada", etiqueta: "Cerrada" },
];


export async function obtenerOcupacion(): Promise<Ocupacion> {
  const { data } = await api.get<Ocupacion>("recepcion/ocupacion/");

  return data;
}


/*
  `estado` admite varios separados por coma —«Calidad» son las muestreadas y
  las retenidas— y `q` **se manda al servidor**. Filtrar en el navegador solo
  alcanzaba a las cincuenta filas descargadas: buscar una guía de la semana
  pasada respondía «no encontramos recepciones» sobre algo que sí existía.
*/
export async function buscarRecepciones(
  filtros: {
    estado?: string;
    silo?: string;
    q?: string;
    pagina?: number;
  } = {},
): Promise<Pagina<Recepcion>> {

  const { data } = await api.get<Pagina<Recepcion>>("recepcion/recepciones/", {
    params: {
      estado: filtros.estado || undefined,
      silo: filtros.silo || undefined,
      q: filtros.q?.trim() || undefined,
      page: filtros.pagina && filtros.pagina > 1 ? filtros.pagina : undefined,
    },
  });

  return data;
}


export interface ResumenRecepcion {
  por_estado: Record<string, number>;
  total: number;
  liberadas_sin_silo: number;
  liberadas_con_silo: number;
}


/*
  Los contadores del panel, **calculados sobre el total**.

  Antes se contaban sobre la página cargada: con más de cincuenta recepciones
  dejaban de decir la verdad, y al filtrar la tabla por un estado mostraban
  ceros en el resto, como si la planta se hubiera vaciado.
*/
export async function obtenerResumen(): Promise<ResumenRecepcion> {
  const { data } = await api.get<ResumenRecepcion>(
    "recepcion/recepciones/resumen/",
  );

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


export async function tomarMuestra(
  id: number,
  codigo_muestra: string,
  responsable: number,
): Promise<Recepcion> {
  const { data } = await api.post<Recepcion>(
    `recepcion/recepciones/${id}/tomar-muestra/`,
    { codigo_muestra, responsable },
  );
  return data;
}

export async function obtenerCatalogosFlujo(): Promise<CatalogosFlujoRecepcion> {
  const { data } = await api.get<CatalogosFlujoRecepcion>(
    "recepcion/recepciones/catalogos-flujo/",
  );
  return data;
}


export async function decidirCalidad(
  id: number,
  controles: Record<string, number | string>,
  decision?: "retener",
  motivo?: string,
): Promise<Recepcion> {
  const { data } = await api.post<Recepcion>(
    `recepcion/recepciones/${id}/decidir-calidad/`,
    { controles, decision, motivo },
  );
  return data;
}


export async function asignarSilo(id: number, silo: number): Promise<Recepcion> {
  const { data } = await api.post<Recepcion>(
    `recepcion/recepciones/${id}/asignar-silo/`,
    { silo },
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
