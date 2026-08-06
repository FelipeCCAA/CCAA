import { lazy, Suspense } from "react";
import { Routes, Route, Navigate } from "react-router-dom";

import RutaProtegida from "../components/RutaProtegida/RutaProtegida";
import RutaAdmin from "../components/RutaAdmin/RutaAdmin";

import AuthLayout from "../layouts/authlayout";
import MainLayout from "../layouts/mainlayout";

import Login from "../pages/Login/Login";
import RecuperarContrasena from "../pages/RecuperarContrasena/RecuperarContrasena";
import RestablecerContrasena from "../pages/RecuperarContrasena/RestablecerContrasena";
const Dashboard = lazy(() => import("../pages/Dashboard/Dashboard"));
const Produccion = lazy(() => import("../pages/Produccion/Produccion"));
const Recepcion = lazy(() => import("../pages/Recepcion/Recepcion"));
const Recoleccion = lazy(() => import("../pages/Recoleccion/Recoleccion"));
const Liberacion = lazy(() => import("../pages/Liberacion/Liberacion"));
const Planificacion = lazy(() => import("../pages/Planificacion/Planificacion"));
const Maestros = lazy(() => import("../pages/Maestros/Maestros"));
const Auditoria = lazy(() => import("../pages/Auditoria/Auditoria"));
const Administracion = lazy(() => import("../pages/Administracion/Administracion"));
const Inventario = lazy(() => import("../pages/Inventario/Inventario"));
const Abastecimiento = lazy(() => import("../pages/Abastecimiento/Abastecimiento"));
const Registros = lazy(() => import("../pages/Registros/Registros"));
const Procesos = lazy(() => import("../pages/Procesos/Procesos"));
const Mantenimiento = lazy(() => import("../pages/Mantenimiento/Mantenimiento"));

const diferido = (componente: React.ReactNode) => (
  <Suspense fallback={<div className="p-10 text-sm text-slate-500">Cargando módulo…</div>}>
    {componente}
  </Suspense>
);


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
                            element={diferido(<Administracion />)}
                        />
                        <Route path="/inventario" element={diferido(<Inventario />)} />
                    </Route>

                    <Route
                        path="/dashboard"
                        element={diferido(<Dashboard />)}
                    />

                    <Route path="/abastecimiento" element={diferido(<Abastecimiento />)} />

                    <Route path="/procesos" element={diferido(<Procesos />)} />

                    <Route path="/mantenimiento" element={diferido(<Mantenimiento />)} />

                    <Route
                        path="/produccion"
                        element={diferido(<Produccion />)}
                    />

                    <Route path="/recoleccion" element={diferido(<Recoleccion />)} />

                    <Route
                        path="/recepcion"
                        element={diferido(<Recepcion />)}
                    />

                    <Route
                        path="/liberacion"
                        element={diferido(<Liberacion />)}
                    />

                    <Route
                        path="/planificacion"
                        element={diferido(<Planificacion />)}
                    />

                    <Route
                        path="/maestros"
                        element={diferido(<Maestros />)}
                    />

                    <Route
                        path="/registros"
                        element={diferido(<Registros />)}
                    />

                    <Route
                        path="/auditoria"
                        element={diferido(<Auditoria />)}
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
