import api from "./api";

import type { Pagina } from "./produccion.service";


/*
  Maestros: productos, mandantes, silos y camiones.

  El SKU del producto **no viaja desde aquí**: lo deriva el backend de los
  atributos en `Producto.save()`. Mandarlo permitiría guardar un código que
  contradiga los atributos del mismo producto, que es el defecto que trae el
  archivo de origen del catálogo.

  Los catálogos de cada segmento tampoco están escritos en el frontend: se
  piden a `/maestros/catalogos/`. Una copia aquí ofrecería tarde o
  temprano un valor que el backend rechaza — el mismo criterio que ya sigue
  el catálogo de parámetros de calidad.
*/

export interface OpcionCatalogo {
  valor: string;
  etiqueta: string;
}

export interface CatalogosSku {
  silo_tipo: OpcionCatalogo[];
  equipo_tipo: OpcionCatalogo[];
  area_documento: OpcionCatalogo[];
  frecuencia_documento: OpcionCatalogo[];
  naturaleza_comercial: OpcionCatalogo[];
  categoria: OpcionCatalogo[];
  tipo: OpcionCatalogo[];
  formato: OpcionCatalogo[];
  mercado: OpcionCatalogo[];
  cliente: OpcionCatalogo[];
  familia: OpcionCatalogo[];
  naturaleza: OpcionCatalogo[];
  unidad_base: OpcionCatalogo[];
}


export interface Mandante {
  id: number;
  nombre: string;
  /* Qué cliente representa dentro del SKU. Sin esto sus productos no
     generan código. */
  codigo_cliente: string;
  codigo_cliente_etiqueta: string;
  activo: boolean;
}


export interface ProductoMaestro {
  id: number;
  /* El SKU. Derivado: es de solo lectura. */
  codigo: string;
  /* El SKU descompuesto en sus valores, o null si el código no tiene esa
     forma — lo normal en los códigos antiguos de planta. */
  sku_legible: Record<string, string> | null;
  nombre: string;
  familia: string;
  familia_etiqueta: string;
  naturaleza: string;
  unidad_base: string;
  mandante: number;
  mandante_nombre: string;
  naturaleza_comercial: string;
  categoria: string;
  tipo: string;
  formato: string;
  mercado: string;
  variante: number | null;
  activo: boolean;
}


/** Campos que se envían al crear o editar. `codigo` no está: se deriva. */
export interface ProductoEditable {
  nombre?: string;
  familia?: string;
  naturaleza?: string;
  unidad_base?: string;
  mandante?: number;
  naturaleza_comercial?: string;
  categoria?: string;
  tipo?: string;
  formato?: string;
  mercado?: string;
  variante?: number | null;
  activo?: boolean;
}


export interface Equipo {
  id: number;
  /* Identificador estable: la planificación lo referencia. */
  codigo: string;
  nombre: string;
  tipo: string;
  tipo_etiqueta: string;
  /* Regla del balance, no etiqueta: solo los evaporadores restan leche.
     Marcarlo en una línea que recibe lo que el evaporador ya produjo restaría
     la misma leche dos veces. */
  consume_leche: boolean;
  orden: number;
  activo: boolean;
}


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
  activo: boolean;
}


export async function obtenerCatalogosSku(): Promise<CatalogosSku> {
  const { data } = await api.get<CatalogosSku>("maestros/catalogos/");

  return data;
}


export async function obtenerMandantes(): Promise<Mandante[]> {
  const { data } = await api.get<Pagina<Mandante>>("maestros/mandantes/");

  return data.results;
}


export async function crearMandante(
  mandante: { nombre: string; codigo_cliente: string },
): Promise<Mandante> {

  const { data } = await api.post<Mandante>("maestros/mandantes/", mandante);

  return data;
}


export async function editarMandante(
  id: number,
  cambios: Partial<Mandante>,
): Promise<Mandante> {

  const { data } = await api.patch<Mandante>(`maestros/mandantes/${id}/`, cambios);

  return data;
}


export async function obtenerProductosMaestros(): Promise<ProductoMaestro[]> {
  const { data } = await api.get<Pagina<ProductoMaestro>>("maestros/productos/");

  return data.results;
}


export async function crearProducto(
  producto: ProductoEditable,
): Promise<ProductoMaestro> {

  const { data } = await api.post<ProductoMaestro>(
    "maestros/productos/",
    producto,
  );

  return data;
}


export async function editarProducto(
  id: number,
  cambios: ProductoEditable,
): Promise<ProductoMaestro> {

  const { data } = await api.patch<ProductoMaestro>(
    `maestros/productos/${id}/`,
    cambios,
  );

  return data;
}


export async function obtenerSilosMaestros(): Promise<Silo[]> {
  const { data } = await api.get<Pagina<Silo>>("maestros/silos/");

  return data.results;
}


export async function obtenerEquipos(): Promise<Equipo[]> {
  const { data } = await api.get<Pagina<Equipo>>("maestros/equipos/");

  return data.results;
}


export async function crearEquipo(equipo: Partial<Equipo>): Promise<Equipo> {
  const { data } = await api.post<Equipo>("maestros/equipos/", equipo);

  return data;
}


export async function editarEquipo(
  id: number,
  cambios: Partial<Equipo>,
): Promise<Equipo> {

  const { data } = await api.patch<Equipo>(`maestros/equipos/${id}/`, cambios);

  return data;
}


/* ------------------------------------------------------- camiones y silos */

export interface Vehiculo {
  id: number;
  numero: string;
  placa: string;
  tipo: string;
  capacidad_l: string | null;
  transportista: string;
  chofer_am: string;
  chofer_pm: string;
  activo: boolean;
}


export async function obtenerVehiculosMaestros(): Promise<Vehiculo[]> {
  const { data } = await api.get<Pagina<Vehiculo>>("maestros/vehiculos/");

  return data.results;
}


export async function guardarVehiculo(
  id: number | null,
  datos: Record<string, unknown>,
): Promise<Vehiculo> {

  const { data } = id
    ? await api.patch<Vehiculo>(`maestros/vehiculos/${id}/`, datos)
    : await api.post<Vehiculo>("maestros/vehiculos/", datos);

  return data;
}


export async function guardarSilo(
  id: number | null,
  datos: Record<string, unknown>,
): Promise<Silo> {

  const { data } = id
    ? await api.patch<Silo>(`maestros/silos/${id}/`, datos)
    : await api.post<Silo>("maestros/silos/", datos);

  return data;
}


/* -------------------------------------------- documentos de liberación */

/*
  El catálogo del checklist. Lo escribe **Calidad**, no Administración: el
  módulo promete que Calidad cambia un campo y el formulario cambia sin
  desplegar, y si para eso hubiera que pedírselo a un administrador la promesa
  quedaría vacía.
*/

export interface DocumentoLiberacion {
  id: number;
  codigo: string;
  nombre: string;
  area: string;
  area_etiqueta: string;
  /* Decide DÓNDE vive el registro: por lote va en el expediente del lote; el
     resto pertenece al equipo y su período, y se lleva en Registros de
     planta. Cambiarla mueve el formulario de una pantalla a la otra. */
  frecuencia: string;
  frecuencia_etiqueta: string;
  aplica_a: string[];
  instruccion: string;
  campos: number;
  fuente: string;
  orden: number;
  activo: boolean;
}


export async function obtenerDocumentos(): Promise<DocumentoLiberacion[]> {
  const { data } = await api.get<Pagina<DocumentoLiberacion>>(
    "maestros/documentos/",
  );

  return data.results;
}


export async function editarDocumento(
  id: number,
  cambios: Partial<DocumentoLiberacion>,
): Promise<DocumentoLiberacion> {

  const { data } = await api.patch<DocumentoLiberacion>(
    `maestros/documentos/${id}/`,
    cambios,
  );

  return data;
}


/*
  Especificaciones de calidad: los rangos aceptables de un producto,
  versionados en el tiempo.

  Un lote se audita contra la versión vigente en SU fecha, no contra la actual.
  Por eso `es_vigente` lo calcula el backend con la misma función que el
  veredicto: reproducir aquí la regla de solape —gana la vigencia más reciente
  y, a igualdad, la versión mayor— daría una lista que marca vigente a una
  versión distinta de la que audita el lote.
*/

export interface Rango {
  min?: number | null;
  max?: number | null;
  obligatorio?: boolean;
}

export interface Especificacion {
  id: number;
  producto: number;
  producto_nombre: string;
  version: number;
  vigente_desde: string;
  vigente_hasta: string | null;
  rangos: Record<string, Rango>;
  fuente: string;
  es_vigente: boolean;
}

export async function obtenerEspecificaciones(): Promise<Especificacion[]> {
  const { data } = await api.get<Pagina<Especificacion>>(
    "maestros/especificaciones/",
  );

  return data.results;
}

export type NuevaEspecificacion = Omit<
  Especificacion,
  "id" | "producto_nombre" | "es_vigente"
>;

export async function guardarEspecificacion(
  id: number | null,
  datos: NuevaEspecificacion,
): Promise<Especificacion> {

  const { data } = id
    ? await api.put<Especificacion>(`maestros/especificaciones/${id}/`, datos)
    : await api.post<Especificacion>("maestros/especificaciones/", datos);

  return data;
}
