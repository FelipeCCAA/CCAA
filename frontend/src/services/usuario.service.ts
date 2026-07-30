import api from "./api";

import type { Sesion, Usuario } from "./sesion";


/**
 * Valida las credenciales y obtiene el token de la sesión.
 *
 * Lanza el error de axios si el backend responde 400, 401 o 403; quien llama
 * decide qué mensaje mostrar.
 */
export async function iniciarSesion(
  username: string,
  password: string,
): Promise<Sesion> {

  const { data } = await api.post<{ token: string; usuario: Usuario }>(
    "usuarios/login/",
    { username, password },
  );

  return { token: data.token, usuario: data.usuario };
}


/**
 * Invalida el token en el servidor.
 *
 * Borrarlo solo en el navegador no basta: el token seguiría sirviendo para
 * quien lo tuviera.
 */
export async function cerrarSesionEnServidor(): Promise<void> {
  await api.post("usuarios/logout/");
}


/** Quién es el usuario del token guardado. Responde 401 si ya no vale. */
export async function obtenerUsuarioActual(): Promise<Usuario> {
  const { data } = await api.get<Usuario>("usuarios/yo/");

  return data;
}


/** Solicita el correo de recuperación sin revelar si la cuenta existe. */
export async function solicitarRecuperacion(
  email: string,
): Promise<{ mensaje: string }> {
  const { data } = await api.post<{ mensaje: string }>(
    "usuarios/recuperar-contrasena/",
    { email },
  );

  return data;
}


export interface ConfirmacionRecuperacion {
  uid: string;
  token: string;
  nueva_contrasena: string;
  confirmar_contrasena: string;
}


/** Confirma el token del enlace y establece la nueva contraseña. */
export async function restablecerContrasena(
  datos: ConfirmacionRecuperacion,
): Promise<{ mensaje: string }> {
  const { data } = await api.post<{ mensaje: string }>(
    "usuarios/restablecer-contrasena/",
    datos,
  );

  return data;
}
