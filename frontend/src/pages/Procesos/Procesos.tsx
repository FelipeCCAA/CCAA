import { useEffect, useState } from "react";
import { Navigate, useSearchParams } from "react-router-dom";
import { ArrowRight, GitBranch, Plus } from "lucide-react";

import { EmptyState, ErrorState, PageLoader } from "../../components/ui/PageState";
import EstadoEquipo from "../../components/EstadoEquipo/EstadoEquipo";
import StatusBadge from "../../components/ui/StatusBadge";
import { iniciarMantequilla, obtenerDescremaciones, obtenerEjecucionesOperativas, obtenerMantequillas, obtenerRutasProducto, transicionarEjecucion, type CorridaDescremacion, type CorridaMantequilla, type EjecucionOperativa, type RutaProducto } from "../../services/procesos.service";
import { esConflictoVersion, esErrorDeEquipo, mensajeErrorProceso } from "../../services/errores-proceso";
import { puedeEscribir } from "../../services/sesion";
import CierreDescremacion from "./CierreDescremacion";
import CierreMantequilla from "./CierreMantequilla";
import DiagnosticoRutas from "./DiagnosticoRutas";
import FormularioDescremacion from "./FormularioDescremacion";
import NuevaMantequilla from "./NuevaMantequilla";
import NuevaRutaProducto from "./NuevaRutaProducto";
import ReworkProduccion from "./ReworkProduccion";
import TrazabilidadProceso from "./TrazabilidadProceso";

export default function Procesos() {
  const puedeOperar = puedeEscribir("produccion");
  const puedeConfigurar = puedeEscribir("maestros");
  const [parametros, setParametros] = useSearchParams();
  const [ejecuciones, setEjecuciones] = useState<EjecucionOperativa[]>([]);
  const [rutas, setRutas] = useState<RutaProducto[]>([]);
  const [rutasCargadas, setRutasCargadas] = useState(false);
  const [mantequillas, setMantequillas] = useState<CorridaMantequilla[]>([]);
  const [mantequillasCargadas, setMantequillasCargadas] = useState(false);
  const [descremaciones, setDescremaciones] = useState<CorridaDescremacion[]>([]);
  const [descremacionesCargadas, setDescremacionesCargadas] = useState(false);
  const [cerrandoDescremacion, setCerrandoDescremacion] = useState<CorridaDescremacion | null>(null);
  const [cerrandoMantequilla, setCerrandoMantequilla] = useState<CorridaMantequilla | null>(null);
  const [accionandoCorrida, setAccionandoCorrida] = useState<number | null>(null);
  const [nuevaMantequilla, setNuevaMantequilla] = useState(false);
  const [nuevaRuta, setNuevaRuta] = useState(false);
  const [cargando, setCargando] = useState(true);
  const [error, setError] = useState("");
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

  const refrescarEjecuciones = async () => {
    try {
      setEjecuciones(await obtenerEjecucionesOperativas());
      return true;
    } catch {
      return false;
    }
  };

  const moverEjecucion = async (ejecucion: EjecucionOperativa) => {
    if (accionando !== null) return;
    setAccionando(ejecucion.id);
    setError("");
    try {
      await transicionarEjecucion(ejecucion.id, "ejecucion", ejecucion.version);
      if (!await refrescarEjecuciones()) {
        setError("La operación se guardó, pero no se pudo actualizar la disponibilidad. Usa actualizar antes de otra acción.");
      }
    } catch (errorPeticion: unknown) {
      setError(mensajeErrorProceso(errorPeticion, "No se pudo iniciar la ejecución."));
      if (esErrorDeEquipo(errorPeticion) || esConflictoVersion(errorPeticion)) {
        await refrescarEjecuciones();
      }
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
    await refrescarEjecuciones();
  };

  const actualizarMantequilla = (corrida: CorridaMantequilla) => {
    setMantequillas((actuales) => actuales.map((item) => item.id === corrida.id ? corrida : item));
  };

  const iniciarCorrida = async (id: number) => {
    if (accionandoCorrida !== null) return;
    setAccionandoCorrida(id); setError("");
    try {
      actualizarMantequilla(await iniciarMantequilla(id));
      if (!await refrescarEjecuciones()) {
        setError("La corrida se inició, pero no se pudo actualizar la disponibilidad.");
      }
    } catch (errorPeticion: unknown) {
      setError(mensajeErrorProceso(
        errorPeticion,
        "No se pudo iniciar la corrida. Revisa equipo, aseo, saldo y estado de la orden.",
      ));
      if (esErrorDeEquipo(errorPeticion)) {
        await refrescarEjecuciones();
      }
    } finally { setAccionandoCorrida(null); }
  };

  const cargarRutas = async () => {
    try {
      const pagina = await obtenerRutasProducto();
      setRutas(pagina.results);
      setRutasCargadas(true);
    } catch { setError("No se pudieron cargar las rutas de proceso."); }
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

  // La evaporación/precondensado se opera en su propio puesto; un enlace
  // guardado o una notificación ya emitida con `?seccion=` sigue aterrizando
  // ahí. Va después de todos los hooks del componente, no al principio de
  // la función: un `return` anterior a ellos los dejaría sin llamar en este
  // render, que es justo lo que evita la regla de los hooks.
  if (seccionSolicitada === "condensacion" || seccionSolicitada === "evaporacion") {
    return <Navigate to="/produccion/evaporacion" replace />;
  }

  return (
    <main className="px-6 py-8 lg:px-10">
      <div className="mx-auto max-w-7xl space-y-8">
        <header>
          <p className="text-sm font-semibold uppercase tracking-wider text-green-700">Procesamiento</p>
          <h1 className="mt-2 text-3xl font-bold text-slate-900">Ejecuciones y trazabilidad</h1>
          <p className="mt-2 max-w-3xl text-slate-600">Entradas, salidas, coproductos, reprocesos y mermas vinculados a los lotes reales.</p>
        </header>

        {error && <ErrorState mensaje={error} />}

        {puedeOperar && siloDescremacion !== null && <FormularioDescremacion siloOrigen={siloDescremacion} ejecuciones={ejecuciones} alConflictoEquipo={async () => { await refrescarEjecuciones(); }} onCerrar={cerrarFormularioDescremacion} onCreada={async (corrida) => { await actualizarDescremacion(corrida); cerrarFormularioDescremacion(); }} />}
        {puedeOperar && cerrandoDescremacion && <CierreDescremacion corrida={cerrandoDescremacion} onCerrar={() => setCerrandoDescremacion(null)} onCerrada={async (corrida) => { await actualizarDescremacion(corrida); setCerrandoDescremacion(null); }} />}
        {puedeOperar && cerrandoMantequilla && <CierreMantequilla corrida={cerrandoMantequilla} onCerrar={() => setCerrandoMantequilla(null)} onCerrada={async (corrida) => { actualizarMantequilla(corrida); setCerrandoMantequilla(null); if (!await refrescarEjecuciones()) setError("El cierre se registró, pero no se pudo actualizar la disponibilidad."); }} />}
        {puedeOperar && nuevaMantequilla && <NuevaMantequilla ejecuciones={ejecuciones} alConflictoEquipo={async () => { await refrescarEjecuciones(); }} onCerrar={() => setNuevaMantequilla(false)} onCreada={async (corrida) => { setMantequillasCargadas(true); setMantequillas((actuales) => [corrida, ...actuales]); await refrescarEjecuciones(); setNuevaMantequilla(false); }} />}
        {puedeConfigurar && nuevaRuta && <NuevaRutaProducto onCerrar={() => setNuevaRuta(false)} onCreada={(ruta) => { setRutasCargadas(true); setRutas((actuales) => [...actuales, ruta]); setNuevaRuta(false); }} />}

        <section className="rounded-2xl border border-slate-200 bg-white p-6">
          <div className="flex flex-wrap items-center justify-between gap-3"><div className="flex items-center gap-3"><GitBranch className="h-5 w-5 text-green-700" /><h2 className="text-lg font-semibold">Rutas configuradas por producto</h2></div>{puedeConfigurar && <button type="button" onClick={() => setNuevaRuta(true)} className="inline-flex items-center gap-2 rounded-xl bg-emerald-700 px-4 py-2 text-sm font-semibold text-white"><Plus className="h-4 w-4" />Nueva ruta</button>}</div>
          <p className="mt-2 text-sm text-slate-600">La secuencia proviene del maestro de procesos; no está codificada en la interfaz.</p>
          <DiagnosticoRutas />
          {!rutasCargadas ? <button type="button" onClick={cargarRutas} className="mt-5 rounded-xl border border-emerald-700 px-4 py-2 text-sm font-semibold text-emerald-700">Cargar rutas</button> : rutas.length === 0 ? <p className="mt-5 text-sm text-slate-600">No hay rutas activas configuradas.</p> : <div className="mt-5 grid gap-4 lg:grid-cols-2">{rutas.map((ruta) => <article key={ruta.id} className="rounded-xl border border-slate-200 p-4"><div className="flex items-start justify-between gap-3"><div><p className="font-semibold text-slate-900">{ruta.producto_nombre}</p><p className="mt-1 text-sm text-green-700">{ruta.proceso_nombre}{ruta.destino ? ` → ${ruta.destino}` : ""}</p>{ruta.insumo_origen_nombre && <p className="mt-1 text-xs font-medium text-amber-700">Origen externo: {ruta.insumo_origen_nombre}</p>}</div><span className="rounded-full bg-slate-100 px-2.5 py-1 text-xs font-medium text-slate-600">Prioridad {ruta.prioridad}</span></div><div className="mt-3 flex flex-wrap items-center gap-2 text-xs text-slate-600">{ruta.etapas.sort((a, b) => a.orden - b.orden).map((etapa, indice) => <span key={etapa.id} className="inline-flex items-center gap-2"><span className="rounded-lg bg-slate-50 px-2 py-1">{etapa.nombre}</span>{indice < ruta.etapas.length - 1 && <ArrowRight className="h-3 w-3" />}</span>)}</div></article>)}</div>}
        </section>

        <section id="proceso-descremacion" className="scroll-mt-6">
          <h2 className="mb-4 text-xl font-semibold text-slate-800">Descremación</h2>
          {!descremacionesCargadas ? <button type="button" onClick={cargarDescremaciones} className="rounded-xl border border-emerald-700 px-4 py-2 text-sm font-semibold text-emerald-700">Cargar corridas de descremación</button> : descremaciones.length === 0 ? <EmptyState titulo="Sin corridas de descremación" detalle="Inicia una desde la acción Descremar disponible en el detalle de un silo." /> : <div className="grid gap-4 lg:grid-cols-2">{descremaciones.map((corrida) => <article key={corrida.id} className="rounded-2xl border border-slate-200 bg-white p-5"><div className="flex items-start justify-between gap-3"><div><p className="font-semibold text-slate-900">{corrida.ejecucion_codigo}</p><p className="mt-1 text-xs text-slate-600">{corrida.equipo_nombre || "Sin equipo"}</p></div><StatusBadge estado={corrida.estado} etiqueta={corrida.estado_etiqueta} /></div><div className="mt-4 rounded-xl bg-slate-50 p-3 text-sm text-slate-700"><span className="font-semibold">{corrida.silo_entera_codigo}</span> · {Number(corrida.litros_entrada).toLocaleString("es-CL")} L · grasa {corrida.grasa_entrada}% · SNG {corrida.sng_entrada}% <ArrowRight className="mx-1 inline h-3.5 w-3.5" /> {corrida.silo_descremada_codigo} + {corrida.estanque_crema_codigo}</div><div className="mt-3 grid gap-2 text-xs sm:grid-cols-2"><p className="rounded-lg bg-sky-50 p-2 text-sky-900"><b>{corrida.producto_descremada_nombre ?? "Descremada histórica"}</b><br />{corrida.litros_descremada ? `${Number(corrida.litros_descremada).toLocaleString("es-CL")} L · grasa ${corrida.grasa_descremada}%` : "Pendiente de salida"}</p><p className="rounded-lg bg-amber-50 p-2 text-amber-900"><b>{corrida.producto_crema_nombre ?? "Crema histórica"}</b><br />{corrida.litros_crema ? `${Number(corrida.litros_crema).toLocaleString("es-CL")} L · grasa ${corrida.grasa_crema}%` : "Pendiente de salida"}</p></div>{corrida.iniciada_en && <p className="mt-3 text-xs text-slate-500">Inició {new Date(corrida.iniciada_en).toLocaleString("es-CL")} · {corrida.iniciada_por_nombre || "operador registrado"}{corrida.finalizada_en ? ` · cerró ${new Date(corrida.finalizada_en).toLocaleString("es-CL")} · ${corrida.finalizada_por_nombre || "operador registrado"}` : ""}</p>}{corrida.estado === "en_curso" && <button type="button" onClick={() => setCerrandoDescremacion(corrida)} className="mt-4 rounded-xl bg-emerald-700 px-4 py-2 text-sm font-semibold text-white">Registrar salidas y cerrar</button>}</article>)}</div>}
        </section>

        <section id="proceso-mantequilla" className="scroll-mt-6">
          <div className="mb-4 flex flex-wrap items-center justify-between gap-3"><h2 className="text-xl font-semibold text-slate-800">Línea de mantequilla</h2>{puedeOperar && <button type="button" onClick={() => setNuevaMantequilla(true)} className="rounded-xl bg-amber-700 px-4 py-2 text-sm font-semibold text-white">Nueva corrida</button>}</div>
          {!mantequillasCargadas ? <button type="button" onClick={cargarMantequillas} className="rounded-xl border border-emerald-700 px-4 py-2 text-sm font-semibold text-emerald-700">Cargar corridas</button> : mantequillas.length === 0 ? <EmptyState titulo="Sin corridas de mantequilla" detalle="Las corridas conservan la relación trazable entre crema, mantequilla y merma declarada." /> : <div className="grid gap-4 lg:grid-cols-2">{mantequillas.map((corrida) => <article key={corrida.id} className="rounded-2xl border border-slate-200 bg-white p-5"><div className="flex items-start justify-between gap-3"><div><p className="font-semibold text-slate-900">{corrida.orden_codigo} · {corrida.mantequilla_codigo}</p><p className="mt-1 text-xs text-slate-600">{corrida.equipo_nombre || "Sin línea"} · {corrida.ejecucion_codigo}</p></div><StatusBadge estado={corrida.estado} etiqueta={corrida.estado_etiqueta} /></div><div className="mt-4 grid grid-cols-2 gap-3 text-sm"><p className="rounded-xl bg-amber-50 p-3 text-amber-900"><span className="block text-xs text-amber-700">Crema utilizada</span>{Number(corrida.kg_crema).toLocaleString("es-CL")} kg · {corrida.crema_codigo}</p><p className="rounded-xl bg-green-50 p-3 text-green-900"><span className="block text-xs text-green-700">Mantequilla</span>{corrida.kg_mantequilla ? `${Number(corrida.kg_mantequilla).toLocaleString("es-CL")} kg` : "Pendiente"}</p><p className="rounded-xl bg-slate-50 p-3 text-slate-700"><span className="block text-xs text-slate-600">Merma</span>{Number(corrida.kg_merma).toLocaleString("es-CL")} kg</p></div>{puedeOperar && corrida.estado === "borrador" && <button type="button" disabled={accionandoCorrida === corrida.id} onClick={() => void iniciarCorrida(corrida.id)} className="mt-4 rounded-xl bg-amber-700 px-4 py-2 text-sm font-semibold text-white disabled:opacity-50">{accionandoCorrida === corrida.id ? "Iniciando…" : "Iniciar con esta crema"}</button>}{puedeOperar && corrida.estado === "en_proceso" && <button type="button" onClick={() => setCerrandoMantequilla(corrida)} className="mt-4 rounded-xl bg-amber-700 px-4 py-2 text-sm font-semibold text-white">Registrar balance y cerrar</button>}{corrida.estado === "pendiente_calidad" && <p className="mt-4 rounded-xl bg-violet-50 px-3 py-2 text-xs font-medium text-violet-800">Producción cerrada; Calidad debe revisar antes de Envasado.</p>}</article>)}</div>}
          {mantequillasCargadas && mantequillas.some((item) => item.finalizada_en) && <div className="mt-3 grid gap-3 lg:grid-cols-2">{mantequillas.filter((item) => item.finalizada_en).map((corrida) => <article key={`auditoria-${corrida.id}`} className="rounded-xl border border-amber-100 bg-amber-50/40 p-4 text-xs text-slate-700"><p className="font-semibold text-amber-950">Registro operativo · {corrida.ejecucion_codigo}</p><p className="mt-2">Inició {corrida.iniciada_en ? new Date(corrida.iniciada_en).toLocaleString("es-CL") : "—"} · {corrida.iniciada_por_nombre || "operador registrado"}</p><p>Cerró {corrida.finalizada_en ? new Date(corrida.finalizada_en).toLocaleString("es-CL") : "—"} · {corrida.finalizada_por_nombre || "operador registrado"}</p>{Object.keys(corrida.controles ?? {}).length > 0 && <div className="mt-2 flex flex-wrap gap-1">{Object.entries(corrida.controles).map(([clave, valor]) => <span key={clave} className="rounded-full bg-white px-2 py-1">{clave.replaceAll("_", " ")}: {String(valor)}</span>)}</div>}</article>)}</div>}
        </section>

        <ReworkProduccion
          ejecuciones={ejecuciones}
          puedeOperar={puedeOperar}
          alConsumir={async () => setEjecuciones(await obtenerEjecucionesOperativas())}
        />

        <TrazabilidadProceso />

        <section>
          <h2 className="mb-1 text-xl font-semibold text-slate-800">Ejecuciones operativas</h2>
          <p className="mb-4 text-sm text-slate-600">Solo pendientes y en curso. El inicio valida nuevamente máquina, ocupación y aseo.</p>
          {cargando ? <PageLoader /> : ejecuciones.length === 0 ? <EmptyState titulo="Sin trabajo operativo pendiente" detalle="Las ejecuciones cerradas no se cargan en esta bandeja." /> : <div className="overflow-x-auto rounded-2xl border border-slate-200 bg-white"><table className="w-full text-left text-sm"><thead className="bg-slate-50 text-slate-600"><tr><th className="px-5 py-3">ID del proceso</th><th className="px-5 py-3">Etapa</th><th className="px-5 py-3">Equipo</th><th className="px-5 py-3">Estado</th><th className="px-5 py-3">Entrada</th><th className="px-5 py-3">Salida</th><th className="px-5 py-3">Acción</th></tr></thead><tbody>{ejecuciones.map((item) => <tr key={item.id} className="border-t border-slate-100"><td className="px-5 py-4 font-semibold text-slate-800">{item.codigo}</td><td className="px-5 py-4">{item.etapa_nombre}</td><td className="px-5 py-4"><span className="block">{item.equipo_nombre ?? "—"}</span>{item.equipo_nombre && <span className="mt-1.5 block"><EstadoEquipo estado={item.estado} ejecucion={item.codigo} /></span>}</td><td className="px-5 py-4"><StatusBadge estado={item.estado} etiqueta={item.estado_etiqueta} /></td><td className="px-5 py-4 text-xs">{item.entradas.join(" + ") || "—"}</td><td className="px-5 py-4 text-xs">{item.salidas.join(" + ") || "—"}</td><td className="px-5 py-4">{item.acciones_permitidas.includes("ejecucion") ? <button type="button" disabled={accionando !== null} onClick={() => void moverEjecucion(item)} className="rounded-lg bg-emerald-700 px-3 py-2 text-xs font-semibold text-white disabled:opacity-50">{accionando === item.id ? "Validando…" : item.estado === "pausada" ? "Reanudar" : "Iniciar"}</button> : <span className="text-xs text-slate-500">Sin acción directa</span>}</td></tr>)}</tbody></table></div>}
        </section>
      </div>
    </main>
  );
}
