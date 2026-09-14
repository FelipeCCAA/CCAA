import { Outlet } from "react-router-dom";

import { AccesoRestringido } from "../RutaModulo/RutaModulo";
import { puedeAccederModulo } from "../../services/access-control";
import { obtenerSesion } from "../../services/sesion";


function RutaAdmin() {
  const usuario = obtenerSesion()?.usuario;

  if (!puedeAccederModulo(usuario, "administracion")) {
    return <AccesoRestringido detalle="Tu puesto no está autorizado para administrar usuarios." />;
  }

  return <Outlet />;
}


export default RutaAdmin;
