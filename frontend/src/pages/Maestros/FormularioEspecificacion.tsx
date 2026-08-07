import { useState } from "react";
import { AlertTriangle, X } from "lucide-react";

import type {
  Especificacion,
  NuevaEspecificacion,
  Rango,
} from "../../services/maestros.service";
import type { ProductoMaestro } from "../../services/maestros.service";
import type { Parametro } from "../../services/produccion.service";

/*
  Los rangos de calidad de un producto.

  **No es un editor de JSON.** `rangos` se guarda como JSON, pero el formulario
  dibuja una fila por parámetro del catálogo que sirve el backend: así no hay
  forma de escribir una clave que `Especificacion.clean()` rechaza, ni de
  equivocarse en la forma del objeto. Un textarea de JSON aquí trasladaría a
  Calidad un problema de sintaxis en el maestro que decide qué sale conforme.

  Un parámetro **no marcado no se guarda**: la especificación solo declara lo
  que exige. Y uno marcado sin mínimo ni máximo no exige nada —el formulario lo
  avisa antes de guardar, porque en el veredicto se leería como un parámetro
  cubierto que no cubre nada.
*/

type Modo = "nueva" | "editar" | "version";

const TEXTO: Record<Modo, { titulo: string; boton: string }> = {
  nueva: { titulo: "Nueva especificación", boton: "Crear especificación" },
  editar: { titulo: "Editar especificación", boton: "Guardar cambios" },
  version: { titulo: "Nueva versión", boton: "Crear versión" },
};

const hoy = () => new Date().toISOString().slice(0, 10);


/*
  Por qué falló el guardado, dicho de forma que se pueda actuar.

  **Separa «el servidor lo rechazó» de «no llegué al servidor»**, y no es una
  distinción de manual: le pasó a Felipe con su servidor de pruebas caído y el
  mensaje decía «no se pudo guardar la especificación», que suena a que los
  datos están mal. Se puso a revisar rangos durante un rato por culpa del
  texto.

  Los nombres de campo del backend se traducen: `non_field_errors` no le dice
  nada a quien escribe una especificación.
*/
const CAMPO: Record<string, string> = {
  non_field_errors: "",
  producto: "Producto",
  version: "Versión",
  vigente_desde: "Vigente desde",
  vigente_hasta: "Vigente hasta",
  rangos: "Rangos",
  detail: "",
};

function motivoDelFallo(e: unknown): string {
  const error = e as {
    response?: { status?: number; data?: unknown };
    code?: string;
  };

  // Sin respuesta no hubo rechazo: la petición no llegó. Es lo que ve
  // cualquiera con el servidor caído, y merece decirlo con esas palabras.
  if (!error?.response) {
    return error?.code === "ECONNABORTED"
      ? "El servidor tardó demasiado en responder. La especificación no se guardó; revisa que siga en pie e inténtalo otra vez."
      : "No se pudo contactar al servidor, así que la especificación no se guardó. Revisa que esté corriendo y vuelve a intentarlo — lo que escribiste sigue aquí.";
  }

  if (error.response.status === 403) {
    return "Tu rol no puede escribir especificaciones: las edita Calidad.";
  }

  const datos = error.response.data;

  if (typeof datos !== "object" || datos === null) {
    return `El servidor rechazó el guardado (error ${error.response.status}).`;
  }

  const motivos = Object.entries(datos as Record<string, unknown>).map(
    ([campo, motivo]) => {
      const texto = Array.isArray(motivo) ? motivo.join(" ") : String(motivo);
      const etiqueta = CAMPO[campo] ?? campo;

      return etiqueta ? `${etiqueta}: ${texto}` : texto;
    },
  );

  return motivos.join(" · ") || "El servidor rechazó el guardado.";
}


function FormularioEspecificacion({
  modo,
  inicial,
  productos,
  parametros,
  onGuardar,
  onCerrar,
}: {
  modo: Modo;
  inicial: Especificacion | null;
  productos: ProductoMaestro[];
  parametros: Parametro[];
  onGuardar: (id: number | null, datos: NuevaEspecificacion) => Promise<void>;
  onCerrar: () => void;
}) {
  const [producto, setProducto] = useState(String(inicial?.producto ?? ""));
  const [version, setVersion] = useState(
    String(modo === "version" ? (inicial?.version ?? 0) + 1 : inicial?.version ?? 1),
  );
  const [desde, setDesde] = useState(
    modo === "version" ? hoy() : inicial?.vigente_desde ?? hoy(),
  );
  const [hasta, setHasta] = useState(
    modo === "version" ? "" : inicial?.vigente_hasta ?? "",
  );
  const [fuente, setFuente] = useState(inicial?.fuente ?? "");
  const [rangos, setRangos] = useState<Record<string, Rango>>(
    () => ({ ...(inicial?.rangos ?? {}) }),
  );
  const [guardando, setGuardando] = useState(false);
  const [error, setError] = useState("");

  const alternar = (clave: string, activo: boolean) =>
    setRangos((previos) => {
      const copia = { ...previos };

      if (activo) {
        copia[clave] = { min: null, max: null, obligatorio: true };
      } else {
        delete copia[clave];
      }

      return copia;
    });

  const cambiar = (clave: string, campo: keyof Rango, valor: unknown) =>
    setRangos((previos) => ({
      ...previos,
      [clave]: { ...previos[clave], [campo]: valor },
    }));

  // Un parámetro exigido sin ningún límite no exige nada, y en el veredicto se
  // leería como cubierto. Se avisa antes de guardar, no después.
  const vacios = Object.entries(rangos)
    .filter(([, r]) => r.min == null && r.max == null)
    .map(([clave]) => clave);

  const guardar = async (e: React.FormEvent) => {
    e.preventDefault();

    if (!Object.keys(rangos).length) {
      setError(
        "Una especificación sin parámetros no evalúa nada: el lote saldría " +
          "conforme sin haberse medido.",
      );
      return;
    }

    setGuardando(true);
    setError("");

    try {
      await onGuardar(modo === "editar" ? inicial?.id ?? null : null, {
        producto: Number(producto),
        version: Number(version),
        vigente_desde: desde,
        vigente_hasta: hasta || null,
        rangos,
        fuente,
      });
    } catch (e) {
      setError(motivoDelFallo(e));
    } finally {
      setGuardando(false);
    }
  };

  const campo =
    "w-full rounded-xl border border-slate-200 px-3 py-2.5 text-sm focus:border-green-500 focus:outline-none";

  return (
    <div className="fixed inset-0 z-[70] flex items-start justify-center overflow-y-auto bg-slate-950/45 p-4">

      <form onSubmit={guardar} className="my-6 w-full max-w-3xl rounded-2xl bg-white p-6">

        <div className="flex items-start justify-between">
          <div>
            <p className="text-xs font-semibold uppercase tracking-wider text-green-700">
              Calidad
            </p>
            <h2 className="mt-1 text-xl font-semibold">{TEXTO[modo].titulo}</h2>
          </div>
          <button
            type="button"
            onClick={onCerrar}
            className="rounded-lg p-2 text-slate-400 hover:bg-slate-100"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        {modo === "editar" && (
          <p className="mt-4 flex gap-2 rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900">
            <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
            <span>
              Editar una versión <strong>reevalúa los lotes que ya se
              auditaron con ella</strong> — un lote conforme puede pasar a no
              conforme sin que nadie lo mida de nuevo. Para cambiar los rangos
              de aquí en adelante, crea una versión nueva.
            </span>
          </p>
        )}

        {modo === "version" && (
          <p className="mt-4 rounded-xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm text-slate-600">
            La versión anterior se queda como está y sigue auditando los lotes
            de su período. Esta manda desde su fecha de inicio en adelante; no
            hace falta cerrar la otra.
          </p>
        )}

        <div className="mt-5 grid gap-4 sm:grid-cols-4">

          <label className="text-sm text-slate-600 sm:col-span-2">
            Producto
            <select
              required
              value={producto}
              onChange={(e) => setProducto(e.target.value)}
              /* El producto no se cambia después: mover una especificación de
                 producto reevaluaría en silencio los lotes de los dos. */
              disabled={modo !== "nueva"}
              className={`mt-1 ${campo} bg-white disabled:bg-slate-50 disabled:text-slate-500`}
            >
              <option value="">Selecciona</option>
              {productos.map((p) => (
                <option key={p.id} value={p.id}>{p.nombre}</option>
              ))}
            </select>
          </label>

          <label className="text-sm text-slate-600">
            Versión
            <input
              required type="number" min="1" value={version}
              onChange={(e) => setVersion(e.target.value)}
              className={`mt-1 ${campo}`}
            />
          </label>

          <label className="text-sm text-slate-600">
            Fuente
            <input
              value={fuente}
              placeholder="Ficha técnica…"
              onChange={(e) => setFuente(e.target.value)}
              className={`mt-1 ${campo}`}
            />
          </label>

          <label className="text-sm text-slate-600 sm:col-span-2">
            Vigente desde
            <input
              required type="date" value={desde}
              onChange={(e) => setDesde(e.target.value)}
              className={`mt-1 ${campo}`}
            />
          </label>

          <label className="text-sm text-slate-600 sm:col-span-2">
            Vigente hasta
            <input
              type="date" value={hasta}
              onChange={(e) => setHasta(e.target.value)}
              className={`mt-1 ${campo}`}
            />
            <span className="mt-1 block text-xs text-slate-400">
              Vacío = sin fecha de término
            </span>
          </label>

        </div>

        <fieldset className="mt-6 rounded-xl border border-slate-200">

          <legend className="ml-4 px-2 text-sm font-semibold text-slate-700">
            Parámetros exigidos
          </legend>

          <table className="w-full">

            <thead>
              <tr className="text-xs uppercase tracking-wide text-slate-500">
                <th className="px-4 py-2 text-left font-semibold">Parámetro</th>
                <th className="px-4 py-2 text-left font-semibold">Mínimo</th>
                <th className="px-4 py-2 text-left font-semibold">Máximo</th>
                <th className="px-4 py-2 text-left font-semibold">Obligatorio</th>
              </tr>
            </thead>

            <tbody>
              {parametros.map((p) => {
                const rango = rangos[p.clave];
                const activo = rango !== undefined;

                return (
                  <tr key={p.clave} className="border-t border-slate-100">

                    <td className="px-4 py-2">
                      <label className="flex items-center gap-2 text-sm">
                        <input
                          type="checkbox"
                          checked={activo}
                          onChange={(e) => alternar(p.clave, e.target.checked)}
                        />
                        <span className={activo ? "text-slate-800" : "text-slate-400"}>
                          {p.etiqueta}
                          {p.unidad && (
                            <span className="ml-1 text-xs text-slate-400">
                              {p.unidad}
                            </span>
                          )}
                        </span>
                      </label>
                    </td>

                    {(["min", "max"] as const).map((extremo) => (
                      <td key={extremo} className="px-4 py-2">
                        <input
                          type="number" step="0.01"
                          disabled={!activo}
                          value={rango?.[extremo] ?? ""}
                          onChange={(e) =>
                            cambiar(
                              p.clave,
                              extremo,
                              e.target.value === "" ? null : Number(e.target.value),
                            )
                          }
                          className="w-28 rounded-lg border border-slate-200 px-2 py-1.5 text-sm disabled:bg-slate-50"
                        />
                      </td>
                    ))}

                    <td className="px-4 py-2">
                      <input
                        type="checkbox"
                        disabled={!activo}
                        checked={Boolean(rango?.obligatorio)}
                        onChange={(e) =>
                          cambiar(p.clave, "obligatorio", e.target.checked)
                        }
                      />
                    </td>

                  </tr>
                );
              })}
            </tbody>

          </table>

        </fieldset>

        <p className="mt-2 text-xs text-slate-400">
          Un parámetro <strong>obligatorio</strong> que el análisis no traiga
          deja el lote sin veredicto conforme: no es que falle, es que no hay
          con qué afirmarlo. Uno no obligatorio que no se mida no penaliza.
        </p>

        {vacios.length > 0 && (
          <p className="mt-4 rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900">
            Sin mínimo ni máximo, {vacios.length === 1 ? "el parámetro" : "los parámetros"}{" "}
            <strong>{vacios.join(", ")}</strong>{" "}
            {vacios.length === 1 ? "no exige" : "no exigen"} nada: cualquier
            valor pasa. Ponle un límite o desmárcalo.
          </p>
        )}

        {error && (
          <p className="mt-4 rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
            {error}
          </p>
        )}

        <div className="mt-6 flex gap-3">
          <button
            type="button"
            onClick={onCerrar}
            className="rounded-xl border border-slate-300 px-5 py-3 text-sm font-medium"
          >
            Cancelar
          </button>
          <button
            disabled={guardando}
            className="flex-1 rounded-xl bg-green-700 px-5 py-3 text-sm font-semibold text-white disabled:opacity-40"
          >
            {TEXTO[modo].boton}
          </button>
        </div>

      </form>

    </div>
  );
}


export default FormularioEspecificacion;
