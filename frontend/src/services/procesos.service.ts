import api from "./api";

export interface Pagina<T> { count: number; next: string | null; previous: string | null; results: T[] }

export interface EjecucionProceso {
  id: number;
  version: number;
  codigo: string;
  estado: string;
  estado_etiqueta: string;
  etapa_nombre: string;
  etapa: number;
  etapa_tipo: string;
  equipo: number | null;
  equipo_nombre: string | null;
  equipo_id: number | null;
  vale_codigo: string | null;
  lote_codigo: string | null;
  producto_nombre: string | null;
  inicio: string | null;
  termino: string | null;
  acciones_permitidas: string[];
  entradas: { id: number; lote: number | null; lote_codigo: string | null; silo: number | null; silo_codigo: string | null; cantidad: string; unidad: string }[];
  salidas: { id: number; lote: number | null; lote_codigo: string | null; silo: number | null; silo_codigo: string | null; cantidad: string; unidad: string; naturaleza: string }[];
}

export interface EjecucionOperativa {
  id: number;
  version: number;
  codigo: string;
  estado: string;
  estado_etiqueta: string;
  etapa_nombre: string;
  etapa_tipo: string;
  equipo_id: number | null;
  equipo_nombre: string | null;
  acciones_permitidas: string[];
  entradas: string[];
  salidas: string[];
}

export interface RutaProducto {
  id: number;
  producto: number;
  proceso: number;
  producto_nombre: string;
  proceso_nombre: string;
  prioridad: number;
  destino: string;
  destino_final: "siguiente_proceso" | "envasado" | "despacho_directo" | "inventario";
  activa: boolean;
  etapas: { id: number; nombre: string; tipo: string; orden: number }[];
}

export interface CorridaCondensacion {
  id: number;
  ejecucion_codigo: string;
  orden_codigo: string;
  lote_codigo: string;
  equipo_nombre: string | null;
  equipo_id: number | null;
  silo_origen_codigo: string;
  silo_destino_codigo: string;
  litros_entrada: string;
  litros_descremada_plan: string | null;
  litros_crema_plan: string | null;
  fuente_plan: Record<string, unknown>;
  plan_confirmado_por: number | null;
  plan_confirmado_en: string | null;
  litros_precondensado: string | null;
  densidad_salida: string | null;
  solidos_salida: string | null;
  flujo_promedio: string | null;
  temperatura_salida: string | null;
  vacio_promedio: string | null;
  presion_promedio: string | null;
  estado: string;
  estado_etiqueta: string;
  iniciada_por_nombre: string | null;
  iniciada_en: string | null;
  finalizada_por_nombre: string | null;
  finalizada_en: string | null;
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
  controles: Record<string, unknown>;
  estado: string;
  estado_etiqueta: string;
  iniciada_por_nombre: string | null;
  iniciada_en: string | null;
  finalizada_por_nombre: string | null;
  finalizada_en: string | null;
}

export interface ProcesoMaestro {
  id: number;
  codigo: string;
  nombre: string;
  activo: boolean;
  etapas: (EtapaProceso & { orden: number })[];
}

export interface DiagnosticoRutaProductoItem {
  producto: number;
  producto_nombre: string;
  sucursal: number;
  sucursal_nombre: string;
  configurada: boolean;
  rutas: {
    id: number;
    proceso: number;
    proceso_nombre: string;
    prioridad: number;
  }[];
}

export interface DiagnosticoRutasProducto {
  completo: boolean;
  faltantes: number;
  productos: DiagnosticoRutaProductoItem[];
  integridad: {
    completa: boolean;
    total_hallazgos: number;
    categorias: Array<{
      codigo: string;
      titulo: string;
      severidad: "critico" | "alto";
      cantidad: number;
      items: Array<{ id: number; codigo: string; detalle: string }>;
    }>;
  };
}

export interface EtapaProceso {
  id: number;
  nombre: string;
  tipo: string;
  activa: boolean;
}

export interface CorridaDescremacion {
  id: number;
  ejecucion: number;
  ejecucion_codigo: string;
  equipo_nombre: string | null;
  silo_entera: number;
  silo_entera_codigo: string;
  silo_descremada: number;
  silo_descremada_codigo: string;
  estanque_crema: number;
  estanque_crema_codigo: string;
  producto_descremada: number;
  producto_crema: number;
  producto_descremada_nombre: string | null;
  producto_crema_nombre: string | null;
  ruta_descremada: number | null;
  ruta_crema: number | null;
  destino_descremada: string;
  destino_crema: string;
  analisis_entrada: number;
  litros_entrada: string;
  grasa_entrada: string;
  sng_entrada: string;
  litros_descremada: string | null;
  grasa_descremada: string | null;
  litros_crema: string | null;
  grasa_crema: string | null;
  controles: Record<string, unknown>;
  estado: string;
  estado_etiqueta: string;
  iniciada_por_nombre: string | null;
  iniciada_en: string | null;
  finalizada_por_nombre: string | null;
  finalizada_en: string | null;
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
      litros_atribuidos: string | null;
      vehiculo: string | null; silo_codigo: string;
      trazabilidad: "confirmada" | "inferida";
    }[];
    nota_recepciones: string;
    litros_no_atribuibles: string;
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
    calidad: { estado: string; autorizada_por: string | null; autorizada_en: string | null };
    pallets: {
      id: number; codigo: string; unidades: number; kg_neto: string; estado: string;
      ubicacion: string | null; despacho: string | null; cliente: string | null;
    }[];
    cadena_procesos: {
      id: number; codigo: string; etapa: string; tipo: string; estado: string;
      equipo: string | null;
      entradas: { origen: string; cantidad: string; unidad: string; tipo: string }[];
      salidas: { id: number; clase: string; destino: string; cantidad: string; unidad: string }[];
    }[];
  } | null;
}

export interface OpcionesAltaCondensacion {
  lotes: { id: number; codigo: string; producto: string; orden: string; ejecucion: string; equipo: string | null; origen: string; litros: string }[];
  silos: { id: number; codigo: string; estado: string; capacidad_l: string; saldo_l: string }[];
}

export interface OpcionesAltaMantequilla {
  ordenes: { id: number; codigo: string; producto: string }[];
  cremas: { id: number; codigo: string; producto: string; disponible_kg: string }[];
  cremas_pendientes_calidad: {
    id: number;
    codigo: string;
    producto: string;
    estado_calidad: "pendiente" | "rechazado" | "trazabilidad_incompleta";
    etapa_origen: string;
  }[];
  sueros: { id: number; codigo: string; producto: string }[];
  equipos: { id: number; nombre: string; tipo: string; ocupado_por: string | null }[];
}

export interface OpcionesAltaDescremacion {
  etapas: EtapaProceso[];
  equipos: { id: number; nombre: string; tipo: string; ocupado_por: string | null }[];
  silos_descremada: { id: number; codigo: string; tipo: string; activo: boolean }[];
  estanques_crema: { id: number; codigo: string; tipo: string; activo: boolean }[];
  productos_descremada: {
    id: number;
    nombre: string;
    tiene_especificacion_silo_vigente: boolean;
  }[];
  productos_crema: {
    id: number;
    nombre: string;
    tiene_especificacion_silo_vigente: boolean;
  }[];
  rutas: RutaProducto[];
  bloqueos: { codigo: string; mensaje: string }[];
}

export async function obtenerEjecuciones(): Promise<Pagina<EjecucionProceso>> {
  const { data } = await api.get<Pagina<EjecucionProceso>>("procesos/ejecuciones/");
  return data;
}

export async function obtenerEjecucionesOperativas(): Promise<EjecucionOperativa[]> {
  const { data } = await api.get<EjecucionOperativa[]>("procesos/ejecuciones/operativas/");
  return data;
}

export interface ResumenOperacionalProduccion {
  procesos_activos: number;
  esperando_calidad: number;
  materiales_listos: number;
  equipos_ocupados: number;
  bloqueos: number;
}

export async function obtenerResumenOperacional(): Promise<ResumenOperacionalProduccion> {
  const { data } = await api.get<ResumenOperacionalProduccion>(
    "procesos/ejecuciones/resumen-operacional/",
  );
  return data;
}

export async function transicionarEjecucion(
  id: number,
  estado: string,
  version: number,
  motivo = "",
): Promise<EjecucionProceso> {
  const { data } = await api.post<EjecucionProceso>(
    `procesos/ejecuciones/${id}/transicionar/`,
    { estado, motivo, version },
  );
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

export async function obtenerProcesosMaestros(): Promise<Pagina<ProcesoMaestro>> {
  const { data } = await api.get<Pagina<ProcesoMaestro>>("procesos/procesos/");
  return data;
}

export async function crearRutaProducto(datos: {
  producto: number;
  proceso: number;
  prioridad: number;
  destino_final: RutaProducto["destino_final"];
  destino?: string;
  observaciones?: string;
}): Promise<RutaProducto> {
  const { data } = await api.post<RutaProducto>("procesos/rutas-producto/", datos);
  return data;
}

export async function obtenerDiagnosticoRutasProducto(): Promise<DiagnosticoRutasProducto> {
  const { data } = await api.get<DiagnosticoRutasProducto>(
    "procesos/rutas-producto/diagnostico/",
  );
  return data;
}

export interface SalidaIntermediaDisponible {
  id: number;
  corrida_codigo: string;
  resultado: string;
  lote_id: number | null;
  lote_codigo: string | null;
  producto_id: number | null;
  producto_nombre: string | null;
  estado_material: string;
  estado_material_etiqueta: string;
  densidad_kg_m3: string | null;
  cantidad_trazable_kg: string | null;
  cantidad_consumida_kg: string | null;
  cantidad_disponible_kg: string | null;
  silo_id: number;
  silo_codigo: string;
  cantidad_total: string;
  cantidad_consumida: string;
  cantidad_disponible: string;
  unidad: string;
  clasificacion: string;
  clasificacion_etiqueta: string;
  destino: string;
  destino_etiqueta: string;
  destinos_permitidos: { valor: string; etiqueta: string }[];
  acciones_permitidas: { codigo: string; etiqueta: string }[];
  etapas_siguientes: {
    id: number;
    nombre: string;
    tipo: string;
    orden: number;
    equipos: {
      id: number;
      nombre: string;
      tipo: string;
      ocupado_por: string | null;
    }[];
  }[];
}

export interface ReworkDisponible {
  id: number;
  unidad_rework_id: number | null;
  codigo_unidad: string | null;
  ubicacion_codigo: string | null;
  trazabilidad_fisica: boolean;
  lote_id: number;
  lote_codigo: string;
  producto_nombre: string;
  origen: string;
  motivo: string;
  cantidad_autorizada_kg: string;
  cantidad_consumida_kg: string;
  cantidad_disponible_kg: string;
}

export async function iniciarCondensacion(id: number): Promise<CorridaCondensacion> {
  const { data } = await api.post<CorridaCondensacion>(`procesos/condensaciones/${id}/iniciar/`);
  return data;
}

export async function cerrarCondensacion(id: number, datos: {
  litros_precondensado: number;
  flujo_promedio?: number;
  densidad_salida?: number;
  solidos_salida?: number;
  temperatura_salida?: number;
  vacio_promedio?: number;
  presion_promedio?: number;
}): Promise<CorridaCondensacion> {
  const { data } = await api.post<CorridaCondensacion>(
    `procesos/condensaciones/${id}/cerrar/`, datos,
  );
  return data;
}

export async function obtenerOpcionesAltaCondensacion(): Promise<OpcionesAltaCondensacion> {
  const { data } = await api.get<OpcionesAltaCondensacion>("procesos/condensaciones/opciones-alta/");
  return data;
}

export async function crearCondensacionGuiada(datos: {
  lote: number; silo_destino: number;
}): Promise<CorridaCondensacion> {
  const { data } = await api.post<CorridaCondensacion>("procesos/condensaciones/crear-guiada/", datos);
  return data;
}

export async function obtenerMantequillas(): Promise<Pagina<CorridaMantequilla>> {
  const { data } = await api.get<Pagina<CorridaMantequilla>>("procesos/mantequillas/");
  return data;
}

export async function obtenerEtapas(): Promise<Pagina<EtapaProceso>> {
  const { data } = await api.get<Pagina<EtapaProceso>>("procesos/etapas/");
  return data;
}

export async function crearEjecucion(datos: {
  codigo: string; etapa: number; equipo: number;
}): Promise<EjecucionProceso> {
  const { data } = await api.post<EjecucionProceso>("procesos/ejecuciones/", datos);
  return data;
}

export async function obtenerDescremaciones(): Promise<Pagina<CorridaDescremacion>> {
  const { data } = await api.get<Pagina<CorridaDescremacion>>("procesos/descremaciones/");
  return data;
}

export async function obtenerOpcionesAltaDescremacion(): Promise<OpcionesAltaDescremacion> {
  const { data } = await api.get<OpcionesAltaDescremacion>(
    "procesos/descremaciones/opciones-alta/",
  );
  return data;
}

export async function iniciarMantequilla(id: number): Promise<CorridaMantequilla> {
  const { data } = await api.post<CorridaMantequilla>(`procesos/mantequillas/${id}/iniciar/`);
  return data;
}

export async function cerrarMantequilla(id: number, datos: {
  kg_mantequilla: number;
  kg_suero?: number;
  kg_merma?: number;
  controles?: Record<string, unknown>;
}): Promise<CorridaMantequilla> {
  const { data } = await api.post<CorridaMantequilla>(
    `procesos/mantequillas/${id}/cerrar/`, datos,
  );
  return data;
}

export async function obtenerOpcionesAltaMantequilla(): Promise<OpcionesAltaMantequilla> {
  const { data } = await api.get<OpcionesAltaMantequilla>("procesos/mantequillas/opciones-alta/");
  return data;
}

export async function crearMantequillaGuiada(datos: {
  orden: number; lote_crema: number; equipo: number;
  codigo_lote_mantequilla: string; lote_suero?: number; kg_crema: number;
}): Promise<CorridaMantequilla> {
  const { data } = await api.post<CorridaMantequilla>("procesos/mantequillas/crear-guiada/", datos);
  return data;
}

export async function obtenerSalidasIntermediasDisponibles(
  siloId?: number,
): Promise<SalidaIntermediaDisponible[]> {
  const { data } = await api.get<SalidaIntermediaDisponible[]>(
    "procesos/salidas/disponibles/",
    { params: { silo: siloId } },
  );
  return data;
}

export async function obtenerReworkDisponible(): Promise<ReworkDisponible[]> {
  const { data } = await api.get<ReworkDisponible[]>("procesos/entradas/opciones-rework/");
  return data;
}

export async function consumirRework(datos: {
  ejecucion: number;
  lote: number;
  unidad_rework?: number;
  cantidad: number;
  motivo: string;
  operacion_id: string;
}): Promise<void> {
  const { ejecucion, ...payload } = datos;
  await api.post(`procesos/ejecuciones/${ejecucion}/incorporar-rework/`, payload);
}

export async function prepararContinuacion(
  salidaId: number,
  datos: { etapa: number; equipo: number; cantidad: number },
): Promise<EjecucionProceso> {
  const { data } = await api.post<EjecucionProceso>(
    `procesos/salidas/${salidaId}/preparar-continuacion/`,
    datos,
  );
  return data;
}

export async function definirDestinoSalida(
  salidaId: number,
  destino: string,
): Promise<void> {
  await api.post(`procesos/salidas/${salidaId}/definir-destino/`, { destino });
}

export async function crearDescremacion(datos: {
  ejecucion: number; silo_entera: number; analisis_entrada: number;
  litros_entrada: number; grasa_entrada: number; sng_entrada: number;
  silo_descremada: number; estanque_crema: number;
  producto_descremada: number; producto_crema: number;
}): Promise<CorridaDescremacion> {
  const { data } = await api.post<CorridaDescremacion>("procesos/descremaciones/", datos);
  return data;
}

export async function crearDescremacionGuiada(datos: {
  codigo: string; etapa: number; equipo: number; silo_entera: number;
  analisis_entrada: number; litros_entrada: number;
  silo_descremada: number; estanque_crema: number;
  producto_descremada: number; producto_crema: number;
  litros_descremada_plan: number; litros_crema_plan: number;
  plan_confirmado: true;
  ruta_descremada: number; ruta_crema: number;
  destino_descremada: "estandarizacion";
  destino_crema: "siguiente_proceso" | "estandarizacion" | "despacho_directo";
}): Promise<CorridaDescremacion> {
  const { data } = await api.post<CorridaDescremacion>(
    "procesos/descremaciones/crear-guiada/",
    datos,
  );
  return data;
}

export interface SugerenciaDescremacion {
  litros_descremada_sugeridos: string;
  litros_crema_sugeridos: string;
  grasa_descremada_objetivo: string;
  grasa_crema_objetivo: string;
  fuente_plan: Record<string, unknown>;
  avisos: string[];
  requiere_confirmacion_operador: true;
}

export async function sugerirBalanceDescremacion(datos: {
  analisis_entrada: number;
  litros_entrada: number;
  producto_descremada: number;
  producto_crema: number;
}): Promise<SugerenciaDescremacion> {
  const { data } = await api.post<SugerenciaDescremacion>(
    "procesos/descremaciones/sugerir-balance/", datos,
  );
  return data;
}

export async function iniciarDescremacion(id: number): Promise<CorridaDescremacion> {
  const { data } = await api.post<CorridaDescremacion>(`procesos/descremaciones/${id}/iniciar/`);
  return data;
}

export async function cerrarDescremacion(id: number, datos: {
  litros_descremada: number; grasa_descremada: number;
  litros_crema: number; grasa_crema: number;
  controles?: Record<string, unknown>;
}): Promise<CorridaDescremacion> {
  const { data } = await api.post<CorridaDescremacion>(
    `procesos/descremaciones/${id}/cerrar/`, datos,
  );
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
