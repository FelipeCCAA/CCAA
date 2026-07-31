import { Navigate, Outlet } from "react-router-dom";

import { obtenerSesion } from "../../services/sesion";


function RutaAdmin() {
  const sesion = obtenerSesion();

  if (sesion?.usuario.rol !== "admin" && sesion?.usuario.perfil?.nivel !== "admin") {
    return <Navigate to="/dashboard" replace />;
  }

  return <Outlet />;
}


export default RutaAdmin;
