import { useState } from "react";
import { X, AlertTriangle, CheckCircle2 } from "lucide-react";
import axios from "axios";

import {
  CONTROLES_NUMERICOS,
  CONTROLES_OPCION,
  crearRecepcion,
  type Silo,
  type Vehiculo,
} from "../../services/recepcion.service";


/*
  Alta de una recepción de leche.

  Los controles del camión se completan aquí y deciden si la leche puede
  liberarse al silo. El formulario adelanta ese veredicto mientras se
  escribe —con la misma regla que aplica el backend— para que quien registra
  vea el motivo antes de guardar y no después.

  El veredicto que vale es el del servidor: este es un anticipo, no la
  decisión.
*/

interface Props {
  silos: Silo[];
  vehiculos: Vehiculo[];
  alCerrar: () => void;
  alGuardar: () => void;
}


const hoy = () => new Date().toISOString().slice(0, 10);

const LIMITES = {
  acidez_max: 18,
  ph_min: 6.5,
  ph_max: 6.9,
  temperatura_max: 8,
  crioscopia_max: -0.51,
};


/** Mismo criterio que recepcion/dominio.py::evaluar_recepcion. */
function motivosDeRetencion(controles: Record<string, string>): string[] {

  const motivos: string[] = [];
  const numero = (v: string) => (v.trim() === "" ? null : Number(v));

  if (controles.delvo === "Positivo") {
    motivos.push("Delvo Test positivo (presencia de antibióticos).");
  }

  if (controles.inhibidores === "Positivo") {
    motivos.push("Inhibidores positivos.");
  }

  if (controles.organoleptico === "No conforme") {
    motivos.push("Evaluación organoléptica no conforme.");
  }

  const acidez = numero(controles.acidez ?? "");
  if (acidez !== null && acidez > LIMITES.acidez_max) {
    motivos.push(`Acidez ${acidez} °D sobre el máximo (${LIMITES.acidez_max} °D).`);
  }

  const ph = numero(controles.ph ?? "");
  if (ph !== null && (ph < LIMITES.ph_min || ph > LIMITES.ph_max)) {
    motivos.push(`pH ${ph} fuera del rango ${LIMITES.ph_min}–${LIMITES.ph_max}.`);
  }

  const temperatura = numero(controles.temperatura ?? "");
  if (temperatura !== null && temperatura > LIMITES.temperatura_max) {
    motivos.push(
      `Temperatura ${temperatura} °C sobre el máximo (${LIMITES.temperatura_max} °C).`,
    );
  }

  const crioscopia = numero(controles.crioscopia ?? "");
  if (crioscopia !== null && crioscopia > LIMITES.crioscopia_max) {
    motivos.push(`Crioscopía ${crioscopia} indica posible aguado.`);
  }

  return motivos;
}


function FormularioRecepcion({ silos, vehiculos, alCerrar, alGuardar }: Props) {

  const [fecha, setFecha] = useState(hoy());
  const [hora, setHora] = useState("");
  const [guia, setGuia] = useState("");
  const [vehiculo, setVehiculo] = useState("");
  const [procedencia, setProcedencia] = useState("");
  const [tipoLeche, setTipoLeche] = useState("Entera");
  const [litros, setLitros] = useState("");
  const [silo, setSilo] = useState("");
  const [turno, setTurno] = useState("");
  const [observacion, setObservacion] = useState("");

  const [controles, setControles] = useState<Record<string, string>>({});

  const [guardando, setGuardando] = useState(false);
  const [error, setError] = useState("");

  const motivos = motivosDeRetencion(controles);

  const cambiarControl = (clave: string, valor: string) => {
    setControles((previos) => ({ ...previos, [clave]: valor }));
  };

  const enviar = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();

    setError("");
    setGuardando(true);

    // Solo viajan los controles completados. Los numéricos como número, para
    // que el backend no los rechace.
    const medidos: Record<string, number | string> = {};

    for (const { clave } of CONTROLES_NUMERICOS) {
      const valor = controles[clave];
      if (valor !== undefined && valor.trim() !== "" && !Number.isNaN(Number(valor))) {
        medidos[clave] = Number(valor);
      }
    }

    for (const { clave } of CONTROLES_OPCION) {
      if (controles[clave]) {
        medidos[clave] = controles[clave];
      }
    }

    try {

      await crearRecepcion({
        fecha,
        hora: hora || undefined,
        guia: guia || undefined,
        vehiculo: vehiculo ? Number(vehiculo) : undefined,
        procedencia: procedencia || undefined,
        tipo_leche: tipoLeche,
        litros,
        silo: silo ? Number(silo) : undefined,
        turno: turno || undefined,
        observacion: observacion || undefined,
        controles: medidos,
      } as never);

      alGuardar();
      alCerrar();

    } catch (error) {

      if (axios.isAxiosError(error) && error.response) {

        const datos = error.response.data;

        setError(
          typeof datos === "object" && datos !== null
            ? Object.entries(datos)
                .map(([campo, errores]) =>
                  campo === "detail" ? String(errores) : `${campo}: ${errores}`,
                )
                .join(" · ")
            : "No se pudo guardar la recepción.",
        );

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

            Nueva recepción de leche

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

              <label className={etiquetaCampo}>Hora</label>

              <input
                type="time"
                className={campo}
                value={hora}
                onChange={(e) => setHora(e.target.value)}
              />

            </div>

            <div>

              <label className={etiquetaCampo}>Guía</label>

              <input
                className={campo}
                value={guia}
                onChange={(e) => setGuia(e.target.value)}
              />

            </div>

            <div className="sm:col-span-2">

              <label className={etiquetaCampo}>Camión</label>

              <select
                className={campo}
                value={vehiculo}
                onChange={(e) => setVehiculo(e.target.value)}
              >

                <option value="">—</option>

                {vehiculos.map((v) => (

                  <option key={v.id} value={v.id}>

                    {v.placa}
                    {v.transportista ? ` · ${v.transportista}` : ""}

                  </option>

                ))}

              </select>

            </div>

            <div>

              <label className={etiquetaCampo}>Procedencia</label>

              <select
                className={campo}
                value={procedencia}
                onChange={(e) => setProcedencia(e.target.value)}
              >

                <option value="">—</option>
                <option value="Nestlé">Nestlé</option>
                <option value="P. Unión">P. Unión</option>

              </select>

            </div>

            <div>

              <label className={etiquetaCampo}>Tipo de leche *</label>

              <select
                className={campo}
                value={tipoLeche}
                onChange={(e) => setTipoLeche(e.target.value)}
                required
              >

                <option value="Entera">Entera</option>
                <option value="Descremada">Descremada</option>

              </select>

            </div>

            <div>

              <label className={etiquetaCampo}>Litros *</label>

              <input
                type="number"
                step="0.01"
                min="0"
                className={campo}
                value={litros}
                onChange={(e) => setLitros(e.target.value)}
                required
              />

            </div>

            <div>

              <label className={etiquetaCampo}>Silo de destino</label>

              <select
                className={campo}
                value={silo}
                onChange={(e) => setSilo(e.target.value)}
              >

                <option value="">—</option>

                {silos.map((s) => (

                  <option key={s.id} value={s.id}>

                    {s.codigo}

                  </option>

                ))}

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

          {/* Controles del camión */}

          <div className="mt-8 border-t border-slate-200 pt-6">

            <h3 className="text-sm font-semibold text-slate-800">

              Controles del camión

            </h3>

            <p className="mt-1 mb-5 text-sm text-slate-400">

              Deciden si la leche se libera al silo o se retiene. Los límites
              son referenciales y están pendientes de confirmar con Calidad.

            </p>

            <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">

              {CONTROLES_NUMERICOS.map((control) => (

                <div key={control.clave}>

                  <label className={etiquetaCampo}>

                    {control.etiqueta}

                    {control.unidad && (

                      <span className="ml-1 font-normal text-slate-400">

                        ({control.unidad})

                      </span>

                    )}

                  </label>

                  <input
                    type="number"
                    step="any"
                    className={campo}
                    value={controles[control.clave] ?? ""}
                    onChange={(e) => cambiarControl(control.clave, e.target.value)}
                  />

                </div>

              ))}

            </div>

            <div className="mt-4 grid grid-cols-1 gap-4 sm:grid-cols-3">

              {CONTROLES_OPCION.map((control) => (

                <div key={control.clave}>

                  <label className={etiquetaCampo}>{control.etiqueta}</label>

                  <select
                    className={campo}
                    value={controles[control.clave] ?? ""}
                    onChange={(e) => cambiarControl(control.clave, e.target.value)}
                  >

                    <option value="">—</option>

                    {control.valores.map((valor) => (

                      <option key={valor} value={valor}>

                        {valor}

                      </option>

                    ))}

                  </select>

                </div>

              ))}

            </div>

            {/* Anticipo del veredicto */}

            {motivos.length > 0 ? (

              <div className="mt-6 rounded-xl bg-red-50 px-4 py-3">

                <p className="flex items-center gap-2 text-sm font-medium text-red-800">

                  <AlertTriangle className="h-4 w-4" />

                  Con estos controles, la leche debe retenerse

                </p>

                <ul className="mt-2 list-disc space-y-1 pl-9 text-sm text-red-700">

                  {motivos.map((motivo) => (

                    <li key={motivo}>{motivo}</li>

                  ))}

                </ul>

              </div>

            ) : (

              Object.values(controles).some((v) => v !== "") && (

                <p className="mt-6 flex items-center gap-2 rounded-xl bg-green-50 px-4 py-3 text-sm font-medium text-green-800">

                  <CheckCircle2 className="h-4 w-4" />

                  Los controles cargados permiten liberar la leche al silo

                </p>

              )

            )}

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

              {guardando ? "Guardando…" : "Registrar recepción"}

            </button>

          </div>

        </form>

      </div>

    </div>
  );
}


export default FormularioRecepcion;
