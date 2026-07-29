import { useState } from "react";
import { X } from "lucide-react";
import axios from "axios";

import {
  crearAnalisis,
  crearLote,
  type Parametro,
  type Producto,
} from "../../services/produccion.service";


/*
  Alta de un lote, con sus parámetros de calidad en el mismo formulario: es
  como llega la información desde planta.

  Los parámetros no están escritos aquí. Se piden a /api/maestros/parametros/,
  de modo que agregar uno en el backend lo hace aparecer en pantalla sin tocar
  esta pantalla — el mismo principio del prototipo, donde los formularios se
  generan desde el esquema.
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
  const [kg, setKg] = useState("");
  const [op, setOp] = useState("");
  const [linea, setLinea] = useState("");
  const [turno, setTurno] = useState("");
  const [bultos, setBultos] = useState("");
  const [muestra, setMuestra] = useState("");
  const [observacion, setObservacion] = useState("");

  const [medidos, setMedidos] = useState<Record<string, string>>({});

  const [guardando, setGuardando] = useState(false);
  const [error, setError] = useState("");

  const cambiarParametro = (clave: string, valor: string) => {
    setMedidos((previos) => ({ ...previos, [clave]: valor }));
  };

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

    try {

      const lote = await crearLote({
        codigo_lote: codigoLote,
        producto: Number(producto),
        fecha,
        kg_producidos: kg,
        op: op || undefined,
        linea: linea || undefined,
        turno: turno || undefined,
        bultos: bultos ? Number(bultos) : undefined,
        observacion: observacion || undefined,
      });

      if (Object.keys(valores).length > 0) {

        try {
          await crearAnalisis(lote.id, fecha, valores, muestra);
        } catch {
          // El lote sí quedó guardado. Se avisa en vez de dejar creer que
          // no se guardó nada y que el usuario lo cargue dos veces.
          setError(
            "El lote se guardó, pero no se pudieron registrar sus parámetros. " +
              "Agrégalos desde la ficha del lote.",
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
                  campo === "non_field_errors"
                    ? String(errores)
                    : `${campo}: ${errores}`,
                )
                .join(" · ")
            : "No se pudo guardar el lote.";

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

          <h2 className="text-lg font-semibold text-slate-800">

            Nuevo lote de producción

          </h2>

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

            <div>

              <label className={etiquetaCampo}>Código de lote *</label>

              <input
                className={campo}
                value={codigoLote}
                onChange={(e) => setCodigoLote(e.target.value)}
                placeholder="CCAA6140N"
                required
              />

            </div>

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

              <label className={etiquetaCampo}>Kilos producidos *</label>

              <input
                type="number"
                step="0.01"
                min="0"
                className={campo}
                value={kg}
                onChange={(e) => setKg(e.target.value)}
                required
              />

            </div>

            <div>

              <label className={etiquetaCampo}>Bultos</label>

              <input
                type="number"
                min="0"
                className={campo}
                value={bultos}
                onChange={(e) => setBultos(e.target.value)}
              />

            </div>

            <div>

              <label className={etiquetaCampo}>OP</label>

              <input
                className={campo}
                value={op}
                onChange={(e) => setOp(e.target.value)}
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

          </div>

          {/* Parámetros de calidad */}

          <div className="mt-8 border-t border-slate-200 pt-6">

            <h3 className="text-sm font-semibold text-slate-800">

              Parámetros de calidad

            </h3>

            <p className="mt-1 mb-5 text-sm text-slate-400">

              Opcionales. Se evalúan solos contra la especificación vigente
              del producto: el resultado no se escribe a mano.

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

              {guardando ? "Guardando…" : "Guardar lote"}

            </button>

          </div>

        </form>

      </div>

    </div>
  );
}


export default FormularioLote;
