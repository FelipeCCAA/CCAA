import { useState } from "react";
import { Star, Truck } from "lucide-react";

import {
  crearProveedor,
  guardarCondiciones,
  obtenerInsumoProveedores,
  obtenerInsumos,
  obtenerProveedores,
} from "../../services/inventario.service";

import { obtenerSesion } from "../../services/sesion";

import { Aviso, Tarjeta, Vacio } from "../../components/seccion/componentes";
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
  Proveedores y sus condiciones por material.

  Estaban solo en el admin de Django, y no correspondía: no son datos de
  referencia que alguien consulta de vez en cuando, **son entradas de un
  cálculo que el sistema presenta como autoritativo**. El MRP sube la cantidad
  sugerida al mínimo de compra, la redondea al múltiplo y resta el plazo de
  entrega para decir cuándo hay que emitir la orden.

  Unas condiciones desactualizadas no se ven distintas de unas al día:
  producen cifras que parecen correctas. Y quien renegocia un precio o un
  plazo es Compras — que hasta ahora tenía que pedirle a un administrador que
  entrara al admin.

  Además es un prerrequisito duro: sin proveedor principal, una solicitud
  aprobada no se puede convertir en orden. El circuito se detenía en un paso
  que el operador no podía resolver desde ninguna pantalla.
*/

const VACIO_PROVEEDOR = { rut: "", nombre: "", email: "", telefono: "" };

const VACIO_CONDICION = {
  insumo: "",
  proveedor: "",
  principal: true,
  costo_unitario: "",
  compra_minima: "",
  multiplo_compra: "1",
  lead_time_dias: "",
};


function Proveedores() {

  const proveedores = useCarga(obtenerProveedores);
  const condiciones = useCarga(obtenerInsumoProveedores);
  const insumos = useCarga(obtenerInsumos);

  const [error, setError] = useState("");
  const [nuevo, setNuevo] = useState(VACIO_PROVEEDOR);
  const [condicion, setCondicion] = useState(VACIO_CONDICION);

  const sesion = obtenerSesion();
  const area = sesion?.usuario.perfil?.area;
  const puedeEditar = area === "compras" || sesion?.usuario.rol === "admin";

  const guardarProveedor = async (evento: React.FormEvent) => {
    evento.preventDefault();
    setError("");

    try {
      await crearProveedor(nuevo);
      setNuevo(VACIO_PROVEEDOR);
      await proveedores.recargar();
    } catch (e) {
      setError(mensajeDe(e, "No se pudo crear: revisa que el RUT no esté repetido."));
    }
  };

  const guardar = async (evento: React.FormEvent) => {
    evento.preventDefault();
    setError("");

    try {
      await guardarCondiciones(null, {
        ...condicion,
        insumo: Number(condicion.insumo),
        proveedor: Number(condicion.proveedor),
        costo_unitario: condicion.costo_unitario || 0,
        compra_minima: condicion.compra_minima || 0,
        multiplo_compra: condicion.multiplo_compra || 1,
        lead_time_dias: Number(condicion.lead_time_dias) || 0,
      });
      setCondicion({ ...VACIO_CONDICION, proveedor: condicion.proveedor });
      await condiciones.recargar();
    } catch (e) {
      setError(mensajeDe(e, "No se pudieron guardar las condiciones."));
    }
  };

  const marcarPrincipal = async (id: number, principal: boolean) => {
    setError("");

    try {
      await guardarCondiciones(id, { principal });
      await condiciones.recargar();
    } catch (e) {
      setError(mensajeDe(e, "No se pudo cambiar el proveedor principal."));
    }
  };

  const lista = condiciones.datos ?? [];

  /* Los materiales sin proveedor principal son los que van a detener una
     conversión a orden. Se muestran arriba para que se resuelvan antes de que
     la solicitud se trabe. */
  const sinPrincipal = (insumos.datos ?? []).filter(
    (i) => !lista.some((c) => c.insumo === i.id && c.principal),
  );

  return (
    <div className="space-y-8">

      {error && <Aviso>{error}</Aviso>}

      {sinPrincipal.length > 0 && (
        <div className="rounded-2xl border border-amber-200 bg-amber-50 px-5 py-4 text-sm text-amber-800">
          <p className="font-medium">
            {sinPrincipal.length} material(es) sin proveedor principal
          </p>
          <p className="mt-1">
            {sinPrincipal.map((i) => i.nombre).join(", ")}. Una solicitud de
            compra que los incluya no se podrá convertir en orden.
          </p>
        </div>
      )}

      {puedeEditar && (
        <div className="grid items-start gap-8 xl:grid-cols-2">

          <Tarjeta titulo="Nuevo proveedor">
            <form onSubmit={guardarProveedor} className="grid gap-3 sm:grid-cols-2">

              <input
                required
                placeholder="RUT"
                value={nuevo.rut}
                onChange={(e) => setNuevo({ ...nuevo, rut: e.target.value })}
                className={claseCampo}
              />

              <input
                required
                placeholder="Nombre"
                value={nuevo.nombre}
                onChange={(e) => setNuevo({ ...nuevo, nombre: e.target.value })}
                className={claseCampo}
              />

              <input
                type="email"
                placeholder="Correo"
                value={nuevo.email}
                onChange={(e) => setNuevo({ ...nuevo, email: e.target.value })}
                className={claseCampo}
              />

              <input
                placeholder="Teléfono"
                value={nuevo.telefono}
                onChange={(e) => setNuevo({ ...nuevo, telefono: e.target.value })}
                className={claseCampo}
              />

              <button className={`${claseBoton} sm:col-span-2`}>
                Crear proveedor
              </button>

            </form>
          </Tarjeta>

          <Tarjeta
            titulo="Condiciones de un material"
            descripcion="El mínimo, el múltiplo y el plazo son lo que el MRP usa para decir cuánto pedir y cuándo."
          >
            <form onSubmit={guardar} className="grid gap-3">

              <select
                required
                value={condicion.insumo}
                onChange={(e) =>
                  setCondicion({ ...condicion, insumo: e.target.value })
                }
                className={claseCampo}
              >
                <option value="">Material…</option>
                {(insumos.datos ?? []).map((i) => (
                  <option key={i.id} value={i.id}>
                    {i.codigo} · {i.nombre}
                  </option>
                ))}
              </select>

              <select
                required
                value={condicion.proveedor}
                onChange={(e) =>
                  setCondicion({ ...condicion, proveedor: e.target.value })
                }
                className={claseCampo}
              >
                <option value="">Proveedor…</option>
                {(proveedores.datos ?? [])
                  .filter((p) => p.activo)
                  .map((p) => (
                    <option key={p.id} value={p.id}>
                      {p.nombre}
                    </option>
                  ))}
              </select>

              <div className="grid gap-3 sm:grid-cols-2">
                <input
                  type="number"
                  step="0.01"
                  min="0"
                  placeholder="Costo unitario"
                  value={condicion.costo_unitario}
                  onChange={(e) =>
                    setCondicion({ ...condicion, costo_unitario: e.target.value })
                  }
                  className={claseCampo}
                />

                <input
                  type="number"
                  min="0"
                  placeholder="Plazo de entrega (días)"
                  value={condicion.lead_time_dias}
                  onChange={(e) =>
                    setCondicion({ ...condicion, lead_time_dias: e.target.value })
                  }
                  className={claseCampo}
                />

                <input
                  type="number"
                  step="0.001"
                  min="0"
                  placeholder="Compra mínima"
                  value={condicion.compra_minima}
                  onChange={(e) =>
                    setCondicion({ ...condicion, compra_minima: e.target.value })
                  }
                  className={claseCampo}
                />

                <input
                  type="number"
                  step="0.001"
                  min="0.001"
                  placeholder="Múltiplo de compra"
                  value={condicion.multiplo_compra}
                  onChange={(e) =>
                    setCondicion({ ...condicion, multiplo_compra: e.target.value })
                  }
                  className={claseCampo}
                />
              </div>

              <label className="flex items-center gap-2 text-sm text-slate-700">
                <input
                  type="checkbox"
                  checked={condicion.principal}
                  onChange={(e) =>
                    setCondicion({ ...condicion, principal: e.target.checked })
                  }
                />
                Proveedor principal de este material
              </label>

              <button className={claseBoton}>Guardar condiciones</button>

            </form>
          </Tarjeta>

        </div>
      )}

      <Tarjeta
        titulo="Condiciones por material"
        descripcion="Solo puede haber un principal por material: es con cuyas condiciones calcula el MRP y a quien se le emite la orden."
        sinRelleno
      >
        {condiciones.error ? (
          <div className="p-5">
            <Aviso>{condiciones.error}</Aviso>
          </div>
        ) : condiciones.cargando ? (
          <Vacio>Cargando…</Vacio>
        ) : lista.length === 0 ? (
          <Vacio>
            Todavía no hay condiciones cargadas. Sin ellas el MRP sugiere la
            cantidad neta sin redondear y usa el plazo del material.
          </Vacio>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full">

              <thead className="bg-slate-50">
                <tr>
                  <th className={claseEncabezado}>Material</th>
                  <th className={claseEncabezado}>Proveedor</th>
                  <th className={claseEncabezado}>Costo</th>
                  <th className={claseEncabezado}>Mínimo</th>
                  <th className={claseEncabezado}>Múltiplo</th>
                  <th className={claseEncabezado}>Plazo</th>
                  <th className={claseEncabezado}>Principal</th>
                </tr>
              </thead>

              <tbody>
                {lista.map((c) => (
                  <tr key={c.id} className="border-t border-slate-100">

                    <td className={`${claseCelda} font-medium text-slate-800`}>
                      {c.insumo_nombre}
                    </td>

                    <td className={`${claseCelda} text-slate-600`}>
                      <span className="inline-flex items-center gap-2">
                        <Truck className="h-4 w-4 text-slate-400" />
                        {c.proveedor_nombre}
                      </span>
                    </td>

                    <td className={`${claseCelda} text-slate-600`}>
                      {numero(c.costo_unitario)}
                    </td>

                    <td className={`${claseCelda} text-slate-600`}>
                      {numero(c.compra_minima)} {c.insumo_unidad}
                    </td>

                    <td className={`${claseCelda} text-slate-600`}>
                      {numero(c.multiplo_compra)} {c.insumo_unidad}
                    </td>

                    <td className={`${claseCelda} text-slate-600`}>
                      {c.lead_time_dias} d
                    </td>

                    <td className={claseCelda}>
                      {c.principal ? (
                        <span className="inline-flex items-center gap-1 rounded-full bg-green-50 px-2.5 py-0.5 text-xs font-medium text-green-700">
                          <Star className="h-3 w-3" />
                          principal
                        </span>
                      ) : puedeEditar ? (
                        <button
                          onClick={() => void marcarPrincipal(c.id, true)}
                          className="rounded-lg border border-slate-200 px-3 py-1 text-xs font-medium text-slate-600 hover:bg-slate-50"
                        >
                          Hacer principal
                        </button>
                      ) : (
                        <span className="text-xs text-slate-400">—</span>
                      )}
                    </td>

                  </tr>
                ))}
              </tbody>

            </table>
          </div>
        )}
      </Tarjeta>

      <Tarjeta titulo="Proveedores" sinRelleno>
        {(proveedores.datos ?? []).length === 0 ? (
          <Vacio>Sin proveedores.</Vacio>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead className="bg-slate-50">
                <tr>
                  <th className={claseEncabezado}>Proveedor</th>
                  <th className={claseEncabezado}>RUT</th>
                  <th className={claseEncabezado}>Contacto</th>
                  <th className={claseEncabezado}>Materiales</th>
                </tr>
              </thead>
              <tbody>
                {(proveedores.datos ?? []).map((p) => (
                  <tr key={p.id} className="border-t border-slate-100">
                    <td className={`${claseCelda} font-medium text-slate-800`}>
                      {p.nombre}
                    </td>
                    <td className={`${claseCelda} text-slate-600`}>{p.rut}</td>
                    <td className={`${claseCelda} text-slate-500`}>
                      {p.email || p.telefono || "—"}
                    </td>
                    <td className={`${claseCelda} text-slate-500`}>
                      {lista.filter((c) => c.proveedor === p.id).length}
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


export default Proveedores;
