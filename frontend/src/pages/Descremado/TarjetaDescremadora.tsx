import { useId } from "react";
import { Link } from "react-router-dom";

import { puedeAccederModulo } from "../../services/access-control";
import type { DescremadoraPuesto } from "../../services/descremado.service";
import { cantidad } from "../../services/formato";
import { accionDeDescremadora, corridaCancelable, moduloDeResolver } from "../../services/puesto-descremado";
import { obtenerSesion } from "../../services/sesion";

/* ¿Lleva el enlace a un módulo en el que el usuario puede entrar? Si no, se
   omite: «Acceso restringido» no resuelve nada. Condensación no entra a
   `/silos`; Calidad sí (Desviación 7). */
function puedeIr(ruta: string): boolean {
  const modulo = moduloDeResolver(ruta);
  return modulo !== null && puedeAccederModulo(obtenerSesion()?.usuario, modulo);
}

const ROTULO = { disponible: "Disponible", preparada: "Preparada", en_curso: "En curso" } as const;

/* Una tarjeta, un estado, una acción. Lo que dice lo decidió el servidor.
   Una descremadora preparada lleva además, en segundo plano, «Cancelar
   preparación», que confirma el puesto en un modal. */
export default function TarjetaDescremadora({ fila, ocupado, puedeOperar, onPreparar, onIniciar, onCerrar, onCancelar }: {
  fila: DescremadoraPuesto;
  ocupado: boolean;
  /* Quien no opera Descremación (Calidad) ve el mismo estado, motivos y
     avisos, sin botones: ninguno le daría otra cosa que un 403. */
  puedeOperar: boolean;
  onPreparar: (equipoId: number) => void;
  onIniciar: (corridaId: number) => void;
  onCerrar: (corridaId: number) => void;
  onCancelar: (fila: DescremadoraPuesto) => void;
}) {
  const accion = accionDeDescremadora(fila);
  const corrida = fila.corrida;
  const corridaId = corrida?.id ?? null;
  const cancelable = fila.estado === "preparada" ? corridaCancelable(corrida) : null;
  const idMotivo = useId();
  /* El botón deshabilitado anuncia por qué: el motivo visible lo describe. */
  const describe = accion.motivo ? idMotivo : undefined;
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
        <div className="space-y-1 text-sm text-slate-700">
          <p className="font-mono">{corrida.ejecucion_codigo}</p>
          {corrida.silo_entera && <p>Desde {corrida.silo_entera} · {cantidad(corrida.litros_entrada, "L")}</p>}
          {corrida.silo_descremada && <p>Descremada → {corrida.silo_descremada} · {cantidad(corrida.litros_descremada_plan, "L")}</p>}
          {corrida.estanque_crema && <p>Crema → {corrida.estanque_crema} · {cantidad(corrida.litros_crema_plan, "L")}</p>}
          {corrida.iniciada_en && <p className="text-slate-600">Inició {new Date(corrida.iniciada_en).toLocaleString("es-CL")}</p>}
        </div>
      )}
      {fila.en_calidad && (
        <p className="text-sm text-violet-800">
          {fila.en_calidad.tanques.length > 0 ? fila.en_calidad.tanques.join(" y ") : "Las salidas"} de{" "}
          <span className="font-mono">{fila.en_calidad.ejecucion_codigo}</span> esperando Calidad
        </p>
      )}
      {accion.tipo === "preparar" && puedeOperar && (
        <button type="button" disabled={!accion.habilitada} aria-describedby={describe} onClick={() => onPreparar(fila.equipo_id)} className="rounded-xl bg-emerald-700 px-4 py-3 text-sm font-semibold text-white hover:bg-emerald-800 disabled:opacity-40">Preparar descremado</button>
      )}
      {accion.tipo === "iniciar" && puedeOperar && corridaId !== null && (
        <button type="button" disabled={!accion.habilitada || ocupado} aria-describedby={describe} onClick={() => onIniciar(corridaId)} className="rounded-xl bg-emerald-700 px-4 py-3 text-sm font-semibold text-white hover:bg-emerald-800 disabled:opacity-40">
          {ocupado ? "Iniciando…" : "Iniciar descremado"}
        </button>
      )}
      {accion.tipo === "cerrar" && puedeOperar && corridaId !== null && (
        <button type="button" disabled={!accion.habilitada} aria-describedby={describe} onClick={() => onCerrar(corridaId)} className="rounded-xl bg-green-700 px-4 py-3 text-sm font-semibold text-white hover:bg-green-800 disabled:opacity-40">Registrar salidas y cerrar</button>
      )}
      {accion.motivo && (
        <p id={idMotivo} className="text-sm text-red-800">
          {accion.motivo}
          {fila.resolver_en && puedeIr(fila.resolver_en) && <>{" "}<Link to={fila.resolver_en} className="font-semibold underline">Ver dónde se resuelve</Link></>}
        </p>
      )}
      {fila.avisos.length > 0 && (
        <ul className="space-y-1 rounded-xl bg-amber-50 px-3 py-2 text-sm text-amber-900">
          {fila.avisos.map((aviso) => <li key={aviso}>{aviso}</li>)}
        </ul>
      )}
      {cancelable !== null && puedeOperar && (
        <button type="button" disabled={ocupado} onClick={() => onCancelar(fila)} className="self-start rounded-xl border border-slate-300 bg-white px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-100 disabled:opacity-40">Cancelar preparación</button>
      )}
    </article>
  );
}
