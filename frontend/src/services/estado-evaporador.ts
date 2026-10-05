export type EstadoTarjetaEvaporador =
  | "disponible"
  | "preparada"
  | "ejecucion"
  | "pausada"
  | "bloqueada";

export interface TarjetaEvaporador<C> {
  estado: EstadoTarjetaEvaporador;
  etiqueta: string;
  /** La corrida que define la tarjeta: la misma que sostiene la acción mostrada. */
  corridaActiva: C | null;
  /** Pendiente de Calidad no reserva el evaporador; se informa aparte. */
  pendienteCalidad: C | null;
}

const ETIQUETAS: Record<EstadoTarjetaEvaporador, string> = {
  disponible: "Disponible",
  preparada: "Preparada",
  ejecucion: "En ejecución",
  pausada: "Pausada",
  bloqueada: "Bloqueada",
};

/**
 * Decide el estado de la tarjeta de un evaporador y la corrida que lo
 * sostiene, leyendo las dos SIEMPRE desde la misma corrida.
 *
 * Antes la tarjeta tomaba la ocupación de `ocupacionesPorEquipo(ejecuciones)`
 * —un `Map` que, al iterar, deja la ÚLTIMA ejecución del arreglo para ese
 * equipo— y la acción de `corridas.find(...)` —que devuelve la PRIMERA
 * corrida que calce por equipo y estado—. Con dos corridas para el mismo
 * equipo (una en curso y una abandonada: ver CLAUDE.md «Máquinas ocupadas
 * por lotes anulados», anular un lote no cierra su `EjecucionProceso`), esas
 * dos búsquedas independientes podían no acertar a la misma corrida, y la
 * tarjeta decía «OCUPADO · EJ-PROD-72» ofreciendo la acción de EJ-PROD-70.
 *
 * `CorridaCondensacion.estado` tampoco distingue pausada/bloqueada: esos son
 * estados de la ejecución genérica, no de la corrida. Por eso, una vez
 * elegida la corrida, el matiz fino se lee de la ejecución que tiene
 * exactamente su código — nunca de otra.
 */
export function tarjetaEvaporador<
  C extends { equipo_id: number | null; estado: string; ejecucion_codigo: string },
>(
  equipoId: number,
  corridas: C[],
  ejecuciones: { codigo: string; estado: string }[],
): TarjetaEvaporador<C> {
  const corridasEquipo = corridas.filter((corrida) => corrida.equipo_id === equipoId);
  const corridaActiva =
    corridasEquipo.find((corrida) => corrida.estado === "en_proceso") ??
    corridasEquipo.find((corrida) => corrida.estado === "borrador") ??
    null;
  const pendienteCalidad =
    corridasEquipo.find((corrida) => corrida.estado === "pendiente_calidad") ?? null;

  if (!corridaActiva) {
    return { estado: "disponible", etiqueta: ETIQUETAS.disponible, corridaActiva: null, pendienteCalidad };
  }

  const ejecucion = ejecuciones.find((item) => item.codigo === corridaActiva.ejecucion_codigo);
  const estado: EstadoTarjetaEvaporador =
    ejecucion?.estado === "pausada" ? "pausada"
    : ejecucion?.estado === "bloqueada" ? "bloqueada"
    : corridaActiva.estado === "borrador" ? "preparada"
    : "ejecucion";

  return { estado, etiqueta: ETIQUETAS[estado], corridaActiva, pendienteCalidad };
}
