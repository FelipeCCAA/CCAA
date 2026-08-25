import { useEffect, useMemo, useState } from "react";
import { AlertTriangle, FlaskConical } from "lucide-react";

import {
  confirmarBorradorAnalisisSilo, crearBorradorAnalisisSilo,
  descartarBorradorAnalisisSilo, guardarBorradorAnalisisSilo,
  listarAnalisisSilo,
  obtenerBorradorAnalisisSilo,
  visualizarAnalisisSilo,
  type AnalisisSilo as Analisis,
} from "../../services/recepcion.service";
import { useBorrador } from "../../hooks/useBorrador";
import { mensajeDe } from "../../components/seccion/utilidades";

/*
  La captura del análisis del silo — `CCAA.REC.FORM.005.01`.

  Vive en la pantalla de silos y no en la del vale porque quien mide el silo
  es Recepción, al llenarlo; el vale lo consume después. Antes este dato no
  se guardaba en ninguna parte: el operador lo copiaba a mano del vale de
  papel a la Hoja RC, y de dónde salía ese «4,35» no quedaba escrito.

  La vigencia la decide el backend contra el libro de movimientos. Aquí solo
  se muestra: recalcularla en el cliente crearía una segunda implementación
  de la regla que decide con qué leche se estandariza.
*/

const PARAMETROS = [
  { clave: "ph", etiqueta: "pH" },
  { clave: "acidez", etiqueta: "Acidez (°Th)" },
  { clave: "grasa", etiqueta: "Grasa (%)" },
  { clave: "sng", etiqueta: "SNG (%)" },
  { clave: "proteina", etiqueta: "Proteína (%)" },
  { clave: "temperatura", etiqueta: "Temperatura (°C)" },
  { clave: "densidad", etiqueta: "Densidad (kg/m³)" },
] as const;

const horaActual = () => new Date().toTimeString().slice(0, 5);

const fechaHora = new Intl.DateTimeFormat("es-CL", {
  dateStyle: "short",
  timeStyle: "short",
});

interface Props {
  siloId: number;
  siloCodigo: string;
}

function AnalisisSiloPanel({ siloId, siloCodigo }: Props) {
  const [historial, setHistorial] = useState<Analisis[]>([]);
  const [valores, setValores] = useState<Record<string, string>>({
    metodo: "delvo_sp", hora_lectura: horaActual(),
  });
  const [error, setError] = useState("");
  const [guardando, setGuardando] = useState(false);
  const [tocado, setTocado] = useState(false);
  const [borradorPendiente, setBorradorPendiente] = useState<Analisis | null>(null);

  useEffect(() => {
    let vigente = true;

    listarAnalisisSilo(siloId)
      .then((filas) => { if (vigente) setHistorial(filas); })
      .catch(() => { if (vigente) setError("No se pudo leer el historial de análisis."); });
    obtenerBorradorAnalisisSilo(siloId)
      .then((borrador) => { if (vigente) setBorradorPendiente(borrador); })
      .catch(() => undefined);
    const reinicio = window.setTimeout(() => {
      setValores({ metodo: "delvo_sp", hora_lectura: horaActual() });
      setTocado(false);
    }, 0);

    return () => {
      vigente = false;
      window.clearTimeout(reinicio);
    };
  }, [siloId]);

  const datosBorrador = useMemo<Record<string, unknown>>(() => ({
    silo: siloId,
    ...Object.fromEntries(
      PARAMETROS.map(({ clave }) => [clave, valores[clave] || null]),
    ),
    inhibidores_resultado: valores.inhibidores_resultado || "",
    metodo: valores.metodo || "",
    hora_lectura: valores.hora_lectura || null,
    alcohol_75_conforme: valores.alcohol_75_conforme === "si" ? true : null,
    hervor_conforme: valores.hervor_conforme === "si" ? true : null,
    organoleptico_conforme: valores.organoleptico_conforme === "si" ? true : null,
  }), [siloId, valores]);

  const borrador = useBorrador({
    datos: datosBorrador,
    activo: tocado && borradorPendiente === null,
    crear: crearBorradorAnalisisSilo,
    actualizar: guardarBorradorAnalisisSilo,
    alError: () => setError("No se pudo autoguardar el análisis."),
  });

  const reanudar = (documento: Analisis) => {
    setValores(Object.fromEntries([
      ...PARAMETROS.map(({ clave }) => [clave, documento[clave] ?? ""]),
      ["inhibidores_resultado", documento.inhibidores_resultado],
      ["metodo", documento.metodo],
      ["hora_lectura", documento.hora_lectura?.slice(0, 5) ?? ""],
      ["alcohol_75_conforme", documento.alcohol_75_conforme ? "si" : ""],
      ["hervor_conforme", documento.hervor_conforme ? "si" : ""],
      ["organoleptico_conforme", documento.organoleptico_conforme ? "si" : ""],
    ]));
    borrador.reanudar(documento.id);
    setTocado(false);
    setBorradorPendiente(null);
  };

  async function guardar() {
    setGuardando(true);
    setError("");

    try {
      let borradorId = await borrador.guardarAhora({ propagarError: true });
      if (borradorId === null) {
        borradorId = (await crearBorradorAnalisisSilo(datosBorrador)).id;
      }
      await confirmarBorradorAnalisisSilo(borradorId);
      borrador.reiniciar();
      setValores({ metodo: "delvo_sp", hora_lectura: horaActual() });
      setTocado(false);
      setHistorial(await listarAnalisisSilo(siloId));
    } catch {
      setError("No se pudo guardar el análisis.");
    } finally {
      setGuardando(false);
    }
  }

  async function firmarVisualizacion(id: number) {
    setError("");
    try {
      await visualizarAnalisisSilo(id);
      setHistorial(await listarAnalisisSilo(siloId));
    } catch (fallo) {
      setError(mensajeDe(fallo, "No se pudo firmar la visualización."));
    }
  }

  const ultimo = historial[0];

  return (
    <section className="rounded-2xl border border-slate-200 bg-white px-6 py-5">

      <div className="flex items-center gap-3">
        <span className="rounded-xl bg-slate-100 p-2 text-slate-600">
          <FlaskConical className="h-4 w-4" strokeWidth={1.8} />
        </span>
        <div>
          <h2 className="font-semibold text-slate-900">Análisis de {siloCodigo}</h2>
          <p className="text-xs text-slate-600">
            Es la composición con la que se calcula el RC del vale.
          </p>
        </div>
      </div>

      {/* Un análisis vencido no se oculta: se muestra con el motivo. Que la
          leche cambió después de la muestra es justamente lo que el operador
          necesita saber antes de componer un vale con esos números. */}
      {ultimo && !ultimo.vigente && (
        <p className="mt-4 flex items-start gap-2 rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900">
          <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
          {ultimo.motivo_vigencia}
        </p>
      )}

      {borradorPendiente && (
        <div className="mt-4 rounded-xl border border-amber-200 bg-amber-50 px-4 py-4 text-sm text-amber-900">
          <strong>Análisis sin terminar.</strong> Puedes continuar los valores
          guardados o descartarlos; todavía no cuentan como muestra vigente.
          <div className="mt-3 flex flex-wrap gap-2">
            <button type="button" onClick={() => reanudar(borradorPendiente)} className="rounded-lg bg-amber-700 px-3 py-2 text-xs font-semibold text-white">Continuar</button>
            <button type="button" onClick={() => void descartarBorradorAnalisisSilo(borradorPendiente.id).then(() => setBorradorPendiente(null))} className="rounded-lg border border-amber-300 px-3 py-2 text-xs font-semibold">Descartar</button>
          </div>
        </div>
      )}

      <div
        className="mt-4 grid grid-cols-2 gap-3 sm:grid-cols-4 xl:grid-cols-7"
        onBlur={() => { if (tocado) void borrador.guardarAhora(); }}
      >
        {PARAMETROS.map(({ clave, etiqueta }) => (
          <label key={clave} className="text-xs font-medium text-slate-600">
            {etiqueta}
            <input
              type="number"
              step="0.01"
              inputMode="decimal"
              value={valores[clave] ?? ""}
              onChange={(e) => {
                setTocado(true);
                setValores({ ...valores, [clave]: e.target.value });
              }}
              disabled={borradorPendiente !== null}
              className="mt-1 w-full rounded-xl border border-slate-200 px-3 py-2 text-sm tabular-nums text-slate-900"
            />
          </label>
        ))}
      </div>

      <div className="mt-4 grid gap-3 sm:grid-cols-3">
        <label className="text-xs font-medium text-slate-600">
          Inhibidores
          <select value={valores.inhibidores_resultado ?? ""} onChange={(e) => { setTocado(true); setValores({ ...valores, inhibidores_resultado: e.target.value }); }} className="mt-1 w-full rounded-xl border border-slate-200 px-3 py-2 text-sm">
            <option value="">Seleccionar</option>
            <option value="negativo">Negativo</option>
            <option value="positivo">Positivo</option>
          </select>
        </label>
        <label className="text-xs font-medium text-slate-600">
          Método
          <select value={valores.metodo ?? "delvo_sp"} onChange={(e) => { setTocado(true); setValores({ ...valores, metodo: e.target.value }); }} className="mt-1 w-full rounded-xl border border-slate-200 px-3 py-2 text-sm">
            <option value="delvo_sp">Delvo SP</option>
            <option value="tri_sensor">Tri Sensor</option>
            <option value="charm">Charm</option>
          </select>
        </label>
        <label className="text-xs font-medium text-slate-600">
          Hora de lectura
          <input type="time" value={valores.hora_lectura ?? horaActual()} onChange={(e) => { setTocado(true); setValores({ ...valores, hora_lectura: e.target.value }); }} className="mt-1 w-full rounded-xl border border-slate-200 px-3 py-2 text-sm" />
        </label>
      </div>

      <fieldset className="mt-4 rounded-xl border border-slate-200 px-4 py-3">
        <legend className="px-1 text-xs font-semibold text-slate-700">Revalidación si la leche supera 48 h</legend>
        <div className="grid gap-2 sm:grid-cols-3">
          {[
            ["alcohol_75_conforme", "Alcohol 75°"],
            ["hervor_conforme", "Hervor"],
            ["organoleptico_conforme", "Organoléptico"],
          ].map(([clave, etiqueta]) => (
            <label key={clave} className="flex items-center gap-2 text-sm text-slate-700">
              <input type="checkbox" checked={valores[clave] === "si"} onChange={(e) => { setTocado(true); setValores({ ...valores, [clave]: e.target.checked ? "si" : "" }); }} />
              {etiqueta} conforme
            </label>
          ))}
        </div>
      </fieldset>

      <div className="mt-4 flex flex-wrap items-center gap-3">
        <button
          type="button"
          onClick={() => void guardar()}
          disabled={guardando || borradorPendiente !== null}
          className="rounded-xl bg-slate-900 px-4 py-2 text-sm font-medium text-white disabled:opacity-50"
        >
          {guardando ? "Confirmando…" : "Confirmar análisis"}
        </button>
        <p className="text-xs text-slate-600">
          {borrador.estado === "guardando" ? "Guardando borrador…" : borrador.id ? "Borrador guardado. La hora de muestra se fija al confirmar." : "La hora de la muestra la pone el servidor al confirmar."}
        </p>
      </div>

      {error && (
        <p className="mt-3 rounded-xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700">
          {error}
        </p>
      )}

      {historial.length > 0 && (
        <div className="mt-5 overflow-x-auto">
          <table className="w-full text-left text-sm">
            <thead className="text-xs uppercase tracking-wide text-slate-500">
              <tr>
                <th className="py-2 pr-4 font-medium">Muestra</th>
                <th className="py-2 pr-4 font-medium">Grasa</th>
                <th className="py-2 pr-4 font-medium">SNG</th>
                <th className="py-2 pr-4 font-medium">Vigencia</th>
                <th className="py-2 font-medium">Analista</th>
                <th className="py-2 font-medium">Inocuidad / firma</th>
              </tr>
            </thead>
            <tbody className="text-slate-700">
              {historial.map((fila) => (
                <tr key={fila.id} className="border-t border-slate-100">
                  <td className="py-2 pr-4 tabular-nums">
                    {fechaHora.format(new Date(fila.tomado_en))}
                  </td>
                  <td className="py-2 pr-4 tabular-nums">{fila.grasa ?? "—"}</td>
                  <td className="py-2 pr-4 tabular-nums">{fila.sng ?? "—"}</td>
                  <td className="py-2 pr-4">
                    {fila.vigente
                      ? <span className="text-emerald-700">Vigente</span>
                      : <span className="text-amber-800">{fila.motivo_vigencia}</span>}
                  </td>
                  <td className="py-2">{fila.analista_nombre || "—"}</td>
                  <td className="py-2">
                    {fila.apto_inocuidad ? "Apto" : "Pendiente"}
                    {fila.visualizado_por_nombre ? (
                      <span className="ml-2 text-emerald-700">
                        Visto por {fila.visualizado_por_nombre}
                      </span>
                    ) : (
                      <button
                        type="button"
                        onClick={() => void firmarVisualizacion(fila.id)}
                        className="ml-2 rounded-lg border border-slate-300 px-2 py-1 text-xs font-semibold"
                      >
                        Firmar visualización
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

    </section>
  );
}

export default AnalisisSiloPanel;
