import { useMemo, useState } from "react";
import { X } from "lucide-react";

import { cerrarMantequilla, type CorridaMantequilla } from "../../services/procesos.service";

const campo = "mt-1 w-full rounded-xl border border-slate-300 px-3 py-2.5 text-sm outline-none focus:border-amber-600";

function mensajeDe(error: unknown) {
  const datos = (error as { response?: { data?: unknown } }).response?.data;
  if (typeof datos === "string") return datos;
  if (datos && typeof datos === "object") return Object.values(datos as Record<string, unknown>).flat().map(String).join(" ");
  return "No se pudo cerrar la corrida de mantequilla.";
}

export default function CierreMantequilla({ corrida, onCerrar, onCerrada }: {
  corrida: CorridaMantequilla;
  onCerrar: () => void;
  onCerrada: (corrida: CorridaMantequilla) => void | Promise<void>;
}) {
  const [datos, setDatos] = useState({ mantequilla: "", suero: "", merma: "", humedad: "" });
  const [ocupado, setOcupado] = useState(false);
  const [error, setError] = useState("");
  const total = useMemo(() => Number(datos.mantequilla || 0) + Number(datos.suero || 0) + Number(datos.merma || 0), [datos]);
  const diferencia = Number(corrida.kg_crema) - total;

  const guardar = async (evento: React.FormEvent) => {
    evento.preventDefault();
    if (ocupado) return;
    setError("");
    if (total > Number(corrida.kg_crema)) { setError("Mantequilla, suero y merma superan la crema utilizada."); return; }
    setOcupado(true);
    try {
      await onCerrada(await cerrarMantequilla(corrida.id, {
        kg_mantequilla: Number(datos.mantequilla),
        kg_suero: Number(datos.suero || 0),
        kg_merma: Number(datos.merma || 0),
        controles: datos.humedad ? { humedad: Number(datos.humedad) } : {},
      }));
    } catch (e) { setError(mensajeDe(e)); }
    finally { setOcupado(false); }
  };

  return <div className="fixed inset-0 z-[80] flex items-start justify-center overflow-y-auto bg-slate-950/45 p-4">
    <form onSubmit={guardar} className="my-8 w-full max-w-2xl rounded-2xl bg-white p-6 shadow-xl">
      <div className="flex items-start justify-between gap-4"><div><p className="text-xs font-bold uppercase tracking-wide text-amber-700">{corrida.ejecucion_codigo}</p><h2 className="mt-1 text-xl font-bold">Cerrar proceso de mantequilla</h2><p className="mt-2 text-sm text-slate-600">Origen {corrida.crema_codigo} · {Number(corrida.kg_crema).toLocaleString("es-CL")} kg de crema.</p></div><button type="button" onClick={onCerrar} className="rounded-lg p-2 hover:bg-slate-100" aria-label="Cerrar"><X className="h-5 w-5" /></button></div>
      <div className="mt-6 grid gap-4 sm:grid-cols-2">
        <Etiqueta texto="Mantequilla producida (kg)"><input required min="0.001" step="0.001" type="number" value={datos.mantequilla} onChange={(e) => setDatos({ ...datos, mantequilla: e.target.value })} className={campo} /></Etiqueta>
        <Etiqueta texto="Suero generado (kg)"><input min="0" step="0.001" type="number" value={datos.suero} onChange={(e) => setDatos({ ...datos, suero: e.target.value })} className={campo} /></Etiqueta>
        <Etiqueta texto="Merma medida (kg)"><input min="0" step="0.001" type="number" value={datos.merma} onChange={(e) => setDatos({ ...datos, merma: e.target.value })} className={campo} /></Etiqueta>
        <Etiqueta texto="Humedad (%)"><input min="0" max="100" step="0.01" type="number" value={datos.humedad} onChange={(e) => setDatos({ ...datos, humedad: e.target.value })} className={campo} /></Etiqueta>
      </div>
      <div className={`mt-4 rounded-xl px-4 py-3 text-sm ${diferencia < 0 ? "bg-rose-50 text-rose-800" : "bg-amber-50 text-amber-900"}`}>Balance: <b>{total.toLocaleString("es-CL")} kg</b> registrados · diferencia pendiente <b>{diferencia.toLocaleString("es-CL")} kg</b>.</div>
      {error && <p className="mt-4 rounded-xl bg-rose-50 px-4 py-3 text-sm text-rose-700">{error}</p>}
      <div className="mt-6 flex justify-end gap-3"><button type="button" onClick={onCerrar} className="px-4 py-2.5 text-sm text-slate-600">Cancelar</button><button disabled={ocupado} className="rounded-xl bg-amber-700 px-5 py-2.5 text-sm font-semibold text-white disabled:opacity-40">{ocupado ? "Cerrando…" : "Cerrar y enviar a Calidad"}</button></div>
    </form>
  </div>;
}

function Etiqueta({ texto, children }: { texto: string; children: React.ReactNode }) {
  return <label className="text-sm font-medium text-slate-700">{texto}{children}</label>;
}
