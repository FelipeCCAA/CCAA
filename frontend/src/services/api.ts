import axios from "axios";

import { cerrarSesion, guardarMotivoCierre, obtenerToken } from "./sesion";
import { debeCerrarSesion, mensajeDeCierre } from "./auth-errors";


const api = axios.create({

    baseURL: import.meta.env.VITE_API_URL || "http://127.0.0.1:8000/api/",
    timeout: 15000,

});


/*
  Adjunta el token a cada llamada.

  Se lee en el momento del envío, no al arrancar la aplicación: así una
  sesión iniciada después de cargar la página funciona sin recargar.
*/
api.interceptors.request.use((config) => {

    const token = obtenerToken();

    if (token) {
        config.headers.Authorization = `Token ${token}`;
    }

    return config;

});


/*
  Si el backend responde 401, el token dejó de servir: caducó, fue revocado
  con un logout desde otro equipo, o la base se recreó en desarrollo.

  Se borra la sesión y se manda al login. La redirección es un cambio de
  ubicación del navegador y no useNavigate porque esto vive fuera de React,
  donde no hay acceso al router.
*/
let redireccionandoAlLogin = false;

api.interceptors.response.use(

    (respuesta) => respuesta,

    (error) => {

        if (debeCerrarSesion(
            error.response?.status,
            window.location.hash || window.location.pathname,
            redireccionandoAlLogin,
        )) {
            redireccionandoAlLogin = true;
            const codigo = error.response?.data?.code;
            cerrarSesion();
            guardarMotivoCierre(mensajeDeCierre(codigo));
            window.location.assign("/#/login");
        }

        return Promise.reject(error);

    },

);


export default api;
