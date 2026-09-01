import api from "./api";


/*
  Liberación de producto.

  Nada de lo que se muestra aquí está guardado: el avance documental y el
  veredicto de calidad los calcula el backend en cada llamada
  (MODELO_DATOS.md §2.2 y §2.6). Por eso, tras completar un formulario, hay
  que volver a pedir el expediente en vez de recalcularlo en el navegador:
  la regla vive en un solo sitio y ese sitio es el servidor.
*/


/* Un campo de la plantilla de un documento. Lo que la pantalla dibuja. */
export interface CampoPlantilla {
  clave: string;
  etiqueta: string;
  tipo:
    | "texto"
    | "entero"
    | "decimal"
    | "fecha"
    | "fechaHora"
    | "hora"
    | "booleano"
    | "enum"
    | "lista"
    | "objeto";
  req?: boolean;
  unidad?: string;
  valores?: string[];
  min?: number;
  max?: number;
  /* Lo ata a un fisicoquímico: se coteja contra el análisis del lote. */
  parametro?: string;
  /* Lo rellena con lo que el sistema ya sabe, p. ej. "lote.codigo_lote". */
  origen?: string;
  campos?: CampoPlantilla[];
}


export interface DocumentoLiberacion {
  id: number;
  codigo: string;
  nombre: string;
  aplica_a: string[];
  instruccion: string;
  plantilla: CampoPlantilla[];
  campos: number;
  fuente: string;
  orden: number;
  activo: boolean;
}


export type EstadoRegistro = "borrador" | "completado" | "observado";


export interface RegistroCalidad {
  id: number;
  lote: number;
  documento: number;
  documento_nombre: string;
  estado: EstadoRegistro;
  estado_etiqueta: string;
  valores: Record<string, unknown>;
  referencia: string;
  completado_por_nombre: string | null;
  completado_en: string | null;
  observacion: string;
  completo: boolean;
  faltantes: string[];
}


export interface Liberacion {
  id: number;
  lote: number;
  lote_codigo: string;
  producto_nombre: string;
  estado: "pendiente" | "en_revision" | "liberado" | "liberado_concesion" | "rechazado";
  estado_etiqueta: string;
  autorizada_por_nombre: string | null;
  autorizada_en: string | null;
  concesion: boolean;
  motivo_concesion: string;
  observacion: string;
  liberado: boolean;
}


export interface ResultadoCalidad {
  resultado: "conforme" | "no_conforme" | "sin_analisis" | "sin_especificacion";
  etiqueta: string;
  evaluados: number;
  desviaciones: {
    analisis_id: number;
    muestra: string;
    parametro: string;
    valor: number;
    min: number | null;
    max: number | null;
    desvio: string | null;
  }[];
  especificacion_id: number | null;
}


export interface Avance {
  completados: number;
  total: number;
  pct: number;
  completo: boolean;
}


export interface EstadoDocumento {
  documento: DocumentoLiberacion;
  registro: RegistroCalidad | null;
  completo: boolean;
  observado: boolean;
  iniciado: boolean;
  /* Lo cumple el registro del sistema, no una casilla: hay control de
     proceso, hay análisis, hay monitoreo. Se distingue porque no es lo mismo
     que alguien lo haya marcado. */
  cumplido_por_dato: boolean;
  faltantes: string[];
}


export interface Discrepancia {
  tipo: "fuera_de_especificacion" | "discrepa_del_analisis";
  parametro: string;
  etiqueta: string;
  declarado: number;
  min: number | null;
  max: number | null;
  medidos: number[];
  mensaje: string;
}


export interface LoteResumen {
  id: number;
  codigo_lote: string;
  fecha: string;
  producto_nombre: string;
  mandante_nombre: string;
  familia: string;
  kg_producidos: string;
  estado: string;
}


export interface FilaExpediente {
  lote: LoteResumen;
  liberacion: Liberacion | null;
  avance: Avance;
  calidad: ResultadoCalidad | null;
  permitido: boolean;
  via_concesion: boolean;
  bloqueos: string[];
  rework: {
    id: number;
    origen: string;
    estado: "pendiente" | "aprobado" | "bloqueado" | "destruido";
    cantidad_kg: string;
    motivo: string;
    observacion_calidad: string;
    solicitado_por: string | null;
    solicitado_en: string;
    decidido_por: string | null;
    decidido_en: string | null;
  } | null;
}

export interface AnalisisResultadoProceso {
  id: number;
  tomado_en: string;
  ph: string | null;
  acidez: string | null;
  grasa: string | null;
  sng: string | null;
  proteina: string | null;
  densidad: string | null;
  resultado: "conforme" | "no_conforme" | "sin_analisis" | "sin_especificacion" | null;
  faltantes: string[];
  desviaciones: Array<{
    parametro: string;
    valor: number | null;
    min: number | null;
    max: number | null;
  }>;
}

export interface ResultadoProcesoCalidad {
  id: number;
  tipo: string;
  corrida_codigo: string;
  lote_codigo: string;
  producto_nombre: string;
  equipo_nombre: string | null;
  silo_destino_codigo: string;
  cantidad: string;
  unidad: string;
  clasificacion: string;
  destino: string;
  estado: "pendiente" | "liberado" | "rechazado";
  observacion: string;
  decidida_en: string | null;
  analisis_seleccionado: number | null;
  especificacion: {
    version: number;
    rangos: Record<string, { min?: number; max?: number; obligatorio?: boolean }>;
  } | null;
  analisis_disponibles: AnalisisResultadoProceso[];
}

export interface RespuestaExpedientes {
  resultados: FilaExpediente[];
  procesos: ResultadoProcesoCalidad[];
  total: number;
  pagina: number;
  limite: number;
  hay_mas: boolean;
}


export interface Expediente {
  lote: LoteResumen;
  liberacion: Liberacion | null;
  decision: {
    permitido: boolean;
    via_concesion: boolean;
    bloqueos: string[];
    calidad: ResultadoCalidad | null;
    avance: (Avance & { detalle: EstadoDocumento[] }) | null;
  };
  /* Por id de documento. */
  discrepancias: Record<string, Discrepancia[]>;
  prellenado: Record<string, Record<string, unknown>>;
  especificacion: {
    id: number;
    version: number;
    fuente: string;
    parametros: {
      clave: string;
      etiqueta: string;
      unidad: string;
      min: number | null;
      max: number | null;
      obligatorio: boolean;
    }[];
  } | null;
  analisis: {
    id: number;
    fecha: string;
    muestra: string;
    valores: Record<string, number>;
    observacion: string;
  }[];
}


export const ESTADOS_LIBERACION = [
  { valor: "pendiente", etiqueta: "Pendiente" },
  { valor: "en_revision", etiqueta: "En revisión" },
  { valor: "liberado", etiqueta: "Liberado" },
  { valor: "liberado_concesion", etiqueta: "Liberado bajo concesión" },
  { valor: "rechazado", etiqueta: "Rechazado" },
];


/*
  El listado de expedientes viene **paginado**, y no por comodidad: cada fila
  evalúa en el servidor el checklist y el veredicto de su lote en memoria, así
  que sin techo el coste crecía con el histórico completo hasta agotar el
  tiempo de la función.

  `total` es el de la consulta, no el de la página: es lo que permite decir
  «50 de 954» en vez de dar a entender que no hay más.
*/
export async function buscarExpedientes(
  filtros: {
    estado?: string;
    desde?: string;
    hasta?: string;
    pagina?: number;
    incluir_procesos?: boolean;
  } = {},
): Promise<RespuestaExpedientes> {

  const { data } = await api.get("calidad/expedientes/", {
    params: {
      estado: filtros.estado || undefined,
      desde: filtros.desde || undefined,
      hasta: filtros.hasta || undefined,
      pagina: filtros.pagina && filtros.pagina > 1 ? filtros.pagina : undefined,
      incluir_procesos: filtros.incluir_procesos ? 1 : undefined,
    },
  });

  return data;
}

export async function liberarResultadoProceso(
  corridaId: number, analisisId: number, observacion = "",
): Promise<void> {
  await api.post(`calidad/resultados-proceso/${corridaId}/liberar/`, {
    analisis_id: analisisId,
    observacion,
  });
}

export async function rechazarResultadoProceso(
  corridaId: number, motivo: string,
): Promise<void> {
  await api.post(`calidad/resultados-proceso/${corridaId}/rechazar/`, { motivo });
}


export async function obtenerExpediente(loteId: number): Promise<Expediente> {
  const { data } = await api.get<Expediente>(`calidad/expedientes/${loteId}/`);

  return data;
}


export async function guardarRegistro(registro: {
  id?: number;
  lote: number;
  documento: number;
  estado: EstadoRegistro;
  valores: Record<string, unknown>;
  referencia?: string;
  observacion?: string;
}): Promise<RegistroCalidad> {

  if (registro.id) {
    const { data } = await api.patch<RegistroCalidad>(
      `calidad/registros/${registro.id}/`,
      registro,
    );

    return data;
  }

  const { data } = await api.post<RegistroCalidad>("calidad/registros/", registro);

  return data;
}


/**
 * Firma la liberación normal.
 *
 * El backend responde 409 con los bloqueos si la regla no se cumple. Ese
 * rechazo es el que vale: la pantalla apaga el botón por cortesía, pero
 * quien lo fuerce se encuentra igual con el servidor.
 */
export async function liberar(loteId: number, observacion = ""): Promise<Liberacion> {
  const { data } = await api.post<Liberacion>(
    `calidad/expedientes/${loteId}/liberar/`,
    { observacion },
  );

  return data;
}

export async function enviarPalletsBodega(loteId: number): Promise<{
  lote: number; enviados: number; pallets: number; ubicacion: string; detail: string;
}> {
  const { data } = await api.post(
    `calidad/expedientes/${loteId}/enviar-bodega/`,
  );
  return data;
}


/** Liberación bajo concesión: exige motivo escrito y deja marca permanente. */
export async function conceder(
  loteId: number,
  motivo: string,
  observacion = "",
): Promise<Liberacion> {

  const { data } = await api.post<Liberacion>(
    `calidad/expedientes/${loteId}/conceder/`,
    { motivo, observacion },
  );

  return data;
}

export async function bloquearLote(loteId: number, motivo: string): Promise<Liberacion> {
  const { data } = await api.post<Liberacion>(
    `calidad/expedientes/${loteId}/bloquear/`, { motivo },
  );
  return data;
}

export async function decidirRework(
  loteId: number,
  datos: {
    estado: "aprobado" | "bloqueado" | "destruido";
    origen: "rechazo" | "saco_danado" | "excedente" | "recuperable";
    cantidad_kg: number;
    motivo: string;
    observacion_calidad?: string;
  },
): Promise<void> {
  await api.post(`calidad/expedientes/${loteId}/rework/`, datos);
}
