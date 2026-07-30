import axios from "axios";

import { cerrarSesion, obtenerToken } from "./sesion";


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
api.interceptors.response.use(

    (respuesta) => respuesta,

    (error) => {

        const esNoAutorizado = error.response?.status === 401;
        const enLogin = window.location.pathname === "/login";

        if (esNoAutorizado && !enLogin) {
            cerrarSesion();
            window.location.assign("/login");
        }

        return Promise.reject(error);

    },

);


export default api;
