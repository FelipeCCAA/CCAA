import { fechaLocalISO } from "./fechas.ts";

/*
  Cómo se ordena el puesto de Despacho: por lo que falta hacer con cada hoja.
  «Despachada hoy» usa el día local de Chile, no el UTC: un camión que sale a
  las 22:00 salió hoy.
*/
export function agruparHojas<T extends { estado: string; despachado_en: string | null }>(hojas: T[], hoy: string) {
  return {
    borrador: hojas.filter((h) => h.estado === "borrador"),
    autorizada: hojas.filter((h) => h.estado === "autorizado"),
    despachadaHoy: hojas.filter(
      (h) => h.estado === "despachado" && h.despachado_en !== null && fechaLocalISO(new Date(h.despachado_en)) === hoy,
    ),
  };
}

export function totalesCarga(
  pallets: { kg_neto: string | number }[],
  graneles: { cantidad: string | number; unidad: string }[],
) {
  const suma = (valores: number[]) => Math.round(valores.reduce((a, b) => a + b, 0) * 1000) / 1000;
  return {
    pallets: pallets.length,
    kg: suma([
      ...pallets.map((p) => Number(p.kg_neto)),
      ...graneles.filter((g) => g.unidad === "kg").map((g) => Number(g.cantidad)),
    ]),
    litros: suma(graneles.filter((g) => g.unidad === "L").map((g) => Number(g.cantidad))),
  };
}

export function buscarPalletPorCodigo<T extends { pallet_codigo: string }>(pallets: T[], codigo: string): T | null {
  const buscado = codigo.trim().toUpperCase();
  return pallets.find((p) => p.pallet_codigo.toUpperCase() === buscado) ?? null;
}
