import { Routes, Route, Navigate } from "react-router-dom";

import RutaProtegida from "../components/RutaProtegida/RutaProtegida";
import RutaAdmin from "../components/RutaAdmin/RutaAdmin";

import AuthLayout from "../layouts/authlayout";
import MainLayout from "../layouts/mainlayout";

import Login from "../pages/Login/Login";
import RecuperarContrasena from "../pages/RecuperarContrasena/RecuperarContrasena";
import RestablecerContrasena from "../pages/RecuperarContrasena/RestablecerContrasena";
import Dashboard from "../pages/Dashboard/Dashboard";
import Produccion from "../pages/Produccion/Produccion";
import Recepcion from "../pages/Recepcion/Recepcion";
import Liberacion from "../pages/Liberacion/Liberacion";
import Planificacion from "../pages/Planificacion/Planificacion";
import Maestros from "../pages/Maestros/Maestros";
import Auditoria from "../pages/Auditoria/Auditoria";
import Administracion from "../pages/Administracion/Administracion";
import Inventario from "../pages/Inventario/Inventario";
import Abastecimiento from "../pages/Abastecimiento/Abastecimiento";


/*
  Rutas agrupadas por layout.

  Las rutas que van dentro de un <Route element={<Layout />}> se dibujan en
  el <Outlet /> de ese layout. Así el menú lateral se define una sola vez y
  lo heredan todas las pantallas internas.

  Las internas van además dentro de <RutaProtegida>, que manda al login a
  quien no haya iniciado sesión.
*/

function RoutesApp(){

    return (

        <Routes>

            {/* La raíz entra al panel; si no hay sesión, RutaProtegida
                desvía al login. */}

            <Route
                path="/"
                element={<Navigate to="/dashboard" replace />}
            />

            {/* Pantallas de acceso: sin menú lateral */}

            <Route element={<AuthLayout />}>

                <Route
                    path="/login"
                    element={<Login />}
                />

                <Route
                    path="/recuperar-contrasena"
                    element={<RecuperarContrasena />}
                />

                <Route
                    path="/restablecer-contrasena"
                    element={<RestablecerContrasena />}
                />

            </Route>

            {/* Pantallas internas: exigen sesión y llevan menú lateral */}

            <Route element={<RutaProtegida />}>

                <Route element={<MainLayout />}>

                    <Route element={<RutaAdmin />}>
                        <Route
                            path="/administracion"
                            element={<Administracion />}
                        />
                        <Route path="/inventario" element={<Inventario />} />
                    </Route>

                    <Route
                        path="/dashboard"
                        element={<Dashboard />}
                    />

                    <Route path="/abastecimiento" element={<Abastecimiento />} />

                    <Route
                        path="/produccion"
                        element={<Produccion />}
                    />

                    <Route
                        path="/recepcion"
                        element={<Recepcion />}
                    />

                    <Route
                        path="/liberacion"
                        element={<Liberacion />}
                    />

                    <Route
                        path="/planificacion"
                        element={<Planificacion />}
                    />

                    <Route
                        path="/maestros"
                        element={<Maestros />}
                    />

                    <Route
                        path="/auditoria"
                        element={<Auditoria />}
                    />

                </Route>

            </Route>

            {/* Cualquier otra dirección vuelve a la raíz */}

            <Route
                path="*"
                element={<Navigate to="/" replace />}
            />

        </Routes>

    );

}


export default RoutesApp;
