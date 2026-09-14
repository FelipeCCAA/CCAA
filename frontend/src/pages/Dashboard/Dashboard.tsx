import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import {
  AlertTriangle, Boxes, CheckCircle2, ChevronRight, Clock3, Droplets,
  Factory, FlaskConical, PackageCheck, RefreshCw, ShieldCheck, Truck,
  type LucideIcon,
} from "lucide-react";

import { obtenerPlantaAhora, type PlantaAhora } from "../../services/procesos.service";
import { rutaDeEtapa, totalEsperandoCalidad } from "../../services/planta-ahora";
import { nombreParaMostrar, obtenerSesion } from "../../services/sesion";

const numero = new Intl.NumberFormat("es-CL", { maximumFractionDigits: 0 });

function Indicador({ etiqueta, valor, detalle, icono: Icono, tono }: {
  etiqueta: string;
  valor: number | string;
  detalle: string;
  icono: LucideIcon;
  tono: "emerald" | "sky" | "amber" | "rose";
}) {
  const tonos = {
    emerald: "bg-emerald-50 text-emerald-700",
    sky: "bg-sky-50 text-sky-700",
    amber: "bg-amber-50 text-amber-700",
    rose: "bg-rose-50 text-rose-700",
  };
  return (
    <article className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm shadow-slate-200/30">
      <div className="flex items-start justify-between gap-3">
        <p className="text-xs font-semibold uppercase tracking-[0.12em] text-slate-600">{etiqueta}</p>
        <span className={`rounded-xl p-2.5 ${tonos[tono]}`} aria-hidden="true"><Icono className="h-5 w-5" /></span>
      </div>
      <p className="mt-4 text-3xl font-semibold tabular-nums tracking-tight text-slate-950">
        {typeof valor === "number" ? numero.format(valor) : valor}
      </p>
      <p className="mt-1 text-xs leading-5 text-slate-600">{detalle}</p>
    </article>
  );
}

function Dashboard() {
  const [datos, setDatos] = useState<PlantaAhora | null>(null);
  const [cargando, setCargando] = useState(true);
  const [error, setError] = useState("");
  const sesion = obtenerSesion();

  const cargar = useCallback(async () => {
    setCargando(true);
    setError("");
    try {
      setDatos(await obtenerPlantaAhora());
    } catch {
      setError("No se pudo obtener la situación actual de la planta.");
    } finally {
      setCargando(false);
    }
  }, []);

  useEffect(() => {
    let vigente = true;
    obtenerPlantaAhora()
      .then((respuesta) => {
        if (vigente) setDatos(respuesta);
      })
      .catch(() => {
        if (vigente) setError("No se pudo obtener la situación actual de la planta.");
      })
      .finally(() => {
        if (vigente) setCargando(false);
      });
    return () => { vigente = false; };
  }, []);

  const indicadores = datos?.indicadores;
  const calidadPendiente = totalEsperandoCalidad(indicadores);

  return (
    <main className="px-5 py-7 sm:px-8 lg:px-10 lg:py-9">
      <div className="mx-auto max-w-[1500px] space-y-7">
        <header className="flex flex-col gap-5 xl:flex-row xl:items-end xl:justify-between">
          <div>
            <div className="flex items-center gap-2 text-sm font-semibold text-emerald-700"><Factory className="h-4 w-4" aria-hidden="true" /> Planta Ahora</div>
            <h1 className="mt-2 text-3xl font-semibold tracking-tight text-slate-950 sm:text-4xl">Buenos días, {sesion ? nombreParaMostrar(sesion.usuario).split(" ")[0] : "equipo"}</h1>
            <p className="mt-2 max-w-2xl text-sm leading-6 text-slate-600">Situación operacional consolidada. Cada cifra considera todos los registros productivos, no solo una página.</p>
          </div>
          <button type="button" onClick={() => void cargar()} disabled={cargando} className="inline-flex min-h-11 items-center justify-center gap-2 rounded-xl border border-slate-200 bg-white px-4 py-2.5 text-sm font-semibold text-slate-700 shadow-sm hover:border-emerald-300 disabled:cursor-wait disabled:opacity-60">
            <RefreshCw className={`h-4 w-4 ${cargando ? "animate-spin" : ""}`} aria-hidden="true" />
            {cargando ? "Actualizando…" : "Actualizar planta"}
          </button>
        </header>

        {error && (
          <div role="alert" className="flex items-start gap-3 rounded-2xl border border-rose-200 bg-rose-50 px-5 py-4 text-sm text-rose-900">
            <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" aria-hidden="true" />
            <div className="flex-1"><p className="font-semibold">Información no disponible</p><p className="mt-1">{error}</p></div>
            <button type="button" onClick={() => void cargar()} className="font-semibold underline underline-offset-2">Reintentar</button>
          </div>
        )}

        <section aria-label="Indicadores de planta" className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
          <Indicador etiqueta="Procesos activos" valor={cargando ? "…" : indicadores?.procesos_activos ?? 0} detalle={`${indicadores?.equipos_ocupados ?? 0} equipos ocupados`} icono={Factory} tono="emerald" />
          <Indicador etiqueta="Esperando Calidad" valor={cargando ? "…" : calidadPendiente} detalle={`${indicadores?.esperando_calidad ?? 0} procesos · ${indicadores?.producto_pendiente_calidad ?? 0} unidades logísticas`} icono={ShieldCheck} tono="amber" />
          <Indicador etiqueta="Materiales listos" valor={cargando ? "…" : indicadores?.materiales_listos ?? 0} detalle="Con saldo liberado para continuar, envasar o despachar" icono={PackageCheck} tono="sky" />
          <Indicador etiqueta="Bloqueos" valor={cargando ? "…" : indicadores?.bloqueos ?? 0} detalle={`${indicadores?.silos_en_alerta ?? 0} silos fuera de rango`} icono={AlertTriangle} tono="rose" />
        </section>

        <section className="grid gap-5 xl:grid-cols-[1.35fr_0.85fr]">
          <article className="rounded-2xl border border-slate-200 bg-white p-5 sm:p-6">
            <div className="flex items-start justify-between gap-4">
              <div><p className="text-xs font-semibold uppercase tracking-[0.12em] text-slate-600">Procesos simultáneos</p><h2 className="mt-1 text-lg font-semibold text-slate-900">Estado por etapa</h2></div>
              <Link to="/produccion" className="inline-flex items-center gap-1 text-sm font-semibold text-emerald-700">Abrir Producción <ChevronRight className="h-4 w-4" /></Link>
            </div>
            <div className="mt-5 grid gap-3 md:grid-cols-2">
              {(datos?.procesos_por_etapa ?? []).map((etapa) => (
                <Link key={etapa.tipo} to={rutaDeEtapa(etapa.tipo)} className="rounded-xl border border-slate-200 p-4 transition hover:border-emerald-300 hover:bg-emerald-50/40">
                  <div className="flex items-center justify-between gap-3"><p className="font-semibold text-slate-900">{etapa.etiqueta}</p><span className="rounded-full bg-slate-100 px-2.5 py-1 text-xs font-semibold text-slate-700">{etapa.total}</span></div>
                  <div className="mt-3 flex flex-wrap gap-x-4 gap-y-1 text-xs text-slate-600"><span>{etapa.activos} activas</span><span>{etapa.esperando_calidad} en Calidad</span><span>{etapa.bloqueados} bloqueadas</span></div>
                </Link>
              ))}
              {!cargando && !datos?.procesos_por_etapa.length && <p className="col-span-full rounded-xl bg-emerald-50 px-4 py-8 text-center text-sm font-medium text-emerald-900">No hay procesos que requieran atención operacional.</p>}
            </div>
          </article>

          <article className="rounded-2xl border border-slate-200 bg-slate-950 p-5 text-white sm:p-6">
            <div className="flex items-center justify-between"><div><p className="text-xs font-semibold uppercase tracking-[0.12em] text-emerald-300">Prioridad de turno</p><h2 className="mt-1 text-lg font-semibold">Atención requerida</h2></div><AlertTriangle className="h-5 w-5 text-slate-300" aria-hidden="true" /></div>
            <div className="mt-5 space-y-3">
              {(datos?.alertas ?? []).map((alerta) => (
                <Link key={alerta.codigo} to={alerta.ruta} className="flex gap-3 rounded-xl bg-white/5 px-4 py-3 transition hover:bg-white/10">
                  <span className={`mt-1 h-2.5 w-2.5 shrink-0 rounded-full ${alerta.nivel === "critica" ? "bg-rose-400" : "bg-amber-400"}`} aria-hidden="true" />
                  <span className="min-w-0 flex-1"><span className="block text-sm font-semibold text-white">{alerta.cantidad} · {alerta.titulo}</span><span className="mt-1 block text-xs leading-5 text-slate-300">{alerta.detalle}</span></span>
                  <ChevronRight className="mt-0.5 h-4 w-4 shrink-0 text-slate-400" aria-hidden="true" />
                </Link>
              ))}
              {!cargando && !datos?.alertas.length && <div className="flex items-center gap-3 rounded-xl bg-white/5 px-4 py-5 text-sm text-slate-200"><CheckCircle2 className="h-5 w-5 text-emerald-400" aria-hidden="true" /> No hay alertas operacionales activas.</div>}
            </div>
          </article>
        </section>

        <section className="grid gap-5 xl:grid-cols-[0.8fr_1.2fr]">
          <article className="rounded-2xl border border-slate-200 bg-white p-5 sm:p-6">
            <p className="text-xs font-semibold uppercase tracking-[0.12em] text-slate-600">Flujo físico</p><h2 className="mt-1 text-lg font-semibold text-slate-900">Puntos de control</h2>
            <div className="mt-5 grid gap-3 sm:grid-cols-2 xl:grid-cols-1">
              <Link to="/leche" className="flex items-center gap-4 rounded-xl bg-sky-50 p-4"><Truck className="h-6 w-6 text-sky-700" aria-hidden="true" /><span className="flex-1"><span className="block text-sm font-semibold text-slate-900">Recepciones por completar</span><span className="text-xs text-slate-600">Incluye muestra, análisis, asignación y descarga</span></span><strong className="text-2xl tabular-nums text-sky-800">{indicadores?.recepciones_pendientes ?? 0}</strong></Link>
              <Link to="/silos" className="flex items-center gap-4 rounded-xl bg-emerald-50 p-4"><Droplets className="h-6 w-6 text-emerald-700" aria-hidden="true" /><span className="flex-1"><span className="block text-sm font-semibold text-slate-900">Volumen en silos</span><span className="text-xs text-slate-600">{datos?.silos.total ?? 0} equipos activos</span></span><strong className="text-xl tabular-nums text-emerald-800">{numero.format(Number(datos?.silos.litros ?? 0))} L</strong></Link>
              <Link to="/calidad" className="flex items-center gap-4 rounded-xl bg-amber-50 p-4"><FlaskConical className="h-6 w-6 text-amber-700" aria-hidden="true" /><span className="flex-1"><span className="block text-sm font-semibold text-slate-900">Decisiones de Calidad</span><span className="text-xs text-slate-600">Material detenido hasta una decisión</span></span><strong className="text-2xl tabular-nums text-amber-800">{calidadPendiente}</strong></Link>
            </div>
          </article>

          <article className="overflow-hidden rounded-2xl border border-slate-200 bg-white">
            <div className="border-b border-slate-100 px-5 py-5 sm:px-6"><p className="text-xs font-semibold uppercase tracking-[0.12em] text-slate-600">Movimiento reciente</p><h2 className="mt-1 text-lg font-semibold text-slate-900">Procesos que siguen abiertos</h2></div>
            <div className="divide-y divide-slate-100">
              {(datos?.actividad_reciente ?? []).map((item) => (
                <Link key={item.id} to={rutaDeEtapa(item.etapa_tipo)} className="grid gap-2 px-5 py-4 transition hover:bg-slate-50 sm:grid-cols-[1fr_1fr_auto] sm:items-center sm:px-6">
                  <div><p className="font-semibold text-slate-900">{item.codigo}</p><p className="mt-0.5 text-xs text-slate-600">{item.etapa}</p></div>
                  <div><p className="text-sm text-slate-700">{item.equipo ?? "Sin equipo asignado"}</p><p className="mt-0.5 inline-flex items-center gap-1 text-xs text-slate-500"><Clock3 className="h-3.5 w-3.5" aria-hidden="true" /> Actualizado {new Date(item.actualizada_en).toLocaleString("es-CL")}</p></div>
                  <span className="w-fit rounded-full bg-slate-100 px-3 py-1 text-xs font-semibold text-slate-700">{item.estado_etiqueta}</span>
                </Link>
              ))}
              {!cargando && !datos?.actividad_reciente.length && <p className="px-6 py-10 text-center text-sm text-slate-600">No hay actividad productiva abierta.</p>}
            </div>
          </article>
        </section>

        <footer className="flex flex-wrap items-center gap-x-5 gap-y-2 border-t border-slate-200 pt-5 text-xs text-slate-600">
          <span className="inline-flex items-center gap-1.5"><Boxes className="h-3.5 w-3.5" aria-hidden="true" /> Conteos completos del servidor</span>
          <span className="inline-flex items-center gap-1.5"><ShieldCheck className="h-3.5 w-3.5" aria-hidden="true" /> Acceso según rol y responsabilidad</span>
          {datos && <span>Actualizado {new Date(datos.generado_en).toLocaleString("es-CL")}</span>}
        </footer>
      </div>
    </main>
  );
}

export default Dashboard;
