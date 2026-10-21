import { useEffect, useState } from "react";
import { Navigate, Outlet, useLocation } from "react-router-dom";

import { actualizarUsuarioSesion, obtenerSesion, obtenerToken } from "../../services/sesion";
import { obtenerUsuarioActual } from "../../services/usuario.service";


/*
  Envuelve las rutas que exigen haber iniciado sesión.

  Si no hay sesión, manda al login y recuerda a dónde iba el usuario, para
  devolverlo ahí después de entrar en vez de dejarlo siempre en el panel.
*/

function RutaProtegida() {

  const ubicacion = useLocation();
  const token = obtenerToken();
  const [intento, setIntento] = useState(0);
  const [validacion, setValidacion] = useState<{
    token: string; intento: number; correcta: boolean;
  } | null>(null);

  useEffect(() => {
    let vigente = true;
    if (token) {
      obtenerUsuarioActual()
        .then((usuario) => {
          if (!vigente) return;
          const correcta = actualizarUsuarioSesion(token, usuario);
          setValidacion({ token, intento, correcta });
        })
        .catch(() => {
          if (vigente) setValidacion({ token, intento, correcta: false });
        });
    }
    return () => { vigente = false; };
  }, [token, intento]);

  useEffect(() => {
    const actualizar = () => setIntento((actual) => actual + 1);
    const cambioAlmacen = (evento: StorageEvent) => {
      if (evento.key === "ccaa.sesion" || evento.key === null) actualizar();
    };
    window.addEventListener("storage", cambioAlmacen);
    window.addEventListener("ccaa:sesion-cerrada", actualizar);
    return () => {
      window.removeEventListener("storage", cambioAlmacen);
      window.removeEventListener("ccaa:sesion-cerrada", actualizar);
    };
  }, []);

  if (!token) {

    return (
      <Navigate
        to="/login"
        replace
        state={{ desde: ubicacion.pathname }}
      />
    );

  }

  if (validacion?.token !== token || validacion.intento !== intento) {
    return <p role="status" className="p-10 text-sm text-slate-600">Verificando acceso…</p>;
  }

  if (!validacion.correcta) {
    return <main className="p-10">
      <p role="alert">No pudimos verificar tu acceso. Reintenta para continuar.</p>
      <button type="button" onClick={() => setIntento((actual) => actual + 1)} className="mt-4 rounded-lg bg-slate-900 px-4 py-2 text-white">Reintentar</button>
    </main>;
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
