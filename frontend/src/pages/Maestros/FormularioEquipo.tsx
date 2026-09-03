import { useState } from "react";
import { AlertTriangle, X } from "lucide-react";
import axios from "axios";

import {
  crearEquipo,
  editarEquipo,
  type CatalogosSku,
  type Equipo,
} from "../../services/maestros.service";


/*
  Alta y edición de una máquina.

  `Consume leche del balance` **no es una etiqueta**: decide si los bloques de
  este equipo restan leche del plan. Un mismo código de producción se programa
  en el evaporador y en la línea que lo recibe; si los dos restaran, el balance
  contaría la misma leche dos veces y la semana parecería no cuadrar. Por eso
  el campo lleva su advertencia a la vista y no escondida en un `title`.

  El código no se edita una vez creado: la planificación lo referencia, y
  cambiarlo dejaría los bloques apuntando a un identificador que ya no existe.
*/

interface Props {
  equipo: Equipo | null;
  catalogos: CatalogosSku;
  alCerrar: () => void;
  alGuardar: () => void;
}


/** Sugiere un código a partir del nombre; el usuario puede cambiarlo. */
function codigoDesde(nombre: string): string {
  return nombre
    .toLowerCase()
    .normalize("NFD")
    .replace(/[̀-ͯ]/g, "")
    .replace(/[^a-z0-9]+/g, "_")
    .replace(/^_+|_+$/g, "")
    .slice(0, 40);
}


function FormularioEquipo({ equipo, catalogos, alCerrar, alGuardar }: Props) {

  const [nombre, setNombre] = useState(equipo?.nombre ?? "");
  const [codigo, setCodigo] = useState(equipo?.codigo ?? "");
  const [tipo, setTipo] = useState(equipo?.tipo ?? "evaporador");
  const [consume, setConsume] = useState(equipo?.consume_leche ?? false);
  const [consumeMateriales, setConsumeMateriales] = useState(
    equipo?.consume_materiales ?? false,
  );
  const [orden, setOrden] = useState(String(equipo?.orden ?? 0));
  const [activo, setActivo] = useState(equipo?.activo ?? true);

  const [codigoTocado, setCodigoTocado] = useState(false);
  const [guardando, setGuardando] = useState(false);
  const [error, setError] = useState("");

  const escribirNombre = (valor: string) => {
    setNombre(valor);

    // Mientras no lo toquen a mano, el código sigue al nombre.
    if (!equipo && !codigoTocado) {
      setCodigo(codigoDesde(valor));
    }
  };

  const guardar = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();

    setError("");
    setGuardando(true);

    const datos = {
      nombre,
      codigo,
      tipo,
      consume_leche: consume,
      consume_materiales: consumeMateriales,
      orden: Number(orden) || 0,
      activo,
    };

    try {

      if (equipo) {
        // El código no viaja en la edición: la planificación lo referencia y
        // cambiarlo dejaría los bloques apuntando a algo que ya no existe.
        const { nombre, tipo, consume_leche, consume_materiales, orden, activo } = datos;
        await editarEquipo(equipo.id, {
          nombre,
          tipo,
          consume_leche,
          consume_materiales,
          orden,
          activo,
        });
      } else {
        await crearEquipo(datos);
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
            {equipo ? "Editar máquina" : "Nueva máquina"}
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
                onChange={(e) => escribirNombre(e.target.value)}
                placeholder="Evaporador Scheffers 2"
                required
              />

            </label>

            <label className="block">

              <span className="mb-1.5 block text-sm font-medium text-slate-700">
                Código *
              </span>

              <input
                className={`${campo} ${equipo ? "bg-slate-50 text-slate-600" : ""}`}
                value={codigo}
                onChange={(e) => {
                  setCodigo(e.target.value);
                  setCodigoTocado(true);
                }}
                disabled={!!equipo}
                required
              />

              <span className="mt-1 block text-xs text-slate-600">
                {equipo
                  ? "No se cambia: la planificación referencia este código."
                  : "Se propone desde el nombre. Se puede editar antes de crear."}
              </span>

            </label>

            <div className="grid grid-cols-2 gap-4">

              <label className="block">

                <span className="mb-1.5 block text-sm font-medium text-slate-700">
                  Tipo
                </span>

                <select
                  className={campo}
                  value={tipo}
                  onChange={(e) => setTipo(e.target.value)}
                >
                  {catalogos.equipo_tipo.map((t) => (
                    <option key={t.valor} value={t.valor}>
                      {t.etiqueta}
                    </option>
                  ))}
                </select>

              </label>

              <label className="block">

                <span className="mb-1.5 block text-sm font-medium text-slate-700">
                  Orden en la carta
                </span>

                <input
                  type="number"
                  min="0"
                  className={campo}
                  value={orden}
                  onChange={(e) => setOrden(e.target.value)}
                />

              </label>

            </div>

            {/* La regla del balance */}

            <div
              className={`rounded-xl border p-4 ${
                consume ? "border-amber-200 bg-amber-50" : "border-slate-200 bg-slate-50"
              }`}
            >

              <label className="flex items-start gap-3">

                <input
                  type="checkbox"
                  className="mt-1"
                  checked={consume}
                  onChange={(e) => setConsume(e.target.checked)}
                />

                <span>

                  <span className="block text-sm font-medium text-slate-800">
                    Consume leche del balance
                  </span>

                  <span className="mt-1 block text-sm text-slate-600">
                    Solo los evaporadores. Una línea recibe lo que el evaporador
                    ya produjo: si también restara, el balance contaría la misma
                    leche dos veces.
                  </span>

                </span>

              </label>

              {consume && tipo !== "evaporador" && (
                <p className="mt-3 flex items-start gap-2 rounded-lg bg-amber-100 px-3 py-2 text-sm text-amber-900">
                  <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
                  Marcaste que consume leche en algo que no es un evaporador.
                  Revisa que no sea leche ya contada por el equipo que lo
                  alimenta.
                </p>
              )}

            </div>

            <div className={`rounded-xl border p-4 ${
              consumeMateriales ? "border-sky-200 bg-sky-50" : "border-slate-200 bg-slate-50"
            }`}>
              <label className="flex items-start gap-3">
                <input
                  type="checkbox"
                  className="mt-1"
                  checked={consumeMateriales}
                  onChange={(e) => setConsumeMateriales(e.target.checked)}
                />
                <span>
                  <span className="block text-sm font-medium text-slate-800">
                    Consume materiales de envase
                  </span>
                  <span className="mt-1 block text-sm text-slate-600">
                    Actívalo solo en el equipo final que descuenta sacos, cajas
                    u otros materiales del MRP. Una descremadora no lo utiliza.
                  </span>
                </span>
              </label>
            </div>

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
              {guardando ? "Guardando…" : equipo ? "Guardar cambios" : "Crear"}
            </button>

          </div>

        </form>

      </div>

    </div>
  );
}


export default FormularioEquipo;
