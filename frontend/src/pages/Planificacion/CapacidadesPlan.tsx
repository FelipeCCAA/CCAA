import { useEffect, useState } from "react";
import { Gauge, Plus } from "lucide-react";
import { crearCapacidad, obtenerCapacidades, type CapacidadProceso } from "../../services/planificacion.service";
import type { Equipo } from "../../services/maestros.service";

export default function CapacidadesPlan({ equipos, editable }: { equipos: Equipo[]; editable: boolean }) {
  const [capacidades, setCapacidades] = useState<CapacidadProceso[]>([]);
  const [abierto, setAbierto] = useState(false);
  const [equipo, setEquipo] = useState("");
  const [vigente, setVigente] = useState(new Date().toISOString().slice(0, 10));
  const [cantidad, setCantidad] = useState("");
  const cargar = () => obtenerCapacidades().then(setCapacidades).catch(() => setCapacidades([]));
  useEffect(() => { void cargar(); }, []);
  const actuales = equipos.map((recurso) => ({ recurso, capacidad: capacidades.filter((item) => item.equipo === recurso.id).sort((a, b) => b.vigente_desde.localeCompare(a.vigente_desde))[0] })).filter((item) => item.capacidad);

  return <section className="rounded-2xl border border-slate-200 bg-white p-5">
    <div className="flex flex-wrap items-start justify-between gap-3"><div><h2 className="flex items-center gap-2 font-semibold text-slate-900"><Gauge className="h-4 w-4 text-emerald-700" />Capacidades vigentes</h2><p className="mt-1 text-xs text-slate-600">Una nueva vigencia no altera el cálculo histórico de actividades ya programadas.</p></div>{editable && <button type="button" onClick={() => setAbierto(!abierto)} className="inline-flex items-center gap-1 rounded-xl border border-emerald-700 px-3 py-2 text-sm font-semibold text-emerald-700"><Plus className="h-4 w-4" />Nueva vigencia</button>}</div>
    <div className="mt-3 flex flex-wrap gap-2">{actuales.map(({ recurso, capacidad }) => <span key={recurso.id} className="rounded-full bg-slate-100 px-3 py-1.5 text-xs text-slate-700"><strong>{recurso.nombre}</strong> · {Number(capacidad.capacidad_hora).toLocaleString("es-CL")} {capacidad.unidad} desde {capacidad.vigente_desde}</span>)}</div>
    {abierto && <form onSubmit={async (e) => { e.preventDefault(); await crearCapacidad({ equipo: Number(equipo), vigente_desde: vigente, capacidad_hora: Number(cantidad), unidad: "L/h" }); setAbierto(false); setCantidad(""); await cargar(); }} className="mt-4 grid gap-2 rounded-xl bg-slate-50 p-3 sm:grid-cols-4"><select required value={equipo} onChange={(e) => setEquipo(e.target.value)} className="rounded-lg border border-slate-300 px-3 py-2 text-sm"><option value="">Recurso…</option>{equipos.map((item) => <option key={item.id} value={item.id}>{item.nombre}</option>)}</select><input required type="date" value={vigente} onChange={(e) => setVigente(e.target.value)} className="rounded-lg border border-slate-300 px-3 py-2 text-sm" /><input required min="0.01" step="0.01" type="number" value={cantidad} onChange={(e) => setCantidad(e.target.value)} placeholder="Capacidad L/h" className="rounded-lg border border-slate-300 px-3 py-2 text-sm" /><button className="rounded-lg bg-emerald-700 px-3 py-2 text-sm font-semibold text-white">Guardar vigencia</button></form>}
  </section>;
}
