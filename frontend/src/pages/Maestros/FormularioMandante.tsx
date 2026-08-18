import { useState } from "react";
import { X } from "lucide-react";
import axios from "axios";

import {
  crearMandante,
  editarMandante,
  type CatalogosSku,
  type Mandante,
} from "../../services/maestros.service";


/*
  Alta y edición de un mandante.

  El código de cliente es el segmento del SKU que dice de quién es el producto.
  Se guarda aquí y no en cada producto porque el mandante ya lo sabe: pedirlo
  dos veces es como las dos copias terminan diciendo cosas distintas.

  Puede quedar vacío —un mandante recién creado, o uno que no aparece en el
  catálogo del SKU— y entonces sus productos no generan código. Se avisa, no se
  impide: cargar el maestro a medias tiene que ser posible.
*/

interface Props {
  mandante: Mandante | null;
  catalogos: CatalogosSku;
  alCerrar: () => void;
  alGuardar: () => void;
}


function FormularioMandante({ mandante, catalogos, alCerrar, alGuardar }: Props) {

  const [nombre, setNombre] = useState(mandante?.nombre ?? "");
  const [codigoCliente, setCodigoCliente] = useState(mandante?.codigo_cliente ?? "");
  const [activo, setActivo] = useState(mandante?.activo ?? true);

  const [guardando, setGuardando] = useState(false);
  const [error, setError] = useState("");

  const guardar = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();

    setError("");
    setGuardando(true);

    try {

      if (mandante) {
        await editarMandante(mandante.id, {
          nombre,
          codigo_cliente: codigoCliente,
          activo,
        });
      } else {
        await crearMandante({ nombre, codigo_cliente: codigoCliente });
      }

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

      <div className="w-full max-w-xl rounded-2xl bg-white shadow-xl">

        <div className="flex items-center justify-between border-b border-slate-200 px-6 py-5">

          <h2 className="text-lg font-semibold text-slate-800">
            {mandante ? "Editar mandante" : "Nuevo mandante"}
          </h2>

          <button
            type="button"
            onClick={alCerrar}
            className="rounded-lg p-1 text-slate-600 hover:bg-slate-100 hover:text-slate-700"
            aria-label="Cerrar"
          >
            <X className="h-5 w-5" />
          </button>

        </div>

        <form onSubmit={guardar} className="px-6 py-6">

          <div className="space-y-5">

            <label className="block">

              <span className="mb-1.5 block text-sm font-medium text-slate-700">
                Nombre *
              </span>

              <input
                className={campo}
                value={nombre}
                onChange={(e) => setNombre(e.target.value)}
                required
              />

            </label>

            <label className="block">

              <span className="mb-1.5 block text-sm font-medium text-slate-700">
                Cliente en el SKU
              </span>

              <select
                className={campo}
                value={codigoCliente}
                onChange={(e) => setCodigoCliente(e.target.value)}
              >
                <option value="">— sin código</option>
                {catalogos.cliente.map((o) => (
                  <option key={o.valor} value={o.valor}>
                    {o.etiqueta}
                  </option>
                ))}
              </select>

              <span className="mt-1 block text-xs text-slate-600">
                {codigoCliente
                  ? "Es el segmento del SKU que dice de quién es el producto."
                  : "Sin esto, los productos de este mandante no generan SKU."}
              </span>

            </label>

            <label className="flex items-center gap-2 text-sm text-slate-700">
              <input
                type="checkbox"
                checked={activo}
                onChange={(e) => setActivo(e.target.checked)}
              />
              Activo
            </label>

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
              {guardando ? "Guardando…" : mandante ? "Guardar cambios" : "Crear"}
            </button>

          </div>

        </form>

      </div>

    </div>
  );
}


export default FormularioMandante;
