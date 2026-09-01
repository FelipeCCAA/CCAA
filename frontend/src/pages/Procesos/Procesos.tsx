import { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { ArrowRight, Beaker, Factory, GitBranch, Search, Truck } from "lucide-react";

import { EmptyState, ErrorState, PageLoader } from "../../components/ui/PageState";
import StatusBadge from "../../components/ui/StatusBadge";
import { iniciarCondensacion, iniciarMantequilla, obtenerCondensaciones, obtenerDescremaciones, obtenerEjecucionesOperativas, obtenerGenealogia, obtenerMantequillas, obtenerRutasProducto, transicionarEjecucion, type CorridaCondensacion, type CorridaDescremacion, type CorridaMantequilla, type EjecucionOperativa, type Genealogia, type RutaProducto } from "../../services/procesos.service";
import { puedeEscribir } from "../../services/sesion";
import ArbolGenealogia from "./ArbolGenealogia";
import CierreCondensacion from "./CierreCondensacion";
import CierreDescremacion from "./CierreDescremacion";
import CierreMantequilla from "./CierreMantequilla";
import FormularioDescremacion from "./FormularioDescremacion";
import NuevaCondensacion from "./NuevaCondensacion";
import NuevaMantequilla from "./NuevaMantequilla";

export default function Procesos() {
  const puedeOperar = puedeEscribir("produccion");
  const [parametros, setParametros] = useSearchParams();
  const [ejecuciones, setEjecuciones] = useState<EjecucionOperativa[]>([]);
  const [rutas, setRutas] = useState<RutaProducto[]>([]);
  const [rutasCargadas, setRutasCargadas] = useState(false);
  const [condensaciones, setCondensaciones] = useState<CorridaCondensacion[]>([]);
  const [condensacionesCargadas, setCondensacionesCargadas] = useState(false);
  const [mantequillas, setMantequillas] = useState<CorridaMantequilla[]>([]);
  const [mantequillasCargadas, setMantequillasCargadas] = useState(false);
  const [descremaciones, setDescremaciones] = useState<CorridaDescremacion[]>([]);
  const [descremacionesCargadas, setDescremacionesCargadas] = useState(false);
  const [cerrandoDescremacion, setCerrandoDescremacion] = useState<CorridaDescremacion | null>(null);
  const [cerrandoCondensacion, setCerrandoCondensacion] = useState<CorridaCondensacion | null>(null);
  const [cerrandoMantequilla, setCerrandoMantequilla] = useState<CorridaMantequilla | null>(null);
  const [accionandoCorrida, setAccionandoCorrida] = useState<number | null>(null);
  const [nuevaCondensacion, setNuevaCondensacion] = useState(false);
  const [nuevaMantequilla, setNuevaMantequilla] = useState(false);
  const [cargando, setCargando] = useState(true);
  const [error, setError] = useState("");
  const [lote, setLote] = useState("");
  const [direccion, setDireccion] = useState<"atras" | "adelante">("atras");
  const [genealogia, setGenealogia] = useState<Genealogia | null>(null);
  const [accionando, setAccionando] = useState<number | null>(null);
  const siloParametro = Number(parametros.get("silo"));
  const siloDescremacion = parametros.get("accion") === "descremar" && Number.isInteger(siloParametro) && siloParametro > 0
    ? siloParametro : null;
  const seccionSolicitada = parametros.get("seccion");

  useEffect(() => {
    if (!seccionSolicitada) return;
    const temporizador = window.setTimeout(() => {
      document.getElementById(`proceso-${seccionSolicitada}`)?.scrollIntoView({ behavior: "smooth", block: "start" });
    }, 0);
    return () => window.clearTimeout(temporizador);
  }, [seccionSolicitada]);

  useEffect(() => {
    obtenerEjecucionesOperativas()
      .then((operativas) => {
        setEjecuciones(operativas);
      })
      .catch(() => setError("No se pudieron cargar las ejecuciones industriales."))
      .finally(() => setCargando(false));
  }, []);

  const moverEjecucion = async (id: number) => {
    setAccionando(id);
    setError("");
    try {
      await transicionarEjecucion(id, "ejecucion");
      setEjecuciones(await obtenerEjecucionesOperativas());
    } catch (errorPeticion: unknown) {
      const respuesta = errorPeticion as { response?: { data?: { error?: string } } };
      setError(respuesta.response?.data?.error || "No se pudo iniciar la ejecución.");
    } finally {
      setAccionando(null);
    }
  };

  useEffect(() => {
    if (siloDescremacion !== null) {
      obtenerDescremaciones().then((pagina) => {
        setDescremaciones(pagina.results);
        setDescremacionesCargadas(true);
      }).catch(() => setError("No se pudieron cargar las descremaciones."));
    }
  }, [siloDescremacion]);

  const cerrarFormularioDescremacion = () => {
    setParametros({}, { replace: true });
  };

  const actualizarDescremacion = async (corrida: CorridaDescremacion) => {
    setDescremacionesCargadas(true);
    setDescremaciones((actuales) => [corrida, ...actuales.filter((item) => item.id !== corrida.id)]);
  };

  const actualizarCondensacion = (corrida: CorridaCondensacion) => {
    setCondensaciones((actuales) => actuales.map((item) => item.id === corrida.id ? corrida : item));
  };

  const actualizarMantequilla = (corrida: CorridaMantequilla) => {
    setMantequillas((actuales) => actuales.map((item) => item.id === corrida.id ? corrida : item));
  };

  const iniciarCorrida = async (tipo: "condensacion" | "mantequilla", id: number) => {
    setAccionandoCorrida(id); setError("");
    try {
      if (tipo === "condensacion") actualizarCondensacion(await iniciarCondensacion(id));
      else actualizarMantequilla(await iniciarMantequilla(id));
      setEjecuciones(await obtenerEjecucionesOperativas());
    } catch (errorPeticion: unknown) {
      const datos = (errorPeticion as { response?: { data?: unknown } }).response?.data;
      const detalle = datos && typeof datos === "object"
        ? Object.values(datos as Record<string, unknown>).flat().map(String).join(" ")
        : "";
      setError(detalle || "No se pudo iniciar la corrida. Revisa equipo, aseo, saldo y estado de la orden.");
    } finally { setAccionandoCorrida(null); }
  };

  const cargarRutas = async () => {
    try {
      const pagina = await obtenerRutasProducto();
      setRutas(pagina.results);
      setRutasCargadas(true);
    } catch { setError("No se pudieron cargar las rutas de proceso."); }
  };

  const cargarCondensaciones = async () => {
    try {
      const pagina = await obtenerCondensaciones();
      setCondensaciones(pagina.results);
      setCondensacionesCargadas(true);
    } catch { setError("No se pudieron cargar las condensaciones."); }
  };

  const cargarMantequillas = async () => {
    try {
      const pagina = await obtenerMantequillas();
      setMantequillas(pagina.results);
      setMantequillasCargadas(true);
    } catch { setError("No se pudieron cargar las corridas de mantequilla."); }
  };

  const cargarDescremaciones = async () => {
    try {
      const pagina = await obtenerDescremaciones();
      setDescremaciones(pagina.results);
      setDescremacionesCargadas(true);
    } catch { setError("No se pudieron cargar las descremaciones."); }
  };

  const buscar = async (evento: React.FormEvent) => {
    evento.preventDefault();
    if (!lote.trim()) {
      setError("Escribe el código del lote.");
      return;
    }

    setError("");

    try {
      setGenealogia(await obtenerGenealogia(lote, direccion));
    } catch {
      setGenealogia(null);
      setError(`No existe el lote «${lote.trim()}» o no se pudo reconstruir su genealogía.`);
    }
  };

  return (
    <main className="px-6 py-8 lg:px-10">
      <div className="mx-auto max-w-7xl space-y-8">
        <header>
          <p className="text-sm font-semibold uppercase tracking-wider text-green-700">Procesamiento</p>
          <h1 className="mt-2 text-3xl font-bold text-slate-900">Ejecuciones y trazabilidad</h1>
          <p className="mt-2 max-w-3xl text-slate-600">Entradas, salidas, coproductos, reprocesos y mermas vinculados a los lotes reales.</p>
        </header>

        {error && <ErrorState mensaje={error} />}

        {puedeOperar && siloDescremacion !== null && <FormularioDescremacion siloOrigen={siloDescremacion} onCerrar={cerrarFormularioDescremacion} onCreada={async (corrida) => { await actualizarDescremacion(corrida); cerrarFormularioDescremacion(); }} />}
        {puedeOperar && cerrandoDescremacion && <CierreDescremacion corrida={cerrandoDescremacion} onCerrar={() => setCerrandoDescremacion(null)} onCerrada={async (corrida) => { await actualizarDescremacion(corrida); setCerrandoDescremacion(null); }} />}
        {puedeOperar && cerrandoCondensacion && <CierreCondensacion corrida={cerrandoCondensacion} onCerrar={() => setCerrandoCondensacion(null)} onCerrada={async (corrida) => { actualizarCondensacion(corrida); setCerrandoCondensacion(null); setEjecuciones(await obtenerEjecucionesOperativas()); }} />}
        {puedeOperar && cerrandoMantequilla && <CierreMantequilla corrida={cerrandoMantequilla} onCerrar={() => setCerrandoMantequilla(null)} onCerrada={async (corrida) => { actualizarMantequilla(corrida); setCerrandoMantequilla(null); setEjecuciones(await obtenerEjecucionesOperativas()); }} />}
        {puedeOperar && nuevaCondensacion && <NuevaCondensacion onCerrar={() => setNuevaCondensacion(false)} onCreada={(corrida) => { setCondensacionesCargadas(true); setCondensaciones((actuales) => [corrida, ...actuales]); setNuevaCondensacion(false); }} />}
        {puedeOperar && nuevaMantequilla && <NuevaMantequilla onCerrar={() => setNuevaMantequilla(false)} onCreada={(corrida) => { setMantequillasCargadas(true); setMantequillas((actuales) => [corrida, ...actuales]); setNuevaMantequilla(false); }} />}

        <section className="rounded-2xl border border-slate-200 bg-white p-6">
          <div className="flex items-center gap-3"><GitBranch className="h-5 w-5 text-green-700" /><h2 className="text-lg font-semibold">Rutas configuradas por producto</h2></div>
          <p className="mt-2 text-sm text-slate-600">La secuencia proviene del maestro de procesos; no está codificada en la interfaz.</p>
          {!rutasCargadas ? <button type="button" onClick={cargarRutas} className="mt-5 rounded-xl border border-emerald-700 px-4 py-2 text-sm font-semibold text-emerald-700">Cargar rutas</button> : rutas.length === 0 ? <p className="mt-5 text-sm text-slate-600">No hay rutas activas configuradas.</p> : <div className="mt-5 grid gap-4 lg:grid-cols-2">{rutas.map((ruta) => <article key={ruta.id} className="rounded-xl border border-slate-200 p-4"><div className="flex items-start justify-between gap-3"><div><p className="font-semibold text-slate-900">{ruta.producto_nombre}</p><p className="mt-1 text-sm text-green-700">{ruta.proceso_nombre}{ruta.destino ? ` → ${ruta.destino}` : ""}</p></div><span className="rounded-full bg-slate-100 px-2.5 py-1 text-xs font-medium text-slate-600">Prioridad {ruta.prioridad}</span></div><div className="mt-3 flex flex-wrap items-center gap-2 text-xs text-slate-600">{ruta.etapas.sort((a, b) => a.orden - b.orden).map((etapa, indice) => <span key={etapa.id} className="inline-flex items-center gap-2"><span className="rounded-lg bg-slate-50 px-2 py-1">{etapa.nombre}</span>{indice < ruta.etapas.length - 1 && <ArrowRight className="h-3 w-3" />}</span>)}</div></article>)}</div>}
        </section>

        <section id="proceso-descremacion" className="scroll-mt-6">
          <h2 className="mb-4 text-xl font-semibold text-slate-800">Descremación</h2>
          {!descremacionesCargadas ? <button type="button" onClick={cargarDescremaciones} className="rounded-xl border border-emerald-700 px-4 py-2 text-sm font-semibold text-emerald-700">Cargar corridas de descremación</button> : descremaciones.length === 0 ? <EmptyState titulo="Sin corridas de descremación" detalle="Inicia una desde la acción Descremar disponible en el detalle de un silo." /> : <div className="grid gap-4 lg:grid-cols-2">{descremaciones.map((corrida) => <article key={corrida.id} className="rounded-2xl border border-slate-200 bg-white p-5"><div className="flex items-start justify-between gap-3"><div><p className="font-semibold text-slate-900">{corrida.ejecucion_codigo}</p><p className="mt-1 text-xs text-slate-600">{corrida.equipo_nombre || "Sin equipo"}</p></div><StatusBadge estado={corrida.estado} etiqueta={corrida.estado_etiqueta} /></div><div className="mt-4 rounded-xl bg-slate-50 p-3 text-sm text-slate-700"><span className="font-semibold">{corrida.silo_entera_codigo}</span> · {Number(corrida.litros_entrada).toLocaleString("es-CL")} L <ArrowRight className="mx-1 inline h-3.5 w-3.5" /> {corrida.silo_descremada_codigo} + {corrida.estanque_crema_codigo}</div>{corrida.estado === "en_curso" && <button type="button" onClick={() => setCerrandoDescremacion(corrida)} className="mt-4 rounded-xl bg-emerald-700 px-4 py-2 text-sm font-semibold text-white">Registrar salidas y cerrar</button>}{corrida.estado === "cerrada" && <p className="mt-3 text-xs text-slate-600">Salida: {Number(corrida.litros_descremada).toLocaleString("es-CL")} L descremada + {Number(corrida.litros_crema).toLocaleString("es-CL")} L crema.</p>}</article>)}</div>}
        </section>

        <section id="proceso-condensacion" className="scroll-mt-6">
          <div className="flex flex-wrap items-center justify-between gap-3"><h2 className="text-xl font-semibold text-slate-800">Evaporación / precondensado</h2>{puedeOperar && <button type="button" onClick={() => setNuevaCondensacion(true)} className="rounded-xl bg-blue-700 px-4 py-2 text-sm font-semibold text-white">Nueva evaporación</button>}</div>
          <p className="mb-4 mt-1 text-sm text-slate-600">Vale estandarizado → evaporador → concentrado. El cierre registra controles y lo envía a Calidad.</p>
          {!condensacionesCargadas ? <button type="button" onClick={cargarCondensaciones} className="rounded-xl border border-emerald-700 px-4 py-2 text-sm font-semibold text-emerald-700">Cargar corridas</button> : condensaciones.length === 0 ? <EmptyState titulo="Sin corridas de evaporación" detalle="No hay corridas vinculadas a una orden, lote, evaporador y silos." /> : <div className="overflow-x-auto rounded-2xl border border-slate-200 bg-white"><table className="w-full min-w-[980px] text-left text-sm"><thead className="bg-slate-50 text-slate-600"><tr><th className="px-5 py-3">Orden / lote</th><th className="px-5 py-3">Evaporador</th><th className="px-5 py-3">Flujo físico</th><th className="px-5 py-3">Resultado</th><th className="px-5 py-3">Estado</th><th className="px-5 py-3">Operación</th></tr></thead><tbody>{condensaciones.map((corrida) => <tr key={corrida.id} className="border-t border-slate-100"><td className="px-5 py-4 font-semibold text-slate-800">{corrida.orden_codigo}<span className="block text-xs font-normal text-slate-600">{corrida.lote_codigo} · {corrida.ejecucion_codigo}</span></td><td className="px-5 py-4">{corrida.equipo_nombre || "—"}</td><td className="px-5 py-4">{corrida.silo_origen_codigo} · {Number(corrida.litros_entrada).toLocaleString("es-CL")} L <ArrowRight className="mx-1 inline h-3.5 w-3.5" /> {corrida.silo_destino_codigo}</td><td className="px-5 py-4">{corrida.litros_precondensado ? `${Number(corrida.litros_precondensado).toLocaleString("es-CL")} L` : "Pendiente"}<span className="block text-xs text-slate-600">{corrida.solidos_salida ? `${corrida.solidos_salida}% sólidos` : "sin control final"}</span></td><td className="px-5 py-4"><StatusBadge estado={corrida.estado} etiqueta={corrida.estado_etiqueta} /></td><td className="px-5 py-4">{puedeOperar && corrida.estado === "borrador" ? <button type="button" disabled={accionandoCorrida === corrida.id} onClick={() => void iniciarCorrida("condensacion", corrida.id)} className="rounded-lg bg-blue-700 px-3 py-2 text-xs font-semibold text-white disabled:opacity-50">{accionandoCorrida === corrida.id ? "Iniciando…" : "Iniciar evaporación"}</button> : puedeOperar && corrida.estado === "en_proceso" ? <button type="button" onClick={() => setCerrandoCondensacion(corrida)} className="rounded-lg bg-blue-700 px-3 py-2 text-xs font-semibold text-white">Registrar salida</button> : <span className="text-xs text-slate-500">Sin acción pendiente</span>}</td></tr>)}</tbody></table></div>}
        </section>

        <section id="proceso-mantequilla" className="scroll-mt-6">
          <div className="mb-4 flex flex-wrap items-center justify-between gap-3"><h2 className="text-xl font-semibold text-slate-800">Línea de mantequilla</h2>{puedeOperar && <button type="button" onClick={() => setNuevaMantequilla(true)} className="rounded-xl bg-amber-700 px-4 py-2 text-sm font-semibold text-white">Nueva corrida</button>}</div>
          {!mantequillasCargadas ? <button type="button" onClick={cargarMantequillas} className="rounded-xl border border-emerald-700 px-4 py-2 text-sm font-semibold text-emerald-700">Cargar corridas</button> : mantequillas.length === 0 ? <EmptyState titulo="Sin corridas de mantequilla" detalle="Las corridas conservarán la relación crema → mantequilla, suero y merma." /> : <div className="grid gap-4 lg:grid-cols-2">{mantequillas.map((corrida) => <article key={corrida.id} className="rounded-2xl border border-slate-200 bg-white p-5"><div className="flex items-start justify-between gap-3"><div><p className="font-semibold text-slate-900">{corrida.orden_codigo} · {corrida.mantequilla_codigo}</p><p className="mt-1 text-xs text-slate-600">{corrida.equipo_nombre || "Sin línea"} · {corrida.ejecucion_codigo}</p></div><StatusBadge estado={corrida.estado} etiqueta={corrida.estado_etiqueta} /></div><div className="mt-4 grid grid-cols-2 gap-3 text-sm"><p className="rounded-xl bg-amber-50 p-3 text-amber-900"><span className="block text-xs text-amber-700">Crema utilizada</span>{Number(corrida.kg_crema).toLocaleString("es-CL")} kg · {corrida.crema_codigo}</p><p className="rounded-xl bg-green-50 p-3 text-green-900"><span className="block text-xs text-green-700">Mantequilla</span>{corrida.kg_mantequilla ? `${Number(corrida.kg_mantequilla).toLocaleString("es-CL")} kg` : "Pendiente"}</p><p className="rounded-xl bg-slate-50 p-3 text-slate-700"><span className="block text-xs text-slate-600">Suero</span>{Number(corrida.kg_suero).toLocaleString("es-CL")} kg</p><p className="rounded-xl bg-slate-50 p-3 text-slate-700"><span className="block text-xs text-slate-600">Merma</span>{Number(corrida.kg_merma).toLocaleString("es-CL")} kg</p></div>{puedeOperar && corrida.estado === "borrador" && <button type="button" disabled={accionandoCorrida === corrida.id} onClick={() => void iniciarCorrida("mantequilla", corrida.id)} className="mt-4 rounded-xl bg-amber-700 px-4 py-2 text-sm font-semibold text-white disabled:opacity-50">{accionandoCorrida === corrida.id ? "Iniciando…" : "Iniciar con esta crema"}</button>}{puedeOperar && corrida.estado === "en_proceso" && <button type="button" onClick={() => setCerrandoMantequilla(corrida)} className="mt-4 rounded-xl bg-amber-700 px-4 py-2 text-sm font-semibold text-white">Registrar balance y cerrar</button>}{corrida.estado === "pendiente_calidad" && <p className="mt-4 rounded-xl bg-violet-50 px-3 py-2 text-xs font-medium text-violet-800">Producción cerrada; Calidad debe revisar antes de Envasado.</p>}</article>)}</div>}
        </section>

        <section className="rounded-2xl border border-slate-200 bg-white p-6">
          <div className="flex items-center gap-3"><GitBranch className="h-5 w-5 text-green-700" /><h2 className="text-lg font-semibold">Consultar genealogía</h2></div>
          <form onSubmit={buscar} className="mt-5 flex flex-col gap-3 sm:flex-row">
            <input value={lote} onChange={(e) => setLote(e.target.value)} placeholder="Código del lote (p. ej. CCAA6212010102010201-01)" className="flex-1 rounded-xl border border-slate-300 px-4 py-2.5" />
            <select value={direccion} onChange={(e) => setDireccion(e.target.value as "atras" | "adelante")} className="rounded-xl border border-slate-300 bg-white px-4 py-2.5"><option value="atras">Hacia atrás</option><option value="adelante">Hacia adelante</option></select>
            <button className="inline-flex items-center justify-center gap-2 rounded-xl bg-green-700 px-5 py-2.5 font-semibold text-white"><Search className="h-4 w-4" />Buscar</button>
          </form>
          {genealogia?.flujo && (
            <div className="mt-6">
              <h3 className="text-sm font-semibold uppercase tracking-wide text-slate-600">
                Línea completa del lote
              </h3>
              <div className="mt-3 grid items-stretch gap-3 lg:grid-cols-[1fr_auto_1fr_auto_1fr]">
                <div className="rounded-xl border border-slate-200 p-4">
                  <div className="flex items-center gap-2 font-semibold text-slate-800">
                    <Truck className="h-4 w-4 text-green-700" /> Recepción
                  </div>
                  <p className="mt-2 text-sm text-slate-600">
                    {genealogia.flujo.recepciones.length} recepción(es) candidata(s)
                  </p>
                  <ul className="mt-2 space-y-1 text-xs text-slate-600">
                    {genealogia.flujo.recepciones.slice(0, 4).map((item) => (
                      <li key={`${item.id}-${item.silo_codigo}`}>
                        {item.fecha} · guía {item.guia || "—"} · {item.silo_codigo}
                      </li>
                    ))}
                  </ul>
                  <p className="mt-2 text-xs text-slate-600">{genealogia.flujo.nota_recepciones}</p>
                </div>
                <ArrowRight className="m-auto hidden h-5 w-5 text-slate-300 lg:block" />
                <div className="rounded-xl border border-green-200 bg-green-50/50 p-4">
                  <div className="flex items-center gap-2 font-semibold text-slate-800">
                    <Beaker className="h-4 w-4 text-green-700" /> Estandarización
                  </div>
                  <p className="mt-2 text-sm font-medium">{genealogia.flujo.estandarizacion.vale_codigo}</p>
                  <p className="mt-1 text-xs text-slate-600">
                    {genealogia.flujo.estandarizacion.silos_origen.map((item) => item.codigo).join(" + ")}
                    {" → "}{genealogia.flujo.estandarizacion.silo_destino}
                  </p>
                  <p className="mt-2 text-xs text-slate-600">
                    Proceso {genealogia.flujo.estandarizacion.ejecucion_codigo || "sin ID"}
                  </p>
                </div>
                <ArrowRight className="m-auto hidden h-5 w-5 text-slate-300 lg:block" />
                <div className="rounded-xl border border-slate-200 p-4">
                  <div className="flex items-center gap-2 font-semibold text-slate-800">
                    <Factory className="h-4 w-4 text-green-700" /> Producción
                  </div>
                  <p className="mt-2 text-sm font-medium">{genealogia.flujo.produccion.lote_codigo}</p>
                  <p className="mt-1 text-xs text-slate-600">
                    {genealogia.flujo.produccion.producto} · {genealogia.flujo.produccion.linea || "sin línea"} · {genealogia.flujo.produccion.equipo || "sin máquina"}
                  </p>
                  <p className="mt-2 text-xs text-slate-600">
                    Proceso {genealogia.flujo.produccion.ejecucion_codigo || "sin ID"}
                  </p>
                </div>
              </div>
              {genealogia.flujo.cadena_procesos.length > 0 && (
                <div className="mt-4 rounded-xl border border-violet-200 bg-violet-50/40 p-4">
                  <p className="text-sm font-semibold text-violet-950">Transformaciones relacionadas</p>
                  <div className="mt-3 flex gap-2 overflow-x-auto pb-2">
                    {genealogia.flujo.cadena_procesos.map((ejecucion, indice) => (
                      <div key={ejecucion.id} className="flex shrink-0 items-center gap-2">
                        {indice > 0 && <ArrowRight className="h-4 w-4 text-violet-300" />}
                        <article className="w-56 rounded-lg border border-violet-200 bg-white p-3 text-xs">
                          <p className="font-bold text-slate-900">{ejecucion.etapa}</p>
                          <p className="mt-1 text-violet-700">{ejecucion.codigo}</p>
                          <p className="mt-1 text-slate-500">{ejecucion.equipo || "Sin equipo"} · {ejecucion.estado}</p>
                          {ejecucion.salidas.map((salida) => (
                            <p key={salida.id} className="mt-2 rounded bg-slate-50 px-2 py-1 text-slate-600">
                              {Number(salida.cantidad).toLocaleString("es-CL")} {salida.unidad} · {salida.clase} → {salida.destino}
                            </p>
                          ))}
                        </article>
                      </div>
                    ))}
                  </div>
                </div>
              )}
              <div className="mt-3 grid gap-3 lg:grid-cols-2">
                <div className="rounded-xl border border-sky-200 bg-sky-50/60 p-4">
                  <p className="text-sm font-semibold text-sky-900">Calidad · {genealogia.flujo.calidad.estado}</p>
                  <p className="mt-1 text-xs text-sky-700">{genealogia.flujo.calidad.autorizada_por ? `Firmado por ${genealogia.flujo.calidad.autorizada_por}` : "Sin firma de liberación"}</p>
                </div>
                <div className="rounded-xl border border-amber-200 bg-amber-50/60 p-4">
                  <p className="text-sm font-semibold text-amber-900">Envase, inventario y despacho</p>
                  {genealogia.flujo.pallets.length === 0 ? <p className="mt-1 text-xs text-amber-700">Sin pallets registrados.</p> : <ul className="mt-2 space-y-1 text-xs text-amber-800">{genealogia.flujo.pallets.map((p) => <li key={p.id}>{p.codigo} · {p.kg_neto} kg · {p.ubicacion ? `ubicación ${p.ubicacion}` : p.estado}{p.cliente ? ` · cliente ${p.cliente} (${p.despacho})` : ""}</li>)}</ul>}
                </div>
              </div>
            </div>
          )}
          {genealogia && <div className="mt-5"><ArbolGenealogia genealogia={genealogia} direccion={direccion} /></div>}
        </section>

        <section>
          <h2 className="mb-1 text-xl font-semibold text-slate-800">Ejecuciones operativas</h2>
          <p className="mb-4 text-sm text-slate-600">Solo pendientes y en curso. El inicio valida nuevamente máquina, ocupación y aseo.</p>
          {cargando ? <PageLoader /> : ejecuciones.length === 0 ? <EmptyState titulo="Sin trabajo operativo pendiente" detalle="Las ejecuciones cerradas no se cargan en esta bandeja." /> : <div className="overflow-x-auto rounded-2xl border border-slate-200 bg-white"><table className="w-full text-left text-sm"><thead className="bg-slate-50 text-slate-600"><tr><th className="px-5 py-3">ID del proceso</th><th className="px-5 py-3">Etapa</th><th className="px-5 py-3">Equipo</th><th className="px-5 py-3">Estado</th><th className="px-5 py-3">Entrada</th><th className="px-5 py-3">Salida</th><th className="px-5 py-3">Acción</th></tr></thead><tbody>{ejecuciones.map((item) => <tr key={item.id} className="border-t border-slate-100"><td className="px-5 py-4 font-semibold text-slate-800">{item.codigo}</td><td className="px-5 py-4">{item.etapa_nombre}</td><td className="px-5 py-4">{item.equipo_nombre ?? "—"}</td><td className="px-5 py-4"><StatusBadge estado={item.estado} etiqueta={item.estado_etiqueta} /></td><td className="px-5 py-4 text-xs">{item.entradas.join(" + ") || "—"}</td><td className="px-5 py-4 text-xs">{item.salidas.join(" + ") || "—"}</td><td className="px-5 py-4">{item.acciones_permitidas.includes("ejecucion") ? <button type="button" disabled={accionando === item.id} onClick={() => void moverEjecucion(item.id)} className="rounded-lg bg-emerald-700 px-3 py-2 text-xs font-semibold text-white disabled:opacity-50">{accionando === item.id ? "Validando…" : item.estado === "pausada" ? "Reanudar" : "Iniciar"}</button> : <span className="text-xs text-slate-500">Sin acción directa</span>}</td></tr>)}</tbody></table></div>}
        </section>
      </div>
    </main>
  );
}
