/*
  Sesión del usuario.

  Guarda el token que entrega el backend y los datos de quien inició sesión.
  El token viaja en cada llamada a la API (ver api.ts); sin él, el backend
  responde 401 a todo salvo el login.

  Dónde se guarda lo decide "Recordarme":

  - Marcado, en `localStorage`: la sesión sobrevive a cerrar el navegador.
  - Sin marcar, en `sessionStorage`: se borra al cerrar la pestaña.

  La diferencia importa en planta. Recepción trabaja en turnos A/B/C sobre los
  mismos terminales, y una sesión que sigue abierta cuando entra el turno
  siguiente hace que los registros queden firmados por quien ya se fue. Que la
  casilla exista y no haga nada era peor que no tenerla: prometía justamente
  esa protección.

  Sobre el riesgo de fondo: los dos almacenes son legibles por JavaScript, así
  que un ataque de tipo XSS podría robar el token. La alternativa más segura es
  una cookie HttpOnly, que exige manejar CSRF y cookies entre orígenes. Para
  una aplicación interna de planta el compromiso es razonable, pero conviene
  saberlo antes de exponerla fuera de la red interna.
*/

const CLAVE = "ccaa.sesion";


export interface PerfilUsuario {
  cargo: string;
  area: string;
  area_etiqueta: string;
  turno: string;
  rol: string;
  rol_etiqueta: string;
  nivel: "admin" | "trabajador";
  nivel_etiqueta: string;
}


export type Rol =
  | "recepcion"
  | "produccion"
  | "calidad"
  | "admin"
  | "lectura";


export interface Usuario {
  id: number;
  username: string;
  nombre: string;
  apellido: string;
  email: string;
  /* Rol efectivo. Un superusuario es "admin" aunque no tenga perfil, y un
     usuario sin perfil es null: no escribe en ninguna parte. */
  rol: Rol | null;
  perfil: PerfilUsuario | null;
}


/*
  Quién escribe en cada módulo. Refleja usuarios/permisos.py.

  Esto NO es seguridad: es cortesía. Sirve para no ofrecer un botón que el
  backend va a rechazar con un 403. Quien lo evite editando el navegador se
  encontrará igual con el rechazo del servidor, que es donde el permiso se
  aplica de verdad.
*/
const ESCRITURA: Record<string, Rol[]> = {
  maestros: ["admin"],
  produccion: ["produccion", "admin"],
  recepcion: ["recepcion", "admin"],
  calidad: ["calidad", "admin"],
};


export function puedeEscribir(modulo: keyof typeof ESCRITURA): boolean {
  const rol = obtenerSesion()?.usuario.rol;

  return rol ? ESCRITURA[modulo].includes(rol) : false;
}


export interface Sesion {
  token: string;
  usuario: Usuario;
}


export function guardarSesion(sesion: Sesion, recordar = false): void {
  const donde = recordar ? localStorage : sessionStorage;
  const elOtro = recordar ? sessionStorage : localStorage;

  // Se limpia el otro almacén antes de escribir: si quedaran dos copias, la
  // de sessionStorage ganaría al leer y "Recordarme" dejaría de recordar en
  // cuanto alguien iniciara sesión sin marcarlo.
  elOtro.removeItem(CLAVE);
  donde.setItem(CLAVE, JSON.stringify(sesion));
}


export function obtenerSesion(): Sesion | null {
  // `sessionStorage` primero: es la sesión de esta pestaña y la más reciente.
  // Leer también `localStorage` mantiene válidas las sesiones abiertas antes
  // de que existiera esta distinción.
  const crudo = sessionStorage.getItem(CLAVE) ?? localStorage.getItem(CLAVE);

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
  // Los dos, sin preguntar dónde estaba: cerrar sesión a medias es peor que
  // no cerrarla, porque el usuario cree que salió.
  sessionStorage.removeItem(CLAVE);
  localStorage.removeItem(CLAVE);
}


export function haySesion(): boolean {
  return obtenerSesion() !== null;
}


/** Nombre para mostrar. Cae al nombre de usuario si no tiene nombre cargado. */
export function nombreParaMostrar(usuario: Usuario): string {
  // Se filtran los vacíos antes de unir: interpolar un campo ausente deja el
  // texto "undefined" a la vista, y `trim()` no lo quita porque está en medio.
  const completo = [usuario.nombre, usuario.apellido]
    .filter(Boolean)
    .join(" ")
    .trim();

  return completo || usuario.username;
}


/** Cargo o rol, lo que haya. Un usuario sin perfil no muestra nada. */
export function cargoParaMostrar(usuario: Usuario): string {
  if (!usuario.perfil) {
    return usuario.username;
  }

  return usuario.perfil.cargo || usuario.perfil.rol_etiqueta;
}
