import { useState } from "react";
import { Link } from "react-router-dom";
import { ClipboardCheck, FlaskConical, ShieldAlert, Sparkles } from "lucide-react";

import {
  buscarExpedientes,
  decidirRework,
  liberarResultadoProceso,
  rechazarResultadoProceso,
  type FilaExpediente,
} from "../../services/calidad.service";
import { decidirInspeccion, obtenerInspecciones } from "../../services/inventario.service";
import { obtenerAseos } from "../../services/aseos.service";
import { obtenerSesion } from "../../services/sesion";
import { Aviso, Estado, Indicador, Tarjeta, Vacio } from "../../components/seccion/componentes";
import { useCarga } from "../../components/seccion/utilidades";

const INSPECCIONES_CERRADAS = ["aprobada", "observada", "rechazada", "bloqueada"];
const LIBERACIONES_CERRADAS = ["liberado", "liberado_concesion", "rechazado"];
const ETIQUETAS_PARAMETRO: Record<string, string> = {
  mg: "Grasa", sng: "SNG", st: "Sólidos totales", acidez: "Acidez",
  ph: "pH", temperatura: "Temperatura", proteina: "Proteína", pesoEsp: "Densidad",
};

function mensajeError(error: unknown, respaldo: string) {
  const respuesta = (error as { response?: { data?: { detail?: string; analisis_id?: string } } })
    ?.response?.data;
  return respuesta?.detail || respuesta?.analisis_id || respaldo;
}

function CentroCalidad() {
  // Tres lecturas independientes y acotadas: el centro carga únicamente lo
  // que Calidad necesita, no todas las tablas de Inventario ni el histórico
  // completo de Producción.
  const expedientes = useCarga(async () => buscarExpedientes({ pagina: 1, incluir_procesos: true }));
  const inspecciones = useCarga(obtenerInspecciones);
  const aseos = useCarga(obtenerAseos);
  const sesion = obtenerSesion();
  const puedeDecidir = ["calidad", "admin"].includes(sesion?.usuario.rol ?? "")
    || sesion?.usuario.perfil?.area === "calidad";

  const [analisisElegido, setAnalisisElegido] = useState<Record<number, string>>({});
  const [errorProceso, setErrorProceso] = useState("");
  const [errorRework, setErrorRework] = useState("");
  const [guardandoRework, setGuardandoRework] = useState(false);
  const [loteAdicionalRework, setLoteAdicionalRework] = useState("");
  const [reworkEditando, setReworkEditando] = useState<{
    loteId: number;
    estado: "aprobado" | "bloqueado" | "destruido";
    origen: "rechazo" | "saco_danado" | "excedente" | "recuperable";
    cantidad: string;
    motivo: string;
    observacion: string;
  } | null>(null);
  const lotes = (expedientes.datos?.resultados ?? []) as FilaExpediente[];
  const resultadosProceso = expedientes.datos?.procesos ?? [];
  const procesosPendientes = resultadosProceso.filter((item) => item.estado === "pendiente");
  const porRevisar = lotes.filter((fila) => !LIBERACIONES_CERRADAS.includes(fila.liberacion?.estado ?? "pendiente"));
  const liberados = lotes.filter((fila) => fila.liberacion?.estado === "liberado" || fila.liberacion?.estado === "liberado_concesion");
  const rechazados = lotes.filter((fila) => fila.liberacion?.estado === "rechazado");
  const materiales = inspecciones.datos ?? [];
  const materialesPendientes = materiales.filter((item) => !INSPECCIONES_CERRADAS.includes(item.estado));
  const aseosPendientes = (aseos.datos ?? []).filter((aseo) => aseo.verificacion !== "conforme");

  const decidirMaterial = async (id: number, estado: "aprobada" | "rechazada") => {
    await decidirInspeccion(id, estado, estado === "rechazada" ? "Rechazado por Calidad" : "Liberado por Calidad");
    await inspecciones.recargar();
  };

  const liberarProceso = async (id: number) => {
    const analisisId = Number(analisisElegido[id]);
    if (!analisisId) return;
    try {
      setErrorProceso("");
      await liberarResultadoProceso(id, analisisId);
      await expedientes.recargar();
    } catch (error) {
      setErrorProceso(mensajeError(error, "No se pudo liberar el resultado intermedio."));
    }
  };

  const rechazarProceso = async (id: number) => {
    const motivo = window.prompt("Motivo del rechazo:")?.trim();
    if (!motivo) return;
    try {
      setErrorProceso("");
      await rechazarResultadoProceso(id, motivo);
      await expedientes.recargar();
    } catch {
      setErrorProceso("No se pudo rechazar el resultado intermedio.");
    }
  };

  const abrirRework = (
    fila: FilaExpediente,
    estado: "aprobado" | "bloqueado" | "destruido",
  ) => {
    setErrorRework("");
    setReworkEditando({
      loteId: fila.lote.id, estado,
      origen: (fila.rework?.origen as "rechazo" | "saco_danado" | "excedente" | "recuperable") ?? "rechazo",
      cantidad: fila.rework?.cantidad_kg ?? fila.lote.kg_producidos,
      motivo: fila.rework?.motivo ?? "",
      observacion: fila.rework?.observacion_calidad ?? "",
    });
  };

  const guardarRework = async (evento: React.FormEvent) => {
    evento.preventDefault();
    if (!reworkEditando) return;
    const cantidad = Number(reworkEditando.cantidad);
    if (!Number.isFinite(cantidad) || cantidad <= 0 || !reworkEditando.motivo.trim()) {
      setErrorRework("Ingresa una cantidad válida y explica la condición del material.");
      return;
    }
    setGuardandoRework(true); setErrorRework("");
    try {
      await decidirRework(reworkEditando.loteId, {
        estado: reworkEditando.estado, origen: reworkEditando.origen,
        cantidad_kg: cantidad, motivo: reworkEditando.motivo.trim(),
        observacion_calidad: reworkEditando.observacion.trim(),
      });
      setReworkEditando(null);
      await expedientes.recargar();
    } catch (error) {
      setErrorRework(mensajeError(error, "No se pudo registrar la decisión de rework."));
    } finally { setGuardandoRework(false); }
  };

  return (
    <div className="mx-auto max-w-7xl space-y-7 px-8 py-10">
      <header>
        <p className="text-sm font-semibold uppercase tracking-wider text-emerald-700">Calidad</p>
        <h1 className="mt-2 text-3xl font-bold text-slate-800">Centro de calidad</h1>
        <p className="mt-2 max-w-3xl text-slate-600">Una sola bandeja para verificar la producción, liberar materiales de embalaje y revisar los aseos que respaldan cada fase.</p>
      </header>

      <section className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <Indicador etiqueta="Resultados por revisar" valor={porRevisar.length + procesosPendientes.length} Icono={FlaskConical} tono={porRevisar.length + procesosPendientes.length ? "alerta" : "normal"} />
        <Indicador etiqueta="Materiales en cuarentena" valor={materialesPendientes.length} Icono={ShieldAlert} tono={materialesPendientes.length ? "alerta" : "normal"} />
        <Indicador etiqueta="Lotes liberados" valor={liberados.length} Icono={ClipboardCheck} />
        <Indicador etiqueta="Aseos por verificar" valor={aseosPendientes.length} Icono={Sparkles} tono={aseosPendientes.length ? "alerta" : "normal"} />
      </section>

      <Tarjeta titulo="Resultados intermedios de proceso" descripcion="Precondensados y condensados quedan bloqueados en su silo hasta que Calidad seleccione un análisis confirmado y tome una decisión.">
        {errorProceso && <Aviso>{errorProceso}</Aviso>}
        {expedientes.error ? <Aviso>No se pudo cargar la cola de procesos.</Aviso> : procesosPendientes.length === 0 ? <Vacio>No hay resultados intermedios pendientes.</Vacio> : (
          <div className="grid gap-3 lg:grid-cols-2">
            {procesosPendientes.map((item) => {
              const seleccionado = item.analisis_disponibles.find(
                (analisis) => analisis.id === Number(analisisElegido[item.id]),
              );
              const puedeLiberarAnalisis = seleccionado
                && (seleccionado.resultado === null || seleccionado.resultado === "conforme");
              return (
              <div key={item.id} className="rounded-xl border border-amber-200 bg-amber-50/40 p-4">
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <p className="font-semibold text-slate-800">{item.tipo} · {item.corrida_codigo}</p>
                    <p className="text-sm text-slate-600">{item.producto_nombre} · {item.cantidad} {item.unidad}</p>
                    <p className="text-xs text-slate-500">{item.equipo_nombre || "Sin equipo"} → {item.silo_destino_codigo}</p>
                    <p className="mt-1 text-xs font-medium text-amber-800">{item.clasificacion} · destino: {item.destino}</p>
                  </div>
                  <Estado valor={item.estado} />
                </div>
                {item.especificacion ? (
                  <div className="mt-3 rounded-lg border border-emerald-200 bg-white p-3">
                    <p className="text-xs font-semibold text-emerald-800">Especificación vigente · v{item.especificacion.version}</p>
                    <div className="mt-2 flex flex-wrap gap-1.5">
                      {Object.entries(item.especificacion.rangos).map(([clave, rango]) => (
                        <span key={clave} className="rounded-full bg-emerald-50 px-2 py-1 text-xs text-emerald-900">
                          {ETIQUETAS_PARAMETRO[clave] ?? clave}: {rango.min ?? "—"} a {rango.max ?? "—"}{rango.obligatorio ? " · obligatorio" : ""}
                        </span>
                      ))}
                    </div>
                  </div>
                ) : item.analisis_disponibles.some((analisis) => analisis.resultado === "sin_especificacion") ? (
                  <p className="mt-3 rounded-lg bg-red-50 px-3 py-2 text-sm font-medium text-red-800">Falta una especificación vigente para este producto. No se puede liberar.</p>
                ) : null}
                {item.analisis_disponibles.length === 0 ? (
                  <p className="mt-3 text-sm text-amber-800">Falta un análisis confirmado tomado después de finalizar la corrida.</p>
                ) : (
                  <select
                    value={analisisElegido[item.id] ?? ""}
                    onChange={(evento) => setAnalisisElegido((actual) => ({ ...actual, [item.id]: evento.target.value }))}
                    className="mt-3 w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm"
                  >
                    <option value="">Selecciona el análisis correspondiente…</option>
                    {item.analisis_disponibles.map((analisis) => (
                      <option key={analisis.id} value={analisis.id}>
                        {new Date(analisis.tomado_en).toLocaleString("es-CL")} · grasa {analisis.grasa ?? "—"} · SNG {analisis.sng ?? "—"} · {analisis.resultado?.replaceAll("_", " ") ?? "control firmado"}
                      </option>
                    ))}
                  </select>
                )}
                {seleccionado?.resultado === "sin_analisis" && (
                  <p className="mt-2 text-sm text-red-700">Faltan parámetros obligatorios: {seleccionado.faltantes.map((clave) => ETIQUETAS_PARAMETRO[clave] ?? clave).join(", ")}.</p>
                )}
                {seleccionado?.resultado === "no_conforme" && (
                  <div className="mt-2 text-sm text-red-700">
                    {seleccionado.desviaciones.map((desvio) => (
                      <p key={desvio.parametro}>{ETIQUETAS_PARAMETRO[desvio.parametro] ?? desvio.parametro}: {desvio.valor ?? "—"} fuera de {desvio.min ?? "—"} a {desvio.max ?? "—"}.</p>
                    ))}
                  </div>
                )}
                {puedeDecidir && (
                  <div className="mt-3 flex gap-2">
                    <button disabled={!puedeLiberarAnalisis} onClick={() => void liberarProceso(item.id)} className="rounded-lg bg-emerald-700 px-3 py-1.5 text-xs font-semibold text-white disabled:opacity-40">Liberar etapa</button>
                    <button onClick={() => void rechazarProceso(item.id)} className="rounded-lg bg-red-50 px-3 py-1.5 text-xs font-semibold text-red-700">Rechazar</button>
                  </div>
                )}
              </div>
              );
            })}
          </div>
        )}
      </Tarjeta>

      <section className="grid items-start gap-7 xl:grid-cols-3">
      <Tarjeta titulo="Productos que requieren aprobación" descripcion="Cada lote toma automáticamente su checklist por familia y fase. Abre el expediente para analizar, verificar y liberar o rechazar.">
        {expedientes.error ? <Aviso>No se pudo cargar la cola de productos.</Aviso> : porRevisar.length === 0 ? <Vacio>No hay lotes pendientes de Calidad.</Vacio> : (
          <div className="space-y-3">
            {porRevisar.map((fila) => (
              <Link key={fila.lote.id} to={`/calidad/expedientes?lote=${fila.lote.id}`} className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-slate-200 px-4 py-3 hover:bg-slate-50">
                <div>
                  <p className="font-medium text-slate-800">{fila.lote.producto_nombre} · {fila.lote.codigo_lote}</p>
                  <p className="text-sm text-slate-600">Análisis: {fila.calidad?.etiqueta ?? "sin análisis"} · Checklist: {fila.avance.completados}/{fila.avance.total}</p>
                  {fila.bloqueos.length > 0 && <p className="mt-1 text-xs text-amber-700">{fila.bloqueos[0]}</p>}
                </div>
                <Estado valor={fila.liberacion?.estado ?? "pendiente"} />
              </Link>
            ))}
          </div>
        )}
      </Tarjeta>

      <Tarjeta titulo="Insumos por confirmar para Bodega" descripcion="Bolsas, etiquetas e insumos en cuarentena. Al liberarlos quedan disponibles para Producción; al rechazarlos van a la ubicación de rechazados.">
        {inspecciones.error ? <Aviso>No se pudo cargar la cuarentena.</Aviso> : materialesPendientes.length === 0 ? <Vacio>No hay materiales esperando decisión.</Vacio> : (
          <div className="space-y-3">
            {materialesPendientes.map((item) => (
              <div key={item.id} className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-amber-200 bg-amber-50/40 px-4 py-3">
                <div><p className="font-medium text-slate-800">{item.insumo_nombre} · lote {item.lote_codigo}</p><p className="text-sm text-slate-600">Estado: {item.estado}</p></div>
                {puedeDecidir && <div className="flex gap-2"><button onClick={() => void decidirMaterial(item.id, "aprobada")} className="rounded-lg bg-emerald-700 px-3 py-1.5 text-xs font-semibold text-white">Liberar</button><button onClick={() => void decidirMaterial(item.id, "rechazada")} className="rounded-lg bg-red-50 px-3 py-1.5 text-xs font-semibold text-red-700">Rechazar</button></div>}
              </div>
            ))}
          </div>
        )}
      </Tarjeta>

        <Tarjeta titulo="Aseos que requieren verificación" descripcion="No bloquean la operación por ahora, pero advierten antes de usar el silo o la máquina asociada.">
          {aseos.error ? <Aviso>No se pudieron cargar los aseos.</Aviso> : aseosPendientes.length === 0 ? <Vacio>Sin aseos pendientes de verificación.</Vacio> : <div className="space-y-2">{aseosPendientes.slice(0, 12).map((aseo) => <Link key={aseo.id} to="/calidad/inocuidad" className="flex items-center justify-between rounded-xl bg-slate-50 px-4 py-3 text-sm hover:bg-slate-100"><span>{aseo.objetivo_nombre} · {aseo.tipo_aseo_etiqueta}</span><Estado valor={aseo.verificacion} /></Link>)}</div>}
        </Tarjeta>
      </section>

      <Tarjeta titulo="Rework y material rechazado" descripcion="Un rechazo no vuelve automáticamente a Producción. Calidad define una cantidad trazable y decide aprobar, bloquear o destruir.">
        {errorRework && <Aviso>{errorRework}</Aviso>}
        {liberados.some((fila) => !fila.rework) && (
          <div className="mb-4 rounded-xl border border-sky-200 bg-sky-50 p-3">
            <p className="text-sm font-semibold text-sky-900">¿Saco dañado, excedente o material recuperable?</p>
            <p className="mt-1 text-xs text-sky-700">También puedes identificar rework sobre un lote liberado sin cambiar su liberación comercial completa.</p>
            <div className="mt-3 flex flex-wrap gap-2">
              <select value={loteAdicionalRework} onChange={(e) => setLoteAdicionalRework(e.target.value)} className="min-w-64 flex-1 rounded-lg border border-sky-300 bg-white px-3 py-2 text-sm"><option value="">Seleccionar lote liberado…</option>{liberados.filter((fila) => !fila.rework).map((fila) => <option key={fila.lote.id} value={fila.lote.id}>{fila.lote.codigo_lote} · {fila.lote.producto_nombre} · {fila.lote.kg_producidos} kg</option>)}</select>
              <button type="button" disabled={!loteAdicionalRework} onClick={() => { const fila = liberados.find((item) => item.lote.id === Number(loteAdicionalRework)); if (fila) abrirRework(fila, "aprobado"); }} className="rounded-lg bg-sky-700 px-3 py-2 text-xs font-semibold text-white disabled:opacity-40">Evaluar rework</button>
            </div>
          </div>
        )}
        {rechazados.length === 0 ? <Vacio>No hay lotes rechazados en la página actual.</Vacio> : (
          <div className="grid gap-3 lg:grid-cols-2">
            {rechazados.map((fila) => (
              <div key={fila.lote.id} className="rounded-xl border border-rose-200 bg-rose-50/40 p-4">
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <p className="font-semibold text-slate-800">{fila.lote.producto_nombre} · {fila.lote.codigo_lote}</p>
                    <p className="text-sm text-slate-600">{fila.lote.kg_producidos} kg producidos</p>
                    {fila.rework && <><p className="mt-1 text-xs text-slate-600">Rework: {fila.rework.cantidad_kg} kg · {fila.rework.motivo}</p><p className="mt-1 text-xs text-slate-500">Decidió {fila.rework.decidido_por ?? "Calidad"}{fila.rework.decidido_en ? ` · ${new Date(fila.rework.decidido_en).toLocaleString("es-CL")}` : ""}{fila.rework.observacion_calidad ? ` · ${fila.rework.observacion_calidad}` : ""}</p></>}
                  </div>
                  <Estado valor={fila.rework?.estado ?? "pendiente_rework"} />
                </div>
                {puedeDecidir && fila.rework?.estado !== "destruido" && reworkEditando?.loteId !== fila.lote.id && (
                  <div className="mt-3 flex flex-wrap gap-2">
                    <button onClick={() => abrirRework(fila, "aprobado")} className="rounded-lg bg-emerald-700 px-3 py-1.5 text-xs font-semibold text-white">Aprobar rework</button>
                    <button onClick={() => abrirRework(fila, "bloqueado")} className="rounded-lg bg-amber-100 px-3 py-1.5 text-xs font-semibold text-amber-800">Bloquear</button>
                    <button onClick={() => abrirRework(fila, "destruido")} className="rounded-lg bg-red-100 px-3 py-1.5 text-xs font-semibold text-red-800">Registrar destrucción</button>
                  </div>
                )}
                {reworkEditando?.loteId === fila.lote.id && (
                  <form onSubmit={guardarRework} className="mt-4 grid gap-3 rounded-xl border border-slate-200 bg-white p-3 sm:grid-cols-2">
                    <div className="sm:col-span-2"><p className="text-sm font-semibold text-slate-800">Decisión: {reworkEditando.estado.replaceAll("_", " ")}</p><p className="text-xs text-slate-500">La destrucción es irreversible. La aprobación habilita el saldo en Producción.</p></div>
                    <label className="text-xs font-semibold text-slate-600">Origen del material<select value={reworkEditando.origen} onChange={(e) => setReworkEditando({ ...reworkEditando, origen: e.target.value as typeof reworkEditando.origen })} className="mt-1 w-full rounded-lg border border-slate-300 bg-white px-2 py-2 text-sm font-normal"><option value="rechazo">Producto rechazado</option><option value="saco_danado">Saco dañado</option><option value="excedente">Excedente</option><option value="recuperable">Material recuperable</option></select></label>
                    <label className="text-xs font-semibold text-slate-600">Cantidad identificada (kg)<input required type="number" min="0.001" step="0.001" max={fila.lote.kg_producidos} value={reworkEditando.cantidad} onChange={(e) => setReworkEditando({ ...reworkEditando, cantidad: e.target.value })} className="mt-1 w-full rounded-lg border border-slate-300 px-2 py-2 text-sm font-normal" /></label>
                    <label className="text-xs font-semibold text-slate-600 sm:col-span-2">Motivo y condición<textarea required value={reworkEditando.motivo} onChange={(e) => setReworkEditando({ ...reworkEditando, motivo: e.target.value })} className="mt-1 min-h-20 w-full rounded-lg border border-slate-300 px-2 py-2 text-sm font-normal" /></label>
                    <label className="text-xs font-semibold text-slate-600 sm:col-span-2">Observación de Calidad<textarea value={reworkEditando.observacion} onChange={(e) => setReworkEditando({ ...reworkEditando, observacion: e.target.value })} className="mt-1 min-h-16 w-full rounded-lg border border-slate-300 px-2 py-2 text-sm font-normal" /></label>
                    <div className="flex justify-end gap-2 sm:col-span-2"><button type="button" onClick={() => setReworkEditando(null)} className="px-3 py-2 text-xs text-slate-600">Cancelar</button><button disabled={guardandoRework} className={`rounded-lg px-3 py-2 text-xs font-semibold text-white disabled:opacity-50 ${reworkEditando.estado === "aprobado" ? "bg-emerald-700" : reworkEditando.estado === "destruido" ? "bg-red-700" : "bg-amber-700"}`}>{guardandoRework ? "Guardando…" : "Confirmar decisión"}</button></div>
                  </form>
                )}
              </div>
            ))}
          </div>
        )}
        {reworkEditando && !rechazados.some((fila) => fila.lote.id === reworkEditando.loteId) && (() => {
          const fila = liberados.find((item) => item.lote.id === reworkEditando.loteId);
          if (!fila) return null;
          return <form onSubmit={guardarRework} className="mt-4 grid gap-3 rounded-xl border border-sky-200 bg-white p-4 sm:grid-cols-2"><div className="sm:col-span-2"><p className="font-semibold text-slate-800">{fila.lote.producto_nombre} · {fila.lote.codigo_lote}</p><p className="text-xs text-slate-500">Define qué parte del lote se convierte en rework; el resto conserva su estado.</p></div><label className="text-xs font-semibold text-slate-600">Origen<select value={reworkEditando.origen} onChange={(e) => setReworkEditando({ ...reworkEditando, origen: e.target.value as typeof reworkEditando.origen })} className="mt-1 w-full rounded-lg border border-slate-300 bg-white px-2 py-2 text-sm font-normal"><option value="saco_danado">Saco dañado</option><option value="excedente">Excedente</option><option value="recuperable">Material recuperable</option><option value="rechazo">Producto rechazado</option></select></label><label className="text-xs font-semibold text-slate-600">Cantidad (kg)<input required type="number" min="0.001" step="0.001" max={fila.lote.kg_producidos} value={reworkEditando.cantidad} onChange={(e) => setReworkEditando({ ...reworkEditando, cantidad: e.target.value })} className="mt-1 w-full rounded-lg border border-slate-300 px-2 py-2 text-sm font-normal" /></label><label className="text-xs font-semibold text-slate-600 sm:col-span-2">Motivo<textarea required value={reworkEditando.motivo} onChange={(e) => setReworkEditando({ ...reworkEditando, motivo: e.target.value })} className="mt-1 min-h-20 w-full rounded-lg border border-slate-300 px-2 py-2 text-sm font-normal" /></label><div className="flex flex-wrap justify-end gap-2 sm:col-span-2"><button type="button" onClick={() => setReworkEditando(null)} className="px-3 py-2 text-xs text-slate-600">Cancelar</button><button type="button" onClick={() => setReworkEditando({ ...reworkEditando, estado: "bloqueado" })} className="rounded-lg bg-amber-100 px-3 py-2 text-xs font-semibold text-amber-800">Dejar bloqueado</button><button disabled={guardandoRework} className="rounded-lg bg-emerald-700 px-3 py-2 text-xs font-semibold text-white disabled:opacity-50">{guardandoRework ? "Guardando…" : reworkEditando.estado === "bloqueado" ? "Confirmar bloqueo" : "Aprobar rework"}</button></div></form>;
        })()}
      </Tarjeta>

      <Tarjeta titulo="Historial de Calidad" descripcion="Liberados y rechazados quedan visibles para trazabilidad; Bodega no puede modificar estas decisiones.">
        {liberados.length + rechazados.length === 0 ? <Vacio>Sin decisiones recientes.</Vacio> : <div className="grid gap-2 md:grid-cols-2">{[...liberados, ...rechazados].slice(0, 12).map((fila) => <div key={fila.lote.id} className="flex items-center justify-between rounded-xl bg-slate-50 px-4 py-3 text-sm"><span>{fila.lote.producto_nombre} · {fila.lote.codigo_lote}</span><Estado valor={fila.liberacion?.estado ?? "pendiente"} /></div>)}</div>}
      </Tarjeta>
    </div>
  );
}

export default CentroCalidad;
