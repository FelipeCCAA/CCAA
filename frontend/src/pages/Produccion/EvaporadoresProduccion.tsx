import { useState } from "react";
import { Factory, RefreshCw } from "lucide-react";

import EstadoEquipo from "../../components/EstadoEquipo/EstadoEquipo";
import { obtenerEquipos, type Equipo } from "../../services/maestros.service";
import {
  iniciarCondensacion,
  obtenerCondensaciones,
  obtenerEjecucionesOperativas,
  type CorridaCondensacion,
  type EjecucionOperativa,
} from "../../services/procesos.service";
import { ocupacionesPorEquipo } from "../../services/disponibilidad-equipos";
import { esErrorDeEquipo, mensajeErrorProceso } from "../../services/errores-proceso";
import CierreCondensacion from "../Procesos/CierreCondensacion";

export default function EvaporadoresProduccion() {
  const [abierto, setAbierto] = useState(false);
  const [equipos, setEquipos] = useState<Equipo[]>([]);
  const [corridas, setCorridas] = useState<CorridaCondensacion[]>([]);
  const [ejecuciones, setEjecuciones] = useState<EjecucionOperativa[]>([]);
  const [cargando, setCargando] = useState(false);
  const [accionando, setAccionando] = useState<number | null>(null);
  const [error, setError] = useState("");
  const [cerrando, setCerrando] = useState<CorridaCondensacion | null>(null);

  async function cargar() {
    if (cargando) return;
    setCargando(true);
    setError("");
    try {
      const [maquinas, pagina, operativas] = await Promise.all([
        obtenerEquipos(),
        obtenerCondensaciones(),
        obtenerEjecucionesOperativas(),
      ]);
      setEquipos(maquinas.filter((equipo) => equipo.activo && equipo.tipo === "evaporador"));
      setCorridas(pagina.results);
      setEjecuciones(operativas);
      setAbierto(true);
    } catch {
      setError("No se pudo cargar el estado de evaporadores.");
    } finally {
      setCargando(false);
    }
  }

  async function refrescarPanel() {
    try {
      const [pagina, operativas] = await Promise.all([
        obtenerCondensaciones(),
        obtenerEjecucionesOperativas(),
      ]);
      setCorridas(pagina.results);
      setEjecuciones(operativas);
      return true;
    } catch {
      return false;
    }
  }

  async function iniciar(corrida: CorridaCondensacion) {
    if (accionando !== null) return;
    setAccionando(corrida.id);
    setError("");
    try {
      await iniciarCondensacion(corrida.id);
      if (!await refrescarPanel()) {
        setError("La evaporación se inició, pero no se pudo actualizar la disponibilidad.");
      }
    } catch (errorPeticion: unknown) {
      const mensaje = mensajeErrorProceso(
        errorPeticion,
        "No se pudo iniciar: revisa saldo, Calidad, aseo y disponibilidad del evaporador.",
      );
      if (esErrorDeEquipo(errorPeticion)) {
        await refrescarPanel();
      }
      setError(mensaje);
    } finally {
      setAccionando(null);
    }
  }

  if (!abierto) {
    return (
      <section className="mb-8 rounded-2xl border border-blue-200 bg-blue-50/60 p-5">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div>
            <h2 className="flex items-center gap-2 font-bold text-slate-900"><Factory className="h-5 w-5 text-blue-700" /> Evaporación / condensación</h2>
            <p className="mt-1 text-sm text-slate-600">Consulta bajo demanda qué evaporador está disponible, reservado u ocupado.</p>
          </div>
          <button onClick={() => void cargar()} disabled={cargando} className="rounded-xl bg-blue-700 px-4 py-2.5 text-sm font-semibold text-white disabled:opacity-60">{cargando ? "Cargando…" : "Ver evaporadores"}</button>
        </div>
        {error && <p className="mt-3 text-sm text-rose-700">{error}</p>}
      </section>
    );
  }

  const ocupaciones = ocupacionesPorEquipo(ejecuciones);

  return (
    <section className="mb-8">
      {cerrando && <CierreCondensacion corrida={cerrando} onCerrar={() => setCerrando(null)} onCerrada={async () => { if (!await refrescarPanel()) setError("La salida se registró, pero no se pudo actualizar la disponibilidad."); setCerrando(null); }} />}
      <div className="mb-3 flex items-center justify-between">
        <div><h2 className="text-xl font-bold text-slate-900">Evaporadores</h2><p className="text-sm text-slate-600">La disponibilidad proviene de las ejecuciones reales del backend.</p></div>
        <button onClick={() => void cargar()} disabled={cargando} className="rounded-lg p-2 text-slate-600 disabled:opacity-50" aria-label="Actualizar evaporadores"><RefreshCw className={`h-4 w-4 ${cargando ? "animate-spin" : ""}`} /></button>
      </div>
      {error && <p className="mb-3 text-sm text-rose-700">{error}</p>}
      <div className="grid gap-4 md:grid-cols-3">
        {equipos.map((equipo) => {
          const ocupacion = ocupaciones.get(equipo.id);
          const corridaActiva = corridas.find((corrida) =>
            corrida.equipo_id === equipo.id && ["borrador", "en_proceso"].includes(corrida.estado),
          );
          const pendienteCalidad = corridas.find((corrida) =>
            corrida.equipo_id === equipo.id && corrida.estado === "pendiente_calidad",
          );
          return (
            <article key={equipo.id} className={`rounded-2xl border bg-white p-5 ${ocupacion?.disponibilidad === "ocupado" ? "border-blue-400 ring-1 ring-blue-200" : ocupacion ? "border-amber-300" : "border-slate-200"}`}>
              <div className="flex items-center justify-between gap-3">
                <span className="rounded-xl bg-blue-50 p-2 text-blue-700"><Factory className="h-5 w-5" /></span>
                <EstadoEquipo estado={ocupacion?.estado} ejecucion={ocupacion?.ejecucion} />
              </div>
              <h3 className="mt-4 font-bold text-slate-900">{equipo.codigo} · {equipo.nombre}</h3>
              {corridaActiva ? (
                <div className="mt-3 text-sm text-slate-600">
                  <p>{corridaActiva.silo_origen_codigo} → {corridaActiva.silo_destino_codigo}</p>
                  <p><b>{Number(corridaActiva.litros_entrada).toLocaleString("es-CL")} L</b> · lote {corridaActiva.lote_codigo}</p>
                  <p className="text-xs">Corrida {corridaActiva.ejecucion_codigo}</p>
                  {corridaActiva.estado === "borrador" && <button onClick={() => void iniciar(corridaActiva)} disabled={accionando !== null} className="mt-3 rounded-xl bg-blue-700 px-4 py-2 text-sm font-semibold text-white disabled:opacity-50">{accionando === corridaActiva.id ? "Iniciando…" : "Iniciar evaporación"}</button>}
                  {corridaActiva.estado === "en_proceso" && <button onClick={() => setCerrando(corridaActiva)} disabled={accionando !== null} className="mt-3 rounded-xl bg-blue-700 px-4 py-2 text-sm font-semibold text-white disabled:opacity-50">Registrar salida y cerrar</button>}
                </div>
              ) : <p className="mt-3 text-sm text-slate-500">Sin corrida físicamente activa.</p>}
              {pendienteCalidad && <p className="mt-3 rounded-lg bg-violet-50 px-3 py-2 text-xs font-medium text-violet-800">{pendienteCalidad.ejecucion_codigo} espera Calidad; no reserva el evaporador.</p>}
            </article>
          );
        })}
      </div>
    </section>
  );
}
