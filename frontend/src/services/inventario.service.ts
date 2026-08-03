import api from "./api";

export interface Insumo {
  id: number; codigo: string; nombre: string; area: string; area_etiqueta: string;
  unidad: string; stock_actual: string; contenido_envase: string;
  eoq: string | null; punto_reposicion: string;
}

export interface ResultadoMRP {
  kilos_producir: string;
  materiales: Array<{ insumo: string; unidad: string; requerido: string; stock: string; faltante: string; envases_a_pedir: number; eoq: string | null }>;
}

export async function obtenerInsumos(): Promise<Insumo[]> {
  const { data } = await api.get<Insumo[] | { results: Insumo[] }>("inventario/insumos/");
  return Array.isArray(data) ? data : data.results;
}

export async function calcularMRP(producto: number, kilos_producir: number): Promise<ResultadoMRP> {
  const { data } = await api.post<ResultadoMRP>("inventario/mrp/", { producto, kilos_producir });
  return data;
}
