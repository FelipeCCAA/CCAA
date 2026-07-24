import api from "./api";


export function obtenerUsuario(){

    return api.get(
        "usuarios/prueba/"
    );

}