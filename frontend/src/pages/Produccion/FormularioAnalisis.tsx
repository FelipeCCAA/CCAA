import { useState } from "react";
import { Plus } from "lucide-react";
import axios from "axios";

import {
  crearAnalisis,
  obtenerParametros,
  type Parametro,
} from "../../services/produccion.service";


/*
  Carga de un análisis sobre un lote ya producido.

  Vive aquí y no en la apertura del proceso porque los parámetros se miden
  sobre el producto terminado: al abrir la corrida no existe todavía nada que
  analizar, y un formulario que los pide invita a rellenarlos con lo que se
  espera en vez de con lo que se midió.

  El resultado de calidad no se escribe: se evalúa solo contra la
  especificación vigente a la fecha del lote (MODELO_DATOS.md §2.2). Aquí solo
  entran los valores medidos.
*/

interface Props {
  loteId: number;
  fechaLote: string;
  alGuardar: () => void;
}


function FormularioAnalisis({ loteId, fechaLote, alGuardar }: Props) {

  const [abierto, setAbierto] = useState(false);
  const [parametros, setParametros] = useState<Parametro[] | null>(null);
  const [cargandoParametros, setCargandoParametros] = useState(false);
  const [fecha, setFecha] = useState(fechaLote);
  const [muestra, setMuestra] = useState("");
  const [medidos, setMedidos] = useState<Record<string, string>>({});
  const [guardando, setGuardando] = useState(false);
  const [error, setError] = useState("");

  const escribir = (clave: string, valor: string) =>
    setMedidos((previos) => ({ ...previos, [clave]: valor }));

  const cerrar = () => {
    setAbierto(false);
    setMedidos({});
    setMuestra("");
    setError("");
  };

  const abrir = async () => {
    if (parametros === null) {
      setCargandoParametros(true);
      setError("");
      try {
        setParametros(await obtenerParametros());
      } catch {
        setError("No se pudieron cargar los parámetros del análisis.");
        setCargandoParametros(false);
        return;
      }
      setCargandoParametros(false);
    }
    setAbierto(true);
  };

  const guardar = async () => {
    // Solo viajan los parámetros que se completaron: un campo vacío no es un
    // cero medido.
    const valores: Record<string, number> = {};

    for (const [clave, valor] of Object.entries(medidos)) {
      if (valor.trim() !== "" && !Number.isNaN(Number(valor))) {
        valores[clave] = Number(valor);
      }
    }

    if (Object.keys(valores).length === 0) {
      setError("Completa al menos un parámetro.");
      return;
    }

    setGuardando(true);
    setError("");

    try {
      await crearAnalisis(loteId, fecha, valores, muestra);
      cerrar();
      alGuardar();
    } catch (e) {
      if (axios.isAxiosError(e) && e.response) {
        const datos = e.response.data as Record<string, string[] | string>;
        setError(Object.values(datos).flat().join(" "));
      } else {
        setError("No se pudo registrar el análisis.");
      }
      setGuardando(false);
    }
  };

  const campo =
    "w-full rounded-xl border border-slate-200 px-3 py-2 text-sm text-slate-800 " +
    "focus:border-green-500 focus:outline-none";

  if (!abierto) {
    return (
      <div className="mt-3">
        <button
          type="button"
          disabled={cargandoParametros}
          onClick={() => void abrir()}
          className="flex items-center gap-1.5 rounded-xl border border-slate-200 px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50 disabled:opacity-50"
        >
          <Plus className="h-4 w-4" />
          {cargandoParametros ? "Preparando…" : "Agregar análisis"}
        </button>
        {error && (
          <p className="mt-3 rounded-xl bg-red-50 px-4 py-3 text-sm text-red-700">
            {error}
          </p>
        )}
      </div>
    );
  }

  return (

    <div className="mt-3 rounded-xl border border-slate-200 p-4">

      <div className="grid grid-cols-2 gap-4">

        <div>

          <label className="mb-1 block text-xs font-medium text-slate-600">
            Fecha del análisis
          </label>

          <input
            type="date"
            className={campo}
            value={fecha}
            onChange={(e) => setFecha(e.target.value)}
          />

        </div>

        <div>

          <label className="mb-1 block text-xs font-medium text-slate-600">
            Muestra
          </label>

          <input
            className={campo}
            value={muestra}
            onChange={(e) => setMuestra(e.target.value)}
            placeholder="M-01"
          />

        </div>

      </div>

      <div className="mt-4 grid grid-cols-2 gap-3 sm:grid-cols-3">

        {(parametros ?? []).map((parametro) => (

          <div key={parametro.clave}>

            <label className="mb-1 block text-xs font-medium text-slate-600">

              {parametro.etiqueta}

              {parametro.unidad && (
                <span className="ml-1 font-normal text-slate-600">
                  ({parametro.unidad})
                </span>
              )}

            </label>

            <input
              type="number"
              step="any"
              className={campo}
              value={medidos[parametro.clave] ?? ""}
              onChange={(e) => escribir(parametro.clave, e.target.value)}
            />

          </div>

        ))}

      </div>

      {error && (
        <p className="mt-3 rounded-xl bg-red-50 px-4 py-3 text-sm text-red-700">
          {error}
        </p>
      )}

      <div className="mt-4 flex gap-2">

        <button
          type="button"
          disabled={guardando}
          onClick={() => void guardar()}
          className="rounded-xl bg-green-600 px-4 py-2 text-sm font-medium text-white hover:bg-green-700 disabled:opacity-50"
        >
          {guardando ? "Registrando…" : "Registrar análisis"}
        </button>

        <button
          type="button"
          onClick={cerrar}
          className="rounded-xl px-4 py-2 text-sm font-medium text-slate-600 hover:bg-slate-100"
        >
          Cancelar
        </button>

      </div>

    </div>

  );
}


export default FormularioAnalisis;
