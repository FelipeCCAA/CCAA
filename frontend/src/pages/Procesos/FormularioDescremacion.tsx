import { useEffect, useState } from "react";
import { X } from "lucide-react";
import { Link } from "react-router-dom";

import { mensajeDe } from "../../components/seccion/utilidades";
import {
  crearDescremacionGuiada, iniciarDescremacion, obtenerOpcionesAltaDescremacion,
  sugerirBalanceDescremacion,
  type CorridaDescremacion, type EjecucionOperativa, type EtapaProceso,
  type OpcionesAltaDescremacion, type RutaProducto, type SugerenciaDescremacion,
} from "../../services/procesos.service";
import { ocupacionesPorEquipo } from "../../services/disponibilidad-equipos";
import { esErrorDeEquipo, mensajeErrorProceso } from "../../services/errores-proceso";
import { listarAnalisisSilo, type AnalisisSilo } from "../../services/recepcion.service";

const control = "mt-1 w-full rounded-xl border border-slate-300 bg-white px-3 py-2.5";

export default function FormularioDescremacion({
  siloOrigen, ejecuciones, onCerrar, onCreada, alConflictoEquipo,
}: {
  siloOrigen: number;
  ejecuciones: EjecucionOperativa[];
  onCerrar: () => void;
  onCreada: (corrida: CorridaDescremacion) => Promise<void>;
  alConflictoEquipo: () => Promise<void>;
}) {
  const [etapas, setEtapas] = useState<EtapaProceso[]>([]);
  const [equipos, setEquipos] = useState<{ id: number; nombre: string; tipo: string; ocupado_por: string | null }[]>([]);
  const [destinoDescremada, setDestinoDescremada] = useState<{ id: number; codigo: string }[]>([]);
  const [destinosCrema, setDestinosCrema] = useState<{ id: number; codigo: string }[]>([]);
  const [productosDescremada, setProductosDescremada] = useState<OpcionesAltaDescremacion["productos_descremada"]>([]);
  const [productosCrema, setProductosCrema] = useState<OpcionesAltaDescremacion["productos_crema"]>([]);
  const [rutas, setRutas] = useState<RutaProducto[]>([]);
  const [analisis, setAnalisis] = useState<AnalisisSilo[]>([]);
  const [bloqueosConfiguracion, setBloqueosConfiguracion] = useState<{ codigo: string; mensaje: string }[]>([]);
  const [ocupado, setOcupado] = useState(true);
  const [error, setError] = useState("");
  const [calculando, setCalculando] = useState(false);
  const [sugerencia, setSugerencia] = useState<SugerenciaDescremacion | null>(null);
  const [planConfirmado, setPlanConfirmado] = useState(false);
  const [datos, setDatos] = useState({
    codigo: `DES-${new Date().toISOString().replace(/\D/g, "").slice(0, 12)}`,
    etapa: "", equipo: "", analisis: "", litros: "",
    silo_descremada: "", estanque_crema: "",
    producto_descremada: "", producto_crema: "",
    ruta_descremada: "", ruta_crema: "", destino_crema: "siguiente_proceso",
    litros_descremada_plan: "", litros_crema_plan: "",
  });

  useEffect(() => {
    let vigente = true;
    Promise.all([obtenerOpcionesAltaDescremacion(), listarAnalisisSilo(siloOrigen)])
    .then(([opciones, muestras]) => {
      if (!vigente) return;
      const validos = muestras.filter((item) => item.estado === "confirmado" && item.vigente);
      const productoDescremada = opciones.productos_descremada[0];
      const productoCrema = opciones.productos_crema[0];
      setEtapas(opciones.etapas);
      setEquipos(opciones.equipos);
      setDestinoDescremada(opciones.silos_descremada);
      setDestinosCrema(opciones.estanques_crema);
      setProductosDescremada(opciones.productos_descremada);
      setProductosCrema(opciones.productos_crema);
      setRutas(opciones.rutas);
      setBloqueosConfiguracion(opciones.bloqueos);
      setAnalisis(validos);
      setDatos((actual) => ({
        ...actual,
        etapa: opciones.etapas[0] ? String(opciones.etapas[0].id) : "",
        analisis: validos[0] ? String(validos[0].id) : "",
        producto_descremada: String(productoDescremada?.id ?? ""),
        producto_crema: String(productoCrema?.id ?? ""),
        ruta_descremada: String(
          opciones.rutas.find((ruta) => ruta.producto === productoDescremada?.id
            && ruta.etapas.some((etapa) => etapa.tipo === "estandarizacion"))?.id ?? "",
        ),
        ruta_crema: String(
          opciones.rutas.find((ruta) => ruta.producto === productoCrema?.id
            && ruta.etapas.some((etapa) => etapa.tipo === "mantequilla"))?.id ?? "",
        ),
      }));
    }).catch((e) => setError(mensajeDe(e, "No se pudieron cargar los datos de descremación.")))
      .finally(() => { if (vigente) setOcupado(false); });
    return () => { vigente = false; };
  }, [siloOrigen]);

  const muestra = analisis.find((item) => item.id === Number(datos.analisis));
  const rutasDescremada = rutas.filter((ruta) =>
    ruta.producto === Number(datos.producto_descremada)
      && ruta.etapas.some((etapa) => etapa.tipo === "estandarizacion"),
  );
  const rutasCrema = rutas.filter((ruta) => datos.destino_crema === "despacho_directo"
    ? ruta.producto === Number(datos.producto_crema) && ruta.destino_final === "despacho_directo"
    : ruta.producto === Number(datos.producto_crema)
      && ruta.etapas.some((etapa) => ["mantequilla", "estandarizacion"].includes(etapa.tipo)));
  const ocupaciones = ocupacionesPorEquipo(ejecuciones);
  const equipoSeleccionado = equipos.find((item) => item.id === Number(datos.equipo));
  const ocupacionSeleccionada = equipoSeleccionado ? ocupaciones.get(equipoSeleccionado.id) : undefined;
  const equipoBloqueado = Boolean(ocupacionSeleccionada || equipoSeleccionado?.ocupado_por);
  const productoDescremadaSeleccionado = productosDescremada.find(
    (item) => item.id === Number(datos.producto_descremada),
  );
  const productoCremaSeleccionado = productosCrema.find(
    (item) => item.id === Number(datos.producto_crema),
  );
  const productosSinEspecificacion = [
    productoDescremadaSeleccionado,
    productoCremaSeleccionado,
  ].filter((producto) => producto && !producto.tiene_especificacion_silo_vigente);
  const especificacionesListas = Boolean(
    productoDescremadaSeleccionado?.tiene_especificacion_silo_vigente
      && productoCremaSeleccionado?.tiene_especificacion_silo_vigente,
  );

  const invalidarPlan = (cambio: Partial<typeof datos>) => {
    setDatos((actual) => ({
      ...actual, ...cambio,
      litros_descremada_plan: "", litros_crema_plan: "",
    }));
    setSugerencia(null);
    setPlanConfirmado(false);
  };

  const calcularSugerencia = async () => {
    if (!datos.analisis || !datos.litros || !datos.producto_descremada || !datos.producto_crema) {
      setError("Selecciona análisis, litros y ambos productos antes de calcular.");
      return;
    }
    if (!especificacionesListas) {
      setError("Los dos productos necesitan una especificación de silo vigente para calcular la sugerencia.");
      return;
    }
    setCalculando(true);
    setError("");
    try {
      const propuesta = await sugerirBalanceDescremacion({
        analisis_entrada: Number(datos.analisis),
        litros_entrada: Number(datos.litros),
        producto_descremada: Number(datos.producto_descremada),
        producto_crema: Number(datos.producto_crema),
      });
      setSugerencia(propuesta);
      setDatos((actual) => ({
        ...actual,
        litros_descremada_plan: propuesta.litros_descremada_sugeridos,
        litros_crema_plan: propuesta.litros_crema_sugeridos,
      }));
      setPlanConfirmado(false);
    } catch (e) {
      setError(mensajeErrorProceso(e, "No se pudo calcular la sugerencia de reparto."));
    } finally {
      setCalculando(false);
    }
  };

  const guardar = async (e: React.FormEvent) => {
    e.preventDefault();
    if (ocupado) return;
    if (!muestra?.grasa || !muestra.sng) return;
    setOcupado(true);
    setError("");
    try {
      const corrida = await crearDescremacionGuiada({
        codigo: datos.codigo.trim(), etapa: Number(datos.etapa),
        equipo: Number(datos.equipo), silo_entera: siloOrigen,
        analisis_entrada: muestra.id, litros_entrada: Number(datos.litros),
        silo_descremada: Number(datos.silo_descremada),
        estanque_crema: Number(datos.estanque_crema),
        producto_descremada: Number(datos.producto_descremada),
        producto_crema: Number(datos.producto_crema),
        litros_descremada_plan: Number(datos.litros_descremada_plan),
        litros_crema_plan: Number(datos.litros_crema_plan),
        plan_confirmado: true,
        ruta_descremada: Number(datos.ruta_descremada),
        ruta_crema: Number(datos.ruta_crema),
        destino_descremada: "estandarizacion",
        destino_crema: datos.destino_crema as "siguiente_proceso" | "estandarizacion" | "despacho_directo",
      });
      await onCreada(await iniciarDescremacion(corrida.id));
    } catch (e) {
      const mensaje = mensajeErrorProceso(e, "No se pudo crear e iniciar la descremación.");
      if (esErrorDeEquipo(e)) await alConflictoEquipo();
      setError(mensaje);
    } finally {
      setOcupado(false);
    }
  };

  return (
    <div className="fixed inset-0 z-[80] flex items-start justify-center overflow-y-auto bg-slate-950/45 p-4">
      <form onSubmit={guardar} className="my-8 w-full max-w-3xl rounded-2xl bg-white p-6 shadow-xl">
        <div className="flex items-center justify-between"><div><p className="text-xs font-semibold uppercase tracking-wide text-emerald-700">Nueva operación</p><h2 className="mt-1 text-xl font-semibold">Iniciar descremación</h2></div><button type="button" onClick={onCerrar} className="rounded-lg p-2 hover:bg-slate-100"><X className="h-5 w-5" /></button></div>
        <div className="mt-5 grid gap-4 sm:grid-cols-2">
          <Campo texto="Código de ejecución"><input required value={datos.codigo} onChange={(e) => setDatos({ ...datos, codigo: e.target.value })} className={control} /></Campo>
          <Campo texto="Etapa de descremación"><select required value={datos.etapa} onChange={(e) => setDatos({ ...datos, etapa: e.target.value })} className={control}><option value="">Seleccionar…</option>{etapas.map((item) => <option key={item.id} value={item.id}>{item.nombre}</option>)}</select></Campo>
          <Campo texto="Equipo"><select required value={datos.equipo} onChange={(e) => setDatos({ ...datos, equipo: e.target.value })} className={control}><option value="">Seleccionar…</option>{equipos.map((item) => { const ocupacion = ocupaciones.get(item.id); const ocupadoPor = ocupacion?.ejecucion ?? item.ocupado_por; return <option key={item.id} value={item.id} disabled={Boolean(ocupadoPor)}>{item.nombre}{ocupadoPor ? ` · ocupado por ${ocupadoPor}` : " · disponible"}</option>; })}</select></Campo>
          <Campo texto="Análisis vigente del origen"><select required value={datos.analisis} onChange={(e) => invalidarPlan({ analisis: e.target.value })} className={control}><option value="">Seleccionar…</option>{analisis.map((item) => <option key={item.id} value={item.id}>{new Date(item.tomado_en).toLocaleString("es-CL")} · {item.grasa}% MG</option>)}</select></Campo>
          <Campo texto="Litros de entrada"><input required type="number" min="0.01" step="0.01" value={datos.litros} onChange={(e) => invalidarPlan({ litros: e.target.value })} className={control} /></Campo>
          <Campo texto="Destino leche descremada"><select required value={datos.silo_descremada} onChange={(e) => setDatos({ ...datos, silo_descremada: e.target.value })} className={control}><option value="">Seleccionar…</option>{destinoDescremada.map((item) => <option key={item.id} value={item.id}>{item.codigo}</option>)}</select></Campo>
          <Campo texto="TK fisico para crema"><select required value={datos.estanque_crema} onChange={(e) => setDatos({ ...datos, estanque_crema: e.target.value })} className={control}><option value="">Seleccionar…</option>{destinosCrema.map((item) => <option key={item.id} value={item.id}>{item.codigo}</option>)}</select></Campo>
          <Campo texto="Producto intermedio · descremada"><select required value={datos.producto_descremada} onChange={(e) => invalidarPlan({ producto_descremada: e.target.value, ruta_descremada: "" })} className={control}><option value="">Seleccionar…</option>{productosDescremada.map((item) => <option key={item.id} value={item.id}>{item.nombre}</option>)}</select></Campo>
          <Campo texto="Producto intermedio · crema"><select required value={datos.producto_crema} onChange={(e) => invalidarPlan({ producto_crema: e.target.value, ruta_crema: "" })} className={control}><option value="">Seleccionar…</option>{productosCrema.map((item) => <option key={item.id} value={item.id}>{item.nombre}</option>)}</select></Campo>
          <Campo texto="Ruta leche descremada"><select required value={datos.ruta_descremada} onChange={(e) => setDatos({ ...datos, ruta_descremada: e.target.value })} className={control}><option value="">Seleccionar destino productivo…</option>{rutasDescremada.map((ruta) => <option key={ruta.id} value={ruta.id}>{ruta.producto_nombre} · {ruta.proceso_nombre}</option>)}</select></Campo>
          <Campo texto="Destino crema"><select required value={datos.destino_crema} onChange={(e) => setDatos({ ...datos, destino_crema: e.target.value, ruta_crema: "" })} className={control}><option value="siguiente_proceso">Mantequilla / siguiente proceso</option><option value="estandarizacion">Estandarizacion</option><option value="despacho_directo">Despacho directo</option></select></Campo>
          <Campo texto="Ruta crema"><select required value={datos.ruta_crema} onChange={(e) => setDatos({ ...datos, ruta_crema: e.target.value })} className={control}><option value="">Seleccionar ruta…</option>{rutasCrema.map((ruta) => <option key={ruta.id} value={ruta.id}>{ruta.producto_nombre} · {ruta.proceso_nombre}</option>)}</select></Campo>
          <div className="rounded-xl bg-slate-50 px-4 py-3 text-sm text-slate-600"><span className="block text-xs">Composición congelada</span>{muestra ? `${muestra.grasa}% MG · ${muestra.sng}% SNG` : "Selecciona un análisis"}</div>
        </div>
        <section className="mt-5 rounded-2xl border border-sky-200 bg-sky-50 p-4">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div><h3 className="font-semibold text-slate-900">Reparto planificado</h3><p className="text-xs text-slate-600">El sistema sugiere por balance de materia grasa; el operador confirma o ajusta.</p></div>
            <button type="button" disabled={calculando || ocupado || !especificacionesListas} onClick={() => void calcularSugerencia()} className="rounded-xl border border-sky-700 bg-white px-4 py-2 text-sm font-semibold text-sky-800 disabled:opacity-50">{calculando ? "Calculando…" : "Calcular sugerencia"}</button>
          </div>
          {sugerencia && <div className="mt-4 grid gap-3 sm:grid-cols-2">
            <Campo texto="Descremada planificada (L)"><input required type="number" min="0.01" step="0.01" value={datos.litros_descremada_plan} onChange={(e) => { setDatos({ ...datos, litros_descremada_plan: e.target.value }); setPlanConfirmado(false); }} className={control} /></Campo>
            <Campo texto="Crema planificada (L)"><input required type="number" min="0.01" step="0.01" value={datos.litros_crema_plan} onChange={(e) => { setDatos({ ...datos, litros_crema_plan: e.target.value }); setPlanConfirmado(false); }} className={control} /></Campo>
            <p className="text-xs text-slate-600">Referencia descremada: {sugerencia.grasa_descremada_objetivo}% MG</p>
            <p className="text-xs text-slate-600">Referencia crema: {sugerencia.grasa_crema_objetivo}% MG</p>
            <label className="sm:col-span-2 flex items-start gap-3 rounded-xl bg-white p-3 text-sm text-slate-700"><input type="checkbox" className="mt-1" checked={planConfirmado} onChange={(e) => setPlanConfirmado(e.target.checked)} /><span>Confirmo que revisé los volúmenes sugeridos y que estos serán los volúmenes reservados en los TK.</span></label>
          </div>}
        </section>
        {analisis.length === 0 && <p className="mt-4 rounded-xl bg-amber-50 px-4 py-3 text-sm text-amber-800">El silo no tiene un análisis confirmado vigente.</p>}
        {productosSinEspecificacion.length > 0 && <div className="mt-4 rounded-xl bg-amber-50 px-4 py-3 text-sm text-amber-800">
          <p>Falta una especificación de silo vigente para: {productosSinEspecificacion.map((producto) => producto?.nombre).join(" y ")}.</p>
          <p className="mt-1">Solicita a Calidad configurarla o abre <Link to="/maestros?seccion=especificaciones" className="font-semibold underline">Maestros · Especificaciones</Link>.</p>
        </div>}
        {bloqueosConfiguracion.map((bloqueo) => <p key={bloqueo.codigo} className="mt-4 rounded-xl bg-amber-50 px-4 py-3 text-sm text-amber-800">{bloqueo.mensaje}</p>)}
        {productosDescremada.length > 0 && rutasDescremada.length === 0 && <p className="mt-4 rounded-xl bg-amber-50 px-4 py-3 text-sm text-amber-800">La leche descremada intermedia no tiene una ruta activa hacia Estandarización.</p>}
        {productosCrema.length > 0 && rutasCrema.length === 0 && <p className="mt-4 rounded-xl bg-amber-50 px-4 py-3 text-sm text-amber-800">La crema intermedia no tiene una ruta activa para el destino seleccionado.</p>}
        {error && <p className="mt-4 rounded-xl bg-rose-50 px-4 py-3 text-sm text-rose-700">{error}</p>}
        <div className="mt-6 flex justify-end gap-3"><button type="button" onClick={onCerrar} className="px-4 py-2.5 text-sm text-slate-600">Cancelar</button><button disabled={ocupado || bloqueosConfiguracion.length > 0 || !especificacionesListas || !muestra || !datos.equipo || !datos.ruta_descremada || !datos.ruta_crema || !planConfirmado || !datos.litros_descremada_plan || !datos.litros_crema_plan || equipoBloqueado} className="rounded-xl bg-emerald-700 px-5 py-2.5 text-sm font-semibold text-white disabled:opacity-40">{ocupado ? "Preparando…" : "Confirmar reservas e iniciar"}</button></div>
      </form>
    </div>
  );
}

function Campo({ texto, children }: { texto: string; children: React.ReactNode }) {
  return <label className="text-sm text-slate-600">{texto}{children}</label>;
}
