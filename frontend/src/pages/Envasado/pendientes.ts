import type { SolicitudEnvase } from "../../services/produccion.service";

export function clavePedidoPendiente(actorId: number, loteId: number): string {
  return `envasado-pendiente-${actorId}-${loteId}`;
}

export function leerPedidosPendientes(actorId: number | undefined): SolicitudEnvase[] {
  if (actorId === undefined) return [];
  const prefijo = `envasado-pendiente-${actorId}-`;
  try {
    return Object.keys(sessionStorage).filter((clave) => clave.startsWith(prefijo))
      .flatMap((clave) => {
        try {
          const pedido = JSON.parse(sessionStorage.getItem(clave) ?? "null") as SolicitudEnvase;
          return pedido?.lote && pedido?.operacion_id && pedido?.pallets_datos?.length
            && clave === clavePedidoPendiente(actorId, pedido.lote) ? [pedido] : [];
        } catch { return []; }
      });
  } catch { return []; }
}
