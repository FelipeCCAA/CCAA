import type { TipoUbicacion } from "./inventario.service.ts";

export type TipoAccionBodega =
  | "recibir" | "reubicar-material" | "consumir" | "contar" | "reubicar-pallet" | "ubicar-liberado";

/* Cantidad tecleada: acepta coma decimal (es lo que se escribe en Chile). */
export function leerCantidad(texto: string): number | null {
  const limpio = texto.trim().replace(",", ".");
  if (!limpio) return null;
  const numero = Number(limpio);
  return Number.isFinite(numero) && numero > 0 ? numero : null;
}

/*
  El ajuste que corresponde a un conteo físico.

  El operador dice cuánto contó —no cuánto sobra o falta—, que es lo que ve en
  la estantería. La diferencia se redondea a milésimas porque así la guarda el
  modelo; sin redondear, 13,1 − 13 daría 0,0999…
*/
export function ajustePorConteo(
  enSistema: string | number, contado: string | number,
): { tipo: "positivo" | "negativo"; cantidad: number } | null {
  const diferencia = Math.round((Number(contado) - Number(enSistema)) * 1000) / 1000;
  if (!Number.isFinite(diferencia) || diferencia === 0) return null;
  return { tipo: diferencia > 0 ? "positivo" : "negativo", cantidad: Math.abs(diferencia) };
}

/*
  Qué tipo de ubicación acepta cada movimiento. Se ofrecen solo esas: ofrecer
  todas deja elegir un destino que el backend rechaza al final del formulario.
  Recibir sigue la regla de `registrar_entrada` (cuarentena si pasa por Calidad).
*/
export function tiposDeDestino(
  accion: TipoAccionBodega,
  contexto: { origenTipo?: TipoUbicacion; requiereCalidad?: boolean },
): TipoUbicacion[] {
  switch (accion) {
    case "recibir":
      return [contexto.requiereCalidad ? "cuarentena" : "disponible"];
    case "reubicar-material":
      return contexto.origenTipo ? [contexto.origenTipo] : [];
    case "reubicar-pallet":
    case "ubicar-liberado":
      return ["disponible"];
    default:
      return [];
  }
}
