import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { AlertTriangle, Clock3, Gauge, PackageCheck, RefreshCw, Wind } from "lucide-react";

import StatusBadge from "../../components/ui/StatusBadge";
import { EmptyState, ErrorState } from "../../components/ui/PageState";
import { esAdministradorGlobal } from "../../services/access-control";
import { bandejaDeSecado, estadoFisicoSecado, siguienteAccionSecado, type BandejaSecado } from "../../services/secado-proceso";
import { obtenerSecados, type CorridaSecado } from "../../services/secado.service";
import { obtenerSesion } from "../../services/sesion";
import CierreSecado from "./CierreSecado";

const formatoCantidad = new Intl.NumberFormat("es-CL", { maximumFractionDigits: 3 });
const formatoFecha = new Intl.DateTimeFormat("es-CL", { dateStyle: "short", timeStyle: "short" });

const bandejas: { id: BandejaSecado; etiqueta: string; detalle: string }[] = [
  { id: "activas", etiqueta: "Corridas activas", detalle: "Torres reservadas u ocupadas" },
  { id: "calidad", etiqueta: "Esperando Calidad", detalle: "Equipo físicamente disponible" },
  { id: "terminadas", etiqueta: "Terminadas", detalle: "Cierres productivos registrados" },
  { id: "historial", etiqueta: "Historial", detalle: "Corridas canceladas" },
];

/*
  Una corrida cae en **una** bandeja, la que diga `bandejaDeSecado`.

  Antes había un segundo clasificador para «historial» que rehacía la
  decisión con una lista de estados escrita a mano, y no coincidía con el
  primero: una corrida `cerrada` salía a la vez en «Terminadas» y en
  «Historial», así que los contadores de las tarjetas la sumaban dos veces.
  Dos verdades sobre lo mismo, y ninguna forma de saber cuál miraba el
  operador.
*/
function pertenece(corrida: CorridaSecado, bandeja: BandejaSecado) {
  return bandejaDeSecado(corrida.estado, corrida.estado_calidad) === bandeja;
}

export default function Secado() {
  const [corridas, setCorridas] = useState<CorridaSecado[]>([]);
  const [bandeja, setBandeja] = useState<BandejaSecado>("activas");
  const [cargando, setCargando] = useState(true);
  const [error, setError] = useState("");
  const [cerrando, setCerrando] = useState<CorridaSecado | null>(null);
  const [mensaje, setMensaje] = useState("");
  const solicitud = useRef<AbortController | null>(null);
  const secuencia = useRef(0);

  const usuario = obtenerSesion()?.usuario;
  const puedeOperar = Boolean(usuario && (
    usuario.perfil?.area === "secado" || esAdministradorGlobal(usuario)
  ));

  const cargar = useCallback(async () => {
    solicitud.current?.abort();
    const controller = new AbortController();
    solicitud.current = controller;
    const turno = ++secuencia.current;
    setCargando(true);
    setError("");
    try {
      const pagina = await obtenerSecados(controller.signal);
      if (turno === secuencia.current) setCorridas(pagina.results);
    } catch (errorDesconocido) {
      if (!controller.signal.aborted && turno === secuencia.current) {
        console.error("Error cargando Secado:", errorDesconocido);
        setError("No se pudieron cargar las corridas de Secado.");
      }
    } finally {
      if (turno === secuencia.current) setCargando(false);
    }
  }, []);

  useEffect(() => {
    const tarea = window.setTimeout(() => void cargar(), 0);
    return () => {
      window.clearTimeout(tarea);
      solicitud.current?.abort();
    };
  }, [cargar]);

  const conteos = useMemo(() => Object.fromEntries(
    bandejas.map((item) => [item.id, corridas.filter((corrida) => pertenece(corrida, item.id)).length]),
  ) as Record<BandejaSecado, number>, [corridas]);
  const visibles = useMemo(
    () => corridas.filter((corrida) => pertenece(corrida, bandeja)),
    [bandeja, corridas],
  );

  const completarCierre = (actualizada: CorridaSecado) => {
    setCorridas((actuales) => actuales.map((corrida) => corrida.id === actualizada.id ? actualizada : corrida));
    setCerrando(null);
    setMensaje(`Corrida ${actualizada.ejecucion_codigo} cerrada correctamente.`);
    setBandeja("terminadas");
  };

  return (
    <main className="px-5 py-8 sm:px-8 sm:py-10">
      <div className="mx-auto max-w-7xl">
        <header className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <p className="text-xs font-bold uppercase tracking-[0.18em] text-amber-700">Puesto operacional</p>
            <h1 className="mt-1 text-3xl font-bold text-slate-900">Secado</h1>
            <p className="mt-2 max-w-2xl text-sm text-slate-600">Seguimiento y cierre de las corridas que nacen automáticamente al abrir un lote en una torre.</p>
          </div>
          <button type="button" onClick={() => void cargar()} disabled={cargando} className="inline-flex items-center gap-2 rounded-xl border border-slate-300 bg-white px-4 py-2.5 text-sm font-semibold text-slate-700 hover:bg-slate-50 disabled:opacity-50"><RefreshCw className={`h-4 w-4 ${cargando ? "animate-spin" : ""}`} />Actualizar Secado</button>
        </header>

        <section className="mt-7 grid gap-3 sm:grid-cols-2 xl:grid-cols-4" aria-label="Bandejas de Secado">
          {bandejas.map((item) => (
            <button key={item.id} type="button" onClick={() => setBandeja(item.id)} className={`rounded-2xl border p-4 text-left transition ${bandeja === item.id ? "border-amber-500 bg-amber-50 ring-1 ring-amber-300" : "border-slate-200 bg-white hover:border-slate-300"}`}>
              <span className="flex items-center justify-between gap-2"><strong className="text-sm text-slate-900">{item.etiqueta}</strong><span className="rounded-full bg-white px-2.5 py-1 text-sm font-bold text-slate-800 ring-1 ring-slate-200">{cargando ? "…" : conteos[item.id]}</span></span>
              <span className="mt-2 block text-xs text-slate-600">{item.detalle}</span>
            </button>
          ))}
        </section>

        {mensaje && <p className="mt-5 rounded-xl bg-emerald-50 px-4 py-3 text-sm text-emerald-800" role="status">{mensaje}</p>}
        {error && <div className="mt-5"><ErrorState mensaje={error} /></div>}

        <section className="mt-6">
          <div className="mb-4">
            <h2 className="text-xl font-bold text-slate-900">{bandejas.find((item) => item.id === bandeja)?.etiqueta}</h2>
            <p className="text-sm text-slate-600">Una sola lectura alimenta estas bandejas; cambiar de vista no vuelve a consultar el servidor.</p>
          </div>

          {cargando ? <EsqueletoCorridas /> : visibles.length === 0 ? (
            <EmptyState
              titulo={bandeja === "calidad" ? "Sin corridas informadas como pendientes de Calidad" : "No hay corridas en esta bandeja"}
              detalle={bandeja === "calidad" ? "Las corridas aparecerán aquí cuando el proceso informe el estado pendiente de control." : "Las nuevas corridas aparecerán cuando el flujo productivo alcance esta etapa."}
            />
          ) : (
            <div className="grid gap-4 lg:grid-cols-2">
              {visibles.map((corrida) => (
                <CorridaCard key={corrida.id} corrida={corrida} puedeOperar={puedeOperar} alCerrar={() => setCerrando(corrida)} />
              ))}
            </div>
          )}
        </section>
      </div>

      {cerrando && <CierreSecado corrida={cerrando} alCerrar={() => setCerrando(null)} alCompletarse={completarCierre} />}
    </main>
  );
}

function CorridaCard({ corrida, puedeOperar, alCerrar }: { corrida: CorridaSecado; puedeOperar: boolean; alCerrar: () => void }) {
  const puedeCerrar = puedeOperar && ["ejecucion", "pausada"].includes(corrida.estado);
  const alerta = corrida.estado === "bloqueada"
    ? "La corrida está bloqueada y mantiene ocupada la torre."
    : corrida.estado === "pausada"
      ? "La corrida está pausada y mantiene ocupada la torre."
      : null;

  return (
    <article className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="text-xs font-bold uppercase tracking-wider text-slate-500">{corrida.orden_codigo || "Sin orden asociada"}</p>
          <h3 className="mt-1 text-lg font-bold text-slate-900">{corrida.lote_codigo}</h3>
          <p className="text-sm text-slate-600">{corrida.producto_nombre}</p>
        </div>
        <StatusBadge estado={corrida.estado} etiqueta={corrida.estado_etiqueta} />
      </div>

      <dl className="mt-4 grid gap-3 text-sm sm:grid-cols-2">
        <Dato icono={<Wind className="h-4 w-4" />} etiqueta="Torre / equipo" valor={corrida.equipo_nombre || "No informado"} />
        <Dato icono={<Gauge className="h-4 w-4" />} etiqueta="Estado físico" valor={estadoFisicoSecado(corrida.estado)} />
        <Dato icono={<PackageCheck className="h-4 w-4" />} etiqueta="Alimentación" valor={corrida.kg_alimentacion ? `${formatoCantidad.format(Number(corrida.kg_alimentacion))} kg` : "Pendiente de cierre"} />
        <Dato icono={<Clock3 className="h-4 w-4" />} etiqueta="Hora" valor={corrida.finalizada_en ? `Finalizada ${formatoFecha.format(new Date(corrida.finalizada_en))}` : corrida.iniciada_en ? `Iniciada ${formatoFecha.format(new Date(corrida.iniciada_en))}` : "Inicio pendiente"} />
      </dl>

      {alerta && <p className="mt-4 flex items-start gap-2 rounded-xl bg-red-50 px-3 py-2 text-xs font-medium text-red-800"><AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />{alerta}</p>}

      <div className="mt-4 rounded-xl bg-slate-50 px-3 py-3">
        <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">Siguiente acción</p>
        <p className="mt-1 text-sm font-medium text-slate-800">{siguienteAccionSecado(corrida.estado, corrida.estado_calidad)}</p>
      </div>

      {puedeCerrar && <button type="button" onClick={alCerrar} className="mt-4 w-full rounded-xl bg-amber-700 px-4 py-2.5 text-sm font-semibold text-white hover:bg-amber-800">Registrar balance y cerrar corrida</button>}
      {!puedeOperar && ["ejecucion", "pausada"].includes(corrida.estado) && <p className="mt-4 rounded-xl bg-slate-100 px-3 py-2 text-xs text-slate-600">Vista de seguimiento. Tu área no ejecuta acciones de Secado.</p>}
    </article>
  );
}

function Dato({ icono, etiqueta, valor }: { icono: React.ReactNode; etiqueta: string; valor: string }) {
  return <div className="rounded-xl border border-slate-100 p-3"><dt className="flex items-center gap-2 text-xs text-slate-500">{icono}{etiqueta}</dt><dd className="mt-1 font-semibold text-slate-800">{valor}</dd></div>;
}

function EsqueletoCorridas() {
  return <div className="grid gap-4 lg:grid-cols-2" aria-live="polite" aria-label="Cargando corridas de Secado">{[1, 2].map((item) => <div key={item} className="h-64 animate-pulse rounded-2xl bg-slate-100" />)}</div>;
}
