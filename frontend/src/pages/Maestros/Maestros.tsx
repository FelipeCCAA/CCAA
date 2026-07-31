import { useCallback, useEffect, useState } from "react";
import { Database, Pencil, Plus } from "lucide-react";

import {
  obtenerCatalogosSku,
  obtenerMandantes,
  obtenerProductosMaestros,
  obtenerSilosMaestros,
  type CatalogosSku,
  type Mandante,
  type ProductoMaestro,
  type Silo,
} from "../../services/maestros.service";

import { puedeEscribir } from "../../services/sesion";

import FormularioMandante from "./FormularioMandante";
import FormularioProducto from "./FormularioProducto";


/*
  Maestros del sistema.

  Cubre productos, mandantes y silos, que es lo que se carga desde la
  operación. Las **especificaciones de calidad** y el **catálogo de documentos
  de liberación** siguen en el admin de Django a propósito: sus formularios son
  JSON (rangos por parámetro, plantilla del documento) y darles una pantalla es
  un trabajo aparte — además el que decide sobre ellos es Calidad, no
  Administración.

  Los silos van de solo lectura: su ocupación no se edita, se calcula desde el
  libro de movimientos, y darles un formulario aquí invitaría a "corregir" un
  saldo escribiéndolo.
*/

type Pestana = "productos" | "mandantes" | "silos";

const PESTANAS: { clave: Pestana; etiqueta: string }[] = [
  { clave: "productos", etiqueta: "Productos" },
  { clave: "mandantes", etiqueta: "Mandantes" },
  { clave: "silos", etiqueta: "Silos y estanques" },
];


function Maestros() {

  const [pestana, setPestana] = useState<Pestana>("productos");

  const [productos, setProductos] = useState<ProductoMaestro[]>([]);
  const [mandantes, setMandantes] = useState<Mandante[]>([]);
  const [silos, setSilos] = useState<Silo[]>([]);
  const [catalogos, setCatalogos] = useState<CatalogosSku | null>(null);

  const [cargando, setCargando] = useState(true);
  const [error, setError] = useState("");

  const [editandoProducto, setEditandoProducto] = useState<ProductoMaestro | null>(null);
  const [nuevoProducto, setNuevoProducto] = useState(false);
  const [editandoMandante, setEditandoMandante] = useState<Mandante | null>(null);
  const [nuevoMandante, setNuevoMandante] = useState(false);

  // Solo Administración escribe maestros: una especificación decide qué sale
  // como conforme. El backend manda; esto solo evita ofrecer lo que rechaza.
  const puedeEditar = puedeEscribir("maestros");

  const cargar = useCallback(async () => {

    setCargando(true);
    setError("");

    try {

      const [p, m, s, c] = await Promise.all([
        obtenerProductosMaestros(),
        obtenerMandantes(),
        obtenerSilosMaestros(),
        obtenerCatalogosSku(),
      ]);

      setProductos(p);
      setMandantes(m);
      setSilos(s);
      setCatalogos(c);

    } catch {
      setError("No se pudieron cargar los maestros. ¿Está corriendo el servidor?");
    } finally {
      setCargando(false);
    }

  }, []);

  useEffect(() => {
    const temporizador = setTimeout(cargar, 0);

    return () => clearTimeout(temporizador);
  }, [cargar]);

  const celda = "px-4 py-3 text-sm";
  const encabezado =
    "px-4 py-3 text-left text-xs font-semibold uppercase tracking-wide text-slate-500";

  return (
    <div className="px-8 py-10">

      <div className="mx-auto max-w-7xl">

        <header className="mb-8 flex flex-wrap items-start justify-between gap-4">

          <div>

            <h1 className="flex items-center gap-3 text-3xl font-bold text-slate-800">
              <Database className="h-7 w-7 text-slate-400" />
              Maestros
            </h1>

            <p className="mt-2 max-w-3xl text-slate-500">
              Productos, mandantes y estanques. El SKU del producto se genera
              desde sus atributos: no se escribe a mano.
            </p>

          </div>

          {!puedeEditar && (
            <p className="rounded-xl bg-slate-100 px-4 py-3 text-sm text-slate-500">
              Tu rol permite consultar, no modificar los maestros.
            </p>
          )}

        </header>

        {/* Pestañas */}

        <div className="mb-6 flex flex-wrap gap-2 border-b border-slate-200">

          {PESTANAS.map((p) => (

            <button
              key={p.clave}
              type="button"
              onClick={() => setPestana(p.clave)}
              className={`-mb-px border-b-2 px-4 py-2.5 text-sm font-medium ${
                pestana === p.clave
                  ? "border-green-700 text-green-800"
                  : "border-transparent text-slate-500 hover:text-slate-700"
              }`}
            >
              {p.etiqueta}
            </button>

          ))}

        </div>

        {error && (
          <div className="mb-6 rounded-2xl border border-red-200 bg-red-50 px-6 py-4 text-sm text-red-700">
            {error}
          </div>
        )}

        {cargando ? (

          <p className="px-6 py-10 text-center text-sm text-slate-400">Cargando…</p>

        ) : (

          <>

            {/* Productos */}

            {pestana === "productos" && (

              <section className="rounded-2xl border border-slate-200 bg-white">

                {puedeEditar && (
                  <div className="border-b border-slate-100 px-4 py-3">
                    <button
                      type="button"
                      onClick={() => setNuevoProducto(true)}
                      className="inline-flex items-center gap-2 rounded-xl bg-green-700 px-4 py-2.5 text-sm font-semibold text-white hover:bg-green-800"
                    >
                      <Plus className="h-4 w-4" />
                      Nuevo producto
                    </button>
                  </div>
                )}

                {productos.length === 0 ? (

                  <p className="px-6 py-10 text-center text-sm text-slate-400">
                    Todavía no hay productos.
                  </p>

                ) : (

                  <div className="overflow-x-auto">

                    <table className="w-full">

                      <thead className="bg-slate-50">
                        <tr>
                          <th className={encabezado}>SKU</th>
                          <th className={encabezado}>Producto</th>
                          <th className={encabezado}>Mandante</th>
                          <th className={encabezado}>Categoría · tipo · formato</th>
                          <th className={encabezado}></th>
                        </tr>
                      </thead>

                      <tbody>

                        {productos.map((p) => (

                          <tr key={p.id} className="border-t border-slate-100">

                            <td className={`${celda} font-mono tabular-nums`}>
                              {p.codigo || (
                                <span className="font-sans text-slate-400">
                                  sin SKU
                                </span>
                              )}
                            </td>

                            <td className={`${celda} font-medium text-slate-800`}>
                              {p.nombre}
                              {!p.activo && (
                                <span className="ml-2 rounded-full bg-slate-100 px-2 py-0.5 text-[10px] font-semibold text-slate-500">
                                  Inactivo
                                </span>
                              )}
                            </td>

                            <td className={`${celda} text-slate-600`}>
                              {p.mandante_nombre}
                            </td>

                            <td className={`${celda} text-slate-500`}>
                              {p.sku_legible
                                ? [
                                    p.sku_legible.categoria,
                                    p.sku_legible.tipo,
                                    p.sku_legible.formato,
                                  ].join(" · ")
                                : "—"}
                            </td>

                            <td className={`${celda} text-right`}>
                              {puedeEditar && (
                                <button
                                  type="button"
                                  onClick={() => setEditandoProducto(p)}
                                  title="Editar"
                                  className="rounded-lg p-1.5 text-slate-400 hover:bg-slate-100 hover:text-slate-700"
                                >
                                  <Pencil className="h-4 w-4" />
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

            )}

            {/* Mandantes */}

            {pestana === "mandantes" && (

              <section className="rounded-2xl border border-slate-200 bg-white">

                {puedeEditar && (
                  <div className="border-b border-slate-100 px-4 py-3">
                    <button
                      type="button"
                      onClick={() => setNuevoMandante(true)}
                      className="inline-flex items-center gap-2 rounded-xl bg-green-700 px-4 py-2.5 text-sm font-semibold text-white hover:bg-green-800"
                    >
                      <Plus className="h-4 w-4" />
                      Nuevo mandante
                    </button>
                  </div>
                )}

                <table className="w-full">

                  <thead className="bg-slate-50">
                    <tr>
                      <th className={encabezado}>Mandante</th>
                      <th className={encabezado}>Cliente en el SKU</th>
                      <th className={encabezado}>Productos</th>
                      <th className={encabezado}></th>
                    </tr>
                  </thead>

                  <tbody>

                    {mandantes.map((m) => (

                      <tr key={m.id} className="border-t border-slate-100">

                        <td className={`${celda} font-medium text-slate-800`}>
                          {m.nombre}
                        </td>

                        <td className={celda}>
                          {m.codigo_cliente ? (
                            <span className="text-slate-600">
                              {m.codigo_cliente_etiqueta}
                            </span>
                          ) : (
                            <span className="rounded-full bg-amber-50 px-2 py-0.5 text-xs font-medium text-amber-800">
                              Sin código: sus productos no generan SKU
                            </span>
                          )}
                        </td>

                        <td className={`${celda} text-slate-500`}>
                          {productos.filter((p) => p.mandante === m.id).length}
                        </td>

                        <td className={`${celda} text-right`}>
                          {puedeEditar && (
                            <button
                              type="button"
                              onClick={() => setEditandoMandante(m)}
                              title="Editar"
                              className="rounded-lg p-1.5 text-slate-400 hover:bg-slate-100 hover:text-slate-700"
                            >
                              <Pencil className="h-4 w-4" />
                            </button>
                          )}
                        </td>

                      </tr>

                    ))}

                  </tbody>

                </table>

              </section>

            )}

            {/* Silos */}

            {pestana === "silos" && (

              <section className="rounded-2xl border border-slate-200 bg-white">

                <p className="border-b border-slate-100 px-6 py-3 text-sm text-slate-500">
                  Solo consulta. La ocupación no se edita: es el saldo del libro
                  de movimientos, y se ve en Recepción y silos.
                </p>

                <table className="w-full">

                  <thead className="bg-slate-50">
                    <tr>
                      <th className={encabezado}>Código</th>
                      <th className={encabezado}>Tipo</th>
                      <th className={encabezado}>Capacidad</th>
                      <th className={encabezado}>Estado</th>
                    </tr>
                  </thead>

                  <tbody>

                    {silos.map((s) => (

                      <tr key={s.id} className="border-t border-slate-100">
                        <td className={`${celda} font-medium text-slate-800`}>
                          {s.codigo}
                        </td>
                        <td className={`${celda} text-slate-600`}>{s.tipo_etiqueta}</td>
                        <td className={`${celda} tabular-nums text-slate-600`}>
                          {Number(s.capacidad_l).toLocaleString("es-CL")} L
                        </td>
                        <td className={`${celda} text-slate-500`}>
                          {s.activo ? "Activo" : "Inactivo"}
                        </td>
                      </tr>

                    ))}

                  </tbody>

                </table>

              </section>

            )}

          </>

        )}

        <p className="mt-6 text-xs text-slate-400">
          Las especificaciones de calidad y el catálogo de documentos de
          liberación se administran desde el admin de Django: sus formularios
          son plantillas JSON y los decide Calidad.
        </p>

      </div>

      {/* Formularios */}

      {catalogos && (nuevoProducto || editandoProducto) && (
        <FormularioProducto
          producto={editandoProducto}
          mandantes={mandantes}
          catalogos={catalogos}
          alCerrar={() => {
            setNuevoProducto(false);
            setEditandoProducto(null);
          }}
          alGuardar={cargar}
        />
      )}

      {catalogos && (nuevoMandante || editandoMandante) && (
        <FormularioMandante
          mandante={editandoMandante}
          catalogos={catalogos}
          alCerrar={() => {
            setNuevoMandante(false);
            setEditandoMandante(null);
          }}
          alGuardar={cargar}
        />
      )}

    </div>
  );
}


export default Maestros;
