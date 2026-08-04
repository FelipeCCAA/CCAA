import { useEffect, useState } from "react";
import { GitBranch, Search } from "lucide-react";

import { EmptyState, ErrorState, PageLoader } from "../../components/ui/PageState";
import StatusBadge from "../../components/ui/StatusBadge";
import { obtenerEjecuciones, obtenerGenealogia, type EjecucionProceso, type Genealogia } from "../../services/procesos.service";

export default function Procesos() {
  const [ejecuciones, setEjecuciones] = useState<EjecucionProceso[]>([]);
  const [cargando, setCargando] = useState(true);
  const [error, setError] = useState("");
  const [loteId, setLoteId] = useState("");
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
    const id = Number(loteId);
    if (!Number.isInteger(id) || id <= 0) {
      setError("Ingresa el identificador numérico de un lote.");
      return;
    }
    setError("");
    try { setGenealogia(await obtenerGenealogia(id, direccion)); }
    catch { setError("No se encontró el lote o no fue posible reconstruir su genealogía."); }
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
            <input value={loteId} onChange={(e) => setLoteId(e.target.value)} placeholder="ID del lote" className="rounded-xl border border-slate-300 px-4 py-2.5" />
            <select value={direccion} onChange={(e) => setDireccion(e.target.value as "atras" | "adelante")} className="rounded-xl border border-slate-300 bg-white px-4 py-2.5"><option value="atras">Hacia atrás</option><option value="adelante">Hacia adelante</option></select>
            <button className="inline-flex items-center justify-center gap-2 rounded-xl bg-green-700 px-5 py-2.5 font-semibold text-white"><Search className="h-4 w-4" />Buscar</button>
          </form>
          {genealogia && <div className="mt-5 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">{genealogia.nodos.map((nodo) => <div key={nodo.id} className="rounded-xl border border-slate-200 p-4"><p className="font-semibold text-slate-800">{nodo.codigo}</p><p className="mt-1 text-sm text-slate-500">{nodo.producto} · {nodo.fecha}</p></div>)}</div>}
        </section>

        <section>
          <h2 className="mb-4 text-xl font-semibold text-slate-800">Ejecuciones recientes</h2>
          {cargando ? <PageLoader /> : ejecuciones.length === 0 ? <EmptyState titulo="Aún no hay ejecuciones" detalle="Crea procesos y etapas desde Administración para comenzar la trazabilidad." /> : <div className="overflow-x-auto rounded-2xl border border-slate-200 bg-white"><table className="w-full text-left text-sm"><thead className="bg-slate-50 text-slate-500"><tr><th className="px-5 py-3">Código</th><th className="px-5 py-3">Etapa</th><th className="px-5 py-3">Equipo</th><th className="px-5 py-3">Estado</th><th className="px-5 py-3">Entradas</th><th className="px-5 py-3">Salidas</th></tr></thead><tbody>{ejecuciones.map((item) => <tr key={item.id} className="border-t border-slate-100"><td className="px-5 py-4 font-semibold text-slate-800">{item.codigo}</td><td className="px-5 py-4">{item.etapa_nombre}</td><td className="px-5 py-4">{item.equipo_nombre ?? "—"}</td><td className="px-5 py-4"><StatusBadge estado={item.estado} etiqueta={item.estado_etiqueta} /></td><td className="px-5 py-4">{item.entradas.length}</td><td className="px-5 py-4">{item.salidas.length}</td></tr>)}</tbody></table></div>}
        </section>
      </div>
    </main>
  );
}
