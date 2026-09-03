import { useCallback, useEffect, useMemo, useState } from "react";
import { Boxes, PackageCheck, RefreshCw } from "lucide-react";

import {
  kilos, obtenerMaterialesEnvasables, obtenerPallets, obtenerRegistrosEnvase,
  type MaterialEnvasable, type PalletProducto, type RegistroEnvaseCreado,
} from "../../services/produccion.service";
import { puedeEscribir } from "../../services/sesion";
import FormularioEnvase from "../Produccion/FormularioEnvase";

const numero = new Intl.NumberFormat("es-CL", { maximumFractionDigits: 0 });

export default function Envasado() {
  const [materiales, setMateriales] = useState<MaterialEnvasable[]>([]);
  const [pallets, setPallets] = useState<PalletProducto[]>([]);
  const [registros, setRegistros] = useState<RegistroEnvaseCreado[]>([]);
  const [seleccionado, setSeleccionado] = useState<number | null>(null);
  const [cargando, setCargando] = useState(true);
  const [error, setError] = useState("");
  const puedeEnvasar = puedeEscribir("envasado");

  const cargar = useCallback(async () => {
    setCargando(true); setError("");
    try {
      const [habilitados, paginaRegistros, paginaPallets] = await Promise.all([
        obtenerMaterialesEnvasables(),
        obtenerRegistrosEnvase(), obtenerPallets(),
      ]);
      setMateriales(habilitados);
      setRegistros(paginaRegistros.results);
      setPallets(paginaPallets.results);
    } catch {
      setError("No se pudo cargar la bandeja de Envasado.");
    } finally { setCargando(false); }
  }, []);

  useEffect(() => {
    const pendiente = setTimeout(() => void cargar(), 0);
    return () => clearTimeout(pendiente);
  }, [cargar]);
  const lote = materiales.find((item) => item.lote_id === seleccionado) ?? null;
  const palletPorLote = useMemo(() => {
    const conteo = new Map<string, number>();
    pallets.forEach((pallet) => conteo.set(pallet.lote_codigo ?? "", (conteo.get(pallet.lote_codigo ?? "") ?? 0) + 1));
    return conteo;
  }, [pallets]);

  return <main className="px-6 py-8 lg:px-10"><div className="mx-auto max-w-7xl space-y-7">
    <header className="flex flex-wrap items-start justify-between gap-4">
      <div><p className="text-sm font-bold uppercase tracking-wider text-emerald-700">Área de Envase</p><h1 className="mt-2 text-3xl font-bold text-slate-900">Envasado y pallets</h1><p className="mt-2 max-w-3xl text-slate-600">Recibe solamente materiales liberados, aplica el formato configurado y crea pallets físicos en cuarentena para Calidad final.</p></div>
      <button type="button" onClick={() => void cargar()} disabled={cargando} className="flex items-center gap-2 rounded-xl border border-slate-300 px-4 py-2.5 text-sm font-semibold text-slate-700 disabled:opacity-50"><RefreshCw className={`h-4 w-4 ${cargando ? "animate-spin" : ""}`} />Actualizar</button>
    </header>
    <section className="grid gap-3 rounded-2xl border border-slate-200 bg-slate-50 p-4 text-sm text-slate-700 md:grid-cols-4">
      <div><b>1. Calidad intermedia</b><br />Libera el material a granel.</div><div><b>2. Envasado</b><br />Envase selecciona lote y máquina.</div><div><b>3. Pallet</b><br />Respeta formato y máximo configurados.</div><div><b>4. Calidad final</b><br />Libera antes de ingresar a Bodega.</div>
    </section>
    {error && <p className="rounded-xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700">{error}</p>}
    <section className="grid items-start gap-6 lg:grid-cols-[1.15fr_.85fr]">
      <div className="overflow-hidden rounded-2xl border border-slate-200 bg-white">
        <div className="border-b border-slate-200 px-5 py-4"><h2 className="font-bold text-slate-900">Lotes disponibles para envasar</h2><p className="mt-1 text-xs text-slate-500">La selección conserva el mismo lote maestro y toda su trazabilidad.</p></div>
        {materiales.length === 0 && !cargando ? <p className="p-8 text-center text-sm text-slate-500">No hay material liberado y con formato válido para envasar.</p> : <div className="divide-y divide-slate-100">{materiales.map((item) => <button key={item.salida_id} type="button" onClick={() => setSeleccionado(item.lote_id)} className={`flex w-full items-center justify-between gap-4 px-5 py-4 text-left hover:bg-slate-50 ${seleccionado === item.lote_id ? "bg-emerald-50" : ""}`}><div><p className="font-semibold text-slate-900">{item.lote_codigo} · {item.producto_nombre}</p><p className="mt-1 text-xs text-slate-500">{kilos(item.cantidad_disponible)} · {item.formato_nombre} · Calidad liberada</p></div><span className="rounded-full bg-slate-100 px-2.5 py-1 text-xs font-bold text-slate-700">{palletPorLote.get(item.lote_codigo) ?? 0} pallet(s)</span></button>)}</div>}
      </div>
      <div className="space-y-4">
        {!lote ? <div className="rounded-2xl border border-dashed border-slate-300 bg-white p-8 text-center"><PackageCheck className="mx-auto h-9 w-9 text-slate-400" /><p className="mt-3 text-sm text-slate-600">Selecciona un material liberado.</p></div> : <section className="rounded-2xl border border-slate-200 bg-white p-5"><h2 className="font-bold text-slate-900">{lote.lote_codigo}</h2><p className="mt-1 text-sm text-slate-600">{lote.producto_nombre} · {kilos(lote.cantidad_disponible)} · {lote.formato_nombre}</p>{puedeEnvasar ? <div className="mt-5"><FormularioEnvase key={lote.salida_id} loteId={lote.lote_id} formatoKg={Number(lote.formato_kg)} formatoNombre={lote.formato_nombre} maximoPalletKg={Number(lote.maximo_pallet_kg)} alGuardar={() => void cargar()} /></div> : <p className="mt-5 rounded-xl bg-slate-100 px-4 py-3 text-sm text-slate-600">Acceso de seguimiento: solamente Envase puede crear pallets.</p>}</section>}
      </div>
    </section>
    <section className="overflow-hidden rounded-2xl border border-slate-200 bg-white"><div className="flex items-center gap-3 border-b border-slate-200 px-5 py-4"><Boxes className="h-5 w-5 text-emerald-700" /><div><h2 className="font-bold text-slate-900">Historial reciente de envasado</h2><p className="text-xs text-slate-500">Operador, período, controles y pallets del cierre físico.</p></div></div>{registros.length === 0 ? <p className="p-8 text-center text-sm text-slate-500">Todavía no hay registros de envase.</p> : <div className="grid gap-3 p-4 lg:grid-cols-2">{registros.map((item) => <article key={item.id} className="rounded-xl border border-slate-200 p-4"><div className="flex items-start justify-between gap-3"><div><p className="font-semibold text-slate-900">{item.lote_codigo ?? item.lote}</p><p className="text-xs text-slate-500">{item.equipo_nombre ?? "Sin equipo"} · {item.operador_nombre || `operador #${item.operador}`}</p></div><b>{numero.format(Number(item.kg_envasados))} kg</b></div><p className="mt-2 text-xs text-slate-600">{new Date(item.inicio).toLocaleString("es-CL")} → {new Date(item.termino).toLocaleString("es-CL")} · {numero.format(item.unidades)} envases</p><div className="mt-3 flex flex-wrap gap-1.5">{Object.entries(item.controles ?? {}).map(([clave, valor]) => <span key={clave} className={`rounded-full px-2 py-1 text-xs ${valor === "conforme" ? "bg-emerald-50 text-emerald-800" : "bg-amber-50 text-amber-800"}`}>{clave.replaceAll("_", " ")}: {String(valor).replaceAll("_", " ")}</span>)}</div>{item.observacion && <p className="mt-3 rounded-lg bg-slate-50 p-2 text-xs text-slate-600">{item.observacion}</p>}<div className="mt-3 text-xs text-slate-500">{item.pallets.map((pallet) => `${pallet.codigo} · ${pallet.kg_neto} kg · ${pallet.estado_etiqueta}`).join(" | ")}</div></article>)}</div>}</section>
  </div></main>;
}
