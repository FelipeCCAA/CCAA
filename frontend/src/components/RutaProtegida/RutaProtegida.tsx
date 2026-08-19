import { Navigate, Outlet, useLocation } from "react-router-dom";

import { haySesion, obtenerSesion } from "../../services/sesion";


/*
  Envuelve las rutas que exigen haber iniciado sesión.

  Si no hay sesión, manda al login y recuerda a dónde iba el usuario, para
  devolverlo ahí después de entrar en vez de dejarlo siempre en el panel.
*/

function RutaProtegida() {

  const ubicacion = useLocation();

  if (!haySesion()) {

    return (
      <Navigate
        to="/login"
        replace
        state={{ desde: ubicacion.pathname }}
      />
    );

  }

  if (
    obtenerSesion()?.usuario.perfil?.debe_cambiar_password
    && ubicacion.pathname !== "/cambiar-password"
  ) {
    return <Navigate to="/cambiar-password" replace />;
  }

  return <Outlet />;

}


export default RutaProtegida;
