import { useState } from "react";
import { NavLink, useNavigate } from "react-router-dom";
import {
  Boxes,
  CalendarRange,
  ClipboardCheck,
  ClipboardList,
  Database,
  Factory,
  FlaskConical,
  GitBranch,
  History,
  LayoutDashboard,
  LogOut,
  MapPinned,
  Menu,
  Truck,
  Users,
  Wrench,
  X,
  type LucideIcon,
} from "lucide-react";

import { cargoParaMostrar, cerrarSesion, nombreParaMostrar, obtenerSesion } from "../../services/sesion";
import { cerrarSesionEnServidor } from "../../services/usuario.service";
import logo from "../../assets/logos/logo-campos-australes-normal.png";


interface Modulo {
  etiqueta: string;
  ruta: string;
  icono: LucideIcon;
  areas?: string[];
}

interface Grupo {
  etiqueta: string;
  modulos: Modulo[];
}

const gruposBase: Grupo[] = [
  {
    etiqueta: "Inicio",
    modulos: [{ etiqueta: "Panel general", ruta: "/dashboard", icono: LayoutDashboard }],
  },
  {
    etiqueta: "Flujo de planta",
    modulos: [
      { etiqueta: "Planificación", ruta: "/planificacion", icono: CalendarRange },
      { etiqueta: "Abastecimiento", ruta: "/abastecimiento", icono: Boxes },
      { etiqueta: "Recolección", ruta: "/recoleccion", icono: MapPinned },
      { etiqueta: "Recepción y silos", ruta: "/recepcion", icono: Truck },
      { etiqueta: "Estandarización", ruta: "/estandarizacion", icono: FlaskConical },
      { etiqueta: "Producción", ruta: "/produccion", icono: Factory },
      { etiqueta: "Procesos", ruta: "/procesos", icono: GitBranch, areas: ["condensacion", "secado", "envase", "administracion"] },
      { etiqueta: "Liberación", ruta: "/liberacion", icono: ClipboardCheck },
      { etiqueta: "Registros de planta", ruta: "/registros", icono: ClipboardList },
    ],
  },
  {
    etiqueta: "Soporte",
    modulos: [
      { etiqueta: "Mantenimiento", ruta: "/mantenimiento", icono: Wrench, areas: ["mantenimiento", "administracion"] },
    ],
  },
  {
    etiqueta: "Gestión",
    modulos: [
      { etiqueta: "Maestros", ruta: "/maestros", icono: Database },
      { etiqueta: "Auditoría", ruta: "/auditoria", icono: History },
      { etiqueta: "Administración", ruta: "/administracion", icono: Users, areas: ["administracion"] },
    ],
  },
];

const enlaceBase = "group flex h-10 items-center gap-3 rounded-xl px-3 text-sm font-medium transition";


function Navbar() {
  const [abierto, setAbierto] = useState(false);
  const navegar = useNavigate();
  const sesion = obtenerSesion();
  const area = sesion?.usuario.perfil?.area;
  const esAdmin = sesion?.usuario.rol === "admin" || sesion?.usuario.perfil?.nivel === "admin";

  const grupos = gruposBase
    .map((grupo) => ({
      ...grupo,
      modulos: grupo.modulos.filter((modulo) => {
        if (!modulo.areas) return true;
        if (modulo.ruta === "/inventario" || modulo.ruta === "/administracion") return esAdmin;
        return esAdmin || Boolean(area && modulo.areas.includes(area));
      }),
    }))
    .filter((grupo) => grupo.modulos.length > 0);

  const salir = async () => {
    try {
      await cerrarSesionEnServidor();
    } catch (error) {
      console.error("No se pudo invalidar el token en el servidor:", error);
    }
    cerrarSesion();
    navegar("/login", { replace: true });
  };

  const contenido = (
    <>
      <div className="flex h-20 items-center justify-between border-b border-slate-100 px-5">
        <img src={logo} alt="Campos Australes" className="w-40" />
        <button type="button" onClick={() => setAbierto(false)} className="rounded-lg p-2 text-slate-400 hover:bg-slate-100 md:hidden" aria-label="Cerrar menú"><X className="h-5 w-5" /></button>
      </div>

      <nav className="flex-1 overflow-y-auto px-3 py-5">
        <div className="space-y-6">
          {grupos.map((grupo) => (
            <section key={grupo.etiqueta}>
              <p className="mb-2 px-3 text-[10px] font-bold uppercase tracking-[0.16em] text-slate-400">{grupo.etiqueta}</p>
              <div className="space-y-1">
                {grupo.modulos.map((modulo) => {
                  const Icono = modulo.icono;
                  return (
                    <NavLink
                      key={modulo.ruta}
                      to={modulo.ruta}
                      onClick={() => setAbierto(false)}
                      className={({ isActive }) => isActive ? `${enlaceBase} bg-emerald-50 text-emerald-800` : `${enlaceBase} text-slate-600 hover:bg-slate-50 hover:text-slate-950`}
                    >
                      {({ isActive }) => (
                        <>
                          <Icono className={`h-[18px] w-[18px] shrink-0 ${isActive ? "text-emerald-700" : "text-slate-400 group-hover:text-slate-600"}`} strokeWidth={1.8} />
                          <span className="truncate">{modulo.etiqueta}</span>
                          {isActive && <span className="ml-auto h-1.5 w-1.5 rounded-full bg-emerald-600" />}
                        </>
                      )}
                    </NavLink>
                  );
                })}
              </div>
            </section>
          ))}
        </div>
      </nav>

      <div className="border-t border-slate-100 p-3">
        <div className="mb-2 flex items-center gap-3 rounded-xl bg-slate-50 px-3 py-3">
          <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-emerald-700 text-xs font-bold uppercase text-white">{sesion ? nombreParaMostrar(sesion.usuario).slice(0, 2) : "—"}</span>
          <div className="min-w-0"><p className="truncate text-sm font-semibold text-slate-800">{sesion ? nombreParaMostrar(sesion.usuario) : "Sin sesión"}</p><p className="truncate text-[11px] text-slate-400">{sesion ? cargoParaMostrar(sesion.usuario) : ""}</p></div>
        </div>
        <button type="button" onClick={salir} className={`${enlaceBase} w-full text-slate-500 hover:bg-rose-50 hover:text-rose-700`}><LogOut className="h-[18px] w-[18px]" strokeWidth={1.8} />Cerrar sesión</button>
      </div>
    </>
  );

  return (
    <>
      <header className="sticky top-0 z-40 flex h-16 items-center justify-between border-b border-slate-200 bg-white/95 px-4 backdrop-blur md:hidden">
        <img src={logo} alt="Campos Australes" className="w-36" />
        <button type="button" onClick={() => setAbierto(true)} className="rounded-xl border border-slate-200 p-2.5 text-slate-600" aria-label="Abrir menú"><Menu className="h-5 w-5" /></button>
      </header>

      {abierto && <button type="button" className="fixed inset-0 z-40 bg-slate-950/40 md:hidden" onClick={() => setAbierto(false)} aria-label="Cerrar menú" />}
      <aside className={`fixed inset-y-0 left-0 z-50 flex w-72 flex-col border-r border-slate-200 bg-white transition-transform duration-200 md:sticky md:top-0 md:h-screen md:translate-x-0 ${abierto ? "translate-x-0" : "-translate-x-full"}`}>{contenido}</aside>
    </>
  );
}


export default Navbar;
