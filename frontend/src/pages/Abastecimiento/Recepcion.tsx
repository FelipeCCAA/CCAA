import { useState } from "react";
import { PackageCheck, Send, Thermometer } from "lucide-react";

import {
  crearRecepcionCompra,
  enviarOrdenCompra,
  obtenerOrdenesCompra,
  obtenerUbicaciones,
  recibirLineaCompra,
  type DetalleOrdenCompra,
  type OrdenCompra,
} from "../../services/inventario.service";

import { obtenerSesion } from "../../services/sesion";

import { Aviso, Estado, Tarjeta, Vacio } from "../../components/seccion/componentes";
import {
  claseBoton,
  claseCampo,
  claseCelda,
  claseEncabezado,
  mensajeDe,
  numero,
  useCarga,
} from "../../components/seccion/utilidades";


/*
  Recepción contra orden: lo que llega del proveedor.

  Es el eslabón que cerraba el circuito. Antes terminaba en la orden emitida y
  no había forma de registrar que el material llegó — el servicio existía y
  ninguna pantalla lo llamaba.

  Recibir una línea hace cinco cosas en una transacción: crea el lote del
  proveedor, lo manda a cuarentena si el material pasa por Calidad y le abre
  su inspección, registra la entrada en el libro, suma a lo recibido de la
  orden y avanza el estado de la orden a parcial o recibida.

  La pantalla muestra **qué exige cada material** antes de pedir los datos.
  `recibir_detalle_compra` rechaza la recepción si falta el lote, el
  vencimiento, la temperatura o el certificado que el material declara, y
  descubrirlo al enviar el formulario obliga a rehacerlo con el camión
  esperando en el andén.
*/

const ABIERTAS = ["aprobada", "enviada", "parcial"];

const VACIA = {
  codigo_lote: "",
  cantidad: "",
  cantidad_danada: "",
  elaboracion: "",
  vencimiento: "",
  temperatura: "",
  embalaje_conforme: true,
  certificado_recibido: false,
};


function Exigencias({ linea }: { linea: DetalleOrdenCompra }) {
  const cosas = [
    linea.requiere_lote && "lote",
    linea.requiere_vencimiento && "vencimiento",
    linea.requiere_temperatura && "temperatura",
    linea.requiere_certificado && "certificado",
  ].filter(Boolean) as string[];

  if (cosas.length === 0 && !linea.requiere_calidad) {
    return <span className="text-xs text-slate-600">sin exigencias</span>;
  }

  return (
    <span className="flex flex-wrap gap-1">
      {linea.requiere_calidad && (
        <span className="rounded-full bg-amber-50 px-2 py-0.5 text-xs font-medium text-amber-800">
          a cuarentena
        </span>
      )}
      {cosas.map((c) => (
        <span
          key={c}
          className="rounded-full bg-slate-100 px-2 py-0.5 text-xs text-slate-600"
        >
          {c}
        </span>
      ))}
    </span>
  );
}


function Recepcion() {

  const ordenes = useCarga(obtenerOrdenesCompra);
  const ubicaciones = useCarga(obtenerUbicaciones);

  const [error, setError] = useState("");
  const [aviso, setAviso] = useState("");

  /* Qué línea se está recibiendo, y la cabecera del documento del proveedor.
     La guía va en la cabecera porque una guía trae varias líneas. */
  const [recibiendo, setRecibiendo] = useState<{
    orden: OrdenCompra;
    linea: DetalleOrdenCompra;
  } | null>(null);
  const [guia, setGuia] = useState("");
  const [ubicacion, setUbicacion] = useState("");
  const [datos, setDatos] = useState(VACIA);

  const sesion = obtenerSesion();
  const area = sesion?.usuario.perfil?.area;
  const puedeRecibir =
    area === "recepcion" || area === "bodega" || sesion?.usuario.rol === "admin";

  const abrir = (orden: OrdenCompra, linea: DetalleOrdenCompra) => {
    setError("");
    setAviso("");
    setRecibiendo({ orden, linea });
    setDatos({
      ...VACIA,
      // Lo pendiente por omisión: es lo que llega la mayoría de las veces, y
      // corregirlo es más rápido que teclearlo entero.
      cantidad: String(Number(linea.cantidad) - Number(linea.cantidad_recibida)),
    });
    setUbicacion("");
    setGuia("");
  };

  const enviar = async (orden: OrdenCompra) => {
    setError("");

    try {
      await enviarOrdenCompra(orden.id);
      await ordenes.recargar();
    } catch (e) {
      setError(mensajeDe(e, "No se pudo enviar la orden."));
    }
  };

  const recibir = async (evento: React.FormEvent) => {
    evento.preventDefault();

    if (!recibiendo) return;

    setError("");

    try {
      // Cabecera y línea van juntas: una recepción sin líneas no registra
      // nada y quedaría ocupando el listado.
      const recepcion = await crearRecepcionCompra({
        orden: recibiendo.orden.id,
        guia,
      });

      const { lote } = await recibirLineaCompra(recepcion.id, {
        detalle_orden: recibiendo.linea.id,
        ubicacion: Number(ubicacion),
        codigo_lote: datos.codigo_lote,
        cantidad: datos.cantidad,
        cantidad_danada: datos.cantidad_danada || 0,
        elaboracion: datos.elaboracion || null,
        vencimiento: datos.vencimiento || null,
        temperatura: datos.temperatura || null,
        embalaje_conforme: datos.embalaje_conforme,
        certificado_recibido: datos.certificado_recibido,
      });

      setAviso(
        `Recibido. Lote ${lote} creado` +
          (recibiendo.linea.requiere_calidad
            ? " y en cuarentena esperando a Calidad."
            : " y disponible."),
      );
      setRecibiendo(null);
      await ordenes.recargar();
    } catch (e) {
      setError(mensajeDe(e, "No se pudo registrar la recepción."));
    }
  };

  const abiertas = (ordenes.datos ?? []).filter((o) =>
    ABIERTAS.includes(o.estado),
  );

  const borradores = (ordenes.datos ?? []).filter((o) => o.estado === "borrador");

  /* La cuarentena es obligatoria para lo que pasa por Calidad, y el servicio
     rechaza la entrada si no corresponde. El desplegable ofrece solo las que
     sirven en vez de dejar elegir mal. */
  const ubicacionesValidas = (linea: DetalleOrdenCompra) =>
    (ubicaciones.datos ?? [])
      .filter((u) => u.activo)
      .filter((u) =>
        linea.requiere_calidad
          ? u.tipo === "cuarentena"
          : u.tipo === "disponible",
      );

  return (
    <div className="space-y-8">

      {error && <Aviso>{error}</Aviso>}

      {aviso && (
        <div className="rounded-2xl border border-green-200 bg-green-50 px-5 py-4 text-sm text-green-800">
          {aviso}
        </div>
      )}

      {borradores.length > 0 && (
        <Tarjeta
          titulo="Órdenes sin enviar"
          descripcion="Un borrador no compromete a nadie: el MRP no lo cuenta como material en camino y no se puede recibir contra él."
          sinRelleno
        >
          <div className="divide-y divide-slate-100">
            {borradores.map((o) => (
              <div
                key={o.id}
                className="flex flex-wrap items-center justify-between gap-3 px-5 py-4"
              >
                <p className="font-medium text-slate-800">
                  {o.numero}
                  <span className="ml-2 text-sm font-normal text-slate-600">
                    {o.proveedor_nombre} · {o.detalles.length} línea(s)
                  </span>
                </p>

                <button
                  onClick={() => void enviar(o)}
                  className="flex items-center gap-2 rounded-lg bg-blue-700 px-3 py-1.5 text-xs font-semibold text-white"
                >
                  <Send className="h-3.5 w-3.5" />
                  Enviar al proveedor
                </button>
              </div>
            ))}
          </div>
        </Tarjeta>
      )}

      <Tarjeta
        titulo="Pendiente de recibir"
        descripcion="Lo comprometido con proveedores que todavía no llega. Cada línea se recibe contra su renglón de la orden."
        sinRelleno
      >
        {ordenes.error ? (
          <div className="p-5">
            <Aviso>{ordenes.error}</Aviso>
          </div>
        ) : ordenes.cargando ? (
          <Vacio>Cargando…</Vacio>
        ) : abiertas.length === 0 ? (
          <Vacio>
            No hay órdenes enviadas esperando material. Se emiten desde
            Compras, al convertir una solicitud aprobada.
          </Vacio>
        ) : (
          <div className="divide-y divide-slate-100">
            {abiertas.map((o) => (
              <div key={o.id} className="p-5">

                <p className="flex flex-wrap items-center gap-2 font-medium text-slate-800">
                  <PackageCheck className="h-4 w-4 text-slate-600" />
                  {o.numero}
                  <Estado valor={o.estado} />
                  <span className="text-sm font-normal text-slate-600">
                    {o.proveedor_nombre}
                    {o.fecha_comprometida
                      ? ` · comprometida ${o.fecha_comprometida}`
                      : ""}
                  </span>
                </p>

                <table className="mt-4 w-full">
                  <thead>
                    <tr>
                      <th className={claseEncabezado}>Material</th>
                      <th className={claseEncabezado}>Pedido</th>
                      <th className={claseEncabezado}>Recibido</th>
                      <th className={claseEncabezado}>Pendiente</th>
                      <th className={claseEncabezado}>Exige</th>
                      <th className={claseEncabezado}></th>
                    </tr>
                  </thead>
                  <tbody>
                    {o.detalles.map((d) => {
                      const pendiente =
                        Number(d.cantidad) - Number(d.cantidad_recibida);

                      return (
                        <tr key={d.id} className="border-t border-slate-100">
                          <td className={`${claseCelda} text-slate-800`}>
                            {d.insumo_nombre}
                          </td>
                          <td className={`${claseCelda} text-slate-600`}>
                            {numero(d.cantidad)} {d.insumo_unidad}
                          </td>
                          <td className={`${claseCelda} text-slate-600`}>
                            {numero(d.cantidad_recibida)}
                          </td>
                          <td className={claseCelda}>
                            <span
                              className={
                                pendiente > 0
                                  ? "font-semibold text-amber-700"
                                  : "text-slate-600"
                              }
                            >
                              {numero(pendiente)}
                            </span>
                          </td>
                          <td className={claseCelda}>
                            <Exigencias linea={d} />
                          </td>
                          <td className={`${claseCelda} text-right`}>
                            {puedeRecibir && pendiente > 0 && (
                              <button
                                onClick={() => abrir(o, d)}
                                className="rounded-lg bg-green-700 px-3 py-1.5 text-xs font-semibold text-white"
                              >
                                Recibir
                              </button>
                            )}
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>

              </div>
            ))}
          </div>
        )}
      </Tarjeta>

      {recibiendo && (
        <Tarjeta
          titulo={`Recibir ${recibiendo.linea.insumo_nombre}`}
          descripcion={`Orden ${recibiendo.orden.numero} · ${recibiendo.orden.proveedor_nombre}`}
          acciones={
            <button
              type="button"
              onClick={() => setRecibiendo(null)}
              className="rounded-xl border border-slate-200 px-4 py-2 text-sm font-medium text-slate-600 hover:bg-slate-50"
            >
              Cancelar
            </button>
          }
        >
          <form onSubmit={recibir} className="grid gap-3 sm:grid-cols-2">

            <input
              required
              placeholder="Guía de despacho"
              value={guia}
              onChange={(e) => setGuia(e.target.value)}
              className={claseCampo}
            />

            <select
              required
              value={ubicacion}
              onChange={(e) => setUbicacion(e.target.value)}
              className={claseCampo}
            >
              <option value="">
                {recibiendo.linea.requiere_calidad
                  ? "Ubicación de cuarentena…"
                  : "Ubicación disponible…"}
              </option>
              {ubicacionesValidas(recibiendo.linea).map((u) => (
                <option key={u.id} value={u.id}>
                  {u.bodega_nombre}/{u.codigo}
                </option>
              ))}
            </select>

            {ubicacionesValidas(recibiendo.linea).length === 0 && (
              <p className="text-sm text-amber-800 sm:col-span-2">
                No hay ubicaciones de{" "}
                {recibiendo.linea.requiere_calidad ? "cuarentena" : "tipo disponible"}
                . Créalas en la pestaña Bodegas: este material no puede entrar
                sin una.
              </p>
            )}

            <input
              required={recibiendo.linea.requiere_lote}
              placeholder={
                recibiendo.linea.requiere_lote
                  ? "Lote del proveedor (obligatorio)"
                  : "Lote del proveedor"
              }
              value={datos.codigo_lote}
              onChange={(e) => setDatos({ ...datos, codigo_lote: e.target.value })}
              className={claseCampo}
            />

            <input
              required
              type="number"
              step="0.001"
              min="0.001"
              placeholder="Cantidad recibida"
              value={datos.cantidad}
              onChange={(e) => setDatos({ ...datos, cantidad: e.target.value })}
              className={claseCampo}
            />

            <input
              type="number"
              step="0.001"
              min="0"
              placeholder="Cantidad dañada"
              title="Se descuenta de lo utilizable, pero queda registrada"
              value={datos.cantidad_danada}
              onChange={(e) =>
                setDatos({ ...datos, cantidad_danada: e.target.value })
              }
              className={claseCampo}
            />

            {/* Los campos de fecha llevan etiqueta visible: un `dd-mm-yyyy`
                vacío no dice si es la elaboración o el vencimiento, y aquí se
                escriben dos seguidos con el camión esperando en el andén. El
                `title` no sirve — solo aparece al pasar el ratón por encima. */}
            <label className="text-sm text-slate-600">
              Elaboración
              <input
                type="date"
                value={datos.elaboracion}
                onChange={(e) => setDatos({ ...datos, elaboracion: e.target.value })}
                className={`${claseCampo} mt-1 w-full`}
              />
            </label>

            {recibiendo.linea.requiere_vencimiento && (
              <label className="text-sm text-slate-600">
                Vencimiento <span className="text-amber-700">(obligatorio)</span>
                <input
                  required
                  type="date"
                  value={datos.vencimiento}
                  onChange={(e) =>
                    setDatos({ ...datos, vencimiento: e.target.value })
                  }
                  className={`${claseCampo} mt-1 w-full`}
                />
              </label>
            )}

            {recibiendo.linea.requiere_temperatura && (
              <div className="relative">
                <Thermometer className="pointer-events-none absolute right-3 top-3 h-4 w-4 text-slate-600" />
                <input
                  required
                  type="number"
                  step="0.01"
                  placeholder="Temperatura de recepción (°C)"
                  value={datos.temperatura}
                  onChange={(e) =>
                    setDatos({ ...datos, temperatura: e.target.value })
                  }
                  className={`${claseCampo} w-full`}
                />
              </div>
            )}

            <label className="flex items-center gap-2 text-sm text-slate-700">
              <input
                type="checkbox"
                checked={datos.embalaje_conforme}
                onChange={(e) =>
                  setDatos({ ...datos, embalaje_conforme: e.target.checked })
                }
              />
              Embalaje conforme
            </label>

            {recibiendo.linea.requiere_certificado && (
              <label className="flex items-center gap-2 text-sm text-slate-700">
                <input
                  type="checkbox"
                  checked={datos.certificado_recibido}
                  onChange={(e) =>
                    setDatos({ ...datos, certificado_recibido: e.target.checked })
                  }
                />
                Certificado del proveedor recibido (obligatorio)
              </label>
            )}

            <button className={`${claseBoton} sm:col-span-2`}>
              Registrar recepción
            </button>

          </form>
        </Tarjeta>
      )}

    </div>
  );
}


export default Recepcion;
