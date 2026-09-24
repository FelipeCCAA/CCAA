/*
  Listas paginadas del backend (PageNumberPagination, 50 por página).

  `lista()` se quedaba con la primera página y la pantalla mostraba 50 filas
  como si fueran todas. Aquí se recorre `next` hasta el final —para conjuntos
  acotados, como ubicaciones o clientes— y se arma la ruta de una página con
  sus filtros —para las listas largas, que se paginan en el servidor—.
*/
export interface Pagina<T> {
  count: number;
  next: string | null;
  previous: string | null;
  results: T[];
}

export type RespuestaLista<T> = T[] | Pagina<T>;

export type Filtros = Record<string, string | number | boolean | null | undefined>;

export const MAXIMO_PAGINAS = 40;

/* `next` viene absoluto con el host del backend; pedirlo tal cual se saltaría
   el proxy de Vite. Se toma solo el número de página y se aplica a la ruta. */
export function rutaDePagina(ruta: string, siguiente: string): string {
  const pagina = new URL(siguiente, "http://relativa").searchParams.get("page");
  if (!pagina) throw new Error("La respuesta paginada no dice qué página sigue.");
  const [base, consulta = ""] = ruta.split("?");
  const parametros = new URLSearchParams(consulta);
  parametros.set("page", pagina);
  return `${base}?${parametros.toString()}`;
}

export async function recorrerPaginas<T>(
  pedir: (ruta: string) => Promise<RespuestaLista<T>>,
  ruta: string,
  maximo = MAXIMO_PAGINAS,
): Promise<T[]> {
  const filas: T[] = [];
  let actual: string | null = ruta;
  for (let vuelta = 0; actual !== null; vuelta += 1) {
    if (vuelta === maximo) {
      // No revienta: una excepción que el llamador atrapa (como hace `lista()`
      // en sus consumidores) esconde el corte y deja pasar una lista vacía sin
      // decir por qué. Mejor una lista truncada, avisada, que una lista muda.
      console.warn(`La lista ${ruta} tiene más de ${maximo} páginas: búscala con filtros. Se devuelven solo las primeras ${maximo}.`);
      return filas;
    }
    const datos: RespuestaLista<T> = await pedir(actual);
    if (Array.isArray(datos)) return filas.concat(datos);
    filas.push(...datos.results);
    actual = datos.next ? rutaDePagina(ruta, datos.next) : null;
  }
  return filas;
}

export function conFiltros(ruta: string, filtros: Filtros): string {
  const parametros = new URLSearchParams();
  for (const [clave, valor] of Object.entries(filtros)) {
    if (valor === undefined || valor === null || valor === "" || valor === false) continue;
    parametros.set(clave, valor === true ? "1" : String(valor));
  }
  const consulta = parametros.toString();
  if (!consulta) return ruta;
  return `${ruta}${ruta.includes("?") ? "&" : "?"}${consulta}`;
}
