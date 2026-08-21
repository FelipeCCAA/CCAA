import { useEffect, useState } from "react";
import { ArrowRight, Beaker, Factory, GitBranch, Search, Truck } from "lucide-react";

import { EmptyState, ErrorState, PageLoader } from "../../components/ui/PageState";
import StatusBadge from "../../components/ui/StatusBadge";
import { obtenerCondensaciones, obtenerEjecuciones, obtenerGenealogia, obtenerMantequillas, obtenerRutasProducto, type CorridaCondensacion, type CorridaMantequilla, type EjecucionProceso, type Genealogia, type RutaProducto } from "../../services/procesos.service";
import ArbolGenealogia from "./ArbolGenealogia";

export default function Procesos() {
  const [ejecuciones, setEjecuciones] = useState<EjecucionProceso[]>([]);
  const [rutas, setRutas] = useState<RutaProducto[]>([]);
  const [condensaciones, setCondensaciones] = useState<CorridaCondensacion[]>([]);
  const [mantequillas, setMantequillas] = useState<CorridaMantequilla[]>([]);
  const [cargando, setCargando] = useState(true);
  const [error, setError] = useState("");
  const [lote, setLote] = useState("");
  const [direccion, setDireccion] = useState<"atras" | "adelante">("atras");
  const [genealogia, setGenealogia] = useState<Genealogia | null>(null);

  useEffect(() => {
    const controlador = new AbortController();
    Promise.all([obtenerEjecuciones(), obtenerRutasProducto(), obtenerCondensaciones(), obtenerMantequillas()])
      .then(([pagina, rutasPagina, condensacionesPagina, mantequillasPagina]) => {
        setEjecuciones(pagina.results);
        setRutas(rutasPagina.results);
        setCondensaciones(condensacionesPagina.results);
        setMantequillas(mantequillasPagina.results);
      })
      .catch(() => setError("No se pudieron cargar las ejecuciones industriales."))
      .finally(() => setCargando(false));
    return () => controlador.abort();
  }, []);

  const buscar = async (evento: React.FormEvent) => {
    evento.preventDefault();
    if (!lote.trim()) {
      setError("Escribe el código del lote.");
      return;
    }

    setError("");

    try {
      setGenealogia(await obtenerGenealogia(lote, direccion));
    } catch {
      setGenealogia(null);
      setError(`No existe el lote «${lote.trim()}» o no se pudo reconstruir su genealogía.`);
    }
  };

  return (
    <main className="px-6 py-8 lg:px-10">
      <div className="mx-auto max-w-7xl space-y-8">
        <header>
          <p className="text-sm font-semibold uppercase tracking-wider text-green-700">Procesamiento</p>
          <h1 className="mt-2 text-3xl font-bold text-slate-900">Ejecuciones y trazabilidad</h1>
          <p className="mt-2 max-w-3xl text-slate-600">Entradas, salidas, coproductos, reprocesos y mermas vinculados a los lotes reales.</p>
        </header>

        {error && <ErrorState mensaje={error} />}

        <section className="rounded-2xl border border-slate-200 bg-white p-6">
          <div className="flex items-center gap-3"><GitBranch className="h-5 w-5 text-green-700" /><h2 className="text-lg font-semibold">Rutas configuradas por producto</h2></div>
          <p className="mt-2 text-sm text-slate-600">La secuencia proviene del maestro de procesos; no está codificada en la interfaz.</p>
          {rutas.length === 0 ? <p className="mt-5 text-sm text-slate-600">No hay rutas activas configuradas.</p> : <div className="mt-5 grid gap-4 lg:grid-cols-2">{rutas.map((ruta) => <article key={ruta.id} className="rounded-xl border border-slate-200 p-4"><div className="flex items-start justify-between gap-3"><div><p className="font-semibold text-slate-900">{ruta.producto_nombre}</p><p className="mt-1 text-sm text-green-700">{ruta.proceso_nombre}{ruta.destino ? ` → ${ruta.destino}` : ""}</p></div><span className="rounded-full bg-slate-100 px-2.5 py-1 text-xs font-medium text-slate-600">Prioridad {ruta.prioridad}</span></div><div className="mt-3 flex flex-wrap items-center gap-2 text-xs text-slate-600">{ruta.etapas.sort((a, b) => a.orden - b.orden).map((etapa, indice) => <span key={etapa.id} className="inline-flex items-center gap-2"><span className="rounded-lg bg-slate-50 px-2 py-1">{etapa.nombre}</span>{indice < ruta.etapas.length - 1 && <ArrowRight className="h-3 w-3" />}</span>)}</div></article>)}</div>}
        </section>

        <section>
          <h2 className="mb-4 text-xl font-semibold text-slate-800">Condensación y precondensado</h2>
          {condensaciones.length === 0 ? <EmptyState titulo="Sin corridas de condensación" detalle="Las corridas aparecerán aquí vinculadas a su orden, lote, evaporador y silos." /> : <div className="overflow-x-auto rounded-2xl border border-slate-200 bg-white"><table className="w-full text-left text-sm"><thead className="bg-slate-50 text-slate-600"><tr><th className="px-5 py-3">Orden / lote</th><th className="px-5 py-3">Evaporador</th><th className="px-5 py-3">Flujo físico</th><th className="px-5 py-3">Resultado</th><th className="px-5 py-3">Estado</th></tr></thead><tbody>{condensaciones.map((corrida) => <tr key={corrida.id} className="border-t border-slate-100"><td className="px-5 py-4 font-semibold text-slate-800">{corrida.orden_codigo}<span className="block text-xs font-normal text-slate-600">{corrida.lote_codigo} · {corrida.ejecucion_codigo}</span></td><td className="px-5 py-4">{corrida.equipo_nombre || "—"}</td><td className="px-5 py-4">{corrida.silo_origen_codigo} · {Number(corrida.litros_entrada).toLocaleString("es-CL")} L <ArrowRight className="mx-1 inline h-3.5 w-3.5" /> {corrida.silo_destino_codigo}</td><td className="px-5 py-4">{corrida.litros_precondensado ? `${Number(corrida.litros_precondensado).toLocaleString("es-CL")} L` : "Pendiente"}<span className="block text-xs text-slate-600">{corrida.solidos_salida ? `${corrida.solidos_salida}% sólidos` : "sin control final"}</span></td><td className="px-5 py-4"><StatusBadge estado={corrida.estado} etiqueta={corrida.estado_etiqueta} /></td></tr>)}</tbody></table></div>}
        </section>

        <section>
          <h2 className="mb-4 text-xl font-semibold text-slate-800">Línea de mantequilla</h2>
          {mantequillas.length === 0 ? <EmptyState titulo="Sin corridas de mantequilla" detalle="Las corridas conservarán la relación crema → mantequilla, suero y merma." /> : <div className="grid gap-4 lg:grid-cols-2">{mantequillas.map((corrida) => <article key={corrida.id} className="rounded-2xl border border-slate-200 bg-white p-5"><div className="flex items-start justify-between gap-3"><div><p className="font-semibold text-slate-900">{corrida.orden_codigo} · {corrida.mantequilla_codigo}</p><p className="mt-1 text-xs text-slate-600">{corrida.equipo_nombre || "Sin línea"} · {corrida.ejecucion_codigo}</p></div><StatusBadge estado={corrida.estado} etiqueta={corrida.estado_etiqueta} /></div><div className="mt-4 grid grid-cols-2 gap-3 text-sm"><p className="rounded-xl bg-amber-50 p-3 text-amber-900"><span className="block text-xs text-amber-700">Crema utilizada</span>{Number(corrida.kg_crema).toLocaleString("es-CL")} kg · {corrida.crema_codigo}</p><p className="rounded-xl bg-green-50 p-3 text-green-900"><span className="block text-xs text-green-700">Mantequilla</span>{corrida.kg_mantequilla ? `${Number(corrida.kg_mantequilla).toLocaleString("es-CL")} kg` : "Pendiente"}</p><p className="rounded-xl bg-slate-50 p-3 text-slate-700"><span className="block text-xs text-slate-600">Suero</span>{Number(corrida.kg_suero).toLocaleString("es-CL")} kg</p><p className="rounded-xl bg-slate-50 p-3 text-slate-700"><span className="block text-xs text-slate-600">Merma</span>{Number(corrida.kg_merma).toLocaleString("es-CL")} kg</p></div></article>)}</div>}
        </section>

        <section className="rounded-2xl border border-slate-200 bg-white p-6">
          <div className="flex items-center gap-3"><GitBranch className="h-5 w-5 text-green-700" /><h2 className="text-lg font-semibold">Consultar genealogía</h2></div>
          <form onSubmit={buscar} className="mt-5 flex flex-col gap-3 sm:flex-row">
            <input value={lote} onChange={(e) => setLote(e.target.value)} placeholder="Código del lote (p. ej. CCAA6212010102010201-01)" className="flex-1 rounded-xl border border-slate-300 px-4 py-2.5" />
            <select value={direccion} onChange={(e) => setDireccion(e.target.value as "atras" | "adelante")} className="rounded-xl border border-slate-300 bg-white px-4 py-2.5"><option value="atras">Hacia atrás</option><option value="adelante">Hacia adelante</option></select>
            <button className="inline-flex items-center justify-center gap-2 rounded-xl bg-green-700 px-5 py-2.5 font-semibold text-white"><Search className="h-4 w-4" />Buscar</button>
          </form>
          {genealogia?.flujo && (
            <div className="mt-6">
              <h3 className="text-sm font-semibold uppercase tracking-wide text-slate-600">
                Línea completa del lote
              </h3>
              <div className="mt-3 grid items-stretch gap-3 lg:grid-cols-[1fr_auto_1fr_auto_1fr]">
                <div className="rounded-xl border border-slate-200 p-4">
                  <div className="flex items-center gap-2 font-semibold text-slate-800">
                    <Truck className="h-4 w-4 text-green-700" /> Recepción
                  </div>
                  <p className="mt-2 text-sm text-slate-600">
                    {genealogia.flujo.recepciones.length} recepción(es) candidata(s)
                  </p>
                  <ul className="mt-2 space-y-1 text-xs text-slate-600">
                    {genealogia.flujo.recepciones.slice(0, 4).map((item) => (
                      <li key={`${item.id}-${item.silo_codigo}`}>
                        {item.fecha} · guía {item.guia || "—"} · {item.silo_codigo}
                      </li>
                    ))}
                  </ul>
                  <p className="mt-2 text-xs text-slate-600">{genealogia.flujo.nota_recepciones}</p>
                </div>
                <ArrowRight className="m-auto hidden h-5 w-5 text-slate-300 lg:block" />
                <div className="rounded-xl border border-green-200 bg-green-50/50 p-4">
                  <div className="flex items-center gap-2 font-semibold text-slate-800">
                    <Beaker className="h-4 w-4 text-green-700" /> Estandarización
                  </div>
                  <p className="mt-2 text-sm font-medium">{genealogia.flujo.estandarizacion.vale_codigo}</p>
                  <p className="mt-1 text-xs text-slate-600">
                    {genealogia.flujo.estandarizacion.silos_origen.map((item) => item.codigo).join(" + ")}
                    {" → "}{genealogia.flujo.estandarizacion.silo_destino}
                  </p>
                  <p className="mt-2 text-xs text-slate-600">
                    Proceso {genealogia.flujo.estandarizacion.ejecucion_codigo || "sin ID"}
                  </p>
                </div>
                <ArrowRight className="m-auto hidden h-5 w-5 text-slate-300 lg:block" />
                <div className="rounded-xl border border-slate-200 p-4">
                  <div className="flex items-center gap-2 font-semibold text-slate-800">
                    <Factory className="h-4 w-4 text-green-700" /> Producción
                  </div>
                  <p className="mt-2 text-sm font-medium">{genealogia.flujo.produccion.lote_codigo}</p>
                  <p className="mt-1 text-xs text-slate-600">
                    {genealogia.flujo.produccion.producto} · {genealogia.flujo.produccion.linea || "sin línea"} · {genealogia.flujo.produccion.equipo || "sin máquina"}
                  </p>
                  <p className="mt-2 text-xs text-slate-600">
                    Proceso {genealogia.flujo.produccion.ejecucion_codigo || "sin ID"}
                  </p>
                </div>
              </div>
              <div className="mt-3 grid gap-3 lg:grid-cols-2">
                <div className="rounded-xl border border-sky-200 bg-sky-50/60 p-4">
                  <p className="text-sm font-semibold text-sky-900">Calidad · {genealogia.flujo.calidad.estado}</p>
                  <p className="mt-1 text-xs text-sky-700">{genealogia.flujo.calidad.autorizada_por ? `Firmado por ${genealogia.flujo.calidad.autorizada_por}` : "Sin firma de liberación"}</p>
                </div>
                <div className="rounded-xl border border-amber-200 bg-amber-50/60 p-4">
                  <p className="text-sm font-semibold text-amber-900">Envase, inventario y despacho</p>
                  {genealogia.flujo.pallets.length === 0 ? <p className="mt-1 text-xs text-amber-700">Sin pallets registrados.</p> : <ul className="mt-2 space-y-1 text-xs text-amber-800">{genealogia.flujo.pallets.map((p) => <li key={p.id}>{p.codigo} · {p.kg_neto} kg · {p.ubicacion ? `ubicación ${p.ubicacion}` : p.estado}{p.cliente ? ` · cliente ${p.cliente} (${p.despacho})` : ""}</li>)}</ul>}
                </div>
              </div>
            </div>
          )}
          {genealogia && <div className="mt-5"><ArbolGenealogia genealogia={genealogia} direccion={direccion} /></div>}
        </section>

        <section>
          <h2 className="mb-4 text-xl font-semibold text-slate-800">Ejecuciones recientes</h2>
          {cargando ? <PageLoader /> : ejecuciones.length === 0 ? <EmptyState titulo="Aún no hay ejecuciones" detalle="Crea procesos y etapas desde Administración para comenzar la trazabilidad." /> : <div className="overflow-x-auto rounded-2xl border border-slate-200 bg-white"><table className="w-full text-left text-sm"><thead className="bg-slate-50 text-slate-600"><tr><th className="px-5 py-3">ID del proceso</th><th className="px-5 py-3">Etapa / documento</th><th className="px-5 py-3">Equipo</th><th className="px-5 py-3">Estado</th><th className="px-5 py-3">Entrada</th><th className="px-5 py-3">Salida</th></tr></thead><tbody>{ejecuciones.map((item) => <tr key={item.id} className="border-t border-slate-100"><td className="px-5 py-4 font-semibold text-slate-800">{item.codigo}</td><td className="px-5 py-4"><span>{item.etapa_nombre}</span><span className="block text-xs text-slate-600">{item.vale_codigo || item.lote_codigo || "—"}</span></td><td className="px-5 py-4">{item.equipo_nombre ?? "—"}</td><td className="px-5 py-4"><StatusBadge estado={item.estado} etiqueta={item.estado_etiqueta} /></td><td className="px-5 py-4 text-xs">{item.entradas.map((entrada) => entrada.lote_codigo || entrada.silo_codigo).filter(Boolean).join(" + ") || "—"}</td><td className="px-5 py-4 text-xs">{item.salidas.map((salida) => salida.lote_codigo || salida.silo_codigo).filter(Boolean).join(" + ") || "—"}</td></tr>)}</tbody></table></div>}
        </section>
      </div>
    </main>
  );
}
