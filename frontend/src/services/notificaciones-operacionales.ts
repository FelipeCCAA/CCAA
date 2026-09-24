import type { Notificacion } from "./inventario.service";

export function rutaDeNotificacion(notificacion: Notificacion): string {
  if (notificacion.accion_url) return notificacion.accion_url;
  if (
    notificacion.tipo.includes("calidad")
    || notificacion.tipo === "inspeccion_material_solicitada"
  ) return "/calidad";
  // Respaldo para una notificación sin `accion_url` propio (no debería darse:
  // los tres orígenes de estos tipos ya lo mandan). Van a Bodega porque es el
  // puesto que reubica pallets liberados y material en cuarentena — la consulta
  // de solo lectura vive en /inventario, no la acción. Las MRQ se preparan en
  // Abastecimiento › Pedidos, que es donde se reservan y entregan.
  if (notificacion.tipo === "mrq_enviada") return "/abastecimiento/pedidos";
  if (
    notificacion.tipo.startsWith("material_")
    || notificacion.tipo === "producto_liberado"
  ) return "/bodega";
  return "/produccion";
}
