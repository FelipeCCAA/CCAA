import { ShoppingCart } from "lucide-react";

import { obtenerOrdenesCompra } from "../../services/inventario.service";

import {
  Aviso,
  Estado,
  Tarjeta,
  Vacio,
} from "./componentes";

import {
  claseCelda,
  claseEncabezado,
  useCarga,
} from "./utilidades";


/*
  Compras.

  Lo que se ve hoy son las órdenes. El backend tiene además el circuito
  completo —solicitud de compra, aprobación con segregación de funciones
  (`decidir_solicitud_compra` rechaza que el solicitante apruebe lo suyo),
  orden, recepción contra la orden— y ninguna de esas pantallas existe: son
  cuatro grupos de endpoints sin interfaz.

  Se construyen en la fase de compras. Esta pestaña es el lugar donde van, y
  está aquí desde ahora para que el circuito tenga un sitio visible en vez de
  quedar repartido cuando se escriba.
*/

function Compras() {

  const ordenes = useCarga(obtenerOrdenesCompra);
  const lista = ordenes.datos ?? [];

  return (
    <div className="space-y-8">

      <Tarjeta
        titulo="Órdenes de compra"
        descripcion="Lo que está comprometido con proveedores y todavía no llega."
        sinRelleno
      >
        {ordenes.error ? (
          <div className="p-5">
            <Aviso>{ordenes.error}</Aviso>
          </div>
        ) : ordenes.cargando ? (
          <Vacio>Cargando…</Vacio>
        ) : lista.length === 0 ? (
          <Vacio>Sin órdenes de compra.</Vacio>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead className="bg-slate-50">
                <tr>
                  <th className={claseEncabezado}>Orden</th>
                  <th className={claseEncabezado}>Proveedor</th>
                  <th className={claseEncabezado}>Estado</th>
                  <th className={claseEncabezado}>Materiales</th>
                </tr>
              </thead>
              <tbody>
                {lista.map((o) => (
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
                    <td className={claseCelda}>
                      <Estado valor={o.estado} />
                    </td>
                    <td className={`${claseCelda} text-slate-500`}>
                      {o.detalles.length}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Tarjeta>

      <Tarjeta titulo="Lo que falta en esta pestaña">
        <ul className="space-y-2 text-sm text-slate-500">
          <li>
            · <span className="font-medium text-slate-700">Solicitudes de compra</span>{" "}
            con su aprobación. El backend ya impide que el solicitante apruebe
            su propia solicitud; falta la bandeja donde se aprueba.
          </li>
          <li>
            · <span className="font-medium text-slate-700">Recepción contra orden</span>,
            que es lo que crea el lote y lo manda a cuarentena.
          </li>
          <li>
            · <span className="font-medium text-slate-700">Proveedores</span> y sus
            condiciones por material: precio, mínimo de compra, plazo de entrega.
          </li>
        </ul>
      </Tarjeta>

    </div>
  );
}


export default Compras;
