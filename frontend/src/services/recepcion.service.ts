import api from "./api";

import type { Pagina } from "./produccion.service";


export interface Silo {
  id: number;
  codigo: string;
  tipo: string;
  tipo_etiqueta: string;
  capacidad_l: string;
  estado: string;
  estado_etiqueta: string;
  producto_actual: number | null;
  temperatura_actual: string | null;
  ultima_limpieza: string | null;
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
  estado: string;
  estado_etiqueta: string;
  producto_actual: string | null;
  temperatura_actual: number | null;
  ultima_limpieza: string | null;
  ultimo_movimiento: string | null;
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


/* Un compartimiento del camión. Lo único que se mide por módulo es la
   crioscopía (columnas M1-M4 del formato); litros, silo y destino son del
   camión. `carga_recoleccion` vincula el módulo con la carga que Recolección
   dejó cerrada en el predio, cuando corresponde. */
export interface ModuloRecepcion {
  id: number;
  numero: number;
  crioscopia: string | null;
  carga_recoleccion: number | null;
}


export interface BusquedaProveedorRecepcion {
  id: number;
  proveedor: string;
  charm_bet: string;
  charm_tetra: string;
  delvo_sp: string;
  hora_lectura: string | null;
  resultado: string;
}


/* PPRO N°1: control de inhibidores en leche fresca. */
export interface ControlInhibidoresRecepcion {
  id: number;
  recepcion: number;
  metodo: string;
  tiras_usadas: number;
  hora_lectura: string | null;
  resultado: string;
  analista: number | null;
  analista_nombre: string;
  busquedas: BusquedaProveedorRecepcion[];
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
  kg_romana: string | null;
  certificada: boolean | null;
  uso: string;
  uso_numero: number | null;
  silo: number | null;
  silo_codigo: string | null;
  operador: number | null;
  operador_nombre: string;
  turno: string;
  controles: Record<string, number | string>;
  modulos: ModuloRecepcion[];
  controles_inhibidores: ControlInhibidoresRecepcion[];

  /* Marcas horarias del formato CCAA.REC.FORM.002.02 */
  hora_programa: string | null;
  hora_arribo_porteria: string | null;
  hora_ingreso: string | null;
  hora_inicio_descarga: string | null;
  hora_termino_descarga: string | null;
  hora_inicio_cip: string | null;
  hora_termino_cip: string | null;
  hora_salida: string | null;

  /* Higiene del camión */
  lavado_ruedas: boolean | null;
  relavado: boolean | null;
  recambio_dilucion: string;
  ph_camion: string | null;

  /* Derivados: los calcula el backend, no se envían */
  kg_guia: string | null;
  diferencia_kg: string | null;
  solidos_totales: number | null;
  solidos_totales_kg: number | null;
  crioscopia_pool: number | null;
  /* Litros del camión contra la suma de las cargas de Recolección vinculadas
     a sus módulos. Sin ninguna carga vinculada, null: no es lo mismo que una
     diferencia de cero. */
  diferencia_recoleccion_litros: string | null;
  permanencia_horas: number | null;
  /* Por qué `permanencia_horas` salió null (qué marca horaria falta). Vacío
     cuando sí se pudo calcular. */
  permanencia_motivo: string;
  horas_en_planta: number | null;
  horas_a_pagar: number | null;
  tiempo_en_fabrica_horas: number | null;
  tiempo_de_descarga_horas: number | null;

  estado: string;
  estado_etiqueta: string;
  es_borrador: boolean;
  abierto_por: number | null;
  abierto_en: string | null;
  actualizado_en: string;
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
  alerta_silo_activa: boolean;
}


export interface ResponsableRecepcion {
  id: number;
  nombre: string;
  turno: string;
}


export interface OpcionCatalogo {
  valor: string;
  etiqueta: string;
}


export interface CatalogosFlujoRecepcion {
  responsables_recepcion: ResponsableRecepcion[];
  usos: OpcionCatalogo[];
  usos_numerados: string[];
  procedencias: OpcionCatalogo[];
  recambios_dilucion: OpcionCatalogo[];
  controles: string[];
}


export interface RecepcionNueva {
  fecha: string;
  hora?: string;
  tipo_leche: string;
  litros: string;
  vehiculo?: number;
  procedencia?: string;
  turno?: string;
  guia?: string;
  observacion?: string;
}


export interface LlegadaCamionNueva {
  fecha: string;
  hora?: string;
  guia?: string;
  vehiculo: number;
  procedencia?: string;
  tipo_leche: string;
  turno?: string;
  litros: string;
  kg_romana?: string;
  certificada?: boolean;
  uso?: string;
  uso_numero?: number;
  hora_programa?: string;
  hora_arribo_porteria?: string;
  hora_ingreso?: string;
  hora_inicio_descarga?: string;
  hora_termino_descarga?: string;
  hora_inicio_cip?: string;
  hora_termino_cip?: string;
  hora_salida?: string;
  lavado_ruedas?: boolean;
  relavado?: boolean;
  recambio_dilucion?: string;
  ph_camion?: string;
  observacion?: string;
  modulos: Array<{
    numero: number;
    crioscopia?: string;
    carga_recoleccion?: number;
  }>;
}


export type BorradorRecepcionDatos = {
  [K in keyof LlegadaCamionNueva]?: LlegadaCamionNueva[K] | null;
} & {
  fecha: string;
  tipo_leche: string;
  litros: string;
  vehiculo: number | null;
  modulos: LlegadaCamionNueva["modulos"];
};


export interface ResumenDiarioRecepcion {
  fecha: string | null;
  desde: string;
  hasta: string;
  camiones: number;
  litros: string;
  kg_guia: string;
  kg_romana: string;
  /* Solo se calcula si al menos un camión tiene romana; null si ninguno la
     tiene (ver `camiones_sin_romana`). */
  diferencia_kg: string | null;
  por_silo: Record<string, string>;
  por_procedencia: Record<string, string>;
  grasa_promedio: number | null;
  sng_promedio: number | null;
  horas_a_pagar: number;
  camiones_sin_marcas_horarias: number;
  /* Camiones sin `kg_romana`: `kg_romana` y `diferencia_kg` se calculan solo
     sobre los que sí se pesaron, así que este contador dice cuántos quedaron
     fuera de esos dos totales. */
  camiones_sin_romana: number;
  detalle?: DetalleResumenRecepcion[];
}


export interface DetalleResumenRecepcion {
  id: number;
  fecha: string;
  hora_arribo: string | null;
  guia: string;
  patente: string;
  procedencia: string;
  tipo_leche: string;
  litros: string;
  kg_guia: string;
  kg_romana: string | null;
  diferencia_kg: string | null;
  silo: string;
  estado: string;
  estado_etiqueta: string;
  crioscopias: Array<{ modulo: number; valor: string | null }>;
  permanencia_horas: number | null;
  permanencia_motivo: string;
  horas_a_pagar: number | null;
}


export interface PeriodoResumenRecepcion {
  fecha?: string;
  desde?: string;
  hasta?: string;
}


/* Los controles numéricos y de opción del camión, tal como los declara el
   backend (`CONTROLES_DECLARADOS` en `recepcion/models.py`). La crioscopía
   NO está aquí: se mide por módulo (`ModuloRecepcion.crioscopia`), no como
   parte de `controles`, y enviarla en `decidir-calidad` sería rechazada
   («Controles no reconocidos»). */
export const CONTROLES_NUMERICOS = [
  { clave: "temperatura", etiqueta: "Temperatura", unidad: "°C" },
  { clave: "acidez", etiqueta: "Acidez", unidad: "°D" },
  { clave: "ph", etiqueta: "pH", unidad: "" },
  { clave: "grasa", etiqueta: "Grasa", unidad: "%" },
  { clave: "sng", etiqueta: "SNG", unidad: "%" },
];

export const CONTROLES_OPCION = [
  { clave: "delvo", etiqueta: "Delvo Test", valores: ["Negativo", "Positivo"] },
  { clave: "inhibidores", etiqueta: "Inhibidores", valores: ["Negativo", "Positivo"] },
  /* Los cuatro ítems que el formato pide por separado (columnas AC-AF).
     Reemplazan al antiguo `organoleptico`, que dejó de escribirse: sigue
     leyéndose en filas históricas pero ya no se ofrece aquí. */
  { clave: "sangre", etiqueta: "Sangre", valores: ["Conforme", "No conforme"] },
  { clave: "pus", etiqueta: "Pus", valores: ["Conforme", "No conforme"] },
  { clave: "materias_extranas", etiqueta: "Materias extrañas", valores: ["Conforme", "No conforme"] },
  { clave: "aroma", etiqueta: "Aroma", valores: ["Conforme", "No conforme"] },
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

/*
  Registra **un camión**: un solo registro, con sus módulos. `registrar-llegada/`
  responde el objeto creado (201), no una lista — antes, un camión producía un
  `Recepcion` por módulo; ahora es una fila por camión y los módulos cuelgan
  de ella.
*/
export async function registrarLlegadaCamion(
  llegada: LlegadaCamionNueva,
): Promise<Recepcion> {
  const { data } = await api.post<Recepcion>(
    "recepcion/recepciones/registrar-llegada/",
    llegada,
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


/*
  Los totales que la planilla pone al pie: litros y kilos del día, reparto
  por silo y por procedencia, promedios de grasa y SNG, y las horas de
  sobreestadía. El backend acepta un `fecha` o el par `desde`/`hasta`.
*/
export async function resumenDiarioRecepcion(
  periodo: string | PeriodoResumenRecepcion,
): Promise<ResumenDiarioRecepcion> {
  const { data } = await api.get<ResumenDiarioRecepcion>(
    "recepcion/recepciones/resumen-diario/",
    {
      params: {
        ...(typeof periodo === "string" ? { fecha: periodo } : periodo),
        detalle: 1,
      },
    },
  );
  return data;
}

export async function corregirCrioscopias(
  id: number,
  modulos: Array<{ id: number; crioscopia: number | null }>,
  motivo: string,
): Promise<Recepcion> {
  const { data } = await api.patch<Recepcion>(
    `recepcion/recepciones/${id}/corregir-crioscopias/`,
    { modulos, motivo },
  );
  return data;
}


export async function obtenerBorradorRecepcion(): Promise<Recepcion | null> {
  const respuesta = await api.get<Recepcion>(
    "recepcion/recepciones/mi-borrador/",
  );
  return respuesta.status === 204 ? null : respuesta.data;
}


export async function crearBorradorRecepcion(
  datos: BorradorRecepcionDatos,
): Promise<Recepcion> {
  const { data } = await api.post<Recepcion>(
    "recepcion/recepciones/crear-borrador/", datos,
  );
  return data;
}


export async function guardarBorradorRecepcion(
  id: number,
  datos: BorradorRecepcionDatos,
): Promise<Recepcion> {
  const { data } = await api.patch<Recepcion>(
    `recepcion/recepciones/${id}/guardar-borrador/`, datos,
  );
  return data;
}


export async function confirmarBorradorRecepcion(id: number): Promise<Recepcion> {
  const { data } = await api.post<Recepcion>(
    `recepcion/recepciones/${id}/confirmar-borrador/`, {},
  );
  return data;
}


export async function descartarBorradorRecepcion(id: number): Promise<void> {
  await api.post(`recepcion/recepciones/${id}/descartar-borrador/`, {});
}


export async function descargarResumenRecepcion(
  periodo: PeriodoResumenRecepcion,
  formato: "csv" | "xlsx",
): Promise<{ contenido: Blob; nombre: string }> {
  const respuesta = await api.get<Blob>(
    "recepcion/recepciones/resumen-diario/",
    { params: { ...periodo, formato }, responseType: "blob" },
  );
  const disposicion = String(respuesta.headers["content-disposition"] ?? "");
  const nombre = disposicion.match(/filename="?([^";]+)"?/i)?.[1]
    ?? `recepciones.${formato}`;
  return { contenido: respuesta.data, nombre };
}


export async function obtenerSilos(): Promise<Silo[]> {
  const { data } = await api.get<Pagina<Silo>>("maestros/silos/");

  return data.results;
}


export async function obtenerVehiculos(): Promise<Vehiculo[]> {
  const { data } = await api.get<Pagina<Vehiculo>>("maestros/vehiculos/");

  return data.results;
}


/*
  El análisis del silo — `CCAA.REC.FORM.005.01`.

  No se confunde con los controles del camión: el silo mezcla varios camiones
  y es esa mezcla la que alimenta el cálculo del RC. `vigente` y
  `motivo_vigencia` los decide el backend contra el libro de movimientos; el
  cliente no los recalcula, porque dos implementaciones de la misma regla
  terminan discrepando justo en el número que se usa para estandarizar.
*/
export interface AnalisisSilo {
  id: number;
  silo: number;
  silo_codigo: string;
  tomado_en: string;
  hora_inicio_llenado: string | null;
  ph: string | null;
  acidez: string | null;
  grasa: string | null;
  sng: string | null;
  proteina: string | null;
  temperatura: string | null;
  densidad: string | null;
  certificada: boolean | null;
  procedencia: string;
  analista_nombre: string;
  observacion: string;
  estado: "borrador" | "confirmado" | "anulado";
  es_borrador: boolean;
  abierto_por: number | null;
  abierto_en: string | null;
  actualizado_en: string;
  vigente: boolean;
  motivo_vigencia: string;
  faltantes_para_vale: string[];
}


export async function listarAnalisisSilo(siloId: number): Promise<AnalisisSilo[]> {
  const { data } = await api.get("/recepcion/analisis-silo/", { params: { silo: siloId } });
  return Array.isArray(data) ? data : data.results;
}


export async function crearAnalisisSilo(
  datos: Record<string, unknown>,
): Promise<AnalisisSilo> {
  const { data } = await api.post("/recepcion/analisis-silo/", datos);
  return data;
}


export async function obtenerBorradorAnalisisSilo(
  siloId: number,
): Promise<AnalisisSilo | null> {
  const respuesta = await api.get<AnalisisSilo>(
    "/recepcion/analisis-silo/mi-borrador/", { params: { silo: siloId } },
  );
  return respuesta.status === 204 ? null : respuesta.data;
}


export async function crearBorradorAnalisisSilo(
  datos: Record<string, unknown>,
): Promise<AnalisisSilo> {
  const { data } = await api.post<AnalisisSilo>(
    "/recepcion/analisis-silo/crear-borrador/", datos,
  );
  return data;
}


export async function guardarBorradorAnalisisSilo(
  id: number,
  datos: Record<string, unknown>,
): Promise<AnalisisSilo> {
  const { data } = await api.patch<AnalisisSilo>(
    `/recepcion/analisis-silo/${id}/guardar-borrador/`, datos,
  );
  return data;
}


export async function confirmarBorradorAnalisisSilo(
  id: number,
): Promise<AnalisisSilo> {
  const { data } = await api.post<AnalisisSilo>(
    `/recepcion/analisis-silo/${id}/confirmar-borrador/`, {},
  );
  return data;
}


export async function descartarBorradorAnalisisSilo(id: number): Promise<void> {
  await api.post(`/recepcion/analisis-silo/${id}/descartar-borrador/`, {});
}
