import { useEffect, useMemo, useState } from "react";
import { AlertTriangle, Boxes, ClipboardCheck, PackageCheck, ShoppingCart } from "lucide-react";

import {
  agregarDetalleMRQ, crearMRQ, decidirInspeccion, entregarMRQ, enviarMRQ,
  consumirRecetaProduccion, crearMaterial, ingresarMaterial, obtenerExistencias, obtenerInspecciones, obtenerInsumos, obtenerMRQ,
  crearAjuste, decidirAjuste, obtenerAjustes, obtenerMovimientos, obtenerNotificaciones,
  obtenerOrdenesCompra, obtenerUbicaciones, registrarSalida, reservarMRQ,
  type AjusteInventario, type MovimientoInventario,
  type Existencia, type InspeccionMaterial, type Insumo, type Notificacion,
  type OrdenCompra, type SolicitudMaterial,
} from "../../services/inventario.service";
import { obtenerSesion } from "../../services/sesion";
import { obtenerLotes, type Lote } from "../../services/produccion.service";
import type { UbicacionInventario } from "../../services/inventario.service";

const formato = (valor: string) => Number(valor).toLocaleString("es-CL", { maximumFractionDigits: 3 });

function Abastecimiento() {
  const [existencias, setExistencias] = useState<Existencia[]>([]);
  const [inspecciones, setInspecciones] = useState<InspeccionMaterial[]>([]);
  const [mrq, setMrq] = useState<SolicitudMaterial[]>([]);
  const [ordenes, setOrdenes] = useState<OrdenCompra[]>([]);
  const [notificaciones, setNotificaciones] = useState<Notificacion[]>([]);
  const [insumos, setInsumos] = useState<Insumo[]>([]);
  const [movimientos, setMovimientos] = useState<MovimientoInventario[]>([]);
  const [ajustes, setAjustes] = useState<AjusteInventario[]>([]);
  const [ubicaciones, setUbicaciones] = useState<UbicacionInventario[]>([]);
  const [lotesProduccion, setLotesProduccion] = useState<Lote[]>([]);
  const [operacion, setOperacion] = useState({ existencia: "", tipo: "consumo", cantidad: "", motivo: "" });
  const [nuevoMaterial, setNuevoMaterial] = useState({ codigo: "", nombre: "", categoria: "materia_prima", unidad: "kg", requiere_calidad: true, requiere_lote: true, requiere_vencimiento: true });
  const [ingreso, setIngreso] = useState({ insumo: "", codigo_lote: "", ubicacion: "", cantidad: "", elaboracion: "", vencimiento: "" });
  const [loteAConsumir, setLoteAConsumir] = useState("");
  const [nuevaMrq, setNuevaMrq] = useState({ insumo: "", cantidad: "", fecha: "" });
  const [error, setError] = useState("");
  const sesion = obtenerSesion();
  const area = sesion?.usuario.perfil?.area ?? "administracion";

  const cargar = async () => {
    try {
      const [e, i, m, o, n, materiales, movimientosData, ajustesData, ubicacionesData, lotesData] = await Promise.all([
        obtenerExistencias(), obtenerInspecciones(), obtenerMRQ(),
        obtenerOrdenesCompra(), obtenerNotificaciones(), obtenerInsumos(), obtenerMovimientos(), obtenerAjustes(), obtenerUbicaciones(), obtenerLotes(100),
      ]);
      setExistencias(e); setInspecciones(i); setMrq(m); setOrdenes(o); setNotificaciones(n); setInsumos(materiales);
      setMovimientos(movimientosData); setAjustes(ajustesData);
      setUbicaciones(ubicacionesData); setLotesProduccion(lotesData);
    } catch { setError("No se pudo cargar el panel de abastecimiento."); }
  };

  useEffect(() => {
    let vigente = true;
    Promise.all([
      obtenerExistencias(), obtenerInspecciones(), obtenerMRQ(),
      obtenerOrdenesCompra(), obtenerNotificaciones(), obtenerInsumos(), obtenerMovimientos(), obtenerAjustes(), obtenerUbicaciones(), obtenerLotes(100),
    ]).then(([e, i, m, o, n, materiales, movimientosData, ajustesData, ubicacionesData, lotesData]) => {
      if (!vigente) return;
      setExistencias(e); setInspecciones(i); setMrq(m); setOrdenes(o); setNotificaciones(n); setInsumos(materiales);
      setMovimientos(movimientosData); setAjustes(ajustesData);
      setUbicaciones(ubicacionesData); setLotesProduccion(lotesData);
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

  const registrarOperacion = async (evento: React.FormEvent) => {
    evento.preventDefault(); setError("");
    try {
      const base = { existencia: Number(operacion.existencia), cantidad: Number(operacion.cantidad), motivo: operacion.motivo };
      if (["positivo", "negativo", "merma"].includes(operacion.tipo)) {
        await crearAjuste({ ...base, tipo: operacion.tipo as "positivo" | "negativo" | "merma" });
      } else {
        await registrarSalida({ ...base, tipo: operacion.tipo as "salida" | "consumo" });
      }
      setOperacion({ existencia: "", tipo: "consumo", cantidad: "", motivo: "" });
      await cargar();
    } catch { setError("No se pudo registrar: verifica Calidad, stock disponible, reservas y motivo."); }
  };

  const guardarMaterial = async (evento: React.FormEvent) => {
    evento.preventDefault();
    try { await crearMaterial({ ...nuevoMaterial, area: "bodega" }); setNuevoMaterial({ codigo: "", nombre: "", categoria: "materia_prima", unidad: "kg", requiere_calidad: true, requiere_lote: true, requiere_vencimiento: true }); await cargar(); }
    catch { setError("No se pudo crear el material; revisa que el código/ID no esté repetido."); }
  };
  const guardarIngreso = async (evento: React.FormEvent) => {
    evento.preventDefault();
    try { await ingresarMaterial({ ...ingreso, insumo: Number(ingreso.insumo), ubicacion: Number(ingreso.ubicacion), cantidad: Number(ingreso.cantidad) }); setIngreso({ insumo: "", codigo_lote: "", ubicacion: "", cantidad: "", elaboracion: "", vencimiento: "" }); await cargar(); }
    catch { setError("No se pudo ingresar: usa Cuarentena si requiere Calidad, o Disponible si no requiere inspección."); }
  };
  const consumirReceta = async () => {
    try { await consumirRecetaProduccion(Number(loteAConsumir)); setLoteAConsumir(""); await cargar(); }
    catch { setError("No se pudo consumir la receta: revisa kilos producidos, receta, Calidad y stock disponible."); }
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

    {puedeBodega && <section className="mt-8 grid gap-8 xl:grid-cols-2">
      <div className="rounded-2xl border border-slate-200 bg-white p-5"><h2 className="font-semibold">1. Crear material</h2><p className="mt-1 text-sm text-slate-500">El código es el ID operativo que relaciona el material con recetas y movimientos.</p><form onSubmit={guardarMaterial} className="mt-4 grid gap-3 sm:grid-cols-2"><input required placeholder="Código / ID" value={nuevoMaterial.codigo} onChange={(e) => setNuevoMaterial({ ...nuevoMaterial, codigo: e.target.value })} className="rounded-xl border px-4 py-3 text-sm"/><input required placeholder="Nombre" value={nuevoMaterial.nombre} onChange={(e) => setNuevoMaterial({ ...nuevoMaterial, nombre: e.target.value })} className="rounded-xl border px-4 py-3 text-sm"/><select value={nuevoMaterial.categoria} onChange={(e) => setNuevoMaterial({ ...nuevoMaterial, categoria: e.target.value })} className="rounded-xl border bg-white px-4 py-3 text-sm">{[["materia_prima","Materia prima"],["empaque","Empaque"],["produccion","Insumo productivo"],["quimico","Químico"],["limpieza","Limpieza"],["repuesto","Repuesto"],["seguridad","Seguridad"],["otro","Otro"]].map(([v,l]) => <option key={v} value={v}>{l}</option>)}</select><select value={nuevoMaterial.unidad} onChange={(e) => setNuevoMaterial({ ...nuevoMaterial, unidad: e.target.value })} className="rounded-xl border bg-white px-4 py-3 text-sm"><option value="kg">kg</option><option value="L">Litros</option><option value="un">Unidades</option></select><label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={nuevoMaterial.requiere_calidad} onChange={(e) => setNuevoMaterial({ ...nuevoMaterial, requiere_calidad: e.target.checked })}/> Requiere Calidad</label><label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={nuevoMaterial.requiere_vencimiento} onChange={(e) => setNuevoMaterial({ ...nuevoMaterial, requiere_vencimiento: e.target.checked })}/> Requiere vencimiento</label><button className="rounded-xl bg-green-700 px-5 py-3 text-sm font-semibold text-white sm:col-span-2">Guardar material</button></form></div>
      <div className="rounded-2xl border border-slate-200 bg-white p-5"><h2 className="font-semibold">2. Ingresar material por lote</h2><p className="mt-1 text-sm text-slate-500">Si requiere Calidad debe ingresar a Cuarentena; quedará disponible solo después de aprobarse.</p><form onSubmit={guardarIngreso} className="mt-4 grid gap-3 sm:grid-cols-2"><select required value={ingreso.insumo} onChange={(e) => setIngreso({ ...ingreso, insumo: e.target.value })} className="rounded-xl border bg-white px-4 py-3 text-sm"><option value="">Material</option>{insumos.map((i) => <option key={i.id} value={i.id}>{i.codigo} · {i.nombre}</option>)}</select><input required placeholder="Lote proveedor" value={ingreso.codigo_lote} onChange={(e) => setIngreso({ ...ingreso, codigo_lote: e.target.value })} className="rounded-xl border px-4 py-3 text-sm"/><select required value={ingreso.ubicacion} onChange={(e) => setIngreso({ ...ingreso, ubicacion: e.target.value })} className="rounded-xl border bg-white px-4 py-3 text-sm"><option value="">Ubicación</option>{ubicaciones.filter((u) => u.activo).map((u) => <option key={u.id} value={u.id}>{u.bodega_nombre}/{u.codigo} · {u.tipo}</option>)}</select><input required type="number" min="0.001" step="0.001" placeholder="Cantidad" value={ingreso.cantidad} onChange={(e) => setIngreso({ ...ingreso, cantidad: e.target.value })} className="rounded-xl border px-4 py-3 text-sm"/><input type="date" title="Elaboración" value={ingreso.elaboracion} onChange={(e) => setIngreso({ ...ingreso, elaboracion: e.target.value })} className="rounded-xl border px-4 py-3 text-sm"/><input type="date" title="Vencimiento" value={ingreso.vencimiento} onChange={(e) => setIngreso({ ...ingreso, vencimiento: e.target.value })} className="rounded-xl border px-4 py-3 text-sm"/><button className="rounded-xl bg-green-700 px-5 py-3 text-sm font-semibold text-white sm:col-span-2">Registrar ingreso</button></form></div>
      {/* La fórmula ya no se edita aquí. Vive en maestros.Receta, que es
          versionada y multinivel, y la escribe Calidad — que es quien
          responde por ella. Que Bodega pudiera cambiarla dejaba que quien
          descuenta el material redefiniera cuánto material lleva. */}
      <div className="rounded-2xl border border-slate-200 bg-white p-5"><h2 className="font-semibold">3. Receta del producto</h2><p className="mt-1 text-sm text-slate-500">La fórmula la mantiene Calidad en el maestro de recetas, versionada por fecha: un lote de mayo se descuenta con la receta de mayo. Aquí solo se consume.</p><p className="mt-3 text-sm text-slate-400">Se edita en el administrador de Django, <span className="font-medium text-slate-600">Maestros › Recetas</span>.</p></div>
      <div className="rounded-2xl border border-slate-200 bg-white p-5"><h2 className="font-semibold">4. Consumir receta por Producción</h2><p className="mt-1 text-sm text-slate-500">Descuenta automáticamente: kg producidos × cantidad por kg, seleccionando lotes FEFO aprobados.</p><div className="mt-4 grid gap-3"><select value={loteAConsumir} onChange={(e) => setLoteAConsumir(e.target.value)} className="rounded-xl border bg-white px-4 py-3 text-sm"><option value="">Lote de Producción</option>{lotesProduccion.filter((l) => l.kg_producidos && l.estado !== "anulado").map((l) => <option key={l.id} value={l.id}>{l.codigo_lote} · {l.producto_nombre} · {l.kg_producidos} kg</option>)}</select><button type="button" disabled={!loteAConsumir} onClick={() => void consumirReceta()} className="rounded-xl bg-blue-700 px-5 py-3 text-sm font-semibold text-white disabled:opacity-40">Registrar consumo completo</button></div></div>
    </section>}

    {puedeBodega && <section className="mt-8 grid gap-8 xl:grid-cols-2">
      <div className="rounded-2xl border border-slate-200 bg-white p-5"><h2 className="font-semibold">Salida, consumo o ajuste</h2><p className="mt-1 text-sm text-slate-500">Las salidas y consumos solo aceptan lotes aprobados y vigentes. Los ajustes quedan pendientes de una segunda aprobación.</p><form onSubmit={registrarOperacion} className="mt-4 grid gap-3">
        <select required value={operacion.existencia} onChange={(e) => setOperacion({ ...operacion, existencia: e.target.value })} className="rounded-xl border border-slate-300 bg-white px-4 py-3 text-sm"><option value="">Existencia y lote</option>{existencias.map((e) => <option key={e.id} value={e.id}>{e.insumo_nombre} · {e.lote_codigo} · disp. {formato(e.cantidad_disponible)}</option>)}</select>
        <div className="grid gap-3 sm:grid-cols-2"><select value={operacion.tipo} onChange={(e) => setOperacion({ ...operacion, tipo: e.target.value })} className="rounded-xl border border-slate-300 bg-white px-4 py-3 text-sm"><option value="consumo">Consumo de material</option><option value="salida">Salida de Bodega</option><option value="positivo">Ajuste positivo</option><option value="negativo">Ajuste negativo</option><option value="merma">Merma</option></select><input required type="number" min="0.001" step="0.001" placeholder="Cantidad" value={operacion.cantidad} onChange={(e) => setOperacion({ ...operacion, cantidad: e.target.value })} className="rounded-xl border border-slate-300 px-4 py-3 text-sm" /></div>
        <textarea required placeholder="Motivo o documento de respaldo" value={operacion.motivo} onChange={(e) => setOperacion({ ...operacion, motivo: e.target.value })} className="rounded-xl border border-slate-300 px-4 py-3 text-sm"/><button className="rounded-xl bg-green-700 px-5 py-3 text-sm font-semibold text-white">Registrar operación</button>
      </form></div>
      <div className="rounded-2xl border border-slate-200 bg-white p-5"><h2 className="font-semibold">Ajustes pendientes</h2><div className="mt-4 space-y-3">{ajustes.filter((a) => a.estado === "pendiente").map((a) => <div key={a.id} className="flex items-center justify-between gap-3 rounded-xl bg-slate-50 p-4"><div><p className="font-medium">{a.tipo} · {formato(a.cantidad)}</p><p className="text-sm text-slate-500">{a.motivo}</p></div><div className="flex gap-2"><button onClick={() => void decidirAjuste(a.id, "aprobar").then(cargar)} className="rounded-lg bg-green-700 px-3 py-2 text-xs font-semibold text-white">Aprobar</button><button onClick={() => void decidirAjuste(a.id, "rechazar").then(cargar)} className="rounded-lg bg-red-50 px-3 py-2 text-xs font-semibold text-red-700">Rechazar</button></div></div>)}{!ajustes.some((a) => a.estado === "pendiente") && <p className="text-sm text-slate-400">Sin ajustes pendientes.</p>}</div></div>
    </section>}

    <section className="mt-8 rounded-2xl border border-slate-200 bg-white"><div className="border-b p-5"><h2 className="font-semibold">Últimos movimientos</h2></div><div className="overflow-x-auto"><table className="w-full text-left text-sm"><thead className="bg-slate-50 text-slate-500"><tr><th className="px-5 py-3">Tipo</th><th className="px-5 py-3">Material</th><th className="px-5 py-3">Lote</th><th className="px-5 py-3">Cantidad</th><th className="px-5 py-3">Motivo</th></tr></thead><tbody>{movimientos.slice(0, 15).map((m) => <tr key={m.id} className="border-t"><td className="px-5 py-3">{m.tipo}</td><td className="px-5 py-3 font-medium">{m.insumo_nombre}</td><td className="px-5 py-3">{m.lote_codigo}</td><td className="px-5 py-3">{formato(m.cantidad)}</td><td className="px-5 py-3 text-slate-500">{m.motivo || "—"}</td></tr>)}</tbody></table></div></section>

    <section className="mt-8 grid gap-8 xl:grid-cols-2">
      <div className="rounded-2xl border border-slate-200 bg-white"><div className="border-b p-5"><h2 className="font-semibold">Calidad de materiales</h2></div><div className="divide-y">{inspecciones.slice(0, 8).map((i) => <div key={i.id} className="p-5"><div className="flex justify-between gap-4"><div><p className="font-medium">{i.insumo_nombre} · {i.lote_codigo}</p><p className="mt-1 text-sm text-slate-500">Estado: {i.estado}</p></div>{puedeCalidad && !["aprobada", "observada", "rechazada", "bloqueada"].includes(i.estado) && <div className="flex gap-2"><button onClick={() => void decidirInspeccion(i.id, "aprobada").then(cargar)} className="rounded-lg bg-green-700 px-3 py-2 text-xs font-semibold text-white">Aprobar</button><button onClick={() => void decidirInspeccion(i.id, "rechazada", "Rechazo desde bandeja").then(cargar)} className="rounded-lg bg-red-50 px-3 py-2 text-xs font-semibold text-red-700">Rechazar</button></div>}</div></div>)}{inspecciones.length === 0 && <p className="p-5 text-sm text-slate-400">Sin inspecciones.</p>}</div></div>
      <div className="rounded-2xl border border-slate-200 bg-white"><div className="border-b p-5"><h2 className="font-semibold">Solicitudes de materiales</h2></div><div className="divide-y">{mrq.slice(0, 8).map((m) => <div key={m.id} className="flex items-center justify-between gap-4 p-5"><div><p className="font-medium">{m.numero}</p><p className="mt-1 text-sm text-slate-500">{m.area} · {m.estado} · requerida {m.fecha_requerida}</p></div>{puedeBodega && ["enviada", "aprobada"].includes(m.estado) && <button onClick={() => void reservarMRQ(m.id).then(cargar)} className="rounded-lg bg-green-700 px-3 py-2 text-xs font-semibold text-white">Reservar FEFO</button>}{puedeBodega && ["preparada", "parcial"].includes(m.estado) && <button onClick={() => void entregarMRQ(m.id).then(cargar)} className="rounded-lg bg-blue-700 px-3 py-2 text-xs font-semibold text-white">Entregar</button>}</div>)}{mrq.length === 0 && <p className="p-5 text-sm text-slate-400">Sin solicitudes.</p>}</div></div>
    </section>

    {area !== "bodega" && <section className="mt-8 rounded-2xl border border-slate-200 bg-white p-5"><h2 className="font-semibold">Solicitar material a Bodega</h2><form onSubmit={solicitarMaterial} className="mt-4 grid gap-3 md:grid-cols-4"><select required value={nuevaMrq.insumo} onChange={(e) => setNuevaMrq({ ...nuevaMrq, insumo: e.target.value })} className="rounded-xl border border-slate-300 bg-white px-4 py-3 text-sm"><option value="">Material</option>{insumos.map((i) => <option key={i.id} value={i.id}>{i.nombre}</option>)}</select><input required type="number" min="0.001" step="0.001" placeholder="Cantidad" value={nuevaMrq.cantidad} onChange={(e) => setNuevaMrq({ ...nuevaMrq, cantidad: e.target.value })} className="rounded-xl border border-slate-300 px-4 py-3 text-sm"/><input required type="date" value={nuevaMrq.fecha} onChange={(e) => setNuevaMrq({ ...nuevaMrq, fecha: e.target.value })} className="rounded-xl border border-slate-300 px-4 py-3 text-sm"/><button className="rounded-xl bg-green-700 px-5 py-3 text-sm font-semibold text-white">Enviar MRQ</button></form></section>}

    <section className="mt-8 grid gap-8 xl:grid-cols-2"><div className="rounded-2xl border border-slate-200 bg-white p-5"><div className="flex items-center gap-2"><ShoppingCart className="h-5 w-5 text-green-700"/><h2 className="font-semibold">Órdenes de compra</h2></div><div className="mt-4 space-y-3">{ordenes.slice(0, 6).map((o) => <div key={o.id} className="rounded-xl bg-slate-50 p-4"><p className="font-medium">{o.numero} · {o.proveedor_nombre}</p><p className="text-sm text-slate-500">{o.estado} · {o.detalles.length} materiales</p></div>)}</div></div><div className="rounded-2xl border border-slate-200 bg-white p-5"><h2 className="font-semibold">Notificaciones</h2><div className="mt-4 space-y-3">{notificaciones.slice(0, 6).map((n) => <div key={n.id} className="rounded-xl bg-slate-50 p-4"><p className="font-medium">{n.titulo}</p><p className="mt-1 text-sm text-slate-500">{n.mensaje}</p></div>)}{notificaciones.length === 0 && <p className="text-sm text-slate-400">Sin notificaciones.</p>}</div></div></section>
  </div></div>;
}

export default Abastecimiento;
