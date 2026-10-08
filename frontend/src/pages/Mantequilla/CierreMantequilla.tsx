import { useEffect, useId, useRef, useState, type ChangeEvent, type FormEvent, type ReactNode } from "react";
import { X } from "lucide-react";

import ConfirmarAccion from "../../components/operacion/ConfirmarAccion";
import { mensajeErrorProceso } from "../../services/errores-proceso";
import { cantidad } from "../../services/formato";
import {
  cerrarMantequilla, revisarCierreMantequilla,
  type RevisionCierreMantequilla, type ValoresCierreMantequilla,
} from "../../services/mantequilla.service";
import type { CorridaMantequilla } from "../../services/procesos.service";
import { estadoDelBalance } from "../../services/puesto-mantequilla";

type Campos = {
  mantequilla: string; suero: string; merma: string; reproceso: string;
  motivoReproceso: string; humedad: string;
};
const VACIO: Campos = { mantequilla: "", suero: "", merma: "", reproceso: "", motivoReproceso: "", humedad: "" };
const control = "mt-1 w-full rounded-xl border border-slate-300 bg-white px-3 py-2.5 text-sm outline-none focus:border-amber-600";
const FRANJA = {
  completo: "bg-emerald-50 text-emerald-900",
  incompleto: "bg-amber-50 text-amber-900",
  excedido: "bg-rose-50 text-rose-800",
  revisando: "bg-slate-50 text-slate-600",
  sin_revision: "bg-slate-50 text-slate-600",
} as const;

function aValores(campos: Campos): ValoresCierreMantequilla {
  const numero = (texto: string) => (texto.trim() === "" ? null : Number(texto));
  return {
    kg_mantequilla: numero(campos.mantequilla),
    kg_suero: numero(campos.suero),
    kg_merma: numero(campos.merma),
    kg_reproceso: numero(campos.reproceso),
    motivo_reproceso: campos.motivoReproceso.trim(),
  };
}

/*
  «Registrar balance y cerrar». El balance lo decide el servidor mientras se
  teclea (`revisar-cierre/`, que no escribe) con la misma función que valida
  el cierre (`balance_mantequilla`). El cliente no calcula nada: «Revisar
  cierre» se habilita solo con la última revisión de los valores actuales,
  que cuadra y no trae errores.
*/
export default function CierreMantequilla({ corrida, alCerrar, alCompletarse }: {
  corrida: CorridaMantequilla;
  alCerrar: () => void;
  alCompletarse: (corrida: CorridaMantequilla) => void;
}) {
  const [campos, setCampos] = useState<Campos>(VACIO);
  const [revision, setRevision] = useState<RevisionCierreMantequilla | null>(null);
  // Pendiente desde la tecla hasta que responde la revisión de lo tecleado:
  // mientras tanto, la anterior ya no habla de lo que se va a cerrar.
  const [revisionPendiente, setRevisionPendiente] = useState(true);
  const [errorRevision, setErrorRevision] = useState(false);
  const [revisando, setRevisando] = useState(false);
  const [guardando, setGuardando] = useState(false);
  const [error, setError] = useState("");
  const enviando = useRef(false);
  const idTitulo = useId();

  useEffect(() => {
    let vigente = true;
    // Con retardo: una consulta por pausa al teclear, no una por tecla.
    const tarea = window.setTimeout(() => {
      revisarCierreMantequilla(corrida.id, aValores(campos))
        .then((datos) => {
          if (!vigente) return;
          setRevision(datos);
          setErrorRevision(false);
          setRevisionPendiente(false);
        })
        .catch(() => {
          if (!vigente) return;
          setRevision(null);
          setErrorRevision(true);
          setRevisionPendiente(false);
        });
    }, 400);
    return () => { vigente = false; window.clearTimeout(tarea); };
  }, [corrida.id, campos]);

  const balance = estadoDelBalance(revision, revisionPendiente, errorRevision);
  const conReproceso = Number(campos.reproceso || 0) > 0;
  const cambiar = (clave: keyof Campos) => (evento: ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) => {
    const valor = evento.target.value;
    setRevisionPendiente(true);
    setCampos((actual) => ({ ...actual, [clave]: valor }));
  };

  const revisar = (evento: FormEvent) => {
    evento.preventDefault();
    if (balance.puedeCerrar) setRevisando(true);
  };

  const confirmar = async () => {
    if (enviando.current) return;
    enviando.current = true;
    setGuardando(true);
    setError("");
    try {
      const cerrada = await cerrarMantequilla(corrida.id, {
        kg_mantequilla: Number(campos.mantequilla),
        kg_suero: Number(campos.suero || 0),
        kg_merma: Number(campos.merma || 0),
        kg_reproceso: Number(campos.reproceso || 0),
        motivo_reproceso: campos.motivoReproceso.trim(),
        controles: campos.humedad ? { humedad: Number(campos.humedad) } : {},
      });
      alCompletarse(cerrada);
    } catch (causa) {
      setError(mensajeErrorProceso(causa, "No se pudo cerrar la corrida de mantequilla."));
      setRevisando(false);
    } finally {
      enviando.current = false;
      setGuardando(false);
    }
  };

  return (
    <div className="fixed inset-0 z-[70] overflow-y-auto bg-slate-950/45 p-4" role="dialog" aria-modal="true" aria-labelledby={idTitulo}>
      <form onSubmit={revisar} className="mx-auto my-8 max-w-2xl space-y-5 rounded-2xl bg-white p-6 shadow-xl">
        <div className="flex items-start justify-between gap-4">
          <div>
            <p className="font-mono text-xs font-semibold text-amber-700">{corrida.ejecucion_codigo}</p>
            <h2 id={idTitulo} className="mt-1 text-2xl font-bold text-slate-900">Registrar balance y cerrar</h2>
            <p className="mt-2 text-sm text-slate-600">Crema {corrida.crema_codigo} · {cantidad(corrida.kg_crema, "kg")} → lote {corrida.mantequilla_codigo}.</p>
          </div>
          <button type="button" onClick={alCerrar} disabled={guardando} className="rounded-lg p-2 hover:bg-slate-100" aria-label="Cerrar"><X className="h-5 w-5" /></button>
        </div>
        <fieldset className="grid gap-4 sm:grid-cols-2" disabled={revisando}>
          <Campo texto="Mantequilla producida (kg)"><input required type="number" min="0.001" step="0.001" value={campos.mantequilla} onChange={cambiar("mantequilla")} className={control} /></Campo>
          <Campo texto="Suero / mazada recuperada (kg)">
            <input type="number" min="0" step="0.001" disabled={!corrida.lote_suero} value={campos.suero} onChange={cambiar("suero")} className={`${control} disabled:bg-slate-100 disabled:text-slate-500`} />
            {!corrida.lote_suero && <span className="mt-1 block text-xs font-normal text-slate-600">Esta corrida no tiene un lote de suero asociado: registra 0 kg.</span>}
          </Campo>
          <Campo texto="Merma medida (kg)"><input type="number" min="0" step="0.001" value={campos.merma} onChange={cambiar("merma")} className={control} /></Campo>
          <Campo texto="Material segregado para reproceso (kg)"><input type="number" min="0" step="0.001" value={campos.reproceso} onChange={cambiar("reproceso")} className={control} /></Campo>
          {conReproceso && (
            <label className="text-sm font-medium text-slate-700 sm:col-span-2">
              Motivo del reproceso
              <textarea required maxLength={250} rows={3} value={campos.motivoReproceso} onChange={cambiar("motivoReproceso")} className={control} placeholder="Ej.: textura fuera de objetivo; segregar para evaluación de Calidad" />
              <span className="mt-1 block text-xs font-normal text-slate-500">Se creará un lote separado y pendiente de la decisión de Calidad.</span>
            </label>
          )}
          <Campo texto="Humedad (%)"><input type="number" min="0" max="100" step="0.01" value={campos.humedad} onChange={cambiar("humedad")} className={control} /></Campo>
        </fieldset>

        <section aria-label="Balance del cierre" aria-live="polite" className={`rounded-xl px-4 py-3 text-sm ${FRANJA[balance.franja]}`}>
          <p className="font-semibold">{balance.titulo}</p>
          {balance.detalle && <p className="mt-1">{balance.detalle}</p>}
          {balance.errores.length > 0 && <ul className="mt-1 space-y-1">{balance.errores.map((texto) => <li key={texto}>{texto}</li>)}</ul>}
        </section>

        {error && !revisando && <p role="alert" className="rounded-xl bg-red-50 px-4 py-3 text-sm text-red-800">{error}</p>}
        {revisando ? (
          <ConfirmarAccion
            titulo="Cerrar la corrida de mantequilla"
            filas={[
              { etiqueta: "Crema", valor: `${corrida.crema_codigo} · ${cantidad(corrida.kg_crema, "kg")}` },
              { etiqueta: "Mantequilla", valor: `${corrida.mantequilla_codigo} · ${cantidad(campos.mantequilla, "kg")}` },
              { etiqueta: "Suero / mazada", valor: cantidad(campos.suero || 0, "kg") },
              { etiqueta: "Merma", valor: cantidad(campos.merma || 0, "kg") },
              { etiqueta: "Reproceso", valor: conReproceso ? `${cantidad(campos.reproceso, "kg")} · ${campos.motivoReproceso.trim()}` : "Sin reproceso" },
            ]}
            advertencia="La mantequilla queda pendiente de Calidad y el lote se declara producido: se descuenta su material de envase."
            textoConfirmar="Cerrar y enviar a Calidad"
            ocupado={guardando}
            error={error}
            onConfirmar={() => void confirmar()}
            onVolver={() => setRevisando(false)}
          />
        ) : (
          <div className="flex justify-end gap-3">
            <button type="button" onClick={alCerrar} className="rounded-xl border border-slate-300 px-4 py-2.5 text-sm font-semibold text-slate-700">Cancelar</button>
            <button type="submit" disabled={!balance.puedeCerrar} className="rounded-xl bg-green-700 px-5 py-2.5 text-sm font-semibold text-white disabled:opacity-40">Revisar cierre</button>
          </div>
        )}
      </form>
    </div>
  );
}

function Campo({ texto, children }: { texto: string; children: ReactNode }) {
  return <label className="text-sm font-medium text-slate-700">{texto}{children}</label>;
}
