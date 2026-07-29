import { Routes, Route, Navigate } from "react-router-dom";

import AuthLayout from "../layouts/authlayout";
import MainLayout from "../layouts/mainlayout";

import Login from "../pages/Login/Login";
import Dashboard from "../pages/Dashboard/Dashboard";


/*
  Rutas agrupadas por layout.

  Las rutas que van dentro de un <Route element={<Layout />}> se dibujan en
  el <Outlet /> de ese layout. Así el menú lateral se define una sola vez y
  lo heredan todas las pantallas internas.
*/

function RoutesApp(){

    return (

        <Routes>

            <Route
                path="/"
                element={<Navigate to="/login" />}
            />

            {/* Pantallas de acceso: sin menú lateral */}

            <Route element={<AuthLayout />}>

                <Route
                    path="/login"
                    element={<Login />}
                />

            </Route>

            {/* Pantallas internas: con menú lateral */}

            <Route element={<MainLayout />}>

                <Route
                    path="/dashboard"
                    element={<Dashboard />}
                />

            </Route>

        </Routes>

    );

}


export default RoutesApp;
