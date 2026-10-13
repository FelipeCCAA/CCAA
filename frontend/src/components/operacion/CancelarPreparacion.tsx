import { useId, useState, type FormEvent } from "react";

import ConfirmarAccion from "./ConfirmarAccion";
import { mensajeErrorProceso } from "../../services/errores-proceso";

/*
  Motivo y confirmación para soltar una preparación. Lo abren la tarjeta y el
  historial de Descremado y de Mantequilla, con la misma regla
  (`corridaCancelable`); cada puesto dice qué se suelta (`advertencia`).
*/
export default function CancelarPreparacion({ codigo, filas, advertencia, maxLength, alVolver, alCancelar }: {
  codigo: string;
  filas: { etiqueta: string; valor: string }[];
  /* Qué se suelta al cancelar: lo dice cada puesto. */
  advertencia: string;
  /* El largo que el servidor acepta para el motivo, si lo limita (Mantequilla: `motivo_anulacion`, 250). */
  maxLength?: number;
  alVolver: () => void;
  /* Rechaza si el servidor no cancela; el modal muestra el motivo. */
  alCancelar: (motivo: string) => Promise<void>;
}) {
  const [motivo, setMotivo] = useState("");
  const [confirmando, setConfirmando] = useState(false);
  const [enviando, setEnviando] = useState(false);
  const [error, setError] = useState("");
  const idTitulo = useId();
  const idMotivo = useId();

  const revisar = (evento: FormEvent) => {
    evento.preventDefault();
    if (motivo.trim()) setConfirmando(true);
  };

  const confirmar = async () => {
    if (enviando) return;
    setEnviando(true);
    setError("");
    try {
      await alCancelar(motivo.trim());
    } catch (causa) {
      setError(mensajeErrorProceso(causa, "No se pudo cancelar la preparación."));
    } finally {
      setEnviando(false);
    }
  };

  return (
    <div className="fixed inset-0 z-[70] overflow-y-auto bg-slate-950/45 p-4" role="dialog" aria-modal="true" aria-labelledby={idTitulo}>
      <div className="mx-auto my-8 max-w-xl space-y-4 rounded-2xl bg-white p-6 shadow-xl">
        <h2 id={idTitulo} className="text-xl font-bold text-slate-900">Cancelar la preparación {codigo}</h2>
        {confirmando ? (
          <ConfirmarAccion
            titulo="Cancelar la preparación"
            filas={[...filas, { etiqueta: "Motivo", valor: motivo.trim() }]}
            advertencia={advertencia}
            textoConfirmar="Cancelar preparación"
            peligro
            ocupado={enviando}
            error={error}
            onConfirmar={() => void confirmar()}
            onVolver={() => { setError(""); setConfirmando(false); }}
          />
        ) : (
          <form onSubmit={revisar} className="space-y-3">
            <label htmlFor={idMotivo} className="block text-sm font-medium text-slate-700">Motivo de la cancelación</label>
            <textarea id={idMotivo} required maxLength={maxLength} value={motivo} onChange={(e) => setMotivo(e.target.value)} rows={3} className="w-full rounded-xl border border-slate-300 bg-white px-3 py-2 text-sm outline-none focus:border-emerald-600" />
            <div className="flex flex-wrap justify-end gap-2">
              <button type="button" onClick={alVolver} className="rounded-xl border border-slate-300 bg-white px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-100">Volver</button>
              <button type="submit" disabled={!motivo.trim()} className="rounded-xl bg-slate-800 px-4 py-2 text-sm font-semibold text-white disabled:opacity-40">Revisar cancelación</button>
            </div>
          </form>
        )}
      </div>
    </div>
  );
}
