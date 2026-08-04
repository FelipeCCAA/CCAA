import { useState } from "react";

import {
  crearMaterial,
  obtenerCatalogosInventario,
  obtenerInsumos,
} from "../../services/inventario.service";

import { obtenerSesion } from "../../services/sesion";

import { Aviso, Tarjeta, Vacio } from "./componentes";
import {
  claseBoton,
  claseCampo,
  claseCelda,
  claseEncabezado,
  numero,
  useCarga,
} from "./utilidades";


/*
  Catálogo de materiales.

  Es el maestro del módulo: qué se compra, en qué unidad, si pasa por Calidad
  y con qué parámetros de reposición. Antes vivía repartido entre dos
  pantallas —el listado en `/inventario`, que era solo para administradores, y
  el formulario de alta en `/abastecimiento`— sin enlace entre las dos.

  Los tres saldos que se muestran (`físico`, `disponible`, `bloqueado`) los
  calcula el backend desde el libro de existencias. No hay un stock guardado
  en el material: un número al lado, editable y sin movimiento que lo
  respalde, se desincroniza y además parece autorizado.
*/

const VACIO = {
  codigo: "",
  nombre: "",
  categoria: "materia_prima",
  unidad: "kg",
  requiere_calidad: true,
  requiere_lote: true,
  requiere_vencimiento: true,
};


function Materiales() {

  const insumos = useCarga(obtenerInsumos);
  const catalogos = useCarga(obtenerCatalogosInventario);

  const [nuevo, setNuevo] = useState(VACIO);
  const [error, setError] = useState("");
  const [abierto, setAbierto] = useState(false);

  const sesion = obtenerSesion();
  const area = sesion?.usuario.perfil?.area;
  const puedeBodega = area === "bodega" || sesion?.usuario.rol === "admin";

  const guardar = async (evento: React.FormEvent) => {
    evento.preventDefault();
    setError("");

    try {
      await crearMaterial({ ...nuevo, area: "bodega" });
      setNuevo(VACIO);
      setAbierto(false);
      await insumos.recargar();
    } catch {
      setError("No se pudo crear el material: revisa que el código no esté repetido.");
    }
  };

  const lista = insumos.datos ?? [];

  return (
    <div className="space-y-8">

      {error && <Aviso>{error}</Aviso>}

      {puedeBodega && (
        <Tarjeta
          titulo="Nuevo material"
          descripcion="El código es el identificador operativo: lo usan las recetas, los movimientos y las órdenes de compra."
          acciones={
            <button
              type="button"
              onClick={() => setAbierto((v) => !v)}
              className="rounded-xl border border-slate-200 px-4 py-2 text-sm font-medium text-slate-600 hover:bg-slate-50"
            >
              {abierto ? "Cancelar" : "Agregar"}
            </button>
          }
        >
          {abierto ? (
            <form onSubmit={guardar} className="grid gap-3 sm:grid-cols-2">

              <input
                required
                placeholder="Código"
                value={nuevo.codigo}
                onChange={(e) => setNuevo({ ...nuevo, codigo: e.target.value })}
                className={claseCampo}
              />

              <input
                required
                placeholder="Nombre"
                value={nuevo.nombre}
                onChange={(e) => setNuevo({ ...nuevo, nombre: e.target.value })}
                className={claseCampo}
              />

              <select
                value={nuevo.categoria}
                onChange={(e) => setNuevo({ ...nuevo, categoria: e.target.value })}
                className={claseCampo}
              >
                {(catalogos.datos?.categoria_insumo ?? []).map((o) => (
                  <option key={o.valor} value={o.valor}>
                    {o.etiqueta}
                  </option>
                ))}
              </select>

              <select
                value={nuevo.unidad}
                onChange={(e) => setNuevo({ ...nuevo, unidad: e.target.value })}
                className={claseCampo}
              >
                {(catalogos.datos?.unidad_insumo ?? []).map((o) => (
                  <option key={o.valor} value={o.valor}>
                    {o.etiqueta}
                  </option>
                ))}
              </select>

              <label className="flex items-center gap-2 text-sm text-slate-700">
                <input
                  type="checkbox"
                  checked={nuevo.requiere_calidad}
                  onChange={(e) =>
                    setNuevo({ ...nuevo, requiere_calidad: e.target.checked })
                  }
                />
                Requiere liberación de Calidad
              </label>

              <label className="flex items-center gap-2 text-sm text-slate-700">
                <input
                  type="checkbox"
                  checked={nuevo.requiere_vencimiento}
                  onChange={(e) =>
                    setNuevo({ ...nuevo, requiere_vencimiento: e.target.checked })
                  }
                />
                Requiere fecha de vencimiento
              </label>

              <button className={`${claseBoton} sm:col-span-2`}>
                Guardar material
              </button>

            </form>
          ) : (
            <p className="text-sm text-slate-400">
              Un material marcado «requiere Calidad» ingresa a cuarentena y no
              se puede consumir hasta que Calidad lo libere.
            </p>
          )}
        </Tarjeta>
      )}

      <Tarjeta
        titulo="Catálogo"
        descripcion="Saldos calculados desde el libro de existencias. El EOQ necesita demanda anual, costo de pedido y costo de mantener."
        sinRelleno
      >
        {insumos.error ? (
          <div className="p-5">
            <Aviso>{insumos.error}</Aviso>
          </div>
        ) : insumos.cargando ? (
          <Vacio>Cargando…</Vacio>
        ) : lista.length === 0 ? (
          <Vacio>Todavía no hay materiales cargados.</Vacio>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full">

              <thead className="bg-slate-50">
                <tr>
                  <th className={claseEncabezado}>Material</th>
                  <th className={claseEncabezado}>Área</th>
                  <th className={claseEncabezado}>Disponible</th>
                  <th className={claseEncabezado}>Bloqueado</th>
                  <th className={claseEncabezado}>Punto reposición</th>
                  <th className={claseEncabezado}>EOQ</th>
                </tr>
              </thead>

              <tbody>
                {lista.map((i) => {
                  // Por debajo del punto de reposición hay que pedir. Se marca
                  // aquí y no solo en las alertas para que se vea al recorrer
                  // el catálogo, que es cuando se decide qué comprar.
                  const bajo =
                    Number(i.stock_disponible) <= Number(i.punto_reposicion) &&
                    Number(i.punto_reposicion) > 0;

                  return (
                    <tr key={i.id} className="border-t border-slate-100">

                      <td className={`${claseCelda} font-medium text-slate-800`}>
                        {i.nombre}
                        <div className="text-xs font-normal text-slate-400">
                          {i.codigo}
                        </div>
                      </td>

                      <td className={`${claseCelda} text-slate-600`}>
                        {i.area_etiqueta}
                      </td>

                      <td className={claseCelda}>
                        <span
                          className={
                            bajo ? "font-semibold text-amber-700" : "text-slate-700"
                          }
                        >
                          {numero(i.stock_disponible)} {i.unidad}
                        </span>
                      </td>

                      <td className={`${claseCelda} text-slate-500`}>
                        {numero(i.stock_bloqueado)} {i.unidad}
                      </td>

                      <td className={`${claseCelda} text-slate-500`}>
                        {numero(i.punto_reposicion)} {i.unidad}
                      </td>

                      <td className={`${claseCelda} text-slate-500`}>
                        {numero(i.eoq)} {i.eoq ? i.unidad : ""}
                      </td>

                    </tr>
                  );
                })}
              </tbody>

            </table>
          </div>
        )}
      </Tarjeta>

    </div>
  );
}


export default Materiales;
