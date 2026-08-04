import { useState } from "react";

import {
  agregarDetalleMRQ,
  crearMRQ,
  entregarMRQ,
  enviarMRQ,
  obtenerInsumos,
  obtenerMRQ,
  reservarMRQ,
} from "../../services/inventario.service";

import { obtenerSesion } from "../../services/sesion";

import { Aviso, Estado, Tarjeta, Vacio } from "./componentes";
import {
  claseBoton,
  claseCampo,
  claseCelda,
  claseEncabezado,
  numero,
  useCarga,
} from "./utilidades";


/*
  Pedidos internos de material (MRQ).

  Es el camino por el que planta le pide a bodega. Tiene tres momentos y cada
  uno cambia el stock de forma distinta:

    enviada → reservada (FEFO) → entregada

  La **reserva** no descuenta: aparta. Por eso `Existencia` lleva
  `cantidad_reservada` aparte de la física, y «disponible» resta las dos
  cosas. Entregar es lo que mueve el material y deja el movimiento.

  Quien pide y quien entrega no son la misma persona: el formulario de pedido
  solo aparece si no eres de Bodega, y las acciones de reservar y entregar
  solo si lo eres.
*/

const CERRADAS = ["entregada", "rechazada", "cancelada"];


function Pedidos() {

  const mrq = useCarga(obtenerMRQ);
  const insumos = useCarga(obtenerInsumos);

  const [error, setError] = useState("");
  const [nueva, setNueva] = useState({ insumo: "", cantidad: "", fecha: "" });

  const sesion = obtenerSesion();
  const area = sesion?.usuario.perfil?.area ?? "administracion";
  const puedeBodega = area === "bodega" || sesion?.usuario.rol === "admin";

  const solicitar = async (evento: React.FormEvent) => {
    evento.preventDefault();
    setError("");

    try {
      // Cabecera, línea y envío van juntos: una solicitud sin líneas no le
      // sirve a nadie y quedaría ocupando la bandeja de bodega.
      const solicitud = await crearMRQ({
        numero: `MRQ-${Date.now()}`,
        area,
        fecha_requerida: nueva.fecha,
        prioridad: 3,
      });

      await agregarDetalleMRQ({
        solicitud: solicitud.id,
        insumo: Number(nueva.insumo),
        cantidad_solicitada: Number(nueva.cantidad),
      });

      await enviarMRQ(solicitud.id);

      setNueva({ insumo: "", cantidad: "", fecha: "" });
      await mrq.recargar();
    } catch {
      setError("No se pudo enviar la solicitud.");
    }
  };

  const accion = async (fn: () => Promise<unknown>) => {
    setError("");

    try {
      await fn();
      await mrq.recargar();
    } catch {
      setError("No se pudo completar la operación: revisa el stock disponible.");
    }
  };

  const lista = mrq.datos ?? [];
  const abiertas = lista.filter((m) => !CERRADAS.includes(m.estado));
  const cerradas = lista.filter((m) => CERRADAS.includes(m.estado));

  return (
    <div className="space-y-8">

      {error && <Aviso>{error}</Aviso>}

      {!puedeBodega && (
        <Tarjeta
          titulo="Pedir material a bodega"
          descripcion="Se envía de inmediato a la bandeja de bodega, que lo reserva por FEFO."
        >
          <form onSubmit={solicitar} className="grid gap-3 md:grid-cols-4">

            <select
              required
              value={nueva.insumo}
              onChange={(e) => setNueva({ ...nueva, insumo: e.target.value })}
              className={`${claseCampo} md:col-span-2`}
            >
              <option value="">Material…</option>
              {(insumos.datos ?? []).map((i) => (
                <option key={i.id} value={i.id}>
                  {i.codigo} · {i.nombre}
                </option>
              ))}
            </select>

            <input
              required
              type="number"
              min="0.001"
              step="0.001"
              placeholder="Cantidad"
              value={nueva.cantidad}
              onChange={(e) => setNueva({ ...nueva, cantidad: e.target.value })}
              className={claseCampo}
            />

            <input
              required
              type="date"
              title="Fecha requerida"
              value={nueva.fecha}
              onChange={(e) => setNueva({ ...nueva, fecha: e.target.value })}
              className={claseCampo}
            />

            <button className={`${claseBoton} md:col-span-4`}>Enviar pedido</button>

          </form>
        </Tarjeta>
      )}

      <Tarjeta
        titulo="Pedidos abiertos"
        descripcion="Reservar aparta el material sin sacarlo; entregar es lo que lo mueve."
        sinRelleno
      >
        {mrq.error ? (
          <div className="p-5">
            <Aviso>{mrq.error}</Aviso>
          </div>
        ) : mrq.cargando ? (
          <Vacio>Cargando…</Vacio>
        ) : abiertas.length === 0 ? (
          <Vacio>Sin pedidos abiertos.</Vacio>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full">

              <thead className="bg-slate-50">
                <tr>
                  <th className={claseEncabezado}>Pedido</th>
                  <th className={claseEncabezado}>Área</th>
                  <th className={claseEncabezado}>Requerido</th>
                  <th className={claseEncabezado}>Materiales</th>
                  <th className={claseEncabezado}>Estado</th>
                  <th className={claseEncabezado}></th>
                </tr>
              </thead>

              <tbody>
                {abiertas.map((m) => (
                  <tr key={m.id} className="border-t border-slate-100">

                    <td className={`${claseCelda} font-medium text-slate-800`}>
                      {m.numero}
                    </td>

                    <td className={`${claseCelda} text-slate-600`}>{m.area}</td>

                    <td className={`${claseCelda} text-slate-600`}>
                      {m.fecha_requerida}
                    </td>

                    <td className={`${claseCelda} text-slate-500`}>
                      {m.detalles.map((d) => (
                        <div key={d.id}>
                          {d.insumo_nombre} · {numero(d.cantidad_solicitada)}
                        </div>
                      ))}
                    </td>

                    <td className={claseCelda}>
                      <Estado valor={m.estado} />
                    </td>

                    <td className={`${claseCelda} text-right`}>
                      {puedeBodega && ["enviada", "aprobada"].includes(m.estado) && (
                        <button
                          onClick={() => void accion(() => reservarMRQ(m.id))}
                          className="rounded-lg bg-green-700 px-3 py-1.5 text-xs font-semibold text-white"
                        >
                          Reservar FEFO
                        </button>
                      )}

                      {puedeBodega && ["preparada", "parcial"].includes(m.estado) && (
                        <button
                          onClick={() => void accion(() => entregarMRQ(m.id))}
                          className="rounded-lg bg-blue-700 px-3 py-1.5 text-xs font-semibold text-white"
                        >
                          Entregar
                        </button>
                      )}
                    </td>

                  </tr>
                ))}
              </tbody>

            </table>
          </div>
        )}
      </Tarjeta>

      <Tarjeta titulo="Pedidos cerrados" sinRelleno>
        {cerradas.length === 0 ? (
          <Vacio>Todavía no hay pedidos cerrados.</Vacio>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead className="bg-slate-50">
                <tr>
                  <th className={claseEncabezado}>Pedido</th>
                  <th className={claseEncabezado}>Área</th>
                  <th className={claseEncabezado}>Estado</th>
                </tr>
              </thead>
              <tbody>
                {cerradas.slice(0, 15).map((m) => (
                  <tr key={m.id} className="border-t border-slate-100">
                    <td className={`${claseCelda} font-medium text-slate-800`}>
                      {m.numero}
                    </td>
                    <td className={`${claseCelda} text-slate-600`}>{m.area}</td>
                    <td className={claseCelda}>
                      <Estado valor={m.estado} />
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


export default Pedidos;
