import { useState } from "react";
import { ArrowRight, FlaskConical, RefreshCw } from "lucide-react";

import {
  obtenerSalidasIntermediasDisponibles,
  prepararContinuacion,
  type SalidaIntermediaDisponible,
} from "../../services/procesos.service";

const numero = new Intl.NumberFormat("es-CL", { maximumFractionDigits: 2 });

export default function SalidasIntermedias() {
  const [salidas, setSalidas] = useState<SalidaIntermediaDisponible[] | null>(null);
  const [cargando, setCargando] = useState(false);
  const [error, setError] = useState("");
  const [preparando, setPreparando] = useState<number | null>(null);
  const [guardando, setGuardando] = useState(false);
  const [etapaId, setEtapaId] = useState(0);
  const [equipoId, setEquipoId] = useState(0);
  const [cantidad, setCantidad] = useState("");
  const [mensaje, setMensaje] = useState("");

  const cargar = async () => {
    if (cargando) return;
    setCargando(true);
    setError("");
    try {
      setSalidas(await obtenerSalidasIntermediasDisponibles());
    } catch {
      setError("No se pudieron consultar los resultados liberados.");
    } finally {
      setCargando(false);
    }
  };

  const abrirPreparacion = (salida: SalidaIntermediaDisponible) => {
    const etapa = salida.etapas_siguientes.find((item) => item.equipos.length > 0);
    if (!etapa) return;
    setPreparando(salida.id);
    setEtapaId(etapa.id);
    setEquipoId(etapa.equipos[0].id);
    setCantidad(salida.cantidad_disponible);
    setError("");
    setMensaje("");
  };

  const seleccionarEtapa = (salida: SalidaIntermediaDisponible, id: number) => {
    const etapa = salida.etapas_siguientes.find((item) => item.id === id);
    setEtapaId(id);
    setEquipoId(etapa?.equipos[0]?.id ?? 0);
  };

  const guardarPreparacion = async (salida: SalidaIntermediaDisponible) => {
    const valor = Number(cantidad);
    if (!etapaId || !equipoId || !Number.isFinite(valor) || valor <= 0) {
      setError("Selecciona etapa, máquina e ingresa una cantidad válida.");
      return;
    }
    setGuardando(true);
    setError("");
    try {
      const ejecucion = await prepararContinuacion(salida.id, {
        etapa: etapaId,
        equipo: equipoId,
        cantidad: valor,
      });
      setMensaje(`${ejecucion.codigo} quedó en preparación.`);
      setPreparando(null);
      await cargar();
    } catch (errorPeticion: unknown) {
      const respuesta = errorPeticion as { response?: { data?: { error?: string } } };
      setError(respuesta.response?.data?.error || "No se pudo preparar la etapa siguiente.");
    } finally {
      setGuardando(false);
    }
  };

  return (
    <section className="mb-8 overflow-hidden rounded-2xl border border-emerald-200 bg-white">
      <div className="flex flex-wrap items-center justify-between gap-3 bg-emerald-50 px-5 py-4">
        <div className="flex items-start gap-3">
          <span className="rounded-xl bg-emerald-700 p-2 text-white">
            <FlaskConical className="h-5 w-5" />
          </span>
          <div>
            <h2 className="font-bold text-slate-900">Resultados intermedios liberados</h2>
            <p className="text-sm text-slate-600">
              Leche o crema aprobada por Calidad y disponible para la etapa siguiente.
            </p>
          </div>
        </div>
        <button
          type="button"
          onClick={() => void cargar()}
          disabled={cargando}
          className="inline-flex items-center gap-2 rounded-xl border border-emerald-700 bg-white px-4 py-2 text-sm font-semibold text-emerald-800 disabled:opacity-60"
        >
          <RefreshCw className={`h-4 w-4 ${cargando ? "animate-spin" : ""}`} />
          {salidas === null ? "Consultar disponibles" : "Actualizar"}
        </button>
      </div>

      {error && <p className="px-5 py-4 text-sm text-rose-700">{error}</p>}
      {mensaje && <p className="px-5 py-3 text-sm font-medium text-emerald-800">{mensaje}</p>}
      {salidas === null && !error && (
        <p className="px-5 py-4 text-sm text-slate-500">
          La consulta se ejecuta solamente al presionar el botón para no cargar el servidor al entrar.
        </p>
      )}
      {salidas?.length === 0 && (
        <p className="px-5 py-4 text-sm text-slate-600">No hay resultados con saldo liberado.</p>
      )}
      {salidas && salidas.length > 0 && (
        <div className="grid gap-3 p-4 lg:grid-cols-2">
          {salidas.map((salida) => (
            <article key={salida.id} className="rounded-xl border border-slate-200 p-4">
              <div className="flex items-start justify-between gap-3">
                <div>
                  <p className="font-semibold text-slate-900">{salida.resultado}</p>
                  <p className="text-xs text-slate-500">
                    {salida.corrida_codigo} · {salida.silo_codigo}
                  </p>
                </div>
                <span className="rounded-full bg-emerald-100 px-3 py-1 text-xs font-bold text-emerald-800">
                  Liberado
                </span>
              </div>
              <div className="mt-3 grid grid-cols-2 gap-2 rounded-xl bg-slate-50 p-3 text-sm">
                <div><span className="text-slate-500">Disponible</span><br /><b>{numero.format(Number(salida.cantidad_disponible))} {salida.unidad}</b></div>
                <div><span className="text-slate-500">Consumido</span><br /><b>{numero.format(Number(salida.cantidad_consumida))} {salida.unidad}</b></div>
              </div>
              <div className="mt-3">
                <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-500">Rutas siguientes</p>
                {salida.etapas_siguientes.length ? (
                  <div className="flex flex-wrap gap-2">
                    {salida.etapas_siguientes.map((etapa) => (
                      <span key={etapa.id} className="inline-flex items-center gap-1 rounded-lg bg-slate-100 px-2.5 py-1.5 text-xs text-slate-700">
                        <ArrowRight className="h-3 w-3" /> {etapa.nombre}
                      </span>
                    ))}
                  </div>
                ) : (
                  <p className="text-sm text-amber-700">No tiene una etapa posterior activa configurada.</p>
                )}
              </div>
              {preparando === salida.id ? (
                <div className="mt-4 space-y-3 rounded-xl border border-emerald-200 bg-emerald-50 p-3">
                  <label className="block text-xs font-semibold text-slate-700">
                    Etapa siguiente
                    <select
                      value={etapaId}
                      onChange={(evento) => seleccionarEtapa(salida, Number(evento.target.value))}
                      className="mt-1 w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm"
                    >
                      {salida.etapas_siguientes.filter((item) => item.equipos.length > 0).map((etapa) => (
                        <option key={etapa.id} value={etapa.id}>{etapa.nombre}</option>
                      ))}
                    </select>
                  </label>
                  <label className="block text-xs font-semibold text-slate-700">
                    Máquina
                    <select
                      value={equipoId}
                      onChange={(evento) => setEquipoId(Number(evento.target.value))}
                      className="mt-1 w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm"
                    >
                      {salida.etapas_siguientes.find((item) => item.id === etapaId)?.equipos.map((equipo) => (
                        <option key={equipo.id} value={equipo.id}>
                          {equipo.nombre}{equipo.ocupado_por ? ` · ocupada por ${equipo.ocupado_por}` : " · disponible"}
                        </option>
                      ))}
                    </select>
                  </label>
                  <label className="block text-xs font-semibold text-slate-700">
                    Cantidad ({salida.unidad})
                    <input
                      type="number"
                      min="0.01"
                      max={salida.cantidad_disponible}
                      step="0.01"
                      value={cantidad}
                      onChange={(evento) => setCantidad(evento.target.value)}
                      className="mt-1 w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm"
                    />
                  </label>
                  <div className="flex justify-end gap-2">
                    <button type="button" onClick={() => setPreparando(null)} className="rounded-lg px-3 py-2 text-sm text-slate-600">Cancelar</button>
                    <button type="button" disabled={guardando} onClick={() => void guardarPreparacion(salida)} className="rounded-lg bg-emerald-700 px-3 py-2 text-sm font-semibold text-white disabled:opacity-60">
                      {guardando ? "Preparando…" : "Confirmar preparación"}
                    </button>
                  </div>
                </div>
              ) : salida.etapas_siguientes.some((item) => item.equipos.length > 0) ? (
                <button type="button" onClick={() => abrirPreparacion(salida)} className="mt-4 inline-flex items-center gap-2 rounded-lg bg-emerald-700 px-3 py-2 text-sm font-semibold text-white">
                  Preparar etapa siguiente <ArrowRight className="h-4 w-4" />
                </button>
              ) : null}
            </article>
          ))}
        </div>
      )}
    </section>
  );
}
