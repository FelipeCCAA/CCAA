import api from "./api";

import type { Sesion } from "./sesion";


interface RespuestaLogin extends Sesion {
  mensaje: string;
}


/**
 * Valida las credenciales contra el backend.
 *
 * Lanza el error de axios si el backend responde 400 o 401; quien llama
 * decide qué mensaje mostrar.
 */
export async function iniciarSesion(
  username: string,
  password: string,
): Promise<RespuestaLogin> {

  const { data } = await api.post<RespuestaLogin>(
    "usuarios/login/",
    { username, password },
  );

  return data;
}
