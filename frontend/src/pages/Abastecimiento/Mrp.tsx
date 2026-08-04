import { useState } from "react";
import { AlertTriangle } from "lucide-react";

import {
  calcularMRP,
  obtenerEjecucionesMRP,
  type ResultadoMRP,
} from "../../services/inventario.service";

import {
  obtenerProductosMaestros,
  type ProductoMaestro,
} from "../../services/maestros.service";

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
  MRP.

  Hay dos, y responden preguntas distintas:

  - El **simulador** de aquí abajo: «si produzco 20.000 kg de esto, qué
    necesito». Explota la receta vigente **hoy** y sirve para cotizar o para
    decidir si se puede correr un lote.

  - El **MRP semanal**, que explota el programa publicado de planificación
    bloque por bloque, a la fecha de cada bloque, y deja `EjecucionMRP` con
    sus `ResultadoMRP`: necesidad bruta, disponible proyectado, recepciones ya
    programadas y compra sugerida con su fecha límite de pedido. Es el que
    sirve para comprar.

  El semanal está escrito y probado en el backend desde hace tiempo y **no se
  podía ejecutar desde ninguna pantalla**. Aquí se listan sus ejecuciones; el
  botón de correrlo y la tabla de resultados son la fase siguiente.
*/

function Mrp() {

  const ejecuciones = useCarga(obtenerEjecucionesMRP);
  const productos = useCarga(obtenerProductosMaestros);

  const [producto, setProducto] = useState("");
  const [kilos, setKilos] = useState("");
  const [resultado, setResultado] = useState<ResultadoMRP | null>(null);
  const [error, setError] = useState("");

  const terminados = (productos.datos ?? []).filter(
    (p: ProductoMaestro) => p.naturaleza === "terminado",
  );

  const simular = async (evento: React.FormEvent) => {
    evento.preventDefault();
    setError("");

    try {
      setResultado(await calcularMRP(Number(producto), Number(kilos)));
    } catch {
      setError(
        "No se pudo calcular. Revisa que el producto tenga una receta vigente con insumos declarados.",
      );
    }
  };

  return (
    <div className="space-y-8">

      {error && <Aviso>{error}</Aviso>}

      <Tarjeta
        titulo="Simulador"
        descripcion="Qué material hace falta para una cantidad dada, con la receta vigente hoy. Multinivel: si el producto lleva un intermedio, el material de ese intermedio también cuenta."
      >
        <form onSubmit={simular} className="flex flex-col gap-3 md:flex-row">

          <select
            required
            value={producto}
            onChange={(e) => setProducto(e.target.value)}
            className={`${claseCampo} flex-1`}
          >
            <option value="">Producto…</option>
            {terminados.map((p) => (
              <option key={p.id} value={p.id}>
                {p.nombre}
              </option>
            ))}
          </select>

          <input
            required
            type="number"
            min="0.001"
            step="0.001"
            placeholder="Kilos a producir"
            value={kilos}
            onChange={(e) => setKilos(e.target.value)}
            className={claseCampo}
          />

          <button className={claseBoton}>Calcular</button>

        </form>

        {resultado && (
          <div className="mt-6">

            {/* Una lista incompleta se parece demasiado a una completa, y con
                ella se emite una orden de compra corta. */}
            {!resultado.receta_completa && (
              <p className="mb-4 flex items-start gap-2 rounded-xl bg-amber-50 px-4 py-3 text-sm text-amber-800">
                <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
                La receta no se pudo explotar hasta el final: hay un producto
                intermedio sin receta propia o un ciclo. Esta lista está
                incompleta.
              </p>
            )}

            {resultado.materiales.length === 0 ? (
              <Vacio>
                La receta vigente de este producto no declara insumos.
              </Vacio>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full">

                  <thead className="bg-slate-50">
                    <tr>
                      <th className={claseEncabezado}>Material</th>
                      <th className={claseEncabezado}>Requerido</th>
                      <th className={claseEncabezado}>En stock</th>
                      <th className={claseEncabezado}>Faltante</th>
                      <th className={claseEncabezado}>Envases a pedir</th>
                    </tr>
                  </thead>

                  <tbody>
                    {resultado.materiales.map((m) => (
                      <tr key={m.insumo} className="border-t border-slate-100">
                        <td className={`${claseCelda} font-medium text-slate-800`}>
                          {m.insumo}
                        </td>
                        <td className={`${claseCelda} text-slate-600`}>
                          {numero(m.requerido)} {m.unidad}
                        </td>
                        <td className={`${claseCelda} text-slate-600`}>
                          {numero(m.stock)} {m.unidad}
                        </td>
                        <td className={claseCelda}>
                          <span
                            className={
                              Number(m.faltante) > 0
                                ? "font-semibold text-amber-700"
                                : "text-slate-500"
                            }
                          >
                            {numero(m.faltante)} {m.unidad}
                          </span>
                        </td>
                        <td className={`${claseCelda} font-semibold text-green-700`}>
                          {m.envases_a_pedir}
                        </td>
                      </tr>
                    ))}
                  </tbody>

                </table>
              </div>
            )}

          </div>
        )}
      </Tarjeta>

      <Tarjeta
        titulo="Ejecuciones del MRP semanal"
        descripcion="Explota el programa publicado bloque por bloque, cada uno con la receta vigente a su fecha."
        sinRelleno
      >
        {ejecuciones.error ? (
          <div className="p-5">
            <Aviso>{ejecuciones.error}</Aviso>
          </div>
        ) : ejecuciones.cargando ? (
          <Vacio>Cargando…</Vacio>
        ) : (ejecuciones.datos ?? []).length === 0 ? (
          <Vacio>
            Todavía no se ha ejecutado el MRP semanal sobre ninguna semana
            publicada.
          </Vacio>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead className="bg-slate-50">
                <tr>
                  <th className={claseEncabezado}>Ejecutada</th>
                  <th className={claseEncabezado}>Corte</th>
                  <th className={claseEncabezado}>Horizonte</th>
                </tr>
              </thead>
              <tbody>
                {(ejecuciones.datos ?? []).map((e) => (
                  <tr key={e.id} className="border-t border-slate-100">
                    <td className={`${claseCelda} text-slate-600`}>
                      {e.creada_en?.slice(0, 10)}
                    </td>
                    <td className={`${claseCelda} text-slate-600`}>
                      {e.fecha_corte}
                    </td>
                    <td className={`${claseCelda} text-slate-600`}>
                      {e.horizonte_hasta}
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


export default Mrp;
