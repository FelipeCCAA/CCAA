import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  AlertTriangle, Beaker, CalendarClock, CheckCircle2, ClipboardCheck,
  Droplets, Factory, Play, Plus, Save, ShieldCheck, X,
} from "lucide-react";
import { mensajeErrorProceso } from "../../services/errores-proceso";

import { EmptyState, ErrorState, PageLoader } from "../../components/ui/PageState";
import StatusBadge from "../../components/ui/StatusBadge";
import {
  actualizarAseo, crearAseo, obtenerAseos, obtenerCatalogosAseo,
  type AseoCip, type CatalogosAseo, type EtapaAseo,
} from "../../services/aseos.service";
import { obtenerEquipos, obtenerSilosMaestros, type Equipo, type Silo } from "../../services/maestros.service";
import { obtenerSesion } from "../../services/sesion";


const control = "w-full rounded-xl border border-slate-300 bg-white px-3 py-2.5 text-sm outline-none focus:border-emerald-600";
const etapasCip = ["pre_enjuague", "soda", "enjuague", "acido", "enjuague"];
const formatoFecha = new Intl.DateTimeFormat("es-CL", {
  dateStyle: "short",
  timeStyle: "short",
});


function fechaLocal(iso: string): string {
  return formatoFecha.format(new Date(iso));
}

function ahoraLocal(): string {
  const fecha = new Date(Date.now() - new Date().getTimezoneOffset() * 60_000);
  return fecha.toISOString().slice(0, 16);
}

function etapasIniciales(): EtapaAseo[] {
  return etapasCip.map((tipo, indice) => ({
    orden: indice + 1, tipo, duracion_min: null, temperatura_c: null,
    caudal: null, conductividad: null, concentracion_pct: null,
    cumple: null, observaciones: "",
  }));
}

interface FormularioNuevo {
  area: string;
  tipo_aseo: "cip" | "cop" | "general";
  tipo_objetivo: "equipo" | "silo" | "seccion";
  equipo: string;
  silo: string;
  seccion: string;
  inicio: string;
  documento_codigo: string;
  observaciones: string;
}

function FormularioPlan({ catalogos, equipos, silos, alCerrar, alCrear }: {
  catalogos: CatalogosAseo;
  equipos: Equipo[];
  silos: Silo[];
  alCerrar: () => void;
  alCrear: (aseo: AseoCip) => void;
}) {
  const perfil = obtenerSesion()?.usuario.perfil;
  const puedeElegirArea = perfil?.area === "aseo" || perfil?.area === "administracion";
  const [datos, setDatos] = useState<FormularioNuevo>({
    area: perfil?.area === "aseo" ? "recepcion" : perfil?.area || "recepcion",
    tipo_aseo: "cip", tipo_objetivo: "equipo", equipo: "", silo: "",
    seccion: "", inicio: ahoraLocal(), documento_codigo: "", observaciones: "",
  });
  const [guardando, setGuardando] = useState(false);
  const [error, setError] = useState("");

  const enviar = async (evento: React.FormEvent) => {
    evento.preventDefault(); setGuardando(true); setError("");
    try {
      const aseo = await crearAseo({
        area: datos.area, tipo_aseo: datos.tipo_aseo, tipo_objetivo: datos.tipo_objetivo,
        equipo: datos.tipo_objetivo === "equipo" && datos.equipo ? Number(datos.equipo) : null,
        silo: datos.tipo_objetivo === "silo" && datos.silo ? Number(datos.silo) : null,
        seccion: datos.tipo_objetivo === "seccion" ? datos.seccion : "",
        inicio: new Date(datos.inicio).toISOString(), documento_codigo: datos.documento_codigo,
        observaciones: datos.observaciones,
        etapas: datos.tipo_aseo === "cip" ? etapasIniciales() : [],
      });
      alCrear(aseo);
    } catch (e) { setError(mensajeErrorProceso(e, "No se pudo guardar el aseo.")); } finally { setGuardando(false); }
  };

  return <form onSubmit={enviar} className="rounded-2xl border border-emerald-200 bg-emerald-50/40 p-5">
    <div className="mb-5 flex items-start justify-between"><div><h2 className="font-semibold text-slate-900">Programar aseo</h2><p className="mt-1 text-sm text-slate-600">Define dónde se hará. El registro queda en la planilla del área.</p></div><button type="button" onClick={alCerrar} className="rounded-lg p-2 text-slate-600 hover:bg-white"><X className="h-5 w-5" /></button></div>
    {error && <div className="mb-4 rounded-xl bg-red-50 px-4 py-3 text-sm text-red-700">{error}</div>}
    <div className="grid gap-4 md:grid-cols-3">
      <label className="text-sm font-medium text-slate-700">Área responsable<select className={`${control} mt-1.5`} value={datos.area} disabled={!puedeElegirArea} onChange={(e) => setDatos({ ...datos, area: e.target.value })}>{catalogos.areas.filter((a) => a.valor !== "aseo").map((o) => <option key={o.valor} value={o.valor}>{o.etiqueta}</option>)}</select></label>
      <label className="text-sm font-medium text-slate-700">Tipo de aseo<select className={`${control} mt-1.5`} value={datos.tipo_aseo} onChange={(e) => setDatos({ ...datos, tipo_aseo: e.target.value as FormularioNuevo["tipo_aseo"] })}>{catalogos.tipos_aseo.map((o) => <option key={o.valor} value={o.valor}>{o.etiqueta}</option>)}</select></label>
      <label className="text-sm font-medium text-slate-700">Objetivo<select className={`${control} mt-1.5`} value={datos.tipo_objetivo} onChange={(e) => setDatos({ ...datos, tipo_objetivo: e.target.value as FormularioNuevo["tipo_objetivo"] })}>{catalogos.tipos_objetivo.map((o) => <option key={o.valor} value={o.valor}>{o.etiqueta}</option>)}</select></label>
      {datos.tipo_objetivo === "equipo" && <label className="text-sm font-medium text-slate-700">Máquina / equipo<select required className={`${control} mt-1.5`} value={datos.equipo} onChange={(e) => setDatos({ ...datos, equipo: e.target.value })}><option value="">Seleccionar…</option>{equipos.map((o) => <option key={o.id} value={o.id}>{o.nombre}</option>)}</select></label>}
      {datos.tipo_objetivo === "silo" && <label className="text-sm font-medium text-slate-700">Silo / tanque<select required className={`${control} mt-1.5`} value={datos.silo} onChange={(e) => setDatos({ ...datos, silo: e.target.value })}><option value="">Seleccionar…</option>{silos.map((o) => <option key={o.id} value={o.id}>{o.codigo} · {o.tipo_etiqueta}</option>)}</select></label>}
      {datos.tipo_objetivo === "seccion" && <label className="text-sm font-medium text-slate-700">Área / sección<input required className={`${control} mt-1.5`} value={datos.seccion} onChange={(e) => setDatos({ ...datos, seccion: e.target.value })} placeholder="Ej. Pretiles, sala de mantequilla" /></label>}
      <label className="text-sm font-medium text-slate-700">Fecha programada<input required type="datetime-local" className={`${control} mt-1.5`} value={datos.inicio} onChange={(e) => setDatos({ ...datos, inicio: e.target.value })} /></label>
      <label className="text-sm font-medium text-slate-700">Documento de Calidad<input className={`${control} mt-1.5`} value={datos.documento_codigo} onChange={(e) => setDatos({ ...datos, documento_codigo: e.target.value })} placeholder="Ej. CCAA.Rec.FORM.015.01" /></label>
      <label className="text-sm font-medium text-slate-700 md:col-span-3">Indicaciones<textarea className={`${control} mt-1.5 min-h-20`} value={datos.observaciones} onChange={(e) => setDatos({ ...datos, observaciones: e.target.value })} /></label>
    </div>
    <div className="mt-5 flex justify-end"><button disabled={guardando} className="flex items-center gap-2 rounded-xl bg-emerald-700 px-5 py-2.5 text-sm font-semibold text-white disabled:opacity-50"><CalendarClock className="h-4 w-4" />{guardando ? "Guardando…" : "Agregar a la planilla"}</button></div>
  </form>;
}

function ControlAseo({ aseo, catalogos, alCambiar, alCerrar }: { aseo: AseoCip; catalogos: CatalogosAseo; alCambiar: (a: AseoCip) => void; alCerrar: () => void }) {
  const [etapas, setEtapas] = useState(aseo.etapas);
  const [ph, setPh] = useState(aseo.ph_final ?? "");
  const [observaciones, setObservaciones] = useState(aseo.observaciones);
  const [guardando, setGuardando] = useState(false);
  const [error, setError] = useState("");

  const cambiarEtapa = (indice: number, cambio: Partial<EtapaAseo>) => setEtapas(etapas.map((e, i) => i === indice ? { ...e, ...cambio } : e));
  const guardar = async (cambios = {}) => {
    setGuardando(true); setError("");
    try {
      const actualizado = await actualizarAseo(aseo.id, { etapas, ph_final: ph || null, observaciones, ...cambios });
      setEtapas(actualizado.etapas); setPh(actualizado.ph_final ?? ""); setObservaciones(actualizado.observaciones);
      alCambiar(actualizado);
    }
    catch (e) { setError(mensajeErrorProceso(e, "No se pudo guardar el aseo.")); } finally { setGuardando(false); }
  };

  return <section className="rounded-2xl border border-slate-200 bg-white p-5">
    <div className="flex items-start justify-between gap-4"><div><p className="text-xs font-bold uppercase tracking-wider text-emerald-700">Control de aseo #{aseo.id}</p><h2 className="mt-1 text-xl font-bold text-slate-900">{aseo.objetivo_nombre}</h2><p className="mt-1 text-sm text-slate-600">{aseo.area_etiqueta} · {aseo.tipo_aseo_etiqueta} · registrado por {aseo.responsable_nombre}</p>{aseo.ejecutado_por_nombre && <p className="mt-1 text-xs text-slate-600">Ejecutado por {aseo.ejecutado_por_nombre}{aseo.verificado_por_nombre ? ` · verificado por ${aseo.verificado_por_nombre}` : ""}</p>}</div><button type="button" onClick={alCerrar} className="rounded-lg p-2 text-slate-600 hover:bg-slate-50"><X className="h-5 w-5" /></button></div>
    {error && <div className="mt-4 rounded-xl bg-red-50 px-4 py-3 text-sm text-red-700">{error}</div>}
    {aseo.estado === "programado" && <div className="mt-5"><button disabled={guardando} onClick={() => void guardar({ estado: "en_curso" })} className="flex items-center gap-2 rounded-xl bg-blue-700 px-4 py-2.5 text-sm font-semibold text-white"><Play className="h-4 w-4" />Iniciar aseo</button></div>}
    {etapas.length > 0 && <div className="mt-6 overflow-x-auto"><table className="w-full min-w-[850px] text-sm"><thead><tr className="border-b border-slate-200 text-left text-xs uppercase tracking-wide text-slate-600"><th className="pb-3">Etapa</th><th className="pb-3">Min</th><th className="pb-3">°C</th><th className="pb-3">Concentración %</th><th className="pb-3">Conductividad</th><th className="pb-3">Caudal</th><th className="pb-3">Resultado</th></tr></thead><tbody>{etapas.map((etapa, i) => <tr key={`${etapa.orden}-${i}`} className="border-b border-slate-100"><td className="py-3 pr-3 font-medium">{catalogos.etapas.find((o) => o.valor === etapa.tipo)?.etiqueta ?? etapa.tipo}</td>{(["duracion_min", "temperatura_c", "concentracion_pct", "conductividad", "caudal"] as const).map((campo) => <td key={campo} className="py-2 pr-2"><input type="number" step="any" className="w-24 rounded-lg border border-slate-300 px-2 py-2" value={etapa[campo] ?? ""} onChange={(e) => cambiarEtapa(i, { [campo]: e.target.value === "" ? null : campo === "duracion_min" ? Number(e.target.value) : e.target.value })} /></td>)}<td className="py-2"><select className="rounded-lg border border-slate-300 px-2 py-2" value={etapa.cumple === null ? "" : String(etapa.cumple)} onChange={(e) => cambiarEtapa(i, { cumple: e.target.value === "" ? null : e.target.value === "true" })}><option value="">Pendiente</option><option value="true">Cumple</option><option value="false">No cumple</option></select></td></tr>)}</tbody></table></div>}
    <div className="mt-6 grid gap-4 md:grid-cols-3"><label className="text-sm font-medium text-slate-700">pH final<input type="number" min="0" max="14" step="0.01" className={`${control} mt-1.5`} value={ph} onChange={(e) => setPh(e.target.value)} placeholder="5,5 a 8,5" /></label><label className="text-sm font-medium text-slate-700 md:col-span-2">Observaciones<textarea className={`${control} mt-1.5 min-h-20`} value={observaciones} onChange={(e) => setObservaciones(e.target.value)} /></label></div>
    <div className="mt-5 flex flex-wrap justify-end gap-2"><button disabled={guardando} onClick={() => void guardar()} className="flex items-center gap-2 rounded-xl border border-slate-300 px-4 py-2.5 text-sm font-semibold text-slate-700"><Save className="h-4 w-4" />Guardar control</button>{aseo.estado === "en_curso" && <><button disabled={guardando} onClick={() => void guardar({ estado: "observado", verificacion: "observado" })} className="flex items-center gap-2 rounded-xl border border-amber-300 bg-amber-50 px-4 py-2.5 text-sm font-semibold text-amber-800"><AlertTriangle className="h-4 w-4" />Cerrar observado</button><button disabled={guardando} onClick={() => void guardar({ estado: "completado", verificacion: "conforme" })} className="flex items-center gap-2 rounded-xl bg-emerald-700 px-4 py-2.5 text-sm font-semibold text-white"><CheckCircle2 className="h-4 w-4" />Completar conforme</button></>}</div>
  </section>;
}

export default function Aseos() {
  const [aseos, setAseos] = useState<AseoCip[]>([]);
  const [catalogos, setCatalogos] = useState<CatalogosAseo | null>(null);
  const [equipos, setEquipos] = useState<Equipo[]>([]);
  const [silos, setSilos] = useState<Silo[]>([]);
  const [cargando, setCargando] = useState(true);
  const [error, setError] = useState("");
  const [nuevo, setNuevo] = useState(false);
  const [preparandoNuevo, setPreparandoNuevo] = useState(false);
  const [seleccionado, setSeleccionado] = useState<number | null>(null);
  const [filtro, setFiltro] = useState("todos");
  const objetivosCargados = useRef(false);

  const cargar = useCallback(async () => {
    setCargando(true); setError("");
    try {
      const [lista, cats] = await Promise.all([obtenerAseos(), obtenerCatalogosAseo()]);
      setAseos(lista); setCatalogos(cats);
    } catch { setError("No se pudo cargar la planilla de aseos."); } finally { setCargando(false); }
  }, []);
  useEffect(() => {
    const tarea = window.setTimeout(() => void cargar(), 0);
    return () => window.clearTimeout(tarea);
  }, [cargar]);

  const abrirNuevo = useCallback(async () => {
    if (objetivosCargados.current) {
      setNuevo(true);
      return;
    }
    setPreparandoNuevo(true);
    setError("");
    try {
      const [maquinas, tanques] = await Promise.all([
        obtenerEquipos(),
        obtenerSilosMaestros(),
      ]);
      setEquipos(maquinas.filter((equipo) => equipo.activo));
      setSilos(tanques.filter((silo) => silo.activo));
      objetivosCargados.current = true;
      setNuevo(true);
    } catch {
      setError("No se pudieron cargar los equipos y estanques del formulario.");
    } finally {
      setPreparandoNuevo(false);
    }
  }, []);

  const visibles = useMemo(() => filtro === "todos" ? aseos : aseos.filter((a) => a.estado === filtro), [aseos, filtro]);
  const resumen = useMemo(() => {
    const cantidades = {
      programado: 0,
      en_curso: 0,
      completado: 0,
      observado: 0,
    };
    aseos.forEach((aseo) => {
      if (aseo.estado in cantidades) {
        cantidades[aseo.estado as keyof typeof cantidades] += 1;
      }
    });
    return cantidades;
  }, [aseos]);
  const activo = aseos.find((a) => a.id === seleccionado) ?? null;
  const reemplazar = (actualizado: AseoCip) => setAseos((lista) => lista.map((a) => a.id === actualizado.id ? actualizado : a));

  return <main className="px-6 py-8 lg:px-10"><div className="mx-auto max-w-7xl space-y-6">
    <header className="flex flex-wrap items-start justify-between gap-4"><div><p className="flex items-center gap-2 text-sm font-semibold uppercase tracking-wider text-emerald-700"><ShieldCheck className="h-4 w-4" />Inocuidad</p><h1 className="mt-2 text-3xl font-bold text-slate-900">Aseos y CIP</h1><p className="mt-2 max-w-3xl text-slate-600">Planifica y controla el aseo de máquinas, silos, tanques y áreas. Cada área ve su planilla; Aseo y saneamiento ve todas las áreas.</p></div><button disabled={preparandoNuevo} onClick={() => void abrirNuevo()} className="flex items-center gap-2 rounded-xl bg-emerald-700 px-5 py-2.5 text-sm font-semibold text-white disabled:opacity-50"><Plus className="h-4 w-4" />{preparandoNuevo ? "Preparando…" : "Programar aseo"}</button></header>
    {error && <ErrorState mensaje={error} />}
    {cargando || !catalogos ? <PageLoader /> : <>
      <section className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">{[
        ["Programados", resumen.programado, CalendarClock],
        ["En curso", resumen.en_curso, Droplets],
        ["Conformes", resumen.completado, ClipboardCheck],
        ["Observados", resumen.observado, AlertTriangle],
      ].map(([etiqueta, valor, Icono]) => { const I = Icono as typeof Beaker; return <article key={String(etiqueta)} className="rounded-2xl border border-slate-200 bg-white p-5"><I className="h-5 w-5 text-emerald-700" /><p className="mt-3 text-sm text-slate-600">{String(etiqueta)}</p><p className="mt-1 text-2xl font-bold text-slate-900">{String(valor)}</p></article>; })}</section>
      {nuevo && <FormularioPlan catalogos={catalogos} equipos={equipos} silos={silos} alCerrar={() => setNuevo(false)} alCrear={(a) => { setAseos((lista) => [a, ...lista]); setNuevo(false); setSeleccionado(a.id); }} />}
      {activo && <ControlAseo aseo={activo} catalogos={catalogos} alCambiar={reemplazar} alCerrar={() => setSeleccionado(null)} />}
      <section className="overflow-hidden rounded-2xl border border-slate-200 bg-white"><div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-200 px-5 py-4"><div><h2 className="font-semibold text-slate-900">Planilla de aseos</h2><p className="mt-1 text-sm text-slate-600">Programación y resultado por ubicación.</p></div><select className="rounded-xl border border-slate-300 px-3 py-2 text-sm" value={filtro} onChange={(e) => setFiltro(e.target.value)}><option value="todos">Todos los estados</option>{catalogos.estados.map((o) => <option key={o.valor} value={o.valor}>{o.etiqueta}</option>)}</select></div>
        {visibles.length === 0 ? <div className="p-6"><EmptyState titulo="Sin aseos en esta vista" detalle="Programa el primer aseo o cambia el filtro de estado." /></div> : <div className="overflow-x-auto"><table className="w-full min-w-[850px] text-left text-sm"><thead className="bg-slate-50 text-xs uppercase tracking-wide text-slate-600"><tr><th className="px-5 py-3">Programado</th><th className="px-5 py-3">Ubicación</th><th className="px-5 py-3">Área</th><th className="px-5 py-3">Tipo</th><th className="px-5 py-3">Documento</th><th className="px-5 py-3">Estado</th><th className="px-5 py-3"></th></tr></thead><tbody>{visibles.map((aseo) => <tr key={aseo.id} className="border-t border-slate-100"><td className="px-5 py-4 whitespace-nowrap">{fechaLocal(aseo.inicio)}</td><td className="px-5 py-4"><p className="font-semibold text-slate-800">{aseo.objetivo_nombre}</p><p className="text-xs text-slate-600">{aseo.tipo_objetivo_etiqueta}</p></td><td className="px-5 py-4">{aseo.area_etiqueta}</td><td className="px-5 py-4">{aseo.tipo_aseo_etiqueta}</td><td className="px-5 py-4 text-xs text-slate-600">{aseo.documento_codigo || "—"}</td><td className="px-5 py-4"><StatusBadge estado={aseo.estado} etiqueta={aseo.estado_etiqueta} /></td><td className="px-5 py-4"><button onClick={() => setSeleccionado(aseo.id)} className="rounded-lg border border-slate-200 px-3 py-2 text-xs font-semibold text-slate-700 hover:bg-slate-50">Abrir control</button></td></tr>)}</tbody></table></div>}
      </section>
      <aside className="flex gap-3 rounded-2xl border border-blue-100 bg-blue-50 p-4 text-sm text-blue-900"><Factory className="mt-0.5 h-5 w-5 shrink-0" /><p>Un CIP en curso bloquea el uso productivo de esa máquina. Si el último aseo queda observado, la máquina continúa no habilitada hasta completar otro conforme.</p></aside>
    </>}
  </div></main>;
}
