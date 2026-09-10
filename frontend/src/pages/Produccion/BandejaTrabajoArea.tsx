import { useCallback, useEffect, useState } from "react";
import { ArrowRight, Play, RefreshCw } from "lucide-react";
import { Link } from "react-router-dom";

import StatusBadge from "../../components/ui/StatusBadge";
import { mensajeErrorProceso } from "../../services/errores-proceso";
import {
  obtenerEjecucionesOperativas,
  transicionarEjecucion,
  type EjecucionOperativa,
} from "../../services/procesos.service";

function destinoDe(ejecucion: EjecucionOperativa) {
  if (ejecucion.etapa_tipo === "secado") return "/secado";
  if (ejecucion.etapa_tipo === "estandarizacion") return "/estandarizacion";
  return `/procesos?seccion=${ejecucion.etapa_tipo}`;
}

export default function BandejaTrabajoArea() {
  const [ejecuciones, setEjecuciones] = useState<EjecucionOperativa[]>([]);
  const [cargando, setCargando] = useState(true);
  const [accionando, setAccionando] = useState<number | null>(null);
  const [error, setError] = useState("");

  const cargar = useCallback(async () => {
    setCargando(true);
    setError("");
    try {
      setEjecuciones(await obtenerEjecucionesOperativas());
    } catch (peticion) {
      setError(mensajeErrorProceso(peticion, "No se pudo cargar el trabajo del área."));
    } finally {
      setCargando(false);
    }
  }, []);

  useEffect(() => {
    let vigente = true;
    obtenerEjecucionesOperativas()
      .then((datos) => {
        if (vigente) setEjecuciones(datos);
      })
      .catch((peticion) => {
        if (vigente) {
          setError(mensajeErrorProceso(peticion, "No se pudo cargar el trabajo del área."));
        }
      })
      .finally(() => {
        if (vigente) setCargando(false);
      });
    return () => {
      vigente = false;
    };
  }, []);

  const iniciar = async (ejecucion: EjecucionOperativa) => {
    if (accionando !== null) return;
    setAccionando(ejecucion.id);
    setError("");
    try {
      await transicionarEjecucion(ejecucion.id, "ejecucion", ejecucion.version);
      await cargar();
    } catch (peticion) {
      const mensaje = mensajeErrorProceso(peticion, "No se pudo iniciar la tarea.");
      await cargar();
      setError(mensaje);
    } finally {
      setAccionando(null);
    }
  };

  const prioridadEstado: Record<string, number> = {
    bloqueada: 0,
    pendiente_control: 1,
    pausada: 2,
    ejecucion: 3,
    preparacion: 4,
    borrador: 5,
  };
  const ordenadas = [...ejecuciones].sort(
    (a, b) => (prioridadEstado[a.estado] ?? 9) - (prioridadEstado[b.estado] ?? 9),
  );
  const bloqueadas = ejecuciones.filter((item) => item.estado === "bloqueada").length;
  const esperandoCalidad = ejecuciones.filter((item) => item.estado === "pendiente_control").length;

  return (
    <section className="mb-8" aria-labelledby="trabajo-area-titulo">
      <div className="mb-4 flex flex-wrap items-end justify-between gap-3">
        <div>
          <p className="text-xs font-bold uppercase tracking-wider text-emerald-700">Prioridad operacional</p>
          <h2 id="trabajo-area-titulo" className="text-xl font-bold text-slate-900">Mi trabajo pendiente</h2>
          <p className="mt-1 text-sm text-slate-600">Solo aparecen procesos que tu área está autorizada a operar.</p>
          <div className="mt-2 flex flex-wrap gap-2 text-xs font-semibold">
            {bloqueadas > 0 && <span className="rounded-full bg-rose-100 px-2.5 py-1 text-rose-800">{bloqueadas} bloqueada{bloqueadas === 1 ? "" : "s"}</span>}
            {esperandoCalidad > 0 && <span className="rounded-full bg-violet-100 px-2.5 py-1 text-violet-800">{esperandoCalidad} esperando Calidad</span>}
          </div>
        </div>
        <button
          type="button"
          onClick={() => void cargar()}
          disabled={cargando}
          className="inline-flex items-center gap-2 rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm font-semibold text-slate-700 hover:border-emerald-500 disabled:opacity-50"
        >
          <RefreshCw className={`h-4 w-4 ${cargando ? "animate-spin" : ""}`} />
          Actualizar
        </button>
      </div>

      {error && <p role="alert" className="mb-3 rounded-xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-800">{error}</p>}

      {cargando ? (
        <div className="rounded-2xl border border-slate-200 bg-white p-6 text-sm text-slate-500">Cargando trabajo del área…</div>
      ) : ejecuciones.length === 0 ? (
        <div className="rounded-2xl border border-emerald-200 bg-emerald-50 p-5">
          <p className="font-semibold text-emerald-900">No hay tareas operativas pendientes para tu área.</p>
          <p className="mt-1 text-sm text-emerald-800">Las ejecuciones cerradas y las asignadas a otras áreas no se muestran aquí.</p>
        </div>
      ) : (
        <div className="grid gap-4 lg:grid-cols-2">
          {ordenadas.map((ejecucion) => {
            const puedeIniciar = ejecucion.acciones_permitidas.includes("ejecucion")
              && !["bloqueada", "pendiente_control"].includes(ejecucion.estado);
            const estaBloqueada = ejecucion.estado === "bloqueada";
            const esperaCalidad = ejecucion.estado === "pendiente_control";
            return (
              <article key={ejecucion.id} className={`rounded-2xl border bg-white p-5 shadow-sm ${estaBloqueada ? "border-rose-300" : esperaCalidad ? "border-violet-300" : "border-slate-200"}`}>
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div>
                    <p className="text-xs font-bold uppercase tracking-wide text-slate-500">{ejecucion.etapa_nombre}</p>
                    <h3 className="mt-1 text-lg font-bold text-slate-900">{ejecucion.codigo}</h3>
                    <p className="mt-1 text-sm text-slate-600">{ejecucion.equipo_nombre ?? "Equipo por asignar"}</p>
                  </div>
                  <StatusBadge estado={ejecucion.estado} etiqueta={ejecucion.estado_etiqueta} />
                </div>

                {estaBloqueada && (
                  <div className="mt-4 rounded-xl border border-rose-200 bg-rose-50 p-3 text-sm text-rose-900">
                    <p className="font-semibold">Requiere resolver el bloqueo antes de continuar.</p>
                    <p className="mt-1">{ejecucion.motivo_bloqueo || "Revisa el último evento de la ejecución para conocer la causa."}</p>
                  </div>
                )}
                {esperaCalidad && (
                  <div className="mt-4 rounded-xl border border-violet-200 bg-violet-50 p-3 text-sm text-violet-900">
                    <p className="font-semibold">Esperando decisión de Calidad.</p>
                    <p className="mt-1">Producción no debe continuar hasta que todas las salidas sean liberadas.</p>
                  </div>
                )}

                <dl className="mt-4 grid gap-3 text-sm sm:grid-cols-2">
                  <div className="rounded-xl bg-slate-50 p-3">
                    <dt className="text-xs font-semibold uppercase text-slate-500">Entrada</dt>
                    <dd className="mt-1 font-medium text-slate-800">{ejecucion.entradas.join(" + ") || "Pendiente de asignación"}</dd>
                  </div>
                  <div className="rounded-xl bg-slate-50 p-3">
                    <dt className="text-xs font-semibold uppercase text-slate-500">Salida</dt>
                    <dd className="mt-1 font-medium text-slate-800">{ejecucion.salidas.join(" + ") || "Aún no registrada"}</dd>
                  </div>
                </dl>

                <div className="mt-4 flex flex-wrap justify-end gap-2">
                  <Link to={destinoDe(ejecucion)} className="inline-flex items-center gap-2 rounded-lg border border-slate-300 px-3 py-2 text-sm font-semibold text-slate-700 hover:border-emerald-500">
                    Abrir tarea <ArrowRight className="h-4 w-4" />
                  </Link>
                  {puedeIniciar && (
                    <button
                      type="button"
                      onClick={() => void iniciar(ejecucion)}
                      disabled={accionando !== null}
                      className="inline-flex items-center gap-2 rounded-lg bg-emerald-700 px-3 py-2 text-sm font-semibold text-white hover:bg-emerald-800 disabled:opacity-50"
                    >
                      <Play className="h-4 w-4" />
                      {accionando === ejecucion.id ? "Validando…" : ejecucion.estado === "pausada" ? "Reanudar" : "Iniciar"}
                    </button>
                  )}
                </div>
              </article>
            );
          })}
        </div>
      )}
    </section>
  );
}
