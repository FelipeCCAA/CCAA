import { useState } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import {
  CalendarRange,
  ChevronRight,
  ClipboardCheck,
  ClipboardList,
  Database,
  Factory,
  FlaskConical,
  GitBranch,
  History,
  Home,
  LogOut,
  Menu,
  PackageCheck,
  ShieldCheck,
  Truck,
  Users,
  Warehouse,
  Wind,
  X,
  type LucideIcon,
} from "lucide-react";

import logo from "../../assets/logos/logo-campos-australes-normal.png";
import NotificacionesOperacionales from "../Navegacion/NotificacionesOperacionales";
import {
  esEnlaceOperacionalActual,
  navegacionPara,
  type EnlaceOperacional,
  type IconoNavegacion,
} from "../../services/navegacion-operacional";
import {
  cargoParaMostrar,
  cerrarSesion,
  nombreParaMostrar,
  obtenerSesion,
} from "../../services/sesion";
import { cerrarSesionEnServidor } from "../../services/usuario.service";

const ICONOS: Record<IconoNavegacion, LucideIcon> = {
  auditoria: History,
  calidad: ClipboardCheck,
  configuracion: Database,
  despacho: Truck,
  documentos: ClipboardList,
  envasado: PackageCheck,
  estandarizacion: FlaskConical,
  inicio: Home,
  inventario: Warehouse,
  inocuidad: ShieldCheck,
  planificacion: CalendarRange,
  procesos: GitBranch,
  produccion: Factory,
  recepcion: Truck,
  secado: Wind,
  silos: Warehouse,
  usuarios: Users,
};

const enlaceBase =
  "group flex min-h-11 items-center gap-3 rounded-xl px-3 text-sm font-medium transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-emerald-600";

function Navbar() {
  const [abierto, setAbierto] = useState(false);
  const navegar = useNavigate();
  const ubicacion = useLocation();
  const sesion = obtenerSesion();
  const navegacion = sesion ? navegacionPara(sesion.usuario) : null;

  const salir = async () => {
    try {
      await cerrarSesionEnServidor();
    } catch (error) {
      console.error("No se pudo invalidar el token en el servidor:", error);
    }
    cerrarSesion();
    navegar("/login", { replace: true });
  };

  const estaActivo = (enlace: EnlaceOperacional) =>
    esEnlaceOperacionalActual(
      enlace,
      ubicacion.pathname,
      ubicacion.search,
      ubicacion.hash,
    );

  const contenido = (
    <>
      <div className="border-b border-slate-100 px-5 py-4">
        <div className="flex min-h-12 items-center justify-between">
          <img src={logo} alt="Campos Australes" className="w-40" />
          <button
            type="button"
            onClick={() => setAbierto(false)}
            className="rounded-lg p-2 text-slate-600 hover:bg-slate-100 md:hidden"
            aria-label="Cerrar menú"
          >
            <X className="h-5 w-5" />
          </button>
        </div>
        {navegacion && (
          <Link
            to={navegacion.inicio.ruta}
            onClick={() => setAbierto(false)}
            aria-current={estaActivo(navegacion.inicio) ? "page" : undefined}
            className={`mt-3 flex min-h-12 items-center gap-3 rounded-xl border px-3 py-2.5 transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-emerald-600 ${
              estaActivo(navegacion.inicio)
                ? "border-emerald-300 bg-emerald-50 text-emerald-900"
                : "border-slate-200 bg-slate-50 text-slate-800 hover:border-emerald-300"
            }`}
          >
            <Home className="h-5 w-5 shrink-0 text-emerald-700" aria-hidden="true" />
            <span className="min-w-0">
              <span className="block text-[10px] font-bold uppercase tracking-wider text-emerald-700">
                Entrada del puesto
              </span>
              <span className="block truncate text-sm font-semibold">
                {navegacion.inicio.etiqueta}
              </span>
            </span>
            <ChevronRight className="ml-auto h-4 w-4 shrink-0" aria-hidden="true" />
          </Link>
        )}
      </div>

      <nav className="flex-1 overflow-y-auto px-3 py-5" aria-label="Navegación operacional">
        <div className="space-y-6">
          {(navegacion?.grupos ?? []).map((grupo) => (
            <section key={grupo.etiqueta} aria-labelledby={`nav-${grupo.etiqueta}`}>
              <p
                id={`nav-${grupo.etiqueta}`}
                className="mb-2 px-3 text-[10px] font-bold uppercase tracking-[0.16em] text-slate-600"
              >
                {grupo.etiqueta}
              </p>
              <div className="space-y-1">
                {grupo.enlaces.map((enlace) => {
                  const Icono = ICONOS[enlace.icono];
                  const activo = estaActivo(enlace);
                  return (
                    <Link
                      key={enlace.ruta}
                      to={enlace.ruta}
                      onClick={() => setAbierto(false)}
                      aria-current={activo ? "page" : undefined}
                      className={`${enlaceBase} ${
                        enlace.nivel === "proceso" ? "ml-4 border-l border-slate-200 pl-3" : ""
                      } ${
                        activo
                          ? "bg-emerald-50 text-emerald-800"
                          : "text-slate-600 hover:bg-slate-50 hover:text-slate-950"
                      }`}
                    >
                      <Icono
                        className={`h-[18px] w-[18px] shrink-0 ${
                          activo ? "text-emerald-700" : "text-slate-500"
                        }`}
                        strokeWidth={1.8}
                        aria-hidden="true"
                      />
                      <span className="truncate">{enlace.etiqueta}</span>
                      {activo && (
                        <span className="ml-auto h-1.5 w-1.5 rounded-full bg-emerald-600" />
                      )}
                    </Link>
                  );
                })}
              </div>
            </section>
          ))}
        </div>
      </nav>

      <NotificacionesOperacionales alNavegar={() => setAbierto(false)} />

      <div className="border-t border-slate-100 p-3">
        <div className="mb-2 flex items-center gap-3 rounded-xl bg-slate-50 px-3 py-3">
          <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-emerald-700 text-xs font-bold uppercase text-white">
            {sesion ? nombreParaMostrar(sesion.usuario).slice(0, 2) : "—"}
          </span>
          <div className="min-w-0">
            <p className="truncate text-sm font-semibold text-slate-800">
              {sesion ? nombreParaMostrar(sesion.usuario) : "Sin sesión"}
            </p>
            <p className="truncate text-[11px] text-slate-600">
              {sesion ? cargoParaMostrar(sesion.usuario) : ""}
            </p>
          </div>
        </div>
        <button
          type="button"
          onClick={salir}
          className={`${enlaceBase} w-full text-slate-600 hover:bg-rose-50 hover:text-rose-700`}
        >
          <LogOut className="h-[18px] w-[18px]" strokeWidth={1.8} />
          Cerrar sesión
        </button>
      </div>
    </>
  );

  return (
    <>
      <header className="sticky top-0 z-40 flex h-16 items-center justify-between border-b border-slate-200 bg-white/95 px-4 backdrop-blur md:hidden">
        <div>
          <img src={logo} alt="Campos Australes" className="w-32" />
          {navegacion && (
            <p className="mt-0.5 text-[10px] font-semibold uppercase tracking-wide text-emerald-700">
              {navegacion.area}
            </p>
          )}
        </div>
        <button
          type="button"
          onClick={() => setAbierto(true)}
          className="rounded-xl border border-slate-200 p-2.5 text-slate-600"
          aria-label="Abrir menú"
          aria-expanded={abierto}
        >
          <Menu className="h-5 w-5" />
        </button>
      </header>

      {abierto && (
        <button
          type="button"
          className="fixed inset-0 z-40 bg-slate-950/40 md:hidden"
          onClick={() => setAbierto(false)}
          aria-label="Cerrar menú"
        />
      )}
      <aside
        className={`fixed inset-y-0 left-0 z-50 flex w-72 flex-col border-r border-slate-200 bg-white transition-transform duration-200 md:sticky md:top-0 md:h-screen md:translate-x-0 ${
          abierto ? "translate-x-0" : "-translate-x-full"
        }`}
      >
        {contenido}
      </aside>
    </>
  );
}

export default Navbar;
