import { Link, useParams } from "react-router-dom";
import { ArrowLeft, CalendarX2, ShieldCheck, ShieldX } from "lucide-react";

import {
  obtenerExistenciasDeLote,
  obtenerLoteInventario,
  obtenerMovimientosDeLote,
} from "../../services/inventario.service";

import { Aviso, Estado, Tarjeta, Vacio } from "../../components/seccion/componentes";
import {
  claseCelda,
  claseEncabezado,
  numero,
  useCarga,
} from "../../components/seccion/utilidades";


/*
  Ficha de un lote de proveedor.

  Es la **primera pantalla de detalle del sistema**: hasta ahora la aplicación
  entera eran listas planas y ninguna ruta llevaba parámetro, así que un
  documento no se podía enlazar, ni compartir, ni volver a él. Este archivo
  fija el patrón que van a seguir la orden de compra y el pedido interno:

    cabecera con lo que identifica y decide · dónde está · qué le pasó

  El historial no es decoración. Cada movimiento trae el saldo antes y después,
  así que la cifra de arriba se puede reconstruir línea por línea — que es la
  diferencia entre un inventario que se cree y uno que se audita.
*/

function Dato({ etiqueta, children }: { etiqueta: string; children: React.ReactNode }) {
  return (
    <div>
      <p className="text-xs uppercase tracking-wide text-slate-400">{etiqueta}</p>
      <p className="mt-1 text-sm font-medium text-slate-800">{children}</p>
    </div>
  );
}


function DetalleLoteInventario() {

  const { id } = useParams();
  const numeroId = Number(id);

  const lote = useCarga(() => obtenerLoteInventario(numeroId));
  const existencias = useCarga(() => obtenerExistenciasDeLote(numeroId));
  const movimientos = useCarga(() => obtenerMovimientosDeLote(numeroId));

  const volver = (
    <Link
      to="/abastecimiento/stock"
      className="mb-6 inline-flex items-center gap-2 text-sm font-medium text-slate-500 hover:text-slate-800"
    >
      <ArrowLeft className="h-4 w-4" />
      Volver a stock
    </Link>
  );

  if (lote.error) {
    return (
      <div>
        {volver}
        <Aviso>No se pudo cargar el lote. {lote.error}</Aviso>
      </div>
    );
  }

  if (!lote.datos) {
    return (
      <div>
        {volver}
        <Vacio>Cargando…</Vacio>
      </div>
    );
  }

  const l = lote.datos;

  const fisico = (existencias.datos ?? []).reduce(
    (suma, e) => suma + Number(e.cantidad_fisica),
    0,
  );

  const disponible = (existencias.datos ?? []).reduce(
    (suma, e) => suma + Number(e.cantidad_disponible),
    0,
  );

  return (
    <div className="space-y-8">

      {volver}

      <Tarjeta>

        <div className="flex flex-wrap items-start justify-between gap-4">

          <div>
            <p className="text-sm text-slate-400">{l.insumo_codigo}</p>
            <h2 className="mt-1 text-2xl font-bold text-slate-800">
              {l.insumo_nombre}
            </h2>
            <p className="mt-1 text-sm text-slate-500">
              Lote del proveedor <strong>{l.codigo}</strong>
            </p>
          </div>

          {/* «Utilizable» resume la decisión: aprobado, vigente y no vencido.
              Va destacado porque es lo único que hay que mirar para saber si
              este lote puede salir a producción. */}
          <div
            className={`flex items-center gap-2 rounded-xl px-4 py-3 text-sm font-medium ${
              l.utilizable
                ? "bg-green-50 text-green-800"
                : "bg-red-50 text-red-800"
            }`}
          >
            {l.utilizable ? (
              <ShieldCheck className="h-5 w-5" />
            ) : (
              <ShieldX className="h-5 w-5" />
            )}
            {l.utilizable ? "Se puede consumir" : "No se puede consumir"}
          </div>

        </div>

        <div className="mt-6 grid gap-5 sm:grid-cols-2 lg:grid-cols-4">

          <Dato etiqueta="Calidad">
            <Estado valor={l.estado_calidad} />
          </Dato>

          <Dato etiqueta="Proveedor">{l.proveedor_nombre ?? "—"}</Dato>

          <Dato etiqueta="Elaboración">{l.elaboracion ?? "—"}</Dato>

          <Dato etiqueta="Vencimiento">
            {l.vencimiento ? (
              <span className={l.vencido ? "text-red-700" : undefined}>
                {l.vencimiento}
                {l.vencido && (
                  <span className="ml-2 inline-flex items-center gap-1 text-xs">
                    <CalendarX2 className="h-3.5 w-3.5" />
                    vencido
                  </span>
                )}
              </span>
            ) : (
              "—"
            )}
          </Dato>

          <Dato etiqueta="Recibido">{l.recibido_en?.slice(0, 10)}</Dato>

          <Dato etiqueta="Físico">
            {numero(fisico)} {l.insumo_unidad}
          </Dato>

          <Dato etiqueta="Disponible">
            <span className="text-green-700">
              {numero(disponible)} {l.insumo_unidad}
            </span>
          </Dato>

          <Dato etiqueta="Reservado">
            {numero(fisico - disponible)} {l.insumo_unidad}
          </Dato>

        </div>

      </Tarjeta>

      <Tarjeta
        titulo="Dónde está"
        descripcion="Un mismo lote puede estar repartido entre ubicaciones: parte disponible y parte todavía en cuarentena."
        sinRelleno
      >
        {existencias.error ? (
          <div className="p-5">
            <Aviso>{existencias.error}</Aviso>
          </div>
        ) : (existencias.datos ?? []).length === 0 ? (
          <Vacio>Este lote ya no tiene existencias: se consumió entero.</Vacio>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead className="bg-slate-50">
                <tr>
                  <th className={claseEncabezado}>Ubicación</th>
                  <th className={claseEncabezado}>Físico</th>
                  <th className={claseEncabezado}>Reservado</th>
                  <th className={claseEncabezado}>Disponible</th>
                </tr>
              </thead>
              <tbody>
                {(existencias.datos ?? []).map((e) => (
                  <tr key={e.id} className="border-t border-slate-100">
                    <td className={`${claseCelda} font-medium text-slate-800`}>
                      {e.ubicacion_codigo}
                    </td>
                    <td className={`${claseCelda} text-slate-600`}>
                      {numero(e.cantidad_fisica)}
                    </td>
                    <td className={`${claseCelda} text-slate-600`}>
                      {numero(e.cantidad_reservada)}
                    </td>
                    <td className={`${claseCelda} font-semibold text-green-700`}>
                      {numero(e.cantidad_disponible)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Tarjeta>

      <Tarjeta
        titulo="Qué le pasó"
        descripcion="Cada movimiento trae el saldo antes y después, así que la cifra de arriba se puede reconstruir línea por línea."
        sinRelleno
      >
        {movimientos.error ? (
          <div className="p-5">
            <Aviso>{movimientos.error}</Aviso>
          </div>
        ) : (movimientos.datos ?? []).length === 0 ? (
          <Vacio>Sin movimientos.</Vacio>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead className="bg-slate-50">
                <tr>
                  <th className={claseEncabezado}>Tipo</th>
                  <th className={claseEncabezado}>Cantidad</th>
                  <th className={claseEncabezado}>Saldo</th>
                  <th className={claseEncabezado}>Documento</th>
                  <th className={claseEncabezado}>Motivo</th>
                </tr>
              </thead>
              <tbody>
                {(movimientos.datos ?? []).map((m) => (
                  <tr key={m.id} className="border-t border-slate-100">
                    <td className={claseCelda}>
                      <Estado valor={m.tipo} />
                    </td>
                    <td className={`${claseCelda} text-slate-600`}>
                      {numero(m.cantidad)}
                    </td>
                    <td className={`${claseCelda} text-slate-500`}>
                      {numero(m.saldo_anterior)} → {numero(m.saldo_posterior)}
                    </td>
                    <td className={`${claseCelda} text-slate-500`}>
                      {m.documento_tipo}
                      {m.documento_id ? ` #${m.documento_id}` : ""}
                    </td>
                    <td className={`${claseCelda} text-slate-500`}>
                      {m.motivo || "—"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Tarjeta>

    </div>
  );
}


export default DetalleLoteInventario;
