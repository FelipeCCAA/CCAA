import { useState } from "react";
import { Check, FileText, ShoppingCart, X } from "lucide-react";

import {
  convertirSolicitudEnOrdenes,
  decidirSolicitudCompra,
  enviarSolicitudCompra,
  obtenerBodegas,
  obtenerDetallesSolicitudCompra,
  obtenerOrdenesCompra,
  obtenerSolicitudesCompra,
  type SolicitudCompra,
} from "../../services/inventario.service";

import { obtenerSesion } from "../../services/sesion";

import { Aviso, Estado, Tarjeta, Vacio } from "../../components/seccion/componentes";
import {
  claseCampo,
  claseCelda,
  claseEncabezado,
  mensajeDe,
  numero,
  useCarga,
} from "../../components/seccion/utilidades";


/*
  Compras: de la solicitud a la orden del proveedor.

    borrador → pendiente → aprobada → convertida

  Cada flecha es una acción de alguien distinto, y eso es lo que hace que
  aprobar signifique algo: el backend rechaza que el solicitante apruebe su
  propia solicitud, así que la pantalla no le ofrece el botón. Ofrecerlo y
  dejar que el servidor lo rechace enseña a ignorar los errores.

  «Convertida» emite **una orden por proveedor**. Una sola obligaría a elegir
  uno y mandarle renglones que no vende.
*/

const PUEDE_ENVIARSE = ["borrador"];
const PUEDE_DECIDIRSE = ["pendiente", "enviada"];
const PUEDE_CONVERTIRSE = ["aprobada"];


function Compras() {

  const solicitudes = useCarga(obtenerSolicitudesCompra);
  const detalles = useCarga(obtenerDetallesSolicitudCompra);
  const ordenes = useCarga(obtenerOrdenesCompra);
  const bodegas = useCarga(obtenerBodegas);

  const [error, setError] = useState("");
  const [aviso, setAviso] = useState("");
  const [bodega, setBodega] = useState("");

  const sesion = obtenerSesion();
  const yo = sesion?.usuario.id;

  const refrescar = async () => {
    await Promise.all([solicitudes.recargar(), ordenes.recargar()]);
  };

  const accion = async (fn: () => Promise<unknown>, porDefecto: string) => {
    setError("");
    setAviso("");

    try {
      await fn();
      await refrescar();
    } catch (e) {
      setError(mensajeDe(e, porDefecto));
    }
  };

  const convertir = async (solicitud: SolicitudCompra) => {
    if (!bodega) {
      setError("Elige la bodega donde se recibe el material antes de convertir.");
      return;
    }

    setError("");

    try {
      const emitidas = await convertirSolicitudEnOrdenes(
        solicitud.id,
        Number(bodega),
      );
      setAviso(
        `${solicitud.numero}: ${emitidas.length} orden(es) emitida(s) — ` +
          emitidas.map((o) => o.numero).join(", "),
      );
      await refrescar();
    } catch (e) {
      setError(mensajeDe(e, "No se pudieron emitir las órdenes."));
    }
  };

  const lineasDe = (solicitud: number) =>
    (detalles.datos ?? []).filter((d) => d.solicitud === solicitud);

  const abiertas = (solicitudes.datos ?? []).filter(
    (s) => !["convertida", "rechazada", "cancelada"].includes(s.estado),
  );

  const cerradas = (solicitudes.datos ?? []).filter((s) =>
    ["convertida", "rechazada", "cancelada"].includes(s.estado),
  );

  return (
    <div className="space-y-8">

      {error && <Aviso>{error}</Aviso>}

      {aviso && (
        <div className="rounded-2xl border border-green-200 bg-green-50 px-5 py-4 text-sm text-green-800">
          {aviso}
        </div>
      )}

      <Tarjeta
        titulo="Solicitudes de compra"
        descripcion="Lo que se pidió y en qué punto está. Las que vienen del MRP traen sus líneas marcadas."
        acciones={
          <select
            value={bodega}
            onChange={(e) => setBodega(e.target.value)}
            className={`${claseCampo} shrink-0`}
            title="Bodega donde se recibe el material al convertir"
          >
            <option value="">Bodega de entrega…</option>
            {(bodegas.datos ?? [])
              .filter((b) => b.activo)
              .map((b) => (
                <option key={b.id} value={b.id}>
                  {b.codigo} · {b.nombre}
                </option>
              ))}
          </select>
        }
        sinRelleno
      >
        {solicitudes.error ? (
          <div className="p-5">
            <Aviso>{solicitudes.error}</Aviso>
          </div>
        ) : solicitudes.cargando ? (
          <Vacio>Cargando…</Vacio>
        ) : abiertas.length === 0 ? (
          <Vacio>
            No hay solicitudes abiertas. Se generan desde el MRP o se crean a
            mano en el administrador.
          </Vacio>
        ) : (
          <div className="divide-y divide-slate-100">
            {abiertas.map((s) => {
              const lineas = lineasDe(s.id);
              // Quien la pidió no la aprueba. El backend lo rechaza, así que
              // ofrecer el botón solo enseñaría a ignorar el error.
              const puedoDecidir =
                PUEDE_DECIDIRSE.includes(s.estado) && s.solicitante !== yo;

              return (
                <div key={s.id} className="p-5">

                  <div className="flex flex-wrap items-start justify-between gap-4">

                    <div className="min-w-0">
                      <p className="flex items-center gap-2 font-medium text-slate-800">
                        <FileText className="h-4 w-4 text-slate-400" />
                        {s.numero}
                        <Estado valor={s.estado} />
                      </p>
                      <p className="mt-1 text-sm text-slate-500">{s.motivo}</p>
                    </div>

                    <div className="flex shrink-0 flex-wrap gap-2">

                      {PUEDE_ENVIARSE.includes(s.estado) && (
                        <button
                          onClick={() =>
                            void accion(
                              () => enviarSolicitudCompra(s.id),
                              "No se pudo enviar.",
                            )
                          }
                          className="rounded-lg bg-blue-700 px-3 py-1.5 text-xs font-semibold text-white"
                        >
                          Enviar a aprobación
                        </button>
                      )}

                      {puedoDecidir && (
                        <>
                          <button
                            onClick={() =>
                              void accion(
                                () => decidirSolicitudCompra(s.id, "aprobada"),
                                "No se pudo aprobar.",
                              )
                            }
                            className="flex items-center gap-1 rounded-lg bg-green-700 px-3 py-1.5 text-xs font-semibold text-white"
                          >
                            <Check className="h-3.5 w-3.5" />
                            Aprobar
                          </button>
                          <button
                            onClick={() =>
                              void accion(
                                () => decidirSolicitudCompra(s.id, "rechazada"),
                                "No se pudo rechazar.",
                              )
                            }
                            className="flex items-center gap-1 rounded-lg bg-red-50 px-3 py-1.5 text-xs font-semibold text-red-700"
                          >
                            <X className="h-3.5 w-3.5" />
                            Rechazar
                          </button>
                        </>
                      )}

                      {PUEDE_DECIDIRSE.includes(s.estado) && s.solicitante === yo && (
                        <span className="rounded-lg bg-slate-100 px-3 py-1.5 text-xs text-slate-500">
                          La aprueba otra persona
                        </span>
                      )}

                      {PUEDE_CONVERTIRSE.includes(s.estado) && (
                        <button
                          onClick={() => void convertir(s)}
                          className="rounded-lg bg-green-700 px-3 py-1.5 text-xs font-semibold text-white"
                        >
                          Emitir órdenes
                        </button>
                      )}

                    </div>

                  </div>

                  {lineas.length > 0 && (
                    <table className="mt-4 w-full">
                      <thead>
                        <tr>
                          <th className={claseEncabezado}>Material</th>
                          <th className={claseEncabezado}>Cantidad</th>
                          <th className={claseEncabezado}>Requerido</th>
                          <th className={claseEncabezado}>Origen</th>
                        </tr>
                      </thead>
                      <tbody>
                        {lineas.map((d) => (
                          <tr key={d.id} className="border-t border-slate-100">
                            <td className={`${claseCelda} text-slate-800`}>
                              {d.insumo_nombre}
                            </td>
                            <td className={`${claseCelda} text-slate-600`}>
                              {numero(d.cantidad)}
                            </td>
                            <td className={`${claseCelda} text-slate-600`}>
                              {d.fecha_requerida}
                            </td>
                            <td className={`${claseCelda} text-slate-500`}>
                              {d.origen_mrp ? "MRP" : "manual"}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  )}

                </div>
              );
            })}
          </div>
        )}
      </Tarjeta>

      <Tarjeta
        titulo="Órdenes de compra"
        descripcion="Lo comprometido con proveedores. «Recibida» la marca la recepción contra la orden, no un botón."
        sinRelleno
      >
        {ordenes.error ? (
          <div className="p-5">
            <Aviso>{ordenes.error}</Aviso>
          </div>
        ) : (ordenes.datos ?? []).length === 0 ? (
          <Vacio>Sin órdenes de compra.</Vacio>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead className="bg-slate-50">
                <tr>
                  <th className={claseEncabezado}>Orden</th>
                  <th className={claseEncabezado}>Proveedor</th>
                  <th className={claseEncabezado}>Comprometida</th>
                  <th className={claseEncabezado}>Estado</th>
                  <th className={claseEncabezado}>Avance</th>
                </tr>
              </thead>
              <tbody>
                {(ordenes.datos ?? []).map((o) => {
                  const pedido = o.detalles.reduce(
                    (s, d) => s + Number(d.cantidad),
                    0,
                  );
                  const recibido = o.detalles.reduce(
                    (s, d) => s + Number(d.cantidad_recibida),
                    0,
                  );

                  return (
                    <tr key={o.id} className="border-t border-slate-100">
                      <td className={`${claseCelda} font-medium text-slate-800`}>
                        <span className="inline-flex items-center gap-2">
                          <ShoppingCart className="h-4 w-4 text-slate-400" />
                          {o.numero}
                        </span>
                      </td>
                      <td className={`${claseCelda} text-slate-600`}>
                        {o.proveedor_nombre}
                      </td>
                      <td className={`${claseCelda} text-slate-600`}>
                        {o.fecha_comprometida ?? "—"}
                      </td>
                      <td className={claseCelda}>
                        <Estado valor={o.estado} />
                      </td>
                      <td className={`${claseCelda} text-slate-500`}>
                        {numero(recibido)} de {numero(pedido)}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </Tarjeta>

      {cerradas.length > 0 && (
        <Tarjeta titulo="Solicitudes cerradas" sinRelleno>
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead className="bg-slate-50">
                <tr>
                  <th className={claseEncabezado}>Solicitud</th>
                  <th className={claseEncabezado}>Área</th>
                  <th className={claseEncabezado}>Estado</th>
                </tr>
              </thead>
              <tbody>
                {cerradas.map((s) => (
                  <tr key={s.id} className="border-t border-slate-100">
                    <td className={`${claseCelda} font-medium text-slate-800`}>
                      {s.numero}
                    </td>
                    <td className={`${claseCelda} text-slate-600`}>{s.area}</td>
                    <td className={claseCelda}>
                      <Estado valor={s.estado} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Tarjeta>
      )}

      <Tarjeta titulo="Lo que falta en esta pestaña">
        <ul className="space-y-2 text-sm text-slate-500">
          <li>
            · <span className="font-medium text-slate-700">Recepción contra orden</span>,
            que es lo que crea el lote y lo manda a cuarentena. El servicio
            existe; falta la pantalla.
          </li>
          <li>
            · <span className="font-medium text-slate-700">Proveedores</span> y sus
            condiciones por material: precio, compra mínima, múltiplo y plazo.
            Hoy se cargan en el administrador, y sin un proveedor principal la
            solicitud no se puede convertir.
          </li>
        </ul>
      </Tarjeta>

    </div>
  );
}


export default Compras;
