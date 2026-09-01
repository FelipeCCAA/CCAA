import api from "./api";
import type { Equipo } from "./maestros.service";


/* Los listados de DRF vienen paginados. */
export interface Pagina<T> {
  count: number;
  next: string | null;
  previous: string | null;
  results: T[];
}


export type ResultadoCalidad =
  | "conforme"
  | "no_conforme"
  | "sin_analisis"
  | "sin_especificacion";


/* Los cuatro veredictos posibles, para poblar filtros. Reflejan las
   constantes de produccion/dominio.py. */
export const RESULTADOS: { valor: ResultadoCalidad; etiqueta: string }[] = [
  { valor: "conforme", etiqueta: "Conforme" },
  { valor: "no_conforme", etiqueta: "No conforme" },
  { valor: "sin_analisis", etiqueta: "Sin análisis" },
  { valor: "sin_especificacion", etiqueta: "Sin especificación" },
];


export interface Desviacion {
  analisis_id: number;
  muestra: string;
  parametro: string;
  valor: number | null;
  min: number | null;
  max: number | null;
  desvio: "bajo" | "alto" | null;
}


export interface CalidadLote {
  resultado: ResultadoCalidad;
  etiqueta: string;
  evaluados: number;
  desviaciones: Desviacion[];
  especificacion_id: number | null;
}


const FORMATO_KG = new Intl.NumberFormat("es-CL", { maximumFractionDigits: 0 });


/**
 * Kilos de un lote, o un guion si todavía no se declararon.
 *
 * Existe porque `Number(null)` es 0: un lote en proceso mostraría "0 kg" y
 * diría que no produjo nada, cuando lo cierto es que aún no se sabe cuánto.
 */
export function kilos(valor: string | number | null | undefined): string {
  if (valor == null || valor === "") {
    return "—";
  }

  return `${FORMATO_KG.format(Number(valor))} kg`;
}


export type EstadoLote = "en_proceso" | "producido" | "cerrado" | "anulado";


/*
  Transiciones válidas entre estados de un lote.

  Refleja `Lote.TRANSICIONES` del backend, que es quien manda: esto solo
  sirve para no ofrecer un botón que el servidor va a rechazar. Un lote
  cerrado o anulado es final — el histórico se audita, y un lote anulado que
  vuelve a producción es un registro que dice algo falso sobre lo que pasó.
*/
export const TRANSICIONES: Record<EstadoLote, EstadoLote[]> = {
  en_proceso: ["producido", "anulado"],
  producido: ["cerrado", "anulado"],
  cerrado: [],
  anulado: [],
};

export const ETIQUETA_ESTADO: Record<EstadoLote, string> = {
  en_proceso: "En proceso",
  producido: "Producido",
  cerrado: "Cerrado",
  anulado: "Anulado",
};

/* Qué significa cada paso, para que el botón diga la consecuencia y no solo
   el nombre del estado. */
export const EXPLICACION_ESTADO: Record<EstadoLote, string> = {
  en_proceso: "El lote sigue en la línea.",
  producido:
    "Cierra la producción. Desde aquí el lote llega a Calidad y puede liberarse.",
  cerrado: "El lote queda cerrado. Es un estado final: no admite vuelta atrás.",
  anulado:
    "El lote no existió como producción. Es un estado final: no admite vuelta atrás.",
};


export interface Analisis {
  id: number;
  lote: number;
  fecha: string;
  muestra: string;
  valores: Record<string, number>;
  observacion: string;
}


export interface Lote {
  id: number;
  codigo_lote: string;
  op: string;
  producto: number;
  producto_nombre: string;
  mandante_nombre: string;
  vale: number | null;
  vale_codigo: string | null;
  silo_estandarizado_codigo: string | null;
  litros_procesados: number | null;
  equipo: number | null;
  equipo_nombre: string | null;
  ejecucion: number | null;
  ejecucion_codigo: string | null;
  fecha: string;
  linea: string;
  turno: string;
  /* Django serializa los decimales como texto, para no perder precisión.
     null mientras el lote está en proceso: todavía no se sabe cuántos. */
  kg_producidos: string | null;
  bultos: number | null;
  hora_inicio: string | null;
  hora_termino: string | null;
  vencimiento: string | null;
  estado: EstadoLote;
  estado_etiqueta: string;
  observacion: string;
  calidad: CalidadLote;
}

export interface PalletProducto {
  id: number;
  codigo: string;
  unidades: number;
  kg_neto: string;
  estado: string;
  estado_etiqueta: string;
  lote_codigo?: string;
  producto_nombre?: string;
}

export async function obtenerPallets(): Promise<Pagina<PalletProducto>> {
  const { data } = await api.get<Pagina<PalletProducto>>("produccion/pallets/");
  return data;
}


/* El lote con sus análisis: lo que devuelve el detalle. */
export interface LoteDetalle extends Lote {
  analisis: Analisis[];
  /* null si Calidad no ha tramitado el expediente todavía. */
  liberacion: {
    estado: string;
    estado_etiqueta: string;
    liberado: boolean;
    autorizada_por_nombre: string | null;
  } | null;
  /* Si el material del lote se descontó de bodega. `pendiente` es cierto
     cuando el lote ya está producido y el descuento no ocurrió: un descuento
     que falló y no se ve deja el saldo de bodega alto sin que nadie lo sepa. */
  consumo_inventario: {
    registrado: boolean;
    registrado_en: string | null;
    kg_base: string | null;
    pendiente: boolean;
  };
  pallets_resumen: {
    total: number;
    pendientes_calidad: number;
    liberados: number;
    en_inventario: number;
  };
  /* Solo viene en la respuesta de un PATCH que cambió algo digno de avisar.
     No bloquean: informan. */
  avisos?: string[];
}


export interface Resumen {
  lotes: number;
  kg_producidos: number;
  calidad: {
    conforme: number;
    no_conforme: number;
    sin_analisis: number;
    sin_especificacion: number;
    evaluados: number;
    /* null cuando no hay lotes: el backend no inventa porcentajes. */
    cobertura: number | null;
    cumplimiento: number | null;
  };
  kg_por_producto: { nombre: string; kg: number }[];
  kg_por_mandante: { nombre: string; kg: number }[];
}


export interface Producto {
  id: number;
  codigo: string;
  nombre: string;
  familia: string;
  familia_etiqueta: string;
  mandante: number;
  mandante_nombre: string;
  activo: boolean;
}


export interface Parametro {
  clave: string;
  etiqueta: string;
  unidad: string;
}


export interface FiltrosLotes {
  producto?: string;
  calidad?: string;
  buscar?: string;
  pagina?: number;
  estado?: EstadoLote;
}


/**
 * Campos para abrir un proceso. Los opcionales se omiten si van vacíos.
 *
 * `kg_producidos` no está: los kilos se saben cuando la corrida termina, y se
 * declaran al marcar el lote como producido. Exigirlos aquí es lo que obligaba
 * a registrar el lote —y con él toda su trazabilidad— al final del día.
 */
export interface LoteNuevo {
  codigo_lote: string;
  producto: number;
  vale: number;
  litros_estandarizados: number;
  equipo?: number;
  fecha: string;
  op?: string;
  linea?: string;
  turno?: string;
  bultos?: number;
  observacion?: string;
}

export interface ValeDisponible {
  id: number;
  codigo: string;
  fecha: string;
  producto: number;
  producto_nombre: string;
  producto_familia: string;
  mandante_nombre: string;
  rc_objetivo: string;
  rc_real: number | null;
  litros_preparados: string;
  litros_usados: string;
  litros_disponibles: string;
  silo_entera_codigo: string;
  silo_descremada_codigo: string | null;
  silo_destino_codigo: string;
}

export interface RegistroEnvaseCreado {
  id: number;
  lote: number;
  formato_kg: string;
  unidades: number;
  kg_envasados: string;
  pallets: PalletProducto[];
  lote_codigo?: string;
  equipo_nombre?: string;
  creado_en?: string;
}

export async function registrarEnvase(datos: {
  lote: number;
  equipo: number;
  formato_kg: number;
  inicio: string;
  termino: string;
  observacion?: string;
  pallets_datos: Array<{ codigo: string; unidades: number; kg_neto: number }>;
}): Promise<RegistroEnvaseCreado> {
  const { data } = await api.post<RegistroEnvaseCreado>("produccion/envases/", datos);
  return data;
}

export async function obtenerRegistrosEnvase(): Promise<Pagina<RegistroEnvaseCreado>> {
  const { data } = await api.get<Pagina<RegistroEnvaseCreado>>("produccion/envases/");
  return data;
}

export interface EquipoInicioProduccion extends Equipo {
  habilitado: boolean;
  motivo_no_habilitado: string;
  aseo_verificacion: "pendiente" | "conforme" | "observado" | null;
  advertencia_aseo: string;
}

export interface OpcionesInicioProduccion {
  entradas: ValeDisponible[];
  equipos: EquipoInicioProduccion[];
  ordenes: {
    id: number; codigo: string; producto: number; producto_nombre: string;
    cantidad_planificada: string; unidad: string; estado: string;
  }[];
}

export async function obtenerOpcionesInicioProduccion(): Promise<OpcionesInicioProduccion> {
  const { data } = await api.get<OpcionesInicioProduccion>(
    "produccion/lotes/opciones-inicio/",
  );
  return data;
}

export async function obtenerValesDisponibles(
  producto?: number,
): Promise<ValeDisponible[]> {
  const { data } = await api.get<ValeDisponible[]>(
    "produccion/lotes/vales-disponibles/",
    { params: { producto: producto || undefined } },
  );
  return data;
}


export interface CodigoSugerido {
  /* null cuando el producto no tiene SKU cargado: se escribe a mano y el
     motivo dice qué falta y dónde. */
  codigo: string | null;
  /* Qué número de lote de ese producto es en la fecha. */
  correlativo: number;
  motivo: string | null;
}


/**
 * El código que le tocaría a este lote.
 *
 * Se compone de año, día juliano, SKU del producto y correlativo del día. El
 * correlativo lo cuenta el servidor a partir de los lotes que ya existen:
 * preguntárselo al operador sería pedirle un dato que el sistema ya tiene.
 *
 * Se sugiere, no se impone: el histórico de planta trae códigos con otra
 * forma —todos los del POE.009.02 anterior— y hay que poder registrarlos.
 */
export async function sugerirCodigoLote(
  equipo: number,
  fecha: string,
): Promise<CodigoSugerido> {

  const { data } = await api.get<CodigoSugerido>(
    "produccion/lotes/codigo-sugerido/",
    { params: { equipo, fecha } },
  );

  return data;
}


export async function obtenerResumen(): Promise<Resumen> {
  const { data } = await api.get<Resumen>("produccion/resumen/");

  return data;
}


export async function obtenerLotes(limite = 8): Promise<Lote[]> {
  const { data } = await api.get<Pagina<Lote>>("produccion/lotes/");

  return data.results.slice(0, limite);
}


export async function buscarLotes(
  filtros: FiltrosLotes = {},
): Promise<Pagina<Lote>> {

  const { data } = await api.get<Pagina<Lote>>("produccion/lotes/", {
    // axios omite los parámetros en undefined, así que un filtro vacío
    // simplemente no viaja.
    params: {
      producto: filtros.producto || undefined,
      calidad: filtros.calidad || undefined,
      buscar: filtros.buscar || undefined,
      estado: filtros.estado || undefined,
      page: filtros.pagina && filtros.pagina > 1 ? filtros.pagina : undefined,
    },
  });

  return data;
}


export async function obtenerProductos(): Promise<Producto[]> {
  const { data } = await api.get<Pagina<Producto>>("maestros/productos/");

  return data.results;
}


export async function obtenerParametros(): Promise<Parametro[]> {
  const { data } = await api.get<Parametro[]>("maestros/parametros/");

  return data;
}


export async function crearLote(lote: LoteNuevo): Promise<Lote> {
  const { data } = await api.post<Lote>("produccion/lotes/", lote);

  return data;
}

export interface DatosBorradorLote {
  codigo_lote_propuesto: string;
  producto?: number | null;
  vale: number | null;
  litros_estandarizados_borrador: number | null;
  equipo: number | null;
  orden: number | null;
  fecha: string;
  op: string;
  linea: string;
  turno: string;
  observacion: string;
}

export interface BorradorLote extends DatosBorradorLote {
  id: number;
  codigo_lote: string;
  estado: "borrador";
  actualizado_en: string;
}

export async function obtenerBorradorLote(): Promise<BorradorLote | null> {
  const respuesta = await api.get<BorradorLote>("produccion/lotes/mi-borrador/");
  return respuesta.status === 204 ? null : respuesta.data;
}

export async function crearBorradorLote(datos: DatosBorradorLote) {
  const { data } = await api.post<BorradorLote>(
    "produccion/lotes/crear-borrador/", datos,
  );
  return data;
}

export async function guardarBorradorLote(id: number, datos: DatosBorradorLote) {
  const { data } = await api.patch<BorradorLote>(
    `produccion/lotes/${id}/guardar-borrador/`, datos,
  );
  return data;
}

export async function confirmarBorradorLote(id: number) {
  const { data } = await api.post<Lote>(
    `produccion/lotes/${id}/confirmar-borrador/`,
  );
  return data;
}

export async function descartarBorradorLote(id: number) {
  await api.post(`produccion/lotes/${id}/descartar-borrador/`);
}


export async function crearAnalisis(
  loteId: number,
  fecha: string,
  valores: Record<string, number>,
  muestra = "",
): Promise<void> {
  await api.post("produccion/analisis/", {
    lote: loteId,
    fecha,
    muestra,
    valores,
  });
}

export async function actualizarAnalisis(
  analisisId: number,
  fecha: string,
  valores: Record<string, number>,
  muestra = "",
): Promise<void> {
  await api.patch(`produccion/analisis/${analisisId}/`, {
    fecha,
    muestra,
    valores,
  });
}


export async function obtenerLote(id: number): Promise<LoteDetalle> {
  const { data } = await api.get<LoteDetalle>(`produccion/lotes/${id}/`);

  return data;
}


/** Campos editables de un lote. Todos opcionales: se manda lo que cambió. */
export interface LoteEditado {
  codigo_lote?: string;
  op?: string;
  producto?: number;
  fecha?: string;
  linea?: string;
  turno?: string;
  kg_producidos?: string;
  bultos?: number | null;
  hora_inicio?: string | null;
  hora_termino?: string | null;
  vencimiento?: string | null;
  observacion?: string;
}


/**
 * Edita los datos de un lote.
 *
 * El backend rechaza con 400 si el lote está cerrado o anulado —es histórico—
 * o si Calidad ya lo liberó, porque cambiar lo que se produjo dejaría esa
 * firma respaldando otra cosa. La observación se puede anotar siempre.
 */
export async function editarLote(
  id: number,
  cambios: LoteEditado,
  motivoCorreccion?: string,
): Promise<LoteDetalle> {

  const { data } = await api.patch<LoteDetalle>(`produccion/lotes/${id}/`, {
    ...cambios,
    ...(motivoCorreccion ? { motivo_correccion: motivoCorreccion } : {}),
  });

  return data;
}


/**
 * Cambia el estado de un lote.
 *
 * El backend valida la transición contra `Lote.TRANSICIONES` y responde 400
 * con el motivo si no es válida. Ese rechazo es el que vale: la pantalla solo
 * oculta los pasos imposibles por cortesía.
 */
export async function cambiarEstadoLote(
  id: number,
  estado: EstadoLote,
  kgProducidos?: string,
  motivoAnulacion?: string,
): Promise<LoteDetalle> {

  // Los kilos viajan con el cambio de estado, no antes: declarar y cerrar la
  // producción es un solo gesto, y en dos llamadas un fallo entre medio
  // dejaría los kilos escritos en un lote que sigue abierto.
  const { data } = await api.patch<LoteDetalle>(`produccion/lotes/${id}/`, {
    estado,
    ...(kgProducidos ? { kg_producidos: kgProducidos } : {}),
    ...(motivoAnulacion ? { motivo_anulacion: motivoAnulacion } : {}),
  });

  return data;
}


/* ---------------------------------------------------------------- asignación

   De qué silos salió la leche de un lote. Aquí empieza la trazabilidad: un
   lote puede mezclar leche de varios estanques, y cada línea es un asiento
   del libro mayor.
*/

export interface LineaAsignacion {
  id: number;
  silo: number;
  silo_codigo: string;
  litros: number;
  fecha_hora: string;
}

export interface Asignacion {
  lote: string;
  estado: string;
  editable: boolean;
  motivo_bloqueo: string | null;
  lineas: LineaAsignacion[];
  /* Lo que Producción declaró haber tomado del silo: el hecho. */
  asignado: number;
  /* Lo que la receta decía que costaba: la expectativa. null si no hay receta. */
  teorico: number | null;
  diferencia: number | null;
  /* Asignado sobre teórico. Bajo 100 se usó menos leche; sobre 100, más. En
     ese orden: la razón inversa sube al consumir menos, y se leería como un
     logro cuando suele significar que falta cargar una línea. */
  consumo_pct: number | null;
  /* El rendimiento como lo mide la planta: leche que costó cada kilo. */
  litros_por_kg: number | null;
  litros_por_kg_receta: number | null;
}

export interface RecepcionCandidata {
  id: number;
  fecha: string;
  guia: string;
  litros: string;
  procedencia: string;
  vehiculo: string | null;
}

export interface Trazabilidad {
  lote: string;
  tramos: {
    silo: number;
    silo_codigo: string;
    litros: number;
    fecha_hora: string;
    recepciones: RecepcionCandidata[];
  }[];
  nota: string;
}


export async function obtenerAsignacion(loteId: number): Promise<Asignacion> {
  const { data } = await api.get<Asignacion>(
    `produccion/lotes/${loteId}/asignacion/`,
  );

  return data;
}


export async function asignarLeche(
  loteId: number,
  asignaciones: { silo: number; litros: number }[],
): Promise<Asignacion> {

  const { data } = await api.post<Asignacion>(
    `produccion/lotes/${loteId}/asignacion/`,
    { asignaciones },
  );

  return data;
}


export async function quitarAsignacion(
  loteId: number,
  movimientoId: number,
): Promise<Asignacion> {

  const { data } = await api.delete<Asignacion>(
    `produccion/lotes/${loteId}/asignacion/${movimientoId}/`,
  );

  return data;
}


export async function obtenerTrazabilidad(loteId: number): Promise<Trazabilidad> {
  const { data } = await api.get<Trazabilidad>(
    `produccion/lotes/${loteId}/trazabilidad/`,
  );

  return data;
}
