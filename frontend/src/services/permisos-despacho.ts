import type { Usuario } from "./sesion.ts";

/*
  Quién despacha. Refleja `PuedeCrearDespacho` y las acciones `autorizar`,
  `ejecutar` y `cancelar` de `inventario/views.py`, que miran **solo** permisos
  (`despacho_crear`, `despacho_autorizar`). La pantalla anterior decidía con el
  área y el rol, y ofrecía botones que el servidor rechazaba con 403.

  El superusuario queda cubierto: `capacidades_de()` le devuelve todas.
*/
type ConCapacidades = Pick<Usuario, "capacidades"> | null | undefined;

export function puedeAutorizarDespacho(usuario: ConCapacidades): boolean {
  return Boolean(usuario?.capacidades?.includes("despacho_autorizar"));
}

export function puedeDespachar(usuario: ConCapacidades): boolean {
  return Boolean(usuario?.capacidades?.includes("despacho_crear")) || puedeAutorizarDespacho(usuario);
}
