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
