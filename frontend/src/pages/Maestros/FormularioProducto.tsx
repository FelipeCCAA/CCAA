import { useState } from "react";
import { X } from "lucide-react";
import axios from "axios";

import {
  crearProducto,
  editarProducto,
  type CatalogosSku,
  type Mandante,
  type OpcionCatalogo,
  type ProductoEditable,
  type ProductoMaestro,
} from "../../services/maestros.service";


/*
  Alta y edición de un producto, con su SKU.

  El SKU **no se escribe**: lo compone el backend desde los atributos al
  guardar, y el formulario muestra el código ya guardado, no una predicción.
  Se pensó en previsualizarlo aquí y se descartó: reproducir el generador en
  el frontend crea una segunda implementación que puede decir algo distinto
  de la que manda, justo en el dato que se imprime en el saco. Lo que sí se
  anticipa es **qué falta** para poder componerlo, que no requiere replicar
  nada.

  Los catálogos de cada segmento vienen del backend por la misma razón.

  El cliente del SKU sale del mandante y no se pregunta aparte: preguntarlo
  dos veces es como las dos copias terminan diciendo cosas distintas.
*/

interface Props {
  producto: ProductoMaestro | null;
  mandantes: Mandante[];
  catalogos: CatalogosSku;
  alCerrar: () => void;
  alGuardar: () => void;
}


/*
  El campo va **dentro** del `<label>`, no al lado.

  Así la asociación es implícita y no depende de mantener a mano un `id` y un
  `htmlFor` que coincidan. Sin eso, un lector de pantalla no sabe qué etiqueta
  corresponde a qué campo y hacer clic en el texto no enfoca el control.
*/
function Campo({
  etiqueta,
  ayuda,
  children,
}: {
  etiqueta: string;
  ayuda?: string;
  children: React.ReactNode;
}) {
  return (
    <label className="block">
      <span className="mb-1.5 block text-sm font-medium text-slate-700">
        {etiqueta}
      </span>
      {children}
      {ayuda && <span className="mt-1 block text-xs text-slate-400">{ayuda}</span>}
    </label>
  );
}


function FormularioProducto({
  producto,
  mandantes,
  catalogos,
  alCerrar,
  alGuardar,
}: Props) {

  const [datos, setDatos] = useState<ProductoEditable>({
    nombre: producto?.nombre ?? "",
    mandante: producto?.mandante,
    familia: producto?.familia ?? "",
    naturaleza: producto?.naturaleza ?? "terminado",
    unidad_base: producto?.unidad_base ?? "kg",
    naturaleza_comercial: producto?.naturaleza_comercial ?? "",
    categoria: producto?.categoria ?? "",
    tipo: producto?.tipo ?? "",
    formato: producto?.formato ?? "",
    mercado: producto?.mercado ?? "local",
    variante: producto?.variante ?? null,
    activo: producto?.activo ?? true,
  });

  const [guardando, setGuardando] = useState(false);
  const [error, setError] = useState("");
  const [errorSku, setErrorSku] = useState("");

  const escribir = (campo: keyof ProductoEditable, valor: unknown) =>
    setDatos((d) => ({ ...d, [campo]: valor }));

  const mandante = mandantes.find((m) => m.id === Number(datos.mandante));

  /* Qué le falta al SKU para poder componerse. Se dice antes de guardar, en
     vez de mostrar un código vacío sin explicación. */
  const faltantes: string[] = [];
  if (!mandante) faltantes.push("mandante");
  else if (!mandante.codigo_cliente) faltantes.push("código de cliente del mandante");
  if (!datos.naturaleza_comercial) faltantes.push("naturaleza comercial");
  if (!datos.categoria) faltantes.push("categoría");
  if (!datos.tipo) faltantes.push("tipo");
  if (!datos.formato) faltantes.push("formato");

  const guardar = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();

    setError("");
    setErrorSku("");
    setGuardando(true);

    const carga: ProductoEditable = {
      ...datos,
      mandante: Number(datos.mandante),
      variante: datos.variante ? Number(datos.variante) : null,
    };

    try {

      if (producto) {
        await editarProducto(producto.id, carga);
      } else {
        await crearProducto(carga);
      }

      alGuardar();
      alCerrar();

    } catch (e) {

      if (axios.isAxiosError(e) && e.response) {
        const cuerpo = e.response.data as Record<string, string[] | string>;

        // El backend rechaza la combinación imposible por
        // `naturaleza_comercial`, con el motivo del generador.
        if (cuerpo.naturaleza_comercial) {
          setErrorSku(String(cuerpo.naturaleza_comercial));
        }

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

  const selector = (
    clave: keyof ProductoEditable,
    opciones: OpcionCatalogo[],
    vacio = "—",
  ) => (
    <select
      className={campo}
      value={String(datos[clave] ?? "")}
      onChange={(e) => escribir(clave, e.target.value)}
    >
      <option value="">{vacio}</option>
      {opciones.map((o) => (
        <option key={o.valor} value={o.valor}>
          {o.etiqueta}
        </option>
      ))}
    </select>
  );

  return (
    <div className="fixed inset-0 z-50 flex items-start justify-center overflow-y-auto bg-slate-900/40 p-4 sm:p-8">

      <div className="w-full max-w-3xl rounded-2xl bg-white shadow-xl">

        <div className="flex items-center justify-between border-b border-slate-200 px-6 py-5">

          <div>

            <h2 className="text-lg font-semibold text-slate-800">
              {producto ? "Editar producto" : "Nuevo producto"}
            </h2>

            <p className="mt-0.5 text-sm text-slate-500">
              El SKU se genera con los atributos: no se escribe a mano.
            </p>

          </div>

          <button
            type="button"
            onClick={alCerrar}
            className="rounded-lg p-1 text-slate-400 hover:bg-slate-100 hover:text-slate-700"
            aria-label="Cerrar"
          >
            <X className="h-5 w-5" />
          </button>

        </div>

        <form onSubmit={guardar} className="px-6 py-6">

          <div className="grid grid-cols-1 gap-5 sm:grid-cols-2">

            <div className="sm:col-span-2">
              <Campo etiqueta="Nombre *">
                <input
                  className={campo}
                  value={datos.nombre ?? ""}
                  onChange={(e) => escribir("nombre", e.target.value)}
                  required
                />
              </Campo>
            </div>

            <Campo
              etiqueta="Mandante *"
              ayuda={
                mandante && !mandante.codigo_cliente
                  ? "Este mandante no tiene código de cliente: sus productos no generan SKU."
                  : "De aquí sale el segmento de cliente del SKU."
              }
            >
              <select
                className={campo}
                value={String(datos.mandante ?? "")}
                onChange={(e) => escribir("mandante", e.target.value)}
                required
              >
                <option value="">Selecciona…</option>
                {mandantes.map((m) => (
                  <option key={m.id} value={m.id}>
                    {m.nombre}
                    {m.codigo_cliente ? "" : "  (sin código de cliente)"}
                  </option>
                ))}
              </select>
            </Campo>

            <Campo etiqueta="Familia *">
              <select
                className={campo}
                value={datos.familia ?? ""}
                onChange={(e) => escribir("familia", e.target.value)}
                required
              >
                <option value="">—</option>
                {catalogos.familia.map((o) => (
                  <option key={o.valor} value={o.valor}>
                    {o.etiqueta}
                  </option>
                ))}
              </select>
            </Campo>

            <Campo
              etiqueta="Naturaleza"
              ayuda="Dónde está en la cadena. No es la naturaleza comercial del SKU."
            >
              {selector("naturaleza", catalogos.naturaleza)}
            </Campo>

            <Campo etiqueta="Unidad base">
              {selector("unidad_base", catalogos.unidad_base)}
            </Campo>

          </div>

          {/* SKU */}

          <div className="mt-8 border-t border-slate-200 pt-6">

            <h3 className="text-sm font-semibold text-slate-800">SKU</h3>

            <p className="mt-1 mb-5 text-sm text-slate-400">
              Cuatro atributos más el código de cliente del mandante. Se compone
              solo desde catálogos: no admite valores inventados.
            </p>

            <div className="grid grid-cols-1 gap-5 sm:grid-cols-2">

              <Campo
                etiqueta="Naturaleza comercial"
                ayuda="Producto propio va sin cliente; servicio a terceros, con uno."
              >
                {selector("naturaleza_comercial", catalogos.naturaleza_comercial)}
              </Campo>

              {/* El cliente es un segmento del SKU como los demás, pero no se
                  elige: lo dice el mandante. Se muestra igual, porque si no
                  la mitad del código se compone con algo que no está en
                  pantalla. */}
              <div>

                <span className="mb-1.5 block text-sm font-medium text-slate-700">
                  Cliente
                </span>

                <div className="rounded-xl border border-slate-200 bg-slate-50 px-4 py-3 text-slate-700">
                  {!mandante
                    ? "— elige el mandante"
                    : mandante.codigo_cliente
                      ? mandante.codigo_cliente_etiqueta
                      : "sin código de cliente"}
                </div>

                <span className="mt-1 block text-xs text-slate-400">
                  {mandante && !mandante.codigo_cliente
                    ? `Asígnale uno a «${mandante.nombre}» en la pestaña Mandantes.`
                    : "Lo define el mandante: no se elige aquí para que no haya dos copias que se contradigan."}
                </span>

              </div>

              <Campo etiqueta="Categoría">
                {selector("categoria", catalogos.categoria)}
              </Campo>

              <Campo etiqueta="Tipo">{selector("tipo", catalogos.tipo)}</Campo>

              <Campo etiqueta="Formato">
                {selector("formato", catalogos.formato)}
              </Campo>

              <Campo etiqueta="Mercado">
                {selector("mercado", catalogos.mercado)}
              </Campo>

              <Campo
                etiqueta="Variante"
                ayuda="Solo si dos productos comparten los seis segmentos."
              >
                <input
                  type="number"
                  min="0"
                  max="99"
                  className={campo}
                  value={datos.variante ?? ""}
                  onChange={(e) =>
                    escribir("variante", e.target.value === "" ? null : e.target.value)
                  }
                />
              </Campo>

            </div>

            {/* Qué código va a salir */}

            <div className="mt-5 rounded-xl bg-slate-50 p-4">

              {faltantes.length > 0 ? (

                <>
                  <p className="text-sm font-medium text-slate-700">
                    Todavía sin SKU
                  </p>
                  <p className="mt-1 text-sm text-slate-500">
                    Falta: {faltantes.join(", ")}. El producto se guarda igual y
                    conserva el código que tenga.
                  </p>
                </>

              ) : (

                <>
                  <p className="text-xs text-slate-400">
                    {producto?.codigo ? "SKU actual" : "SKU al guardar"}
                  </p>
                  <p className="mt-0.5 font-mono text-lg font-medium tabular-nums text-slate-800">
                    {producto?.codigo || "se genera al guardar"}
                  </p>
                  <p className="mt-1 text-xs text-slate-400">
                    Lo compone el servidor con estos atributos. Si cambias uno,
                    el código se recalcula.
                  </p>
                </>

              )}

              {errorSku && (
                <p className="mt-3 rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">
                  {errorSku}
                </p>
              )}

            </div>

          </div>

          <label className="mt-6 flex items-center gap-2 text-sm text-slate-700">
            <input
              type="checkbox"
              checked={datos.activo ?? true}
              onChange={(e) => escribir("activo", e.target.checked)}
            />
            Activo
          </label>

          {error && !errorSku && (
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
              {guardando ? "Guardando…" : producto ? "Guardar cambios" : "Crear producto"}
            </button>

          </div>

        </form>

      </div>

    </div>
  );
}


export default FormularioProducto;
