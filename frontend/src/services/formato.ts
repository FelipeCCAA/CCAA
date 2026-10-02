/*
  Cantidades en pantalla.

  El backend manda decimales con tres cifras («13.000»), y en Chile el punto
  separa miles: sin formatear, trece unidades se leen trece mil. Toda cantidad
  del módulo pasa por aquí, con su unidad al lado.
*/
const NUMERO = new Intl.NumberFormat("es-CL", { maximumFractionDigits: 3 });

// Un formateador por cantidad de decimales exactos, creado una sola vez por
// valor: la crioscopía (3) y el RC (3) necesitan decimales fijos —«-0,510»
// como «-0,512», no «-0,51»— y `Intl.NumberFormat` cuesta construir.
const NUMERO_DECIMALES_FIJOS = new Map<number, Intl.NumberFormat>();

function formateadorDecimalesFijos(decimales: number): Intl.NumberFormat {
  let formateador = NUMERO_DECIMALES_FIJOS.get(decimales);
  if (!formateador) {
    formateador = new Intl.NumberFormat("es-CL", {
      minimumFractionDigits: decimales,
      maximumFractionDigits: decimales,
    });
    NUMERO_DECIMALES_FIJOS.set(decimales, formateador);
  }
  return formateador;
}

/**
 * Formatea una cantidad en chileno. Sin `decimales`, muestra hasta tres y
 * recorta los ceros que sobran (13 L, no 13,000 L). Con `decimales`, fija esa
 * cantidad exacta: una crioscopía o un RC pierden su cifra significativa si
 * «0,510» se recorta a «0,51».
 */
export function cantidad(
  valor: string | number | null | undefined,
  unidad?: string,
  decimales?: number,
): string {
  if (valor === null || valor === undefined || valor === "") return "—";
  const numero = Number(valor);
  if (!Number.isFinite(numero)) return "—";
  const formateador = decimales === undefined ? NUMERO : formateadorDecimalesFijos(decimales);
  const texto = formateador.format(numero);
  return unidad ? `${texto} ${unidad}` : texto;
}
