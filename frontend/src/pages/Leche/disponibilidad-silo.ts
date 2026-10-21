import type { OcupacionSilo } from "../../services/recepcion.service";

export const formatoLitros = new Intl.NumberFormat("es-CL", { maximumFractionDigits: 2 });

export function cantidadInformada(valor: unknown): number | null {
  if (valor === null || valor === undefined || valor === "") return null;
  if (typeof valor !== "number" && typeof valor !== "string") return null;
  const numero = Number(valor);
  return Number.isFinite(numero) ? numero : null;
}

export function disponibleSilo(silo: Pick<OcupacionSilo, "litros_disponibles">): number | null {
  return cantidadInformada(silo.litros_disponibles);
}

export function bloqueoSilo(silo: OcupacionSilo): string | undefined {
  const disponible = disponibleSilo(silo);
  if (disponible === null) return "Disponibilidad desconocida. Actualiza los saldos antes de operar.";
  const reservaDestino = silo.reservas_activas.find((reserva) => reserva.tipo === "destino");
  if (reservaDestino) return `Destino reservado por ${reservaDestino.ejecucion_codigo}.`;
  if (silo.motivos_no_disponible.length) return silo.motivos_no_disponible[0];
  if (disponible <= 0) return "No hay litros disponibles para otra operación.";
  return undefined;
}

export function validarLitrosDespacho(litros: string, disponible: number | null): string {
  if (disponible === null) return "Actualiza la disponibilidad antes de despachar.";
  if (!/^\d+(\.\d{1,2})?$/.test(litros) || Number(litros) <= 0) {
    return "Indica litros positivos con un máximo de dos decimales (0,01 L).";
  }
  if (Number(litros) > disponible) return `La cantidad supera los ${formatoLitros.format(disponible)} L disponibles.`;
  return "";
}
