/*
  Sesión del usuario.

  Guarda el token que entrega el backend y los datos de quien inició sesión.
  El token viaja en cada llamada a la API (ver api.ts); sin él, el backend
  responde 401 a todo salvo el login.

  Sobre dónde se guarda: localStorage es legible por JavaScript, así que un
  ataque de tipo XSS podría robar el token. La alternativa más segura es una
  cookie HttpOnly, que exige manejar CSRF y cookies entre orígenes. Para una
  aplicación interna de planta este compromiso es razonable, pero conviene
  saberlo antes de exponerla fuera de la red interna.
*/

const CLAVE = "ccaa.sesion";


export interface PerfilUsuario {
  cargo: string;
  area: string;
  turno: string;
  rol: string;
  rol_etiqueta: string;
}


export interface Usuario {
  id: number;
  username: string;
  nombre: string;
  apellido: string;
  email: string;
  perfil: PerfilUsuario | null;
}


export interface Sesion {
  token: string;
  usuario: Usuario;
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

    // Un valor corrupto (editado a mano, o de una versión anterior de la
    // aplicación) se descarta en vez de romper al leerlo.
    return sesion && typeof sesion.token === "string" && sesion.usuario
      ? sesion
      : null;
  } catch {
    return null;
  }
}


export function obtenerToken(): string | null {
  return obtenerSesion()?.token ?? null;
}


export function cerrarSesion(): void {
  localStorage.removeItem(CLAVE);
}


export function haySesion(): boolean {
  return obtenerSesion() !== null;
}


/** Nombre para mostrar. Cae al nombre de usuario si no tiene nombre cargado. */
export function nombreParaMostrar(usuario: Usuario): string {
  const completo = `${usuario.nombre} ${usuario.apellido}`.trim();

  return completo || usuario.username;
}


/** Cargo o rol, lo que haya. Un usuario sin perfil no muestra nada. */
export function cargoParaMostrar(usuario: Usuario): string {
  if (!usuario.perfil) {
    return usuario.username;
  }

  return usuario.perfil.cargo || usuario.perfil.rol_etiqueta;
}
