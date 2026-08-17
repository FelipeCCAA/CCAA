import api from "./api";

export interface Pagina<T> { count: number; next: string | null; previous: string | null; results: T[] }

export interface EjecucionProceso {
  id: number;
  codigo: string;
  estado: string;
  estado_etiqueta: string;
  etapa_nombre: string;
  equipo_nombre: string | null;
  vale_codigo: string | null;
  lote_codigo: string | null;
  producto_nombre: string | null;
  inicio: string | null;
  termino: string | null;
  acciones_permitidas: string[];
  entradas: { id: number; lote: number | null; lote_codigo: string | null; silo: number | null; silo_codigo: string | null; cantidad: string; unidad: string }[];
  salidas: { id: number; lote: number | null; lote_codigo: string | null; silo: number | null; silo_codigo: string | null; cantidad: string; unidad: string; naturaleza: string }[];
}

export interface RutaProducto {
  id: number;
  producto_nombre: string;
  proceso_nombre: string;
  prioridad: number;
  destino: string;
  activa: boolean;
  etapas: { id: number; nombre: string; tipo: string; orden: number }[];
}

export interface CorridaCondensacion {
  id: number;
  ejecucion_codigo: string;
  orden_codigo: string;
  lote_codigo: string;
  equipo_nombre: string | null;
  silo_origen_codigo: string;
  silo_destino_codigo: string;
  litros_entrada: string;
  litros_precondensado: string | null;
  densidad_salida: string | null;
  solidos_salida: string | null;
  estado: string;
  estado_etiqueta: string;
}

export interface CorridaMantequilla {
  id: number;
  ejecucion_codigo: string;
  orden_codigo: string;
  crema_codigo: string;
  mantequilla_codigo: string;
  equipo_nombre: string | null;
  kg_crema: string;
  kg_mantequilla: string | null;
  kg_suero: string;
  kg_merma: string;
  estado: string;
  estado_etiqueta: string;
}

export interface NodoGenealogia {
  id: number;
  codigo: string;
  producto: string;
  fecha: string;
}


/*
  Genealogía de un lote.

  `enlaces` es lo que la hace una genealogía y no una lista: dice qué salió de
  qué. Un `origen → destino` significa que el lote de origen entró a un proceso
  del que salió el de destino.

  `raiz` es el lote por el que se preguntó, que es desde donde hay que dibujar.
*/
export interface Genealogia {
  raiz: number;
  nodos: NodoGenealogia[];
  enlaces: { origen: number; destino: number }[];
  flujo: {
    recepciones: {
      id: number; fecha: string; guia: string; litros: string;
      vehiculo: string | null; silo_codigo: string;
    }[];
    nota_recepciones: string;
    estandarizacion: {
      vale_id: number; vale_codigo: string; ejecucion_id: number | null;
      ejecucion_codigo: string | null;
      silos_origen: { codigo: string; litros: string }[];
      silo_destino: string; rc_objetivo: string; rc_real: number | null;
    };
    produccion: {
      lote_id: number; lote_codigo: string; producto: string; linea: string;
      equipo: string | null; ejecucion_id: number | null;
      ejecucion_codigo: string | null; estado: string;
    };
  } | null;
}

export async function obtenerEjecuciones(): Promise<Pagina<EjecucionProceso>> {
  const { data } = await api.get<Pagina<EjecucionProceso>>("procesos/ejecuciones/");
  return data;
}

export async function obtenerRutasProducto(): Promise<Pagina<RutaProducto>> {
  const { data } = await api.get<Pagina<RutaProducto>>("procesos/rutas-producto/");
  return data;
}

export async function obtenerCondensaciones(): Promise<Pagina<CorridaCondensacion>> {
  const { data } = await api.get<Pagina<CorridaCondensacion>>("procesos/condensaciones/");
  return data;
}

export async function obtenerMantequillas(): Promise<Pagina<CorridaMantequilla>> {
  const { data } = await api.get<Pagina<CorridaMantequilla>>("procesos/mantequillas/");
  return data;
}

/* Acepta el código de lote o el id. En planta se conoce el código —lo que va
   impreso en el saco—, así que es lo que la pantalla pide. */
export async function obtenerGenealogia(
  lote: string | number,
  direccion: "atras" | "adelante",
): Promise<Genealogia> {
  const { data } = await api.get<Genealogia>(
    `procesos/trazabilidad/lotes/${encodeURIComponent(String(lote).trim())}/`,
    { params: { direccion } },
  );

  return data;
}
