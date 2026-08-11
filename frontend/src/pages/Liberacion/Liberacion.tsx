import { useCallback, useEffect, useState } from "react";
import { AlertTriangle, ShieldCheck } from "lucide-react";

import {
  buscarExpedientes,
  ESTADOS_LIBERACION,
  type FilaExpediente,
} from "../../services/calidad.service";

import { kilos } from "../../services/produccion.service";

import Expediente from "./Expediente";


/*
  Liberación de producto.

  La pantalla de Calidad: qué lotes esperan decisión y qué le falta a cada uno.

  El orden importa. Arriba van los que ya se pueden firmar y los que solo
  pueden salir por concesión, porque son los que esperan a una persona; los
  que están a medias van después. Un listado por fecha obligaría a buscar el
  trabajo pendiente entre lo que ya está resuelto.
*/


const ESTILO_LIBERACION: Record<string, string> = {
  pendiente: "bg-slate-100 text-slate-600",
  en_revision: "bg-blue-50 text-blue-700",
  liberado: "bg-green-50 text-green-700",
  liberado_concesion: "bg-amber-50 text-amber-800",
  rechazado: "bg-red-50 text-red-700",
};

const ESTILO_CALIDAD: Record<string, string> = {
  conforme: "bg-green-50 text-green-700",
  no_conforme: "bg-red-50 text-red-700",
  sin_analisis: "bg-slate-100 text-slate-500",
  sin_especificacion: "bg-slate-100 text-slate-500",
};


/** Lo accionable primero: lo que espera a una persona, no a un dato. */
function prioridad(fila: FilaExpediente): number {
  if (fila.liberacion?.liberado) return 3;
  if (fila.permitido) return 0;
  if (fila.via_concesion) return 1;
  return 2;
}


function Liberacion() {

  const [filas, setFilas] = useState<FilaExpediente[]>([]);
  const [cargando, setCargando] = useState(true);
  const [error, setError] = useState("");

  const [filtroEstado, setFiltroEstado] = useState("");
  const [loteAbierto, setLoteAbierto] = useState<number | null>(null);

  /* El listado viene paginado desde el servidor: armar el expediente de cada
     lote es caro, y sin techo la pantalla pedía el histórico entero. */
  const [pagina, setPagina] = useState(1);
  const [total, setTotal] = useState(0);
  const [hayMas, setHayMas] = useState(false);

  const cargar = useCallback(async () => {

    setCargando(true);
    setError("");

    try {
      const datos = await buscarExpedientes({ estado: filtroEstado, pagina });

      setFilas([...datos.resultados].sort((a, b) => prioridad(a) - prioridad(b)));
      setTotal(datos.total);
      setHayMas(datos.hay_mas);

    } catch {
      setError("No se pudo cargar el listado.");
    } finally {
      setCargando(false);
    }

  }, [filtroEstado, pagina]);

  // Diferido: agrupa los cambios de filtro en una sola consulta y evita
  // actualizar el estado dentro del propio efecto.
  useEffect(() => {

    const temporizador = setTimeout(cargar, 150);

    return () => clearTimeout(temporizador);

  }, [cargar]);

  if (loteAbierto !== null) {
    return (
      <Expediente
        loteId={loteAbierto}
        alVolver={() => {
          setLoteAbierto(null);
          void cargar();
        }}
      />
    );
  }

  const porFirmar = filas.filter((f) => f.permitido || f.via_concesion).length;

  return (
    <div className="space-y-6">

      <div className="flex flex-wrap items-end justify-between gap-4">

        <div>

          <h1 className="text-2xl font-semibold text-slate-800">
            Liberación de producto
          </h1>

          {/* Se dice «de cuántos»: con solo el recuento de la página, la
              pantalla afirmaría que el trabajo pendiente es el que se ve. */}
          <p className="mt-1 text-sm text-slate-500">
            {cargando
              ? "Cargando…"
              : `${filas.length} de ${total} lote(s) · ${porFirmar} esperando decisión en esta página`}
          </p>

        </div>

        <select
          value={filtroEstado}
          onChange={(e) => setFiltroEstado(e.target.value)}
          className="rounded-xl border border-slate-200 px-3 py-2 text-sm text-slate-700 focus:border-green-500 focus:outline-none"
        >
          <option value="">Todos los estados</option>

          {ESTADOS_LIBERACION.map((e) => (
            <option key={e.valor} value={e.valor}>{e.etiqueta}</option>
          ))}

        </select>

      </div>

      {error && (
        <p className="rounded-xl bg-red-50 px-4 py-3 text-sm text-red-700">{error}</p>
      )}

      {!cargando && filas.length === 0 && !error && (
        <p className="rounded-2xl border border-slate-200 bg-white px-5 py-8 text-center text-sm text-slate-500">
          No hay lotes que liberar. Aparecen aquí en cuanto Producción cierra uno.
        </p>
      )}

      <div className="overflow-hidden rounded-2xl border border-slate-200 bg-white">

        <div className="overflow-x-auto">

          <table className="w-full text-sm">

            <thead className="border-b border-slate-200 bg-slate-50 text-left text-xs uppercase tracking-wide text-slate-500">

              <tr>
                <th className="px-5 py-3 font-medium">Lote</th>
                <th className="px-5 py-3 font-medium">Producto</th>
                <th className="px-5 py-3 font-medium">Fecha</th>
                <th className="px-5 py-3 text-right font-medium">Kilos</th>
                <th className="px-5 py-3 font-medium">Checklist</th>
                <th className="px-5 py-3 font-medium">Calidad</th>
                <th className="px-5 py-3 font-medium">Estado</th>
              </tr>

            </thead>

            <tbody className="divide-y divide-slate-100">

              {filas.map((fila) => (

                <tr
                  key={fila.lote.id}
                  onClick={() => setLoteAbierto(fila.lote.id)}
                  className="cursor-pointer hover:bg-slate-50"
                >

                  <td className="px-5 py-3">

                    <div className="flex items-center gap-2">

                      <span className="font-medium text-slate-800">
                        {fila.lote.codigo_lote}
                      </span>

                      {fila.permitido && (
                        <ShieldCheck
                          className="h-4 w-4 text-green-600"
                          aria-label="Se puede liberar"
                        />
                      )}

                      {fila.via_concesion && (
                        <AlertTriangle
                          className="h-4 w-4 text-amber-600"
                          aria-label="Solo por concesión"
                        />
                      )}

                    </div>

                  </td>

                  <td className="px-5 py-3 text-slate-600">
                    {fila.lote.producto_nombre}
                    <span className="block text-xs text-slate-400">
                      {fila.lote.mandante_nombre}
                    </span>
                  </td>

                  <td className="px-5 py-3 text-slate-600">{fila.lote.fecha}</td>

                  <td className="px-5 py-3 text-right text-slate-600">
                    {kilos(fila.lote.kg_producidos)}
                  </td>

                  <td className="px-5 py-3">

                    <div className="flex items-center gap-2">

                      <div className="h-1.5 w-16 overflow-hidden rounded-full bg-slate-100">
                        <div
                          className={`h-full rounded-full ${
                            fila.avance.completo ? "bg-green-600" : "bg-slate-400"
                          }`}
                          style={{ width: `${fila.avance.pct}%` }}
                        />
                      </div>

                      <span className="text-xs text-slate-500">
                        {fila.avance.completados}/{fila.avance.total}
                      </span>

                    </div>

                  </td>

                  <td className="px-5 py-3">

                    <span
                      className={`rounded-full px-2.5 py-1 text-xs font-medium ${
                        ESTILO_CALIDAD[fila.calidad?.resultado || "sin_analisis"]
                      }`}
                    >
                      {fila.calidad?.etiqueta || "Sin análisis"}
                    </span>

                  </td>

                  <td className="px-5 py-3">

                    <span
                      className={`rounded-full px-2.5 py-1 text-xs font-medium ${
                        ESTILO_LIBERACION[fila.liberacion?.estado || "pendiente"]
                      }`}
                    >
                      {fila.liberacion?.estado_etiqueta || "Pendiente"}
                    </span>

                  </td>

                </tr>

              ))}

            </tbody>

          </table>

        </div>

        {(pagina > 1 || hayMas) && (
          <div className="flex items-center justify-between border-t border-slate-200 px-5 py-4">
            <button
              type="button"
              onClick={() => setPagina((p) => Math.max(1, p - 1))}
              disabled={pagina <= 1}
              className="rounded-lg px-3 py-2 text-sm font-medium text-slate-600 hover:bg-slate-100 disabled:opacity-30"
            >
              Anterior
            </button>

            <span className="text-xs font-medium text-slate-500">
              Página {pagina}
            </span>

            <button
              type="button"
              onClick={() => setPagina((p) => p + 1)}
              disabled={!hayMas}
              className="rounded-lg px-3 py-2 text-sm font-medium text-slate-600 hover:bg-slate-100 disabled:opacity-30"
            >
              Siguiente
            </button>
          </div>
        )}

      </div>

    </div>
  );
}


export default Liberacion;
