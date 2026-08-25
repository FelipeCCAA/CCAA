import { useState } from "react";
import { X } from "lucide-react";

import { mensajeDe } from "../../components/seccion/utilidades";
import { cerrarDescremacion, type CorridaDescremacion } from "../../services/procesos.service";

const control = "mt-1 w-full rounded-xl border border-slate-300 bg-white px-3 py-2.5";

export default function CierreDescremacion({ corrida, onCerrar, onCerrada }: {
  corrida: CorridaDescremacion;
  onCerrar: () => void;
  onCerrada: (corrida: CorridaDescremacion) => Promise<void>;
}) {
  const [ocupado, setOcupado] = useState(false);
  const [error, setError] = useState("");
  const [datos, setDatos] = useState({ litros_descremada: "", grasa_descremada: "", litros_crema: "", grasa_crema: "" });

  const guardar = async (evento: React.FormEvent) => {
    evento.preventDefault();
    setOcupado(true);
    setError("");
    try {
      const cerrada = await cerrarDescremacion(corrida.id, {
        litros_descremada: Number(datos.litros_descremada), grasa_descremada: Number(datos.grasa_descremada),
        litros_crema: Number(datos.litros_crema), grasa_crema: Number(datos.grasa_crema),
      });
      await onCerrada(cerrada);
    } catch (e) {
      setError(mensajeDe(e, "No se pudo cerrar la descremación."));
    } finally { setOcupado(false); }
  };

  return (
    <div className="fixed inset-0 z-[80] flex items-start justify-center overflow-y-auto bg-slate-950/45 p-4">
      <form onSubmit={guardar} className="my-8 w-full max-w-2xl rounded-2xl bg-white p-6 shadow-xl">
        <div className="flex items-center justify-between"><div><p className="text-xs font-semibold uppercase tracking-wide text-emerald-700">{corrida.ejecucion_codigo}</p><h2 className="mt-1 text-xl font-semibold">Cerrar descremación</h2></div><button type="button" onClick={onCerrar} className="rounded-lg p-2 hover:bg-slate-100"><X className="h-5 w-5" /></button></div>
        <p className="mt-3 text-sm text-slate-600">Entrada: {Number(corrida.litros_entrada).toLocaleString("es-CL")} L desde {corrida.silo_entera_codigo}.</p>
        <div className="mt-5 grid gap-4 sm:grid-cols-2">
          <Campo texto={`Litros a ${corrida.silo_descremada_codigo}`}><input required type="number" min="0.01" step="0.01" value={datos.litros_descremada} onChange={(e) => setDatos({ ...datos, litros_descremada: e.target.value })} className={control} /></Campo>
          <Campo texto="Grasa leche descremada (%)"><input required type="number" min="0" step="0.01" value={datos.grasa_descremada} onChange={(e) => setDatos({ ...datos, grasa_descremada: e.target.value })} className={control} /></Campo>
          <Campo texto={`Litros a ${corrida.estanque_crema_codigo}`}><input required type="number" min="0.01" step="0.01" value={datos.litros_crema} onChange={(e) => setDatos({ ...datos, litros_crema: e.target.value })} className={control} /></Campo>
          <Campo texto="Grasa crema (%)"><input required type="number" min="0" step="0.01" value={datos.grasa_crema} onChange={(e) => setDatos({ ...datos, grasa_crema: e.target.value })} className={control} /></Campo>
        </div>
        {error && <p className="mt-4 rounded-xl bg-rose-50 px-4 py-3 text-sm text-rose-700">{error}</p>}
        <div className="mt-6 flex justify-end gap-3"><button type="button" onClick={onCerrar} className="px-4 py-2.5 text-sm text-slate-600">Cancelar</button><button disabled={ocupado} className="rounded-xl bg-emerald-700 px-5 py-2.5 text-sm font-semibold text-white disabled:opacity-40">{ocupado ? "Cerrando…" : "Cerrar corrida"}</button></div>
      </form>
    </div>
  );
}

function Campo({ texto, children }: { texto: string; children: React.ReactNode }) {
  return <label className="text-sm text-slate-600">{texto}{children}</label>;
}
