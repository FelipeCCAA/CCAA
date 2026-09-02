import { lazy, Suspense } from "react";
import { Routes, Route, Navigate } from "react-router-dom";

import RutaProtegida from "../components/RutaProtegida/RutaProtegida";
import RutaAdmin from "../components/RutaAdmin/RutaAdmin";
import RutaModulo, { AccesoRestringido } from "../components/RutaModulo/RutaModulo";
import { destinoInicial } from "../services/access-control";
import { obtenerSesion } from "../services/sesion";

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
const LecheReporte = lazy(() => import("../pages/Leche/ReporteDiario"));
const Liberacion = lazy(() => import("../pages/Liberacion/Liberacion"));
const CentroCalidad = lazy(() => import("../pages/Calidad/CentroCalidad"));
const Planificacion = lazy(() => import("../pages/Planificacion/Planificacion"));
const Maestros = lazy(() => import("../pages/Maestros/Maestros"));
const Auditoria = lazy(() => import("../pages/Auditoria/Auditoria"));
const Registros = lazy(() => import("../pages/Registros/Registros"));
const Administracion = lazy(() => import("../pages/Administracion/Administracion"));
const CambiarPassword = lazy(() => import("../pages/CambiarPassword/CambiarPassword"));
const Procesos = lazy(() => import("../pages/Procesos/Procesos"));
const Aseos = lazy(() => import("../pages/Inocuidad/Aseos"));
const Inventario = lazy(() => import("../pages/Inventario/Inventario"));
const Envasado = lazy(() => import("../pages/Envasado/Envasado"));
const Secado = lazy(() => import("../pages/Secado/Secado"));

/* Abastecimiento queda conservado en código, pero no se monta ni precarga. */

const diferido = (componente: React.ReactNode) => (
  <Suspense fallback={<div className="p-10 text-sm text-slate-600">Cargando módulo…</div>}>
    {componente}
  </Suspense>
);

function InicioPorArea() {
  const usuario = obtenerSesion()?.usuario;
  return <Navigate to={usuario ? destinoInicial(usuario) : "/login"} replace />;
}


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

            <Route path="/" element={<InicioPorArea />} />

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

                    <Route element={<RutaModulo modulo="dashboard" />}>
                        <Route path="/dashboard" element={diferido(<Dashboard />)} />
                    </Route>

                    <Route element={<RutaModulo modulo="inventario" />}>
                        <Route path="/inventario" element={diferido(<Inventario />)} />
                    </Route>
                    {/* Compatibilidad sin montar el módulo desactivado. */}
                    <Route path="/abastecimiento/*" element={<Navigate to="/inventario" replace />} />

                    <Route element={<RutaModulo modulo="procesos" />}>
                        <Route path="/procesos" element={diferido(<Procesos />)} />
                        <Route path="/calidad/trazabilidad" element={diferido(<Procesos />)} />
                    </Route>

                    <Route path="/mantenimiento" element={<AccesoRestringido detalle="Mantención se encuentra desactivada." />} />

                    <Route element={<RutaModulo modulo="inocuidad" />}>
                        <Route path="/calidad/inocuidad" element={diferido(<Aseos />)} />
                        <Route path="/inocuidad/aseos" element={<Navigate to="/calidad/inocuidad" replace />} />
                    </Route>

                    {/* Acceso directo al panel de los ocho silos principales.
                        Reutiliza la pantalla de recepción y su única lectura
                        de ocupación; no duplica consultas ni reglas. */}
                    <Route element={<RutaModulo modulo="recepcion" />}>
                        <Route path="/silos" element={diferido(<LecheSilos soloPrincipales />)} />
                    </Route>

                    <Route element={<RutaModulo modulo="produccion" />}>
                        <Route path="/produccion" element={diferido(<Produccion />)} />
                    </Route>

                    <Route element={<RutaModulo modulo="secado" />}>
                        <Route path="/secado" element={diferido(<Secado />)} />
                    </Route>

                    <Route element={<RutaModulo modulo="envasado" />}>
                        <Route path="/envasado" element={diferido(<Envasado />)} />
                    </Route>

                    <Route element={<RutaModulo modulo="recepcion" />}>
                        <Route path="/leche" element={diferido(<Leche />)}>
                            <Route index element={diferido(<LechePanel />)} />
                            <Route path="rutas" element={diferido(<LecheRutas />)} />
                            <Route path="en-camino" element={diferido(<LecheEnCamino />)} />
                            <Route path="muestreo" element={diferido(<LecheMuestreo />)} />
                            <Route path="calidad" element={diferido(<LecheCalidad />)} />
                            <Route path="descarga" element={diferido(<LecheDescarga />)} />
                            <Route path="silos" element={diferido(<LecheSilos />)} />
                            <Route path="historial" element={diferido(<LecheHistorial />)} />
                            <Route path="reporte" element={diferido(<LecheReporte />)} />
                        </Route>
                    </Route>

                    {/* Las dos direcciones anteriores siguen funcionando: hay
                        enlaces guardados y gente con la ruta en la memoria. */}
                    <Route path="/recepcion" element={<Navigate to="/leche" replace />} />
                    <Route path="/recoleccion" element={<Navigate to="/leche/rutas" replace />} />

                    <Route element={<RutaModulo modulo="estandarizacion" />}>
                        <Route path="/estandarizacion" element={diferido(<Estandarizacion />)} />
                    </Route>

                    <Route element={<RutaModulo modulo="calidad" />}>
                        <Route path="/calidad" element={diferido(<CentroCalidad />)} />
                        <Route path="/calidad/expedientes" element={diferido(<Liberacion />)} />
                        <Route path="/liberacion" element={diferido(<Liberacion />)} />
                    </Route>

                    <Route element={<RutaModulo modulo="planificacion" />}>
                        <Route path="/planificacion" element={diferido(<Planificacion />)} />
                    </Route>

                    <Route element={<RutaModulo modulo="maestros" />}>
                        <Route path="/maestros" element={diferido(<Maestros />)} />
                    </Route>

                    <Route element={<RutaModulo modulo="registros" />}>
                        <Route path="/registros" element={diferido(<Registros />)} />
                        <Route path="/calidad/registros" element={diferido(<Registros />)} />
                    </Route>

                    <Route element={<RutaModulo modulo="auditoria" />}>
                        <Route path="/auditoria" element={diferido(<Auditoria />)} />
                    </Route>

                    <Route path="/acceso-restringido" element={<AccesoRestringido />} />

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
