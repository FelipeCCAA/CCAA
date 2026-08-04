import { useState } from "react";
import { Link } from "react-router-dom";

import {
  consumirRecetaProduccion,
  crearAjuste,
  decidirAjuste,
  ingresarMaterial,
  obtenerAjustes,
  obtenerExistencias,
  obtenerInsumos,
  obtenerMovimientos,
  obtenerUbicaciones,
  registrarSalida,
} from "../../services/inventario.service";

import { obtenerLotes } from "../../services/produccion.service";
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
  Stock: qué hay, dónde, y todo lo que lo mueve.

  El saldo no se edita. Cada variación entra por una operación —ingreso,
  salida, consumo, ajuste— y deja un `MovimientoInventario` con el saldo
  anterior y el posterior. Por eso los movimientos están en esta misma
  pestaña y no escondidos en un histórico: son la explicación de la cifra de
  arriba.

  Los ajustes son el único camino que **no** aplica de inmediato: quedan
  pendientes de una segunda firma. Quien cuenta el stock no es quien autoriza
  la diferencia.
*/

const OPERACIONES = [
  ["consumo", "Consumo de material"],
  ["salida", "Salida de bodega"],
  ["positivo", "Ajuste positivo"],
  ["negativo", "Ajuste negativo"],
  ["merma", "Merma"],
];

const ES_AJUSTE = ["positivo", "negativo", "merma"];


function Stock() {

  const existencias = useCarga(obtenerExistencias);
  const movimientos = useCarga(obtenerMovimientos);
  const ajustes = useCarga(obtenerAjustes);
  const insumos = useCarga(obtenerInsumos);
  const ubicaciones = useCarga(obtenerUbicaciones);
  const lotes = useCarga(() => obtenerLotes(100));

  const [error, setError] = useState("");
  const [operacion, setOperacion] = useState({
    existencia: "",
    tipo: "consumo",
    cantidad: "",
    motivo: "",
  });
  const [ingreso, setIngreso] = useState({
    insumo: "",
    codigo_lote: "",
    ubicacion: "",
    cantidad: "",
    elaboracion: "",
    vencimiento: "",
  });
  const [loteAConsumir, setLoteAConsumir] = useState("");

  const sesion = obtenerSesion();
  const area = sesion?.usuario.perfil?.area;
  const puedeBodega = area === "bodega" || sesion?.usuario.rol === "admin";

  const refrescar = async () => {
    await Promise.all([
      existencias.recargar(),
      movimientos.recargar(),
      ajustes.recargar(),
    ]);
  };

  const registrarOperacion = async (evento: React.FormEvent) => {
    evento.preventDefault();
    setError("");

    const base = {
      existencia: Number(operacion.existencia),
      cantidad: Number(operacion.cantidad),
      motivo: operacion.motivo,
    };

    try {
      if (ES_AJUSTE.includes(operacion.tipo)) {
        await crearAjuste({
          ...base,
          tipo: operacion.tipo as "positivo" | "negativo" | "merma",
        });
      } else {
        await registrarSalida({
          ...base,
          tipo: operacion.tipo as "salida" | "consumo",
        });
      }

      setOperacion({ existencia: "", tipo: "consumo", cantidad: "", motivo: "" });
      await refrescar();
    } catch {
      setError(
        "No se pudo registrar. Solo sale material aprobado por Calidad y no reservado, y la operación exige un motivo.",
      );
    }
  };

  const guardarIngreso = async (evento: React.FormEvent) => {
    evento.preventDefault();
    setError("");

    try {
      await ingresarMaterial({
        ...ingreso,
        insumo: Number(ingreso.insumo),
        ubicacion: Number(ingreso.ubicacion),
        cantidad: Number(ingreso.cantidad),
      });

      setIngreso({
        insumo: "",
        codigo_lote: "",
        ubicacion: "",
        cantidad: "",
        elaboracion: "",
        vencimiento: "",
      });
      await refrescar();
    } catch {
      setError(
        "No se pudo ingresar. Si el material requiere Calidad debe entrar a Cuarentena; si no, a Disponible.",
      );
    }
  };

  const consumir = async () => {
    setError("");

    try {
      await consumirRecetaProduccion(Number(loteAConsumir));
      setLoteAConsumir("");
      await refrescar();
    } catch {
      setError(
        "No se pudo consumir la receta: revisa kilos producidos, receta vigente, liberación de Calidad y stock.",
      );
    }
  };

  const pendientes = (ajustes.datos ?? []).filter((a) => a.estado === "pendiente");

  return (
    <div className="space-y-8">

      {error && <Aviso>{error}</Aviso>}

      <Tarjeta
        titulo="Existencias por lote y ubicación"
        descripcion="«Disponible» descuenta lo reservado y excluye lo que no está liberado."
        sinRelleno
      >
        {existencias.error ? (
          <div className="p-5">
            <Aviso>{existencias.error}</Aviso>
          </div>
        ) : existencias.cargando ? (
          <Vacio>Cargando…</Vacio>
        ) : (existencias.datos ?? []).length === 0 ? (
          <Vacio>No hay existencias registradas.</Vacio>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead className="bg-slate-50">
                <tr>
                  <th className={claseEncabezado}>Material</th>
                  <th className={claseEncabezado}>Lote</th>
                  <th className={claseEncabezado}>Ubicación</th>
                  <th className={claseEncabezado}>Calidad</th>
                  <th className={claseEncabezado}>Físico</th>
                  <th className={claseEncabezado}>Disponible</th>
                </tr>
              </thead>
              <tbody>
                {(existencias.datos ?? []).map((e) => (
                  <tr key={e.id} className="border-t border-slate-100">
                    <td className={`${claseCelda} font-medium text-slate-800`}>
                      {e.insumo_nombre}
                    </td>
                    <td className={claseCelda}>
                      {/* El lote es lo que se sigue: desde aquí se llega a su
                          ficha, con dónde está y todo lo que le pasó. */}
                      <Link
                        to={`lotes/${e.lote}`}
                        className="font-medium text-green-700 hover:underline"
                      >
                        {e.lote_codigo}
                      </Link>
                    </td>
                    <td className={`${claseCelda} text-slate-600`}>
                      {e.ubicacion_codigo}
                    </td>
                    <td className={claseCelda}>
                      <Estado valor={e.estado_calidad} />
                    </td>
                    <td className={`${claseCelda} text-slate-600`}>
                      {numero(e.cantidad_fisica)}
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

      {puedeBodega && (
        <div className="grid items-start gap-8 xl:grid-cols-2">

          <Tarjeta
            titulo="Ingresar material"
            descripcion="Crea el lote de proveedor y su entrada. Si el material requiere Calidad, entra a cuarentena."
          >
            <form onSubmit={guardarIngreso} className="grid gap-3 sm:grid-cols-2">

              <select
                required
                value={ingreso.insumo}
                onChange={(e) => setIngreso({ ...ingreso, insumo: e.target.value })}
                className={claseCampo}
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
                placeholder="Lote del proveedor"
                value={ingreso.codigo_lote}
                onChange={(e) =>
                  setIngreso({ ...ingreso, codigo_lote: e.target.value })
                }
                className={claseCampo}
              />

              <select
                required
                value={ingreso.ubicacion}
                onChange={(e) =>
                  setIngreso({ ...ingreso, ubicacion: e.target.value })
                }
                className={claseCampo}
              >
                <option value="">Ubicación…</option>
                {(ubicaciones.datos ?? [])
                  .filter((u) => u.activo)
                  .map((u) => (
                    <option key={u.id} value={u.id}>
                      {u.bodega_nombre}/{u.codigo} · {u.tipo}
                    </option>
                  ))}
              </select>

              <input
                required
                type="number"
                min="0.001"
                step="0.001"
                placeholder="Cantidad"
                value={ingreso.cantidad}
                onChange={(e) => setIngreso({ ...ingreso, cantidad: e.target.value })}
                className={claseCampo}
              />

              <input
                type="date"
                title="Elaboración"
                value={ingreso.elaboracion}
                onChange={(e) =>
                  setIngreso({ ...ingreso, elaboracion: e.target.value })
                }
                className={claseCampo}
              />

              <input
                type="date"
                title="Vencimiento"
                value={ingreso.vencimiento}
                onChange={(e) =>
                  setIngreso({ ...ingreso, vencimiento: e.target.value })
                }
                className={claseCampo}
              />

              <button className={`${claseBoton} sm:col-span-2`}>
                Registrar ingreso
              </button>

            </form>
          </Tarjeta>

          <Tarjeta
            titulo="Salida, consumo o ajuste"
            descripcion="Salidas y consumos aplican de inmediato. Los ajustes quedan esperando una segunda firma."
          >
            <form onSubmit={registrarOperacion} className="grid gap-3">

              <select
                required
                value={operacion.existencia}
                onChange={(e) =>
                  setOperacion({ ...operacion, existencia: e.target.value })
                }
                className={claseCampo}
              >
                <option value="">Existencia y lote…</option>
                {(existencias.datos ?? []).map((e) => (
                  <option key={e.id} value={e.id}>
                    {e.insumo_nombre} · {e.lote_codigo} · disp.{" "}
                    {numero(e.cantidad_disponible)}
                  </option>
                ))}
              </select>

              <div className="grid gap-3 sm:grid-cols-2">
                <select
                  value={operacion.tipo}
                  onChange={(e) =>
                    setOperacion({ ...operacion, tipo: e.target.value })
                  }
                  className={claseCampo}
                >
                  {OPERACIONES.map(([valor, etiqueta]) => (
                    <option key={valor} value={valor}>
                      {etiqueta}
                    </option>
                  ))}
                </select>

                <input
                  required
                  type="number"
                  min="0.001"
                  step="0.001"
                  placeholder="Cantidad"
                  value={operacion.cantidad}
                  onChange={(e) =>
                    setOperacion({ ...operacion, cantidad: e.target.value })
                  }
                  className={claseCampo}
                />
              </div>

              <textarea
                required
                placeholder="Motivo o documento de respaldo"
                value={operacion.motivo}
                onChange={(e) =>
                  setOperacion({ ...operacion, motivo: e.target.value })
                }
                className={claseCampo}
              />

              <button className={claseBoton}>Registrar operación</button>

            </form>
          </Tarjeta>

        </div>
      )}

      {puedeBodega && (
        <div className="grid items-start gap-8 xl:grid-cols-2">

          <Tarjeta
            titulo="Ajustes esperando firma"
            descripcion="Quien cuenta el stock no autoriza la diferencia."
          >
            {pendientes.length === 0 ? (
              <Vacio>Sin ajustes pendientes.</Vacio>
            ) : (
              <div className="space-y-3">
                {pendientes.map((a) => (
                  <div
                    key={a.id}
                    className="flex items-center justify-between gap-3 rounded-xl bg-slate-50 px-4 py-3"
                  >
                    <div className="min-w-0">
                      <p className="text-sm font-medium text-slate-800">
                        {a.tipo} · {numero(a.cantidad)}
                      </p>
                      <p className="mt-0.5 text-sm text-slate-500">{a.motivo}</p>
                    </div>

                    <div className="flex shrink-0 gap-2">
                      <button
                        onClick={() =>
                          void decidirAjuste(a.id, "aprobar").then(refrescar)
                        }
                        className="rounded-lg bg-green-700 px-3 py-2 text-xs font-semibold text-white"
                      >
                        Aprobar
                      </button>
                      <button
                        onClick={() =>
                          void decidirAjuste(a.id, "rechazar").then(refrescar)
                        }
                        className="rounded-lg bg-red-50 px-3 py-2 text-xs font-semibold text-red-700"
                      >
                        Rechazar
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </Tarjeta>

          <Tarjeta
            titulo="Consumo por lote de producción"
            descripcion="Descuenta por FEFO lo que la receta vigente del lote declara. Se dispara solo al declarar el lote producido; esto es para reintentarlo si falló."
          >
            <div className="grid gap-3">
              <select
                value={loteAConsumir}
                onChange={(e) => setLoteAConsumir(e.target.value)}
                className={claseCampo}
              >
                <option value="">Lote de producción…</option>
                {(lotes.datos ?? [])
                  .filter((l) => l.kg_producidos && l.estado !== "anulado")
                  .map((l) => (
                    <option key={l.id} value={l.id}>
                      {l.codigo_lote} · {l.producto_nombre} · {l.kg_producidos} kg
                    </option>
                  ))}
              </select>

              <button
                type="button"
                disabled={!loteAConsumir}
                onClick={() => void consumir()}
                className={claseBoton}
              >
                Registrar consumo
              </button>
            </div>
          </Tarjeta>

        </div>
      )}

      <Tarjeta
        titulo="Últimos movimientos"
        descripcion="La explicación de cada cifra de arriba. Un movimiento no se edita ni se borra."
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
                  <th className={claseEncabezado}>Material</th>
                  <th className={claseEncabezado}>Lote</th>
                  <th className={claseEncabezado}>Cantidad</th>
                  <th className={claseEncabezado}>Motivo</th>
                </tr>
              </thead>
              <tbody>
                {(movimientos.datos ?? []).slice(0, 20).map((m) => (
                  <tr key={m.id} className="border-t border-slate-100">
                    <td className={claseCelda}>
                      <Estado valor={m.tipo} />
                    </td>
                    <td className={`${claseCelda} font-medium text-slate-800`}>
                      {m.insumo_nombre}
                    </td>
                    <td className={`${claseCelda} text-slate-600`}>{m.lote_codigo}</td>
                    <td className={`${claseCelda} text-slate-600`}>
                      {numero(m.cantidad)}
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


export default Stock;
