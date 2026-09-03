import { useEffect, useState } from "react";
import { ArrowRightLeft, Boxes, LogOut, PackagePlus, Truck, X } from "lucide-react";
import { crearDespacho, ingresarMaterial, ingresarPallet, obtenerClientesDespacho, obtenerExistencias, obtenerGranelDisponible, obtenerInsumos, obtenerProductoTerminado, obtenerUbicaciones, registrarSalida, trasladarExistencia, type ClienteDespacho, type Existencia, type ExistenciaProductoTerminado, type GranelDisponible, type Insumo, type UbicacionInventario } from "../../services/inventario.service";
import { esAdministradorGlobal } from "../../services/access-control";
import { obtenerSesion } from "../../services/sesion";

type Operacion = "entrada" | "pallet" | "traslado" | "salida" | "despacho";
const campo = "w-full rounded-xl border border-slate-300 bg-white px-3 py-2.5 text-sm";
const vacio = { insumo: "", lote: "", existencia: "", ubicacion: "", cantidad: "", motivo: "", cliente: "", numero: "", pallet: "", granel: "", tipo_despacho: "pallet" };

export default function OperacionesBodega({ onCambio }: { onCambio: () => void }) {
  const usuario = obtenerSesion()?.usuario;
  const area = usuario?.perfil?.area;
  const [operacion, setOperacion] = useState<Operacion | null>(null);
  const [insumos, setInsumos] = useState<Insumo[]>([]);
  const [ubicaciones, setUbicaciones] = useState<UbicacionInventario[]>([]);
  const [existencias, setExistencias] = useState<Existencia[]>([]);
  const [productos, setProductos] = useState<ExistenciaProductoTerminado[]>([]);
  const [clientes, setClientes] = useState<ClienteDespacho[]>([]);
  const [graneles, setGraneles] = useState<GranelDisponible[]>([]);
  const [datos, setDatos] = useState(vacio);
  const [mensaje, setMensaje] = useState("");
  const [guardando, setGuardando] = useState(false);

  useEffect(() => {
    if (!operacion) return;
    const cargas = operacion === "despacho"
      ? [obtenerProductoTerminado().then(setProductos), obtenerClientesDespacho().then(setClientes), obtenerGranelDisponible().then(setGraneles)]
      : operacion === "pallet"
        ? [obtenerProductoTerminado().then(setProductos), obtenerUbicaciones().then(setUbicaciones)]
        : operacion === "entrada"
          ? [obtenerInsumos().then(setInsumos), obtenerUbicaciones().then(setUbicaciones)]
          : [obtenerExistencias().then(setExistencias), ...(operacion === "traslado" ? [obtenerUbicaciones().then(setUbicaciones)] : [])];
    void Promise.all(cargas).catch(() => setMensaje("No se pudieron cargar los datos de bodega."));
  }, [operacion]);

  async function guardar(evento: React.FormEvent) {
    evento.preventDefault(); setGuardando(true); setMensaje("");
    try {
      if (operacion === "entrada") await ingresarMaterial({ insumo: Number(datos.insumo), codigo_lote: datos.lote, ubicacion: Number(datos.ubicacion), cantidad: Number(datos.cantidad) });
      if (operacion === "pallet") await ingresarPallet(Number(datos.pallet), Number(datos.ubicacion));
      if (operacion === "traslado") await trasladarExistencia({ existencia: Number(datos.existencia), destino: Number(datos.ubicacion), cantidad: Number(datos.cantidad), motivo: datos.motivo });
      if (operacion === "salida") await registrarSalida({ existencia: Number(datos.existencia), cantidad: Number(datos.cantidad), tipo: "salida", motivo: datos.motivo });
      if (operacion === "despacho") await crearDespacho({
        numero: datos.numero,
        cliente: Number(datos.cliente),
        pallet_ids: datos.tipo_despacho === "pallet" ? [Number(datos.pallet)] : undefined,
        graneles: datos.tipo_despacho === "granel" ? [{ salida: Number(datos.granel), cantidad: Number(datos.cantidad) }] : undefined,
        observacion: datos.motivo,
      });
      setMensaje("Movimiento registrado y trazado correctamente."); onCambio(); setDatos(vacio);
    } catch (error) {
      const detalle = (error as { response?: { data?: { error?: string; detail?: string } } }).response?.data;
      setMensaje(detalle?.error || detalle?.detail || "No se pudo registrar la operación.");
    } finally { setGuardando(false); }
  }

  const todosLosBotones: Array<[Operacion, string, typeof PackagePlus]> = [
    ["entrada", "Ingresar envases/materiales", PackagePlus], ["pallet", "Recibir pallet liberado", Boxes], ["traslado", "Mover stock", ArrowRightLeft], ["salida", "Salida de bodega", LogOut], ["despacho", "Despachar producto", Truck],
  ];
  const operacionesBodega: Operacion[] = ["entrada", "pallet", "traslado", "salida"];
  const puedeDespachar = Boolean(
    usuario && (esAdministradorGlobal(usuario) || area === "despacho" || usuario.capacidades.includes("despacho_crear"))
  );
  const botones = todosLosBotones.filter(([id]) =>
    esAdministradorGlobal(usuario) || (area === "bodega" && operacionesBodega.includes(id)) || (id === "despacho" && puedeDespachar)
  );
  const palletsLiberados = productos.filter((p) => p.estado_inventario === "disponible" && p.ubicacion_tipo === "cuarentena");
  const materialSeleccionado = insumos.find((item) => item.id === Number(datos.insumo));
  const ubicacionesEntrada = ubicaciones.filter((item) =>
    item.tipo === (materialSeleccionado?.requiere_calidad ? "cuarentena" : "disponible")
  );

  return <section className="rounded-2xl border border-slate-200 bg-white p-6">
    <h2 className="text-xl font-bold text-slate-900">Operaciones de bodega</h2>
    <p className="mt-2 text-sm text-slate-600">Cada entrada, consumo, traslado y despacho genera trazabilidad; el saldo nunca se edita directamente.</p>
    {botones.length === 0
      ? <p className="mt-4 rounded-xl bg-slate-50 p-4 text-sm text-slate-600">Tu área tiene acceso de consulta. Los movimientos los registra Bodega y los despachos requieren autorización específica.</p>
      : <div className="mt-5 grid gap-3 sm:grid-cols-2 xl:grid-cols-5">{botones.map(([id, texto, Icono]) => <button key={id} type="button" onClick={() => { setMensaje(""); setOperacion(id); }} className="flex items-center gap-3 rounded-xl border border-slate-200 px-4 py-3 text-left text-sm font-semibold text-slate-800 hover:border-emerald-400 hover:bg-emerald-50"><Icono className="h-5 w-5 text-emerald-700" />{texto}</button>)}</div>}
    {operacion && <form onSubmit={guardar} className="mt-5 rounded-2xl bg-slate-50 p-5">
      <div className="flex items-center justify-between"><h3 className="font-bold text-slate-900">{botones.find(([id]) => id === operacion)?.[1]}</h3><button type="button" onClick={() => setOperacion(null)}><X className="h-5 w-5" /></button></div>
      <div className="mt-4 grid gap-3 md:grid-cols-2">
        {operacion === "entrada" && <><select required className={campo} value={datos.insumo} onChange={(e) => setDatos({ ...datos, insumo: e.target.value, ubicacion: "" })}><option value="">Envase o material…</option>{insumos.map((i) => <option key={i.id} value={i.id}>{i.codigo} · {i.nombre} ({i.unidad})</option>)}</select><input required className={campo} placeholder="Lote del proveedor" value={datos.lote} onChange={(e) => setDatos({ ...datos, lote: e.target.value })} /><SelectorUbicacion ubicaciones={ubicacionesEntrada} valor={datos.ubicacion} alCambiar={(ubicacion) => setDatos({ ...datos, ubicacion })} /><input required min="0.001" step="0.001" type="number" className={campo} placeholder="Cantidad recibida" value={datos.cantidad} onChange={(e) => setDatos({ ...datos, cantidad: e.target.value })} />{materialSeleccionado && <p className="text-xs font-medium text-slate-600 md:col-span-2">Destino requerido: {materialSeleccionado.requiere_calidad ? "Cuarentena; Calidad debe liberarlo antes de producir." : "Ubicación disponible; no requiere liberación de Calidad."}</p>}</>}
        {operacion === "pallet" && <><select required className={campo} value={datos.pallet} onChange={(e) => setDatos({ ...datos, pallet: e.target.value })}><option value="">Pallet liberado en cuarentena…</option>{palletsLiberados.map((p) => <option key={p.id} value={p.pallet}>{p.pallet_codigo} · {p.producto_nombre} · {p.kg_neto} kg</option>)}</select><SelectorUbicacion ubicaciones={ubicaciones.filter((u) => u.tipo === "disponible")} valor={datos.ubicacion} alCambiar={(ubicacion) => setDatos({ ...datos, ubicacion })} />{palletsLiberados.length === 0 && <p className="text-sm text-amber-700 md:col-span-2">No hay pallets liberados por Calidad pendientes de recibir.</p>}</>}
        {(operacion === "traslado" || operacion === "salida") && <><select required className={campo} value={datos.existencia} onChange={(e) => setDatos({ ...datos, existencia: e.target.value })}><option value="">Stock / lote…</option>{existencias.map((e) => <option key={e.id} value={e.id}>{e.insumo_nombre} · {e.lote_codigo} · {e.cantidad_disponible}</option>)}</select>{operacion === "traslado" && <SelectorUbicacion ubicaciones={ubicaciones} valor={datos.ubicacion} alCambiar={(ubicacion) => setDatos({ ...datos, ubicacion })} />}<input required min="0.001" step="0.001" type="number" className={campo} placeholder="Cantidad" value={datos.cantidad} onChange={(e) => setDatos({ ...datos, cantidad: e.target.value })} /><input required className={campo} placeholder="Motivo / documento" value={datos.motivo} onChange={(e) => setDatos({ ...datos, motivo: e.target.value })} /></>}
        {operacion === "despacho" && <>
          <input required className={campo} placeholder="Nº de despacho" value={datos.numero} onChange={(e) => setDatos({ ...datos, numero: e.target.value })} />
          <select required className={campo} value={datos.cliente} onChange={(e) => setDatos({ ...datos, cliente: e.target.value })}><option value="">Cliente…</option>{clientes.filter((c) => c.activo).map((c) => <option key={c.id} value={c.id}>{c.codigo} · {c.nombre}</option>)}</select>
          <select className={campo} value={datos.tipo_despacho} onChange={(e) => setDatos({ ...datos, tipo_despacho: e.target.value, pallet: "", granel: "", cantidad: "" })}>
            <option value="pallet">Producto terminado en pallet</option>
            <option value="granel">Precondensado / producto a granel</option>
          </select>
          {datos.tipo_despacho === "pallet" ? (
            <select required className={campo} value={datos.pallet} onChange={(e) => setDatos({ ...datos, pallet: e.target.value })}><option value="">Pallet disponible…</option>{productos.filter((p) => p.estado_inventario === "disponible" && p.ubicacion_tipo === "disponible").map((p) => <option key={p.id} value={p.pallet}>{p.pallet_codigo} · {p.producto_nombre} · {p.kg_neto} kg</option>)}</select>
          ) : <>
            <select required className={campo} value={datos.granel} onChange={(e) => { const elegido = graneles.find((item) => item.id === Number(e.target.value)); setDatos({ ...datos, granel: e.target.value, cantidad: elegido?.cantidad_disponible ?? "" }); }}><option value="">Granel liberado para despacho…</option>{graneles.map((item) => <option key={item.id} value={item.id}>{item.lote_codigo ?? item.corrida_codigo} · {item.producto_nombre} · {item.silo_codigo ?? "sin silo"} · {item.cantidad_disponible} {item.unidad}</option>)}</select>
            <input required min="0.001" step="0.001" type="number" className={campo} placeholder="Cantidad a despachar" value={datos.cantidad} onChange={(e) => setDatos({ ...datos, cantidad: e.target.value })} />
          </>}
          <input className={campo} placeholder="Observación" value={datos.motivo} onChange={(e) => setDatos({ ...datos, motivo: e.target.value })} />
        </>}
      </div>
      {mensaje && <p className="mt-3 text-sm text-slate-700">{mensaje}</p>}<button disabled={guardando} className="mt-4 rounded-xl bg-emerald-700 px-5 py-2.5 text-sm font-semibold text-white disabled:opacity-50">{guardando ? "Registrando…" : "Confirmar movimiento"}</button>
    </form>}
  </section>;
}

function SelectorUbicacion({ ubicaciones, valor, alCambiar }: { ubicaciones: UbicacionInventario[]; valor: string; alCambiar: (id: string) => void }) {
  return <select required className={campo} value={valor} onChange={(e) => alCambiar(e.target.value)}><option value="">Ubicación destino…</option>{ubicaciones.filter((u) => u.activo).map((u) => <option key={u.id} value={u.id}>{u.bodega_nombre}/{u.codigo} · {u.tipo_etiqueta}</option>)}</select>;
}
