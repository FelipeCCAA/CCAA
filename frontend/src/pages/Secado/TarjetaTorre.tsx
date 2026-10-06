import { Link } from "react-router-dom";

import { cantidad } from "../../services/formato";
import { accionDeTorre } from "../../services/puesto-secado";
import type { TorrePuesto } from "../../services/secado.service";

const ROTULO = { disponible: "Disponible", preparada: "Preparada", en_curso: "En curso" } as const;

/* Una tarjeta, un estado, una acción. Lo que dice lo decidió el servidor. */
export default function TarjetaTorre({ fila, ocupado, puedeOperar, onTomar, onIniciar, onCerrar }: {
  fila: TorrePuesto;
  ocupado: boolean;
  /* Quien no opera Secado (Calidad) ve el mismo estado, los mismos motivos
     y avisos, sin botones: ninguno le daría otra cosa que un 403. */
  puedeOperar: boolean;
  onTomar: (equipoId: number) => void;
  onIniciar: (corridaId: number) => void;
  onCerrar: (corridaId: number) => void;
}) {
  const accion = accionDeTorre(fila);
  const corrida = fila.corrida;
  const corridaId = corrida?.id ?? null;
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
        <button type="button" onClick={() => onTomar(fila.equipo_id)} className="rounded-xl bg-amber-700 px-4 py-3 text-sm font-semibold text-white hover:bg-amber-800">Tomar concentrado</button>
      )}
      {accion.tipo === "iniciar" && puedeOperar && corridaId !== null && (
        <button type="button" disabled={!accion.habilitada || ocupado} onClick={() => onIniciar(corridaId)} className="rounded-xl bg-amber-700 px-4 py-3 text-sm font-semibold text-white hover:bg-amber-800 disabled:opacity-40">
          {ocupado ? "Iniciando…" : "Iniciar secado"}
        </button>
      )}
      {accion.tipo === "cerrar" && puedeOperar && corridaId !== null && (
        <button type="button" disabled={!accion.habilitada} onClick={() => onCerrar(corridaId)} className="rounded-xl bg-green-700 px-4 py-3 text-sm font-semibold text-white hover:bg-green-800 disabled:opacity-40">Registrar balance y cerrar</button>
      )}
      {accion.motivo && (
        <p className="text-sm text-red-800">
          {accion.motivo}
          {fila.resolver_en && <>{" "}<Link to={fila.resolver_en} className="font-semibold underline">Ver dónde se resuelve</Link></>}
        </p>
      )}
      {fila.avisos.length > 0 && (
        <ul className="space-y-1 rounded-xl bg-amber-50 px-3 py-2 text-sm text-amber-900">
          {fila.avisos.map((aviso) => <li key={aviso}>{aviso}</li>)}
          {fila.falta_inspeccion && (
            <li><Link to="/registros" className="font-semibold underline">Registrar la inspección pre-operativa</Link></li>
          )}
        </ul>
      )}
    </article>
  );
}
