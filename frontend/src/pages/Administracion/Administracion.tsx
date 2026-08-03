import { useEffect, useMemo, useState } from "react";
import {
  BadgeCheck,
  BriefcaseBusiness,
  Search,
  ShieldCheck,
  Users,
} from "lucide-react";

import {
  obtenerTrabajadores,
  type Trabajador,
} from "../../services/usuario.service";
import { nombreParaMostrar } from "../../services/sesion";


function Indicador({
  etiqueta,
  valor,
  icono: Icono,
}: {
  etiqueta: string;
  valor: number;
  icono: typeof Users;
}) {
  return (
    <div className="rounded-2xl border border-slate-200 bg-white p-6">
      <div className="flex items-center justify-between">
        <div>
          <p className="text-sm font-medium text-slate-500">{etiqueta}</p>
          <p className="mt-3 text-3xl font-bold text-slate-900">{valor}</p>
        </div>
        <span className="rounded-xl bg-green-50 p-3 text-green-700">
          <Icono className="h-6 w-6" />
        </span>
      </div>
    </div>
  );
}


function Administracion() {
  const [trabajadores, setTrabajadores] = useState<Trabajador[]>([]);
  const [busqueda, setBusqueda] = useState("");
  const [area, setArea] = useState("");
  const [cargando, setCargando] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    let vigente = true;

    obtenerTrabajadores()
      .then((datos) => {
        if (vigente) setTrabajadores(datos);
      })
      .catch(() => {
        if (vigente) setError("No se pudo cargar la lista de trabajadores.");
      })
      .finally(() => {
        if (vigente) setCargando(false);
      });

    return () => {
      vigente = false;
    };
  }, []);

  const areas = useMemo(
    () =>
      [...new Set(trabajadores.map((t) => t.perfil?.area).filter(Boolean))]
        .sort() as string[],
    [trabajadores],
  );

  const visibles = useMemo(() => {
    const texto = busqueda.trim().toLocaleLowerCase("es");

    return trabajadores.filter((trabajador) => {
      const coincideArea = !area || trabajador.perfil?.area === area;
      const contenido = [
        nombreParaMostrar(trabajador),
        trabajador.username,
        trabajador.email,
        trabajador.perfil?.cargo,
        trabajador.perfil?.area,
        trabajador.perfil?.turno,
      ]
        .filter(Boolean)
        .join(" ")
        .toLocaleLowerCase("es");

      return coincideArea && (!texto || contenido.includes(texto));
    });
  }, [area, busqueda, trabajadores]);

  const activos = trabajadores.filter((t) => t.activo).length;
  return (
    <div className="px-8 py-10">
      <div className="mx-auto max-w-7xl">
        <header className="mb-10">
          <p className="text-sm font-semibold uppercase tracking-wider text-green-700">
            Administración
          </p>
          <h1 className="mt-2 text-3xl font-bold text-slate-800">
            Panel de personal
          </h1>
          <p className="mt-2 text-slate-500">
            Consulta los usuarios, sus funciones y el área asignada en su perfil.
          </p>
        </header>

        <section className="grid grid-cols-1 gap-6 sm:grid-cols-2 xl:grid-cols-4">
          <Indicador etiqueta="Usuarios registrados" valor={trabajadores.length} icono={Users} />
          <Indicador etiqueta="Cuentas activas" valor={activos} icono={BadgeCheck} />
          <Indicador etiqueta="Áreas registradas" valor={areas.length} icono={BriefcaseBusiness} />
          <Indicador etiqueta="Administradores" valor={trabajadores.filter((t) => t.perfil?.nivel === "admin" || t.rol === "admin").length} icono={ShieldCheck} />
        </section>

        <section className="mt-10 overflow-hidden rounded-2xl border border-slate-200 bg-white">
          <div className="flex flex-col gap-4 border-b border-slate-200 px-6 py-5 lg:flex-row lg:items-center lg:justify-between">
            <div>
              <h2 className="text-lg font-semibold text-slate-800">Trabajadores</h2>
              <p className="mt-1 text-sm text-slate-400">
                {visibles.length} de {trabajadores.length} usuarios
              </p>
            </div>

            <div className="flex flex-col gap-3 sm:flex-row">
              <label className="relative">
                <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
                <input
                  value={busqueda}
                  onChange={(e) => setBusqueda(e.target.value)}
                  placeholder="Buscar trabajador"
                  className="w-full rounded-xl border border-slate-300 py-2.5 pl-10 pr-4 text-sm outline-none focus:border-green-600 sm:w-64"
                />
              </label>
              <select
                value={area}
                onChange={(e) => setArea(e.target.value)}
                className="rounded-xl border border-slate-300 bg-white px-4 py-2.5 text-sm text-slate-600 outline-none focus:border-green-600"
              >
                <option value="">Todas las áreas</option>
                {areas.map((nombre) => <option key={nombre}>{nombre}</option>)}
              </select>
            </div>
          </div>

          {cargando ? (
            <p className="px-6 py-10 text-sm text-slate-400">Cargando personal…</p>
          ) : error ? (
            <p className="px-6 py-10 text-sm text-red-700">{error}</p>
          ) : visibles.length === 0 ? (
            <p className="px-6 py-10 text-sm text-slate-400">No hay trabajadores que coincidan con los filtros.</p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-left text-sm">
                <thead className="bg-slate-50 text-slate-500">
                  <tr>
                    <th className="px-6 py-3 font-medium">Trabajador</th>
                    <th className="px-6 py-3 font-medium">Área</th>
                    <th className="px-6 py-3 font-medium">Cargo</th>
                    <th className="px-6 py-3 font-medium">Turno</th>
                    <th className="px-6 py-3 font-medium">Rol</th>
                    <th className="px-6 py-3 font-medium">Estado</th>
                  </tr>
                </thead>
                <tbody>
                  {visibles.map((trabajador) => (
                    <tr key={trabajador.id} className="border-t border-slate-100">
                      <td className="px-6 py-4">
                        <p className="font-medium text-slate-800">{nombreParaMostrar(trabajador)}</p>
                        <p className="mt-0.5 text-xs text-slate-400">{trabajador.email || `@${trabajador.username}`}</p>
                      </td>
                      <td className="px-6 py-4 text-slate-600">{trabajador.perfil?.area || "Sin área"}</td>
                      <td className="px-6 py-4 text-slate-600">{trabajador.perfil?.cargo || "—"}</td>
                      <td className="px-6 py-4 text-slate-600">{trabajador.perfil?.turno || "—"}</td>
                      <td className="px-6 py-4">
                        <span className="rounded-full bg-slate-100 px-3 py-1 text-xs font-medium text-slate-600">
                          {trabajador.perfil?.nivel_etiqueta || (trabajador.rol === "admin" ? "Administrador" : "Sin nivel")}
                        </span>
                      </td>
                      <td className="px-6 py-4">
                        <span className={trabajador.activo ? "text-green-700" : "text-slate-400"}>
                          {trabajador.activo ? "Activo" : "Inactivo"}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>
      </div>
    </div>
  );
}


export default Administracion;
