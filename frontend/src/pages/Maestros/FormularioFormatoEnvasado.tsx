import { useMemo, useState } from "react";
import axios from "axios";
import { AlertTriangle, X } from "lucide-react";

import {
  guardarFormatoEnvasado,
  type Equipo,
  type FormatoEnvasado,
  type ProductoMaestro,
} from "../../services/maestros.service";

interface Props {
  formato: FormatoEnvasado | null;
  productos: ProductoMaestro[];
  equipos: Equipo[];
  alCerrar: () => void;
  alGuardar: () => void;
}

const campo =
  "w-full rounded-xl border border-slate-300 bg-white px-4 py-3 outline-none focus:border-green-600";

export default function FormularioFormatoEnvasado({
  formato,
  productos,
  equipos,
  alCerrar,
  alGuardar,
}: Props) {
  const [producto, setProducto] = useState(String(formato?.producto ?? ""));
  const [codigo, setCodigo] = useState(formato?.codigo ?? "");
  const [nombre, setNombre] = useState(formato?.nombre ?? "");
  const [kgNeto, setKgNeto] = useState(formato?.kg_neto ?? "25");
  const [unidades, setUnidades] = useState(
    String(formato?.unidades_maximas_pallet ?? 20),
  );
  const [equiposElegidos, setEquiposElegidos] = useState<number[]>(
    formato?.equipos ?? [],
  );
  const [activo, setActivo] = useState(formato?.activo ?? true);
  const [guardando, setGuardando] = useState(false);
  const [error, setError] = useState("");

  const pesoPallet = Number(kgNeto || 0) * Number(unidades || 0);
  const productosTerminados = useMemo(
    () => productos.filter((item) => item.activo && item.naturaleza === "terminado"),
    [productos],
  );
  const lineas = useMemo(
    () => equipos.filter(
      (item) => item.activo && ["envasadora", "linea"].includes(item.tipo),
    ),
    [equipos],
  );
  const valido = Boolean(
    producto && codigo.trim() && nombre.trim() && Number(kgNeto) > 0
      && Number(unidades) > 0 && pesoPallet <= 500 && equiposElegidos.length,
  );

  const alternarEquipo = (id: number) => {
    setEquiposElegidos((actuales) =>
      actuales.includes(id)
        ? actuales.filter((actual) => actual !== id)
        : [...actuales, id],
    );
  };

  const guardar = async (evento: React.FormEvent<HTMLFormElement>) => {
    evento.preventDefault();
    if (!valido || guardando) return;
    setGuardando(true);
    setError("");
    try {
      await guardarFormatoEnvasado(formato?.id ?? null, {
        producto: Number(producto),
        codigo: codigo.trim(),
        nombre: nombre.trim(),
        kg_neto: Number(kgNeto),
        unidades_maximas_pallet: Number(unidades),
        equipos: equiposElegidos,
        activo,
      });
      alGuardar();
      alCerrar();
    } catch (excepcion) {
      if (axios.isAxiosError(excepcion) && excepcion.response) {
        const datos = excepcion.response.data as Record<string, string | string[]>;
        setError(Object.entries(datos).map(([clave, valor]) =>
          `${clave === "non_field_errors" ? "formato" : clave}: ${String(valor)}`,
        ).join(" · "));
      } else {
        setError("No se pudo conectar con el servidor.");
      }
    } finally {
      setGuardando(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-start justify-center overflow-y-auto bg-slate-900/40 p-4 sm:p-8">
      <div className="w-full max-w-2xl rounded-2xl bg-white shadow-xl">
        <div className="flex items-center justify-between border-b border-slate-200 px-6 py-5">
          <div>
            <h2 className="text-lg font-semibold text-slate-800">
              {formato ? "Editar formato de envase" : "Nuevo formato de envase"}
            </h2>
            <p className="mt-1 text-xs text-slate-500">
              Presentación comercial, límite físico del pallet y líneas autorizadas.
            </p>
          </div>
          <button type="button" onClick={alCerrar} aria-label="Cerrar" className="rounded-lg p-1 text-slate-600 hover:bg-slate-100">
            <X className="h-5 w-5" />
          </button>
        </div>
        <form onSubmit={guardar} className="space-y-5 px-6 py-6">
          <label className="block text-sm font-medium text-slate-700">
            Producto terminado *
            <select required disabled={Boolean(formato)} className={`mt-1.5 ${campo}`} value={producto} onChange={(e) => setProducto(e.target.value)}>
              <option value="">Seleccionar producto…</option>
              {productosTerminados.map((item) => <option key={item.id} value={item.id}>{item.codigo} · {item.nombre}</option>)}
            </select>
          </label>
          <div className="grid gap-4 sm:grid-cols-2">
            <label className="text-sm font-medium text-slate-700">Código *<input required className={`mt-1.5 ${campo}`} value={codigo} onChange={(e) => setCodigo(e.target.value)} placeholder="SACO-25KG" /></label>
            <label className="text-sm font-medium text-slate-700">Nombre *<input required className={`mt-1.5 ${campo}`} value={nombre} onChange={(e) => setNombre(e.target.value)} placeholder="Saco 25 kg" /></label>
            <label className="text-sm font-medium text-slate-700">Peso neto por envase (kg) *<input required type="number" min="0.001" step="0.001" className={`mt-1.5 ${campo}`} value={kgNeto} onChange={(e) => setKgNeto(e.target.value)} /></label>
            <label className="text-sm font-medium text-slate-700">Máximo de envases por pallet *<input required type="number" min="1" step="1" className={`mt-1.5 ${campo}`} value={unidades} onChange={(e) => setUnidades(e.target.value)} /></label>
          </div>
          <div className={`rounded-xl border p-4 ${pesoPallet > 500 ? "border-red-200 bg-red-50" : "border-emerald-200 bg-emerald-50"}`}>
            <p className="text-sm font-bold">Máximo configurado: {pesoPallet.toLocaleString("es-CL")} kg por pallet</p>
            <p className="mt-1 text-xs">El sistema impide superar 500 kg y también este máximo de unidades.</p>
          </div>
          <fieldset>
            <legend className="text-sm font-medium text-slate-700">Líneas autorizadas *</legend>
            <div className="mt-2 grid gap-2 sm:grid-cols-2">
              {lineas.map((item) => <label key={item.id} className="flex items-center gap-3 rounded-xl border border-slate-200 px-3 py-2 text-sm"><input type="checkbox" checked={equiposElegidos.includes(item.id)} onChange={() => alternarEquipo(item.id)} /><span><b>{item.codigo}</b> · {item.nombre}</span></label>)}
              {lineas.length === 0 && <p className="text-sm text-amber-700">Primero configura una línea o envasadora activa.</p>}
            </div>
          </fieldset>
          <label className="flex items-center gap-3 text-sm text-slate-700"><input type="checkbox" checked={activo} onChange={(e) => setActivo(e.target.checked)} />Formato activo y disponible para operar</label>
          {error && <p className="flex gap-2 rounded-xl border border-red-200 bg-red-50 p-3 text-sm text-red-700"><AlertTriangle className="h-5 w-5 shrink-0" />{error}</p>}
          <div className="flex justify-end gap-3 border-t border-slate-100 pt-5">
            <button type="button" onClick={alCerrar} className="rounded-xl border border-slate-300 px-4 py-2 text-sm font-semibold">Cancelar</button>
            <button disabled={!valido || guardando} className="rounded-xl bg-green-700 px-4 py-2 text-sm font-semibold text-white disabled:opacity-50">{guardando ? "Guardando…" : "Guardar formato"}</button>
          </div>
        </form>
      </div>
    </div>
  );
}
