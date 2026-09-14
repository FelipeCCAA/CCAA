import { useMemo, useState } from "react";
import { X } from "lucide-react";

import { calcularBalanceMantequilla } from "../../services/balance-mantequilla";
import { mensajeErrorProceso } from "../../services/errores-proceso";
import { cerrarMantequilla, type CorridaMantequilla } from "../../services/procesos.service";

const campo = "mt-1 w-full rounded-xl border border-slate-300 px-3 py-2.5 text-sm outline-none focus:border-amber-600";

export default function CierreMantequilla({ corrida, onCerrar, onCerrada }: {
  corrida: CorridaMantequilla;
  onCerrar: () => void;
  onCerrada: (corrida: CorridaMantequilla) => void | Promise<void>;
}) {
  const [datos, setDatos] = useState({
    mantequilla: "", suero: "", merma: "", reproceso: "",
    motivoReproceso: "", humedad: "",
  });
  const [ocupado, setOcupado] = useState(false);
  const [error, setError] = useState("");
  const balance = useMemo(() => calcularBalanceMantequilla(corrida.kg_crema, {
    mantequilla: datos.mantequilla,
    suero: datos.suero,
    merma: datos.merma,
    reproceso: datos.reproceso,
  }), [corrida.kg_crema, datos]);

  const guardar = async (evento: React.FormEvent) => {
    evento.preventDefault();
    if (ocupado) return;
    setError("");
    if (!balance.cuadrado) {
      setError(balance.excedido
        ? `El balance excede la crema utilizada por ${Math.abs(balance.diferencia).toLocaleString("es-CL")} kg.`
        : `Faltan ${balance.diferencia.toLocaleString("es-CL")} kg por clasificar.`);
      return;
    }
    if (Number(datos.reproceso || 0) > 0 && !datos.motivoReproceso.trim()) {
      setError("Indica por qué el material debe segregarse para reproceso.");
      return;
    }
    setOcupado(true);
    try {
      await onCerrada(await cerrarMantequilla(corrida.id, {
        kg_mantequilla: Number(datos.mantequilla),
        kg_suero: Number(datos.suero || 0),
        kg_merma: Number(datos.merma || 0),
        kg_reproceso: Number(datos.reproceso || 0),
        motivo_reproceso: datos.motivoReproceso.trim(),
        controles: datos.humedad ? { humedad: Number(datos.humedad) } : {},
      }));
    } catch (e) {
      setError(mensajeErrorProceso(e, "No se pudo cerrar la corrida de mantequilla."));
    } finally {
      setOcupado(false);
    }
  };

  return <div className="fixed inset-0 z-[80] flex items-start justify-center overflow-y-auto bg-slate-950/45 p-4">
    <form onSubmit={guardar} className="my-8 w-full max-w-2xl rounded-2xl bg-white p-6 shadow-xl">
      <div className="flex items-start justify-between gap-4">
        <div>
          <p className="text-xs font-bold uppercase tracking-wide text-amber-700">{corrida.ejecucion_codigo}</p>
          <h2 className="mt-1 text-xl font-bold">Cerrar proceso de mantequilla</h2>
          <p className="mt-2 text-sm text-slate-600">Origen {corrida.crema_codigo} · {Number(corrida.kg_crema).toLocaleString("es-CL")} kg de crema.</p>
        </div>
        <button type="button" onClick={onCerrar} className="rounded-lg p-2 hover:bg-slate-100" aria-label="Cerrar"><X className="h-5 w-5" /></button>
      </div>

      <div className="mt-6 grid gap-4 sm:grid-cols-2">
        <Etiqueta texto="Mantequilla producida (kg)">
          <input required min="0.001" step="0.001" type="number" value={datos.mantequilla} onChange={(e) => setDatos({ ...datos, mantequilla: e.target.value })} className={campo} />
        </Etiqueta>
        <Etiqueta texto="Suero / mazada recuperada (kg)">
          <input min="0" step="0.001" type="number" disabled={!corrida.lote_suero} value={datos.suero} onChange={(e) => setDatos({ ...datos, suero: e.target.value })} className={`${campo} disabled:bg-slate-100 disabled:text-slate-500`} />
          {!corrida.lote_suero && <span className="mt-1 block text-xs font-normal text-rose-700">Esta corrida no tiene un lote de suero asociado. Registra 0 kg.</span>}
        </Etiqueta>
        <Etiqueta texto="Merma medida (kg)">
          <input min="0" step="0.001" type="number" value={datos.merma} onChange={(e) => setDatos({ ...datos, merma: e.target.value })} className={campo} />
        </Etiqueta>
        <Etiqueta texto="Material segregado para reproceso (kg)">
          <input min="0" step="0.001" type="number" value={datos.reproceso} onChange={(e) => setDatos({ ...datos, reproceso: e.target.value })} className={campo} />
        </Etiqueta>
        {Number(datos.reproceso || 0) > 0 && <label className="text-sm font-medium text-slate-700 sm:col-span-2">
          Motivo del reproceso
          <textarea required maxLength={250} rows={3} value={datos.motivoReproceso} onChange={(e) => setDatos({ ...datos, motivoReproceso: e.target.value })} className={campo} placeholder="Ej.: textura fuera de objetivo; segregar para evaluación de Calidad" />
          <span className="mt-1 block text-xs font-normal text-slate-500">Se creará un lote separado y pendiente de la decisión de Calidad.</span>
        </label>}
        <Etiqueta texto="Humedad (%)">
          <input min="0" max="100" step="0.01" type="number" value={datos.humedad} onChange={(e) => setDatos({ ...datos, humedad: e.target.value })} className={campo} />
        </Etiqueta>
      </div>

      <div className={`mt-4 rounded-xl px-4 py-3 text-sm ${balance.cuadrado ? "bg-emerald-50 text-emerald-900" : balance.excedido ? "bg-rose-50 text-rose-800" : "bg-amber-50 text-amber-900"}`} role="status">
        <span className="font-semibold">{balance.cuadrado ? "Balance completo" : balance.excedido ? "Balance excedido" : "Balance incompleto"}</span>
        {" · "}{balance.clasificado.toLocaleString("es-CL")} de {balance.entrada.toLocaleString("es-CL")} kg clasificados
        {!balance.cuadrado && <> · diferencia <b>{balance.diferencia.toLocaleString("es-CL")} kg</b></>}.
      </div>
      {error && <p className="mt-4 rounded-xl bg-rose-50 px-4 py-3 text-sm text-rose-700">{error}</p>}
      <div className="mt-6 flex justify-end gap-3">
        <button type="button" onClick={onCerrar} className="px-4 py-2.5 text-sm text-slate-600">Cancelar</button>
        <button disabled={ocupado || !balance.cuadrado} className="rounded-xl bg-amber-700 px-5 py-2.5 text-sm font-semibold text-white disabled:opacity-40">{ocupado ? "Cerrando…" : "Cerrar y enviar a Calidad"}</button>
      </div>
    </form>
  </div>;
}

function Etiqueta({ texto, children }: { texto: string; children: React.ReactNode }) {
  return <label className="text-sm font-medium text-slate-700">{texto}{children}</label>;
}
