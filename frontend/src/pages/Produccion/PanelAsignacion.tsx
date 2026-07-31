import { useCallback, useEffect, useState } from "react";
import { Beaker, Info, Plus, Trash2 } from "lucide-react";
import axios from "axios";

import {
  asignarLeche,
  obtenerAsignacion,
  obtenerTrazabilidad,
  quitarAsignacion,
  type Asignacion,
  type Trazabilidad,
} from "../../services/produccion.service";

import { obtenerSilos, type Silo } from "../../services/recepcion.service";


/*
  De qué leche salió este lote.

  Aquí empieza la trazabilidad real. Un producto puede mezclar leche de varios
  estanques —lo normal cuando ninguno alcanza solo—, así que la asignación son
  N líneas: un silo y sus litros cada una.

  Los litros **los escribe Producción**. El sistema podría derivarlos de la
  receta, y de hecho muestra ese número al lado, pero como estimación: lo que
  se descuenta del estanque tiene que ser lo que realmente se sacó, o el saldo
  del silo deja de ser un saldo. La diferencia entre ambos es el rendimiento
  real del lote, que no se medía en ninguna parte.

  Se informa, no se bloquea. Una merma mayor de la prevista es algo que
  explicar, no algo que impedir.
*/

interface Props {
  loteId: number;
  /* El rol manda en el backend; esto solo evita ofrecer lo que se va a
     rechazar. */
  puedeEditar: boolean;
  /* Asignar mueve el saldo de los silos: el dashboard de arriba se entera. */
  alCambiar?: () => void;
}


const litros = new Intl.NumberFormat("es-CL", { maximumFractionDigits: 0 });


function mensajeDe(e: unknown, porDefecto: string): string {
  if (axios.isAxiosError(e)) {
    return (e.response?.data as { detail?: string })?.detail ?? porDefecto;
  }
  return porDefecto;
}


function Cifra({
  etiqueta,
  valor,
  nota,
  tono = "text-slate-800",
}: {
  etiqueta: string;
  valor: string;
  nota?: string;
  tono?: string;
}) {
  return (
    <div>
      <p className="text-xs text-slate-400">{etiqueta}</p>
      <p className={`mt-0.5 text-lg font-medium tabular-nums ${tono}`}>{valor}</p>
      {nota && <p className="text-xs text-slate-400">{nota}</p>}
    </div>
  );
}


function PanelAsignacion({ loteId, puedeEditar, alCambiar }: Props) {

  const [datos, setDatos] = useState<Asignacion | null>(null);
  const [silos, setSilos] = useState<Silo[]>([]);
  const [cargando, setCargando] = useState(true);
  const [error, setError] = useState("");
  const [guardando, setGuardando] = useState(false);

  /* Líneas que el usuario está escribiendo, todavía sin enviar. */
  const [nuevas, setNuevas] = useState<{ silo: string; litros: string }[]>([]);

  const [traza, setTraza] = useState<Trazabilidad | null>(null);
  const [verTraza, setVerTraza] = useState(false);

  const cargar = useCallback(async () => {
    try {
      setDatos(await obtenerAsignacion(loteId));
    } catch (e) {
      setError(mensajeDe(e, "No se pudo cargar la asignación de leche."));
    } finally {
      setCargando(false);
    }
  }, [loteId]);

  /* Se difiere igual que en la ficha: pintar el panel y cargar después, en
     vez de encadenar renders desde dentro del efecto. */
  useEffect(() => {
    const temporizador = setTimeout(cargar, 0);

    return () => clearTimeout(temporizador);
  }, [cargar]);

  useEffect(() => {
    obtenerSilos()
      .then(setSilos)
      // Sin la lista no se puede elegir silo, pero lo ya asignado igual se ve.
      .catch(() => setSilos([]));
  }, []);

  const agregar = () => setNuevas((n) => [...n, { silo: "", litros: "" }]);

  const editarLinea = (i: number, campo: "silo" | "litros", valor: string) =>
    setNuevas((n) => n.map((l, j) => (j === i ? { ...l, [campo]: valor } : l)));

  const quitarLinea = (i: number) =>
    setNuevas((n) => n.filter((_, j) => j !== i));

  const guardar = async () => {
    const lineas = nuevas
      .filter((l) => l.silo && l.litros)
      .map((l) => ({ silo: Number(l.silo), litros: Number(l.litros) }));

    if (lineas.length === 0) {
      setError("Indica al menos un silo con sus litros.");
      return;
    }

    setGuardando(true);
    setError("");

    try {
      setDatos(await asignarLeche(loteId, lineas));
      setNuevas([]);
      setTraza(null);
      alCambiar?.();
    } catch (e) {
      setError(mensajeDe(e, "No se pudo registrar la asignación."));
    } finally {
      setGuardando(false);
    }
  };

  const quitar = async (movimientoId: number) => {
    setGuardando(true);
    setError("");

    try {
      setDatos(await quitarAsignacion(loteId, movimientoId));
      setTraza(null);
      alCambiar?.();
    } catch (e) {
      setError(mensajeDe(e, "No se pudo quitar la línea."));
    } finally {
      setGuardando(false);
    }
  };

  const mostrarTraza = async () => {
    setVerTraza((v) => !v);

    if (!traza) {
      try {
        setTraza(await obtenerTrazabilidad(loteId));
      } catch (e) {
        setError(mensajeDe(e, "No se pudo cargar la trazabilidad."));
      }
    }
  };

  if (cargando) {
    return (
      <p className="text-sm text-slate-400">Cargando la asignación de leche…</p>
    );
  }

  if (!datos) {
    return <p className="text-sm text-red-700">{error}</p>;
  }

  const editable = puedeEditar && datos.editable;
  /* Solo se pueden retirar líneas mientras el lote sigue en la línea: después
     es histórico, y un asiento se corrige con un ajuste, no borrándolo. */
  const sePuedeQuitar = editable && datos.estado === "en_proceso";

  return (

    <div className="border-t border-slate-200 pt-5">

      <div className="flex items-start justify-between gap-3">

        <div>

          <h3 className="text-sm font-medium text-slate-700">
            Leche asignada
          </h3>

          <p className="mt-0.5 text-xs text-slate-500">
            De qué estanques salió la leche de este lote. Puede ser más de uno.
          </p>

        </div>

        {datos.lineas.length > 0 && (
          <button
            type="button"
            onClick={() => void mostrarTraza()}
            className="shrink-0 rounded-xl border border-slate-200 px-3 py-1.5 text-xs font-medium text-slate-600 hover:bg-slate-50"
          >
            {verTraza ? "Ocultar trazabilidad" : "Ver trazabilidad"}
          </button>
        )}

      </div>

      {/* Asignado vs. teórico */}

      <div className="mt-4 grid grid-cols-2 gap-4 rounded-xl bg-slate-50 p-4 sm:grid-cols-4">

        <Cifra
          etiqueta="Asignado"
          valor={`${litros.format(datos.asignado)} L`}
          nota="lo que salió del silo"
        />

        <Cifra
          etiqueta="Según receta"
          valor={
            datos.teorico == null ? "—" : `${litros.format(datos.teorico)} L`
          }
          nota={datos.teorico == null ? "sin receta vigente" : "estimación"}
        />

        {datos.diferencia != null && datos.consumo_pct != null && (
          <Cifra
            etiqueta="Consumo vs. previsto"
            valor={`${datos.consumo_pct.toLocaleString("es-CL")}%`}
            tono={datos.consumo_pct > 100 ? "text-amber-700" : "text-slate-800"}
            nota={`${datos.diferencia > 0 ? "+" : ""}${litros.format(
              datos.diferencia,
            )} L · se usó ${datos.diferencia > 0 ? "más" : "menos"} de lo previsto`}
          />
        )}

        <Cifra
          etiqueta="Rendimiento"
          valor={
            datos.litros_por_kg == null
              ? "—"
              : `${datos.litros_por_kg.toLocaleString("es-CL")} L/kg`
          }
          nota={
            datos.litros_por_kg_receta == null
              ? "leche por kilo producido"
              : `receta: ${datos.litros_por_kg_receta.toLocaleString("es-CL")} L/kg`
          }
        />

      </div>

      {/* Líneas ya registradas */}

      {datos.lineas.length === 0 ? (

        <p className="mt-4 text-sm text-slate-500">
          Sin asignar. Mientras no se declare de qué silos salió la leche, este
          lote no tiene trazabilidad hacia las recepciones.
        </p>

      ) : (

        <ul className="mt-4 divide-y divide-slate-100 rounded-xl border border-slate-200">

          {datos.lineas.map((l) => (

            <li key={l.id} className="flex items-center gap-3 px-4 py-2.5 text-sm">

              <Beaker className="h-4 w-4 shrink-0 text-slate-400" />

              <span className="font-medium text-slate-700">{l.silo_codigo}</span>

              <span className="tabular-nums text-slate-800">
                {litros.format(l.litros)} L
              </span>

              <span className="ml-auto text-xs text-slate-400">
                {new Date(l.fecha_hora).toLocaleString("es-CL", {
                  dateStyle: "short",
                  timeStyle: "short",
                })}
              </span>

              {sePuedeQuitar && (
                <button
                  type="button"
                  disabled={guardando}
                  onClick={() => void quitar(l.id)}
                  title="Quitar esta línea"
                  className="rounded-lg p-1 text-slate-400 hover:bg-red-50 hover:text-red-600 disabled:opacity-50"
                >
                  <Trash2 className="h-4 w-4" />
                </button>
              )}

            </li>

          ))}

        </ul>

      )}

      {/* Por qué no se puede tocar */}

      {datos.motivo_bloqueo && (
        <p className="mt-3 flex items-start gap-2 rounded-xl bg-slate-50 px-4 py-3 text-sm text-slate-600">
          <Info className="mt-0.5 h-4 w-4 shrink-0 text-slate-400" />
          {datos.motivo_bloqueo}
        </p>
      )}

      {/* Alta de líneas */}

      {editable && (

        <div className="mt-4">

          {nuevas.map((linea, i) => (

            <div key={i} className="mb-2 flex items-center gap-2">

              <select
                value={linea.silo}
                onChange={(e) => editarLinea(i, "silo", e.target.value)}
                className="flex-1 rounded-xl border border-slate-200 px-3 py-2 text-sm text-slate-800 focus:border-green-500 focus:outline-none"
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
                value={linea.litros}
                onChange={(e) => editarLinea(i, "litros", e.target.value)}
                placeholder="Litros"
                className="w-32 rounded-xl border border-slate-200 px-3 py-2 text-sm tabular-nums text-slate-800 focus:border-green-500 focus:outline-none"
              />

              <button
                type="button"
                onClick={() => quitarLinea(i)}
                title="Descartar esta línea"
                className="rounded-lg p-2 text-slate-400 hover:bg-slate-100"
              >
                <Trash2 className="h-4 w-4" />
              </button>

            </div>

          ))}

          <div className="flex flex-wrap gap-2">

            <button
              type="button"
              onClick={agregar}
              className="flex items-center gap-1.5 rounded-xl border border-slate-200 px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50"
            >
              <Plus className="h-4 w-4" />
              Agregar silo
            </button>

            {nuevas.length > 0 && (
              <button
                type="button"
                disabled={guardando}
                onClick={() => void guardar()}
                className="rounded-xl bg-green-600 px-4 py-2 text-sm font-medium text-white hover:bg-green-700 disabled:opacity-50"
              >
                {guardando ? "Registrando…" : "Registrar asignación"}
              </button>
            )}

          </div>

          <p className="mt-2 text-xs text-slate-400">
            Los litros son los que realmente se tomaron del estanque, no los que
            dice la receta: es lo que se descuenta del saldo del silo.
          </p>

        </div>

      )}

      {error && (
        <p className="mt-3 rounded-xl bg-red-50 px-4 py-3 text-sm text-red-700">
          {error}
        </p>
      )}

      {/* Trazabilidad */}

      {verTraza && traza && (

        <div className="mt-4 rounded-xl border border-slate-200 p-4">

          <h4 className="text-sm font-medium text-slate-700">
            Recepciones candidatas
          </h4>

          <p className="mt-0.5 text-xs text-slate-500">{traza.nota}</p>

          {traza.tramos.length === 0 ? (

            <p className="mt-3 text-sm text-slate-500">
              No hay recepciones registradas en esos silos antes de la
              asignación.
            </p>

          ) : (

            traza.tramos.map((tramo, i) => (

              <div key={i} className="mt-3">

                <p className="text-xs font-medium text-slate-600">
                  {tramo.silo_codigo} · {litros.format(tramo.litros)} L
                </p>

                {tramo.recepciones.length === 0 ? (

                  <p className="mt-1 text-sm text-slate-500">
                    Sin recepciones previas en este estanque.
                  </p>

                ) : (

                  <ul className="mt-1 space-y-1">
                    {tramo.recepciones.map((r) => (
                      <li key={r.id} className="text-sm text-slate-700">
                        <span className="text-slate-400">{r.fecha}</span>
                        {" · "}
                        guía {r.guia || "—"}
                        {" · "}
                        <span className="tabular-nums">
                          {litros.format(Number(r.litros))} L
                        </span>
                        {r.procedencia && (
                          <span className="text-slate-500"> · {r.procedencia}</span>
                        )}
                        {r.vehiculo && (
                          <span className="text-slate-400"> · {r.vehiculo}</span>
                        )}
                      </li>
                    ))}
                  </ul>

                )}

              </div>

            ))

          )}

        </div>

      )}

    </div>

  );
}


export default PanelAsignacion;
