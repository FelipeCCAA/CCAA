import { useEffect, useMemo, useState } from "react";
import {
  Boxes, History, PackageCheck, RefreshCw, Search, ShieldAlert,
  TestTube2, Warehouse,
} from "lucide-react";

import {
  autorizarDespacho, ejecutarDespacho,
  obtenerDespachos,
  obtenerEstadoOperacionalInventario, obtenerMovimientosProductoTerminado,
  obtenerProductoTerminado, type EstadoOperacionalInventario,
  type Despacho, type ExistenciaProductoTerminado, type MovimientoProductoTerminado,
} from "../../services/inventario.service";
import { esAdministradorGlobal } from "../../services/access-control";
import { obtenerSesion } from "../../services/sesion";
import OperacionesBodega from "./OperacionesBodega";

type Pestana = "stock" | "productos" | "lotes" | "movimientos" | "despachos" | "historial";
const numero = new Intl.NumberFormat("es-CL", { maximumFractionDigits: 0 });
const fecha = new Intl.DateTimeFormat("es-CL", { dateStyle: "short", timeStyle: "short" });

function valor(cantidad: string | number) {
  return numero.format(Number(cantidad || 0));
}

function TarjetaStock({ titulo, cantidad, tono, icono: Icono }: {
  titulo: string; cantidad: string | number; tono: string; icono: typeof Warehouse;
}) {
  return <article className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
    <div className="flex items-center justify-between">
      <p className="text-sm font-medium text-slate-600">{titulo}</p>
      <span className={`rounded-xl p-2 ${tono}`}><Icono className="h-5 w-5" /></span>
    </div>
    <p className="mt-4 text-3xl font-bold tabular-nums text-slate-900">{valor(cantidad)} <small className="text-base font-medium text-slate-500">kg</small></p>
  </article>;
}

export default function Inventario() {
  const usuario = obtenerSesion()?.usuario;
  const puedeAutorizarDespachos = Boolean(
    usuario && (esAdministradorGlobal(usuario) || usuario.capacidades.includes("despacho_autorizar")),
  );
  const [resumen, setResumen] = useState<EstadoOperacionalInventario | null>(null);
  const [pestana, setPestana] = useState<Pestana>("stock");
  const [productos, setProductos] = useState<ExistenciaProductoTerminado[] | null>(null);
  const [movimientos, setMovimientos] = useState<MovimientoProductoTerminado[] | null>(null);
  const [despachos, setDespachos] = useState<Despacho[] | null>(null);
  const [accionandoDespacho, setAccionandoDespacho] = useState<number | null>(null);
  const [error, setError] = useState("");
  const [cargando, setCargando] = useState(true);
  const [busquedaMaterial, setBusquedaMaterial] = useState("");

  async function cargarResumen(refrescar = false) {
    setCargando(true); setError("");
    try { setResumen(await obtenerEstadoOperacionalInventario(refrescar)); }
    catch { setError("No se pudo cargar el estado operacional de Inventario."); }
    finally { setCargando(false); }
  }

  function actualizarDespuesDeMovimiento() {
    setProductos(null);
    setMovimientos(null);
    void cargarResumen(true);
  }

  useEffect(() => {
    let vigente = true;
    void obtenerEstadoOperacionalInventario()
      .then((datos) => { if (vigente) setResumen(datos); })
      .catch(() => { if (vigente) setError("No se pudo cargar el estado operacional de Inventario."); })
      .finally(() => { if (vigente) setCargando(false); });
    return () => { vigente = false; };
  }, []);

  useEffect(() => {
    if ((pestana === "productos" || pestana === "lotes") && productos === null) {
      void obtenerProductoTerminado().then(setProductos).catch(() => setError("No se pudo cargar el producto terminado."));
    }
    if ((pestana === "movimientos" || pestana === "historial") && movimientos === null) {
      void obtenerMovimientosProductoTerminado().then(setMovimientos).catch(() => setError("No se pudo cargar el historial de movimientos."));
    }
    if (pestana === "despachos" && despachos === null) {
      void obtenerDespachos().then(setDespachos).catch(() => setError("No se pudieron cargar los despachos."));
    }
  }, [pestana, productos, movimientos, despachos]);

  async function avanzarDespacho(despacho: Despacho) {
    setAccionandoDespacho(despacho.id); setError("");
    try {
      const actualizado = despacho.estado === "borrador"
        ? await autorizarDespacho(despacho.id)
        : await ejecutarDespacho(despacho.id);
      setDespachos((actuales) => actuales?.map((item) => item.id === actualizado.id ? actualizado : item) ?? null);
      if (actualizado.estado === "despachado") actualizarDespuesDeMovimiento();
    } catch (errorPeticion: unknown) {
      const datos = (errorPeticion as { response?: { data?: { detail?: string; error?: string } } }).response?.data;
      setError(datos?.detail || datos?.error || "No se pudo avanzar el despacho.");
    } finally { setAccionandoDespacho(null); }
  }

  const lotes = useMemo(() => {
    const agrupados = new Map<string, { producto: string; fisico: number; disponible: number; pallets: number }>();
    for (const item of productos ?? []) {
      const actual = agrupados.get(item.lote_codigo) ?? { producto: item.producto_nombre, fisico: 0, disponible: 0, pallets: 0 };
      actual.fisico += Number(item.kg_neto); actual.disponible += Number(item.kg_disponible); actual.pallets += 1;
      agrupados.set(item.lote_codigo, actual);
    }
    return [...agrupados.entries()];
  }, [productos]);

  const materialesFiltrados = useMemo(() => {
    const termino = busquedaMaterial.trim().toLocaleLowerCase("es");
    if (!termino) return resumen?.materiales ?? [];
    return (resumen?.materiales ?? []).filter((item) =>
      `${item.codigo} ${item.nombre} ${item.categoria}`.toLocaleLowerCase("es").includes(termino),
    );
  }, [busquedaMaterial, resumen]);

  const pestanas: Array<[Pestana, string]> = [
    ["stock", "Stock"], ["productos", "Productos"], ["lotes", "Lotes"],
    ["movimientos", "Movimientos"], ["despachos", "Despachos"], ["historial", "Historial"],
  ];

  return <main className="min-h-screen bg-slate-50 px-4 py-7 sm:px-8">
    <div className="mx-auto max-w-7xl space-y-6">
      <header className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <p className="text-xs font-bold uppercase tracking-[0.18em] text-emerald-700">Fuente oficial de existencias</p>
          <h1 className="mt-2 flex items-center gap-3 text-3xl font-bold text-slate-950"><Warehouse className="h-8 w-8 text-emerald-700" /> Inventario operacional</h1>
          <p className="mt-2 text-sm text-slate-600">Materiales, ubicaciones, producto terminado y movimientos de bodega.</p>
        </div>
        <button type="button" onClick={() => void cargarResumen(true)} disabled={cargando} className="flex items-center gap-2 rounded-xl border border-slate-300 bg-white px-4 py-2.5 text-sm font-semibold text-slate-700 hover:bg-slate-100 disabled:opacity-50">
          <RefreshCw className={`h-4 w-4 ${cargando ? "animate-spin" : ""}`} /> Actualizar
        </button>
      </header>

      {error && <p className="rounded-xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700">{error}</p>}
      {cargando && !resumen ? <p className="py-16 text-center text-sm text-slate-500">Cargando Inventario…</p> : resumen && <>
        <section className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
          <TarjetaStock titulo="Stock físico" cantidad={resumen.stock.fisico_kg} tono="bg-slate-100 text-slate-700" icono={Boxes} />
          <TarjetaStock titulo="Disponible" cantidad={resumen.stock.disponible_kg} tono="bg-emerald-50 text-emerald-700" icono={PackageCheck} />
          <TarjetaStock titulo="En cuarentena" cantidad={resumen.stock.cuarentena_kg} tono="bg-amber-50 text-amber-700" icono={TestTube2} />
          <TarjetaStock titulo="Bloqueado" cantidad={resumen.stock.bloqueado_kg} tono="bg-rose-50 text-rose-700" icono={ShieldAlert} />
        </section>

        <nav className="flex gap-1 overflow-x-auto rounded-2xl border border-slate-200 bg-white p-1.5" aria-label="Secciones de Inventario">
          {pestanas.map(([id, etiqueta]) => <button key={id} type="button" onClick={() => setPestana(id)} className={`whitespace-nowrap rounded-xl px-4 py-2 text-sm font-semibold ${pestana === id ? "bg-slate-900 text-white" : "text-slate-600 hover:bg-slate-100"}`}>{etiqueta}</button>)}
        </nav>

        {pestana === "stock" && <div className="space-y-6">
          <section className="overflow-hidden rounded-2xl border border-slate-200 bg-white">
            <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-200 px-5 py-4">
              <div>
                <h2 className="font-bold text-slate-900">Materiales, envases y pallets</h2>
                <p className="mt-1 text-xs text-slate-500">Saldo físico y realmente utilizable por Bodega y Producción.</p>
              </div>
              <label className="flex min-w-64 items-center gap-2 rounded-xl border border-slate-300 bg-white px-3 py-2 text-sm text-slate-600 focus-within:border-emerald-500">
                <Search className="h-4 w-4" />
                <input value={busquedaMaterial} onChange={(evento) => setBusquedaMaterial(evento.target.value)} placeholder="Buscar código o material" className="w-full bg-transparent outline-none" />
              </label>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full min-w-[920px] text-left text-sm">
                <thead className="bg-slate-50 text-xs uppercase text-slate-500"><tr><th className="px-5 py-3">Material</th><th className="px-5 py-3">Físico</th><th className="px-5 py-3">Disponible</th><th className="px-5 py-3">Reservado</th><th className="px-5 py-3">Cuarentena</th><th className="px-5 py-3">Bloqueado</th><th className="px-5 py-3">Ubicaciones</th><th className="px-5 py-3">Estado</th></tr></thead>
                <tbody>{materialesFiltrados.map((item) => {
                  const bajoMinimo = Number(item.stock_minimo) > 0 && Number(item.disponible) <= Number(item.stock_minimo);
                  const conRetencion = Number(item.cuarentena) > 0 || Number(item.bloqueado) > 0;
                  return <tr key={item.insumo_id} className="border-t border-slate-100">
                    <td className="px-5 py-4"><p className="font-semibold text-slate-900">{item.nombre}</p><p className="text-xs text-slate-500">{item.codigo} · {item.categoria.replaceAll("_", " ")}</p></td>
                    <td className="px-5 py-4 font-semibold">{valor(item.fisico)} {item.unidad}</td>
                    <td className="px-5 py-4 font-bold text-emerald-700">{valor(item.disponible)} {item.unidad}</td>
                    <td className="px-5 py-4">{valor(item.reservado)} {item.unidad}</td>
                    <td className="px-5 py-4 text-amber-700">{valor(item.cuarentena)} {item.unidad}</td>
                    <td className="px-5 py-4 text-rose-700">{valor(item.bloqueado)} {item.unidad}</td>
                    <td className="px-5 py-4">{item.ubicaciones}</td>
                    <td className="px-5 py-4">{bajoMinimo ? <span className="rounded-full bg-rose-100 px-2.5 py-1 text-xs font-bold text-rose-800">Bajo mínimo</span> : conRetencion ? <span className="rounded-full bg-amber-100 px-2.5 py-1 text-xs font-bold text-amber-800">Revisar Calidad</span> : <span className="rounded-full bg-emerald-100 px-2.5 py-1 text-xs font-bold text-emerald-800">Disponible</span>}</td>
                  </tr>;
                })}</tbody>
              </table>
              {materialesFiltrados.length === 0 && <p className="px-5 py-8 text-center text-sm text-slate-500">{busquedaMaterial ? "No hay materiales que coincidan con la búsqueda." : "No hay materiales con existencia física."}</p>}
            </div>
          </section>
          <section className="overflow-hidden rounded-2xl border border-slate-200 bg-white">
            <div className="border-b border-slate-200 px-5 py-4">
              <h2 className="font-bold text-slate-900">Productos: Producción → Calidad → Bodega</h2>
              <p className="mt-1 text-xs text-slate-500">Un solo resumen: lotes activos, kilos físicos y pallets realmente registrados.</p>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full min-w-[760px] text-left text-sm">
                <thead className="bg-slate-50 text-xs uppercase text-slate-500"><tr><th className="px-5 py-3">Producto</th><th className="px-5 py-3">En producción</th><th className="px-5 py-3">Producidos</th><th className="px-5 py-3">En bodega</th><th className="px-5 py-3">Disponible</th><th className="px-5 py-3">Pallets</th><th className="px-5 py-3">Calidad</th></tr></thead>
                <tbody>{resumen.productos.map((item) => <tr key={item.producto_id} className="border-t border-slate-100">
                  <td className="px-5 py-4 font-semibold text-slate-900">{item.producto_nombre}</td>
                  <td className="px-5 py-4"><b>{item.lotes_en_proceso}</b> lotes</td>
                  <td className="px-5 py-4"><b>{item.lotes_producidos}</b> · {valor(item.kg_declarados)} kg</td>
                  <td className="px-5 py-4 font-semibold">{valor(item.kg_bodega)} kg</td>
                  <td className="px-5 py-4 text-emerald-700">{valor(item.kg_disponible)} kg</td>
                  <td className="px-5 py-4"><b>{item.pallets_bodega}</b></td>
                  <td className="px-5 py-4">{item.pallets_cuarentena > 0 ? <span className="rounded-full bg-amber-100 px-2.5 py-1 text-xs font-bold text-amber-800">{item.pallets_cuarentena} en cuarentena</span> : <span className="text-xs text-slate-500">Sin pendientes</span>}</td>
                </tr>)}</tbody>
              </table>
              {resumen.productos.length === 0 && <p className="px-5 py-8 text-center text-sm text-slate-500">No hay lotes activos ni pallets en bodega.</p>}
            </div>
          </section>
          <OperacionesBodega onCambio={actualizarDespuesDeMovimiento} />
        </div>}

        {pestana === "productos" && <section className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">{productos?.map((item) => <article key={item.id} className="rounded-2xl border border-slate-200 bg-white p-5"><div className="flex justify-between gap-3"><div><p className="font-bold text-slate-900">{item.pallet_codigo}</p><p className="text-sm text-slate-600">{item.producto_nombre}</p></div><span className="h-fit rounded-full bg-slate-100 px-2.5 py-1 text-xs font-semibold text-slate-700">{item.estado_inventario}</span></div><p className="mt-4 text-2xl font-bold text-slate-900">{valor(item.kg_neto)} kg</p><p className="mt-1 text-xs text-slate-500">Lote {item.lote_codigo} · {item.ubicacion_codigo}</p>{item.estado_inventario === "disponible" && item.ubicacion_tipo === "cuarentena" && <p className="mt-2 text-xs font-medium text-amber-700">Liberado por Calidad; pendiente de reubicación física.</p>}</article>)}{productos?.length === 0 && <p className="text-sm text-slate-500">No hay producto terminado físico.</p>}</section>}

        {pestana === "lotes" && <section className="overflow-x-auto rounded-2xl border border-slate-200 bg-white"><table className="w-full text-left text-sm"><thead className="bg-slate-50 text-xs uppercase text-slate-500"><tr><th className="px-5 py-3">Lote</th><th className="px-5 py-3">Producto</th><th className="px-5 py-3">Pallets</th><th className="px-5 py-3">Físico</th><th className="px-5 py-3">Disponible</th></tr></thead><tbody>{lotes.map(([codigo, lote]) => <tr key={codigo} className="border-t border-slate-100"><td className="px-5 py-3 font-semibold">{codigo}</td><td className="px-5 py-3">{lote.producto}</td><td className="px-5 py-3">{lote.pallets}</td><td className="px-5 py-3">{valor(lote.fisico)} kg</td><td className="px-5 py-3">{valor(lote.disponible)} kg</td></tr>)}</tbody></table></section>}

        {pestana === "despachos" && <section className="space-y-3">{despachos?.map((despacho) => <article key={despacho.id} className="flex flex-wrap items-center justify-between gap-4 rounded-2xl border border-slate-200 bg-white p-5"><div><p className="font-bold text-slate-900">{despacho.numero} · {despacho.cliente_nombre}</p><p className="mt-1 text-xs text-slate-500">{despacho.detalles.length > 0 ? `${despacho.detalles.length} pallet(s) · ${valor(despacho.detalles.reduce((suma, item) => suma + Number(item.kg_neto), 0))} kg` : ""}{despacho.detalles.length > 0 && despacho.detalles_granel.length > 0 ? " · " : ""}{despacho.detalles_granel.map((item) => `${item.lote_codigo ?? item.corrida_codigo} · ${item.producto_nombre} · ${item.silo_codigo ?? "sin silo"}: ${valor(item.cantidad)} ${item.unidad}`).join(" · ")}</p></div><div className="flex items-center gap-2"><span className="rounded-full bg-slate-100 px-3 py-1 text-xs font-bold uppercase text-slate-700">{despacho.estado}</span>{["borrador", "autorizado"].includes(despacho.estado) && (puedeAutorizarDespachos ? <button type="button" disabled={accionandoDespacho === despacho.id} onClick={() => void avanzarDespacho(despacho)} className="rounded-xl bg-emerald-700 px-4 py-2 text-sm font-semibold text-white disabled:opacity-50">{accionandoDespacho === despacho.id ? "Validando…" : despacho.estado === "borrador" ? "Autorizar" : "Confirmar salida"}</button> : <span className="text-xs font-medium text-amber-700">Pendiente de autorización</span>)}</div></article>)}{despachos?.length === 0 && <p className="text-sm text-slate-500">No hay despachos registrados.</p>}</section>}

        {(pestana === "movimientos" || pestana === "historial") && <section className="space-y-3">{movimientos?.map((item) => <article key={item.id} className="flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-slate-200 bg-white px-5 py-4"><div className="flex items-center gap-3"><span className="rounded-xl bg-slate-100 p-2 text-slate-600"><History className="h-4 w-4" /></span><div><p className="font-semibold text-slate-900">{item.tipo.replaceAll("_", " ")} · {item.pallet_codigo}</p><p className="text-xs text-slate-500">{item.motivo || "Movimiento de producto terminado"}</p></div></div><time className="text-xs text-slate-500">{fecha.format(new Date(item.registrado_en))}</time></article>)}{movimientos?.length === 0 && <p className="text-sm text-slate-500">No hay movimientos registrados.</p>}</section>}
      </>}
    </div>
  </main>;
}
