import { useEffect, useState } from "react";
import { ArrowRightLeft, LogOut, PackagePlus, Truck, X } from "lucide-react";

import {
  crearDespacho, ingresarMaterial, obtenerClientesDespacho, obtenerExistencias,
  obtenerInsumos, obtenerProductoTerminado, obtenerUbicaciones,
  registrarSalida, trasladarExistencia, type Existencia, type Insumo,
  type ClienteDespacho, type ExistenciaProductoTerminado, type UbicacionInventario,
} from "../../services/inventario.service";

type Operacion = "entrada" | "traslado" | "salida" | "despacho";
const campo = "w-full rounded-xl border border-slate-300 bg-white px-3 py-2.5 text-sm";

export default function OperacionesBodega({ onCambio }: { onCambio: () => void }) {
  const [operacion, setOperacion] = useState<Operacion | null>(null);
  const [insumos, setInsumos] = useState<Insumo[]>([]);
  const [ubicaciones, setUbicaciones] = useState<UbicacionInventario[]>([]);
  const [existencias, setExistencias] = useState<Existencia[]>([]);
  const [productos, setProductos] = useState<ExistenciaProductoTerminado[]>([]);
  const [clientes, setClientes] = useState<ClienteDespacho[]>([]);
  const [datos, setDatos] = useState({ insumo: "", lote: "", existencia: "", ubicacion: "", cantidad: "", motivo: "", cliente: "", numero: "", pallet: "" });
  const [mensaje, setMensaje] = useState("");
  const [guardando, setGuardando] = useState(false);

  useEffect(() => {
    if (!operacion) return;
    setMensaje("");
    const cargas = operacion === "despacho"
      ? [obtenerProductoTerminado().then(setProductos), obtenerClientesDespacho().then(setClientes)]
      : operacion === "entrada"
      ? [obtenerInsumos().then(setInsumos), obtenerUbicaciones().then(setUbicaciones)]
      : [obtenerExistencias().then(setExistencias), ...(operacion === "traslado" ? [obtenerUbicaciones().then(setUbicaciones)] : [])];
    void Promise.all(cargas).catch(() => setMensaje("No se pudieron cargar los datos maestros de bodega."));
  }, [operacion]);

  async function guardar(evento: React.FormEvent) {
    evento.preventDefault(); setGuardando(true); setMensaje("");
    try {
      if (operacion === "entrada") await ingresarMaterial({ insumo: Number(datos.insumo), codigo_lote: datos.lote, ubicacion: Number(datos.ubicacion), cantidad: Number(datos.cantidad) });
      if (operacion === "traslado") await trasladarExistencia({ existencia: Number(datos.existencia), destino: Number(datos.ubicacion), cantidad: Number(datos.cantidad), motivo: datos.motivo });
      if (operacion === "salida") await registrarSalida({ existencia: Number(datos.existencia), cantidad: Number(datos.cantidad), tipo: "salida", motivo: datos.motivo });
      if (operacion === "despacho") await crearDespacho({ numero: datos.numero, cliente: Number(datos.cliente), pallet_ids: [Number(datos.pallet)], observacion: datos.motivo });
      setMensaje("Operación registrada y trazada correctamente."); onCambio();
      setDatos({ insumo: "", lote: "", existencia: "", ubicacion: "", cantidad: "", motivo: "", cliente: "", numero: "", pallet: "" });
    } catch (error) {
      const detalle = (error as { response?: { data?: { error?: string; detail?: string } } }).response?.data;
      setMensaje(detalle?.error || detalle?.detail || "No se pudo registrar la operación.");
    } finally { setGuardando(false); }
  }

  const botones: Array<[Operacion, string, typeof PackagePlus]> = [
    ["entrada", "Entrada de material", PackagePlus], ["traslado", "Mover stock", ArrowRightLeft], ["salida", "Salida de bodega", LogOut],
    ["despacho", "Despachar producto", Truck],
  ];

  return <section className="rounded-2xl border border-slate-200 bg-white p-6">
    <h2 className="text-xl font-bold text-slate-900">Operaciones de bodega</h2>
    <p className="mt-2 text-sm text-slate-600">Como en SAP: cada acción genera un movimiento; nunca se edita el saldo directamente.</p>
    <div className="mt-5 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">{botones.map(([id, texto, Icono]) => <button key={id} type="button" onClick={() => setOperacion(id)} className="flex items-center gap-3 rounded-xl border border-slate-200 px-4 py-3 text-left text-sm font-semibold text-slate-800 hover:border-emerald-400 hover:bg-emerald-50"><Icono className="h-5 w-5 text-emerald-700" />{texto}</button>)}</div>
    {operacion && <form onSubmit={guardar} className="mt-5 rounded-2xl bg-slate-50 p-5"><div className="flex items-center justify-between"><h3 className="font-bold capitalize text-slate-900">{operacion}</h3><button type="button" onClick={() => setOperacion(null)}><X className="h-5 w-5" /></button></div><div className="mt-4 grid gap-3 md:grid-cols-2">
      {operacion === "despacho" ? <><input required className={campo} placeholder="Nº de despacho" value={datos.numero} onChange={(e) => setDatos({ ...datos, numero: e.target.value })} /><select required className={campo} value={datos.cliente} onChange={(e) => setDatos({ ...datos, cliente: e.target.value })}><option value="">Cliente…</option>{clientes.filter((c) => c.activo).map((c) => <option key={c.id} value={c.id}>{c.codigo} · {c.nombre}</option>)}</select><select required className={campo} value={datos.pallet} onChange={(e) => setDatos({ ...datos, pallet: e.target.value })}><option value="">Pallet disponible…</option>{productos.filter((p) => p.estado_inventario === "disponible").map((p) => <option key={p.id} value={p.pallet}>{p.pallet_codigo} · {p.producto_nombre} · {p.kg_neto} kg</option>)}</select><input className={campo} placeholder="Observación" value={datos.motivo} onChange={(e) => setDatos({ ...datos, motivo: e.target.value })} /></> : <>{operacion === "entrada" ? <><select required className={campo} value={datos.insumo} onChange={(e) => setDatos({ ...datos, insumo: e.target.value })}><option value="">Material…</option>{insumos.map((i) => <option key={i.id} value={i.id}>{i.codigo} · {i.nombre}</option>)}</select><input required className={campo} placeholder="Lote del proveedor" value={datos.lote} onChange={(e) => setDatos({ ...datos, lote: e.target.value })} /></> : <select required className={campo} value={datos.existencia} onChange={(e) => setDatos({ ...datos, existencia: e.target.value })}><option value="">Stock / lote…</option>{existencias.map((e) => <option key={e.id} value={e.id}>{e.insumo_nombre} · {e.lote_codigo} · {e.cantidad_disponible}</option>)}</select>}{(operacion === "entrada" || operacion === "traslado") && <select required className={campo} value={datos.ubicacion} onChange={(e) => setDatos({ ...datos, ubicacion: e.target.value })}><option value="">Ubicación destino…</option>{ubicaciones.filter((u) => u.activo).map((u) => <option key={u.id} value={u.id}>{u.bodega_nombre}/{u.codigo} · {u.tipo_etiqueta}</option>)}</select>}<input required min="0.001" step="0.001" type="number" className={campo} placeholder="Cantidad" value={datos.cantidad} onChange={(e) => setDatos({ ...datos, cantidad: e.target.value })} />{operacion !== "entrada" && <input required className={campo} placeholder="Motivo / documento" value={datos.motivo} onChange={(e) => setDatos({ ...datos, motivo: e.target.value })} />}</>}
    </div>{mensaje && <p className="mt-3 text-sm text-slate-700">{mensaje}</p>}<button disabled={guardando} className="mt-4 rounded-xl bg-emerald-700 px-5 py-2.5 text-sm font-semibold text-white disabled:opacity-50">{guardando ? "Registrando…" : "Confirmar movimiento"}</button></form>}
  </section>;
}
