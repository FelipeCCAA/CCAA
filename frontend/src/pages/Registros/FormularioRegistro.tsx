import { useState } from "react";
import { X } from "lucide-react";
import axios from "axios";

import {
  guardarRegistroEquipo,
  type DocumentoPeriodico,
  type RegistroEquipo,
} from "../../services/registros.service";

import type { Equipo } from "../../services/maestros.service";
import CampoDePlantilla from "../../components/CampoDePlantilla/CampoDePlantilla";


/*
  Captura de un registro de máquina.

  Los campos los dibuja `CampoDePlantilla`, el mismo componente que usa el
  expediente del lote: es el mismo contrato. Un aseo y un formulario de
  liberación se llenan igual; lo que cambia es a quién pertenecen.

  La cabecera —equipo, fecha, turno— no está en la plantilla porque no es del
  formulario: es la **clave** del registro, lo que decide a qué lotes alcanza.
*/

interface Props {
  documento: DocumentoPeriodico | null;
  registro: RegistroEquipo | null;
  equipos: Equipo[];
  alCerrar: () => void;
  alGuardar: () => void;
}


const hoy = () => new Date().toISOString().slice(0, 10);


function FormularioRegistro({
  documento,
  registro,
  equipos,
  alCerrar,
  alGuardar,
}: Props) {

  const [equipo, setEquipo] = useState(String(registro?.equipo ?? ""));
  const [fecha, setFecha] = useState(registro?.fecha ?? hoy());
  const [turno, setTurno] = useState(registro?.turno ?? "");
  const [hasta, setHasta] = useState(registro?.vigente_hasta ?? "");
  const [valores, setValores] = useState<Record<string, unknown>>(
    registro?.valores ?? {},
  );
  const [observacion, setObservacion] = useState(registro?.observacion ?? "");

  const [guardando, setGuardando] = useState(false);
  const [error, setError] = useState("");

  if (!documento) {
    return null;
  }

  const segunPrograma = documento.frecuencia === "segun_programa";

  const guardar = async (estado: "borrador" | "completado" | "observado") => {

    setError("");
    setGuardando(true);

    try {
      await guardarRegistroEquipo(registro?.id ?? null, {
        documento: documento.id,
        equipo: equipo ? Number(equipo) : null,
        fecha,
        turno,
        vigente_hasta: hasta || null,
        valores,
        observacion,
        estado,
      });

      alGuardar();
      alCerrar();

    } catch (e) {

      if (axios.isAxiosError(e) && e.response) {
        const cuerpo = e.response.data as Record<string, string[] | string>;
        setError(
          Object.entries(cuerpo)
            .map(([campo, msg]) =>
              campo === "non_field_errors" || campo === "detail"
                ? String(msg)
                : `${campo}: ${msg}`,
            )
            .join(" · "),
        );
      } else {
        setError("No se pudo conectar con el servidor.");
      }

      setGuardando(false);
    }
  };

  const campo =
    "w-full rounded-xl border border-slate-300 bg-white px-4 py-3 outline-none focus:border-green-600";

  return (
    <div className="fixed inset-0 z-50 flex items-start justify-center overflow-y-auto bg-slate-900/40 p-4 sm:p-8">

      <div className="w-full max-w-3xl rounded-2xl bg-white shadow-xl">

        <div className="flex items-start justify-between border-b border-slate-200 px-6 py-5">

          <div>

            <h2 className="text-lg font-semibold text-slate-800">
              {documento.nombre}
            </h2>

            <p className="mt-0.5 text-sm text-slate-600">
              {documento.codigo} · {documento.frecuencia_etiqueta ?? documento.frecuencia}
            </p>

          </div>

          <button
            type="button"
            onClick={alCerrar}
            className="rounded-lg p-1 text-slate-600 hover:bg-slate-100 hover:text-slate-700"
            aria-label="Cerrar"
          >
            <X className="h-5 w-5" />
          </button>

        </div>

        <div className="px-6 py-6">

          {/* La clave del registro: decide a qué lotes alcanza */}

          <div className="grid grid-cols-1 gap-5 sm:grid-cols-3">

            <label className="block">

              <span className="mb-1.5 block text-sm font-medium text-slate-700">
                Equipo
              </span>

              <select
                className={campo}
                value={equipo}
                onChange={(e) => setEquipo(e.target.value)}
              >
                <option value="">— sin equipo</option>
                {equipos.map((e) => (
                  <option key={e.id} value={e.id}>
                    {e.nombre}
                  </option>
                ))}
              </select>

            </label>

            <label className="block">

              <span className="mb-1.5 block text-sm font-medium text-slate-700">
                Fecha *
              </span>

              <input
                type="date"
                className={campo}
                value={fecha}
                onChange={(e) => setFecha(e.target.value)}
                required
              />

            </label>

            <label className="block">

              <span className="mb-1.5 block text-sm font-medium text-slate-700">
                Turno
              </span>

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

            </label>

            {segunPrograma && (
              <label className="block sm:col-span-3">

                <span className="mb-1.5 block text-sm font-medium text-slate-700">
                  Vigente hasta *
                </span>

                <input
                  type="date"
                  className={campo}
                  value={hasta}
                  onChange={(e) => setHasta(e.target.value)}
                  required
                />

                <span className="mt-1 block text-xs text-slate-600">
                  Este formulario es «según programa»: su período no se puede
                  deducir, así que sin esta fecha no cubriría ningún lote.
                </span>

              </label>
            )}

          </div>

          {/* El formulario, dibujado desde su plantilla */}

          <div className="mt-8 border-t border-slate-200 pt-6">

            {documento.plantilla.length === 0 ? (

              <p className="text-sm text-slate-600">
                Este documento todavía no tiene plantilla: se registra como
                atestación. La plantilla se define contra su formato real.
              </p>

            ) : (

              <div className="grid grid-cols-1 gap-5 sm:grid-cols-2">

                {documento.plantilla.map((campo) => (

                  <label key={campo.clave} className="block">

                    <span className="mb-1.5 block text-sm font-medium text-slate-700">
                      {campo.etiqueta}
                      {campo.req && <span className="ml-1 text-red-600">*</span>}
                      {campo.unidad && (
                        <span className="ml-1 font-normal text-slate-600">
                          ({campo.unidad})
                        </span>
                      )}
                    </span>

                    <CampoDePlantilla
                      campo={campo}
                      valor={valores[campo.clave]}
                      deshabilitado={guardando}
                      alCambiar={(valor: unknown) =>
                        setValores((previos) => ({
                          ...previos,
                          [campo.clave]: valor,
                        }))
                      }
                    />

                  </label>

                ))}

              </div>

            )}

          </div>

          <label className="mt-6 block">

            <span className="mb-1.5 block text-sm font-medium text-slate-700">
              Observación
            </span>

            <textarea
              className={campo}
              rows={2}
              value={observacion}
              onChange={(e) => setObservacion(e.target.value)}
            />

          </label>

          {error && (
            <div className="mt-6 rounded-xl bg-red-50 px-4 py-3 text-sm text-red-700">
              {error}
            </div>
          )}

          <div className="mt-8 flex flex-wrap justify-end gap-3">

            <button
              type="button"
              onClick={alCerrar}
              className="rounded-xl px-5 py-3 text-sm font-medium text-slate-600 hover:bg-slate-100"
            >
              Cancelar
            </button>

            <button
              type="button"
              disabled={guardando}
              onClick={() => void guardar("borrador")}
              className="rounded-xl border border-slate-200 px-5 py-3 text-sm font-medium text-slate-700 hover:bg-slate-50 disabled:opacity-60"
            >
              Guardar borrador
            </button>

            <button
              type="button"
              disabled={guardando}
              onClick={() => void guardar("observado")}
              className="rounded-xl border border-amber-200 bg-amber-50 px-5 py-3 text-sm font-medium text-amber-800 hover:bg-amber-100 disabled:opacity-60"
              title="Queda como alerta abierta y no cubre a ningún lote"
            >
              Marcar observado
            </button>

            <button
              type="button"
              disabled={guardando}
              onClick={() => void guardar("completado")}
              className="rounded-xl bg-green-700 px-6 py-3 text-sm font-semibold text-white hover:bg-green-800 disabled:opacity-60"
            >
              {guardando ? "Guardando…" : "Completar"}
            </button>

          </div>

        </div>

      </div>

    </div>
  );
}


export default FormularioRegistro;
