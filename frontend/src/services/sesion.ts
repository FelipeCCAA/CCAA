/*
  Sesión del usuario en el navegador.

  Guarda quién inició sesión para que el menú lo muestre y para que las rutas
  internas sepan si dejar pasar.

  IMPORTANTE — esto NO es seguridad. El backend hoy valida la contraseña pero
  no devuelve ningún token ni cookie de sesión, así que esto es solo un
  recordatorio local: cualquiera puede escribir esta clave a mano en el
  navegador y entrar. Para proteger de verdad hacen falta tokens en el backend
  y que la API los exija en cada petición.
*/

const CLAVE = "ccaa.sesion";

export interface Sesion {
  usuario: string;
  nombre: string;
  apellido: string;
}


export function guardarSesion(sesion: Sesion): void {
  localStorage.setItem(CLAVE, JSON.stringify(sesion));
}


export function obtenerSesion(): Sesion | null {
  const crudo = localStorage.getItem(CLAVE);

  if (!crudo) {
    return null;
  }

  try {
    const sesion = JSON.parse(crudo) as Sesion;

    // Un valor corrupto (editado a mano, o de una versión anterior) se
    // descarta en vez de romper la aplicación al leerlo.
    return sesion && typeof sesion.usuario === "string" ? sesion : null;
  } catch {
    return null;
  }
}


export function cerrarSesion(): void {
  localStorage.removeItem(CLAVE);
}


export function haySesion(): boolean {
  return obtenerSesion() !== null;
}


/** Nombre para mostrar. Cae al nombre de usuario si no tiene nombre cargado. */
export function nombreParaMostrar(sesion: Sesion): string {
  const completo = `${sesion.nombre} ${sesion.apellido}`.trim();

  return completo || sesion.usuario;
}
