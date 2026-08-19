const MENSAJES: Record<string, string> = {
  SESSION_REVOKED: "Tu sesión fue cerrada. Vuelve a iniciar sesión.",
  SESSION_EXPIRED: "Tu sesión expiró por inactividad.",
  USER_DISABLED: "Tu cuenta fue desactivada.",
  PASSWORD_CHANGED: "Tu contraseña cambió. Inicia sesión nuevamente.",
};

export function mensajeDeCierre(codigo: unknown): string {
  return typeof codigo === "string" && MENSAJES[codigo]
    ? MENSAJES[codigo]
    : "Tu sesión ya no es válida.";
}

export function debeCerrarSesion(
  estado: number | undefined,
  ruta: string,
  redireccionando: boolean,
): boolean {
  return estado === 401 && ruta !== "/login" && !redireccionando;
}
