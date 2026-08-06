import { NavLink, useNavigate } from "react-router-dom";

import {
  LayoutDashboard,
  Factory,
  Truck,
  ClipboardCheck,
  CalendarRange,
  ClipboardList,
  Database,
  History,
  Users,
  Boxes,
  GitBranch,
  Milk,
  Wrench,
  LogOut,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";

import {
  cargoParaMostrar,
  cerrarSesion,
  nombreParaMostrar,
  obtenerSesion,
} from "../../services/sesion";

import { cerrarSesionEnServidor } from "../../services/usuario.service";

import logo from "../../assets/logos/logo-campos-australes-normal.png";


/*
  Módulos del sistema, agrupados y en el orden del flujo de planta: llega la
  leche, se planifica, se produce, Calidad libera.

  Antes eran enlaces planos ordenados por cuándo se fueron agregando
  —«Abastecimiento» arriba de «Panel general»— y con dos entradas distintas,
  mismo icono, para el mismo dominio: «Abastecimiento y Bodega» e «Inventario
  y MRP». Esta última ya no existe: su contenido son dos pestañas dentro de
  abastecimiento.

  **`areas` restringe a quién se le muestra el módulo.** Un módulo sin `areas`
  lo ve cualquiera; uno que las declara, solo quien trabaja ahí (y quien tenga
  rol de administración, que ve todo). No es seguridad —eso lo aplica el
  backend— sino no ofrecerle a un operador de envase una pantalla que no le
  toca.

  `ruta: null` significa que la pantalla todavía no existe. Se muestra apagada
  para que se vea el alcance del sistema, pero no navega a ninguna parte.
*/

/* El tipo va declarado y no inferido: sin él, TypeScript deduce una forma
   distinta por grupo —los que no declaran `areas` quedan sin ese campo— y
   filtrarlos todos con la misma función deja de compilar. */
interface Modulo {
  etiqueta: string;
  ruta: string | null;
  icono: LucideIcon;
  areas?: string[];
}

interface Grupo {
  titulo: string | null;
  modulos: Modulo[];
}

const GRUPOS: Grupo[] = [
  {
    titulo: null,
    modulos: [
      { etiqueta: "Panel general", ruta: "/dashboard", icono: LayoutDashboard },
    ],
  },
  {
    titulo: "Operación",
    modulos: [
      { etiqueta: "Planificación", ruta: "/planificacion", icono: CalendarRange },
      { etiqueta: "Recolección en predios", ruta: "/recoleccion", icono: Milk },
      { etiqueta: "Recepción y silos", ruta: "/recepcion", icono: Truck },
      { etiqueta: "Producción", ruta: "/produccion", icono: Factory },
      {
        etiqueta: "Procesamiento y trazabilidad",
        ruta: "/procesos",
        icono: GitBranch,
        areas: ["condensacion", "secado", "envase", "administracion"],
      },
      { etiqueta: "Abastecimiento", ruta: "/abastecimiento", icono: Boxes },
      {
        etiqueta: "Mantenimiento",
        ruta: "/mantenimiento",
        icono: Wrench,
        areas: ["mantenimiento", "administracion"],
      },
    ],
  },
  {
    titulo: "Calidad",
    modulos: [
      { etiqueta: "Liberación de producto", ruta: "/liberacion", icono: ClipboardCheck },
      { etiqueta: "Registros de planta", ruta: "/registros", icono: ClipboardList },
    ],
  },
  {
    titulo: "Configuración",
    modulos: [
      { etiqueta: "Maestros", ruta: "/maestros", icono: Database },
      { etiqueta: "Auditoría", ruta: "/auditoria", icono: History },
    ],
  },
];


const enlaceBase =
  "flex items-center gap-3 rounded-xl px-4 py-3 text-sm font-medium transition-colors";


function Navbar() {

  const navegar = useNavigate();
  const sesion = obtenerSesion();
  const esAdmin =
    sesion?.usuario.rol === "admin" || sesion?.usuario.perfil?.nivel === "admin";

  const area = sesion?.usuario.perfil?.area;

  /* Un módulo sin `areas` lo ve cualquiera; uno que las declara, solo quien
     trabaja ahí. Administración ve todo. */
  const leToca = (modulo: { areas?: string[] }) =>
    !modulo.areas || esAdmin || (!!area && modulo.areas.includes(area));

  // Administración se agrega al grupo de configuración en vez de encabezar el
  // menú: es de mantención, no de trabajo diario.
  const grupos = GRUPOS.map((grupo) => ({
    ...grupo,
    modulos: (grupo.titulo === "Configuración" && esAdmin
      ? [
          { etiqueta: "Administración", ruta: "/administracion", icono: Users },
          ...grupo.modulos,
        ]
      : grupo.modulos
    ).filter(leToca),
    // Un grupo que se queda sin módulos no debe dejar su título suelto.
  })).filter((grupo) => grupo.modulos.length > 0);

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

      <nav className="flex-1 overflow-y-auto px-4 pb-4">

        {grupos.map((grupo) => (

          <div key={grupo.titulo ?? "inicio"} className="mb-6 space-y-1">

            {grupo.titulo && (
              <p className="px-4 pb-2 text-[11px] font-semibold uppercase tracking-wider text-slate-400">
                {grupo.titulo}
              </p>
            )}

            {grupo.modulos.map((modulo) => {

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

          </div>

        ))}

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
