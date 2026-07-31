import { useCallback, useEffect, useState } from "react";
import { Plus, Search, Trash2 } from "lucide-react";
import axios from "axios";

import EtiquetaCalidad from "../../components/EtiquetaCalidad/EtiquetaCalidad";

import {
  borrarLote,
  buscarLotes,
  kilos,
  obtenerParametros,
  obtenerProductos,
  RESULTADOS,
  type Lote,
  type Parametro,
  type Producto,
} from "../../services/produccion.service";

import { puedeEscribir } from "../../services/sesion";

import DetalleLote from "./DetalleLote";
import FormularioLote from "./FormularioLote";


const formato = new Intl.NumberFormat("es-CL", { maximumFractionDigits: 0 });

const POR_PAGINA = 50;


function Produccion() {

  const [lotes, setLotes] = useState<Lote[]>([]);
  const [total, setTotal] = useState(0);
  const [pagina, setPagina] = useState(1);

  const [productos, setProductos] = useState<Producto[]>([]);
  const [parametros, setParametros] = useState<Parametro[]>([]);

  const [buscar, setBuscar] = useState("");
  const [filtroProducto, setFiltroProducto] = useState("");
  const [filtroCalidad, setFiltroCalidad] = useState("");

  const [cargando, setCargando] = useState(true);
  const [error, setError] = useState("");
  const [formularioAbierto, setFormularioAbierto] = useState(false);
  const [loteAbierto, setLoteAbierto] = useState<number | null>(null);

  // Solo Producción y Administración registran lotes. El resto consulta.
  const puedeEditar = puedeEscribir("produccion");

  const cargarLotes = useCallback(async () => {

    setCargando(true);
    setError("");

    try {

      const pagina_ = await buscarLotes({
        buscar,
        producto: filtroProducto,
        calidad: filtroCalidad,
        pagina,
      });

      setLotes(pagina_.results);
      setTotal(pagina_.count);

    } catch (error) {

      console.error("Error cargando los lotes:", error);
      setError("No se pudieron cargar los lotes. ¿Está corriendo el servidor?");

    } finally {

      setCargando(false);

    }

  }, [buscar, filtroProducto, filtroCalidad, pagina]);

  // Los maestros no cambian al filtrar: se cargan una sola vez.
  useEffect(() => {

    Promise.all([obtenerProductos(), obtenerParametros()])
      .then(([listaProductos, listaParametros]) => {
        setProductos(listaProductos);
        setParametros(listaParametros);
      })
      .catch((error) => console.error("Error cargando los maestros:", error));

  }, []);

  // Espera a que el usuario deje de escribir antes de consultar, para no
  // lanzar una petición por tecla.
  useEffect(() => {

    const temporizador = setTimeout(cargarLotes, 250);

    return () => clearTimeout(temporizador);

  }, [cargarLotes]);

  const cambiarFiltro = (aplicar: () => void) => {
    aplicar();
    setPagina(1);
  };

  const eliminar = async (lote: Lote) => {

    const confirmado = window.confirm(
      `¿Eliminar el lote ${lote.codigo_lote}?\n\n` +
        "Se borrarán también sus análisis de calidad. No se puede deshacer.",
    );

    if (!confirmado) return;

    try {
      await borrarLote(lote.id);
      cargarLotes();
    } catch (error) {
      console.error("Error eliminando el lote:", error);

      // Si el backend rechazó por permisos, explica el motivo: mostrar
      // "no se pudo" deja al usuario sin saber qué hacer.
      const detalle = axios.isAxiosError(error)
        ? error.response?.data?.detail
        : null;

      setError(detalle || "No se pudo eliminar el lote.");
    }

  };

  const ultimaPagina = Math.max(1, Math.ceil(total / POR_PAGINA));

  const control =
    "rounded-xl border border-slate-300 bg-white px-4 py-2.5 text-sm outline-none focus:border-green-600";

  return (
    <div className="px-8 py-10">

      <div className="mx-auto max-w-7xl">

        {/* Encabezado */}

        <header className="mb-8 flex flex-wrap items-start justify-between gap-4">

          <div>

            <h1 className="text-3xl font-bold text-slate-800">

              Producción

            </h1>

            <p className="mt-2 text-slate-500">

              Lotes de polvo y crema. El resultado de calidad se evalúa contra
              la especificación vigente a la fecha de cada lote.

            </p>

          </div>

          {puedeEditar ? (

            <button
              type="button"
              onClick={() => setFormularioAbierto(true)}
              className="inline-flex items-center gap-2 rounded-xl bg-green-700 px-5 py-3 text-sm font-semibold text-white hover:bg-green-800"
            >

              <Plus className="h-5 w-5" />

              Abrir proceso

            </button>

          ) : (

            <p className="rounded-xl bg-slate-100 px-4 py-3 text-sm text-slate-500">

              Tu rol permite consultar, no registrar lotes.

            </p>

          )}

        </header>

        {/* Filtros */}

        <section className="mb-6 flex flex-wrap items-center gap-3">

          <div className="relative">

            <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />

            <input
              className={`${control} w-56 pl-9`}
              placeholder="Buscar por código…"
              value={buscar}
              onChange={(e) => cambiarFiltro(() => setBuscar(e.target.value))}
            />

          </div>

          <select
            className={control}
            value={filtroProducto}
            onChange={(e) =>
              cambiarFiltro(() => setFiltroProducto(e.target.value))
            }
          >

            <option value="">Todos los productos</option>

            {productos.map((p) => (

              <option key={p.id} value={p.id}>

                {p.nombre}

              </option>

            ))}

          </select>

          <select
            className={control}
            value={filtroCalidad}
            onChange={(e) =>
              cambiarFiltro(() => setFiltroCalidad(e.target.value))
            }
          >

            <option value="">Toda la calidad</option>

            {RESULTADOS.map((r) => (

              <option key={r.valor} value={r.valor}>

                {r.etiqueta}

              </option>

            ))}

          </select>

          <span className="ml-auto text-sm text-slate-400">

            {cargando ? "Cargando…" : `${formato.format(total)} lote${total === 1 ? "" : "s"}`}

          </span>

        </section>

        {error && (

          <div className="mb-6 rounded-2xl border border-red-200 bg-red-50 px-6 py-4 text-sm text-red-700">

            {error}

          </div>

        )}

        {/* Tabla */}

        <section className="rounded-2xl border border-slate-200 bg-white">

          {!cargando && lotes.length === 0 ? (

            <p className="px-6 py-10 text-center text-sm text-slate-400">

              {total === 0 && !buscar && !filtroProducto && !filtroCalidad
                ? "Todavía no hay lotes registrados."
                : "Ningún lote coincide con los filtros."}

            </p>

          ) : (

            <div className="overflow-x-auto">

              <table className="w-full text-left text-sm">

                <thead className="text-slate-500">

                  <tr>

                    <th className="px-6 py-3 font-medium">Lote</th>
                    <th className="px-6 py-3 font-medium">Producto</th>
                    <th className="px-6 py-3 font-medium">Mandante</th>
                    <th className="px-6 py-3 font-medium">Fecha</th>
                    <th className="px-6 py-3 font-medium">Kilos</th>
                    <th className="px-6 py-3 font-medium">Línea</th>
                    <th className="px-6 py-3 font-medium">Turno</th>
                    <th className="px-6 py-3 font-medium">Estado</th>
                    <th className="px-6 py-3 font-medium">Calidad</th>
                    <th className="px-6 py-3"></th>

                  </tr>

                </thead>

                <tbody>

                  {lotes.map((lote) => (

                    <tr
                      key={lote.id}
                      onClick={() => setLoteAbierto(lote.id)}
                      className="cursor-pointer border-t border-slate-100 hover:bg-slate-50"
                      title="Ver el lote y cerrar la producción"
                    >

                      <td className="px-6 py-4 font-medium text-slate-800">

                        {lote.codigo_lote}

                      </td>

                      <td className="px-6 py-4 text-slate-600">

                        {lote.producto_nombre}

                      </td>

                      <td className="px-6 py-4 text-slate-600">

                        {lote.mandante_nombre}

                      </td>

                      <td className="px-6 py-4 text-slate-600">{lote.fecha}</td>

                      <td className="px-6 py-4 text-slate-600">

                        {kilos(lote.kg_producidos)}

                      </td>

                      <td className="px-6 py-4 text-slate-600">

                        {lote.linea || "—"}

                      </td>

                      <td className="px-6 py-4 text-slate-600">

                        {lote.turno || "—"}

                      </td>

                      <td className="px-6 py-4 text-slate-600">

                        {lote.estado_etiqueta}

                      </td>

                      <td className="px-6 py-4">

                        <EtiquetaCalidad calidad={lote.calidad} />

                      </td>

                      <td className="px-6 py-4 text-right">

                        {puedeEditar && (

                          <button
                            type="button"
                            /* Sin `stopPropagation`, el clic llegaría también
                               a la fila y abriría la ficha del lote que se
                               acaba de borrar. */
                            onClick={(e) => {
                              e.stopPropagation();
                              eliminar(lote);
                            }}
                            className="rounded-lg p-2 text-slate-400 hover:bg-red-50 hover:text-red-600"
                            aria-label={`Eliminar el lote ${lote.codigo_lote}`}
                            title="Eliminar"
                          >

                            <Trash2 className="h-4 w-4" />

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

        {/* Paginación */}

        {ultimaPagina > 1 && (

          <div className="mt-6 flex items-center justify-between">

            <button
              type="button"
              onClick={() => setPagina((p) => Math.max(1, p - 1))}
              disabled={pagina <= 1}
              className="rounded-xl border border-slate-300 px-4 py-2 text-sm text-slate-600 disabled:opacity-40"
            >

              Anterior

            </button>

            <span className="text-sm text-slate-500">

              Página {pagina} de {ultimaPagina}

            </span>

            <button
              type="button"
              onClick={() => setPagina((p) => Math.min(ultimaPagina, p + 1))}
              disabled={pagina >= ultimaPagina}
              className="rounded-xl border border-slate-300 px-4 py-2 text-sm text-slate-600 disabled:opacity-40"
            >

              Siguiente

            </button>

          </div>

        )}

      </div>

      {formularioAbierto && (

        <FormularioLote
          productos={productos}
          parametros={parametros}
          alCerrar={() => setFormularioAbierto(false)}
          alGuardar={cargarLotes}
        />

      )}

      {loteAbierto !== null && (

        <DetalleLote
          loteId={loteAbierto}
          puedeEditar={puedeEditar}
          alCerrar={() => setLoteAbierto(null)}
          alCambiar={cargarLotes}
        />

      )}

    </div>
  );
}


export default Produccion;
