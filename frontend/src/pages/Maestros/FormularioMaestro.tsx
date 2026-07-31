import { useState } from "react";
import { X } from "lucide-react";
import axios from "axios";


/*
  Formulario genérico de un maestro, descrito por datos.

  Los maestros simples —silos, camiones, códigos de producción— son la misma
  pantalla con otros campos. En vez de tres componentes casi iguales, el
  formulario recibe la **descripción de sus campos** y los dibuja. Es el mismo
  principio que ya gobierna los formularios de calidad: el formulario es dato,
  no código (MODELO_DATOS.md §2.6).

  Los productos, los mandantes y las máquinas **no** usan esto: tienen reglas
  propias que mostrar —el SKU derivado, el cliente que aporta el mandante, la
  advertencia del balance— y meterlas aquí convertiría el genérico en un nudo
  de casos particulares.
*/

export type TipoCampo = "texto" | "numero" | "select" | "checkbox";

export interface Campo {
  clave: string;
  etiqueta: string;
  tipo: TipoCampo;
  requerido?: boolean;
  ayuda?: string;
  /* Para los select. */
  opciones?: { valor: string | number; etiqueta: string }[];
  /* Se muestra pero no se edita: p. ej. un código que otros registros
     referencian. */
  soloLecturaAlEditar?: boolean;
  /* Ancho en la rejilla de dos columnas. */
  ancho?: 1 | 2;
}

interface Props {
  titulo: string;
  campos: Campo[];
  valores: Record<string, unknown>;
  /* null al crear. */
  edicion: boolean;
  alCerrar: () => void;
  alGuardar: (datos: Record<string, unknown>) => Promise<unknown>;
  alTerminar: () => void;
}


function FormularioMaestro({
  titulo,
  campos,
  valores,
  edicion,
  alCerrar,
  alGuardar,
  alTerminar,
}: Props) {

  const [datos, setDatos] = useState<Record<string, unknown>>(valores);
  const [guardando, setGuardando] = useState(false);
  const [error, setError] = useState("");

  const escribir = (clave: string, valor: unknown) =>
    setDatos((d) => ({ ...d, [clave]: valor }));

  const enviar = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();

    setError("");
    setGuardando(true);

    // Un campo de solo lectura en edición no viaja: lo referencian otros
    // registros y mandarlo invitaría a cambiarlo por accidente.
    const carga: Record<string, unknown> = {};

    for (const campo of campos) {
      if (edicion && campo.soloLecturaAlEditar) continue;

      const valor = datos[campo.clave];

      // Un número vacío es "sin dato", no cero.
      carga[campo.clave] =
        campo.tipo === "numero" && (valor === "" || valor === null)
          ? null
          : valor;
    }

    try {
      await alGuardar(carga);
      alTerminar();
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

  const clase =
    "w-full rounded-xl border border-slate-300 bg-white px-4 py-3 outline-none focus:border-green-600";

  return (
    <div className="fixed inset-0 z-50 flex items-start justify-center overflow-y-auto bg-slate-900/40 p-4 sm:p-8">

      <div className="w-full max-w-2xl rounded-2xl bg-white shadow-xl">

        <div className="flex items-center justify-between border-b border-slate-200 px-6 py-5">

          <h2 className="text-lg font-semibold text-slate-800">{titulo}</h2>

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

          <div className="grid grid-cols-1 gap-5 sm:grid-cols-2">

            {campos.map((campo) => {

              const bloqueado = edicion && campo.soloLecturaAlEditar;
              const valor = datos[campo.clave];

              if (campo.tipo === "checkbox") {
                return (
                  <label
                    key={campo.clave}
                    className="flex items-center gap-2 text-sm text-slate-700 sm:col-span-2"
                  >
                    <input
                      type="checkbox"
                      checked={Boolean(valor)}
                      onChange={(e) => escribir(campo.clave, e.target.checked)}
                    />
                    {campo.etiqueta}
                  </label>
                );
              }

              return (
                <label
                  key={campo.clave}
                  className={`block ${campo.ancho === 2 ? "sm:col-span-2" : ""}`}
                >

                  <span className="mb-1.5 block text-sm font-medium text-slate-700">
                    {campo.etiqueta}
                    {campo.requerido && " *"}
                  </span>

                  {campo.tipo === "select" ? (

                    <select
                      className={clase}
                      value={String(valor ?? "")}
                      onChange={(e) => escribir(campo.clave, e.target.value)}
                      required={campo.requerido}
                      disabled={bloqueado}
                    >
                      <option value="">—</option>
                      {(campo.opciones ?? []).map((o) => (
                        <option key={o.valor} value={o.valor}>
                          {o.etiqueta}
                        </option>
                      ))}
                    </select>

                  ) : (

                    <input
                      type={campo.tipo === "numero" ? "number" : "text"}
                      step={campo.tipo === "numero" ? "any" : undefined}
                      className={`${clase} ${bloqueado ? "bg-slate-50 text-slate-500" : ""}`}
                      value={String(valor ?? "")}
                      onChange={(e) => escribir(campo.clave, e.target.value)}
                      required={campo.requerido}
                      disabled={bloqueado}
                    />

                  )}

                  {(campo.ayuda || bloqueado) && (
                    <span className="mt-1 block text-xs text-slate-400">
                      {bloqueado
                        ? "No se cambia: otros registros lo referencian."
                        : campo.ayuda}
                    </span>
                  )}

                </label>
              );
            })}

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
              {guardando ? "Guardando…" : edicion ? "Guardar cambios" : "Crear"}
            </button>

          </div>

        </form>

      </div>

    </div>
  );
}


export default FormularioMaestro;
