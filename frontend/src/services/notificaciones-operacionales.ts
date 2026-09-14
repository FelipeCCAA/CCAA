import type { Notificacion } from "./inventario.service";

export function rutaDeNotificacion(notificacion: Notificacion): string {
  if (notificacion.accion_url) return notificacion.accion_url;
  if (
    notificacion.tipo.includes("calidad")
    || notificacion.tipo === "inspeccion_material_solicitada"
  ) return "/calidad";
  if (
    notificacion.tipo.startsWith("material_")
    || notificacion.tipo === "producto_liberado"
    || notificacion.tipo === "mrq_enviada"
  ) return "/inventario";
  return "/produccion";
}
