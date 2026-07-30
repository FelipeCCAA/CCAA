import { Routes, Route, Navigate } from "react-router-dom";

import RutaProtegida from "../components/RutaProtegida/RutaProtegida";

import AuthLayout from "../layouts/authlayout";
import MainLayout from "../layouts/mainlayout";

import Login from "../pages/Login/Login";
import Dashboard from "../pages/Dashboard/Dashboard";
import Produccion from "../pages/Produccion/Produccion";
import Recepcion from "../pages/Recepcion/Recepcion";
import Liberacion from "../pages/Liberacion/Liberacion";


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

            </Route>

            {/* Pantallas internas: exigen sesión y llevan menú lateral */}

            <Route element={<RutaProtegida />}>

                <Route element={<MainLayout />}>

                    <Route
                        path="/dashboard"
                        element={<Dashboard />}
                    />

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
