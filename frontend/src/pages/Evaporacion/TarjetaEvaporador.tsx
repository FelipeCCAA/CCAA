import { useId, useState } from "react";
import { Link } from "react-router-dom";

import ConfirmarAccion from "../../components/operacion/ConfirmarAccion";
import { puedeAccederModulo } from "../../services/access-control";
import { mensajeErrorProceso } from "../../services/errores-proceso";
import { cantidad } from "../../services/formato";
import type { EvaporadorPuesto } from "../../services/procesos.service";
import { accionDeEvaporador, corridaCancelable } from "../../services/puesto-evaporacion";
import { obtenerSesion } from "../../services/sesion";

const ROTULO = {
  disponible: "Disponible",
  preparada: "Preparada",
  en_curso: "En curso",
  esperando_calidad: "Esperando Calidad",
} as const;

/* Una tarjeta, un estado, una acción. Lo que dice lo decidió el servidor.
   Un evaporador preparado lleva además, en segundo plano, «Cancelar
   preparación», igual que la torre en Secado. */
export default function TarjetaEvaporador({ fila, ocupado, puedeOperar, onAbrir, onIniciar, onCerrar, onCancelar }: {
  fila: EvaporadorPuesto;
  ocupado: boolean;
  /* Quien no opera la evaporación ve el mismo estado, la misma
     corrida, el mismo "en Calidad" y el mismo motivo -son lectura-, pero
     ningún botón: ninguno le resultaría en algo distinto de un 403. */
  puedeOperar: boolean;
  onAbrir: (equipoId: number) => void;
  onIniciar: (corridaId: number) => void;
  onCerrar: (corridaId: number) => void;
  /* Rechaza si el servidor no cancela; la tarjeta muestra el motivo. */
  onCancelar: (corridaId: number, motivo: string) => Promise<void>;
}) {
  const accion = accionDeEvaporador(fila);
  const corrida = fila.corrida;
  const cancelable = corridaCancelable(fila);
  const idMotivoAccion = useId();
  const idMotivo = useId();
  const [cancelando, setCancelando] = useState<"no" | "motivo" | "confirmar">("no");
  const [motivo, setMotivo] = useState("");
  const [enviando, setEnviando] = useState(false);
  const [error, setError] = useState("");
  /* `en_calidad` nombra una corrida que quedó esperando a Calidad en esta
     misma máquina aunque la tarjeta esté mostrando otro estado -la máquina
     puede volver a ofrecerse para abrir mientras esa corrida sigue
     pendiente-. Se omite cuando el estado ya es "esperando_calidad": ahí
     `corrida` es esa misma corrida y repetirla sería redundante. */
  const mostrarEnCalidad = fila.en_calidad && fila.estado !== "esperando_calidad";
  /* "Ir a silos" solo cuando el motivo es justamente el silo de origen -lo
     dice el backend con `bloqueo_silo_origen`, no un adivine sobre el texto
     del motivo- y solo si el usuario puede entrar al módulo que lo analiza:
     un operador de Condensación sin acceso a Recepción se encontraría con
     «Acceso restringido» en vez de con el silo. */
  const puedeIrASilos = puedeAccederModulo(obtenerSesion()?.usuario, "recepcion");

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
        <h3 className="text-lg font-semibold text-slate-900">{fila.nombre}</h3>
        <span className="rounded-full bg-slate-100 px-3 py-1 text-xs font-semibold text-slate-800">{ROTULO[fila.estado]}</span>
      </header>
      {corrida && (
        <p className="text-sm text-slate-700">
          <span className="font-mono">{corrida.codigo}</span>{corrida.lote_codigo ? ` · lote ${corrida.lote_codigo}` : ""}
          <span className="block">{corrida.silo_origen} → {corrida.silo_destino} · {cantidad(corrida.litros_entrada, "L")}</span>
          {corrida.iniciada_en && <span className="block text-slate-600">Inició {new Date(corrida.iniciada_en).toLocaleString("es-CL")}</span>}
        </p>
      )}
      {mostrarEnCalidad && fila.en_calidad && (
        <p className="text-sm text-violet-800">
          En Calidad: <span className="font-mono">{fila.en_calidad.codigo}</span>
          {fila.en_calidad.lote_codigo ? ` · lote ${fila.en_calidad.lote_codigo}` : ""}
        </p>
      )}
      {accion.tipo === "abrir" && puedeOperar && (
        <button type="button" onClick={() => onAbrir(fila.equipo_id)} className="rounded-xl bg-blue-700 px-4 py-3 text-sm font-semibold text-white hover:bg-blue-800">Abrir lote desde vale</button>
      )}
      {accion.tipo === "iniciar" && corrida && (
        <>
          {puedeOperar && (
            <button
              type="button"
              disabled={!accion.habilitada || ocupado || cancelando !== "no"}
              aria-describedby={accion.motivo ? idMotivoAccion : undefined}
              onClick={() => onIniciar(corrida.id)}
              className="rounded-xl bg-blue-700 px-4 py-3 text-sm font-semibold text-white hover:bg-blue-800 disabled:opacity-40"
            >
              {ocupado ? "Iniciando…" : "Iniciar evaporación"}
            </button>
          )}
          {accion.motivo && (
            <p id={idMotivoAccion} className="text-sm text-amber-900">
              {accion.motivo}
              {fila.bloqueo_silo_origen && puedeIrASilos && (
                <>
                  {" "}
                  <Link to="/leche/silos" className="font-semibold underline">Analizar silo {fila.bloqueo_silo_origen}</Link>
                </>
              )}
            </p>
          )}
        </>
      )}
      {accion.tipo === "cerrar" && corrida && puedeOperar && (
        <button type="button" onClick={() => onCerrar(corrida.id)} className="rounded-xl bg-green-700 px-4 py-3 text-sm font-semibold text-white hover:bg-green-800">Registrar salida y cerrar</button>
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
          <textarea id={idMotivo} required value={motivo} onChange={(e) => setMotivo(e.target.value)} rows={2} className="w-full rounded-xl border border-slate-300 bg-white px-3 py-2 text-sm outline-none focus:border-blue-600" />
          <div className="flex flex-wrap gap-2">
            <button type="submit" disabled={!motivo.trim()} className="rounded-xl bg-slate-800 px-4 py-2 text-sm font-semibold text-white disabled:opacity-40">Revisar cancelación</button>
            <button type="button" onClick={soltar} className="rounded-xl border border-slate-300 bg-white px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-100">Volver</button>
          </div>
        </form>
      )}
      {cancelable !== null && puedeOperar && cancelando === "confirmar" && (
        <ConfirmarAccion
          titulo="Cancelar la preparación del evaporador"
          filas={[
            { etiqueta: "Evaporador", valor: fila.nombre },
            { etiqueta: "Lote", valor: corrida?.lote_codigo ?? "—" },
            { etiqueta: "Leche", valor: corrida ? `${cantidad(corrida.litros_entrada, "L")} de ${corrida.silo_origen}` : "—" },
            { etiqueta: "Motivo", valor: motivo.trim() },
          ]}
          advertencia="El lote se anula y la leche vuelve al silo del que salió, con un ingreso de devolución. Ese ingreso vence el análisis del silo para todos los evaporadores que se alimentan de él, no solo para este: habrá que repetirlo antes de iniciar cualquiera de ellos. El evaporador queda disponible."
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
