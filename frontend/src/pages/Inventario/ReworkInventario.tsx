import { useEffect, useMemo, useState } from "react";
import { CheckCircle2, PackageOpen, RefreshCw, ShieldAlert, Trash2 } from "lucide-react";

import {
  habilitarRework, obtenerReworkInventario, obtenerUbicaciones,
  type UbicacionInventario, type UnidadRework,
} from "../../services/inventario.service";
import { esAdministradorGlobal } from "../../services/access-control";
import { obtenerSesion } from "../../services/sesion";

type Bandeja = "aprobado" | "bloqueado" | "consumido" | "destruido";
const numero = new Intl.NumberFormat("es-CL", { maximumFractionDigits: 3 });

function detalleError(error: unknown) {
  const data = (error as { response?: { data?: unknown } }).response?.data;
  if (typeof data === "string") return data;
  if (data && typeof data === "object") {
    const valor = (data as { detail?: unknown; error?: unknown }).detail
      ?? (data as { error?: unknown }).error;
    if (Array.isArray(valor)) return valor.join(" ");
    if (typeof valor === "string") return valor;
  }
  return "No se pudo completar el movimiento de rework.";
}

export default function ReworkInventario() {
  const usuario = obtenerSesion()?.usuario;
  const puedeMover = Boolean(
    usuario && (esAdministradorGlobal(usuario) || usuario.perfil?.area === "bodega"),
  );
  const [unidades, setUnidades] = useState<UnidadRework[] | null>(null);
  const [ubicaciones, setUbicaciones] = useState<UbicacionInventario[]>([]);
  const [bandeja, setBandeja] = useState<Bandeja>("aprobado");
  const [seleccionada, setSeleccionada] = useState<UnidadRework | null>(null);
  const [destino, setDestino] = useState(0);
  const [cargando, setCargando] = useState(true);
  const [guardando, setGuardando] = useState(false);
  const [error, setError] = useState("");
  const [mensaje, setMensaje] = useState("");

  async function cargar() {
    setCargando(true); setError("");
    try {
      const [rework, lugares] = await Promise.all([
        obtenerReworkInventario(), obtenerUbicaciones(),
      ]);
      setUnidades(rework);
      setUbicaciones(lugares.filter((item) => item.activo && item.tipo === "disponible"));
    } catch {
      setError("No se pudo cargar la existencia física de rework.");
    } finally { setCargando(false); }
  }

  useEffect(() => {
    let vigente = true;
    void Promise.all([obtenerReworkInventario(), obtenerUbicaciones()])
      .then(([rework, lugares]) => {
        if (!vigente) return;
        setUnidades(rework);
        setUbicaciones(lugares.filter((item) => item.activo && item.tipo === "disponible"));
      })
      .catch(() => { if (vigente) setError("No se pudo cargar la existencia física de rework."); })
      .finally(() => { if (vigente) setCargando(false); });
    return () => { vigente = false; };
  }, []);

  const agrupadas = useMemo(() => ({
    aprobado: (unidades ?? []).filter((item) => ["pendiente_ubicacion", "disponible"].includes(item.estado)),
    bloqueado: (unidades ?? []).filter((item) => item.estado === "bloqueado"),
    consumido: (unidades ?? []).filter((item) => item.estado === "consumido"),
    destruido: (unidades ?? []).filter((item) => item.estado === "destruido"),
  }), [unidades]);

  function prepararIngreso(unidad: UnidadRework) {
    setSeleccionada(unidad);
    setDestino(ubicaciones[0]?.id ?? 0);
    setError(""); setMensaje("");
  }

  async function confirmarIngreso(evento: React.FormEvent) {
    evento.preventDefault();
    if (!seleccionada || !destino || guardando) return;
    setGuardando(true); setError("");
    try {
      const actualizada = await habilitarRework(
        seleccionada.id, destino, crypto.randomUUID(),
      );
      setUnidades((actuales) => actuales?.map((item) => (
        item.id === actualizada.id ? actualizada : item
      )) ?? null);
      setMensaje(`${actualizada.codigo} quedó disponible para Producción.`);
      setSeleccionada(null);
    } catch (peticion) { setError(detalleError(peticion)); }
    finally { setGuardando(false); }
  }

  const etiquetas: Array<[Bandeja, string]> = [
    ["aprobado", "Aprobado"], ["bloqueado", "Bloqueado"],
    ["consumido", "Consumido"], ["destruido", "Destruido"],
  ];
  const iconos = { aprobado: CheckCircle2, bloqueado: ShieldAlert, consumido: PackageOpen, destruido: Trash2 };
  const Icono = iconos[bandeja];

  return <section className="space-y-4">
    <header className="flex flex-wrap items-start justify-between gap-3 rounded-2xl border border-slate-200 bg-white p-5">
      <div><h2 className="text-lg font-bold text-slate-900">Existencia física de rework</h2><p className="mt-1 text-sm text-slate-600">Calidad decide; Bodega confirma la zona liberada; Producción consume el saldo de esta unidad.</p></div>
      <button type="button" onClick={() => void cargar()} disabled={cargando} className="inline-flex items-center gap-2 rounded-xl border border-slate-300 px-3 py-2 text-sm font-semibold text-slate-700 disabled:opacity-50"><RefreshCw className={`h-4 w-4 ${cargando ? "animate-spin" : ""}`} />Actualizar</button>
    </header>
    {error && <p className="rounded-xl bg-rose-50 px-4 py-3 text-sm text-rose-700">{error}</p>}
    {mensaje && <p className="rounded-xl bg-emerald-50 px-4 py-3 text-sm text-emerald-800">{mensaje}</p>}
    <nav className="grid grid-cols-2 gap-2 rounded-2xl border border-slate-200 bg-white p-2 md:grid-cols-4" aria-label="Estados de rework">
      {etiquetas.map(([id, texto]) => <button key={id} type="button" onClick={() => setBandeja(id)} className={`rounded-xl px-3 py-2 text-sm font-semibold ${bandeja === id ? "bg-amber-700 text-white" : "text-slate-600 hover:bg-slate-100"}`}>{texto} <span className="ml-1 tabular-nums">{agrupadas[id].length}</span></button>)}
    </nav>
    {cargando && unidades === null ? <div className="h-36 animate-pulse rounded-2xl bg-slate-200" /> : <div className="grid gap-3 lg:grid-cols-2">
      {agrupadas[bandeja].map((item) => <article key={item.id} className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
        <div className="flex items-start justify-between gap-3"><div className="flex gap-3"><span className="rounded-xl bg-slate-100 p-2 text-slate-600"><Icono className="h-5 w-5" /></span><div><h3 className="font-bold text-slate-900">{item.codigo} · {item.producto_nombre}</h3><p className="text-xs text-slate-500">Lote {item.lote_codigo} · {item.origen_rework.replaceAll("_", " ")}</p></div></div><span className="rounded-full bg-slate-100 px-2.5 py-1 text-xs font-bold text-slate-700">{item.estado_etiqueta}</span></div>
        <div className="mt-4 grid grid-cols-3 gap-3 text-sm"><div><p className="text-xs text-slate-500">Inicial</p><b>{numero.format(Number(item.cantidad_inicial_kg))} kg</b></div><div><p className="text-xs text-slate-500">Disponible</p><b className="text-emerald-700">{numero.format(Number(item.cantidad_disponible_kg))} kg</b></div><div><p className="text-xs text-slate-500">Ubicación</p><b>{item.ubicacion_codigo}</b></div></div>
        {item.estado === "pendiente_ubicacion" && <div className="mt-4 flex flex-wrap items-center justify-between gap-2 rounded-xl bg-amber-50 p-3"><p className="text-xs font-medium text-amber-800">Aprobado por Calidad; aún no utilizable hasta que Bodega confirme ubicación.</p>{puedeMover && <button type="button" onClick={() => prepararIngreso(item)} className="rounded-lg bg-amber-700 px-3 py-2 text-xs font-bold text-white">Ingresar a zona liberada</button>}</div>}
        {item.estado === "disponible" && <p className="mt-4 rounded-xl bg-emerald-50 px-3 py-2 text-xs font-semibold text-emerald-800">Disponible para selección en Producción.</p>}
      </article>)}
      {agrupadas[bandeja].length === 0 && <p className="rounded-2xl border border-dashed border-slate-300 bg-white p-8 text-center text-sm text-slate-500 lg:col-span-2">No hay unidades en esta bandeja.</p>}
    </div>}
    {seleccionada && <form onSubmit={confirmarIngreso} className="rounded-2xl border border-amber-200 bg-amber-50 p-5"><h3 className="font-bold text-amber-950">Ingresar {seleccionada.codigo}</h3><p className="mt-1 text-xs text-amber-800">Elige una ubicación disponible de la misma planta. Esta acción habilita el consumo en Producción.</p><div className="mt-4 flex flex-wrap gap-3"><select required value={destino} onChange={(evento) => setDestino(Number(evento.target.value))} className="min-w-64 rounded-xl border border-amber-300 bg-white px-3 py-2 text-sm"><option value={0}>Seleccionar ubicación…</option>{ubicaciones.map((item) => <option key={item.id} value={item.id}>{item.bodega_nombre} / {item.codigo}</option>)}</select><button type="button" onClick={() => setSeleccionada(null)} className="px-3 py-2 text-sm text-slate-600">Cancelar</button><button disabled={guardando || !destino} className="rounded-xl bg-amber-700 px-4 py-2 text-sm font-bold text-white disabled:opacity-50">{guardando ? "Confirmando…" : "Confirmar ingreso"}</button></div></form>}
  </section>;
}
