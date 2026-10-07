import { useEffect, useId, useRef, useState, type ChangeEvent, type FormEvent, type ReactNode } from "react";
import { X } from "lucide-react";

import ConfirmarAccion from "../../components/operacion/ConfirmarAccion";
import {
  revisarCierreDescremado, type RevisionCierreDescremado, type ValoresCierreDescremado,
} from "../../services/descremado.service";
import { mensajeErrorProceso } from "../../services/errores-proceso";
import { cantidad } from "../../services/formato";
import { cerrarDescremacion, type CorridaDescremacion } from "../../services/procesos.service";
import { avisosDeCierre } from "../../services/puesto-descremado";

type Campos = Record<keyof ValoresCierreDescremado, string>;
const VACIO: Campos = { litros_descremada: "", grasa_descremada: "", litros_crema: "", grasa_crema: "" };
const control = "mt-1 w-full rounded-xl border border-slate-300 bg-white px-3 py-2.5 text-sm outline-none focus:border-emerald-600";

function aValores(campos: Campos): ValoresCierreDescremado {
  const numero = (texto: string) => (texto.trim() === "" ? null : Number(texto));
  return {
    litros_descremada: numero(campos.litros_descremada),
    grasa_descremada: numero(campos.grasa_descremada),
    litros_crema: numero(campos.litros_crema),
    grasa_crema: numero(campos.grasa_crema),
  };
}

/*
  «Registrar salidas y cerrar». Los avisos —límites de grasa y balance— los
  calcula el servidor mientras se teclea (`revisar-cierre/`, que no escribe),
  con la misma función que los guarda al cerrar. El cliente no calcula nada.
  Avisan: no deshabilitan el cierre.
*/
export default function CierreDescremado({ corrida, alCerrar, alCompletarse }: {
  corrida: CorridaDescremacion;
  alCerrar: () => void;
  alCompletarse: (corrida: CorridaDescremacion) => void;
}) {
  const [campos, setCampos] = useState<Campos>(VACIO);
  const [revision, setRevision] = useState<RevisionCierreDescremado | null>(null);
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
      revisarCierreDescremado(corrida.id, aValores(campos))
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

  const panel = avisosDeCierre({ revision, error: errorRevision, pendiente: revisionPendiente });
  const completo = Object.values(campos).every((valor) => valor.trim() !== "" && Number(valor) >= 0)
    && Number(campos.litros_descremada) > 0 && Number(campos.litros_crema) > 0;
  const cambiar = (clave: keyof Campos) => (evento: ChangeEvent<HTMLInputElement>) => {
    const valor = evento.target.value;
    setRevisionPendiente(true);
    setCampos((actual) => ({ ...actual, [clave]: valor }));
  };

  const revisar = (evento: FormEvent) => {
    evento.preventDefault();
    if (completo) setRevisando(true);
  };

  const confirmar = async () => {
    if (enviando.current) return;
    enviando.current = true;
    setGuardando(true);
    setError("");
    try {
      const cerrada = await cerrarDescremacion(corrida.id, {
        litros_descremada: Number(campos.litros_descremada),
        grasa_descremada: Number(campos.grasa_descremada),
        litros_crema: Number(campos.litros_crema),
        grasa_crema: Number(campos.grasa_crema),
      });
      alCompletarse(cerrada);
    } catch (causa) {
      setError(mensajeErrorProceso(causa, "No se pudo cerrar la descremación."));
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
            <p className="font-mono text-xs font-semibold text-emerald-700">{corrida.ejecucion_codigo}</p>
            <h2 id={idTitulo} className="mt-1 text-2xl font-bold text-slate-900">Registrar salidas</h2>
            <p className="mt-2 text-sm text-slate-600">Entrada: {cantidad(corrida.litros_entrada, "L")} desde {corrida.silo_entera_codigo} · {corrida.grasa_entrada} % MG.</p>
          </div>
          <button type="button" onClick={alCerrar} disabled={guardando} className="rounded-lg p-2 hover:bg-slate-100" aria-label="Cerrar"><X className="h-5 w-5" /></button>
        </div>
        <fieldset className="grid gap-4 sm:grid-cols-2" disabled={revisando}>
          <Campo texto={`Litros a ${corrida.silo_descremada_codigo}`}><input required type="number" min="0.01" step="0.01" value={campos.litros_descremada} onChange={cambiar("litros_descremada")} className={control} /></Campo>
          <Campo texto="Grasa leche descremada (%)"><input required type="number" min="0" step="0.001" value={campos.grasa_descremada} onChange={cambiar("grasa_descremada")} className={control} /></Campo>
          <Campo texto={`Litros a ${corrida.estanque_crema_codigo}`}><input required type="number" min="0.01" step="0.01" value={campos.litros_crema} onChange={cambiar("litros_crema")} className={control} /></Campo>
          <Campo texto="Grasa crema (%)"><input required type="number" min="0" step="0.001" value={campos.grasa_crema} onChange={cambiar("grasa_crema")} className={control} /></Campo>
        </fieldset>

        <section aria-label="Avisos del cierre" aria-live="polite" className={`rounded-xl px-4 py-3 text-sm ${panel.avisos.length || errorRevision ? "bg-amber-50 text-amber-900" : "bg-slate-50 text-slate-600"}`}>
          {panel.avisos.length > 0 && <ul className="space-y-1">{panel.avisos.map((aviso) => <li key={aviso}>{aviso}</li>)}</ul>}
          {panel.mensaje && <p>{panel.mensaje}</p>}
          {panel.vigente && revision?.merma_l && <p className="mt-1">Diferencia volumétrica: {cantidad(revision.merma_l, "L")}</p>}
        </section>

        {error && !revisando && <p role="alert" className="rounded-xl bg-red-50 px-4 py-3 text-sm text-red-800">{error}</p>}
        {revisando ? (
          <ConfirmarAccion
            titulo="Cerrar la descremación"
            filas={[
              { etiqueta: "Entrada", valor: `${corrida.silo_entera_codigo} · ${cantidad(corrida.litros_entrada, "L")}` },
              { etiqueta: "Leche descremada", valor: `${corrida.silo_descremada_codigo} · ${cantidad(campos.litros_descremada, "L")} · ${campos.grasa_descremada} % MG` },
              { etiqueta: "Crema", valor: `${corrida.estanque_crema_codigo} · ${cantidad(campos.litros_crema, "L")} · ${campos.grasa_crema} % MG` },
            ]}
            advertencia={panel.advertencia}
            textoConfirmar="Confirmar salidas y cerrar"
            ocupado={guardando}
            error={error}
            onConfirmar={() => void confirmar()}
            onVolver={() => setRevisando(false)}
          />
        ) : (
          <div className="flex justify-end gap-3">
            <button type="button" onClick={alCerrar} className="rounded-xl border border-slate-300 px-4 py-2.5 text-sm font-semibold text-slate-700">Cancelar</button>
            <button type="submit" disabled={!completo} className="rounded-xl bg-green-700 px-5 py-2.5 text-sm font-semibold text-white disabled:opacity-40">Revisar cierre</button>
          </div>
        )}
      </form>
    </div>
  );
}

function Campo({ texto, children }: { texto: string; children: ReactNode }) {
  return <label className="text-sm font-medium text-slate-700">{texto}{children}</label>;
}
