import { useCallback, useEffect, useState } from "react";
import { Plus, Trash2, X } from "lucide-react";
import axios from "axios";

import {
  crearAnalisis,
  crearLote,
  sugerirCodigoLote,
  type Parametro,
  type Producto,
} from "../../services/produccion.service";

import { obtenerSilos, type Silo } from "../../services/recepcion.service";


/*
  Apertura de un proceso de producción.

  El lote se abre cuando la corrida empieza, no cuando termina. Por eso aquí
  no se piden los kilos: se declaran al marcar el lote como producido, que es
  cuando se saben. Exigirlos al abrir obligaba a registrar el lote al final
  del día, y con él toda su trazabilidad — que entonces ya era documentación
  retroactiva.

  La leche va en el mismo formulario y en la misma llamada. Si fuera un
  segundo paso, un fallo entre medio dejaría un lote abierto sin materia
  prima, y nadie vuelve a completar lo que ya parece creado.

  El código se sugiere según el POE.009.02 pero queda editable: el histórico
  de planta trae códigos que no siguen el patrón y hay que poder registrarlos.

  Los parámetros de calidad siguen aquí porque hoy es la única vía para
  cargarlos. Al abrir un proceso normalmente van vacíos.
*/

interface Props {
  productos: Producto[];
  parametros: Parametro[];
  alCerrar: () => void;
  alGuardar: () => void;
}


const hoy = () => new Date().toISOString().slice(0, 10);


function FormularioLote({ productos, parametros, alCerrar, alGuardar }: Props) {

  const [codigoLote, setCodigoLote] = useState("");
  const [producto, setProducto] = useState("");
  const [fecha, setFecha] = useState(hoy());
  const [op, setOp] = useState("");
  const [linea, setLinea] = useState("");
  const [turno, setTurno] = useState("");
  const [muestra, setMuestra] = useState("");
  const [observacion, setObservacion] = useState("");

  /* Una vez que el operador escribe el código, la sugerencia deja de pisarlo:
     lo que escribió a mano gana. */
  const [codigoEditado, setCodigoEditado] = useState(false);
  const [notaCodigo, setNotaCodigo] = useState("");

  const [silos, setSilos] = useState<Silo[]>([]);
  const [asignaciones, setAsignaciones] = useState<
    { silo: string; litros: string }[]
  >([]);

  const [medidos, setMedidos] = useState<Record<string, string>>({});

  const [guardando, setGuardando] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    obtenerSilos()
      .then(setSilos)
      // Sin la lista no se puede asignar leche, pero el lote se abre igual.
      .catch(() => setSilos([]));
  }, []);

  const sugerir = useCallback(async () => {
    if (!producto || !fecha || codigoEditado) {
      return;
    }

    try {
      const sugerencia = await sugerirCodigoLote(Number(producto), fecha, linea);

      setCodigoLote(sugerencia.codigo ?? "");
      setNotaCodigo(sugerencia.motivo ?? "");
    } catch {
      // Sin sugerencia el campo queda libre: se escribe a mano.
      setNotaCodigo("");
    }
  }, [producto, fecha, linea, codigoEditado]);

  useEffect(() => {
    const temporizador = setTimeout(sugerir, 0);

    return () => clearTimeout(temporizador);
  }, [sugerir]);

  const cambiarParametro = (clave: string, valor: string) => {
    setMedidos((previos) => ({ ...previos, [clave]: valor }));
  };

  const agregarSilo = () =>
    setAsignaciones((a) => [...a, { silo: "", litros: "" }]);

  const editarSilo = (i: number, campo: "silo" | "litros", valor: string) =>
    setAsignaciones((a) =>
      a.map((l, j) => (j === i ? { ...l, [campo]: valor } : l)),
    );

  const quitarSilo = (i: number) =>
    setAsignaciones((a) => a.filter((_, j) => j !== i));

  const enviar = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();

    setError("");
    setGuardando(true);

    // Solo viajan los parámetros que se completaron.
    const valores: Record<string, number> = {};

    for (const [clave, valor] of Object.entries(medidos)) {
      if (valor.trim() !== "" && !Number.isNaN(Number(valor))) {
        valores[clave] = Number(valor);
      }
    }

    const leche = asignaciones
      .filter((l) => l.silo && l.litros)
      .map((l) => ({ silo: Number(l.silo), litros: Number(l.litros) }));

    try {

      const lote = await crearLote({
        codigo_lote: codigoLote,
        producto: Number(producto),
        fecha,
        op: op || undefined,
        linea: linea || undefined,
        turno: turno || undefined,
        observacion: observacion || undefined,
        asignaciones: leche.length > 0 ? leche : undefined,
      });

      if (Object.keys(valores).length > 0) {

        try {
          await crearAnalisis(lote.id, fecha, valores, muestra);
        } catch {
          // El lote sí quedó abierto. Se avisa en vez de dejar creer que no
          // se guardó nada y que el usuario lo cargue dos veces.
          setError(
            "El proceso se abrió, pero no se pudieron registrar sus " +
              "parámetros. Agrégalos desde la ficha del lote.",
          );
          setGuardando(false);
          alGuardar();
          return;
        }

      }

      alGuardar();
      alCerrar();

    } catch (error) {

      if (axios.isAxiosError(error) && error.response) {

        const datos = error.response.data;

        // DRF devuelve {campo: [mensajes]}. Se muestran todos, porque el
        // más común aquí es el de la clave natural duplicada.
        const mensajes =
          typeof datos === "object" && datos !== null
            ? Object.entries(datos)
                .map(([campo, errores]) =>
                  campo === "non_field_errors" || campo === "detail"
                    ? String(errores)
                    : `${campo}: ${errores}`,
                )
                .join(" · ")
            : "No se pudo abrir el proceso.";

        setError(mensajes);

      } else {
        setError("No se pudo conectar con el servidor.");
      }

      setGuardando(false);

    }
  };

  const etiquetaCampo = "mb-1.5 block text-sm font-medium text-slate-700";
  const campo =
    "w-full rounded-xl border border-slate-300 bg-white px-4 py-3 outline-none focus:border-green-600";

  return (
    <div className="fixed inset-0 z-50 flex items-start justify-center overflow-y-auto bg-slate-900/40 p-4 sm:p-8">

      <div className="w-full max-w-3xl rounded-2xl bg-white shadow-xl">

        <div className="flex items-center justify-between border-b border-slate-200 px-6 py-5">

          <div>

            <h2 className="text-lg font-semibold text-slate-800">

              Abrir proceso de producción

            </h2>

            <p className="mt-0.5 text-sm text-slate-500">

              El lote queda en proceso. Los kilos se declaran al cerrarlo.

            </p>

          </div>

          <button
            type="button"
            onClick={alCerrar}
            className="rounded-lg p-1 text-slate-400 hover:bg-slate-100 hover:text-slate-700"
            aria-label="Cerrar"
          >

            <X className="h-5 w-5" />

          </button>

        </div>

        <form onSubmit={enviar} className="px-6 py-6">

          <div className="grid grid-cols-1 gap-5 sm:grid-cols-3">

            <div className="sm:col-span-2">

              <label className={etiquetaCampo}>Producto *</label>

              <select
                className={campo}
                value={producto}
                onChange={(e) => setProducto(e.target.value)}
                required
              >

                <option value="">Selecciona un producto…</option>

                {productos.map((p) => (

                  <option key={p.id} value={p.id}>

                    {p.nombre} · {p.mandante_nombre}

                  </option>

                ))}

              </select>

            </div>

            <div>

              <label className={etiquetaCampo}>Fecha *</label>

              <input
                type="date"
                className={campo}
                value={fecha}
                onChange={(e) => setFecha(e.target.value)}
                required
              />

            </div>

            <div>

              <label className={etiquetaCampo}>Línea</label>

              <select
                className={campo}
                value={linea}
                onChange={(e) => setLinea(e.target.value)}
              >

                <option value="">—</option>
                <option value="E1">E1</option>
                <option value="E2">E2</option>

              </select>

            </div>

            <div className="sm:col-span-2">

              <label className={etiquetaCampo}>Código de lote *</label>

              <input
                className={campo}
                value={codigoLote}
                onChange={(e) => {
                  setCodigoLote(e.target.value);
                  setCodigoEditado(true);
                }}
                placeholder="CCAA6140N"
                required
              />

              <p className="mt-1.5 text-xs text-slate-400">

                {notaCodigo ||
                  "Se propone según el POE.009.02 a partir del producto, la " +
                    "fecha y la línea. Se puede cambiar."}

              </p>

            </div>

            <div>

              <label className={etiquetaCampo}>Turno</label>

              <select
                className={campo}
                value={turno}
                onChange={(e) => setTurno(e.target.value)}
              >

                <option value="">—</option>
                <option value="A">A</option>
                <option value="B">B</option>
                <option value="C">C</option>

              </select>

            </div>

            <div className="sm:col-span-2">

              <label className={etiquetaCampo}>OP</label>

              <input
                className={campo}
                value={op}
                onChange={(e) => setOp(e.target.value)}
              />

            </div>

          </div>

          {/* Leche asignada */}

          <div className="mt-8 border-t border-slate-200 pt-6">

            <h3 className="text-sm font-semibold text-slate-800">

              Leche asignada

            </h3>

            <p className="mt-1 mb-5 text-sm text-slate-400">

              De qué estanques sale la leche de este lote. Puede ser más de
              uno. Es lo que da trazabilidad hacia las recepciones: sin esto
              el lote queda sin origen.

            </p>

            {asignaciones.map((linea, i) => (

              <div key={i} className="mb-3 flex items-center gap-3">

                <select
                  className={campo}
                  value={linea.silo}
                  onChange={(e) => editarSilo(i, "silo", e.target.value)}
                >

                  <option value="">Silo…</option>

                  {silos.map((s) => (
                    <option key={s.id} value={s.id}>
                      {s.codigo}
                    </option>
                  ))}

                </select>

                <input
                  type="number"
                  min="1"
                  inputMode="numeric"
                  className={`${campo} w-40`}
                  value={linea.litros}
                  onChange={(e) => editarSilo(i, "litros", e.target.value)}
                  placeholder="Litros"
                />

                <button
                  type="button"
                  onClick={() => quitarSilo(i)}
                  aria-label="Quitar este silo"
                  className="rounded-lg p-2 text-slate-400 hover:bg-slate-100"
                >

                  <Trash2 className="h-5 w-5" />

                </button>

              </div>

            ))}

            <button
              type="button"
              onClick={agregarSilo}
              className="flex items-center gap-1.5 rounded-xl border border-slate-300 px-4 py-2.5 text-sm font-medium text-slate-700 hover:bg-slate-50"
            >

              <Plus className="h-4 w-4" />

              Agregar silo

            </button>

          </div>

          {/* Parámetros de calidad */}

          <div className="mt-8 border-t border-slate-200 pt-6">

            <h3 className="text-sm font-semibold text-slate-800">

              Parámetros de calidad

            </h3>

            <p className="mt-1 mb-5 text-sm text-slate-400">

              Opcionales, y normalmente vacíos al abrir: se miden sobre el
              producto terminado. Se evalúan solos contra la especificación
              vigente, el resultado no se escribe a mano.

            </p>

            <div className="mb-5 max-w-xs">

              <label className={etiquetaCampo}>Muestra</label>

              <input
                className={campo}
                value={muestra}
                onChange={(e) => setMuestra(e.target.value)}
                placeholder="M-01"
              />

            </div>

            <div className="grid grid-cols-2 gap-4 sm:grid-cols-3">

              {parametros.map((parametro) => (

                <div key={parametro.clave}>

                  <label className={etiquetaCampo}>

                    {parametro.etiqueta}

                    {parametro.unidad && (

                      <span className="ml-1 font-normal text-slate-400">

                        ({parametro.unidad})

                      </span>

                    )}

                  </label>

                  <input
                    type="number"
                    step="any"
                    className={campo}
                    value={medidos[parametro.clave] ?? ""}
                    onChange={(e) =>
                      cambiarParametro(parametro.clave, e.target.value)
                    }
                  />

                </div>

              ))}

            </div>

          </div>

          <div className="mt-6">

            <label className={etiquetaCampo}>Observación</label>

            <textarea
              className={campo}
              rows={2}
              value={observacion}
              onChange={(e) => setObservacion(e.target.value)}
            />

          </div>

          {error && (

            <div className="mt-6 rounded-xl bg-red-50 px-4 py-3 text-sm text-red-700">

              {error}

            </div>

          )}

          <div className="mt-8 flex justify-end gap-3">

            <button
              type="button"
              onClick={alCerrar}
              className="rounded-xl px-5 py-3 text-sm font-medium text-slate-600 hover:bg-slate-100"
            >

              Cancelar

            </button>

            <button
              type="submit"
              disabled={guardando}
              className="rounded-xl bg-green-700 px-6 py-3 text-sm font-semibold text-white hover:bg-green-800 disabled:opacity-60"
            >

              {guardando ? "Abriendo…" : "Abrir proceso"}

            </button>

          </div>

        </form>

      </div>

    </div>
  );
}


export default FormularioLote;
