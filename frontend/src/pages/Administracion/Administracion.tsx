import { useEffect, useMemo, useState } from "react";
import axios from "axios";
import {
  BadgeCheck,
  BriefcaseBusiness,
  Search,
  ShieldCheck,
  Users,
} from "lucide-react";

import {
  cambiarEstadoTrabajador,
  crearTrabajador,
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
  const [mostrarFormulario, setMostrarFormulario] = useState(false);
  const [nuevo, setNuevo] = useState<{ username: string; email: string; nombre: string; apellido: string; area: string; nivel: "admin" | "trabajador"; cargo: string; password: string }>({ username: "", email: "", nombre: "", apellido: "", area: "secado", nivel: "trabajador", cargo: "", password: "" });

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
      ]
        .filter(Boolean)
        .join(" ")
        .toLocaleLowerCase("es");

      return coincideArea && (!texto || contenido.includes(texto));
    });
  }, [area, busqueda, trabajadores]);

  const activos = trabajadores.filter((t) => t.activo).length;
  const guardarNuevo = async (evento: React.FormEvent) => {
    evento.preventDefault();
    try {
      const creado = await crearTrabajador(nuevo);
      setTrabajadores((actuales) => [...actuales, creado]);
      setNuevo({ username: "", email: "", nombre: "", apellido: "", area: "secado", nivel: "trabajador", cargo: "", password: "" });
      setMostrarFormulario(false);
      setError("");
    } catch (errorCreacion) {
      const mensaje = axios.isAxiosError(errorCreacion) && typeof errorCreacion.response?.data?.error === "string"
        ? errorCreacion.response.data.error
        : "No se pudo crear el usuario. Revisa los datos ingresados.";
      setError(mensaje);
    }
  };

  const alternar = async (trabajador: Trabajador) => {
    try {
      const actualizado = await cambiarEstadoTrabajador(trabajador.id, !trabajador.activo);
      setTrabajadores((actuales) => actuales.map((t) => t.id === actualizado.id ? actualizado : t));
    } catch { setError("No se pudo cambiar el estado del usuario."); }
  };
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

        <section className="mt-10 rounded-2xl border border-slate-200 bg-white p-6">
          <div className="flex items-center justify-between gap-4"><div><h2 className="text-lg font-semibold text-slate-800">Personal</h2><p className="mt-1 text-sm text-slate-400">Crea una cuenta con contraseña inicial para ingreso inmediato.</p></div><button type="button" onClick={() => setMostrarFormulario((visible) => !visible)} className="rounded-xl bg-green-700 px-5 py-3 text-sm font-semibold text-white">{mostrarFormulario ? "Cancelar" : "Agregar trabajador"}</button></div>
          {mostrarFormulario && <>
          <h3 className="mt-6 font-semibold text-slate-700">Nuevo trabajador</h3>
          <form onSubmit={guardarNuevo} className="mt-5 grid gap-3 md:grid-cols-2 xl:grid-cols-4">
            <input required placeholder="Usuario" value={nuevo.username} onChange={(e) => setNuevo({ ...nuevo, username: e.target.value })} className="rounded-xl border border-slate-300 px-4 py-3 text-sm" />
            <input type="email" placeholder="Correo corporativo" value={nuevo.email} onChange={(e) => setNuevo({ ...nuevo, email: e.target.value })} className="rounded-xl border border-slate-300 px-4 py-3 text-sm" />
            <input placeholder="Nombre" value={nuevo.nombre} onChange={(e) => setNuevo({ ...nuevo, nombre: e.target.value })} className="rounded-xl border border-slate-300 px-4 py-3 text-sm" />
            <input placeholder="Apellido" value={nuevo.apellido} onChange={(e) => setNuevo({ ...nuevo, apellido: e.target.value })} className="rounded-xl border border-slate-300 px-4 py-3 text-sm" />
            <input required type="password" minLength={8} autoComplete="new-password" placeholder="Contraseña inicial" value={nuevo.password} onChange={(e) => setNuevo({ ...nuevo, password: e.target.value })} className="rounded-xl border border-slate-300 px-4 py-3 text-sm" />
            <select value={nuevo.area} onChange={(e) => setNuevo({ ...nuevo, area: e.target.value })} className="rounded-xl border border-slate-300 bg-white px-4 py-3 text-sm">
              {["recepcion", "condensacion", "secado", "envase", "calidad", "bodega", "compras", "despacho", "administracion"].map((a) => <option key={a} value={a}>{a}</option>)}
            </select>
            <select value={nuevo.nivel} onChange={(e) => setNuevo({ ...nuevo, nivel: e.target.value as "admin" | "trabajador" })} className="rounded-xl border border-slate-300 bg-white px-4 py-3 text-sm"><option value="trabajador">Trabajador</option><option value="admin">Administrador de área</option></select>
            <input placeholder="Cargo" value={nuevo.cargo} onChange={(e) => setNuevo({ ...nuevo, cargo: e.target.value })} className="rounded-xl border border-slate-300 px-4 py-3 text-sm" />
            <button className="rounded-xl bg-green-700 px-5 py-3 text-sm font-semibold text-white">Crear usuario</button>
          </form>
          </>}
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
                      <td className="px-6 py-4">
                        <span className="rounded-full bg-slate-100 px-3 py-1 text-xs font-medium text-slate-600">
                          {trabajador.perfil?.nivel_etiqueta || (trabajador.rol === "admin" ? "Administrador" : "Sin nivel")}
                        </span>
                      </td>
                      <td className="px-6 py-4">
                        <button type="button" onClick={() => void alternar(trabajador)} className={trabajador.activo ? "text-green-700 hover:underline" : "text-slate-400 hover:underline"}>
                          {trabajador.activo ? "Activo" : "Inactivo"}
                        </button>
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
