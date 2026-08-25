import { useCallback, useEffect, useState } from "react";
import {
  AlertTriangle, ChevronLeft, ChevronRight, Clock3,
  Download, Droplets, FileSpreadsheet, Scale, Truck, type LucideIcon,
} from "lucide-react";

import {
  descargarResumenRecepcion,
  resumenDiarioRecepcion,
  type PeriodoResumenRecepcion,
  type ResumenDiarioRecepcion,
} from "../../services/recepcion.service";


const fechaLocal = (fecha = new Date()) => {
  const desfase = fecha.getTimezoneOffset() * 60_000;
  return new Date(fecha.getTime() - desfase).toISOString().slice(0, 10);
};

const numero = new Intl.NumberFormat("es-CL", { maximumFractionDigits: 2 });
const fechaVisible = new Intl.DateTimeFormat("es-CL", {
  day: "2-digit", month: "short", year: "numeric", timeZone: "UTC",
});

function moverDia(valor: string, dias: number) {
  const fecha = new Date(`${valor}T12:00:00`);
  fecha.setDate(fecha.getDate() + dias);
  return fechaLocal(fecha);
}

function descargar(contenido: Blob, nombre: string) {
  const url = URL.createObjectURL(contenido);
  const enlace = document.createElement("a");
  enlace.href = url;
  enlace.download = nombre;
  enlace.click();
  URL.revokeObjectURL(url);
}

function Indicador({ icono: Icono, etiqueta, valor, detalle }: {
  icono: LucideIcon; etiqueta: string; valor: string; detalle: string;
}) {
  return (
    <div className="rounded-2xl border border-slate-200 bg-white p-5">
      <div className="flex items-start justify-between gap-4">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.12em] text-slate-600">{etiqueta}</p>
          <p className="mt-2 text-2xl font-semibold tabular-nums text-slate-950">{valor}</p>
          <p className="mt-1 text-xs text-slate-600">{detalle}</p>
        </div>
        <span className="rounded-xl bg-emerald-50 p-2.5 text-emerald-700"><Icono className="h-5 w-5" /></span>
      </div>
    </div>
  );
}

function ReporteDiario() {
  const [modo, setModo] = useState<"dia" | "rango">("dia");
  const [fecha, setFecha] = useState(fechaLocal());
  const [desde, setDesde] = useState(fechaLocal());
  const [hasta, setHasta] = useState(fechaLocal());
  const [resumen, setResumen] = useState<ResumenDiarioRecepcion | null>(null);
  const [cargando, setCargando] = useState(true);
  const [exportando, setExportando] = useState(false);
  const [error, setError] = useState("");

  const periodo: PeriodoResumenRecepcion = modo === "dia" ? { fecha } : { desde, hasta };

  const cargar = useCallback(async () => {
    if (modo === "rango" && desde > hasta) {
      setResumen(null);
      setError("La fecha desde no puede ser posterior a la fecha hasta.");
      setCargando(false);
      return;
    }
    setCargando(true);
    setError("");
    try {
      setResumen(await resumenDiarioRecepcion(
        modo === "dia" ? { fecha } : { desde, hasta },
      ));
    } catch {
      setResumen(null);
      setError("No se pudo cargar el reporte. Revisa la conexión e inténtalo nuevamente.");
    } finally {
      setCargando(false);
    }
  }, [modo, fecha, desde, hasta]);

  useEffect(() => {
    const temporizador = window.setTimeout(() => { void cargar(); }, 0);
    return () => window.clearTimeout(temporizador);
  }, [cargar]);

  const exportar = async (formato: "csv" | "xlsx") => {
    setExportando(true);
    setError("");
    try {
      const archivo = await descargarResumenRecepcion(periodo, formato);
      descargar(archivo.contenido, archivo.nombre);
    } catch {
      setError(`No se pudo descargar el archivo ${formato.toUpperCase()}.`);
    } finally {
      setExportando(false);
    }
  };

  const detalle = resumen?.detalle ?? [];
  const tituloPeriodo = resumen
    ? resumen.fecha
      ? fechaVisible.format(new Date(`${resumen.fecha}T00:00:00Z`))
      : `${fechaVisible.format(new Date(`${resumen.desde}T00:00:00Z`))} – ${fechaVisible.format(new Date(`${resumen.hasta}T00:00:00Z`))}`
    : "";

  return (
    <div className="space-y-6">
      <section className="rounded-2xl border border-slate-200 bg-white p-5">
        <div className="flex flex-wrap items-end justify-between gap-4">
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.12em] text-emerald-700">Cierre de recepción</p>
            <h2 className="mt-1 text-xl font-semibold text-slate-950">Reporte de camiones</h2>
            {tituloPeriodo && <p className="mt-1 text-sm text-slate-600">{tituloPeriodo}</p>}
          </div>

          <div className="flex flex-wrap items-end gap-2">
            <label className="text-xs font-semibold text-slate-700">
              Período
              <select value={modo} onChange={(e) => setModo(e.target.value as "dia" | "rango")} className="mt-1 block h-10 rounded-xl border border-slate-300 bg-white px-3 text-sm">
                <option value="dia">Un día</option>
                <option value="rango">Rango</option>
              </select>
            </label>
            {modo === "dia" ? (
              <div className="flex items-center gap-1">
                <button type="button" onClick={() => setFecha(moverDia(fecha, -1))} className="h-10 rounded-xl border border-slate-300 px-3 text-slate-700 hover:bg-slate-50" aria-label="Día anterior"><ChevronLeft className="h-4 w-4" /></button>
                <label className="text-xs font-semibold text-slate-700">Fecha<input type="date" value={fecha} onChange={(e) => setFecha(e.target.value)} className="mt-1 block h-10 rounded-xl border border-slate-300 px-3 text-sm" /></label>
                <button type="button" onClick={() => setFecha(moverDia(fecha, 1))} className="h-10 rounded-xl border border-slate-300 px-3 text-slate-700 hover:bg-slate-50" aria-label="Día siguiente"><ChevronRight className="h-4 w-4" /></button>
              </div>
            ) : (
              <>
                <label className="text-xs font-semibold text-slate-700">Desde<input type="date" value={desde} onChange={(e) => setDesde(e.target.value)} className="mt-1 block h-10 rounded-xl border border-slate-300 px-3 text-sm" /></label>
                <label className="text-xs font-semibold text-slate-700">Hasta<input type="date" value={hasta} onChange={(e) => setHasta(e.target.value)} className="mt-1 block h-10 rounded-xl border border-slate-300 px-3 text-sm" /></label>
              </>
            )}
            <button type="button" disabled={exportando || !resumen} onClick={() => void exportar("csv")} className="inline-flex h-10 items-center gap-2 rounded-xl border border-slate-300 px-4 text-sm font-semibold text-slate-700 hover:bg-slate-50 disabled:opacity-50"><Download className="h-4 w-4" />CSV</button>
            <button type="button" disabled={exportando || !resumen} onClick={() => void exportar("xlsx")} className="inline-flex h-10 items-center gap-2 rounded-xl bg-emerald-700 px-4 text-sm font-semibold text-white hover:bg-emerald-800 disabled:opacity-50"><FileSpreadsheet className="h-4 w-4" />Excel</button>
          </div>
        </div>
      </section>

      {error && <div role="alert" className="rounded-2xl border border-rose-200 bg-rose-50 px-5 py-4 text-sm text-rose-800">{error}</div>}
      {cargando && <div className="rounded-2xl border border-slate-200 bg-white p-8 text-center text-sm text-slate-600">Cargando reporte…</div>}

      {!cargando && resumen && (
        <>
          <section className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
            <Indicador icono={Truck} etiqueta="Camiones" valor={numero.format(resumen.camiones)} detalle="recepciones del período" />
            <Indicador icono={Droplets} etiqueta="Volumen" valor={`${numero.format(Number(resumen.litros))} L`} detalle={`${numero.format(Number(resumen.kg_guia))} kg de guía`} />
            <Indicador icono={Scale} etiqueta="Romana" valor={`${numero.format(Number(resumen.kg_romana))} kg`} detalle={resumen.diferencia_kg === null ? "sin pesajes para comparar" : `${numero.format(Number(resumen.diferencia_kg))} kg de diferencia`} />
            <Indicador icono={Clock3} etiqueta="Sobreestadía" valor={`${numero.format(resumen.horas_a_pagar)} h`} detalle="horas totales a pagar" />
          </section>

          <section className="grid gap-3 md:grid-cols-2">
            <div className={`flex items-start gap-3 rounded-2xl border px-5 py-4 text-sm ${resumen.camiones_sin_romana ? "border-amber-200 bg-amber-50 text-amber-900" : "border-emerald-200 bg-emerald-50 text-emerald-900"}`}><Scale className="mt-0.5 h-4 w-4 shrink-0" /><span><strong>{resumen.camiones_sin_romana}</strong> camiones sin pesaje de romana. Los totales de romana y diferencia excluyen esos camiones.</span></div>
            <div className={`flex items-start gap-3 rounded-2xl border px-5 py-4 text-sm ${resumen.camiones_sin_marcas_horarias ? "border-amber-200 bg-amber-50 text-amber-900" : "border-emerald-200 bg-emerald-50 text-emerald-900"}`}><AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" /><span><strong>{resumen.camiones_sin_marcas_horarias}</strong> camiones sin marcas horarias suficientes. Las horas a pagar excluyen esos camiones.</span></div>
          </section>

          <section className="grid gap-4 lg:grid-cols-2">
            <Desglose titulo="Litros por silo" datos={resumen.por_silo} vacio="No hay silos asignados." />
            <Desglose titulo="Litros por procedencia" datos={resumen.por_procedencia} vacio="No hay procedencias registradas." />
          </section>

          <section className="overflow-hidden rounded-2xl border border-slate-200 bg-white">
            <div className="border-b border-slate-200 px-5 py-4"><h3 className="font-semibold text-slate-950">Detalle por camión</h3><p className="mt-1 text-xs text-slate-600">La crioscopía se muestra por módulo; los vacíos permanecen visibles como datos faltantes.</p></div>
            <div className="overflow-x-auto">
              <table className="min-w-[1250px] w-full text-left text-sm">
                <thead className="bg-slate-50 text-xs uppercase tracking-wide text-slate-600"><tr>{["Fecha / hora", "Guía / patente", "Origen", "Litros", "Kg guía", "Kg romana", "Silo", "Estado", "Crioscopías", "Permanencia", "A pagar"].map((titulo) => <th key={titulo} className="px-4 py-3 font-semibold">{titulo}</th>)}</tr></thead>
                <tbody className="divide-y divide-slate-100">
                  {detalle.map((item) => (
                    <tr key={item.id} className="align-top hover:bg-slate-50/60">
                      <td className="px-4 py-3 tabular-nums text-slate-700">{item.fecha}<br /><span className="text-xs text-slate-500">{item.hora_arribo ?? "Sin hora"}</span></td>
                      <td className="px-4 py-3 font-medium text-slate-900">{item.guia || "Sin guía"}<br /><span className="text-xs font-normal text-slate-500">{item.patente || "Sin patente"}</span></td>
                      <td className="px-4 py-3 text-slate-700">{item.procedencia || "Sin dato"}<br /><span className="text-xs text-slate-500">{item.tipo_leche}</span></td>
                      <td className="px-4 py-3 tabular-nums">{numero.format(Number(item.litros))}</td>
                      <td className="px-4 py-3 tabular-nums">{numero.format(Number(item.kg_guia))}</td>
                      <td className="px-4 py-3 tabular-nums">{item.kg_romana === null ? <Falta /> : numero.format(Number(item.kg_romana))}</td>
                      <td className="px-4 py-3">{item.silo || <Falta />}</td>
                      <td className="px-4 py-3"><span className="rounded-full bg-slate-100 px-2.5 py-1 text-xs font-medium text-slate-700">{item.estado_etiqueta}</span></td>
                      <td className="px-4 py-3 text-xs text-slate-700">{item.crioscopias.length ? item.crioscopias.map((m) => <div key={m.modulo}>M{m.modulo}: {m.valor ?? <Falta />}</div>) : <Falta />}</td>
                      <td className="px-4 py-3 tabular-nums">{item.permanencia_horas === null ? <span className="text-xs text-amber-700">{item.permanencia_motivo}</span> : `${numero.format(item.permanencia_horas)} h`}</td>
                      <td className="px-4 py-3 tabular-nums">{item.horas_a_pagar === null ? <Falta /> : `${item.horas_a_pagar} h`}</td>
                    </tr>
                  ))}
                  {detalle.length === 0 && <tr><td colSpan={11} className="px-5 py-10 text-center text-slate-600">No hay camiones en el período seleccionado.</td></tr>}
                </tbody>
              </table>
            </div>
          </section>
        </>
      )}
    </div>
  );
}

function Falta() { return <span className="text-xs font-medium text-amber-700">Sin dato</span>; }

function Desglose({ titulo, datos, vacio }: { titulo: string; datos: Record<string, string>; vacio: string }) {
  const filas = Object.entries(datos);
  return <div className="rounded-2xl border border-slate-200 bg-white p-5"><h3 className="font-semibold text-slate-950">{titulo}</h3><div className="mt-4 space-y-2">{filas.map(([clave, valor]) => <div key={clave} className="flex justify-between gap-4 border-b border-slate-100 pb-2 text-sm"><span className="text-slate-700">{clave}</span><strong className="tabular-nums text-slate-900">{numero.format(Number(valor))} L</strong></div>)}{!filas.length && <p className="text-sm text-slate-600">{vacio}</p>}</div></div>;
}

export default ReporteDiario;
