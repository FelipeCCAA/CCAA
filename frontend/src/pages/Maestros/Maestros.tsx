import { useCallback, useEffect, useState } from "react";
import { Database, Pencil, Plus } from "lucide-react";

import {
  obtenerCatalogosSku,
  obtenerEquipos,
  obtenerMandantes,
  obtenerProductosMaestros,
  obtenerSilosMaestros,
  obtenerVehiculosMaestros,
  editarDocumento,
  guardarSilo,
  guardarVehiculo,
  guardarEspecificacion,
  obtenerDocumentos,
  obtenerEspecificaciones,
  type CatalogosSku,
  type DocumentoLiberacion,
  type Equipo,
  type Especificacion,
  type Mandante,
  type ProductoMaestro,
  type Silo,
  type Vehiculo,
} from "../../services/maestros.service";

import { obtenerParametros, type Parametro } from "../../services/produccion.service";

import {
  guardarCodigo,
  obtenerCatalogosPlanificacion,
  obtenerCodigos,
  type CatalogosPlanificacion,
  type CodigoProduccion,
} from "../../services/planificacion.service";

import { puedeEscribir } from "../../services/sesion";

import FormularioEquipo from "./FormularioEquipo";
import FormularioEspecificacion from "./FormularioEspecificacion";
import FormularioMaestro, { type Campo } from "./FormularioMaestro";
import FormularioMandante from "./FormularioMandante";
import FormularioProducto from "./FormularioProducto";


/*
  Maestros del sistema.

  Cubre productos, mandantes, especificaciones, máquinas y silos.

  Las **especificaciones** y el **catálogo de documentos** los escribe Calidad,
  no Administración: son los que deciden qué sale conforme y qué se exige para
  liberar. El permiso lo aplica el backend; aquí solo se deja de ofrecer lo que
  va a rechazar.

  De los formularios JSON queda uno en el admin: la **plantilla** de cada
  documento de liberación, que se construye contra el formato real de planta.
  Los rangos de una especificación ya no: se editan con una fila por parámetro
  del catálogo, así que no hay forma de escribir una clave que el modelo
  rechaza.

  Los silos van de solo lectura: su ocupación no se edita, se calcula desde el
  libro de movimientos, y darles un formulario aquí invitaría a "corregir" un
  saldo escribiéndolo.
*/

type Pestana =
  | "productos"
  | "mandantes"
  | "especificaciones"
  | "equipos"
  | "silos"
  | "camiones"
  | "codigos"
  | "documentos";

const PESTANAS: { clave: Pestana; etiqueta: string }[] = [
  { clave: "productos", etiqueta: "Productos" },
  { clave: "mandantes", etiqueta: "Mandantes" },
  { clave: "especificaciones", etiqueta: "Especificaciones" },
  { clave: "equipos", etiqueta: "Máquinas" },
  { clave: "silos", etiqueta: "Silos y estanques" },
  { clave: "camiones", etiqueta: "Camiones" },
  { clave: "codigos", etiqueta: "Códigos de producción" },
  { clave: "documentos", etiqueta: "Documentos de liberación" },
];



/*
  El nombre legible de un parámetro, según el catálogo del backend.

  Si el catálogo todavía no llegó, se muestra la clave cruda en vez de una
  etiqueta escrita aquí: una tabla de nombres en el frontend se separa del
  modelo sin que nadie lo note, y esta pantalla existe justamente para no
  tener que conocer las claves.
*/
function etiquetaParametro(parametros: Parametro[], clave: string): string {
  return parametros.find((p) => p.clave === clave)?.etiqueta ?? clave;
}


/*
  Los campos de cada maestro simple, descritos como datos.

  Se arman con los catálogos que sirve el backend, así que un valor nuevo en el
  modelo aparece en el desplegable sin tocar esta pantalla.
*/
function camposDe(
  entidad: "silo" | "camion" | "codigo",
  catalogos: CatalogosSku | null,
  catPlan: CatalogosPlanificacion | null,
  productos: ProductoMaestro[],
  mandantes: Mandante[],
): Campo[] {

  if (entidad === "silo") {
    return [
      {
        clave: "codigo",
        etiqueta: "Código",
        tipo: "texto",
        requerido: true,
        soloLecturaAlEditar: true,
        ayuda: "SILO 1, TK CREMA 2…",
      },
      {
        clave: "tipo",
        etiqueta: "Tipo",
        tipo: "select",
        requerido: true,
        opciones: catalogos?.silo_tipo ?? [],
      },
      {
        clave: "capacidad_l",
        etiqueta: "Capacidad (litros)",
        tipo: "numero",
        requerido: true,
      },
      { clave: "activo", etiqueta: "Activo", tipo: "checkbox" },
    ];
  }

  if (entidad === "camion") {
    return [
      { clave: "placa", etiqueta: "Placa", tipo: "texto", requerido: true },
      { clave: "numero", etiqueta: "Número interno", tipo: "texto" },
      { clave: "tipo", etiqueta: "Tipo", tipo: "texto" },
      { clave: "capacidad_l", etiqueta: "Capacidad (litros)", tipo: "numero" },
      {
        clave: "transportista",
        etiqueta: "Transportista",
        tipo: "texto",
        ancho: 2,
      },
      { clave: "chofer_am", etiqueta: "Chofer A.M.", tipo: "texto" },
      { clave: "chofer_pm", etiqueta: "Chofer P.M.", tipo: "texto" },
      { clave: "activo", etiqueta: "Activo", tipo: "checkbox" },
    ];
  }

  return [
    {
      clave: "codigo",
      etiqueta: "Código",
      tipo: "texto",
      requerido: true,
      soloLecturaAlEditar: true,
      ayuda: "LNSH2, RCSH2N…",
    },
    { clave: "nombre", etiqueta: "Nombre", tipo: "texto" },
    {
      clave: "producto",
      etiqueta: "Producto",
      tipo: "select",
      opciones: productos.map((p) => ({ valor: p.id, etiqueta: p.nombre })),
    },
    {
      clave: "mandante",
      etiqueta: "Mandante",
      tipo: "select",
      opciones: mandantes.map((m) => ({ valor: m.id, etiqueta: m.nombre })),
    },
    {
      clave: "categoria",
      etiqueta: "Categoría de consumo",
      tipo: "select",
      requerido: true,
      ayuda: "A qué fila del balance suma.",
      opciones: catPlan?.categoria_consumo ?? [],
    },
    {
      clave: "formato",
      etiqueta: "Formato",
      tipo: "select",
      opciones: catPlan?.formato ?? [],
    },
    {
      clave: "rendimiento_lh",
      etiqueta: "Rendimiento (L/h)",
      tipo: "numero",
      requerido: true,
      ancho: 2,
      ayuda:
        "Litros de leche por hora de corrida. Es lo que convierte horas de programa en litros del balance.",
    },
    { clave: "activo", etiqueta: "Activo", tipo: "checkbox" },
  ];
}



const TITULO_SIMPLE = {
  silo: "silo",
  camion: "camión",
  codigo: "código de producción",
};


function Maestros() {

  const [pestana, setPestana] = useState<Pestana>("productos");

  const [productos, setProductos] = useState<ProductoMaestro[]>([]);
  const [mandantes, setMandantes] = useState<Mandante[]>([]);
  const [equipos, setEquipos] = useState<Equipo[]>([]);
  const [silos, setSilos] = useState<Silo[]>([]);
  const [camiones, setCamiones] = useState<Vehiculo[]>([]);
  const [codigos, setCodigos] = useState<CodigoProduccion[]>([]);
  const [catPlan, setCatPlan] = useState<CatalogosPlanificacion | null>(null);
  const [documentos, setDocumentos] = useState<DocumentoLiberacion[]>([]);
  const [especificaciones, setEspecificaciones] = useState<Especificacion[]>([]);
  const [parametros, setParametros] = useState<Parametro[]>([]);
  /* Qué especificación se está editando y cómo: crear, editar la versión o
     abrir una nueva. Los tres usan el mismo formulario. */
  const [spec, setSpec] = useState<{
    modo: "nueva" | "editar" | "version";
    inicial: Especificacion | null;
  } | null>(null);
  /* Qué documento se está guardando, para no dejar la fila muda al hacer clic. */
  const [guardandoDoc, setGuardandoDoc] = useState<number | null>(null);
  const [catalogos, setCatalogos] = useState<CatalogosSku | null>(null);

  const [cargando, setCargando] = useState(true);
  const [error, setError] = useState("");

  const [editandoProducto, setEditandoProducto] = useState<ProductoMaestro | null>(null);
  const [nuevoProducto, setNuevoProducto] = useState(false);
  const [editandoMandante, setEditandoMandante] = useState<Mandante | null>(null);
  const [nuevoMandante, setNuevoMandante] = useState(false);
  const [editandoEquipo, setEditandoEquipo] = useState<Equipo | null>(null);
  const [nuevoEquipo, setNuevoEquipo] = useState(false);

  /* Los maestros simples comparten un formulario descrito por datos: qué
     entidad se está editando y con qué valores. */
  const [simple, setSimple] = useState<{
    entidad: "silo" | "camion" | "codigo";
    id: number | null;
    valores: Record<string, unknown>;
  } | null>(null);

  // Solo Administración escribe maestros: una especificación decide qué sale
  // como conforme. El backend manda; esto solo evita ofrecer lo que rechaza.
  const puedeEditar = puedeEscribir("maestros");

  const cargar = useCallback(async () => {

    setCargando(true);
    setError("");

    try {

      // Los listados van juntos: sin ellos no hay nada que mostrar.
      const [p, m, e, s, v, k, d, esp] = await Promise.all([
        obtenerProductosMaestros(),
        obtenerMandantes(),
        obtenerEquipos(),
        obtenerSilosMaestros(),
        obtenerVehiculosMaestros(),
        obtenerCodigos(),
        obtenerDocumentos(),
        obtenerEspecificaciones(),
      ]);

      setProductos(p);
      setMandantes(m);
      setEquipos(e);
      setSilos(s);
      setCamiones(v);
      setCodigos(k);
      setDocumentos(d);
      setEspecificaciones(esp);

    } catch {
      setError(
        "No se pudieron cargar los maestros. Revisa que el servidor esté " +
          "corriendo y vuelve a intentarlo.",
      );
    } finally {
      setCargando(false);
    }

    /*
      Los catálogos van aparte y cada uno por su cuenta.

      Solo alimentan los desplegables de los formularios. Pedirlos en el mismo
      `Promise.all` que los listados hacía que un solo endpoint caído dejara
      las seis pestañas vacías — pasó con un 500 en los catálogos de
      planificación, y desde la pantalla parecía que no había datos.
    */
    obtenerCatalogosSku()
      .then(setCatalogos)
      .catch(() => setCatalogos(null));

    obtenerCatalogosPlanificacion()
      .then(setCatPlan)
      .catch(() => setCatPlan(null));

    // El catálogo de parámetros medibles alimenta el formulario de rangos.
    // Viene del backend por la misma razón que el resto: escribir las nueve
    // claves aquí dejaría ofrecer una que `Especificacion.clean()` rechaza.
    obtenerParametros()
      .then(setParametros)
      .catch(() => setParametros([]));

  }, []);

  useEffect(() => {
    const temporizador = setTimeout(cargar, 0);

    return () => clearTimeout(temporizador);
  }, [cargar]);

  /*
    Lo que decide sobre la calidad del producto lo escribe Calidad, no
    Administración: el checklist —el módulo promete que Calidad cambia un campo
    y el formulario cambia sin desplegar— y las especificaciones, que son las
    que dicen qué sale conforme.
  */
  const puedeEditarCalidad = puedeEscribir("calidad");

  const cambiarFrecuencia = async (
    documento: DocumentoLiberacion,
    frecuencia: string,
  ) => {

    setGuardandoDoc(documento.id);
    setError("");

    try {
      const guardado = await editarDocumento(documento.id, { frecuencia });

      setDocumentos((previos) =>
        previos.map((d) => (d.id === guardado.id ? guardado : d)),
      );
    } catch {
      setError(
        `No se pudo cambiar la frecuencia de «${documento.nombre}».`,
      );
    } finally {
      setGuardandoDoc(null);
    }
  };

  /*
    Productos sin especificación vigente hoy.

    Es lo primero que la pestaña tiene que decir, porque es la causa del
    «Sin especificación» que aparece en Producción: sin ella no hay veredicto
    y el lote **no se puede liberar por ninguna vía**, ni siquiera por
    concesión —no se concede una excepción sobre algo que nunca se midió—.

    Qué versión está vigente lo dice el backend en `es_vigente`, con la misma
    función que audita el lote. Aquí solo se resta.
  */
  const conVigente = new Set(
    especificaciones.filter((e) => e.es_vigente).map((e) => e.producto),
  );
  const sinEspecificacion = productos.filter(
    (p) => p.activo && !conVigente.has(p.id),
  );

  const guardarSpec = async (
    id: number | null,
    datos: Parameters<typeof guardarEspecificacion>[1],
  ) => {
    await guardarEspecificacion(id, datos);
    setSpec(null);
    // Se recarga la lista entera y no se parchea la fila: crear una versión
    // cambia cuál es la vigente, y esa respuesta la da el backend.
    setEspecificaciones(await obtenerEspecificaciones());
  };

  const celda = "px-4 py-3 text-sm";
  const encabezado =
    "px-4 py-3 text-left text-xs font-semibold uppercase tracking-wide text-slate-600";

  return (
    <div className="px-8 py-10">

      <div className="mx-auto max-w-7xl">

        <header className="mb-8 flex flex-wrap items-start justify-between gap-4">

          <div>

            <h1 className="flex items-center gap-3 text-3xl font-bold text-slate-800">
              <Database className="h-7 w-7 text-slate-600" />
              Maestros
            </h1>

            <p className="mt-2 max-w-3xl text-slate-600">
              Productos, especificaciones, máquinas y estanques: la
              configuración del entorno productivo. El SKU del producto se
              genera desde sus atributos, no se escribe a mano.
            </p>

          </div>

          {!puedeEditar && (
            <p className="rounded-xl bg-slate-100 px-4 py-3 text-sm text-slate-600">
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
                  : "border-transparent text-slate-600 hover:text-slate-700"
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

          <p className="px-6 py-10 text-center text-sm text-slate-600">Cargando…</p>

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

                  <p className="px-6 py-10 text-center text-sm text-slate-600">
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
                                <span className="font-sans text-slate-600">
                                  sin SKU
                                </span>
                              )}
                            </td>

                            <td className={`${celda} font-medium text-slate-800`}>
                              {p.nombre}
                              {!p.activo && (
                                <span className="ml-2 rounded-full bg-slate-100 px-2 py-0.5 text-[10px] font-semibold text-slate-600">
                                  Inactivo
                                </span>
                              )}
                            </td>

                            <td className={`${celda} text-slate-600`}>
                              {p.mandante_nombre}
                            </td>

                            <td className={`${celda} text-slate-600`}>
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
                                  className="rounded-lg p-1.5 text-slate-600 hover:bg-slate-100 hover:text-slate-700"
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

                        <td className={`${celda} text-slate-600`}>
                          {productos.filter((p) => p.mandante === m.id).length}
                        </td>

                        <td className={`${celda} text-right`}>
                          {puedeEditar && (
                            <button
                              type="button"
                              onClick={() => setEditandoMandante(m)}
                              title="Editar"
                              className="rounded-lg p-1.5 text-slate-600 hover:bg-slate-100 hover:text-slate-700"
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

            {/* Especificaciones de calidad */}

            {pestana === "especificaciones" && (

              <div className="space-y-6">

                {/*
                  El aviso va primero porque es la causa del «Sin
                  especificación» de Producción, y porque el efecto no es
                  cosmético: esos lotes no se liberan por ninguna vía.
                */}
                {sinEspecificacion.length > 0 && (
                  <section className="rounded-2xl border border-amber-200 bg-amber-50 px-6 py-5">

                    <h2 className="text-sm font-semibold text-amber-900">
                      {sinEspecificacion.length}{" "}
                      {sinEspecificacion.length === 1
                        ? "producto activo no tiene especificación vigente"
                        : "productos activos no tienen especificación vigente"}
                    </h2>

                    <p className="mt-1 text-sm text-amber-800">
                      Sus lotes salen como <strong>«Sin especificación»</strong>{" "}
                      y <strong>no se pueden liberar</strong>, ni siquiera por
                      concesión: no se concede una excepción sobre algo que
                      nunca se midió.
                    </p>

                    <div className="mt-3 flex flex-wrap gap-2">
                      {sinEspecificacion.map((p) => (
                        <span
                          key={p.id}
                          className="rounded-full bg-white px-3 py-1 text-xs text-amber-900"
                        >
                          {p.nombre}
                        </span>
                      ))}
                    </div>

                  </section>
                )}

                <section className="rounded-2xl border border-slate-200 bg-white">

                  <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-100 px-6 py-3">

                    <p className="max-w-3xl text-sm text-slate-600">
                      Los rangos que decide si un lote es conforme. Un lote se
                      audita contra la versión vigente en <strong>su</strong>{" "}
                      fecha, no contra la de hoy — por eso se versiona en vez
                      de corregirse encima.
                    </p>

                    {puedeEditarCalidad && (
                      <button
                        type="button"
                        onClick={() => setSpec({ modo: "nueva", inicial: null })}
                        className="inline-flex items-center gap-2 rounded-xl bg-green-700 px-4 py-2.5 text-sm font-semibold text-white hover:bg-green-800"
                      >
                        <Plus className="h-4 w-4" />
                        Nueva especificación
                      </button>
                    )}

                  </div>

                  <div className="overflow-x-auto">

                    <table className="w-full">

                      <thead className="bg-slate-50">
                        <tr>
                          <th className={encabezado}>Producto</th>
                          <th className={encabezado}>Versión</th>
                          <th className={encabezado}>Vigencia</th>
                          <th className={encabezado}>Parámetros</th>
                          <th className={encabezado}>Fuente</th>
                          <th className={encabezado}></th>
                        </tr>
                      </thead>

                      <tbody>

                        {especificaciones.length === 0 && (
                          <tr>
                            <td
                              colSpan={6}
                              className="px-6 py-10 text-center text-sm text-slate-600"
                            >
                              Todavía no hay especificaciones cargadas.
                            </td>
                          </tr>
                        )}

                        {especificaciones.map((e) => (

                          <tr key={e.id} className="border-t border-slate-100">

                            <td className={`${celda} font-medium text-slate-800`}>
                              {e.producto_nombre}
                            </td>

                            <td className={celda}>
                              <span className="text-slate-600">v{e.version}</span>
                              {e.es_vigente && (
                                <span className="ml-2 rounded-full bg-green-50 px-2 py-0.5 text-xs font-medium text-green-700">
                                  vigente
                                </span>
                              )}
                            </td>

                            <td className={`${celda} text-slate-600`}>
                              {e.vigente_desde} →{" "}
                              {e.vigente_hasta ?? (
                                <span className="text-slate-600">sin término</span>
                              )}
                            </td>

                            <td className={`${celda} text-slate-600`}>
                              {Object.entries(e.rangos).map(([clave, r]) => (
                                <span
                                  key={clave}
                                  className="mr-1.5 inline-block rounded-lg bg-slate-100 px-2 py-0.5 text-xs"
                                  title={r.obligatorio ? "Obligatorio" : "Opcional"}
                                >
                                  {etiquetaParametro(parametros, clave)}{" "}
                                  {r.min ?? "—"}…{r.max ?? "—"}
                                  {r.obligatorio && "*"}
                                </span>
                              ))}
                            </td>

                            <td className={`${celda} text-slate-600`}>
                              {e.fuente || "—"}
                            </td>

                            <td className={`${celda} whitespace-nowrap text-right`}>
                              {puedeEditarCalidad && (
                                <>
                                  <button
                                    type="button"
                                    onClick={() =>
                                      setSpec({ modo: "version", inicial: e })
                                    }
                                    className="rounded-lg px-2 py-1 text-xs font-medium text-green-700 hover:bg-green-50"
                                  >
                                    Nueva versión
                                  </button>
                                  <button
                                    type="button"
                                    onClick={() =>
                                      setSpec({ modo: "editar", inicial: e })
                                    }
                                    title="Editar esta versión"
                                    className="rounded-lg p-1.5 text-slate-600 hover:bg-slate-100 hover:text-slate-700"
                                  >
                                    <Pencil className="h-4 w-4" />
                                  </button>
                                </>
                              )}
                            </td>

                          </tr>

                        ))}

                      </tbody>

                    </table>

                  </div>

                  {!puedeEditarCalidad && (
                    <p className="border-t border-slate-100 px-6 py-3 text-sm text-slate-600">
                      Solo Calidad edita las especificaciones: son las que
                      deciden qué producto sale como conforme.
                    </p>
                  )}

                </section>

              </div>

            )}

            {/* Máquinas */}

            {pestana === "equipos" && (

              <section className="rounded-2xl border border-slate-200 bg-white">

                {puedeEditar && (
                  <div className="border-b border-slate-100 px-4 py-3">
                    <button
                      type="button"
                      onClick={() => setNuevoEquipo(true)}
                      className="inline-flex items-center gap-2 rounded-xl bg-green-700 px-4 py-2.5 text-sm font-semibold text-white hover:bg-green-800"
                    >
                      <Plus className="h-4 w-4" />
                      Nueva máquina
                    </button>
                  </div>
                )}

                <table className="w-full">

                  <thead className="bg-slate-50">
                    <tr>
                      <th className={encabezado}>Máquina</th>
                      <th className={encabezado}>Tipo</th>
                      <th className={encabezado}>Balance de leche</th>
                      <th className={encabezado}>Bloques</th>
                      <th className={encabezado}></th>
                    </tr>
                  </thead>

                  <tbody>

                    {equipos.map((e) => (

                      <tr key={e.id} className="border-t border-slate-100">

                        <td className={`${celda} font-medium text-slate-800`}>
                          {e.nombre}
                          {!e.activo && (
                            <span className="ml-2 rounded-full bg-slate-100 px-2 py-0.5 text-[10px] font-semibold text-slate-600">
                              Inactiva
                            </span>
                          )}
                          <div className="font-mono text-xs font-normal text-slate-600">
                            {e.codigo}
                          </div>
                        </td>

                        <td className={`${celda} text-slate-600`}>{e.tipo_etiqueta}</td>

                        <td className={celda}>
                          {e.consume_leche ? (
                            <span className="rounded-full bg-amber-50 px-2 py-0.5 text-xs font-medium text-amber-800">
                              Resta leche
                            </span>
                          ) : (
                            <span className="text-slate-600">No resta</span>
                          )}
                        </td>

                        <td className={`${celda} text-slate-600`}>
                          orden {e.orden}
                        </td>

                        <td className={`${celda} text-right`}>
                          {puedeEditar && (
                            <button
                              type="button"
                              onClick={() => setEditandoEquipo(e)}
                              title="Editar"
                              className="rounded-lg p-1.5 text-slate-600 hover:bg-slate-100 hover:text-slate-700"
                            >
                              <Pencil className="h-4 w-4" />
                            </button>
                          )}
                        </td>

                      </tr>

                    ))}

                  </tbody>

                </table>

                <p className="border-t border-slate-100 px-6 py-3 text-sm text-slate-600">
                  «Resta leche» decide qué bloques consumen del balance
                  semanal. Solo los evaporadores: una línea recibe lo que el
                  evaporador ya produjo, y marcar ambos contaría la misma leche
                  dos veces.
                </p>

              </section>

            )}

            {/* Documentos de liberación */}

            {pestana === "documentos" && (

              <section className="rounded-2xl border border-slate-200 bg-white">

                <p className="border-b border-slate-100 px-6 py-3 text-sm text-slate-600">
                  El checklist de liberación. La <strong>frecuencia</strong> decide
                  dónde se lleva cada formulario: «por lote» va en el expediente
                  del lote; el resto pertenece al equipo y su período, y se
                  registra en Registros operacionales. Cambiarla mueve el formulario
                  de una pantalla a la otra.
                </p>

                <div className="overflow-x-auto">

                  <table className="w-full">

                    <thead className="bg-slate-50">
                      <tr>
                        <th className={encabezado}>#</th>
                        <th className={encabezado}>Documento</th>
                        <th className={encabezado}>Área</th>
                        <th className={encabezado}>Frecuencia</th>
                        <th className={encabezado}>Formulario</th>
                      </tr>
                    </thead>

                    <tbody>

                      {documentos.map((d) => (

                        <tr key={d.id} className="border-t border-slate-100">

                          <td className={`${celda} text-slate-600`}>{d.orden}</td>

                          <td className={`${celda} font-medium text-slate-800`}>
                            {d.nombre}
                            <div className="font-mono text-xs font-normal text-slate-600">
                              {d.codigo || "sin código"}
                            </div>
                          </td>

                          <td className={`${celda} text-slate-600`}>
                            {d.area_etiqueta}
                          </td>

                          <td className={celda}>
                            {puedeEditarCalidad ? (
                              <select
                                className="rounded-xl border border-slate-200 px-3 py-1.5 text-sm text-slate-800 focus:border-green-500 focus:outline-none disabled:opacity-50"
                                value={d.frecuencia}
                                disabled={guardandoDoc === d.id}
                                onChange={(e) =>
                                  void cambiarFrecuencia(d, e.target.value)
                                }
                              >
                                {(catalogos?.frecuencia_documento ?? []).map((o) => (
                                  <option key={o.valor} value={o.valor}>
                                    {o.etiqueta}
                                  </option>
                                ))}
                              </select>
                            ) : (
                              <span className="text-slate-600">
                                {d.frecuencia_etiqueta}
                              </span>
                            )}
                          </td>

                          <td className={`${celda} text-slate-600`}>
                            {d.campos > 0
                              ? `${d.campos} campos`
                              : "solo atestación"}
                          </td>

                        </tr>

                      ))}

                    </tbody>

                  </table>

                </div>

                {!puedeEditarCalidad && (
                  <p className="border-t border-slate-100 px-6 py-3 text-sm text-slate-600">
                    Solo Calidad cambia el checklist: es quien responde por él.
                  </p>
                )}

                <p className="border-t border-slate-100 px-6 py-3 text-xs text-slate-600">
                  La plantilla de cada formulario —qué campos pide— se edita en el
                  admin de Django. Se construye contra el formato operacional:
                  una plantilla inventada se completa igual y da el documento por
                  cumplido.
                </p>

              </section>

            )}

            {/* Silos */}

            {pestana === "silos" && (

              <section className="rounded-2xl border border-slate-200 bg-white">

                {puedeEditar && (
                  <div className="border-b border-slate-100 px-4 py-3">
                    <button
                      type="button"
                      onClick={() =>
                        setSimple({
                          entidad: "silo",
                          id: null,
                          valores: { tipo: "silo", activo: true },
                        })
                      }
                      className="inline-flex items-center gap-2 rounded-xl bg-green-700 px-4 py-2.5 text-sm font-semibold text-white hover:bg-green-800"
                    >
                      <Plus className="h-4 w-4" />
                      Nuevo silo
                    </button>
                  </div>
                )}

                <table className="w-full">

                  <thead className="bg-slate-50">
                    <tr>
                      <th className={encabezado}>Código</th>
                      <th className={encabezado}>Tipo</th>
                      <th className={encabezado}>Capacidad</th>
                      <th className={encabezado}>Estado</th>
                      <th className={encabezado}></th>
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
                        <td className={`${celda} text-slate-600`}>
                          {s.activo ? "Activo" : "Inactivo"}
                        </td>
                        <td className={`${celda} text-right`}>
                          {puedeEditar && (
                            <button
                              type="button"
                              onClick={() =>
                                setSimple({
                                  entidad: "silo",
                                  id: s.id,
                                  valores: {
                                    codigo: s.codigo,
                                    tipo: s.tipo,
                                    capacidad_l: s.capacidad_l,
                                    activo: s.activo,
                                  },
                                })
                              }
                              title="Editar"
                              className="rounded-lg p-1.5 text-slate-600 hover:bg-slate-100 hover:text-slate-700"
                            >
                              <Pencil className="h-4 w-4" />
                            </button>
                          )}
                        </td>
                      </tr>

                    ))}

                  </tbody>

                </table>

                <p className="border-t border-slate-100 px-6 py-3 text-sm text-slate-600">
                  La capacidad se configura aquí; la <strong>ocupación</strong> no,
                  porque es el saldo del libro de movimientos y se ve en Recepción
                  y silos. Escribirla a mano la desalinearía de los movimientos que
                  la producen.
                </p>

              </section>

            )}

            {/* Camiones */}

            {pestana === "camiones" && (

              <section className="rounded-2xl border border-slate-200 bg-white">

                {puedeEditar && (
                  <div className="border-b border-slate-100 px-4 py-3">
                    <button
                      type="button"
                      onClick={() =>
                        setSimple({
                          entidad: "camion",
                          id: null,
                          valores: { tipo: "Camión", activo: true },
                        })
                      }
                      className="inline-flex items-center gap-2 rounded-xl bg-green-700 px-4 py-2.5 text-sm font-semibold text-white hover:bg-green-800"
                    >
                      <Plus className="h-4 w-4" />
                      Nuevo camión
                    </button>
                  </div>
                )}

                {camiones.length === 0 ? (

                  <p className="px-6 py-10 text-center text-sm text-slate-600">
                    Todavía no hay camiones.
                  </p>

                ) : (

                  <table className="w-full">

                    <thead className="bg-slate-50">
                      <tr>
                        <th className={encabezado}>Placa</th>
                        <th className={encabezado}>Transportista</th>
                        <th className={encabezado}>Choferes</th>
                        <th className={encabezado}>Capacidad</th>
                        <th className={encabezado}></th>
                      </tr>
                    </thead>

                    <tbody>

                      {camiones.map((v) => (

                        <tr key={v.id} className="border-t border-slate-100">

                          <td className={`${celda} font-medium text-slate-800`}>
                            {v.placa}
                            {v.numero && (
                              <span className="ml-2 text-xs text-slate-600">
                                n.º {v.numero}
                              </span>
                            )}
                          </td>

                          <td className={`${celda} text-slate-600`}>
                            {v.transportista || "—"}
                          </td>

                          <td className={`${celda} text-slate-600`}>
                            {[v.chofer_am, v.chofer_pm].filter(Boolean).join(" · ") || "—"}
                          </td>

                          <td className={`${celda} tabular-nums text-slate-600`}>
                            {v.capacidad_l
                              ? `${Number(v.capacidad_l).toLocaleString("es-CL")} L`
                              : "—"}
                          </td>

                          <td className={`${celda} text-right`}>
                            {puedeEditar && (
                              <button
                                type="button"
                                onClick={() =>
                                  setSimple({
                                    entidad: "camion",
                                    id: v.id,
                                    valores: {
                                      placa: v.placa,
                                      numero: v.numero,
                                      tipo: v.tipo,
                                      capacidad_l: v.capacidad_l,
                                      transportista: v.transportista,
                                      chofer_am: v.chofer_am,
                                      chofer_pm: v.chofer_pm,
                                      activo: v.activo,
                                    },
                                  })
                                }
                                title="Editar"
                                className="rounded-lg p-1.5 text-slate-600 hover:bg-slate-100 hover:text-slate-700"
                              >
                                <Pencil className="h-4 w-4" />
                              </button>
                            )}
                          </td>

                        </tr>

                      ))}

                    </tbody>

                  </table>

                )}

              </section>

            )}

            {/* Códigos de producción */}

            {pestana === "codigos" && (

              <section className="rounded-2xl border border-slate-200 bg-white">

                {puedeEditar && (
                  <div className="border-b border-slate-100 px-4 py-3">
                    <button
                      type="button"
                      onClick={() =>
                        setSimple({
                          entidad: "codigo",
                          id: null,
                          valores: { activo: true },
                        })
                      }
                      className="inline-flex items-center gap-2 rounded-xl bg-green-700 px-4 py-2.5 text-sm font-semibold text-white hover:bg-green-800"
                    >
                      <Plus className="h-4 w-4" />
                      Nuevo código
                    </button>
                  </div>
                )}

                <table className="w-full">

                  <thead className="bg-slate-50">
                    <tr>
                      <th className={encabezado}>Código</th>
                      <th className={encabezado}>Producto</th>
                      <th className={encabezado}>Consumo</th>
                      <th className={encabezado}>Rendimiento</th>
                      <th className={encabezado}></th>
                    </tr>
                  </thead>

                  <tbody>

                    {codigos.map((k) => (

                      <tr key={k.id} className="border-t border-slate-100">

                        <td className={`${celda} font-medium text-slate-800`}>
                          {k.codigo}
                          {k.nombre && (
                            <div className="text-xs font-normal text-slate-600">
                              {k.nombre}
                            </div>
                          )}
                        </td>

                        <td className={`${celda} text-slate-600`}>
                          {k.producto_nombre || "—"}
                          <div className="text-xs text-slate-600">
                            {k.mandante_nombre || ""}
                          </div>
                        </td>

                        <td className={`${celda} text-slate-600`}>
                          {k.categoria_etiqueta}
                        </td>

                        <td className={`${celda} tabular-nums text-slate-600`}>
                          {Number(k.rendimiento_lh).toLocaleString("es-CL")} L/h
                        </td>

                        <td className={`${celda} text-right`}>
                          {puedeEditar && (
                            <button
                              type="button"
                              onClick={() =>
                                setSimple({
                                  entidad: "codigo",
                                  id: k.id,
                                  valores: {
                                    codigo: k.codigo,
                                    nombre: k.nombre,
                                    producto: k.producto,
                                    mandante: k.mandante,
                                    formato: k.formato,
                                    categoria: k.categoria,
                                    rendimiento_lh: k.rendimiento_lh,
                                    activo: k.activo,
                                  },
                                })
                              }
                              title="Editar"
                              className="rounded-lg p-1.5 text-slate-600 hover:bg-slate-100 hover:text-slate-700"
                            >
                              <Pencil className="h-4 w-4" />
                            </button>
                          )}
                        </td>

                      </tr>

                    ))}

                  </tbody>

                </table>

                <p className="border-t border-slate-100 px-6 py-3 text-sm text-slate-600">
                  El <strong>rendimiento</strong> convierte horas de programa en
                  litros de leche: es lo que hace que el balance semanal cuadre o
                  no. Un código es una forma de programar un producto, no un
                  producto nuevo.
                </p>

              </section>

            )}

          </>

        )}

        <p className="mt-6 text-xs text-slate-600">
          Lo que decide sobre la calidad del producto —especificaciones y
          checklist— lo escribe Calidad, no Administración. Del admin de Django
          queda una cosa: la <strong>plantilla</strong> de cada documento de
          liberación, que se construye contra el formato operacional.
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

      {simple && (
        <FormularioMaestro
          titulo={`${simple.id ? "Editar" : "Nuevo"} ${TITULO_SIMPLE[simple.entidad]}`}
          campos={camposDe(
            simple.entidad,
            catalogos,
            catPlan,
            productos,
            mandantes,
          )}
          valores={simple.valores}
          edicion={simple.id !== null}
          alCerrar={() => setSimple(null)}
          alGuardar={(datos) => {
            if (simple.entidad === "silo") return guardarSilo(simple.id, datos);
            if (simple.entidad === "camion")
              return guardarVehiculo(simple.id, datos);
            return guardarCodigo(simple.id, datos);
          }}
          alTerminar={cargar}
        />
      )}

      {(nuevoEquipo || editandoEquipo) && (
        <FormularioEquipo
          equipo={editandoEquipo}
          alCerrar={() => {
            setNuevoEquipo(false);
            setEditandoEquipo(null);
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

      {spec && (
        <FormularioEspecificacion
          modo={spec.modo}
          inicial={spec.inicial}
          productos={productos}
          parametros={parametros}
          onGuardar={guardarSpec}
          onCerrar={() => setSpec(null)}
        />
      )}

    </div>
  );
}


export default Maestros;
