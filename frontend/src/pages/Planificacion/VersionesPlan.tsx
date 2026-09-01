import { useState } from "react";
import { GitCompareArrows } from "lucide-react";
import { compararVersiones, type ComparacionVersiones, type Programa } from "../../services/planificacion.service";

export default function VersionesPlan({ semanaId, versiones }: { semanaId: number; versiones: Programa["versiones"] }) {
  const [desde, setDesde] = useState("");
  const [hasta, setHasta] = useState("");
  const [resultado, setResultado] = useState<ComparacionVersiones | null>(null);
  if (versiones.length === 0) return null;
  const opciones = [...versiones].sort((a, b) => a.numero - b.numero);
  return <section className="rounded-2xl border border-slate-200 bg-white p-5">
    <h2 className="flex items-center gap-2 font-semibold text-slate-900"><GitCompareArrows className="h-4 w-4 text-violet-700" />Versiones publicadas</h2>
    <p className="mt-1 text-xs text-slate-600">Cada publicación conserva su fotografía; reabrir no borra la anterior.</p>
    <div className="mt-3 flex flex-wrap items-center gap-2"><select value={desde} onChange={(e) => setDesde(e.target.value)} className="rounded-lg border border-slate-300 px-3 py-2 text-sm"><option value="">Versión inicial…</option>{opciones.map((v) => <option key={v.id} value={v.numero}>v{v.numero} · {new Date(v.publicada_en).toLocaleString("es-CL")}</option>)}</select><select value={hasta} onChange={(e) => setHasta(e.target.value)} className="rounded-lg border border-slate-300 px-3 py-2 text-sm"><option value="">Versión final…</option>{opciones.map((v) => <option key={v.id} value={v.numero}>v{v.numero}</option>)}</select><button type="button" disabled={!desde || !hasta || desde === hasta} onClick={async () => setResultado(await compararVersiones(semanaId, Number(desde), Number(hasta)))} className="rounded-lg bg-violet-700 px-4 py-2 text-sm font-semibold text-white disabled:opacity-50">Comparar</button></div>
    {resultado && <div className="mt-4 grid gap-3 text-sm sm:grid-cols-2"><p className="rounded-xl bg-violet-50 p-3 text-violet-900"><strong>Actividades</strong><span className="mt-1 block text-xs">+{resultado.actividades.agregados.length} · −{resultado.actividades.eliminados.length} · {resultado.actividades.modificados.length} modificadas</span></p><p className="rounded-xl bg-sky-50 p-3 text-sky-900"><strong>Movimientos</strong><span className="mt-1 block text-xs">+{resultado.movimientos.agregados.length} · −{resultado.movimientos.eliminados.length} · {resultado.movimientos.modificados.length} modificados</span></p></div>}
  </section>;
}
