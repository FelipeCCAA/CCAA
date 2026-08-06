import api from "./api";

interface Pagina<T> { results: T[] }

export interface ParadaRuta {
  id: number; ruta: number; orden: number; proveedor: string; predio: string;
  sala: string; estado: "pendiente" | "completada" | "no_cargada";
  recoleccion_id: number | null;
}

export interface RutaRecoleccion {
  id: number; codigo: string; fecha: string; vehiculo: number;
  vehiculo_placa: string; conductor_nombre: string;
  estado: "programada" | "en_curso" | "cerrada" | "cancelada";
  observacion: string; paradas: ParadaRuta[];
}

export interface RecoleccionPredio {
  id: number; parada: number; estado: "registrada" | "cargada" | "rechazada";
}

export interface CargaEsperada {
  id: number; codigo: string; recoleccion: number; modulo: string;
  estanque_origen: string; litros: string; vehiculo: number;
  vehiculo_placa: string; proveedor: string; predio: string; recepcionada: boolean;
}

export async function obtenerRutas(): Promise<RutaRecoleccion[]> {
  const { data } = await api.get<Pagina<RutaRecoleccion>>("recoleccion/rutas/");
  return data.results;
}

export async function obtenerCargasPendientes(): Promise<CargaEsperada[]> {
  const { data } = await api.get<Pagina<CargaEsperada>>("recoleccion/cargas/", {
    params: { pendientes: true },
  });
  return data.results;
}

export async function crearRuta(datos: { codigo: string; fecha: string; vehiculo: number }) {
  const { data } = await api.post<RutaRecoleccion>("recoleccion/rutas/", datos);
  return data;
}

export async function crearParada(datos: { ruta: number; orden: number; proveedor: string; predio: string; sala?: string }) {
  const { data } = await api.post<ParadaRuta>("recoleccion/paradas/", datos);
  return data;
}

export async function registrarRecoleccion(datos: {
  parada: number; fecha_hora: string; litros_medidos: number; temperatura?: number;
  alcohol: "conforme" | "no_conforme"; codigo_muestra?: string; observacion?: string;
}) {
  const { data } = await api.post<RecoleccionPredio>("recoleccion/recolecciones/", datos);
  return data;
}

export async function agregarCarga(id: number, datos: {
  codigo: string; modulo: string; estanque_origen?: string; litros: number;
}) {
  await api.post(`recoleccion/recolecciones/${id}/cargas/`, datos);
}

export async function cerrarRuta(id: number) {
  const { data } = await api.post<RutaRecoleccion>(`recoleccion/rutas/${id}/cerrar/`);
  return data;
}
