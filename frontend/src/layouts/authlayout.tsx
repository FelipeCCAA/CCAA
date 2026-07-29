import { Outlet } from "react-router-dom";


/*
  Estructura de las pantallas de acceso (login, recuperar contraseña).

  No lleva menú lateral: son pantallas a las que se entra sin haber iniciado
  sesión. Cada página define su propio diseño a pantalla completa.
*/

function AuthLayout() {
  return (
    <div className="min-h-screen">

      <Outlet />

    </div>
  );
}


export default AuthLayout;
