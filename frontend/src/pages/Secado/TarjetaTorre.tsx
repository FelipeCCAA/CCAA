import { useId, useState } from "react";
import { Link } from "react-router-dom";

import ConfirmarAccion from "../../components/operacion/ConfirmarAccion";
import { puedeAccederModulo } from "../../services/access-control";
import { mensajeErrorProceso } from "../../services/errores-proceso";
import { cantidad } from "../../services/formato";
import { accionDeTorre, corridaCancelable, moduloDeResolver } from "../../services/puesto-secado";
import type { TorrePuesto } from "../../services/secado.service";
import { obtenerSesion } from "../../services/sesion";

/* ¿Lleva el enlace a un módulo en el que el usuario puede entrar? Si no, se
   omite: «Acceso restringido» no resuelve nada (igual que «Analizar silo» en
   Evaporación). */
function puedeIr(ruta: string): boolean {
  const modulo = moduloDeResolver(ruta);
  return modulo !== null && puedeAccederModulo(obtenerSesion()?.usuario, modulo);
}

const ROTULO = { disponible: "Disponible", preparada: "Preparada", en_curso: "En curso" } as const;

/* Una tarjeta, un estado, una acción. Lo que dice lo decidió el servidor.
   Una torre preparada lleva además, en segundo plano, «Cancelar preparación». */
export default function TarjetaTorre({ fila, ocupado, puedeOperar, onTomar, onIniciar, onCerrar, onCancelar }: {
  fila: TorrePuesto;
  ocupado: boolean;
  /* Quien no opera Secado (Calidad) ve el mismo estado, los mismos motivos
     y avisos, sin botones: ninguno le daría otra cosa que un 403. */
  puedeOperar: boolean;
  onTomar: (equipoId: number) => void;
  onIniciar: (corridaId: number) => void;
  onCerrar: (corridaId: number) => void;
  /* Rechaza si el servidor no cancela; la tarjeta muestra el motivo. */
  onCancelar: (corridaId: number, motivo: string) => Promise<void>;
}) {
  const accion = accionDeTorre(fila);
  const corrida = fila.corrida;
  const corridaId = corrida?.id ?? null;
  const cancelable = corridaCancelable(fila);
  const idMotivo = useId();
  const idMotivoAccion = useId();
  /* El botón deshabilitado anuncia por qué: el motivo visible lo describe. */
  const describe = accion.motivo ? idMotivoAccion : undefined;
  const [cancelando, setCancelando] = useState<"no" | "motivo" | "confirmar">("no");
  const [motivo, setMotivo] = useState("");
  const [enviando, setEnviando] = useState(false);
  const [error, setError] = useState("");

  const soltar = () => {
    setCancelando("no");
    setMotivo("");
    setError("");
  };

  const confirmarCancelacion = async () => {
    if (cancelable === null || enviando) return;
    setEnviando(true);
    setError("");
    try {
      await onCancelar(cancelable, motivo.trim());
      soltar();
    } catch (causa) {
      setError(mensajeErrorProceso(causa, "No se pudo cancelar la preparación."));
    } finally {
      setEnviando(false);
    }
  };

  return (
    <article aria-label={fila.nombre} className="flex flex-col gap-3 rounded-2xl border border-slate-200 bg-white p-5">
      <header className="flex items-start justify-between gap-3">
        <div>
          <h3 className="text-lg font-semibold text-slate-900">{fila.nombre}</h3>
          <p className="font-mono text-xs text-slate-600">{fila.codigo}</p>
        </div>
        <span className="rounded-full bg-slate-100 px-3 py-1 text-xs font-semibold text-slate-800">{ROTULO[fila.estado]}</span>
      </header>
      {corrida && (
        <p className="text-sm text-slate-700">
          {corrida.lote_codigo
            ? <>Lote <span className="font-mono">{corrida.lote_codigo}</span></>
            : <span className="font-mono">{corrida.ejecucion_codigo}</span>}
          {corrida.origen && (
            <span className="block">Desde {corrida.origen} · {cantidad(corrida.cantidad, corrida.unidad ?? undefined)}</span>
          )}
          {corrida.iniciada_en && <span className="block text-slate-600">Inició {new Date(corrida.iniciada_en).toLocaleString("es-CL")}</span>}
        </p>
      )}
      {fila.en_calidad && (
        <p className="text-sm text-violet-800">Polvo de <span className="font-mono">{fila.en_calidad.lote_codigo}</span> esperando Calidad</p>
      )}
      {accion.tipo === "tomar" && puedeOperar && (
        <button type="button" disabled={!accion.habilitada} aria-describedby={describe} onClick={() => onTomar(fila.equipo_id)} className="rounded-xl bg-amber-700 px-4 py-3 text-sm font-semibold text-white hover:bg-amber-800 disabled:opacity-40">Tomar concentrado</button>
      )}
      {accion.tipo === "iniciar" && puedeOperar && corridaId !== null && (
        <button type="button" disabled={!accion.habilitada || ocupado || cancelando !== "no"} aria-describedby={describe} onClick={() => onIniciar(corridaId)} className="rounded-xl bg-amber-700 px-4 py-3 text-sm font-semibold text-white hover:bg-amber-800 disabled:opacity-40">
          {ocupado ? "Iniciando…" : "Iniciar secado"}
        </button>
      )}
      {accion.tipo === "cerrar" && puedeOperar && corridaId !== null && (
        <button type="button" disabled={!accion.habilitada} aria-describedby={describe} onClick={() => onCerrar(corridaId)} className="rounded-xl bg-green-700 px-4 py-3 text-sm font-semibold text-white hover:bg-green-800 disabled:opacity-40">Registrar balance y cerrar</button>
      )}
      {accion.motivo && (
        <p id={idMotivoAccion} className="text-sm text-red-800">
          {accion.motivo}
          {fila.resolver_en && puedeIr(fila.resolver_en) && <>{" "}<Link to={fila.resolver_en} className="font-semibold underline">Ver dónde se resuelve</Link></>}
        </p>
      )}
      {fila.avisos.length > 0 && (
        <ul className="space-y-1 rounded-xl bg-amber-50 px-3 py-2 text-sm text-amber-900">
          {fila.avisos.map((aviso) => <li key={aviso}>{aviso}</li>)}
          {fila.falta_inspeccion && puedeIr("/registros") && (
            <li><Link to="/registros" className="font-semibold underline">Registrar la inspección pre-operativa</Link></li>
          )}
        </ul>
      )}
      {cancelable !== null && puedeOperar && cancelando === "no" && (
        <button type="button" disabled={ocupado} onClick={() => setCancelando("motivo")} className="self-start rounded-xl border border-slate-300 bg-white px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-100 disabled:opacity-40">Cancelar preparación</button>
      )}
      {cancelable !== null && puedeOperar && cancelando === "motivo" && (
        <form
          onSubmit={(evento) => { evento.preventDefault(); if (motivo.trim()) setCancelando("confirmar"); }}
          className="space-y-2 rounded-xl border border-slate-200 bg-slate-50 p-3"
        >
          <label htmlFor={idMotivo} className="block text-sm font-medium text-slate-700">Motivo de la cancelación</label>
          <textarea id={idMotivo} required value={motivo} onChange={(e) => setMotivo(e.target.value)} rows={2} className="w-full rounded-xl border border-slate-300 bg-white px-3 py-2 text-sm outline-none focus:border-amber-600" />
          <div className="flex flex-wrap gap-2">
            <button type="submit" disabled={!motivo.trim()} className="rounded-xl bg-slate-800 px-4 py-2 text-sm font-semibold text-white disabled:opacity-40">Revisar cancelación</button>
            <button type="button" onClick={soltar} className="rounded-xl border border-slate-300 bg-white px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-100">Volver</button>
          </div>
        </form>
      )}
      {cancelable !== null && puedeOperar && cancelando === "confirmar" && (
        <ConfirmarAccion
          titulo="Cancelar la preparación de la torre"
          filas={[
            { etiqueta: "Torre", valor: fila.nombre },
            { etiqueta: "Lote", valor: corrida?.lote_codigo ?? "—" },
            { etiqueta: "Alimentación", valor: corrida?.origen ? `${corrida.origen} · ${cantidad(corrida.cantidad, corrida.unidad ?? undefined)}` : "—" },
            { etiqueta: "Motivo", valor: motivo.trim() },
          ]}
          advertencia="La torre queda disponible y el concentrado vuelve a ofrecerse con su saldo completo. Si la torre se alimentó desde bodega, la materia prima ya descontada no vuelve sola y el lote de salida se anula."
          textoConfirmar="Cancelar preparación"
          peligro
          ocupado={enviando}
          error={error}
          onConfirmar={() => void confirmarCancelacion()}
          onVolver={() => { setError(""); setCancelando("motivo"); }}
        />
      )}
    </article>
  );
}
