import { useEffect, useMemo, useState } from "react";
import { X } from "lucide-react";

import { crearCondensacionGuiada, obtenerOpcionesAltaCondensacion, type CorridaCondensacion, type OpcionesAltaCondensacion } from "../../services/procesos.service";
import { mensajeErrorProceso } from "../../services/errores-proceso";

const campo = "w-full rounded-xl border border-slate-300 bg-white px-3 py-2.5 text-sm";

export default function NuevaCondensacion({ onCerrar, onCreada }: { onCerrar: () => void; onCreada: (corrida: CorridaCondensacion) => void }) {
  const [opciones, setOpciones] = useState<OpcionesAltaCondensacion | null>(null);
  const [lote, setLote] = useState("");
  const [destino, setDestino] = useState("");
  const [error, setError] = useState("");
  const [guardando, setGuardando] = useState(false);
  useEffect(() => { void obtenerOpcionesAltaCondensacion().then(setOpciones).catch(() => setError("No se pudieron cargar las entradas válidas.")); }, []);
  const seleccionado = opciones?.lotes.find((item) => item.id === Number(lote));
  const destinos = useMemo(() => (opciones?.silos ?? []).filter((silo) => {
    if (!seleccionado || silo.codigo === seleccionado.origen) return false;
    return Number(silo.capacidad_l) - Number(silo.saldo_l) >= Number(seleccionado.litros);
  }), [opciones, seleccionado]);
  const guardar = async (e: React.FormEvent) => { e.preventDefault(); if (guardando) return; setGuardando(true); setError(""); try { onCreada(await crearCondensacionGuiada({ lote: Number(lote), silo_destino: Number(destino) })); } catch (err) { setError(mensajeErrorProceso(err, "No se pudo crear la corrida.")); } finally { setGuardando(false); } };
  return <div className="fixed inset-0 z-[80] flex items-start justify-center overflow-y-auto bg-slate-950/45 p-4"><form onSubmit={guardar} className="my-8 w-full max-w-2xl rounded-2xl bg-white p-6 shadow-xl"><div className="flex justify-between gap-3"><div><p className="text-xs font-bold uppercase tracking-wide text-blue-700">Alta guiada</p><h2 className="mt-1 text-xl font-bold">Nueva evaporación</h2><p className="mt-2 text-sm text-slate-600">Solo aparecen lotes abiertos desde un vale, con orden y evaporador ya trazados.</p></div><button type="button" onClick={onCerrar} className="h-fit rounded-lg p-2 hover:bg-slate-100"><X className="h-5 w-5" /></button></div>{!opciones && !error ? <p className="mt-6 text-sm text-slate-500">Cargando opciones…</p> : <div className="mt-6 space-y-4"><label className="block text-sm font-medium text-slate-700">Lote / entrada preparada<select required value={lote} onChange={(e) => { setLote(e.target.value); setDestino(""); }} className={`mt-1 ${campo}`}><option value="">Seleccionar…</option>{opciones?.lotes.map((item) => <option key={item.id} value={item.id}>{item.codigo} · {item.producto} · {item.origen} · {Number(item.litros).toLocaleString("es-CL")} L</option>)}</select></label>{opciones?.lotes.length === 0 && <p className="rounded-xl bg-amber-50 p-3 text-sm text-amber-800">No hay entradas preparadas. Abre el lote desde un vale, vincúlalo a una OP y selecciona un evaporador.</p>}{seleccionado && <div className="grid gap-2 rounded-xl bg-blue-50 p-4 text-sm sm:grid-cols-2"><p><span className="text-slate-500">Orden</span><br /><b>{seleccionado.orden}</b></p><p><span className="text-slate-500">Equipo</span><br /><b>{seleccionado.equipo}</b></p><p><span className="text-slate-500">Origen</span><br /><b>{seleccionado.origen}</b></p><p><span className="text-slate-500">Litros trazados</span><br /><b>{Number(seleccionado.litros).toLocaleString("es-CL")} L</b></p></div>}<label className="block text-sm font-medium text-slate-700">Silo de concentrado<select required disabled={!seleccionado} value={destino} onChange={(e) => setDestino(e.target.value)} className={`mt-1 ${campo}`}><option value="">Seleccionar destino con capacidad…</option>{destinos.map((item) => <option key={item.id} value={item.id}>{item.codigo} · libre {(Number(item.capacidad_l) - Number(item.saldo_l)).toLocaleString("es-CL")} L · {item.estado}</option>)}</select></label></div>}{error && <p className="mt-4 rounded-xl bg-rose-50 p-3 text-sm text-rose-700">{error}</p>}<div className="mt-6 flex justify-end gap-3"><button type="button" onClick={onCerrar} className="px-4 py-2 text-sm text-slate-600">Cancelar</button><button disabled={guardando || !lote || !destino} className="rounded-xl bg-blue-700 px-5 py-2.5 text-sm font-semibold text-white disabled:opacity-40">{guardando ? "Creando…" : "Crear corrida preparada"}</button></div></form></div>;
}
