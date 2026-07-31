import { useMemo, useState } from "react";
import { AlertTriangle, Check, X } from "lucide-react";
import axios from "axios";

import CampoDePlantilla from "../../components/CampoDePlantilla/CampoDePlantilla";

import {
  guardarRegistro,
  type CampoPlantilla,
  type Discrepancia,
  type EstadoDocumento,
} from "../../services/calidad.service";


/*
  Un formulario del checklist, dibujado desde la plantilla del documento.

  Esta pantalla no sabe qué formularios existen ni qué campos tienen: los lee
  de `documento.plantilla` (MODELO_DATOS.md §2.6). Por eso Calidad puede
  agregar un campo desde Administración y aparece aquí sin desplegar nada, y
  por eso no hay diecinueve formularios escritos a mano esperando a que
  alguien los mantenga.

  Las validaciones se adelantan mientras se escribe, con el mismo criterio que
  aplica el backend, para que el motivo se vea antes de guardar y no después.
  La que vale es la del servidor.
*/

interface Props {
  loteId: number;
  estado: EstadoDocumento;
  prellenado: Record<string, unknown>;
  discrepancias: Discrepancia[];
  puedeEditar: boolean;
  alCerrar: () => void;
  alGuardar: () => void;
}


const vacio = (v: unknown) => v === null || v === undefined || v === "";


/** Campos obligatorios sin llenar. Mismo criterio que dominio.campos_faltantes. */
function faltantes(
  plantilla: CampoPlantilla[],
  valores: Record<string, unknown>,
): CampoPlantilla[] {
  return plantilla.filter((c) => c.req && vacio(valores[c.clave]));
}


/** Valores fuera del min/max declarado en la plantilla. */
function fueraDeRango(
  plantilla: CampoPlantilla[],
  valores: Record<string, unknown>,
): string[] {

  const avisos: string[] = [];

  for (const campo of plantilla) {
    const crudo = valores[campo.clave];

    if (vacio(crudo)) {
      continue;
    }

    const valor = Number(crudo);

    if (Number.isNaN(valor)) {
      continue;
    }

    if (campo.min !== undefined && valor < campo.min) {
      avisos.push(`${campo.etiqueta}: no puede ser menor que ${campo.min}.`);
    }

    if (campo.max !== undefined && valor > campo.max) {
      avisos.push(`${campo.etiqueta}: no puede ser mayor que ${campo.max}.`);
    }
  }

  return avisos;
}


function FormularioDinamico({
  loteId,
  estado,
  prellenado,
  discrepancias,
  puedeEditar,
  alCerrar,
  alGuardar,
}: Props) {

  const documento = estado.documento;
  const registro = estado.registro;

  // El prellenado solo se aplica a lo que todavía no tiene valor: nunca pisa
  // lo que alguien escribió.
  const [valores, setValores] = useState<Record<string, unknown>>(() => ({
    ...prellenado,
    ...(registro?.valores || {}),
  }));

  const [observacion, setObservacion] = useState(registro?.observacion || "");
  const [referencia, setReferencia] = useState(registro?.referencia || "");
  const [guardando, setGuardando] = useState(false);
  const [error, setError] = useState("");

  const sinLlenar = useMemo(
    () => faltantes(documento.plantilla, valores),
    [documento.plantilla, valores],
  );

  const avisos = useMemo(
    () => fueraDeRango(documento.plantilla, valores),
    [documento.plantilla, valores],
  );

  const puedeCompletar = sinLlenar.length === 0 && avisos.length === 0;

  const guardar = async (nuevoEstado: "borrador" | "completado" | "observado") => {

    setError("");
    setGuardando(true);

    try {
      await guardarRegistro({
        id: registro?.id,
        lote: loteId,
        documento: documento.id,
        estado: nuevoEstado,
        valores,
        referencia,
        observacion,
      });

      alGuardar();

    } catch (e) {

      if (axios.isAxiosError(e) && e.response?.data) {
        const datos = e.response.data as Record<string, string[] | string>;

        setError(
          Object.values(datos)
            .flat()
            .join(" "),
        );
      } else {
        setError("No se pudo guardar el formulario.");
      }

    } finally {
      setGuardando(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-start justify-center overflow-y-auto bg-slate-900/40 p-4">

      <div className="my-8 w-full max-w-2xl rounded-2xl bg-white shadow-xl">

        {/* Cabecera */}

        <div className="flex items-start justify-between gap-4 border-b border-slate-200 px-6 py-5">

          <div>

            <h2 className="text-lg font-semibold text-slate-800">
              {documento.nombre}
            </h2>

            {documento.codigo && (
              <p className="mt-0.5 text-xs text-slate-400">{documento.codigo}</p>
            )}

            {documento.instruccion && (
              <p className="mt-2 text-sm text-slate-600">{documento.instruccion}</p>
            )}

          </div>

          <button
            type="button"
            onClick={alCerrar}
            className="rounded-lg p-1 text-slate-400 hover:bg-slate-100 hover:text-slate-600"
          >
            <X className="h-5 w-5" />
          </button>

        </div>

        {/* Campos */}

        <div className="space-y-5 px-6 py-5">

          {documento.plantilla.length === 0 && (
            <p className="rounded-xl bg-slate-50 px-4 py-3 text-sm text-slate-600">
              Este documento no tiene campos: se firma como atestación.
            </p>
          )}

          {documento.plantilla.map((campo) => (

            <div key={campo.clave}>

              <label className="mb-1.5 block text-sm font-medium text-slate-700">

                {campo.etiqueta}

                {campo.req && <span className="text-red-500"> *</span>}

                {campo.unidad && (
                  <span className="font-normal text-slate-400"> ({campo.unidad})</span>
                )}

                {campo.origen && (
                  <span
                    className="ml-2 rounded-full bg-slate-100 px-2 py-0.5 text-[10px] font-normal text-slate-500"
                    title="Lo rellena el sistema con un dato que ya tiene"
                  >
                    del sistema
                  </span>
                )}

              </label>

              <CampoDePlantilla
                campo={campo}
                valor={valores[campo.clave]}
                deshabilitado={!puedeEditar || guardando}
                alCambiar={(valor) =>
                  setValores((previos) => ({ ...previos, [campo.clave]: valor }))
                }
              />

            </div>

          ))}

          {/* Referencia al documento físico, si lo hay */}

          <div>

            <label className="mb-1.5 block text-sm font-medium text-slate-700">
              Referencia
              <span className="font-normal text-slate-400"> (documento físico, si lo hay)</span>
            </label>

            <input
              type="text"
              value={referencia}
              disabled={!puedeEditar || guardando}
              onChange={(e) => setReferencia(e.target.value)}
              className="w-full rounded-xl border border-slate-200 px-3 py-2 text-sm text-slate-800 focus:border-green-500 focus:outline-none disabled:bg-slate-50"
            />

          </div>

          <div>

            <label className="mb-1.5 block text-sm font-medium text-slate-700">
              Observación
            </label>

            <textarea
              rows={2}
              value={observacion}
              disabled={!puedeEditar || guardando}
              onChange={(e) => setObservacion(e.target.value)}
              placeholder="Obligatoria si el formulario queda observado"
              className="w-full rounded-xl border border-slate-200 px-3 py-2 text-sm text-slate-800 focus:border-green-500 focus:outline-none disabled:bg-slate-50"
            />

          </div>

          {/* Lo que el sistema ya sabe y no cuadra */}

          {discrepancias.length > 0 && (

            <div className="rounded-xl bg-amber-50 px-4 py-3">

              <p className="flex items-center gap-1.5 text-sm font-medium text-amber-800">
                <AlertTriangle className="h-4 w-4" />
                El formulario no cuadra con lo que el sistema ya sabe
              </p>

              <ul className="mt-2 space-y-1 text-sm text-amber-700">
                {discrepancias.map((d, i) => (
                  <li key={i}>· {d.mensaje}</li>
                ))}
              </ul>

            </div>

          )}

          {sinLlenar.length > 0 && (

            <p className="text-sm text-slate-500">
              Faltan por llenar: {sinLlenar.map((c) => c.etiqueta).join(", ")}.
            </p>

          )}

          {avisos.map((aviso, i) => (
            <p key={i} className="text-sm text-red-600">{aviso}</p>
          ))}

          {error && (
            <p className="rounded-xl bg-red-50 px-4 py-3 text-sm text-red-700">{error}</p>
          )}

        </div>

        {/* Acciones */}

        <div className="flex flex-wrap items-center justify-end gap-2 border-t border-slate-200 px-6 py-4">

          <button
            type="button"
            onClick={alCerrar}
            className="rounded-xl px-4 py-2 text-sm font-medium text-slate-600 hover:bg-slate-100"
          >
            Cerrar
          </button>

          {puedeEditar && (
            <>

              <button
                type="button"
                disabled={guardando}
                onClick={() => guardar("borrador")}
                className="rounded-xl border border-slate-200 px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50 disabled:opacity-50"
              >
                Guardar borrador
              </button>

              <button
                type="button"
                disabled={guardando || !observacion.trim()}
                onClick={() => guardar("observado")}
                title={
                  observacion.trim()
                    ? "Bloquea la liberación hasta que se resuelva"
                    : "Escribe primero qué se observó"
                }
                className="rounded-xl border border-amber-200 bg-amber-50 px-4 py-2 text-sm font-medium text-amber-800 hover:bg-amber-100 disabled:opacity-50"
              >
                Observar
              </button>

              <button
                type="button"
                disabled={guardando || !puedeCompletar}
                onClick={() => guardar("completado")}
                title={
                  puedeCompletar
                    ? "Da el formulario por cumplido"
                    : "Faltan campos obligatorios"
                }
                className="flex items-center gap-1.5 rounded-xl bg-green-600 px-4 py-2 text-sm font-medium text-white hover:bg-green-700 disabled:opacity-50"
              >
                <Check className="h-4 w-4" />
                Dar por completado
              </button>

            </>
          )}

        </div>

      </div>

    </div>
  );
}


export default FormularioDinamico;
