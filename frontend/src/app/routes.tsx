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
import Registros from "../pages/Registros/Registros";
import Administracion from "../pages/Administracion/Administracion";

/*
  Abastecimiento es una sección con pestañas, no una página. El orden de las
  subrutas es el ciclo del material —se compra, llega, Calidad lo libera, entra
  a stock, se pide y se consume— y es lo que ordena la navegación.

  `/inventario` ya no existe: su listado de materiales vive en la pestaña de
  materiales y su simulador en la de MRP. Eran dos pantallas contestando la
  misma pregunta con distinta granularidad, sin enlace entre ellas y con el
  mismo icono en el menú.
*/
import Abastecimiento from "../pages/Abastecimiento/Abastecimiento";
import AbastecimientoPanel from "../pages/Abastecimiento/Panel";
import AbastecimientoMateriales from "../pages/Abastecimiento/Materiales";
import AbastecimientoStock from "../pages/Abastecimiento/Stock";
import AbastecimientoDetalleLote from "../pages/Abastecimiento/DetalleLoteInventario";
import AbastecimientoCompras from "../pages/Abastecimiento/Compras";
import AbastecimientoCalidad from "../pages/Abastecimiento/Calidad";
import AbastecimientoPedidos from "../pages/Abastecimiento/Pedidos";
import AbastecimientoMrp from "../pages/Abastecimiento/Mrp";


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
                    </Route>

                    <Route
                        path="/dashboard"
                        element={<Dashboard />}
                    />

                    {/* La pestaña activa vive en la URL: un enlace a
                        /abastecimiento/compras lleva a compras, y el botón de
                        volver del navegador funciona entre pestañas. */}
                    <Route path="/abastecimiento" element={<Abastecimiento />}>
                        <Route index element={<AbastecimientoPanel />} />
                        <Route path="materiales" element={<AbastecimientoMateriales />} />
                        <Route path="stock" element={<AbastecimientoStock />} />
                        {/* La primera ruta de detalle del sistema. Hasta aquí
                            todo eran listas y ningún documento tenía URL: no
                            se podía enlazar, ni compartir, ni volver a él. */}
                        <Route
                            path="stock/lotes/:id"
                            element={<AbastecimientoDetalleLote />}
                        />
                        <Route path="compras" element={<AbastecimientoCompras />} />
                        <Route path="calidad" element={<AbastecimientoCalidad />} />
                        <Route path="pedidos" element={<AbastecimientoPedidos />} />
                        <Route path="mrp" element={<AbastecimientoMrp />} />
                    </Route>

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
                        path="/registros"
                        element={<Registros />}
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
