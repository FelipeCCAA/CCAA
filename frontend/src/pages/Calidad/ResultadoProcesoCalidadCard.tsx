import { describirRango } from "../../services/calidad-proceso";
import type {
  AnalisisLoteResultadoProceso,
  AnalisisSiloResultadoProceso,
  ResultadoProcesoCalidad,
} from "../../services/calidad.service";

const ETIQUETAS_PARAMETRO: Record<string, string> = {
  mg: "Grasa",
  grasa: "Grasa",
  sng: "SNG",
  st: "Sólidos totales",
  acidez: "Acidez",
  ph: "pH",
  humedad: "Humedad",
  temperatura: "Temperatura",
  proteina: "Proteína",
  pesoEsp: "Densidad",
  densidad: "Densidad",
};

const ESTADOS = {
  pendiente: { etiqueta: "Pendiente de Calidad", clase: "bg-amber-100 text-amber-900" },
  liberado: { etiqueta: "Liberada", clase: "bg-emerald-100 text-emerald-800" },
  rechazado: { etiqueta: "Rechazada", clase: "bg-red-100 text-red-800" },
};

type Accion = "liberar" | "rechazar" | null;

interface Props {
  item: ResultadoProcesoCalidad;
  analisisId: string;
  observacion: string;
  motivo: string;
  rechazando: boolean;
  accion: Accion;
  puedeDecidir: boolean;
  alElegirAnalisis: (valor: string) => void;
  alCambiarObservacion: (valor: string) => void;
  alCambiarMotivo: (valor: string) => void;
  alAbrirRechazo: () => void;
  alCancelarRechazo: () => void;
  alLiberar: () => void;
  alRechazar: () => void;
}

function valoresAnalisisLote(analisis: AnalisisLoteResultadoProceso) {
  return Object.entries(analisis.valores);
}

function valoresAnalisisSilo(analisis: AnalisisSiloResultadoProceso) {
  return [
    ["ph", analisis.ph],
    ["acidez", analisis.acidez],
    ["grasa", analisis.grasa],
    ["sng", analisis.sng],
    ["proteina", analisis.proteina],
    ["densidad", analisis.densidad],
  ].filter(([, valor]) => valor !== null);
}

export default function ResultadoProcesoCalidadCard({
  item,
  analisisId,
  observacion,
  motivo,
  rechazando,
  accion,
  puedeDecidir,
  alElegirAnalisis,
  alCambiarObservacion,
  alCambiarMotivo,
  alAbrirRechazo,
  alCancelarRechazo,
  alLiberar,
  alRechazar,
}: Props) {
  const seleccionado = item.analisis_disponibles.find(
    (analisis) => analisis.id === Number(analisisId),
  );
  const puedeLiberar = seleccionado
    && (seleccionado.resultado === null || seleccionado.resultado === "conforme");
  const estado = ESTADOS[item.estado];
  const esMantequilla = item.analisis_tipo === "lote";

  return (
    <article className={`rounded-xl border p-4 ${esMantequilla ? "border-violet-200 bg-violet-50/40" : "border-amber-200 bg-amber-50/40"}`}>
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="font-semibold text-slate-900">{item.lote_codigo} · {item.corrida_codigo}</p>
          <p className="mt-1 text-sm text-slate-700">{item.producto_nombre} · {Number(item.cantidad).toLocaleString("es-CL")} {item.unidad}</p>
          <p className="mt-1 text-xs text-slate-500">
            {item.equipo_nombre || "Sin equipo"}
            {item.silo_destino_codigo ? ` → ${item.silo_destino_codigo}` : " · producto a granel"}
          </p>
        </div>
        <span className={`rounded-full px-2.5 py-1 text-xs font-semibold ${estado.clase}`}>
          {estado.etiqueta}
        </span>
      </div>

      <div className="mt-3 grid gap-3 md:grid-cols-2">
        {item.especificacion ? (
          <div className="rounded-lg border border-emerald-200 bg-white p-3">
            <p className="text-xs font-semibold text-emerald-800">Rangos de referencia · versión {item.especificacion.version}</p>
            <dl className="mt-2 space-y-1.5 text-xs text-slate-700">
              {Object.entries(item.especificacion.rangos).map(([clave, rango]) => (
                <div key={clave} className="flex justify-between gap-3">
                  <dt className="font-medium">{ETIQUETAS_PARAMETRO[clave] ?? clave}</dt>
                  <dd className="text-right">{describirRango(rango)}</dd>
                </div>
              ))}
            </dl>
          </div>
        ) : (
          <p className="rounded-lg bg-red-50 p-3 text-sm font-medium text-red-800">
            No existe una especificación vigente para comparar este resultado.
          </p>
        )}

        <div className="rounded-lg border border-slate-200 bg-white p-3">
          <p className="text-xs font-semibold text-slate-700">
            {esMantequilla ? "Resultado del análisis de lote" : "Resultado del análisis de silo"}
          </p>
          {!seleccionado ? (
            <p className="mt-2 text-xs text-slate-500">Selecciona un análisis para ver sus resultados junto a los rangos.</p>
          ) : (
            <div className="mt-2 flex flex-wrap gap-1.5">
              {(item.analisis_tipo === "lote"
                ? valoresAnalisisLote(seleccionado as AnalisisLoteResultadoProceso)
                : valoresAnalisisSilo(seleccionado as AnalisisSiloResultadoProceso)
              ).map(([clave, valor]) => (
                <span key={String(clave)} className="rounded-full bg-slate-100 px-2 py-1 text-xs text-slate-700">
                  {ETIQUETAS_PARAMETRO[String(clave)] ?? String(clave)}: {String(valor)}
                </span>
              ))}
            </div>
          )}
        </div>
      </div>

      {item.estado === "pendiente" && (
        <>
          {item.analisis_disponibles.length === 0 ? (
            <p className="mt-3 rounded-lg bg-amber-100 px-3 py-2 text-sm text-amber-900">
              {esMantequilla
                ? `Falta registrar un análisis de lote para ${item.lote_codigo}. No se solicita silo.`
                : "Falta un análisis de silo confirmado y posterior al cierre de la corrida."}
            </p>
          ) : (
            <label className="mt-3 block text-sm font-medium text-slate-700">
              {esMantequilla ? "Análisis del lote de mantequilla" : "Análisis confirmado del silo"}
              <select value={analisisId} onChange={(evento) => alElegirAnalisis(evento.target.value)} className="mt-1 w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm">
                <option value="">Seleccionar análisis…</option>
                {item.analisis_tipo === "lote"
                  ? item.analisis_disponibles.map((analisis) => (
                    <option key={analisis.id} value={analisis.id}>
                      {analisis.fecha} · {analisis.muestra || "muestra de lote"} · {analisis.resultado?.replaceAll("_", " ") ?? "sin evaluación"}
                    </option>
                  ))
                  : item.analisis_disponibles.map((analisis) => (
                    <option key={analisis.id} value={analisis.id}>
                      {new Date(analisis.tomado_en).toLocaleString("es-CL")} · grasa {analisis.grasa ?? "—"} · SNG {analisis.sng ?? "—"} · {analisis.resultado?.replaceAll("_", " ") ?? "control firmado"}
                    </option>
                  ))}
              </select>
            </label>
          )}

          {seleccionado?.resultado === "sin_analisis" && (
            <p className="mt-2 text-sm text-red-700">Faltan parámetros obligatorios: {seleccionado.faltantes.map((clave) => ETIQUETAS_PARAMETRO[clave] ?? clave).join(", ")}.</p>
          )}
          {seleccionado?.resultado === "no_conforme" && (
            <div className="mt-2 text-sm text-red-700">
              {seleccionado.desviaciones.map((desvio) => (
                <p key={desvio.parametro}>{ETIQUETAS_PARAMETRO[desvio.parametro] ?? desvio.parametro}: {desvio.valor ?? "—"} fuera de {desvio.min ?? "—"} a {desvio.max ?? "—"}.</p>
              ))}
            </div>
          )}

          {puedeDecidir && !rechazando && (
            <div className="mt-3 space-y-3">
              {esMantequilla && (
                <label className="block text-xs font-semibold text-slate-600">
                  Observación de liberación
                  <input value={observacion} onChange={(evento) => alCambiarObservacion(evento.target.value)} placeholder="Resultado conforme" className="mt-1 w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm font-normal" />
                </label>
              )}
              <div className="flex flex-wrap gap-2">
                <button type="button" disabled={!puedeLiberar || accion !== null} onClick={alLiberar} className="rounded-lg bg-emerald-700 px-3 py-2 text-xs font-semibold text-white disabled:opacity-40">
                  {accion === "liberar" ? "Liberando…" : esMantequilla ? "Liberar para Envasado" : "Liberar etapa"}
                </button>
                <button type="button" disabled={accion !== null} onClick={alAbrirRechazo} className="rounded-lg bg-red-50 px-3 py-2 text-xs font-semibold text-red-700 disabled:opacity-40">Rechazar</button>
              </div>
            </div>
          )}

          {puedeDecidir && rechazando && (
            <div className="mt-3 rounded-lg border border-red-200 bg-white p-3">
              <label className="text-xs font-semibold text-slate-700">
                Motivo del rechazo
                <textarea required value={motivo} onChange={(evento) => alCambiarMotivo(evento.target.value)} className="mt-1 min-h-20 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm font-normal" />
              </label>
              <div className="mt-2 flex justify-end gap-2">
                <button type="button" disabled={accion !== null} onClick={alCancelarRechazo} className="px-3 py-2 text-xs text-slate-600">Cancelar</button>
                <button type="button" disabled={!motivo.trim() || accion !== null} onClick={alRechazar} className="rounded-lg bg-red-700 px-3 py-2 text-xs font-semibold text-white disabled:opacity-40">{accion === "rechazar" ? "Rechazando…" : "Confirmar rechazo"}</button>
              </div>
            </div>
          )}
        </>
      )}

      {item.estado !== "pendiente" && item.observacion && (
        <p className="mt-3 rounded-lg bg-white px-3 py-2 text-xs text-slate-600">{item.observacion}</p>
      )}
    </article>
  );
}
