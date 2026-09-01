import { useState } from "react";
import { ArrowDownToLine, Trash2 } from "lucide-react";

import { borrarMovimientoPlan, crearMovimientoPlan, type MovimientoPlan } from "../../services/planificacion.service";
import type { Mandante } from "../../services/maestros.service";

interface Props {
  semanaId: number;
  fechaInicio: string;
  movimientos: MovimientoPlan[];
  mandantes: Mandante[];
  editable: boolean;
  alCambiar: () => Promise<void>;
}

const campo = "rounded-xl border border-slate-300 bg-white px-3 py-2 text-sm";

export default function MovimientosPlan({ semanaId, fechaInicio, movimientos, mandantes, editable, alCambiar }: Props) {
  const [abierto, setAbierto] = useState(false);
  const [tipo, setTipo] = useState<MovimientoPlan["tipo"]>("recepcion");
  const [propietario, setPropietario] = useState("");
  const [fechaHora, setFechaHora] = useState(`${fechaInicio}T08:00`);
  const [cantidad, setCantidad] = useState("");
  const [documento, setDocumento] = useState("");
  const [observacion, setObservacion] = useState("");
  const [error, setError] = useState("");

  const guardar = async (evento: React.FormEvent) => {
    evento.preventDefault(); setError("");
    try {
      await crearMovimientoPlan({ semana: semanaId, fecha_hora: new Date(fechaHora).toISOString(), propietario: Number(propietario), tipo, cantidad: Number(cantidad), documento, observacion });
      setCantidad(""); setDocumento(""); setObservacion(""); setAbierto(false);
      await alCambiar();
    } catch { setError("No se pudo registrar. Revisa fecha, cantidad y motivo del ajuste."); }
  };

  return <section className="rounded-2xl border border-slate-200 bg-white p-5">
    <div className="flex flex-wrap items-start justify-between gap-3"><div><h2 className="font-semibold text-slate-900">Movimientos planificados de leche</h2><p className="mt-1 text-xs text-slate-600">Stock, recepciones, despachos y trasvasijes quedan identificados; no se esconden dentro de fórmulas.</p></div>{editable && <button type="button" onClick={() => setAbierto(!abierto)} className="inline-flex items-center gap-2 rounded-xl bg-emerald-700 px-4 py-2 text-sm font-semibold text-white"><ArrowDownToLine className="h-4 w-4" />Registrar movimiento</button>}</div>

    {abierto && <form onSubmit={(e) => void guardar(e)} className="mt-4 grid gap-3 rounded-xl bg-slate-50 p-4 md:grid-cols-3">
      <select required value={tipo} onChange={(e) => setTipo(e.target.value as MovimientoPlan["tipo"])} className={campo}><option value="stock_inicial">Stock inicial</option><option value="recepcion">Recepción</option><option value="despacho">Despacho</option><option value="trasvasije_salida">Trasvasije salida</option><option value="trasvasije_entrada">Trasvasije entrada</option><option value="ajuste">Ajuste identificado</option></select>
      <select required value={propietario} onChange={(e) => setPropietario(e.target.value)} className={campo}><option value="">Propietario / origen…</option>{mandantes.filter((m) => m.activo).map((m) => <option key={m.id} value={m.id}>{m.nombre}</option>)}</select>
      <input required type="datetime-local" value={fechaHora} min={`${fechaInicio}T00:00`} onChange={(e) => setFechaHora(e.target.value)} className={campo} />
      <input required type="number" step="0.01" value={cantidad} onChange={(e) => setCantidad(e.target.value)} placeholder="Cantidad (L)" className={campo} />
      <input value={documento} onChange={(e) => setDocumento(e.target.value)} placeholder="Documento / referencia" className={campo} />
      <input required={tipo === "ajuste"} value={observacion} onChange={(e) => setObservacion(e.target.value)} placeholder={tipo === "ajuste" ? "Motivo obligatorio" : "Observación"} className={campo} />
      {error && <p className="text-sm text-red-700 md:col-span-3">{error}</p>}
      <button className="rounded-xl bg-emerald-700 px-4 py-2 text-sm font-semibold text-white md:col-span-3">Guardar y recalcular</button>
    </form>}

    {movimientos.length === 0 ? <p className="mt-4 text-sm text-slate-600">Aún no hay movimientos explícitos. El balance histórico sigue visible mientras completas esta semana.</p> : <div className="mt-4 overflow-x-auto"><table className="w-full text-left text-sm"><thead className="text-xs uppercase text-slate-600"><tr><th className="pb-2">Fecha</th><th className="pb-2">Tipo</th><th className="pb-2">Propietario</th><th className="pb-2 text-right">Cantidad</th><th className="pb-2">Documento</th><th /></tr></thead><tbody>{movimientos.map((m) => <tr key={m.id} className="border-t border-slate-100"><td className="py-3">{new Date(m.fecha_hora).toLocaleString("es-CL")}</td><td>{m.tipo_etiqueta}</td><td>{m.propietario_nombre}</td><td className="text-right font-medium">{Number(m.cantidad).toLocaleString("es-CL")} L</td><td>{m.documento || m.observacion || "—"}</td><td className="text-right">{editable && <button type="button" onClick={async () => { await borrarMovimientoPlan(m.id); await alCambiar(); }} className="rounded-lg p-2 text-slate-500 hover:bg-red-50 hover:text-red-700" aria-label="Eliminar movimiento"><Trash2 className="h-4 w-4" /></button>}</td></tr>)}</tbody></table></div>}
  </section>;
}
