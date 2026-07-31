import { useCallback, useEffect, useState } from "react";
import { AlertTriangle, Check, ClipboardList, Plus } from "lucide-react";

import {
  buscarRegistrosEquipo,
  obtenerDocumentosPeriodicos,
  type DocumentoPeriodico,
  type RegistroEquipo,
} from "../../services/registros.service";

import { obtenerEquipos, type Equipo } from "../../services/maestros.service";
import { puedeEscribir } from "../../services/sesion";

import FormularioRegistro from "./FormularioRegistro";


/*
  Registros de planta: aseos, inspecciones y controles de máquina.

  Se organiza **por equipo y fecha**, no por lote, porque es como se trabaja:
  quien asea una torre no piensa en qué lotes va a cubrir. El checklist de
  liberación los consume solo — un aseo semanal se llena una vez y cubre todos
  los lotes de esa semana.

  Aquí solo aparecen los documentos cuya frecuencia NO es «por lote». Los que
  sí lo son viven en el expediente del lote, que es donde tienen sentido.
*/

const ESTILO_ESTADO: Record<string, string> = {
  completado: "bg-green-50 text-green-700",
  observado: "bg-amber-50 text-amber-800",
  borrador: "bg-slate-100 text-slate-600",
};


/** Los últimos 30 días, que es el rango en que se trabaja normalmente. */
function haceUnMes(): string {
  const d = new Date();
  d.setDate(d.getDate() - 30);

  return d.toISOString().slice(0, 10);
}


function Registros() {

  const [documentos, setDocumentos] = useState<DocumentoPeriodico[]>([]);
  const [equipos, setEquipos] = useState<Equipo[]>([]);
  const [registros, setRegistros] = useState<RegistroEquipo[]>([]);

  const [documento, setDocumento] = useState("");
  const [equipo, setEquipo] = useState("");
  const [desde, setDesde] = useState(haceUnMes());

  const [cargando, setCargando] = useState(true);
  const [error, setError] = useState("");

  const [editando, setEditando] = useState<RegistroEquipo | null>(null);
  const [nuevo, setNuevo] = useState<DocumentoPeriodico | null>(null);

  const puedeEditar = puedeEscribir("produccion") || puedeEscribir("calidad");

  const cargar = useCallback(async () => {

    setCargando(true);
    setError("");

    try {
      setRegistros(
        await buscarRegistrosEquipo({
          documento: documento ? Number(documento) : undefined,
          equipo: equipo ? Number(equipo) : undefined,
          desde,
        }),
      );
    } catch {
      setError("No se pudieron cargar los registros.");
    } finally {
      setCargando(false);
    }

  }, [documento, equipo, desde]);

  useEffect(() => {
    const t = setTimeout(cargar, 250);

    return () => clearTimeout(t);
  }, [cargar]);

  useEffect(() => {
    // Los maestros van aparte: si fallan, el listado igual se ve.
    obtenerDocumentosPeriodicos().then(setDocumentos).catch(() => setDocumentos([]));
    obtenerEquipos().then(setEquipos).catch(() => setEquipos([]));
  }, []);

  const control =
    "rounded-xl border border-slate-300 bg-white px-4 py-2.5 text-sm outline-none focus:border-green-600";

  const encabezado =
    "px-4 py-3 text-left text-xs font-semibold uppercase tracking-wide text-slate-500";

  const celda = "px-4 py-3 text-sm";

  return (
    <div className="px-8 py-10">

      <div className="mx-auto max-w-7xl">

        <header className="mb-8">

          <h1 className="flex items-center gap-3 text-3xl font-bold text-slate-800">
            <ClipboardList className="h-7 w-7 text-slate-400" />
            Registros de planta
          </h1>

          <p className="mt-2 max-w-3xl text-slate-500">
            Aseos, inspecciones y controles de máquina. Se registran por equipo
            y fecha; el checklist de los lotes de ese período los toma solo.
            Un aseo semanal se llena una vez y cubre toda su semana.
          </p>

        </header>

        {/* Filtros */}

        <section className="mb-6 flex flex-wrap items-center gap-3">

          <select
            className={control}
            value={documento}
            onChange={(e) => setDocumento(e.target.value)}
          >
            <option value="">Todos los formularios</option>
            {documentos.map((d) => (
              <option key={d.id} value={d.id}>
                {d.nombre}
              </option>
            ))}
          </select>

          <select
            className={control}
            value={equipo}
            onChange={(e) => setEquipo(e.target.value)}
          >
            <option value="">Todos los equipos</option>
            {equipos.map((e) => (
              <option key={e.id} value={e.id}>
                {e.nombre}
              </option>
            ))}
          </select>

          <input
            type="date"
            className={control}
            value={desde}
            onChange={(e) => setDesde(e.target.value)}
            title="Desde"
          />

          <span className="ml-auto text-sm text-slate-400">
            {cargando ? "Cargando…" : `${registros.length} registro(s)`}
          </span>

        </section>

        {/* Alta */}

        {puedeEditar && documentos.length > 0 && (

          <section className="mb-6 rounded-2xl border border-slate-200 bg-white p-4">

            <p className="mb-3 text-sm font-medium text-slate-700">
              Registrar un formulario
            </p>

            <div className="flex flex-wrap gap-2">

              {documentos.map((d) => (
                <button
                  key={d.id}
                  type="button"
                  onClick={() => setNuevo(d)}
                  className="flex items-center gap-1.5 rounded-xl border border-slate-200 px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50"
                >
                  <Plus className="h-4 w-4" />
                  {d.nombre}
                  <span className="text-xs text-slate-400">
                    · {d.frecuencia_etiqueta ?? d.frecuencia}
                  </span>
                </button>
              ))}

            </div>

          </section>

        )}

        {documentos.length === 0 && !cargando && (
          <div className="mb-6 rounded-2xl border border-slate-200 bg-white px-6 py-5 text-sm text-slate-500">
            Ningún documento está marcado con una frecuencia distinta de «por
            lote», así que no hay registros de planta que llevar. La frecuencia
            se define en el catálogo de documentos.
          </div>
        )}

        {error && (
          <div className="mb-6 rounded-2xl border border-red-200 bg-red-50 px-6 py-4 text-sm text-red-700">
            {error}
          </div>
        )}

        <section className="rounded-2xl border border-slate-200 bg-white">

          {!cargando && registros.length === 0 ? (

            <p className="px-6 py-10 text-center text-sm text-slate-400">
              Sin registros en el período.
            </p>

          ) : (

            <div className="overflow-x-auto">

              <table className="w-full">

                <thead className="bg-slate-50">
                  <tr>
                    <th className={encabezado}>Fecha</th>
                    <th className={encabezado}>Formulario</th>
                    <th className={encabezado}>Equipo</th>
                    <th className={encabezado}>Estado</th>
                    <th className={encabezado}>Cubre</th>
                    <th className={encabezado}></th>
                  </tr>
                </thead>

                <tbody>

                  {registros.map((r) => (

                    <tr key={r.id} className="border-t border-slate-100">

                      <td className={`${celda} whitespace-nowrap text-slate-600`}>
                        {r.fecha}
                        {r.turno && (
                          <span className="ml-2 text-xs text-slate-400">
                            turno {r.turno}
                          </span>
                        )}
                      </td>

                      <td className={`${celda} font-medium text-slate-800`}>
                        {r.documento_nombre}
                        <div className="text-xs font-normal text-slate-400">
                          {r.documento_codigo}
                        </div>
                      </td>

                      <td className={`${celda} text-slate-600`}>
                        {r.equipo_nombre ?? "—"}
                      </td>

                      <td className={celda}>
                        <span
                          className={`rounded-full px-2 py-0.5 text-xs font-medium ${
                            ESTILO_ESTADO[r.estado] ?? "bg-slate-100 text-slate-600"
                          }`}
                        >
                          {r.estado_etiqueta}
                        </span>

                        {r.estado === "completado" && !r.completo && (
                          <span
                            className="ml-2 inline-flex items-center gap-1 text-xs text-amber-700"
                            title={`Faltan: ${r.faltantes.join(", ")}`}
                          >
                            <AlertTriangle className="h-3 w-3" />
                            {r.faltantes.length} campo(s)
                          </span>
                        )}
                      </td>

                      <td className={`${celda} text-slate-500`}>
                        {/* Qué período cubre: es lo que decide a qué lotes
                            alcanza, y por eso se muestra. */}
                        {r.frecuencia_etiqueta}
                        {r.vigente_hasta && (
                          <span className="text-xs"> · hasta {r.vigente_hasta}</span>
                        )}
                      </td>

                      <td className={`${celda} text-right`}>
                        {puedeEditar && (
                          <button
                            type="button"
                            onClick={() => setEditando(r)}
                            className="rounded-xl border border-slate-200 px-3 py-1.5 text-xs font-medium text-slate-600 hover:bg-slate-50"
                          >
                            {r.estado === "borrador" ? "Continuar" : "Ver"}
                          </button>
                        )}
                      </td>

                    </tr>

                  ))}

                </tbody>

              </table>

            </div>

          )}

        </section>

        <p className="mt-6 flex items-start gap-2 text-xs text-slate-400">
          <Check className="mt-0.5 h-3.5 w-3.5 shrink-0" />
          Un registro completado cubre a los lotes de su período sin que nadie
          lo vuelva a llenar. Un borrador o uno observado no cubre: el primero
          es trabajo a medias y el segundo es una alerta abierta.
        </p>

      </div>

      {(nuevo || editando) && (
        <FormularioRegistro
          documento={
            nuevo ??
            documentos.find((d) => d.id === editando?.documento) ??
            null
          }
          registro={editando}
          equipos={equipos}
          alCerrar={() => {
            setNuevo(null);
            setEditando(null);
          }}
          alGuardar={cargar}
        />
      )}

    </div>
  );
}


export default Registros;
