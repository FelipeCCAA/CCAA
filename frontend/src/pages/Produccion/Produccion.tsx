import {
  lazy,
  memo,
  Suspense,
  useCallback,
  useEffect,
  useState,
} from "react";
import { Plus, Search } from "lucide-react";

import EtiquetaCalidad from "../../components/EtiquetaCalidad/EtiquetaCalidad";

import {
  buscarLotes,
  kilos,
  obtenerPallets,
  obtenerProductos,
  RESULTADOS,
  type Lote,
  type PalletProducto,
  type Producto,
} from "../../services/produccion.service";

import { puedeEscribir } from "../../services/sesion";

const DetalleLote = lazy(() => import("./DetalleLote"));
const FormularioLote = lazy(() => import("./FormularioLote"));


const formato = new Intl.NumberFormat("es-CL", { maximumFractionDigits: 0 });

const POR_PAGINA = 50;


const FilaLote = memo(function FilaLote({
  lote,
  onAbrir,
}: {
  lote: Lote;
  onAbrir: (id: number) => void;
}) {
  return (
    <tr
      onClick={() => onAbrir(lote.id)}
      className="cursor-pointer border-t border-slate-100 hover:bg-slate-50"
      title="Ver el lote y cerrar la producción"
    >
      <td className="px-6 py-4 font-medium text-slate-800">
        {lote.codigo_lote}
      </td>
      <td className="px-6 py-4 text-slate-600">{lote.producto_nombre}</td>
      <td className="px-6 py-4 text-slate-600">{lote.mandante_nombre}</td>
      <td className="px-6 py-4 text-slate-600">{lote.fecha}</td>
      <td className="px-6 py-4 text-slate-600">{kilos(lote.kg_producidos)}</td>
      <td className="px-6 py-4 text-slate-600">{lote.linea || "—"}</td>
      <td className="px-6 py-4 text-slate-600">{lote.turno || "—"}</td>
      <td className="px-6 py-4 text-slate-600">{lote.estado_etiqueta}</td>
      <td className="px-6 py-4">
        <EtiquetaCalidad calidad={lote.calidad} />
      </td>
    </tr>
  );
});


function Produccion() {

  const [lotes, setLotes] = useState<Lote[]>([]);
  const [total, setTotal] = useState(0);
  const [pagina, setPagina] = useState(1);

  const [productos, setProductos] = useState<Producto[]>([]);
  const [pallets, setPallets] = useState<PalletProducto[] | null>(null);
  const [cargandoPallets, setCargandoPallets] = useState(false);
  const [errorPallets, setErrorPallets] = useState("");

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

  // Los productos alimentan el filtro visible y se cargan una sola vez. Los
  // parámetros y pallets se piden al abrir las secciones que los usan.
  useEffect(() => {
    obtenerProductos()
      .then(setProductos)
      .catch((error) => console.error("Error cargando los productos:", error));
  }, []);

  const cargarPallets = useCallback(async () => {
    if (pallets !== null || cargandoPallets) return;
    setCargandoPallets(true);
    setErrorPallets("");
    try {
      const paginaPallets = await obtenerPallets();
      setPallets(paginaPallets.results);
    } catch {
      setErrorPallets("No se pudieron cargar los pallets recientes.");
    } finally {
      setCargandoPallets(false);
    }
  }, [cargandoPallets, pallets]);

  const abrirLote = useCallback((id: number) => setLoteAbierto(id), []);

  // Mantiene la sección automática, pero deja primero pasar las dos lecturas
  // críticas (lotes y productos). Así entrar al módulo no dispara las tres
  // consultas en la misma ráfaga.
  useEffect(() => {
    if (pallets !== null || cargandoPallets || errorPallets) return;
    const temporizador = window.setTimeout(() => void cargarPallets(), 600);
    return () => window.clearTimeout(temporizador);
  }, [cargandoPallets, cargarPallets, errorPallets, pallets]);

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

            <p className="mt-2 text-slate-600">

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

            <p className="rounded-xl bg-slate-100 px-4 py-3 text-sm text-slate-600">

              Tu rol permite consultar, no registrar lotes.

            </p>

          )}

        </header>

        <section className="mb-8 grid gap-3 rounded-2xl border border-slate-200 bg-slate-50 p-4 text-sm text-slate-700 md:grid-cols-4">
          <div><b>1. Recepción</b><br /><span className="text-slate-600">Leche analizada y descargada a silo.</span></div>
          <div><b>2. Estandarización</b><br /><span className="text-slate-600">Vale liberado y leche disponible en silo destino.</span></div>
          <div><b>3. Producción</b><br /><span className="text-slate-600">Producto, máquina compatible y lote trazable.</span></div>
          <div><b>4. Calidad e Inventario</b><br /><span className="text-slate-600">Análisis, liberación, pallet y ubicación de bodega.</span></div>
        </section>

        {/* Filtros */}

        <section className="mb-6 flex flex-wrap items-center gap-3">

          <div className="relative">

            <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-600" />

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

          <span className="ml-auto text-sm text-slate-600">

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

            <p className="px-6 py-10 text-center text-sm text-slate-600">

              {total === 0 && !buscar && !filtroProducto && !filtroCalidad
                ? "Todavía no hay lotes registrados."
                : "Ningún lote coincide con los filtros."}

            </p>

          ) : (

            <div className="overflow-x-auto">

              <table className="w-full text-left text-sm">

                <thead className="text-slate-600">

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

                  </tr>

                </thead>

                <tbody>

                  {lotes.map((lote) => (
                    <FilaLote
                      key={lote.id}
                      lote={lote}
                      onAbrir={abrirLote}
                    />
                  ))}

                </tbody>

              </table>

            </div>

          )}

        </section>

        <section className="mt-8 rounded-2xl border border-slate-200 bg-white p-6">
          <h2 className="text-lg font-semibold text-slate-800">Envase y pallets recientes</h2>
          <p className="mt-1 text-sm text-slate-600">Unidades físicas vinculadas al lote maestro y pendientes de su puerta de Calidad.</p>
          {pallets === null ? (
            errorPallets ? (
              <div className="pt-5">
                <p className="text-sm text-red-700">{errorPallets}</p>
                <button
                  type="button"
                  onClick={() => void cargarPallets()}
                  className="mt-3 rounded-xl border border-green-700 px-4 py-2 text-sm font-semibold text-green-700"
                >
                  Reintentar
                </button>
              </div>
            ) : (
              <p className="py-8 text-center text-sm text-slate-600">
                Cargando pallets recientes…
              </p>
            )
          ) : pallets.length === 0 ? (
            <p className="py-8 text-center text-sm text-slate-600">
              Todavía no hay pallets registrados.
            </p>
          ) : (
            <div className="mt-5 overflow-x-auto">
              <table className="w-full text-left text-sm">
                <thead className="text-slate-600">
                  <tr>
                    <th className="px-4 py-3">Pallet</th>
                    <th className="px-4 py-3">Unidades</th>
                    <th className="px-4 py-3">Peso neto</th>
                    <th className="px-4 py-3">Estado</th>
                  </tr>
                </thead>
                <tbody>
                  {pallets.slice(0, 10).map((pallet) => (
                    <tr key={pallet.id} className="border-t border-slate-100">
                      <td className="px-4 py-3 font-semibold text-slate-800">
                        {pallet.codigo}
                      </td>
                      <td className="px-4 py-3 text-slate-600">
                        {formato.format(pallet.unidades)}
                      </td>
                      <td className="px-4 py-3 text-slate-600">
                        {kilos(pallet.kg_neto)}
                      </td>
                      <td className="px-4 py-3 text-slate-600">
                        {pallet.estado_etiqueta}
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

            <span className="text-sm text-slate-600">

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

      <Suspense
        fallback={(
          <div className="fixed inset-0 z-50 grid place-items-center bg-slate-900/30">
            <p className="rounded-xl bg-white px-5 py-3 text-sm text-slate-600 shadow-lg">
              Preparando detalle…
            </p>
          </div>
        )}
      >
        {formularioAbierto && (
          <FormularioLote
            productos={productos}
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
      </Suspense>

    </div>
  );
}


export default Produccion;
