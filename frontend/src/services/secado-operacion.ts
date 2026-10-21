import type { CorridaSecado, EntradaAlimentacionSecado } from "./secado.service";

export function requiereReferenciaMedicionKg(corrida: Pick<CorridaSecado, "entradas_alimentacion" | "requiere_referencia_medicion_kg">): boolean {
  return corrida.requiere_referencia_medicion_kg === true
    || (corrida.entradas_alimentacion ?? []).some((entrada) => entrada.unidad.toLocaleLowerCase("es-CL") === "l");
}

export function kgConocidosDeEntradas(entradas: readonly EntradaAlimentacionSecado[] = []): number | null {
  if (!entradas.length || entradas.some((entrada) => entrada.unidad.toLocaleLowerCase("es-CL") !== "kg")) return null;
  const total = entradas.reduce((suma, entrada) => suma + Number(entrada.cantidad), 0);
  return Number.isFinite(total) ? total : null;
}

export function fifoOperacionalValido(recomendado: unknown, motivo: string): boolean {
  return recomendado === true || (recomendado === false && motivo.trim().length >= 5);
}
