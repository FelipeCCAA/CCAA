import { useState } from "react";
import { Ban } from "lucide-react";

import {
  crearConductor,
  crearPredio,
  crearProveedorLeche,
  obtenerConductores,
  obtenerPredios,
  obtenerProveedoresLeche,
} from "../../services/recoleccion.service";

import { Aviso, Tarjeta, Vacio } from "../../components/seccion/componentes";
import {
  claseBoton,
  claseCampo,
  claseCelda,
  claseEncabezado,
  mensajeDe,
  useCarga,
} from "../../components/seccion/utilidades";


/*
  Maestros de la recolección: proveedores, predios y conductores.

  Los tres son prerrequisito duro: sin conductor y sin predio no se puede
  registrar nada, y el desplegable vacío no explica por qué. Por eso viven aquí
  y no en el admin de Django — es el mismo criterio con que las bodegas
  salieron del admin.

  El **bloqueo** de un proveedor se edita en el admin a propósito: lo pondrá la
  cadena de antibióticos, y desbloquear a mano desde la pantalla de captura
  invitaría a saltarse el motivo por el que se bloqueó.

  Los módulos siguen en el admin porque cuelgan del vehículo, que es un maestro
  de `maestros`, y crear uno aquí implicaría duplicar esa pantalla.
*/

function Maestros() {

  const proveedores = useCarga(obtenerProveedoresLeche);
  const predios = useCarga(obtenerPredios);
  const conductores = useCarga(obtenerConductores);

  const [error, setError] = useState("");
  const [proveedor, setProveedor] = useState({ rut: "", nombre: "" });
  const [predio, setPredio] = useState({
    proveedor: "",
    codigo: "",
    nombre: "",
    comuna: "",
  });
  const [conductor, setConductor] = useState({
    rut: "",
    nombre: "",
    telefono: "",
  });

  const guardar = async (fn: () => Promise<unknown>, limpiar: () => void) => {
    setError("");

    try {
      await fn();
      limpiar();
      await Promise.all([
        proveedores.recargar(),
        predios.recargar(),
        conductores.recargar(),
      ]);
    } catch (e) {
      setError(mensajeDe(e, "No se pudo guardar: revisa que el RUT o el código no estén repetidos."));
    }
  };

  return (
    <div className="space-y-8">

      {error && <Aviso>{error}</Aviso>}

      <div className="grid items-start gap-8 xl:grid-cols-2">

        <Tarjeta
          titulo="Nuevo proveedor de leche"
          descripcion="Quien entrega la materia prima. No es el mismo maestro que los proveedores de compras: aquel vende materiales contra una orden."
        >
          <form
            onSubmit={(e) => {
              e.preventDefault();
              void guardar(
                () => crearProveedorLeche(proveedor),
                () => setProveedor({ rut: "", nombre: "" }),
              );
            }}
            className="grid gap-3 sm:grid-cols-2"
          >
            <input
              required
              placeholder="RUT"
              value={proveedor.rut}
              onChange={(e) => setProveedor({ ...proveedor, rut: e.target.value })}
              className={claseCampo}
            />
            <input
              required
              placeholder="Nombre"
              value={proveedor.nombre}
              onChange={(e) =>
                setProveedor({ ...proveedor, nombre: e.target.value })
              }
              className={claseCampo}
            />
            <button className={`${claseBoton} sm:col-span-2`}>
              Crear proveedor
            </button>
          </form>
        </Tarjeta>

        <Tarjeta
          titulo="Nuevo conductor"
          descripcion="Es un maestro y no un texto libre porque firma: el registro que se llena frente al estanque lo respalda una persona."
        >
          <form
            onSubmit={(e) => {
              e.preventDefault();
              void guardar(
                () => crearConductor(conductor),
                () => setConductor({ rut: "", nombre: "", telefono: "" }),
              );
            }}
            className="grid gap-3 sm:grid-cols-3"
          >
            <input
              required
              placeholder="RUT"
              value={conductor.rut}
              onChange={(e) => setConductor({ ...conductor, rut: e.target.value })}
              className={claseCampo}
            />
            <input
              required
              placeholder="Nombre"
              value={conductor.nombre}
              onChange={(e) =>
                setConductor({ ...conductor, nombre: e.target.value })
              }
              className={claseCampo}
            />
            <input
              placeholder="Teléfono"
              value={conductor.telefono}
              onChange={(e) =>
                setConductor({ ...conductor, telefono: e.target.value })
              }
              className={claseCampo}
            />
            <button className={`${claseBoton} sm:col-span-3`}>
              Crear conductor
            </button>
          </form>
        </Tarjeta>

      </div>

      <Tarjeta
        titulo="Nuevo predio"
        descripcion="El campo de donde se recolecta. Un proveedor puede tener varios, y es el eslabón que la trazabilidad necesita para llegar del lote al origen."
      >
        <form
          onSubmit={(e) => {
            e.preventDefault();
            void guardar(
              () =>
                crearPredio({
                  ...predio,
                  proveedor: Number(predio.proveedor),
                }),
              () =>
                setPredio({
                  proveedor: predio.proveedor,
                  codigo: "",
                  nombre: "",
                  comuna: "",
                }),
            );
          }}
          className="grid gap-3 md:grid-cols-4"
        >
          <select
            required
            value={predio.proveedor}
            onChange={(e) => setPredio({ ...predio, proveedor: e.target.value })}
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
          <input
            required
            placeholder="Código"
            value={predio.codigo}
            onChange={(e) => setPredio({ ...predio, codigo: e.target.value })}
            className={claseCampo}
          />
          <input
            required
            placeholder="Nombre"
            value={predio.nombre}
            onChange={(e) => setPredio({ ...predio, nombre: e.target.value })}
            className={claseCampo}
          />
          <input
            placeholder="Comuna"
            value={predio.comuna}
            onChange={(e) => setPredio({ ...predio, comuna: e.target.value })}
            className={claseCampo}
          />
          <button className={`${claseBoton} md:col-span-4`}>Crear predio</button>
        </form>
      </Tarjeta>

      <Tarjeta titulo="Predios" sinRelleno>
        {(predios.datos ?? []).length === 0 ? (
          <Vacio>Sin predios cargados.</Vacio>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead className="bg-slate-50">
                <tr>
                  <th className={claseEncabezado}>Predio</th>
                  <th className={claseEncabezado}>Proveedor</th>
                  <th className={claseEncabezado}>Comuna</th>
                  <th className={claseEncabezado}>Estado</th>
                </tr>
              </thead>
              <tbody>
                {(predios.datos ?? []).map((p) => (
                  <tr key={p.id} className="border-t border-slate-100">
                    <td className={`${claseCelda} font-medium text-slate-800`}>
                      {p.nombre}
                      <div className="text-xs font-normal text-slate-400">
                        {p.codigo}
                      </div>
                    </td>
                    <td className={`${claseCelda} text-slate-600`}>
                      {p.proveedor_nombre}
                    </td>
                    <td className={`${claseCelda} text-slate-500`}>
                      {p.comuna || "—"}
                    </td>
                    <td className={claseCelda}>
                      {p.proveedor_bloqueado ? (
                        <span className="inline-flex items-center gap-1 rounded-full bg-red-50 px-2.5 py-0.5 text-xs font-medium text-red-700">
                          <Ban className="h-3 w-3" />
                          proveedor bloqueado
                        </span>
                      ) : (
                        <span className="text-xs text-slate-400">
                          {p.activo ? "activo" : "inactivo"}
                        </span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Tarjeta>

      <Tarjeta titulo="Conductores" sinRelleno>
        {(conductores.datos ?? []).length === 0 ? (
          <Vacio>Sin conductores cargados.</Vacio>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead className="bg-slate-50">
                <tr>
                  <th className={claseEncabezado}>Conductor</th>
                  <th className={claseEncabezado}>RUT</th>
                  <th className={claseEncabezado}>Teléfono</th>
                </tr>
              </thead>
              <tbody>
                {(conductores.datos ?? []).map((c) => (
                  <tr key={c.id} className="border-t border-slate-100">
                    <td className={`${claseCelda} font-medium text-slate-800`}>
                      {c.nombre}
                    </td>
                    <td className={`${claseCelda} text-slate-600`}>{c.rut}</td>
                    <td className={`${claseCelda} text-slate-500`}>
                      {c.telefono || "—"}
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


export default Maestros;
