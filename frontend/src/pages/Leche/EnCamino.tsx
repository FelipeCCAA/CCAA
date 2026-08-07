import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Truck } from "lucide-react";

import {
  obtenerCargasPendientes, type CargaEsperada,
} from "../../services/recoleccion.service";

/*
  Cargas cerradas en el predio que todavía no se recepcionaron en planta.

  Este dato ya existía —`CargaModulo.recepcion_planta` es el puente en el
  modelo, y `obtenerCargasPendientes` estaba escrito— pero solo se usaba
  **dentro del desplegable** del formulario de recepción: había que empezar a
  registrar una llegada para saber qué venía en camino. Nadie podía mirar la
  lista.

  Es la única pestaña que mira las dos mitades a la vez, y por eso justifica
  que recolección y recepción vivan en la misma sección.
*/

const formato = new Intl.NumberFormat("es-CL", { maximumFractionDigits: 0 });


function EnCamino() {
  const [cargas, setCargas] = useState<CargaEsperada[] | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    const t = setTimeout(() => {
      void obtenerCargasPendientes()
        .then(setCargas)
        .catch(() => setError("No se pudo cargar lo que viene en camino."));
    }, 0);

    return () => clearTimeout(t);
  }, []);

  if (error) {
    return (
      <p className="rounded-2xl border border-rose-200 bg-rose-50 px-5 py-4 text-sm text-rose-700">
        {error}
      </p>
    );
  }

  const total = (cargas ?? []).reduce((suma, c) => suma + Number(c.litros), 0);

  return (
    <section className="overflow-hidden rounded-2xl border border-slate-200 bg-white">

      <div className="flex flex-wrap items-center justify-between gap-4 border-b border-slate-200 px-5 py-5">
        <div>
          <h2 className="font-semibold text-slate-900">En camino a planta</h2>
          <p className="mt-1 text-sm text-slate-500">
            Cargas cerradas en el predio que todavía no se recepcionaron.
          </p>
        </div>
        {cargas && cargas.length > 0 && (
          <p className="text-sm font-semibold tabular-nums text-slate-700">
            {formato.format(total)} L en {cargas.length}{" "}
            {cargas.length === 1 ? "carga" : "cargas"}
          </p>
        )}
      </div>

      {cargas === null ? (
        <p className="py-10 text-center text-sm text-slate-400">Cargando…</p>
      ) : cargas.length === 0 ? (
        <div className="px-6 py-16 text-center">
          <span className="mx-auto flex h-11 w-11 items-center justify-center rounded-full bg-slate-100 text-slate-400">
            <Truck className="h-5 w-5" />
          </span>
          <p className="mt-4 text-sm font-medium text-slate-700">
            No hay cargas pendientes de llegar
          </p>
          <p className="mt-1 text-xs text-slate-400">
            Aparecen aquí en cuanto se registra una carga en{" "}
            <Link to="../rutas" className="underline">Rutas</Link>.
          </p>
        </div>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full min-w-[820px] text-left text-sm">

            <thead className="bg-slate-50/80 text-[11px] font-semibold uppercase tracking-[0.08em] text-slate-400">
              <tr>
                <th className="px-5 py-3">Carga</th>
                <th className="px-5 py-3">Origen</th>
                <th className="px-5 py-3">Módulo</th>
                <th className="px-5 py-3">Camión</th>
                <th className="px-5 py-3 text-right">Litros</th>
              </tr>
            </thead>

            <tbody className="divide-y divide-slate-100">
              {cargas.map((c) => (
                <tr key={c.id} className="transition hover:bg-slate-50/70">
                  <td className="px-5 py-4 font-semibold text-slate-800">{c.codigo}</td>
                  <td className="px-5 py-4">
                    <p className="text-slate-700">{c.predio || "—"}</p>
                    <p className="mt-1 text-xs text-slate-400">{c.proveedor || "—"}</p>
                  </td>
                  <td className="px-5 py-4 text-slate-700">
                    {c.modulo}
                    {c.estanque_origen && (
                      <span className="ml-1 text-xs text-slate-400">
                        · {c.estanque_origen}
                      </span>
                    )}
                  </td>
                  <td className="px-5 py-4 text-slate-700">
                    {c.vehiculo_placa || "—"}
                  </td>
                  <td className="px-5 py-4 text-right font-semibold tabular-nums text-slate-800">
                    {formato.format(Number(c.litros))} L
                  </td>
                </tr>
              ))}
            </tbody>

          </table>
        </div>
      )}

      <p className="border-t border-slate-100 px-5 py-3 text-xs text-slate-400">
        Una carga sale de esta lista cuando se registra su llegada en{" "}
        <Link to="../muestreo" className="underline">Muestreo</Link>, eligiéndola
        en el formulario de nueva recepción.
      </p>

    </section>
  );
}


export default EnCamino;
