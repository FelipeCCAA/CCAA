import { useEffect, useState } from "react";
import { ArrowRight, Beaker, Factory, GitBranch, Search, Truck } from "lucide-react";

import { EmptyState, ErrorState, PageLoader } from "../../components/ui/PageState";
import StatusBadge from "../../components/ui/StatusBadge";
import { obtenerEjecuciones, obtenerGenealogia, type EjecucionProceso, type Genealogia } from "../../services/procesos.service";
import ArbolGenealogia from "./ArbolGenealogia";

export default function Procesos() {
  const [ejecuciones, setEjecuciones] = useState<EjecucionProceso[]>([]);
  const [cargando, setCargando] = useState(true);
  const [error, setError] = useState("");
  const [lote, setLote] = useState("");
  const [direccion, setDireccion] = useState<"atras" | "adelante">("atras");
  const [genealogia, setGenealogia] = useState<Genealogia | null>(null);

  useEffect(() => {
    const controlador = new AbortController();
    obtenerEjecuciones()
      .then((pagina) => setEjecuciones(pagina.results))
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
          <p className="mt-2 max-w-3xl text-slate-500">Entradas, salidas, coproductos, reprocesos y mermas vinculados a los lotes reales.</p>
        </header>

        {error && <ErrorState mensaje={error} />}

        <section className="rounded-2xl border border-slate-200 bg-white p-6">
          <div className="flex items-center gap-3"><GitBranch className="h-5 w-5 text-green-700" /><h2 className="text-lg font-semibold">Consultar genealogía</h2></div>
          <form onSubmit={buscar} className="mt-5 flex flex-col gap-3 sm:flex-row">
            <input value={lote} onChange={(e) => setLote(e.target.value)} placeholder="Código del lote (p. ej. CCAA6212010102010201-01)" className="flex-1 rounded-xl border border-slate-300 px-4 py-2.5" />
            <select value={direccion} onChange={(e) => setDireccion(e.target.value as "atras" | "adelante")} className="rounded-xl border border-slate-300 bg-white px-4 py-2.5"><option value="atras">Hacia atrás</option><option value="adelante">Hacia adelante</option></select>
            <button className="inline-flex items-center justify-center gap-2 rounded-xl bg-green-700 px-5 py-2.5 font-semibold text-white"><Search className="h-4 w-4" />Buscar</button>
          </form>
          {genealogia?.flujo && (
            <div className="mt-6">
              <h3 className="text-sm font-semibold uppercase tracking-wide text-slate-500">
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
                  <ul className="mt-2 space-y-1 text-xs text-slate-500">
                    {genealogia.flujo.recepciones.slice(0, 4).map((item) => (
                      <li key={`${item.id}-${item.silo_codigo}`}>
                        {item.fecha} · guía {item.guia || "—"} · {item.silo_codigo}
                      </li>
                    ))}
                  </ul>
                  <p className="mt-2 text-xs text-slate-400">{genealogia.flujo.nota_recepciones}</p>
                </div>
                <ArrowRight className="m-auto hidden h-5 w-5 text-slate-300 lg:block" />
                <div className="rounded-xl border border-green-200 bg-green-50/50 p-4">
                  <div className="flex items-center gap-2 font-semibold text-slate-800">
                    <Beaker className="h-4 w-4 text-green-700" /> Estandarización
                  </div>
                  <p className="mt-2 text-sm font-medium">{genealogia.flujo.estandarizacion.vale_codigo}</p>
                  <p className="mt-1 text-xs text-slate-500">
                    {genealogia.flujo.estandarizacion.silos_origen.map((item) => item.codigo).join(" + ")}
                    {" → "}{genealogia.flujo.estandarizacion.silo_destino}
                  </p>
                  <p className="mt-2 text-xs text-slate-400">
                    Proceso {genealogia.flujo.estandarizacion.ejecucion_codigo || "sin ID"}
                  </p>
                </div>
                <ArrowRight className="m-auto hidden h-5 w-5 text-slate-300 lg:block" />
                <div className="rounded-xl border border-slate-200 p-4">
                  <div className="flex items-center gap-2 font-semibold text-slate-800">
                    <Factory className="h-4 w-4 text-green-700" /> Producción
                  </div>
                  <p className="mt-2 text-sm font-medium">{genealogia.flujo.produccion.lote_codigo}</p>
                  <p className="mt-1 text-xs text-slate-500">
                    {genealogia.flujo.produccion.producto} · {genealogia.flujo.produccion.linea || "sin línea"} · {genealogia.flujo.produccion.equipo || "sin máquina"}
                  </p>
                  <p className="mt-2 text-xs text-slate-400">
                    Proceso {genealogia.flujo.produccion.ejecucion_codigo || "sin ID"}
                  </p>
                </div>
              </div>
            </div>
          )}
          {genealogia && <div className="mt-5"><ArbolGenealogia genealogia={genealogia} direccion={direccion} /></div>}
        </section>

        <section>
          <h2 className="mb-4 text-xl font-semibold text-slate-800">Ejecuciones recientes</h2>
          {cargando ? <PageLoader /> : ejecuciones.length === 0 ? <EmptyState titulo="Aún no hay ejecuciones" detalle="Crea procesos y etapas desde Administración para comenzar la trazabilidad." /> : <div className="overflow-x-auto rounded-2xl border border-slate-200 bg-white"><table className="w-full text-left text-sm"><thead className="bg-slate-50 text-slate-500"><tr><th className="px-5 py-3">ID del proceso</th><th className="px-5 py-3">Etapa / documento</th><th className="px-5 py-3">Equipo</th><th className="px-5 py-3">Estado</th><th className="px-5 py-3">Entrada</th><th className="px-5 py-3">Salida</th></tr></thead><tbody>{ejecuciones.map((item) => <tr key={item.id} className="border-t border-slate-100"><td className="px-5 py-4 font-semibold text-slate-800">{item.codigo}</td><td className="px-5 py-4"><span>{item.etapa_nombre}</span><span className="block text-xs text-slate-400">{item.vale_codigo || item.lote_codigo || "—"}</span></td><td className="px-5 py-4">{item.equipo_nombre ?? "—"}</td><td className="px-5 py-4"><StatusBadge estado={item.estado} etiqueta={item.estado_etiqueta} /></td><td className="px-5 py-4 text-xs">{item.entradas.map((entrada) => entrada.lote_codigo || entrada.silo_codigo).filter(Boolean).join(" + ") || "—"}</td><td className="px-5 py-4 text-xs">{item.salidas.map((salida) => salida.lote_codigo || salida.silo_codigo).filter(Boolean).join(" + ") || "—"}</td></tr>)}</tbody></table></div>}
        </section>
      </div>
    </main>
  );
}
