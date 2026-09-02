export type TipoAnalisisProceso = "silo" | "lote";

export function payloadLiberacionProceso(
  tipo: TipoAnalisisProceso,
  analisisId: number,
  observacion: string,
): { analisis_id: number; observacion: string } | {
  analisis_lote_id: number;
  observacion: string;
} {
  if (tipo === "lote") {
    return { analisis_lote_id: analisisId, observacion };
  }
  return { analisis_id: analisisId, observacion };
}

export function describirRango(valor: unknown): string {
  if (!valor || typeof valor !== "object" || Array.isArray(valor)) {
    return String(valor ?? "—");
  }
  const rango = valor as Record<string, unknown>;
  const minimo = rango.min ?? "—";
  const maximo = rango.max ?? "—";
  const unidad = rango.unidad ? ` ${String(rango.unidad)}` : "";
  const obligatorio = rango.obligatorio ? " · obligatorio" : "";
  return `${String(minimo)} a ${String(maximo)}${unidad}${obligatorio}`;
}
