import { lazy, Suspense } from "react";
import { Routes, Route, Navigate } from "react-router-dom";

import RutaProtegida from "../components/RutaProtegida/RutaProtegida";
import RutaAdmin from "../components/RutaAdmin/RutaAdmin";

import AuthLayout from "../layouts/authlayout";
import MainLayout from "../layouts/mainlayout";

import Login from "../pages/Login/Login";
import RecuperarContrasena from "../pages/RecuperarContrasena/RecuperarContrasena";
import RestablecerContrasena from "../pages/RecuperarContrasena/RestablecerContrasena";
/*
  Todas las pantallas se cargan con `lazy`: el bundle pasaba de 500 kB y el
  build lo venía advirtiendo. Nadie entra a mantenimiento y a recolección en la
  misma sesión, así que no hay razón para descargar las dos.
*/
const Dashboard = lazy(() => import("../pages/Dashboard/Dashboard"));
const Produccion = lazy(() => import("../pages/Produccion/Produccion"));
const Estandarizacion = lazy(() => import("../pages/Estandarizacion/Estandarizacion"));

/*
  Leche cruda: recolección y recepción, en una sola sección con pestañas.

  Eran dos pantallas que no se hablaban aunque el modelo ya las une
  (`CargaModulo.recepcion_planta`): la carga que sale del predio es la que
  llega a planta, y «qué viene en camino» no se veía en ninguna parte. El
  orden de las subrutas es el viaje de la leche, igual que en abastecimiento
  es el ciclo del material.
*/
const Leche = lazy(() => import("../pages/Leche/Leche"));
const LechePanel = lazy(() => import("../pages/Leche/Panel"));
const LecheRutas = lazy(() => import("../pages/Leche/Rutas"));
const LecheEnCamino = lazy(() => import("../pages/Leche/EnCamino"));
const LecheMuestreo = lazy(() => import("../pages/Leche/Muestreo"));
const LecheCalidad = lazy(() => import("../pages/Leche/Calidad"));
const LecheDescarga = lazy(() => import("../pages/Leche/SiloDescarga"));
const LecheSilos = lazy(() => import("../pages/Leche/Silos"));
const LecheHistorial = lazy(() => import("../pages/Leche/Historial"));
const Liberacion = lazy(() => import("../pages/Liberacion/Liberacion"));
const Planificacion = lazy(() => import("../pages/Planificacion/Planificacion"));
const Maestros = lazy(() => import("../pages/Maestros/Maestros"));
const Auditoria = lazy(() => import("../pages/Auditoria/Auditoria"));
const Registros = lazy(() => import("../pages/Registros/Registros"));
const Administracion = lazy(() => import("../pages/Administracion/Administracion"));
const CambiarPassword = lazy(() => import("../pages/CambiarPassword/CambiarPassword"));
const Procesos = lazy(() => import("../pages/Procesos/Procesos"));
const Mantenimiento = lazy(() => import("../pages/Mantenimiento/Mantenimiento"));
const Aseos = lazy(() => import("../pages/Inocuidad/Aseos"));

/*
  Abastecimiento es una sección con pestañas, no una página. El orden de las
  subrutas es el ciclo del material —se compra, llega, Calidad lo libera, entra
  a stock, se pide y se consume— y es lo que ordena la navegación.

  `/inventario` ya no existe: su listado de materiales vive en la pestaña de
  materiales y su simulador en la de MRP. Eran dos pantallas contestando la
  misma pregunta con distinta granularidad, sin enlace entre ellas y con el
  mismo icono en el menú. Main la reintrodujo en su rama; no se repone aquí
  porque el archivo que servía ya no existe.
*/
const Abastecimiento = lazy(() => import("../pages/Abastecimiento/Abastecimiento"));
const AbastecimientoPanel = lazy(() => import("../pages/Abastecimiento/Panel"));
const AbastecimientoMateriales = lazy(() => import("../pages/Abastecimiento/Materiales"));
const AbastecimientoStock = lazy(() => import("../pages/Abastecimiento/Stock"));
const AbastecimientoProductoTerminado = lazy(() => import("../pages/Abastecimiento/ProductoTerminado"));
const AbastecimientoDetalleLote = lazy(
  () => import("../pages/Abastecimiento/DetalleLoteInventario"),
);
const AbastecimientoBodegas = lazy(() => import("../pages/Abastecimiento/Bodegas"));
const AbastecimientoCompras = lazy(() => import("../pages/Abastecimiento/Compras"));
const AbastecimientoProveedores = lazy(() => import("../pages/Abastecimiento/Proveedores"));
const AbastecimientoRecepcion = lazy(() => import("../pages/Abastecimiento/Recepcion"));
const AbastecimientoCalidad = lazy(() => import("../pages/Abastecimiento/Calidad"));
const AbastecimientoPedidos = lazy(() => import("../pages/Abastecimiento/Pedidos"));
const AbastecimientoMrp = lazy(() => import("../pages/Abastecimiento/Mrp"));

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

                <Route
                    path="/cambiar-password"
                    element={diferido(<CambiarPassword />)}
                />

                <Route element={<MainLayout />}>

                    <Route element={<RutaAdmin />}>
                        <Route
                            path="/administracion"
                            element={diferido(<Administracion />)}
                        />
                    </Route>

                    <Route
                        path="/dashboard"
                        element={diferido(<Dashboard />)}
                    />

                    {/* La pestaña activa vive en la URL: un enlace a
                        /abastecimiento/compras lleva a compras, y el botón de
                        volver del navegador funciona entre pestañas. */}
                    <Route path="/abastecimiento" element={diferido(<Abastecimiento />)}>
                        <Route index element={diferido(<AbastecimientoPanel />)} />
                        <Route path="materiales" element={diferido(<AbastecimientoMateriales />)} />
                        <Route path="stock" element={diferido(<AbastecimientoStock />)} />
                        <Route path="producto-terminado" element={diferido(<AbastecimientoProductoTerminado />)} />
                        {/* La primera ruta de detalle del sistema. Hasta aquí
                            todo eran listas y ningún documento tenía URL: no
                            se podía enlazar, ni compartir, ni volver a él. */}
                        <Route
                            path="stock/lotes/:id"
                            element={diferido(<AbastecimientoDetalleLote />)}
                        />
                        <Route path="bodegas" element={diferido(<AbastecimientoBodegas />)} />
                        <Route path="compras" element={diferido(<AbastecimientoCompras />)} />
                        <Route path="proveedores" element={diferido(<AbastecimientoProveedores />)} />
                        <Route path="recepcion" element={diferido(<AbastecimientoRecepcion />)} />
                        <Route path="calidad" element={diferido(<AbastecimientoCalidad />)} />
                        <Route path="pedidos" element={diferido(<AbastecimientoPedidos />)} />
                        <Route path="mrp" element={diferido(<AbastecimientoMrp />)} />
                    </Route>

                    <Route path="/procesos" element={diferido(<Procesos />)} />

                    <Route path="/mantenimiento" element={diferido(<Mantenimiento />)} />

                    <Route path="/inocuidad/aseos" element={diferido(<Aseos />)} />

                    <Route
                        path="/produccion"
                        element={diferido(<Produccion />)}
                    />

                    <Route path="/leche" element={diferido(<Leche />)}>
                        <Route index element={diferido(<LechePanel />)} />
                        <Route path="rutas" element={diferido(<LecheRutas />)} />
                        <Route path="en-camino" element={diferido(<LecheEnCamino />)} />
                        <Route path="muestreo" element={diferido(<LecheMuestreo />)} />
                        <Route path="calidad" element={diferido(<LecheCalidad />)} />
                        <Route path="descarga" element={diferido(<LecheDescarga />)} />
                        <Route path="silos" element={diferido(<LecheSilos />)} />
                        <Route path="historial" element={diferido(<LecheHistorial />)} />
                    </Route>

                    {/* Las dos direcciones anteriores siguen funcionando: hay
                        enlaces guardados y gente con la ruta en la memoria. */}
                    <Route path="/recepcion" element={<Navigate to="/leche" replace />} />
                    <Route path="/recoleccion" element={<Navigate to="/leche/rutas" replace />} />

                    <Route
                        path="/estandarizacion"
                        element={diferido(<Estandarizacion />)}
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
