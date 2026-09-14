export type TipoReferenciaTrazable = "lote" | "ejecucion" | "salida";

export function rutaTrazabilidad(
  tipo: TipoReferenciaTrazable,
  referencia: string | number,
): string {
  const valor = encodeURIComponent(String(referencia).trim());
  return tipo === "lote"
    ? `procesos/trazabilidad/lotes/${valor}/`
    : `procesos/trazabilidad/${tipo}/${valor}/`;
}
