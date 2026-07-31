import { useEffect, useState } from "react";
import { Boxes, Calculator, PackageOpen } from "lucide-react";

import { calcularMRP, obtenerInsumos, type Insumo, type ResultadoMRP } from "../../services/inventario.service";
import { obtenerProductosMaestros, type ProductoMaestro } from "../../services/maestros.service";

const numero = (valor: string | null) => valor == null ? "—" : Number(valor).toLocaleString("es-CL", { maximumFractionDigits: 2 });

function Inventario() {
  const [insumos, setInsumos] = useState<Insumo[]>([]);
  const [error, setError] = useState("");
  const [productos, setProductos] = useState<ProductoMaestro[]>([]);
  const [producto, setProducto] = useState("");
  const [kilos, setKilos] = useState("");
  const [mrp, setMrp] = useState<ResultadoMRP | null>(null);

  useEffect(() => {
    Promise.all([obtenerInsumos(), obtenerProductosMaestros()])
      .then(([datosInsumos, datosProductos]) => { setInsumos(datosInsumos); setProductos(datosProductos.filter((p) => p.naturaleza === "terminado")); })
      .catch(() => setError("No se pudo cargar el inventario."));
  }, []);

  const simular = async (evento: React.FormEvent) => {
    evento.preventDefault();
    setError("");
    try { setMrp(await calcularMRP(Number(producto), Number(kilos))); }
    catch { setError("No se pudo calcular el MRP. Revisa que el producto tenga consumos configurados."); }
  };

  return (
    <div className="px-8 py-10">
      <div className="mx-auto max-w-7xl">
        <header className="mb-8">
          <p className="text-sm font-semibold uppercase tracking-wider text-green-700">Bodega</p>
          <h1 className="mt-2 text-3xl font-bold text-slate-800">Inventario, MRP y EOQ</h1>
          <p className="mt-2 text-slate-500">Existencias y recomendaciones de compra para la producción de cada área.</p>
        </header>

        <section className="mb-8 grid gap-5 md:grid-cols-3">
          {[
            { etiqueta: "Insumos activos", valor: insumos.length, Icono: Boxes },
            { etiqueta: "Bajo punto de reposición", valor: insumos.filter((i) => Number(i.stock_actual) <= Number(i.punto_reposicion)).length, Icono: PackageOpen },
            { etiqueta: "Con EOQ calculado", valor: insumos.filter((i) => i.eoq !== null).length, Icono: Calculator },
          ].map(({ etiqueta, valor, Icono }) => (
            <div key={etiqueta} className="rounded-2xl border border-slate-200 bg-white p-6">
              <Icono className="h-6 w-6 text-green-700" />
              <p className="mt-4 text-sm text-slate-500">{etiqueta}</p>
              <p className="mt-1 text-3xl font-bold text-slate-900">{valor}</p>
            </div>
          ))}
        </section>

        <section className="overflow-hidden rounded-2xl border border-slate-200 bg-white">
          <div className="border-b border-slate-200 px-6 py-5">
            <h2 className="font-semibold text-slate-800">Existencias por área</h2>
            <p className="mt-1 text-sm text-slate-400">EOQ usa demanda anual, costo de pedido y costo anual de mantener una unidad.</p>
          </div>
          {error ? <p className="p-6 text-red-700">{error}</p> : insumos.length === 0 ? (
            <p className="p-6 text-slate-400">Aún no hay insumos. Cárgalos desde Django Admin.</p>
          ) : (
            <div className="overflow-x-auto"><table className="w-full text-left text-sm">
              <thead className="bg-slate-50 text-slate-500"><tr><th className="px-6 py-3">Insumo</th><th className="px-6 py-3">Área</th><th className="px-6 py-3">Stock</th><th className="px-6 py-3">Punto reposición</th><th className="px-6 py-3">EOQ sugerido</th></tr></thead>
              <tbody>{insumos.map((i) => <tr key={i.id} className="border-t border-slate-100"><td className="px-6 py-4 font-medium text-slate-800">{i.codigo} · {i.nombre}</td><td className="px-6 py-4 text-slate-600">{i.area_etiqueta}</td><td className="px-6 py-4">{numero(i.stock_actual)} {i.unidad}</td><td className="px-6 py-4">{numero(i.punto_reposicion)} {i.unidad}</td><td className="px-6 py-4">{numero(i.eoq)} {i.unidad}</td></tr>)}</tbody>
            </table></div>
          )}
        </section>

        <section className="mt-8 rounded-2xl border border-slate-200 bg-white p-6">
          <h2 className="font-semibold text-slate-800">Simulador MRP</h2>
          <p className="mt-1 text-sm text-slate-400">Indica el producto y los kilos planificados para calcular materiales, faltantes y envases.</p>
          <form onSubmit={simular} className="mt-5 flex flex-col gap-3 md:flex-row">
            <select required value={producto} onChange={(e) => setProducto(e.target.value)} className="flex-1 rounded-xl border border-slate-300 bg-white px-4 py-3 text-sm">
              <option value="">Selecciona un producto</option>
              {productos.map((p) => <option key={p.id} value={p.id}>{p.nombre}</option>)}
            </select>
            <input required min="0.001" step="0.001" type="number" value={kilos} onChange={(e) => setKilos(e.target.value)} placeholder="Kilos a producir" className="rounded-xl border border-slate-300 px-4 py-3 text-sm" />
            <button className="rounded-xl bg-green-700 px-6 py-3 font-semibold text-white hover:bg-green-800">Calcular</button>
          </form>
          {mrp && <div className="mt-6 overflow-x-auto"><table className="w-full text-left text-sm">
            <thead className="bg-slate-50 text-slate-500"><tr><th className="px-4 py-3">Material</th><th className="px-4 py-3">Requerido</th><th className="px-4 py-3">Stock</th><th className="px-4 py-3">Faltante</th><th className="px-4 py-3">Envases a pedir</th></tr></thead>
            <tbody>{mrp.materiales.map((m) => <tr key={m.insumo} className="border-t border-slate-100"><td className="px-4 py-3 font-medium">{m.insumo}</td><td className="px-4 py-3">{numero(m.requerido)} {m.unidad}</td><td className="px-4 py-3">{numero(m.stock)} {m.unidad}</td><td className="px-4 py-3">{numero(m.faltante)} {m.unidad}</td><td className="px-4 py-3 font-semibold text-green-700">{m.envases_a_pedir}</td></tr>)}</tbody>
          </table>{mrp.materiales.length === 0 && <p className="py-5 text-sm text-amber-700">Este producto todavía no tiene consumos de materiales configurados.</p>}</div>}
        </section>
      </div>
    </div>
  );
}

export default Inventario;
