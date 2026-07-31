import { useState } from "react";
import { X } from "lucide-react";
import axios from "axios";

import {
  crearBloque,
  EQUIPOS,
  ESTADO_EQUIPO,
  type CodigoProduccion,
  type Equipo,
} from "../../services/planificacion.service";


/*
  Alta de un bloque del programa.

  El bloque es un tramo de horas en un equipo, no una celda pintada: por eso
  se piden inicio y fin en vez de "cuántas casillas". Admite medias horas
  porque así se programa en planta.

  El solapamiento lo rechaza el servidor, que es quien ve los demás bloques
  del mismo equipo y día. Aquí solo se muestra su motivo.
*/

interface Props {
  semanaId: number;
  equipo: string;
  dia: number;
  horaInicio: number;
  codigos: CodigoProduccion[];
  alCerrar: () => void;
  alGuardar: () => void;
}


const claseCampo =
  "w-full rounded-xl border border-slate-200 px-3 py-2 text-sm text-slate-800 " +
  "focus:border-green-500 focus:outline-none";


function FormularioBloque({
  semanaId,
  equipo,
  dia,
  horaInicio,
  codigos,
  alCerrar,
  alGuardar,
}: Props) {

  const [tipo, setTipo] = useState<"produccion" | "estado">("produccion");
  const [inicio, setInicio] = useState(String(horaInicio));
  const [fin, setFin] = useState(String(Math.min(horaInicio + 4, 24)));
  const [codigo, setCodigo] = useState<string>("");
  const [estado, setEstado] = useState("A");
  const [kg, setKg] = useState("");
  const [observacion, setObservacion] = useState("");

  const [guardando, setGuardando] = useState(false);
  const [error, setError] = useState("");

  const nombreEquipo =
    EQUIPOS.find((e) => e.valor === equipo)?.etiqueta ?? equipo;

  const guardar = async () => {

    setError("");
    setGuardando(true);

    try {

      await crearBloque({
        semana: semanaId,
        equipo: equipo as Equipo,
        dia,
        hora_inicio: Number(inicio),
        hora_fin: Number(fin),
        tipo,
        codigo: tipo === "produccion" ? Number(codigo) || null : null,
        estado_equipo: tipo === "estado" ? estado : "",
        cantidad_kg: kg ? Number(kg) : null,
        observacion,
      });

      alGuardar();

    } catch (e) {

      if (axios.isAxiosError(e) && e.response?.data) {
        const datos = e.response.data as Record<string, string[] | string>;
        setError([...new Set(Object.values(datos).flat())].join(" "));
      } else {
        setError("No se pudo guardar el bloque.");
      }

    } finally {
      setGuardando(false);
    }
  };

  const listo =
    Number(fin) > Number(inicio) &&
    (tipo === "estado" || Boolean(codigo));

  return (
    <div className="fixed inset-0 z-50 flex items-start justify-center overflow-y-auto bg-slate-900/40 p-4">

      <div className="my-8 w-full max-w-lg rounded-2xl bg-white shadow-xl">

        <div className="flex items-start justify-between gap-4 border-b border-slate-200 px-6 py-5">

          <div>
            <h2 className="text-lg font-semibold text-slate-800">
              Programar bloque
            </h2>
            <p className="mt-0.5 text-sm text-slate-500">{nombreEquipo}</p>
          </div>

          <button
            type="button"
            onClick={alCerrar}
            aria-label="Cerrar"
            className="rounded-lg p-1 text-slate-400 hover:bg-slate-100 hover:text-slate-600"
          >
            <X className="h-5 w-5" />
          </button>

        </div>

        <div className="space-y-4 px-6 py-5">

          <div className="flex gap-2">
            {(["produccion", "estado"] as const).map((t) => (
              <button
                key={t}
                type="button"
                onClick={() => setTipo(t)}
                className={`flex-1 rounded-xl border px-4 py-2 text-sm font-medium ${
                  tipo === t
                    ? "border-green-500 bg-green-50 text-green-700"
                    : "border-slate-200 text-slate-600 hover:bg-slate-50"
                }`}
              >
                {t === "produccion" ? "Producción" : "Estado del equipo"}
              </button>
            ))}
          </div>

          <div className="grid grid-cols-2 gap-4">

            <div>
              <label className="mb-1 block text-xs font-medium text-slate-600">
                Hora de inicio
              </label>
              <input
                type="number"
                min="0"
                max="24"
                step="0.5"
                value={inicio}
                onChange={(e) => setInicio(e.target.value)}
                className={claseCampo}
              />
            </div>

            <div>
              <label className="mb-1 block text-xs font-medium text-slate-600">
                Hora de término
              </label>
              <input
                type="number"
                min="0"
                max="24"
                step="0.5"
                value={fin}
                onChange={(e) => setFin(e.target.value)}
                className={claseCampo}
              />
            </div>

          </div>

          {tipo === "produccion" ? (
            <>
              <div>
                <label className="mb-1 block text-xs font-medium text-slate-600">
                  Código de producción
                </label>
                <select
                  value={codigo}
                  onChange={(e) => setCodigo(e.target.value)}
                  className={claseCampo}
                >
                  <option value="">Elegir…</option>
                  {codigos.map((c) => (
                    <option key={c.id} value={c.id}>
                      {c.codigo} · {c.categoria_etiqueta} · {c.rendimiento_lh} L/h
                    </option>
                  ))}
                </select>

                {codigos.length === 0 && (
                  <p className="mt-1 text-xs text-amber-700">
                    No hay códigos cargados. Se cargan desde Administración.
                  </p>
                )}
              </div>

              <div>
                <label className="mb-1 block text-xs font-medium text-slate-600">
                  Kilos objetivo
                  <span className="ml-1 font-normal text-slate-400">opcional</span>
                </label>
                <input
                  type="number"
                  min="0"
                  value={kg}
                  onChange={(e) => setKg(e.target.value)}
                  className={claseCampo}
                />
              </div>
            </>
          ) : (
            <div>
              <label className="mb-1 block text-xs font-medium text-slate-600">
                Qué pasa en el equipo
              </label>
              <select
                value={estado}
                onChange={(e) => setEstado(e.target.value)}
                className={claseCampo}
              >
                {Object.entries(ESTADO_EQUIPO).map(([clave, meta]) => (
                  <option key={clave} value={clave}>
                    {clave} · {meta.etiqueta}
                  </option>
                ))}
              </select>
            </div>
          )}

          <div>
            <label className="mb-1 block text-xs font-medium text-slate-600">
              Observación
            </label>
            <textarea
              rows={2}
              value={observacion}
              onChange={(e) => setObservacion(e.target.value)}
              className={claseCampo}
            />
          </div>

          {tipo === "produccion" && (
            <p className="text-xs text-slate-500">
              Solo los evaporadores restan del balance de leche. Un bloque en
              una línea se programa igual, pero su leche ya la contó el
              evaporador que la alimenta.
            </p>
          )}

          {error && (
            <p className="rounded-xl bg-red-50 px-4 py-3 text-sm text-red-700">
              {error}
            </p>
          )}

        </div>

        <div className="flex justify-end gap-2 border-t border-slate-200 px-6 py-4">

          <button
            type="button"
            onClick={alCerrar}
            className="rounded-xl px-4 py-2 text-sm font-medium text-slate-600 hover:bg-slate-100"
          >
            Cancelar
          </button>

          <button
            type="button"
            disabled={guardando || !listo}
            onClick={() => void guardar()}
            className="rounded-xl bg-green-600 px-4 py-2 text-sm font-medium text-white hover:bg-green-700 disabled:opacity-50"
          >
            {guardando ? "Guardando…" : "Agregar bloque"}
          </button>

        </div>

      </div>

    </div>
  );
}


export default FormularioBloque;
