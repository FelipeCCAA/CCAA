import { useState } from "react";
import { Recycle, RefreshCw } from "lucide-react";

import {
  consumirRework, obtenerReworkDisponible,
  type EjecucionOperativa, type ReworkDisponible,
} from "../../services/procesos.service";

const numero = new Intl.NumberFormat("es-CL", { maximumFractionDigits: 2 });

export default function ReworkProduccion({
  ejecuciones, puedeOperar, alConsumir,
}: {
  ejecuciones: EjecucionOperativa[];
  puedeOperar: boolean;
  alConsumir: () => Promise<void>;
}) {
  const [materiales, setMateriales] = useState<ReworkDisponible[] | null>(null);
  const [seleccionado, setSeleccionado] = useState<ReworkDisponible | null>(null);
  const [ejecucion, setEjecucion] = useState(0);
  const [cantidad, setCantidad] = useState("");
  const [motivo, setMotivo] = useState("");
  const [cargando, setCargando] = useState(false);
  const [guardando, setGuardando] = useState(false);
  const [mensaje, setMensaje] = useState("");
  const [error, setError] = useState("");

  const cargar = async () => {
    setCargando(true); setError("");
    try { setMateriales(await obtenerReworkDisponible()); }
    catch { setError("No se pudo consultar el rework autorizado."); }
    finally { setCargando(false); }
  };

  const elegir = (item: ReworkDisponible) => {
    setSeleccionado(item);
    setCantidad(item.cantidad_disponible_kg);
    setMotivo(item.motivo);
    setEjecucion(ejecuciones[0]?.id ?? 0);
    setMensaje(""); setError("");
  };

  const guardar = async (evento: React.FormEvent) => {
    evento.preventDefault();
    if (!seleccionado || !ejecucion) return;
    const kg = Number(cantidad);
    if (!Number.isFinite(kg) || kg <= 0 || kg > Number(seleccionado.cantidad_disponible_kg)) {
      setError(`Ingresa entre 0,01 y ${seleccionado.cantidad_disponible_kg} kg.`);
      return;
    }
    if (!motivo.trim()) { setError("El uso de rework requiere un motivo operativo."); return; }
    setGuardando(true); setError("");
    try {
      await consumirRework({ ejecucion, lote: seleccionado.lote_id, cantidad: kg, motivo: motivo.trim() });
      setMensaje(`${numero.format(kg)} kg de ${seleccionado.lote_codigo} vinculados a la ejecución.`);
      setSeleccionado(null);
      await Promise.all([cargar(), alConsumir()]);
    } catch (peticion: unknown) {
      const datos = (peticion as { response?: { data?: unknown } }).response?.data;
      setError(datos && typeof datos === "object" ? Object.values(datos as Record<string, unknown>).flat().map(String).join(" ") : "No se pudo registrar el consumo.");
    } finally { setGuardando(false); }
  };

  return (
    <section className="rounded-2xl border border-amber-200 bg-white p-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="flex gap-3"><span className="rounded-xl bg-amber-100 p-2 text-amber-800"><Recycle className="h-5 w-5" /></span><div><h2 className="font-bold text-slate-900">Rework autorizado</h2><p className="mt-1 text-sm text-slate-600">Sólo muestra lotes aprobados por Calidad y su saldo reutilizable.</p></div></div>
        <button type="button" onClick={() => void cargar()} disabled={cargando} className="inline-flex items-center gap-2 rounded-xl border border-amber-300 px-3 py-2 text-sm font-semibold text-amber-800 disabled:opacity-50"><RefreshCw className={`h-4 w-4 ${cargando ? "animate-spin" : ""}`} />{materiales === null ? "Consultar" : "Actualizar"}</button>
      </div>
      {error && <p className="mt-3 rounded-lg bg-rose-50 px-3 py-2 text-sm text-rose-700">{error}</p>}
      {mensaje && <p className="mt-3 rounded-lg bg-emerald-50 px-3 py-2 text-sm text-emerald-800">{mensaje}</p>}
      {materiales === null && <p className="mt-4 text-sm text-slate-500">La consulta se ejecuta al presionar el botón para reducir carga.</p>}
      {materiales?.length === 0 && <p className="mt-4 text-sm text-slate-500">No hay rework aprobado con saldo.</p>}
      {materiales && materiales.length > 0 && <div className="mt-4 grid gap-3 lg:grid-cols-2">{materiales.map((item) => <button key={item.id} type="button" disabled={!puedeOperar} onClick={() => elegir(item)} className="rounded-xl border border-slate-200 p-4 text-left hover:border-amber-300 disabled:cursor-not-allowed disabled:opacity-60"><div className="flex justify-between gap-3"><div><p className="font-semibold text-slate-900">{item.producto_nombre}</p><p className="text-xs text-slate-500">Lote {item.lote_codigo} · {item.origen.replaceAll("_", " ")}</p></div><span className="text-lg font-bold text-amber-800">{numero.format(Number(item.cantidad_disponible_kg))} kg</span></div><p className="mt-2 text-xs text-slate-600">Autorizado {numero.format(Number(item.cantidad_autorizada_kg))} kg · utilizado {numero.format(Number(item.cantidad_consumida_kg))} kg</p><p className="mt-1 text-xs text-slate-500">{item.motivo}</p></button>)}</div>}
      {seleccionado && <form onSubmit={guardar} className="mt-4 grid gap-3 rounded-xl bg-amber-50 p-4 md:grid-cols-2"><div className="md:col-span-2"><p className="font-semibold text-amber-950">Consumir lote {seleccionado.lote_codigo}</p><p className="text-xs text-amber-800">Disponible: {seleccionado.cantidad_disponible_kg} kg. La genealogía conservará el lote de origen.</p></div><label className="text-sm font-medium text-slate-700">Ejecución destino<select required value={ejecucion} onChange={(e) => setEjecucion(Number(e.target.value))} className="mt-1 w-full rounded-lg border border-slate-300 bg-white px-3 py-2"><option value={0}>Seleccionar…</option>{ejecuciones.map((item) => <option key={item.id} value={item.id}>{item.codigo} · {item.etapa_nombre} · {item.equipo_nombre ?? "sin equipo"}</option>)}</select></label><label className="text-sm font-medium text-slate-700">Cantidad (kg)<input required type="number" min="0.01" step="0.01" max={seleccionado.cantidad_disponible_kg} value={cantidad} onChange={(e) => setCantidad(e.target.value)} className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2" /></label><label className="text-sm font-medium text-slate-700 md:col-span-2">Motivo de incorporación<textarea required value={motivo} onChange={(e) => setMotivo(e.target.value)} className="mt-1 min-h-20 w-full rounded-lg border border-slate-300 px-3 py-2" /></label><div className="flex justify-end gap-2 md:col-span-2"><button type="button" onClick={() => setSeleccionado(null)} className="px-3 py-2 text-sm text-slate-600">Cancelar</button><button disabled={guardando} className="rounded-lg bg-amber-700 px-4 py-2 text-sm font-semibold text-white disabled:opacity-50">{guardando ? "Registrando…" : "Registrar consumo"}</button></div></form>}
    </section>
  );
}
