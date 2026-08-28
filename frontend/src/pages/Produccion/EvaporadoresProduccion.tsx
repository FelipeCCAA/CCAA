import { useState } from "react";
import { Factory, RefreshCw } from "lucide-react";

import { obtenerEquipos, type Equipo } from "../../services/maestros.service";
import { iniciarCondensacion, obtenerCondensaciones, type CorridaCondensacion } from "../../services/procesos.service";

export default function EvaporadoresProduccion() {
  const [abierto, setAbierto] = useState(false);
  const [equipos, setEquipos] = useState<Equipo[]>([]);
  const [corridas, setCorridas] = useState<CorridaCondensacion[]>([]);
  const [cargando, setCargando] = useState(false);
  const [error, setError] = useState("");

  async function cargar() {
    setCargando(true); setError("");
    try {
      const [maquinas, pagina] = await Promise.all([obtenerEquipos(), obtenerCondensaciones()]);
      setEquipos(maquinas.filter((e) => e.activo && e.tipo === "evaporador"));
      setCorridas(pagina.results);
      setAbierto(true);
    } catch { setError("No se pudo cargar el estado de evaporadores."); }
    finally { setCargando(false); }
  }

  async function iniciar(corrida: CorridaCondensacion) {
    setError("");
    try {
      const actualizada = await iniciarCondensacion(corrida.id);
      setCorridas((lista) => lista.map((item) => item.id === actualizada.id ? actualizada : item));
    } catch (e) {
      const data = (e as { response?: { data?: unknown } }).response?.data;
      setError(typeof data === "string" ? data : "No se pudo iniciar: revisa saldo, Calidad, aseo y disponibilidad del evaporador.");
    }
  }

  if (!abierto) return <section className="mb-8 rounded-2xl border border-blue-200 bg-blue-50/60 p-5"><div className="flex flex-wrap items-center justify-between gap-4"><div><h2 className="flex items-center gap-2 font-bold text-slate-900"><Factory className="h-5 w-5 text-blue-700" /> Evaporación / condensación</h2><p className="mt-1 text-sm text-slate-600">Consulta bajo demanda qué evaporador está disponible, preparado o evaporando leche.</p></div><button onClick={() => void cargar()} disabled={cargando} className="rounded-xl bg-blue-700 px-4 py-2.5 text-sm font-semibold text-white">{cargando ? "Cargando…" : "Ver evaporadores"}</button></div>{error && <p className="mt-3 text-sm text-rose-700">{error}</p>}</section>;

  return <section className="mb-8"><div className="mb-3 flex items-center justify-between"><div><h2 className="text-xl font-bold text-slate-900">Evaporadores</h2><p className="text-sm text-slate-600">El estado se deriva de la corrida real; no se marca manualmente.</p></div><button onClick={() => void cargar()} className="rounded-lg p-2 text-slate-600"><RefreshCw className="h-4 w-4" /></button></div>{error && <p className="mb-3 text-sm text-rose-700">{error}</p>}<div className="grid gap-4 md:grid-cols-3">{equipos.map((equipo) => {
    const corrida = corridas.find((c) => c.equipo_id === equipo.id && ["borrador", "en_proceso", "pendiente_calidad"].includes(c.estado));
    const evaporando = corrida?.estado === "en_proceso";
    return <article key={equipo.id} className={`rounded-2xl border bg-white p-5 ${evaporando ? "border-blue-400 ring-1 ring-blue-200" : "border-slate-200"}`}><div className="flex items-center justify-between"><span className="rounded-xl bg-blue-50 p-2 text-blue-700"><Factory className="h-5 w-5" /></span><span className={`rounded-full px-2.5 py-1 text-xs font-bold ${evaporando ? "bg-blue-100 text-blue-800" : corrida ? "bg-amber-100 text-amber-800" : "bg-emerald-100 text-emerald-800"}`}>{evaporando ? "EVAPORANDO LECHE" : corrida ? "PREPARADO" : "DISPONIBLE"}</span></div><h3 className="mt-4 font-bold text-slate-900">{equipo.codigo} · {equipo.nombre}</h3>{corrida ? <div className="mt-3 text-sm text-slate-600"><p>{corrida.silo_origen_codigo} → {corrida.silo_destino_codigo}</p><p><b>{Number(corrida.litros_entrada).toLocaleString("es-CL")} L</b> · lote {corrida.lote_codigo}</p><p className="text-xs">Corrida {corrida.ejecucion_codigo}</p>{corrida.estado === "borrador" && <button onClick={() => void iniciar(corrida)} className="mt-3 rounded-xl bg-blue-700 px-4 py-2 text-sm font-semibold text-white">Iniciar evaporación</button>}</div> : <p className="mt-3 text-sm text-slate-500">Sin corrida asignada.</p>}</article>;
  })}</div></section>;
}
