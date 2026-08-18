import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import {
  AlertTriangle, ArrowRight, CalendarRange, CheckCircle2, ChevronRight,
  CircleDot, Droplets, Factory, FlaskConical, Gauge, GitBranch, PackageCheck,
  ShieldCheck, Truck, Wrench, type LucideIcon,
} from "lucide-react";

import { buscarExpedientes, type FilaExpediente } from "../../services/calidad.service";
import { obtenerResumenMantenimiento, type ResumenMantenimiento } from "../../services/mantenimiento.service";
import { obtenerContraste, obtenerSemanas, type Contraste, type Semana } from "../../services/planificacion.service";
import { obtenerEjecuciones, type EjecucionProceso } from "../../services/procesos.service";
import { obtenerLotes, obtenerResumen as obtenerResumenProduccion, type Lote, type Resumen } from "../../services/produccion.service";
import { obtenerOcupacion, obtenerResumen as obtenerResumenRecepcion, type Ocupacion, type ResumenRecepcion } from "../../services/recepcion.service";
import { nombreParaMostrar, obtenerSesion } from "../../services/sesion";

const numero = new Intl.NumberFormat("es-CL", { maximumFractionDigits: 0 });
const porcentaje = new Intl.NumberFormat("es-CL", { maximumFractionDigits: 1 });

type DatosPanel = {
  produccion: Resumen | null;
  lotes: Lote[];
  recepcion: ResumenRecepcion | null;
  ocupacion: Ocupacion | null;
  ejecuciones: EjecucionProceso[];
  calidad: FilaExpediente[];
  mantenimiento: ResumenMantenimiento | null;
  semana: Semana | null;
  contraste: Contraste | null;
};

const VACIO: DatosPanel = {
  produccion: null, lotes: [], recepcion: null, ocupacion: null,
  ejecuciones: [], calidad: [], mantenimiento: null, semana: null, contraste: null,
};

function Kpi({ etiqueta, valor, unidad, detalle, icono: Icono, tono = "emerald" }: {
  etiqueta: string;
  valor: string;
  unidad?: string;
  detalle: string;
  icono: LucideIcon;
  tono?: "emerald" | "blue" | "amber" | "violet";
}) {
  const tonos = {
    emerald: "bg-emerald-50 text-emerald-700", blue: "bg-sky-50 text-sky-700",
    amber: "bg-amber-50 text-amber-700", violet: "bg-violet-50 text-violet-700",
  };
  return (
    <article className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm shadow-slate-200/30">
      <div className="flex items-start justify-between gap-3">
        <p className="text-xs font-semibold uppercase tracking-[0.12em] text-slate-600">{etiqueta}</p>
        <span className={`rounded-xl p-2.5 ${tonos[tono]}`}><Icono className="h-5 w-5" /></span>
      </div>
      <p className="mt-4 text-3xl font-semibold tracking-tight text-slate-950">
        {valor}{unidad && <span className="ml-1 text-base font-medium text-slate-600">{unidad}</span>}
      </p>
      <p className="mt-1 text-xs leading-5 text-slate-600">{detalle}</p>
    </article>
  );
}

const etapas = [
  { nombre: "Planificación", ruta: "/planificacion", icono: CalendarRange },
  { nombre: "Recepción", ruta: "/leche", icono: Truck },
  { nombre: "Silos", ruta: "/leche/silos", icono: Droplets },
  { nombre: "Estandarización", ruta: "/estandarizacion", icono: FlaskConical },
  { nombre: "Procesamiento", ruta: "/procesos", icono: Factory },
  { nombre: "Calidad", ruta: "/liberacion", icono: ShieldCheck },
  { nombre: "Inventario", ruta: "/abastecimiento/stock", icono: PackageCheck },
];

function Dashboard() {
  const [datos, setDatos] = useState<DatosPanel>(VACIO);
  const [cargando, setCargando] = useState(true);
  const [fuentesConError, setFuentesConError] = useState(0);
  const sesion = obtenerSesion();

  useEffect(() => {
    let vigente = true;
    const cargar = async () => {
      const resultados = await Promise.allSettled([
        obtenerResumenProduccion(), obtenerLotes(6), obtenerResumenRecepcion(),
        obtenerOcupacion(), obtenerEjecuciones(), buscarExpedientes(),
        obtenerResumenMantenimiento(), obtenerSemanas(),
      ]);
      if (!vigente) return;
      const valor = <T,>(indice: number, defecto: T): T => resultados[indice].status === "fulfilled"
        ? (resultados[indice] as PromiseFulfilledResult<T>).value : defecto;
      const semanas = valor<Semana[]>(7, []);
      const semana = semanas.find((item) => item.estado === "publicada") ?? semanas[0] ?? null;
      let contraste: Contraste | null = null;
      if (semana) {
        try { contraste = await obtenerContraste(semana.id); } catch { /* El resto del panel sigue disponible. */ }
      }
      if (!vigente) return;
      setDatos({
        produccion: valor<Resumen | null>(0, null), lotes: valor<Lote[]>(1, []),
        recepcion: valor<ResumenRecepcion | null>(2, null), ocupacion: valor<Ocupacion | null>(3, null),
        ejecuciones: valor<{ results: EjecucionProceso[] }>(4, { results: [] }).results,
        calidad: valor<{ resultados: FilaExpediente[] }>(5, { resultados: [] }).resultados,
        mantenimiento: valor<ResumenMantenimiento | null>(6, null), semana, contraste,
      });
      setFuentesConError(resultados.filter((item) => item.status === "rejected").length + (semana && !contraste ? 1 : 0));
      setCargando(false);
    };
    void cargar();
    return () => { vigente = false; };
  }, []);

  const procesosActivos = datos.ejecuciones.filter((item) => !["cerrada", "cerrado", "anulada", "anulado"].includes(item.estado));
  const pendientesCalidad = datos.calidad.filter((item) => !item.liberacion?.liberado);
  const bloqueadosCalidad = datos.calidad.filter((item) => item.bloqueos.length > 0).length;
  const silosCriticos = datos.ocupacion?.silos.filter((item) => item.excedido || item.negativo) ?? [];
  const recibida = datos.contraste?.resumen.leche_recibida;
  const cumplimiento = recibida?.pct == null ? null : 100 + recibida.pct;
  const alertas = useMemo(() => [
    ...(silosCriticos.length ? [{ texto: `${silosCriticos.length} silo(s) con saldo fuera de rango`, ruta: "/leche/silos", tono: "rose" }] : []),
    ...(bloqueadosCalidad ? [{ texto: `${bloqueadosCalidad} lote(s) bloqueados por Calidad`, ruta: "/liberacion", tono: "amber" }] : []),
    ...((datos.mantenimiento?.fallas_criticas_abiertas ?? 0) ? [{ texto: `${datos.mantenimiento?.fallas_criticas_abiertas} falla(s) crítica(s) abierta(s)`, ruta: "/mantenimiento", tono: "rose" }] : []),
  ], [bloqueadosCalidad, datos.mantenimiento?.fallas_criticas_abiertas, silosCriticos.length]);

  return (
    <main className="px-5 py-7 sm:px-8 lg:px-10 lg:py-9">
      <div className="mx-auto max-w-[1500px] space-y-7">
        <header className="flex flex-col gap-5 xl:flex-row xl:items-end xl:justify-between">
          <div>
            <div className="flex items-center gap-2 text-sm font-semibold text-emerald-700"><CircleDot className="h-4 w-4 fill-emerald-100" /> Centro de control operacional</div>
            <h1 className="mt-2 text-3xl font-semibold tracking-tight text-slate-950 sm:text-4xl">Buenos días, {sesion ? nombreParaMostrar(sesion.usuario).split(" ")[0] : "equipo"}</h1>
            <p className="mt-2 max-w-2xl text-sm leading-6 text-slate-600">Una vista del flujo operacional, desde lo planificado hasta la liberación del producto.</p>
          </div>
          <div className="flex flex-wrap items-center gap-3">
            {datos.semana && <Link to="/planificacion" className="rounded-xl border border-slate-200 bg-white px-4 py-2.5 text-sm font-medium text-slate-700 shadow-sm hover:border-emerald-300">{datos.semana.codigo} / {datos.semana.anio} · {datos.semana.estado_etiqueta}</Link>}
            <Link to="/procesos" className="inline-flex items-center gap-2 rounded-xl bg-emerald-700 px-4 py-2.5 text-sm font-semibold text-white shadow-sm hover:bg-emerald-800"><GitBranch className="h-4 w-4" /> Consultar trazabilidad</Link>
          </div>
        </header>

        {fuentesConError > 0 && !cargando && <div className="flex items-start gap-3 rounded-2xl border border-amber-200 bg-amber-50 px-5 py-4 text-sm text-amber-900"><AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" /><p>Hay {fuentesConError} fuente(s) sin respuesta. Los indicadores disponibles siguen mostrando datos reales; los demás aparecen sin valor.</p></div>}

        <section aria-label="Flujo operacional" className="overflow-x-auto rounded-2xl border border-slate-200 bg-white p-3 shadow-sm shadow-slate-200/30">
          <div className="flex min-w-[900px] items-center">
            {etapas.map((etapa, indice) => { const Icono = etapa.icono; return <div key={etapa.ruta} className="contents"><Link to={etapa.ruta} className="group flex flex-1 items-center gap-3 rounded-xl px-3 py-3 transition hover:bg-emerald-50"><span className="rounded-lg bg-slate-100 p-2 text-slate-600 group-hover:bg-white group-hover:text-emerald-700"><Icono className="h-4 w-4" /></span><span className="text-xs font-semibold text-slate-600 group-hover:text-emerald-800">{etapa.nombre}</span></Link>{indice < etapas.length - 1 && <ArrowRight className="h-4 w-4 shrink-0 text-slate-300" />}</div>; })}
          </div>
        </section>

        <section className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
          <Kpi etiqueta="Recibido real" valor={recibida ? numero.format(recibida.real) : cargando ? "…" : "—"} unidad="L" detalle={recibida ? `Plan: ${numero.format(recibida.plan)} L · diferencia ${numero.format(recibida.diferencia)} L` : "Sin contraste semanal disponible"} icono={Truck} tono="blue" />
          <Kpi etiqueta="En silos" valor={datos.ocupacion ? numero.format(datos.ocupacion.litros_totales) : cargando ? "…" : "—"} unidad="L" detalle={`${datos.ocupacion?.silos.length ?? 0} silos monitoreados desde movimientos`} icono={Droplets} />
          <Kpi etiqueta="Procesos activos" valor={cargando ? "…" : numero.format(procesosActivos.length)} detalle={`${datos.ejecuciones.length} ejecuciones visibles · entradas y salidas trazables`} icono={Factory} tono="violet" />
          <Kpi etiqueta="Producto registrado" valor={datos.produccion ? numero.format(datos.produccion.kg_producidos) : cargando ? "…" : "—"} unidad="kg" detalle={`${datos.produccion?.lotes ?? 0} lotes, sin incluir anulados`} icono={PackageCheck} tono="amber" />
        </section>

        <section className="grid gap-5 xl:grid-cols-[1.4fr_0.8fr]">
          <article className="rounded-2xl border border-slate-200 bg-white p-5 sm:p-6">
            <div className="flex flex-wrap items-start justify-between gap-4"><div><p className="text-xs font-semibold uppercase tracking-[0.12em] text-slate-600">Planificación vs realidad</p><h2 className="mt-1 text-lg font-semibold text-slate-900">Resultado de la semana operacional</h2></div><Link to="/planificacion" className="inline-flex items-center gap-1 text-sm font-semibold text-emerald-700 hover:text-emerald-800">Ver planificación <ChevronRight className="h-4 w-4" /></Link></div>
            <div className="mt-6 grid gap-5 sm:grid-cols-3">
              {[["Planificado", recibida?.plan, "L"], ["Recibido", recibida?.real, "L"], ["Procesado", datos.contraste?.resumen.leche_consumida.real, "L"]].map(([etiqueta, valor, unidad]) => <div key={String(etiqueta)}><p className="text-sm text-slate-600">{etiqueta}</p><p className="mt-1 text-2xl font-semibold tabular-nums text-slate-900">{typeof valor === "number" ? numero.format(valor) : "—"} <span className="text-sm font-medium text-slate-600">{unidad}</span></p></div>)}
            </div>
            <div className="mt-6 rounded-xl bg-slate-50 p-4"><div className="flex items-center justify-between text-sm"><span className="font-medium text-slate-600">Cumplimiento de recepción</span><strong className="text-slate-900">{cumplimiento == null ? "—" : `${porcentaje.format(cumplimiento)}%`}</strong></div><div className="mt-3 h-2 overflow-hidden rounded-full bg-slate-200"><div className="h-full rounded-full bg-emerald-600" style={{ width: `${Math.max(0, Math.min(100, cumplimiento ?? 0))}%` }} /></div><p className="mt-3 text-xs text-slate-600">Los datos reales provienen de descargas y movimientos; nunca reemplazan los valores planificados.</p></div>
          </article>

          {/*
            Única superficie oscura de la aplicación, y por eso la única donde
            los grises van al revés: aquí `text-slate-400` contrasta 7,4:1 sobre
            el fondo y `text-slate-600` solo 2,6:1. Un barrido que oscurezca
            grises «para mejorar el contraste» rompe justamente este bloque —ya
            pasó una vez—, así que los tonos claros de dentro son deliberados.
          */}
          <article className="rounded-2xl border border-slate-200 bg-slate-950 p-5 text-white sm:p-6">
            <div className="flex items-center justify-between"><div><p className="text-xs font-semibold uppercase tracking-[0.12em] text-emerald-300">Puertas de control</p><h2 className="mt-1 text-lg font-semibold">Atención requerida</h2></div><Gauge className="h-6 w-6 text-slate-400" /></div>
            <div className="mt-5 space-y-3">{alertas.length === 0 ? <div className="flex items-center gap-3 rounded-xl bg-white/5 px-4 py-4 text-sm text-slate-300"><CheckCircle2 className="h-5 w-5 text-emerald-400" /> Sin alertas críticas visibles</div> : alertas.map((alerta) => <Link key={alerta.texto} to={alerta.ruta} className="flex items-center gap-3 rounded-xl bg-white/5 px-4 py-3 text-sm text-slate-200 transition hover:bg-white/10"><AlertTriangle className={`h-4 w-4 ${alerta.tono === "rose" ? "text-rose-400" : "text-amber-400"}`} /><span className="flex-1">{alerta.texto}</span><ChevronRight className="h-4 w-4 text-slate-400" /></Link>)}</div>
            <div className="mt-5 grid grid-cols-3 gap-2 border-t border-white/10 pt-5 text-center"><div><p className="text-xl font-semibold">{pendientesCalidad.length}</p><p className="mt-1 text-[10px] uppercase tracking-wide text-slate-400">Calidad</p></div><div><p className="text-xl font-semibold">{datos.recepcion?.por_estado.retenida ?? 0}</p><p className="mt-1 text-[10px] uppercase tracking-wide text-slate-400">Retenidas</p></div><div><p className="text-xl font-semibold">{datos.mantenimiento?.ordenes_abiertas ?? 0}</p><p className="mt-1 text-[10px] uppercase tracking-wide text-slate-400">Mantención</p></div></div>
          </article>
        </section>

        <section className="grid gap-5 xl:grid-cols-[0.9fr_1.1fr]">
          <article className="rounded-2xl border border-slate-200 bg-white p-5 sm:p-6">
            <div className="flex items-center justify-between"><div><p className="text-xs font-semibold uppercase tracking-[0.12em] text-slate-600">Inventario de proceso</p><h2 className="mt-1 text-lg font-semibold text-slate-900">Ocupación de silos</h2></div><Link to="/leche/silos" className="text-sm font-semibold text-emerald-700">Ver silos</Link></div>
            <div className="mt-5 space-y-4">{(datos.ocupacion?.silos ?? []).slice(0, 6).map((silo) => <div key={silo.silo_id}><div className="flex items-center justify-between text-sm"><span className="font-medium text-slate-700">{silo.codigo}</span><span className={silo.excedido || silo.negativo ? "font-semibold text-rose-600" : "text-slate-600"}>{numero.format(silo.litros)} / {numero.format(silo.capacidad)} L · {porcentaje.format(silo.pct)}%</span></div><div className="mt-2 h-2 overflow-hidden rounded-full bg-slate-100"><div className={`h-full rounded-full ${silo.excedido || silo.negativo ? "bg-rose-500" : silo.pct >= 85 ? "bg-amber-500" : "bg-sky-500"}`} style={{ width: `${Math.max(0, Math.min(100, silo.pct))}%` }} /></div></div>)}{!cargando && !datos.ocupacion?.silos.length && <p className="py-8 text-center text-sm text-slate-600">No hay silos con movimientos registrados.</p>}</div>
          </article>

          <article className="overflow-hidden rounded-2xl border border-slate-200 bg-white">
            <div className="flex items-center justify-between border-b border-slate-100 px-5 py-5 sm:px-6"><div><p className="text-xs font-semibold uppercase tracking-[0.12em] text-slate-600">Trazabilidad reciente</p><h2 className="mt-1 text-lg font-semibold text-slate-900">Últimos lotes</h2></div><Link to="/produccion" className="text-sm font-semibold text-emerald-700">Ver producción</Link></div>
            <div className="divide-y divide-slate-100">{datos.lotes.map((lote) => <Link key={lote.id} to="/produccion" className="grid gap-2 px-5 py-4 transition hover:bg-slate-50 sm:grid-cols-[1.1fr_1fr_auto] sm:items-center sm:px-6"><div><p className="font-semibold text-slate-800">{lote.codigo_lote}</p><p className="mt-0.5 text-xs text-slate-600">{lote.op || "Sin orden"} · {lote.fecha}</p></div><div><p className="text-sm text-slate-600">{lote.producto_nombre}</p><p className="mt-0.5 text-xs text-slate-600">{lote.equipo_nombre || lote.linea || "Equipo por asignar"}</p></div><span className="w-fit rounded-full bg-slate-100 px-3 py-1 text-xs font-medium text-slate-600">{lote.estado_etiqueta}</span></Link>)}{!cargando && datos.lotes.length === 0 && <p className="px-6 py-10 text-center text-sm text-slate-600">Todavía no hay lotes registrados.</p>}</div>
          </article>
        </section>

        <footer className="flex flex-wrap gap-3 border-t border-slate-200 pt-5 text-xs text-slate-600"><span className="inline-flex items-center gap-1.5"><Truck className="h-3.5 w-3.5" /> Recepción real</span><span className="inline-flex items-center gap-1.5"><Droplets className="h-3.5 w-3.5" /> Saldos por movimientos</span><span className="inline-flex items-center gap-1.5"><ShieldCheck className="h-3.5 w-3.5" /> Calidad transversal</span><span className="inline-flex items-center gap-1.5"><Wrench className="h-3.5 w-3.5" /> Disponibilidad operacional</span></footer>
      </div>
    </main>
  );
}

export default Dashboard;
