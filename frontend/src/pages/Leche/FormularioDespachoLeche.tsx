import { useState } from "react";
import { Truck, X } from "lucide-react";

import { mensajeDe } from "../../components/seccion/utilidades";
import { crearDespachoLeche, type DespachoLeche } from "../../services/recepcion.service";

const control = "mt-1 w-full rounded-xl border border-slate-300 bg-white px-3 py-2.5";
const ahoraLocal = () => {
  const fecha = new Date();
  fecha.setMinutes(fecha.getMinutes() - fecha.getTimezoneOffset());
  return fecha.toISOString().slice(0, 16);
};

export default function FormularioDespachoLeche({ siloId, siloCodigo, disponible, onCerrar, onCreado }: {
  siloId: number;
  siloCodigo: string;
  disponible: number;
  onCerrar: () => void;
  onCreado: (despacho: DespachoLeche) => Promise<void>;
}) {
  const [datos, setDatos] = useState({
    litros: "", destino: "", guia_despacho: "", patente: "", fecha_hora: ahoraLocal(),
  });
  const [operacionId] = useState(() => crypto.randomUUID());
  const [guardando, setGuardando] = useState(false);
  const [error, setError] = useState("");

  const guardar = async (evento: React.FormEvent) => {
    evento.preventDefault();
    setGuardando(true);
    setError("");
    try {
      const despacho = await crearDespachoLeche({
        silo: siloId, litros: Number(datos.litros), destino: datos.destino.trim(),
        guia_despacho: datos.guia_despacho.trim(), patente: datos.patente.trim(),
        fecha_hora: new Date(datos.fecha_hora).toISOString(), operacion_id: operacionId,
      });
      await onCreado(despacho);
    } catch (fallo) {
      setError(mensajeDe(fallo, "No se pudo registrar el despacho."));
    } finally { setGuardando(false); }
  };

  return (
    <div className="fixed inset-0 z-[80] flex items-start justify-center overflow-y-auto bg-slate-950/45 p-4">
      <form onSubmit={guardar} className="my-8 w-full max-w-2xl rounded-2xl bg-white p-6 shadow-xl">
        <div className="flex items-center justify-between"><div className="flex items-center gap-3"><span className="rounded-xl bg-emerald-50 p-2 text-emerald-700"><Truck className="h-5 w-5" /></span><div><p className="text-xs font-semibold uppercase tracking-wide text-emerald-700">Salida a granel</p><h2 className="text-xl font-semibold">Despachar desde {siloCodigo}</h2></div></div><button type="button" onClick={onCerrar} className="rounded-lg p-2 hover:bg-slate-100"><X className="h-5 w-5" /></button></div>
        <p className="mt-4 rounded-xl bg-slate-50 px-4 py-3 text-sm text-slate-600">Disponible: {disponible.toLocaleString("es-CL")} L. Se exige análisis vigente, firma de visualización y liberación de inocuidad.</p>
        <div className="mt-5 grid gap-4 sm:grid-cols-2">
          <Campo texto="Litros"><input required type="number" min="0.01" max={disponible} step="0.01" value={datos.litros} onChange={(e) => setDatos({ ...datos, litros: e.target.value })} className={control} /></Campo>
          <Campo texto="Fecha y hora"><input required type="datetime-local" value={datos.fecha_hora} onChange={(e) => setDatos({ ...datos, fecha_hora: e.target.value })} className={control} /></Campo>
          <Campo texto="Destino o cliente"><input required maxLength={160} value={datos.destino} onChange={(e) => setDatos({ ...datos, destino: e.target.value })} className={control} /></Campo>
          <Campo texto="Guía de despacho"><input required maxLength={60} value={datos.guia_despacho} onChange={(e) => setDatos({ ...datos, guia_despacho: e.target.value })} className={control} /></Campo>
          <Campo texto="Patente del vehículo"><input required maxLength={15} value={datos.patente} onChange={(e) => setDatos({ ...datos, patente: e.target.value.toUpperCase() })} className={control} /></Campo>
        </div>
        {error && <p className="mt-4 rounded-xl bg-rose-50 px-4 py-3 text-sm text-rose-700">{error}</p>}
        <div className="mt-6 flex justify-end gap-3"><button type="button" onClick={onCerrar} className="px-4 py-2.5 text-sm text-slate-600">Cancelar</button><button disabled={guardando} className="rounded-xl bg-emerald-700 px-5 py-2.5 text-sm font-semibold text-white disabled:opacity-40">{guardando ? "Registrando…" : "Confirmar despacho"}</button></div>
      </form>
    </div>
  );
}

function Campo({ texto, children }: { texto: string; children: React.ReactNode }) {
  return <label className="text-sm text-slate-600">{texto}{children}</label>;
}
