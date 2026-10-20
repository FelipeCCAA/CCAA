import type { EntradaActoVale } from "../../services/estandarizacion.service.ts";

/** Comprobar el texto antes de convertir evita aceptar 0,001 L por redondeo. */
export function errorPrecisionLitros(valores: Record<string, string | number | null | undefined>): string {
  for (const [campo, valor] of Object.entries(valores)) {
    if (valor === null || valor === undefined || valor === "") continue;
    if (!/^\d+(?:\.\d{1,2})?$/.test(String(valor)) || !Number.isFinite(Number(valor))) {
      return `${campo}: usa cantidades no negativas con precisión de 0,01 L (máximo dos decimales). No se redondeará el dato.`;
    }
  }
  return "";
}

export function validarActo(acto: Omit<EntradaActoVale, "clave">): string {
  if (acto.motivo.trim().length < 5) return "Indica un motivo de al menos cinco caracteres.";
  if (acto.tipo === "medicion") {
    if (!acto.volumen_medido?.trim()) return "Indica el volumen medido del vale.";
    return errorPrecisionLitros({ "Volumen medido": acto.volumen_medido });
  }
  if (acto.tipo === "adicion" || acto.tipo === "retiro") {
    if (!acto.litros?.trim() || !(Number(acto.litros) > 0)) return "Indica litros mayores que cero.";
    const error = errorPrecisionLitros({ Litros: acto.litros });
    if (error) return error;
    if (!acto.silo_contraparte) return "Selecciona el silo de origen o destino del movimiento.";
  }
  if (acto.tipo === "documental" && (!acto.rectificacion || !Object.keys(acto.rectificacion).length
    || Object.values(acto.rectificacion).some((valor) => valor === null || String(valor).trim() === ""))) {
    return "Selecciona el campo y registra los valores anterior y nuevo de la rectificación.";
  }
  return "";
}
