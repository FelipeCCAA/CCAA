import { NavLink, useNavigate } from "react-router-dom";

import {
  LayoutDashboard,
  Factory,
  Truck,
  ClipboardCheck,
  Database,
  LogOut,
} from "lucide-react";

import {
  cargoParaMostrar,
  cerrarSesion,
  nombreParaMostrar,
  obtenerSesion,
} from "../../services/sesion";

import { cerrarSesionEnServidor } from "../../services/usuario.service";

import logo from "../../assets/logos/logo-campos-australes-normal.png";


/*
  Módulos del sistema.

  `ruta` en null significa que la página todavía no existe. Se muestra en el
  menú (para que se vea el alcance del sistema) pero no es un enlace, así
  nadie llega a una pantalla en blanco. Al crear la página, se le pone su
  ruta aquí y queda navegable.
*/

const modulos = [
  {
    etiqueta: "Panel general",
    ruta: "/dashboard",
    icono: LayoutDashboard,
  },
  {
    etiqueta: "Producción",
    ruta: "/produccion",
    icono: Factory,
  },
  {
    etiqueta: "Recepción y silos",
    ruta: null,
    icono: Truck,
  },
  {
    etiqueta: "Liberación de producto",
    ruta: null,
    icono: ClipboardCheck,
  },
  {
    etiqueta: "Maestros",
    ruta: null,
    icono: Database,
  },
];


const enlaceBase =
  "flex items-center gap-3 rounded-xl px-4 py-3 text-sm font-medium transition-colors";


function Navbar() {

  const navegar = useNavigate();
  const sesion = obtenerSesion();

  const salir = async () => {

    // Se invalida el token en el servidor. Si la llamada falla (servidor
    // caído, red), igual se cierra en el navegador: dejar al usuario dentro
    // porque no se pudo avisar sería peor.
    try {
      await cerrarSesionEnServidor();
    } catch (error) {
      console.error("No se pudo invalidar el token en el servidor:", error);
    }

    cerrarSesion();
    navegar("/login", { replace: true });

  };

  return (
    <aside className="sticky top-0 flex h-screen w-64 flex-col border-r border-slate-200 bg-white">

      {/* Logo */}

      <div className="px-6 py-8">

        <img
          src={logo}
          alt="Campos Australes"
          className="w-40"
        />

      </div>

      {/* Módulos */}

      <nav className="flex-1 space-y-1 px-4">

        {modulos.map((modulo) => {

          const Icono = modulo.icono;

          if (!modulo.ruta) {

            return (

              <div
                key={modulo.etiqueta}
                className={`${enlaceBase} cursor-default text-slate-300`}
                title="Módulo aún no desarrollado"
              >

                <Icono className="h-5 w-5" />

                <span className="flex-1">{modulo.etiqueta}</span>

                <span className="rounded-full bg-slate-100 px-2 py-0.5 text-[10px] font-semibold text-slate-400">

                  Pronto

                </span>

              </div>

            );

          }

          return (

            <NavLink
              key={modulo.etiqueta}
              to={modulo.ruta}
              className={({ isActive }) =>
                isActive
                  ? `${enlaceBase} bg-green-50 text-green-700`
                  : `${enlaceBase} text-slate-600 hover:bg-slate-50 hover:text-slate-900`
              }
            >

              <Icono className="h-5 w-5" />

              {modulo.etiqueta}

            </NavLink>

          );

        })}

      </nav>

      {/* Usuario */}

      <div className="border-t border-slate-200 p-4">

        <div className="mb-3 px-2">

          <p className="text-sm font-medium text-slate-800">

            {sesion ? nombreParaMostrar(sesion.usuario) : "Sin sesión"}

          </p>

          <p className="text-xs text-slate-400">

            {sesion ? cargoParaMostrar(sesion.usuario) : ""}

          </p>

        </div>

        <button
          type="button"
          onClick={salir}
          className={`${enlaceBase} w-full text-slate-600 hover:bg-slate-50 hover:text-slate-900`}
        >

          <LogOut className="h-5 w-5" />

          Cerrar sesión

        </button>

      </div>

    </aside>
  );
}


export default Navbar;
