import axios, { type AxiosRequestConfig, type AxiosResponse, type InternalAxiosRequestConfig } from "axios";

import { cerrarSesion, guardarMotivoCierre, obtenerToken } from "./sesion";
import { debeCerrarSesion, mensajeDeCierre } from "./auth-errors";
import { claveGet, LimitadorSolicitudes } from "./request-control";


const api = axios.create({

    baseURL: import.meta.env.VITE_API_URL || "http://127.0.0.1:8000/api/",
    timeout: 15000,

});

const limitadorGet = new LimitadorSolicitudes(2);
const liberadores = new WeakMap<InternalAxiosRequestConfig, () => void>();


/*
  Adjunta el token a cada llamada.

  Se lee en el momento del envío, no al arrancar la aplicación: así una
  sesión iniciada después de cargar la página funciona sin recargar.
*/
api.interceptors.request.use(async (config) => {

    if (config.method?.toLowerCase() === "get") {
        liberadores.set(config, await limitadorGet.adquirir());
    }

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

    (respuesta) => {
        liberadores.get(respuesta.config)?.();
        return respuesta;
    },

    (error) => {

        if (error.config) liberadores.get(error.config)?.();

        // Con HashRouter la ruta vive en el hash (por ejemplo, `#/login`).
        const rutaActual = window.location.hash.slice(1) || window.location.pathname;

        if (debeCerrarSesion(
            error.response?.status,
            rutaActual,
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


/*
  Volver entre módulos ya visitados no debe repetir inmediatamente las mismas
  lecturas. La caché es privada del navegador, dura diez segundos y conserva
  como máximo veinte respuestas. Toda escritura la vacía para no mostrar un
  saldo anterior después de guardar.
*/
const CACHE_MS = 10_000;
const CACHE_MAXIMA = 20;
const cacheGet = new Map<string, { vence: number; respuesta: AxiosResponse }>();
const getPendientes = new Map<string, Promise<AxiosResponse>>();
const getOriginal = api.get.bind(api);

api.get = (function getControlado<T = unknown, R = AxiosResponse<T>, D = unknown>(
    url: string,
    config?: AxiosRequestConfig<D>,
): Promise<R> {
    const clave = claveGet(url, config?.params, obtenerToken());
    const guardada = cacheGet.get(clave);
    if (guardada && guardada.vence > Date.now()) {
        return Promise.resolve(guardada.respuesta as R);
    }
    const pendiente = getPendientes.get(clave);
    if (pendiente) return pendiente as Promise<R>;

    const solicitud = getOriginal<T, AxiosResponse<T>, D>(url, config)
        .then((respuesta) => {
            if (cacheGet.size >= CACHE_MAXIMA) {
                const primera = cacheGet.keys().next().value;
                if (primera !== undefined) cacheGet.delete(primera);
            }
            cacheGet.set(clave, { vence: Date.now() + CACHE_MS, respuesta });
            return respuesta;
        })
        .finally(() => getPendientes.delete(clave));
    getPendientes.set(clave, solicitud as Promise<AxiosResponse>);
    return solicitud as Promise<R>;
}) as typeof api.get;

api.interceptors.response.use((respuesta) => {
    if (respuesta.config.method?.toLowerCase() !== "get") cacheGet.clear();
    return respuesta;
});


export default api;
