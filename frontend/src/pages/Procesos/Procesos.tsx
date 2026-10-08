import { useEffect, useState } from "react";
import { Link, Navigate, useSearchParams } from "react-router-dom";
import { ArrowRight, GitBranch, Plus } from "lucide-react";

import { EmptyState, ErrorState, PageLoader } from "../../components/ui/PageState";
import EstadoEquipo from "../../components/EstadoEquipo/EstadoEquipo";
import StatusBadge from "../../components/ui/StatusBadge";
import { obtenerEjecucionesOperativas, obtenerRutasProducto, transicionarEjecucion, type EjecucionOperativa, type RutaProducto } from "../../services/procesos.service";
import { esConflictoVersion, esErrorDeEquipo, mensajeErrorProceso } from "../../services/errores-proceso";
import { rutaDeEtapa, textoIniciarEnPuesto } from "../../services/planta-ahora";
import { puedeEscribir } from "../../services/sesion";
import DiagnosticoRutas from "./DiagnosticoRutas";
import NuevaRutaProducto from "./NuevaRutaProducto";
import ReworkProduccion from "./ReworkProduccion";
import TrazabilidadProceso from "./TrazabilidadProceso";

export default function Procesos() {
  const puedeOperar = puedeEscribir("produccion");
  const puedeConfigurar = puedeEscribir("maestros");
  const [parametros] = useSearchParams();
  const [ejecuciones, setEjecuciones] = useState<EjecucionOperativa[]>([]);
  const [rutas, setRutas] = useState<RutaProducto[]>([]);
  const [rutasCargadas, setRutasCargadas] = useState(false);
  const [nuevaRuta, setNuevaRuta] = useState(false);
  const [cargando, setCargando] = useState(true);
  const [error, setError] = useState("");
  const [accionando, setAccionando] = useState<number | null>(null);
  const seccionSolicitada = parametros.get("seccion");

  useEffect(() => {
    if (!seccionSolicitada) return;
    const temporizador = window.setTimeout(() => {
      document.getElementById(`proceso-${seccionSolicitada}`)?.scrollIntoView({ behavior: "smooth", block: "start" });
    }, 0);
    return () => window.clearTimeout(temporizador);
  }, [seccionSolicitada]);

  useEffect(() => {
    obtenerEjecucionesOperativas()
      .then((operativas) => {
        setEjecuciones(operativas);
      })
      .catch(() => setError("No se pudieron cargar las ejecuciones industriales."))
      .finally(() => setCargando(false));
  }, []);

  const refrescarEjecuciones = async () => {
    try {
      setEjecuciones(await obtenerEjecucionesOperativas());
      return true;
    } catch {
      return false;
    }
  };

  const moverEjecucion = async (ejecucion: EjecucionOperativa) => {
    if (accionando !== null) return;
    setAccionando(ejecucion.id);
    setError("");
    try {
      await transicionarEjecucion(ejecucion.id, "ejecucion", ejecucion.version);
      if (!await refrescarEjecuciones()) {
        setError("La operación se guardó, pero no se pudo actualizar la disponibilidad. Usa actualizar antes de otra acción.");
      }
    } catch (errorPeticion: unknown) {
      setError(mensajeErrorProceso(errorPeticion, "No se pudo iniciar la ejecución."));
      if (esErrorDeEquipo(errorPeticion) || esConflictoVersion(errorPeticion)) {
        await refrescarEjecuciones();
      }
    } finally {
      setAccionando(null);
    }
  };

  const cargarRutas = async () => {
    try {
      const pagina = await obtenerRutasProducto();
      setRutas(pagina.results);
      setRutasCargadas(true);
    } catch { setError("No se pudieron cargar las rutas de proceso."); }
  };

  // La evaporación/precondensado se opera en su propio puesto; un enlace
  // guardado o una notificación ya emitida con `?seccion=` sigue aterrizando
  // ahí. Va después de todos los hooks del componente, no al principio de
  // la función: un `return` anterior a ellos los dejaría sin llamar en este
  // render, que es justo lo que evita la regla de los hooks.
  if (seccionSolicitada === "condensacion" || seccionSolicitada === "evaporacion") {
    return <Navigate to="/produccion/evaporacion" replace />;
  }
  // Descremado también tiene puesto propio. La acción «Descremar» del silo
  // llegaba aquí con `?accion=descremar&silo=`: un enlace guardado sigue
  // aterrizando en el puesto con el silo elegido.
  if (seccionSolicitada === "descremacion") {
    return <Navigate to="/produccion/descremado" replace />;
  }
  if (parametros.get("accion") === "descremar") {
    const silo = parametros.get("silo");
    return <Navigate to={silo ? `/produccion/descremado?silo=${encodeURIComponent(silo)}` : "/produccion/descremado"} replace />;
  }
  // Mantequilla también tiene puesto propio: un enlace guardado o una
  // notificación con `?seccion=mantequilla` aterriza en el puesto.
  if (seccionSolicitada === "mantequilla") {
    return <Navigate to="/produccion/mantequilla" replace />;
  }

  return (
    <main className="px-6 py-8 lg:px-10">
      <div className="mx-auto max-w-7xl space-y-8">
        <header>
          <p className="text-sm font-semibold uppercase tracking-wider text-green-700">Procesamiento</p>
          <h1 className="mt-2 text-3xl font-bold text-slate-900">Ejecuciones y trazabilidad</h1>
          <p className="mt-2 max-w-3xl text-slate-600">Entradas, salidas, coproductos, reprocesos y mermas vinculados a los lotes reales.</p>
        </header>

        {error && <ErrorState mensaje={error} />}

        {puedeConfigurar && nuevaRuta && <NuevaRutaProducto onCerrar={() => setNuevaRuta(false)} onCreada={(ruta) => { setRutasCargadas(true); setRutas((actuales) => [...actuales, ruta]); setNuevaRuta(false); }} />}

        <section className="rounded-2xl border border-slate-200 bg-white p-6">
          <div className="flex flex-wrap items-center justify-between gap-3"><div className="flex items-center gap-3"><GitBranch className="h-5 w-5 text-green-700" /><h2 className="text-lg font-semibold">Rutas configuradas por producto</h2></div>{puedeConfigurar && <button type="button" onClick={() => setNuevaRuta(true)} className="inline-flex items-center gap-2 rounded-xl bg-emerald-700 px-4 py-2 text-sm font-semibold text-white"><Plus className="h-4 w-4" />Nueva ruta</button>}</div>
          <p className="mt-2 text-sm text-slate-600">La secuencia proviene del maestro de procesos; no está codificada en la interfaz.</p>
          <DiagnosticoRutas />
          {!rutasCargadas ? <button type="button" onClick={cargarRutas} className="mt-5 rounded-xl border border-emerald-700 px-4 py-2 text-sm font-semibold text-emerald-700">Cargar rutas</button> : rutas.length === 0 ? <p className="mt-5 text-sm text-slate-600">No hay rutas activas configuradas.</p> : <div className="mt-5 grid gap-4 lg:grid-cols-2">{rutas.map((ruta) => <article key={ruta.id} className="rounded-xl border border-slate-200 p-4"><div className="flex items-start justify-between gap-3"><div><p className="font-semibold text-slate-900">{ruta.producto_nombre}</p><p className="mt-1 text-sm text-green-700">{ruta.proceso_nombre}{ruta.destino ? ` → ${ruta.destino}` : ""}</p>{ruta.insumo_origen_nombre && <p className="mt-1 text-xs font-medium text-amber-700">Origen externo: {ruta.insumo_origen_nombre}</p>}</div><span className="rounded-full bg-slate-100 px-2.5 py-1 text-xs font-medium text-slate-600">Prioridad {ruta.prioridad}</span></div><div className="mt-3 flex flex-wrap items-center gap-2 text-xs text-slate-600">{ruta.etapas.sort((a, b) => a.orden - b.orden).map((etapa, indice) => <span key={etapa.id} className="inline-flex items-center gap-2"><span className="rounded-lg bg-slate-50 px-2 py-1">{etapa.nombre}</span>{indice < ruta.etapas.length - 1 && <ArrowRight className="h-3 w-3" />}</span>)}</div></article>)}</div>}
        </section>

        <ReworkProduccion
          ejecuciones={ejecuciones}
          puedeOperar={puedeOperar}
          alConsumir={async () => setEjecuciones(await obtenerEjecucionesOperativas())}
        />

        <TrazabilidadProceso />

        <section>
          <h2 className="mb-1 text-xl font-semibold text-slate-800">Ejecuciones operativas</h2>
          <p className="mb-4 text-sm text-slate-600">Solo pendientes y en curso. El inicio valida nuevamente máquina, ocupación y aseo.</p>
          {cargando ? <PageLoader /> : ejecuciones.length === 0 ? <EmptyState titulo="Sin trabajo operativo pendiente" detalle="Las ejecuciones cerradas no se cargan en esta bandeja." /> : <div className="overflow-x-auto rounded-2xl border border-slate-200 bg-white"><table className="w-full text-left text-sm"><thead className="bg-slate-50 text-slate-600"><tr><th className="px-5 py-3">ID del proceso</th><th className="px-5 py-3">Etapa</th><th className="px-5 py-3">Equipo</th><th className="px-5 py-3">Estado</th><th className="px-5 py-3">Entrada</th><th className="px-5 py-3">Salida</th><th className="px-5 py-3">Acción</th></tr></thead><tbody>{ejecuciones.map((item) => <tr key={item.id} className="border-t border-slate-100"><td className="px-5 py-4 font-semibold text-slate-800">{item.codigo}</td><td className="px-5 py-4">{item.etapa_nombre}</td><td className="px-5 py-4"><span className="block">{item.equipo_nombre ?? "—"}</span>{item.equipo_nombre && <span className="mt-1.5 block"><EstadoEquipo estado={item.estado} ejecucion={item.codigo} /></span>}</td><td className="px-5 py-4"><StatusBadge estado={item.estado} etiqueta={item.estado_etiqueta} /></td><td className="px-5 py-4 text-xs">{item.entradas.join(" + ") || "—"}</td><td className="px-5 py-4 text-xs">{item.salidas.join(" + ") || "—"}</td><td className="px-5 py-4">{item.acciones_permitidas.includes("ejecucion") ? <button type="button" disabled={accionando !== null} onClick={() => void moverEjecucion(item)} className="rounded-lg bg-emerald-700 px-3 py-2 text-xs font-semibold text-white disabled:opacity-50">{accionando === item.id ? "Validando…" : item.estado === "pausada" ? "Reanudar" : "Iniciar"}</button> : textoIniciarEnPuesto(item.etapa_tipo, item.estado) ? <Link to={rutaDeEtapa(item.etapa_tipo)} className="text-xs font-semibold text-amber-800 underline">{textoIniciarEnPuesto(item.etapa_tipo, item.estado)}</Link> : <span className="text-xs text-slate-500">Sin acción directa</span>}</td></tr>)}</tbody></table></div>}
        </section>
      </div>
    </main>
  );
}
