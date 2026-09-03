import { useEffect, useState } from "react";
import { X } from "lucide-react";

import { mensajeDe } from "../../components/seccion/utilidades";
import { obtenerProductosMaestros, type ProductoMaestro } from "../../services/maestros.service";
import {
  crearRutaProducto,
  obtenerProcesosMaestros,
  type ProcesoMaestro,
  type RutaProducto,
} from "../../services/procesos.service";

const control = "mt-1 w-full rounded-xl border border-slate-300 bg-white px-3 py-2.5 text-sm";

export default function NuevaRutaProducto({ onCerrar, onCreada }: {
  onCerrar: () => void;
  onCreada: (ruta: RutaProducto) => void;
}) {
  const [productos, setProductos] = useState<ProductoMaestro[]>([]);
  const [procesos, setProcesos] = useState<ProcesoMaestro[]>([]);
  const [datos, setDatos] = useState({ producto: "", proceso: "", prioridad: "1", destino_final: "siguiente_proceso", destino: "", observaciones: "" });
  const [cargando, setCargando] = useState(true);
  const [guardando, setGuardando] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    let vigente = true;
    Promise.all([obtenerProductosMaestros(), obtenerProcesosMaestros()])
      .then(([catalogo, pagina]) => {
        if (!vigente) return;
        setProductos(catalogo.filter((item) => item.activo));
        setProcesos(pagina.results.filter((item) => item.activo && item.etapas.some((etapa) => etapa.activa)));
      })
      .catch((e) => setError(mensajeDe(e, "No se pudieron cargar productos y procesos.")))
      .finally(() => { if (vigente) setCargando(false); });
    return () => { vigente = false; };
  }, []);

  const guardar = async (evento: React.FormEvent) => {
    evento.preventDefault();
    if (guardando) return;
    setGuardando(true);
    setError("");
    try {
      onCreada(await crearRutaProducto({
        producto: Number(datos.producto),
        proceso: Number(datos.proceso),
        prioridad: Number(datos.prioridad),
        destino_final: datos.destino_final as RutaProducto["destino_final"],
        destino: datos.destino.trim(),
        observaciones: datos.observaciones.trim(),
      }));
    } catch (e) {
      setError(mensajeDe(e, "No se pudo crear la ruta productiva."));
    } finally {
      setGuardando(false);
    }
  };

  const proceso = procesos.find((item) => item.id === Number(datos.proceso));

  return <div className="fixed inset-0 z-[80] flex items-start justify-center overflow-y-auto bg-slate-950/45 p-4">
    <form onSubmit={guardar} className="my-8 w-full max-w-2xl rounded-2xl bg-white p-6 shadow-xl">
      <div className="flex items-start justify-between gap-3"><div><p className="text-xs font-semibold uppercase tracking-wide text-emerald-700">Configuración</p><h2 className="mt-1 text-xl font-semibold">Nueva ruta por producto</h2><p className="mt-2 text-sm text-slate-600">Relaciona un producto con una secuencia ya configurada. No crea ni altera etapas.</p></div><button type="button" onClick={onCerrar} aria-label="Cerrar" className="rounded-lg p-2 hover:bg-slate-100"><X className="h-5 w-5" /></button></div>
      {cargando ? <p className="mt-6 text-sm text-slate-600">Cargando catálogos…</p> : <div className="mt-6 grid gap-4 sm:grid-cols-2">
        <Campo texto="Producto"><select required value={datos.producto} onChange={(e) => setDatos({ ...datos, producto: e.target.value })} className={control}><option value="">Seleccionar…</option>{productos.map((item) => <option key={item.id} value={item.id}>{item.nombre}</option>)}</select></Campo>
        <Campo texto="Proceso / secuencia"><select required value={datos.proceso} onChange={(e) => setDatos({ ...datos, proceso: e.target.value })} className={control}><option value="">Seleccionar…</option>{procesos.map((item) => <option key={item.id} value={item.id}>{item.nombre}</option>)}</select></Campo>
        <Campo texto="Prioridad"><input required type="number" min="1" step="1" value={datos.prioridad} onChange={(e) => setDatos({ ...datos, prioridad: e.target.value })} className={control} /></Campo>
        <Campo texto="Destino final"><select value={datos.destino_final} onChange={(e) => setDatos({ ...datos, destino_final: e.target.value })} className={control}><option value="siguiente_proceso">Siguiente proceso</option><option value="envasado">Envasado</option><option value="despacho_directo">Despacho directo</option><option value="inventario">Inventario</option></select></Campo>
        <Campo texto="Destino descriptivo (opcional)"><input value={datos.destino} onChange={(e) => setDatos({ ...datos, destino: e.target.value })} className={control} /></Campo>
        <Campo texto="Observaciones"><textarea value={datos.observaciones} onChange={(e) => setDatos({ ...datos, observaciones: e.target.value })} className={control} /></Campo>
        {proceso && <div className="sm:col-span-2 rounded-xl bg-slate-50 p-3 text-sm text-slate-700"><span className="font-semibold">Secuencia:</span> {proceso.etapas.filter((item) => item.activa).map((item) => item.nombre).join(" → ")}</div>}
      </div>}
      {error && <p className="mt-4 rounded-xl bg-rose-50 p-3 text-sm text-rose-700">{error}</p>}
      <div className="mt-6 flex justify-end gap-3"><button type="button" onClick={onCerrar} className="px-4 py-2 text-sm text-slate-600">Cancelar</button><button disabled={cargando || guardando || !datos.producto || !datos.proceso} className="rounded-xl bg-emerald-700 px-5 py-2.5 text-sm font-semibold text-white disabled:opacity-40">{guardando ? "Creando…" : "Crear ruta"}</button></div>
    </form>
  </div>;
}

function Campo({ texto, children }: { texto: string; children: React.ReactNode }) {
  return <label className="text-sm font-medium text-slate-700">{texto}{children}</label>;
}
