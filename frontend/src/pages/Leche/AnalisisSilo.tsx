import { useEffect, useState } from "react";
import { AlertTriangle, FlaskConical } from "lucide-react";

import {
  crearAnalisisSilo,
  listarAnalisisSilo,
  type AnalisisSilo as Analisis,
} from "../../services/recepcion.service";

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
  const [valores, setValores] = useState<Record<string, string>>({});
  const [error, setError] = useState("");
  const [guardando, setGuardando] = useState(false);

  useEffect(() => {
    let vigente = true;

    listarAnalisisSilo(siloId)
      .then((filas) => { if (vigente) setHistorial(filas); })
      .catch(() => { if (vigente) setError("No se pudo leer el historial de análisis."); });

    return () => { vigente = false; };
  }, [siloId]);

  async function guardar() {
    setGuardando(true);
    setError("");

    try {
      const datos: Record<string, unknown> = {
        silo: siloId,
        tomado_en: new Date().toISOString(),
      };
      for (const { clave } of PARAMETROS) {
        if (valores[clave]) datos[clave] = valores[clave];
      }

      await crearAnalisisSilo(datos);
      setValores({});
      setHistorial(await listarAnalisisSilo(siloId));
    } catch {
      setError("No se pudo guardar el análisis.");
    } finally {
      setGuardando(false);
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

      <div className="mt-4 grid grid-cols-2 gap-3 sm:grid-cols-4 xl:grid-cols-7">
        {PARAMETROS.map(({ clave, etiqueta }) => (
          <label key={clave} className="text-xs font-medium text-slate-600">
            {etiqueta}
            <input
              type="number"
              step="0.01"
              inputMode="decimal"
              value={valores[clave] ?? ""}
              onChange={(e) => setValores({ ...valores, [clave]: e.target.value })}
              className="mt-1 w-full rounded-xl border border-slate-200 px-3 py-2 text-sm tabular-nums text-slate-900"
            />
          </label>
        ))}
      </div>

      <div className="mt-4 flex flex-wrap items-center gap-3">
        <button
          type="button"
          onClick={() => void guardar()}
          disabled={guardando}
          className="rounded-xl bg-slate-900 px-4 py-2 text-sm font-medium text-white disabled:opacity-50"
        >
          {guardando ? "Guardando…" : "Registrar análisis"}
        </button>
        <p className="text-xs text-slate-600">
          La hora de la muestra la pone el servidor al registrar.
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
