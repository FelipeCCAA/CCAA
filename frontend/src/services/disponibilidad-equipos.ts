export type DisponibilidadEquipo = "disponible" | "reservado" | "ocupado";

export interface OcupacionEquipo {
  disponibilidad: DisponibilidadEquipo;
  ejecucion: string;
  estado: string;
  estado_etiqueta: string;
}

export function disponibilidadSegunEstado(estado?: string | null): DisponibilidadEquipo {
  if (estado === "preparacion") return "reservado";
  if (["ejecucion", "pausada", "bloqueada"].includes(estado ?? "")) return "ocupado";
  return "disponible";
}

export function ocupacionesPorEquipo<T extends {
  codigo: string;
  estado: string;
  estado_etiqueta: string;
  equipo_id: number | null;
}>(ejecuciones: T[]): Map<number, OcupacionEquipo> {
  const resultado = new Map<number, OcupacionEquipo>();
  for (const ejecucion of ejecuciones) {
    if (ejecucion.equipo_id === null) continue;
    const disponibilidad = disponibilidadSegunEstado(ejecucion.estado);
    if (disponibilidad === "disponible") continue;
    resultado.set(ejecucion.equipo_id, {
      disponibilidad,
      ejecucion: ejecucion.codigo,
      estado: ejecucion.estado,
      estado_etiqueta: ejecucion.estado_etiqueta,
    });
  }
  return resultado;
}
