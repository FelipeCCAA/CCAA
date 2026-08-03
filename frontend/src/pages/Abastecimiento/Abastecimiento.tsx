import { useEffect, useMemo, useState } from "react";
import { AlertTriangle, Boxes, ClipboardCheck, PackageCheck, ShoppingCart } from "lucide-react";

import {
  agregarDetalleMRQ, crearMRQ, decidirInspeccion, entregarMRQ, enviarMRQ,
  obtenerExistencias, obtenerInspecciones, obtenerInsumos, obtenerMRQ,
  obtenerNotificaciones, obtenerOrdenesCompra, reservarMRQ,
  type Existencia, type InspeccionMaterial, type Insumo, type Notificacion,
  type OrdenCompra, type SolicitudMaterial,
} from "../../services/inventario.service";
import { obtenerSesion } from "../../services/sesion";

const formato = (valor: string) => Number(valor).toLocaleString("es-CL", { maximumFractionDigits: 3 });

function Abastecimiento() {
  const [existencias, setExistencias] = useState<Existencia[]>([]);
  const [inspecciones, setInspecciones] = useState<InspeccionMaterial[]>([]);
  const [mrq, setMrq] = useState<SolicitudMaterial[]>([]);
  const [ordenes, setOrdenes] = useState<OrdenCompra[]>([]);
  const [notificaciones, setNotificaciones] = useState<Notificacion[]>([]);
  const [insumos, setInsumos] = useState<Insumo[]>([]);
  const [nuevaMrq, setNuevaMrq] = useState({ insumo: "", cantidad: "", fecha: "" });
  const [error, setError] = useState("");
  const sesion = obtenerSesion();
  const area = sesion?.usuario.perfil?.area ?? "administracion";

  const cargar = async () => {
    try {
      const [e, i, m, o, n, materiales] = await Promise.all([
        obtenerExistencias(), obtenerInspecciones(), obtenerMRQ(),
        obtenerOrdenesCompra(), obtenerNotificaciones(), obtenerInsumos(),
      ]);
      setExistencias(e); setInspecciones(i); setMrq(m); setOrdenes(o); setNotificaciones(n); setInsumos(materiales);
    } catch { setError("No se pudo cargar el panel de abastecimiento."); }
  };

  useEffect(() => {
    let vigente = true;
    Promise.all([
      obtenerExistencias(), obtenerInspecciones(), obtenerMRQ(),
      obtenerOrdenesCompra(), obtenerNotificaciones(), obtenerInsumos(),
    ]).then(([e, i, m, o, n, materiales]) => {
      if (!vigente) return;
      setExistencias(e); setInspecciones(i); setMrq(m); setOrdenes(o); setNotificaciones(n); setInsumos(materiales);
    }).catch(() => { if (vigente) setError("No se pudo cargar el panel de abastecimiento."); });
    return () => { vigente = false; };
  }, []);

  const indicadores = useMemo(() => ({
    disponible: existencias.reduce((s, e) => s + Number(e.cantidad_disponible), 0),
    cuarentena: existencias.filter((e) => e.estado_calidad === "pendiente").reduce((s, e) => s + Number(e.cantidad_fisica), 0),
    inspecciones: inspecciones.filter((i) => !["aprobada", "observada", "rechazada", "bloqueada"].includes(i.estado)).length,
    mrq: mrq.filter((m) => !["entregada", "rechazada", "cancelada"].includes(m.estado)).length,
  }), [existencias, inspecciones, mrq]);

  const puedeCalidad = area === "calidad" || sesion?.usuario.rol === "admin";
  const puedeBodega = area === "bodega" || sesion?.usuario.rol === "admin";
  const solicitarMaterial = async (evento: React.FormEvent) => {
    evento.preventDefault();
    try {
      const solicitud = await crearMRQ({ numero: `MRQ-${Date.now()}`, area, fecha_requerida: nuevaMrq.fecha, prioridad: 3 });
      await agregarDetalleMRQ({ solicitud: solicitud.id, insumo: Number(nuevaMrq.insumo), cantidad_solicitada: Number(nuevaMrq.cantidad) });
      await enviarMRQ(solicitud.id);
      setNuevaMrq({ insumo: "", cantidad: "", fecha: "" });
      await cargar();
    } catch { setError("No se pudo enviar la solicitud de materiales."); }
  };

  return <div className="px-8 py-10"><div className="mx-auto max-w-7xl">
    <header className="mb-8"><p className="text-sm font-semibold uppercase tracking-wider text-green-700">Cadena de suministro</p><h1 className="mt-2 text-3xl font-bold text-slate-800">Abastecimiento y Bodega</h1><p className="mt-2 text-slate-500">Inventario liberado, cuarentena, compras y solicitudes internas con trazabilidad por lote.</p></header>
    {error && <div className="mb-6 rounded-xl bg-red-50 p-4 text-red-700">{error}</div>}
    <section className="grid gap-5 sm:grid-cols-2 xl:grid-cols-4">
      {[
        { etiqueta: "Stock disponible", valor: indicadores.disponible, Icono: Boxes },
        { etiqueta: "En cuarentena", valor: indicadores.cuarentena, Icono: AlertTriangle },
        { etiqueta: "Inspecciones pendientes", valor: indicadores.inspecciones, Icono: ClipboardCheck },
        { etiqueta: "MRQ abiertas", valor: indicadores.mrq, Icono: PackageCheck },
      ].map(({ etiqueta, valor, Icono }) => <div key={etiqueta} className="rounded-2xl border border-slate-200 bg-white p-5"><Icono className="h-5 w-5 text-green-700"/><p className="mt-4 text-sm text-slate-500">{etiqueta}</p><p className="mt-1 text-2xl font-bold text-slate-900">{valor.toLocaleString("es-CL")}</p></div>)}
    </section>

    <section className="mt-8 rounded-2xl border border-slate-200 bg-white"><div className="border-b p-5"><h2 className="font-semibold text-slate-800">Existencias por lote</h2></div><div className="overflow-x-auto"><table className="w-full text-left text-sm"><thead className="bg-slate-50 text-slate-500"><tr><th className="px-5 py-3">Material</th><th className="px-5 py-3">Lote</th><th className="px-5 py-3">Ubicación</th><th className="px-5 py-3">Calidad</th><th className="px-5 py-3">Físico</th><th className="px-5 py-3">Disponible</th></tr></thead><tbody>{existencias.map((e) => <tr key={e.id} className="border-t"><td className="px-5 py-3 font-medium">{e.insumo_nombre}</td><td className="px-5 py-3">{e.lote_codigo}</td><td className="px-5 py-3">{e.ubicacion_codigo}</td><td className="px-5 py-3">{e.estado_calidad}</td><td className="px-5 py-3">{formato(e.cantidad_fisica)}</td><td className="px-5 py-3 font-semibold text-green-700">{formato(e.cantidad_disponible)}</td></tr>)}</tbody></table></div></section>

    <section className="mt-8 grid gap-8 xl:grid-cols-2">
      <div className="rounded-2xl border border-slate-200 bg-white"><div className="border-b p-5"><h2 className="font-semibold">Calidad de materiales</h2></div><div className="divide-y">{inspecciones.slice(0, 8).map((i) => <div key={i.id} className="p-5"><div className="flex justify-between gap-4"><div><p className="font-medium">{i.insumo_nombre} · {i.lote_codigo}</p><p className="mt-1 text-sm text-slate-500">Estado: {i.estado}</p></div>{puedeCalidad && !["aprobada", "observada", "rechazada", "bloqueada"].includes(i.estado) && <div className="flex gap-2"><button onClick={() => void decidirInspeccion(i.id, "aprobada").then(cargar)} className="rounded-lg bg-green-700 px-3 py-2 text-xs font-semibold text-white">Aprobar</button><button onClick={() => void decidirInspeccion(i.id, "rechazada", "Rechazo desde bandeja").then(cargar)} className="rounded-lg bg-red-50 px-3 py-2 text-xs font-semibold text-red-700">Rechazar</button></div>}</div></div>)}{inspecciones.length === 0 && <p className="p-5 text-sm text-slate-400">Sin inspecciones.</p>}</div></div>
      <div className="rounded-2xl border border-slate-200 bg-white"><div className="border-b p-5"><h2 className="font-semibold">Solicitudes de materiales</h2></div><div className="divide-y">{mrq.slice(0, 8).map((m) => <div key={m.id} className="flex items-center justify-between gap-4 p-5"><div><p className="font-medium">{m.numero}</p><p className="mt-1 text-sm text-slate-500">{m.area} · {m.estado} · requerida {m.fecha_requerida}</p></div>{puedeBodega && ["enviada", "aprobada"].includes(m.estado) && <button onClick={() => void reservarMRQ(m.id).then(cargar)} className="rounded-lg bg-green-700 px-3 py-2 text-xs font-semibold text-white">Reservar FEFO</button>}{puedeBodega && ["preparada", "parcial"].includes(m.estado) && <button onClick={() => void entregarMRQ(m.id).then(cargar)} className="rounded-lg bg-blue-700 px-3 py-2 text-xs font-semibold text-white">Entregar</button>}</div>)}{mrq.length === 0 && <p className="p-5 text-sm text-slate-400">Sin solicitudes.</p>}</div></div>
    </section>

    {area !== "bodega" && <section className="mt-8 rounded-2xl border border-slate-200 bg-white p-5"><h2 className="font-semibold">Solicitar material a Bodega</h2><form onSubmit={solicitarMaterial} className="mt-4 grid gap-3 md:grid-cols-4"><select required value={nuevaMrq.insumo} onChange={(e) => setNuevaMrq({ ...nuevaMrq, insumo: e.target.value })} className="rounded-xl border border-slate-300 bg-white px-4 py-3 text-sm"><option value="">Material</option>{insumos.map((i) => <option key={i.id} value={i.id}>{i.nombre}</option>)}</select><input required type="number" min="0.001" step="0.001" placeholder="Cantidad" value={nuevaMrq.cantidad} onChange={(e) => setNuevaMrq({ ...nuevaMrq, cantidad: e.target.value })} className="rounded-xl border border-slate-300 px-4 py-3 text-sm"/><input required type="date" value={nuevaMrq.fecha} onChange={(e) => setNuevaMrq({ ...nuevaMrq, fecha: e.target.value })} className="rounded-xl border border-slate-300 px-4 py-3 text-sm"/><button className="rounded-xl bg-green-700 px-5 py-3 text-sm font-semibold text-white">Enviar MRQ</button></form></section>}

    <section className="mt-8 grid gap-8 xl:grid-cols-2"><div className="rounded-2xl border border-slate-200 bg-white p-5"><div className="flex items-center gap-2"><ShoppingCart className="h-5 w-5 text-green-700"/><h2 className="font-semibold">Órdenes de compra</h2></div><div className="mt-4 space-y-3">{ordenes.slice(0, 6).map((o) => <div key={o.id} className="rounded-xl bg-slate-50 p-4"><p className="font-medium">{o.numero} · {o.proveedor_nombre}</p><p className="text-sm text-slate-500">{o.estado} · {o.detalles.length} materiales</p></div>)}</div></div><div className="rounded-2xl border border-slate-200 bg-white p-5"><h2 className="font-semibold">Notificaciones</h2><div className="mt-4 space-y-3">{notificaciones.slice(0, 6).map((n) => <div key={n.id} className="rounded-xl bg-slate-50 p-4"><p className="font-medium">{n.titulo}</p><p className="mt-1 text-sm text-slate-500">{n.mensaje}</p></div>)}{notificaciones.length === 0 && <p className="text-sm text-slate-400">Sin notificaciones.</p>}</div></div></section>
  </div></div>;
}

export default Abastecimiento;
