import { useCallback, useEffect, useMemo, useState } from "react";
import { Boxes, PackageCheck, RefreshCw } from "lucide-react";

import {
  buscarLotes, kilos, obtenerPallets, obtenerRegistrosEnvase,
  type Lote, type PalletProducto, type RegistroEnvaseCreado,
} from "../../services/produccion.service";
import { puedeEscribir } from "../../services/sesion";
import FormularioEnvase from "../Produccion/FormularioEnvase";

const numero = new Intl.NumberFormat("es-CL", { maximumFractionDigits: 0 });

export default function Envasado() {
  const [lotes, setLotes] = useState<Lote[]>([]);
  const [pallets, setPallets] = useState<PalletProducto[]>([]);
  const [registros, setRegistros] = useState<RegistroEnvaseCreado[]>([]);
  const [seleccionado, setSeleccionado] = useState<number | null>(null);
  const [cargando, setCargando] = useState(true);
  const [error, setError] = useState("");
  const puedeEnvasar = puedeEscribir("envasado");

  const cargar = useCallback(async () => {
    setCargando(true); setError("");
    try {
      const [producidos, cerrados, paginaRegistros, paginaPallets] = await Promise.all([
        buscarLotes({ estado: "producido" }), buscarLotes({ estado: "cerrado" }),
        obtenerRegistrosEnvase(), obtenerPallets(),
      ]);
      setLotes([...producidos.results, ...cerrados.results]);
      setRegistros(paginaRegistros.results);
      setPallets(paginaPallets.results);
    } catch {
      setError("No se pudo cargar la bandeja de Envasado.");
    } finally { setCargando(false); }
  }, []);

  useEffect(() => { void cargar(); }, [cargar]);
  const lote = lotes.find((item) => item.id === seleccionado) ?? null;
  const palletPorLote = useMemo(() => {
    const conteo = new Map<string, number>();
    pallets.forEach((pallet) => conteo.set(pallet.lote_codigo ?? "", (conteo.get(pallet.lote_codigo ?? "") ?? 0) + 1));
    return conteo;
  }, [pallets]);

  return <main className="px-6 py-8 lg:px-10"><div className="mx-auto max-w-7xl space-y-7">
    <header className="flex flex-wrap items-start justify-between gap-4">
      <div><p className="text-sm font-bold uppercase tracking-wider text-emerald-700">Área de Envase</p><h1 className="mt-2 text-3xl font-bold text-slate-900">Envasado y pallets</h1><p className="mt-2 max-w-3xl text-slate-600">Recibe lotes producidos, registra sacos de 25 kg y crea pallets físicos en cuarentena para Calidad.</p></div>
      <button type="button" onClick={() => void cargar()} disabled={cargando} className="flex items-center gap-2 rounded-xl border border-slate-300 px-4 py-2.5 text-sm font-semibold text-slate-700 disabled:opacity-50"><RefreshCw className={`h-4 w-4 ${cargando ? "animate-spin" : ""}`} />Actualizar</button>
    </header>
    <section className="grid gap-3 rounded-2xl border border-slate-200 bg-slate-50 p-4 text-sm text-slate-700 md:grid-cols-4">
      <div><b>1. Lote producido</b><br />Producción declara sus kilos.</div><div><b>2. Envasado</b><br />Envase selecciona lote y máquina.</div><div><b>3. Pallet</b><br />Máximo 20 sacos · 500 kg.</div><div><b>4. Calidad</b><br />Libera antes de ingresar a Bodega.</div>
    </section>
    {error && <p className="rounded-xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700">{error}</p>}
    <section className="grid items-start gap-6 lg:grid-cols-[1.15fr_.85fr]">
      <div className="overflow-hidden rounded-2xl border border-slate-200 bg-white">
        <div className="border-b border-slate-200 px-5 py-4"><h2 className="font-bold text-slate-900">Lotes disponibles para envasar</h2><p className="mt-1 text-xs text-slate-500">La selección conserva el mismo lote maestro y toda su trazabilidad.</p></div>
        {lotes.length === 0 && !cargando ? <p className="p-8 text-center text-sm text-slate-500">No hay lotes producidos pendientes de trabajo.</p> : <div className="divide-y divide-slate-100">{lotes.map((item) => <button key={item.id} type="button" onClick={() => setSeleccionado(item.id)} className={`flex w-full items-center justify-between gap-4 px-5 py-4 text-left hover:bg-slate-50 ${seleccionado === item.id ? "bg-emerald-50" : ""}`}><div><p className="font-semibold text-slate-900">{item.codigo_lote} · {item.producto_nombre}</p><p className="mt-1 text-xs text-slate-500">{kilos(item.kg_producidos)} · {item.equipo_nombre ?? "sin equipo"}</p></div><span className="rounded-full bg-slate-100 px-2.5 py-1 text-xs font-bold text-slate-700">{palletPorLote.get(item.codigo_lote) ?? 0} pallet(s)</span></button>)}</div>}
      </div>
      <div className="space-y-4">
        {!lote ? <div className="rounded-2xl border border-dashed border-slate-300 bg-white p-8 text-center"><PackageCheck className="mx-auto h-9 w-9 text-slate-400" /><p className="mt-3 text-sm text-slate-600">Selecciona un lote producido.</p></div> : <section className="rounded-2xl border border-slate-200 bg-white p-5"><h2 className="font-bold text-slate-900">{lote.codigo_lote}</h2><p className="mt-1 text-sm text-slate-600">{lote.producto_nombre} · {kilos(lote.kg_producidos)}</p>{puedeEnvasar ? <div className="mt-5"><FormularioEnvase loteId={lote.id} alGuardar={() => void cargar()} /></div> : <p className="mt-5 rounded-xl bg-slate-100 px-4 py-3 text-sm text-slate-600">Acceso de seguimiento: solamente Envase puede crear pallets.</p>}</section>}
      </div>
    </section>
    <section className="overflow-hidden rounded-2xl border border-slate-200 bg-white"><div className="flex items-center gap-3 border-b border-slate-200 px-5 py-4"><Boxes className="h-5 w-5 text-emerald-700" /><div><h2 className="font-bold text-slate-900">Historial reciente de envasado</h2><p className="text-xs text-slate-500">Registros y pallets creados, sin duplicar información de Inventario.</p></div></div>{registros.length === 0 ? <p className="p-8 text-center text-sm text-slate-500">Todavía no hay registros de envase.</p> : <div className="overflow-x-auto"><table className="w-full min-w-[720px] text-left text-sm"><thead className="bg-slate-50 text-xs uppercase text-slate-500"><tr><th className="px-5 py-3">Lote</th><th className="px-5 py-3">Equipo</th><th className="px-5 py-3">Unidades</th><th className="px-5 py-3">Kg</th><th className="px-5 py-3">Pallets</th></tr></thead><tbody>{registros.map((item) => <tr key={item.id} className="border-t border-slate-100"><td className="px-5 py-4 font-semibold">{item.lote_codigo ?? item.lote}</td><td className="px-5 py-4">{item.equipo_nombre ?? "—"}</td><td className="px-5 py-4">{numero.format(item.unidades)}</td><td className="px-5 py-4">{numero.format(Number(item.kg_envasados))} kg</td><td className="px-5 py-4">{item.pallets.length}</td></tr>)}</tbody></table></div>}</section>
  </div></main>;
}
