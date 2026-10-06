import { Link } from "react-router-dom";

import { cantidad } from "../../services/formato";
import type { EvaporadorPuesto } from "../../services/procesos.service";
import { accionDeEvaporador } from "../../services/puesto-evaporacion";

const ROTULO = {
  disponible: "Disponible",
  preparada: "Preparada",
  en_curso: "En curso",
  esperando_calidad: "Esperando Calidad",
} as const;

/* Una tarjeta, un estado, una acción. Lo que dice lo decidió el servidor. */
export default function TarjetaEvaporador({ fila, ocupado, onAbrir, onIniciar, onCerrar }: {
  fila: EvaporadorPuesto;
  ocupado: boolean;
  onAbrir: (equipoId: number) => void;
  onIniciar: (corridaId: number) => void;
  onCerrar: (corridaId: number) => void;
}) {
  const accion = accionDeEvaporador(fila);
  const corrida = fila.corrida;
  /* `en_calidad` nombra una corrida que quedó esperando a Calidad en esta
     misma máquina aunque la tarjeta esté mostrando otro estado -la máquina
     puede volver a ofrecerse para abrir mientras esa corrida sigue
     pendiente-. Se omite cuando el estado ya es "esperando_calidad": ahí
     `corrida` es esa misma corrida y repetirla sería redundante. */
  const mostrarEnCalidad = fila.en_calidad && fila.estado !== "esperando_calidad";
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
      {accion.tipo === "abrir" && (
        <button type="button" onClick={() => onAbrir(fila.equipo_id)} className="rounded-xl bg-blue-700 px-4 py-3 text-sm font-semibold text-white hover:bg-blue-800">Abrir lote desde vale</button>
      )}
      {accion.tipo === "iniciar" && corrida && (
        <>
          <button type="button" disabled={!accion.habilitada || ocupado} onClick={() => onIniciar(corrida.id)} className="rounded-xl bg-blue-700 px-4 py-3 text-sm font-semibold text-white hover:bg-blue-800 disabled:opacity-40">
            {ocupado ? "Iniciando…" : "Iniciar evaporación"}
          </button>
          {accion.motivo && (
            <p className="text-sm text-amber-900">
              {accion.motivo}{" "}
              <Link to="/silos" className="font-semibold underline">Ir a silos</Link>
            </p>
          )}
        </>
      )}
      {accion.tipo === "cerrar" && corrida && (
        <button type="button" onClick={() => onCerrar(corrida.id)} className="rounded-xl bg-green-700 px-4 py-3 text-sm font-semibold text-white hover:bg-green-800">Registrar salida y cerrar</button>
      )}
    </article>
  );
}
