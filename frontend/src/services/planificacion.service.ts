import api from "./api";


/*
  Planificación semanal de producción.

  Lo que hay que tener presente al consumir esta API: el balance NO se guarda.
  El consumo, el stock arrastrado y los saldos por origen se calculan en cada
  llamada desde los bloques del programa. Por eso, después de mover un bloque
  hay que volver a pedir el programa entero en vez de recalcular aquí: el
  acoplamiento entre la grilla y el balance vive en el servidor, y duplicarlo
  en el navegador es garantizar que algún día digan cosas distintas.
*/


export type EstadoSemana = "borrador" | "publicada" | "cerrada" | "cancelada";


export type CategoriaConsumo =
  | "prec_nestle"
  | "prec_ccaa"
  | "secado_ccaa"
  | "secado_nestle"
  | "secado_colun";

export type Origen = "ccaa" | "nestle" | "punion";


/*
  Los equipos ya no están escritos aquí: son maestro y se piden a
  `/maestros/equipos/`. Agregar una máquina era editar este archivo y
  desplegar, que es lo contrario de que el administrador configure la planta.

  `consume_leche` viene con cada equipo porque es una regla del balance: un
  mismo código se programa en el evaporador y en la línea que lo recibe, y si
  ambos restaran, la leche se contaría dos veces.
*/
export type { Equipo } from "./maestros.service";

export const DIAS = [
  "Lunes",
  "Martes",
  "Miércoles",
  "Jueves",
  "Viernes",
  "Sábado",
  "Domingo",
];

export const CATEGORIAS: { valor: CategoriaConsumo; etiqueta: string; origen: Origen }[] = [
  { valor: "prec_nestle", etiqueta: "Prec. Nestlé", origen: "nestle" },
  { valor: "prec_ccaa", etiqueta: "Prec. CCAA", origen: "ccaa" },
  { valor: "secado_ccaa", etiqueta: "Secado CCAA", origen: "ccaa" },
  { valor: "secado_nestle", etiqueta: "Secado Nestlé", origen: "nestle" },
  { valor: "secado_colun", etiqueta: "Secado Colún", origen: "punion" },
];

export const ORIGENES: { valor: Origen; etiqueta: string }[] = [
  { valor: "ccaa", etiqueta: "CCAA" },
  { valor: "nestle", etiqueta: "Nestlé" },
  { valor: "punion", etiqueta: "P. Unión" },
];


/*
  Paleta de las familias de código.

  Validada con el verificador de la skill dataviz sobre pairlist "all" —en una
  carta Gantt cualquier par puede quedar contiguo—: peor par CVD ΔE 9.2,
  visión normal 16.3. El verde queda en 2,74:1 contra el fondo, bajo 3:1, y
  por eso **el código va siempre escrito dentro del bloque**: la etiqueta
  visible es la compensación que el propio verificador exige.
*/
export const COLOR_FAMILIA: Record<string, { color: string; etiqueta: string }> = {
  RC: { color: "#2a78d6", etiqueta: "Precondensado" },
  LN: { color: "#eb6834", etiqueta: "Secado Nestlé" },
  LU: { color: "#1baf7a", etiqueta: "Secado Colún" },
  LC: { color: "#4a3aa7", etiqueta: "Secado CCAA" },
};

/*
  Estados de equipo: grises deliberadamente desaturados, para que la
  producción sea la señal y lo que no produce quede de fondo. Los que llevan
  trama la usan como segunda codificación, no solo el color.
*/
export const ESTADO_EQUIPO: Record<
  string,
  { color: string; etiqueta: string; trama: boolean }
> = {
  A: { color: "#8b9da4", etiqueta: "Aseo", trama: true },
  X: { color: "#b6c5ca", etiqueta: "Preparación", trama: true },
  M: { color: "#6b7f87", etiqueta: "Mantenimiento", trama: true },
  P: { color: "#d03b3b", etiqueta: "PNP", trama: false },
  AP: { color: "#fab219", etiqueta: "Atraso de partida", trama: false },
};


/** La familia sale de las dos primeras letras del código (RC…, LN…, LU…, LC…). */
export function familiaDe(codigo: string | null | undefined): string {
  return (codigo || "").slice(0, 2).toUpperCase();
}

export function colorDeBloque(bloque: Bloque): string {
  if (bloque.tipo === "estado") {
    return ESTADO_EQUIPO[bloque.estado_equipo]?.color ?? "#94a3b8";
  }

  return COLOR_FAMILIA[familiaDe(bloque.codigo_texto)]?.color ?? "#64748b";
}


export interface Semana {
  id: number;
  codigo: string;
  anio: number;
  fecha_inicio: string;
  estado: EstadoSemana;
  estado_etiqueta: string;
  publicada_por_nombre: string | null;
  publicada_en: string | null;
  observacion: string;
  cancelada_en: string | null;
  motivo_cancelacion: string;
}

export interface CodigoProduccion {
  id: number;
  codigo: string;
  nombre: string;
  producto: number | null;
  producto_nombre: string | null;
  mandante: number | null;
  mandante_nombre: string | null;
  formato: string;
  categoria: CategoriaConsumo;
  categoria_etiqueta: string;
  rendimiento_lh: string;
  activo: boolean;
}

export interface Bloque {
  id: number;
  semana: number;
  /* Id del equipo en el maestro. */
  equipo: number;
  equipo_codigo: string;
  equipo_etiqueta: string;
  dia: number;
  hora_inicio: string;
  hora_fin: string;
  horas: number;
  tipo: "produccion" | "estado";
  codigo: number | null;
  codigo_texto: string | null;
  categoria: CategoriaConsumo | null;
  estado_equipo: string;
  cantidad_kg: string | null;
  observacion: string;
  /* Solo los evaporadores restan del balance. */
  consume_leche: boolean;
  tipo_actividad: number | null;
  tipo_actividad_nombre: string | null;
  fecha_hora_inicio: string | null;
  fecha_hora_fin: string | null;
  producto: number | null;
  producto_nombre: string | null;
  orden_produccion: number | null;
  orden_codigo: string | null;
  origen_leche: number | null;
  origen_leche_nombre: string | null;
  cliente: number | null;
  cliente_nombre: string | null;
  capacidad_hora: string | null;
  color: string;
  actualizado_en: string;
}

export interface OrdenProduccionPlan {
  id: number; codigo: string; producto: number; producto_nombre: string;
  cantidad_planificada: string; unidad: string; estado: string;
}

export interface TipoActividadPlan {
  id: number;
  codigo: string;
  nombre: string;
  color: string;
  requiere_producto: boolean;
  requiere_origen: boolean;
  requiere_capacidad: boolean;
}

export interface CapacidadProceso {
  id: number; equipo: number; equipo_nombre: string; vigente_desde: string;
  capacidad_hora: string; unidad: string; observacion: string;
}

export interface MovimientoPlan {
  id: number;
  semana: number;
  fecha_hora: string;
  propietario: number;
  propietario_nombre: string;
  tipo: "stock_inicial" | "recepcion" | "despacho" | "trasvasije_salida" | "trasvasije_entrada" | "ajuste";
  tipo_etiqueta: string;
  cantidad: string;
  documento: string;
  observacion: string;
}

export interface IndicadoresPlan {
  propietarios: { id: number; nombre: string }[];
  dias: Array<{
    dia: number; fecha: string; stock_inicial: Record<string, number>;
    movimientos: Array<{ id: number; tipo: string; propietario: number; cantidad: number; efecto: number; documento: string; observacion: string }>;
    consumo_por_propietario: Record<string, number>; consumo: number;
    stock_final: Record<string, number>;
  }>;
  alertas: Array<{ tipo: string; dia?: number; actividad?: number; propietario?: number; mensaje: string }>;
  consumo_total: number;
  stock_final_total: number;
  utilizacion_por_equipo: Record<string, number>;
}

export interface ComparacionVersiones {
  desde: number; hasta: number;
  actividades: { agregados: Bloque[]; eliminados: Bloque[]; modificados: Array<{ id: string; anterior: Bloque; nuevo: Bloque }> };
  movimientos: { agregados: MovimientoPlan[]; eliminados: MovimientoPlan[]; modificados: Array<{ id: string; anterior: MovimientoPlan; nuevo: MovimientoPlan }> };
}

export interface ConsumoDia {
  por_categoria: Record<CategoriaConsumo, number>;
  trasvasije: number;
  derivado: number;
  total: number;
}

export interface FilaBalance {
  dia: number;
  stock_inicial: number;
  recepciones: Record<Origen, number>;
  total_recepciones: number;
  total_disponible: number;
  consumo: ConsumoDia;
  stock_final: number;
  stock_por_origen: Record<Origen, number>;
  /* Falta leche de ese mandante para lo programado. Se informa, no se oculta. */
  origenes_negativos: Origen[];
}

export interface Programa {
  semana: Semana;
  bloques: Bloque[];
  balance: FilaBalance[];
  fechas: string[];
  publicable: boolean;
  bloqueos: string[];
  movimientos: MovimientoPlan[];
  indicadores: IndicadoresPlan;
  alertas: IndicadoresPlan["alertas"];
  versiones: Array<{ id: number; numero: number; publicada_por_nombre: string; publicada_en: string }>;
}

export interface Balance {
  id: number;
  semana: number;
  dia: number;
  stock_inicial: string | null;
  recepcion_ccaa: string;
  recepcion_nestle: string;
  recepcion_punion: string;
  trasvasije: string;
  crema_disponible_ton: string | null;
  ajustes: Partial<Record<Origen, number>>;
  observacion: string;
}

export interface Desviacion {
  plan: number;
  real: number;
  diferencia: number;
  /* null cuando no se planificó nada: el backend no inventa porcentajes. */
  pct: number | null;
}

export interface ContrasteDia {
  dia: number;
  fecha: string;
  leche_recibida: Desviacion;
  leche_consumida: Desviacion;
  kilos: Desviacion;
  lotes: number[];
  hubo_actividad: boolean;
}

export interface Contraste {
  semana: Semana;
  dias: ContrasteDia[];
  resumen: {
    leche_recibida: Desviacion;
    leche_consumida: Desviacion;
    kilos: Desviacion;
    dias_con_actividad: number;
  };
}


interface Pagina<T> {
  count: number;
  results: T[];
}


export async function obtenerSemanas(): Promise<Semana[]> {
  const { data } = await api.get<Pagina<Semana>>("planificacion/semanas/");

  return data.results;
}


export async function crearSemana(semana: {
  codigo: string;
  anio: number;
  fecha_inicio: string;
}): Promise<Semana> {
  const { data } = await api.post<Semana>("planificacion/semanas/", semana);

  return data;
}


export async function obtenerPrograma(semanaId: number): Promise<Programa> {
  const { data } = await api.get<Programa>(
    `planificacion/semanas/${semanaId}/programa/`,
  );

  return data;
}


export async function obtenerContraste(semanaId: number): Promise<Contraste> {
  const { data } = await api.get<Contraste>(
    `planificacion/semanas/${semanaId}/contraste/`,
  );

  return data;
}


export async function obtenerCodigos(): Promise<CodigoProduccion[]> {
  const { data } = await api.get<Pagina<CodigoProduccion>>(
    "planificacion/codigos/",
    { params: { activo: true } },
  );

  return data.results;
}


export async function obtenerBalances(semanaId: number): Promise<Balance[]> {
  const { data } = await api.get<Pagina<Balance>>("planificacion/balances/", {
    params: { semana: semanaId },
  });

  return data.results;
}


export async function guardarBalance(
  balance: Partial<Balance> & { semana: number; dia: number },
): Promise<Balance> {

  if (balance.id) {
    const { data } = await api.patch<Balance>(
      `planificacion/balances/${balance.id}/`,
      balance,
    );

    return data;
  }

  const { data } = await api.post<Balance>("planificacion/balances/", balance);

  return data;
}


export async function crearBloque(bloque: {
  semana: number;
  equipo: number;
  dia: number;
  hora_inicio: number;
  hora_fin: number;
  tipo: "produccion" | "estado";
  codigo?: number | null;
  estado_equipo?: string;
  cantidad_kg?: number | null;
  observacion?: string;
  tipo_actividad?: number | null;
  producto?: number | null;
  origen_leche?: number | null;
  capacidad_hora?: number | null;
  orden_produccion?: number | null;
  cliente?: number | null;
}): Promise<Bloque> {

  const { data } = await api.post<Bloque>("planificacion/bloques/", bloque);

  return data;
}

export async function obtenerOrdenesPlan(): Promise<OrdenProduccionPlan[]> {
  const { data } = await api.get<Pagina<OrdenProduccionPlan>>("produccion/ordenes/", { params: { estado: "programada" } });
  return data.results;
}

export async function actualizarBloque(
  id: number,
  cambios: Partial<Bloque>,
): Promise<Bloque> {
  const { data } = await api.patch<Bloque>(`planificacion/bloques/${id}/`, cambios);
  return data;
}

export async function obtenerTiposActividad(): Promise<TipoActividadPlan[]> {
  const { data } = await api.get<TipoActividadPlan[]>("planificacion/tipos-actividad/");
  return data;
}

export async function obtenerCapacidades(): Promise<CapacidadProceso[]> {
  const { data } = await api.get<Pagina<CapacidadProceso>>("planificacion/capacidades/");
  return data.results;
}

export async function crearCapacidad(datos: {
  equipo: number; vigente_desde: string; capacidad_hora: number; unidad: string; observacion?: string;
}): Promise<CapacidadProceso> {
  const { data } = await api.post<CapacidadProceso>("planificacion/capacidades/", datos);
  return data;
}

export async function crearMovimientoPlan(datos: {
  semana: number; fecha_hora: string; propietario: number; tipo: MovimientoPlan["tipo"];
  cantidad: number; documento?: string; observacion?: string;
}): Promise<MovimientoPlan> {
  const { data } = await api.post<MovimientoPlan>("planificacion/movimientos/", datos);
  return data;
}

export async function borrarMovimientoPlan(id: number): Promise<void> {
  await api.delete(`planificacion/movimientos/${id}/`);
}

export async function compararVersiones(semanaId: number, desde: number, hasta: number): Promise<ComparacionVersiones> {
  const { data } = await api.get<ComparacionVersiones>(`planificacion/semanas/${semanaId}/comparar-versiones/`, { params: { desde, hasta } });
  return data;
}


export async function borrarBloque(id: number): Promise<void> {
  await api.delete(`planificacion/bloques/${id}/`);
}


/**
 * Publica la semana: la compromete con planta.
 *
 * El backend responde 409 con los motivos si el plan no cuadra —días sin
 * balance, o saldos negativos por origen—. Ese rechazo es el que vale.
 */
export async function publicarSemana(id: number): Promise<Semana> {
  const { data } = await api.post<Semana>(`planificacion/semanas/${id}/publicar/`);

  return data;
}


export async function reabrirSemana(id: number): Promise<Semana> {
  const { data } = await api.post<Semana>(`planificacion/semanas/${id}/reabrir/`);

  return data;
}


export async function cerrarSemana(id: number): Promise<Semana> {
  const { data } = await api.post<Semana>(`planificacion/semanas/${id}/cerrar/`);

  return data;
}

export async function cancelarSemana(id: number, motivo: string): Promise<Semana> {
  const { data } = await api.post<Semana>(
    `planificacion/semanas/${id}/cancelar/`, { motivo },
  );
  return data;
}

export async function duplicarSemana(
  id: number,
  datos: { codigo: string; anio: number; fecha_inicio: string },
): Promise<Semana> {
  const { data } = await api.post<Semana>(
    `planificacion/semanas/${id}/duplicar/`, datos,
  );
  return data;
}


export interface CatalogosPlanificacion {
  categoria_consumo: { valor: string; etiqueta: string }[];
  formato: { valor: string; etiqueta: string }[];
  estado_semana: { valor: string; etiqueta: string }[];
  tipo_bloque: { valor: string; etiqueta: string }[];
  estado_equipo: { valor: string; etiqueta: string }[];
}


export async function obtenerCatalogosPlanificacion(): Promise<CatalogosPlanificacion> {
  const { data } = await api.get<CatalogosPlanificacion>(
    "planificacion/catalogos/",
  );

  return data;
}


/** Alta y edición de un código de producción, desde el maestro. */
export async function guardarCodigo(
  id: number | null,
  datos: Record<string, unknown>,
): Promise<CodigoProduccion> {

  const { data } = id
    ? await api.patch<CodigoProduccion>(`planificacion/codigos/${id}/`, datos)
    : await api.post<CodigoProduccion>("planificacion/codigos/", datos);

  return data;
}
