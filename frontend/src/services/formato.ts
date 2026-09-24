/*
  Cantidades en pantalla.

  El backend manda decimales con tres cifras («13.000»), y en Chile el punto
  separa miles: sin formatear, trece unidades se leen trece mil. Toda cantidad
  del módulo pasa por aquí, con su unidad al lado.
*/
const NUMERO = new Intl.NumberFormat("es-CL", { maximumFractionDigits: 3 });

export function cantidad(valor: string | number | null | undefined, unidad?: string): string {
  if (valor === null || valor === undefined || valor === "") return "—";
  const numero = Number(valor);
  if (!Number.isFinite(numero)) return "—";
  const texto = NUMERO.format(numero);
  return unidad ? `${texto} ${unidad}` : texto;
}
