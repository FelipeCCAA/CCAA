import { useMemo, useState } from "react";
import axios from "axios";
import { Plus, Trash2, X } from "lucide-react";

import type { Insumo } from "../../services/inventario.service";
import {
  crearReceta,
  type OpcionCatalogo,
  type ProductoMaestro,
  type RecetaMaestro,
} from "../../services/maestros.service";

interface Fila {
  clave: string;
  tipo: "producto" | "insumo";
  referencia: string;
  fase: "proceso" | "envasado";
  cantidad: string;
  merma: string;
}

interface Props {
  productos: ProductoMaestro[];
  insumos: Insumo[];
  recetas: RecetaMaestro[];
  fases: OpcionCatalogo[];
  alCerrar: () => void;
  alGuardar: () => void;
}

const nuevaFila = (): Fila => ({
  clave: crypto.randomUUID(),
  tipo: "insumo",
  referencia: "",
  fase: "proceso",
  cantidad: "",
  merma: "0",
});

export default function FormularioReceta({
  productos, insumos, recetas, fases, alCerrar, alGuardar,
}: Props) {
  const [producto, setProducto] = useState("");
  const [cantidadBase, setCantidadBase] = useState("1");
  const [vigenteDesde, setVigenteDesde] = useState(new Date().toISOString().slice(0, 10));
  const [fuente, setFuente] = useState("");
  const [filas, setFilas] = useState<Fila[]>([nuevaFila()]);
  const [guardando, setGuardando] = useState(false);
  const [error, setError] = useState("");

  const version = useMemo(() => {
    const id = Number(producto);
    return Math.max(0, ...recetas.filter((r) => r.producto === id).map((r) => r.version)) + 1;
  }, [producto, recetas]);

  const cambiar = (clave: string, cambios: Partial<Fila>) =>
    setFilas((actuales) => actuales.map((fila) => fila.clave === clave ? { ...fila, ...cambios } : fila));

  async function enviar(evento: React.FormEvent) {
    evento.preventDefault();
    if (guardando) return;
    setGuardando(true);
    setError("");
    try {
      await crearReceta({
        producto: Number(producto),
        version,
        cantidad_base: Number(cantidadBase),
        vigente_desde: vigenteDesde,
        fuente: fuente.trim(),
        componentes: filas.map((fila) => {
          const catalogo = fila.tipo === "producto" ? productos : insumos;
          const elegido = catalogo.find((item) => item.id === Number(fila.referencia));
          return {
            [fila.tipo]: Number(fila.referencia),
            fase: fila.fase,
            cantidad: Number(fila.cantidad),
            unidad: "unidad_base" in (elegido ?? {})
              ? (elegido as ProductoMaestro).unidad_base
              : (elegido as Insumo | undefined)?.unidad,
            merma: Number(fila.merma || 0),
          };
        }),
      });
      alGuardar();
      alCerrar();
    } catch (e) {
      if (axios.isAxiosError(e) && e.response) {
        const cuerpo = e.response.data as Record<string, unknown>;
        setError(Object.entries(cuerpo).map(([k, v]) => `${k}: ${String(v)}`).join(" · "));
      } else setError("No se pudo conectar con el servidor.");
      setGuardando(false);
    }
  }

  const clase = "w-full rounded-xl border border-slate-300 bg-white px-3 py-2.5 text-sm outline-none focus:border-green-600";

  return (
    <div className="fixed inset-0 z-50 flex items-start justify-center overflow-y-auto bg-slate-900/40 p-4 sm:p-8">
      <div className="w-full max-w-5xl rounded-2xl bg-white shadow-xl">
        <header className="flex items-center justify-between border-b border-slate-200 px-6 py-5">
          <div><h2 className="text-lg font-semibold text-slate-900">Nueva versión de receta</h2><p className="text-xs text-slate-600">Se conserva la versión anterior para trazabilidad.</p></div>
          <button type="button" onClick={alCerrar} aria-label="Cerrar" className="rounded-lg p-2 hover:bg-slate-100"><X className="h-5 w-5" /></button>
        </header>
        <form onSubmit={enviar} className="space-y-5 p-6">
          <div className="grid gap-4 md:grid-cols-4">
            <label className="md:col-span-2 text-sm font-medium">Producto
              <select required value={producto} onChange={(e) => setProducto(e.target.value)} className={`${clase} mt-1.5`}><option value="">Selecciona…</option>{productos.filter((p) => p.naturaleza !== "materia_prima").map((p) => <option key={p.id} value={p.id}>{p.nombre}</option>)}</select>
            </label>
            <label className="text-sm font-medium">Versión<input readOnly value={version} className={`${clase} mt-1.5 bg-slate-50`} /></label>
            <label className="text-sm font-medium">Cantidad producida<input required min="0.001" step="any" type="number" value={cantidadBase} onChange={(e) => setCantidadBase(e.target.value)} className={`${clase} mt-1.5`} /></label>
            <label className="text-sm font-medium">Vigente desde<input required type="date" value={vigenteDesde} onChange={(e) => setVigenteDesde(e.target.value)} className={`${clase} mt-1.5`} /></label>
            <label className="md:col-span-3 text-sm font-medium">Fuente / respaldo<input required value={fuente} onChange={(e) => setFuente(e.target.value)} className={`${clase} mt-1.5`} /></label>
          </div>

          <div className="space-y-3">
            <div className="flex items-center justify-between"><h3 className="font-semibold">Componentes</h3><button type="button" onClick={() => setFilas((f) => [...f, nuevaFila()])} className="inline-flex items-center gap-1 rounded-lg border px-3 py-2 text-sm"><Plus className="h-4 w-4" /> Agregar</button></div>
            {filas.map((fila, indice) => {
              const opciones = fila.tipo === "producto" ? productos.filter((p) => p.id !== Number(producto)) : insumos;
              return <div key={fila.clave} className="grid gap-3 rounded-xl border border-slate-200 p-3 md:grid-cols-12">
                <select value={fila.tipo} onChange={(e) => cambiar(fila.clave, { tipo: e.target.value as Fila["tipo"], referencia: "" })} className={`${clase} md:col-span-2`}><option value="producto">Producto</option><option value="insumo">Insumo</option></select>
                <select required value={fila.referencia} onChange={(e) => cambiar(fila.clave, { referencia: e.target.value })} className={`${clase} md:col-span-3`}><option value="">Selecciona…</option>{opciones.map((o) => <option key={o.id} value={o.id}>{o.nombre}</option>)}</select>
                <select value={fila.fase} onChange={(e) => cambiar(fila.clave, { fase: e.target.value as Fila["fase"] })} className={`${clase} md:col-span-2`}>{fases.map((f) => <option key={f.valor} value={f.valor}>{f.etiqueta}</option>)}</select>
                <input aria-label={`Cantidad componente ${indice + 1}`} required min="0.0001" step="any" type="number" placeholder="Cantidad" value={fila.cantidad} onChange={(e) => cambiar(fila.clave, { cantidad: e.target.value })} className={`${clase} md:col-span-2`} />
                <input aria-label={`Merma componente ${indice + 1}`} min="0" step="any" type="number" placeholder="Merma %" value={fila.merma} onChange={(e) => cambiar(fila.clave, { merma: e.target.value })} className={`${clase} md:col-span-2`} />
                <button type="button" disabled={filas.length === 1} onClick={() => setFilas((f) => f.filter((x) => x.clave !== fila.clave))} aria-label={`Eliminar componente ${indice + 1}`} className="grid place-items-center rounded-lg text-red-700 disabled:opacity-30"><Trash2 className="h-4 w-4" /></button>
              </div>;
            })}
          </div>
          <p className="rounded-xl bg-sky-50 p-3 text-xs text-sky-800"><strong>Proceso</strong> se descuenta al cerrar el lote. <strong>Envasado</strong> se descuenta por cada pallet registrado.</p>
          {error && <p className="rounded-xl bg-red-50 p-3 text-sm text-red-700">{error}</p>}
          <div className="flex justify-end gap-3"><button type="button" onClick={alCerrar} className="rounded-xl px-4 py-2.5 text-sm">Cancelar</button><button disabled={guardando} className="rounded-xl bg-green-700 px-5 py-2.5 text-sm font-semibold text-white disabled:opacity-50">{guardando ? "Guardando…" : "Crear versión"}</button></div>
        </form>
      </div>
    </div>
  );
}
