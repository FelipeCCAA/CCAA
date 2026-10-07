import { useEffect, useId, useRef, useState, type FormEvent, type ReactNode } from "react";
import { X } from "lucide-react";
import { Link } from "react-router-dom";

import ConfirmarAccion from "../../components/operacion/ConfirmarAccion";
import {
  prepararDescremado, type DestinoRamaCrema, type PuestoDescremado,
} from "../../services/descremado.service";
import { mensajeErrorProceso } from "../../services/errores-proceso";
import { cantidad } from "../../services/formato";
import {
  obtenerOpcionesAltaDescremacion, sugerirBalanceDescremacion,
  type OpcionesAltaDescremacion, type SugerenciaDescremacion,
} from "../../services/procesos.service";

const control = "mt-1 w-full rounded-xl border border-slate-300 bg-white px-3 py-2.5 text-sm outline-none focus:border-emerald-600";

/*
  «Preparar descremado»: silo → descremadora → litros → producto y TK de cada
  rama → destino y ruta de la crema → sugerencia → confirmación. Silos,
  descremadoras y TK vienen del puesto (`descremaciones/puesto/`), con la
  regla que «Preparar» vuelve a aplicar: no hay selector de análisis —el
  servidor usa el último confirmado del silo— ni de código. Preparar no
  inicia: la tarjeta habilita «Iniciar descremado» cuando el servidor lo
  permite.
*/
export default function PrepararDescremado({ puesto, siloInicial, equipoInicial, alCerrar, alPreparar }: {
  puesto: PuestoDescremado;
  siloInicial?: number;
  equipoInicial?: number;
  alCerrar: () => void;
  alPreparar: (codigo: string) => void;
}) {
  const [opciones, setOpciones] = useState<OpcionesAltaDescremacion | null>(null);
  const [silo, setSilo] = useState(siloInicial ? String(siloInicial) : "");
  const [equipo, setEquipo] = useState(equipoInicial ? String(equipoInicial) : "");
  const [etapaElegida, setEtapaElegida] = useState("");
  const [litros, setLitros] = useState("");
  const [productoDescremada, setProductoDescremada] = useState("");
  const [productoCrema, setProductoCrema] = useState("");
  const [tkDescremada, setTkDescremada] = useState("");
  const [tkCrema, setTkCrema] = useState("");
  const [ramaCrema, setRamaCrema] = useState<DestinoRamaCrema>("siguiente_proceso");
  const [rutaDescremada, setRutaDescremada] = useState("");
  const [rutaCrema, setRutaCrema] = useState("");
  const [sugerencia, setSugerencia] = useState<SugerenciaDescremacion | null>(null);
  const [planDescremada, setPlanDescremada] = useState("");
  const [planCrema, setPlanCrema] = useState("");
  const [planConfirmado, setPlanConfirmado] = useState(false);
  const [calculando, setCalculando] = useState(false);
  const [revisando, setRevisando] = useState(false);
  const [guardando, setGuardando] = useState(false);
  const [error, setError] = useState("");
  const enviando = useRef(false);
  const idTitulo = useId();

  useEffect(() => {
    let vigente = true;
    obtenerOpcionesAltaDescremacion()
      .then((datos) => {
        if (!vigente) return;
        const descremada = datos.productos_descremada[0];
        const crema = datos.productos_crema[0];
        setOpciones(datos);
        setProductoDescremada(String(descremada?.id ?? ""));
        setProductoCrema(String(crema?.id ?? ""));
        setRutaDescremada(String(datos.rutas.find((ruta) => ruta.producto === descremada?.id
          && ruta.etapas.some((etapa) => etapa.tipo === "estandarizacion"))?.id ?? ""));
        setRutaCrema(String(datos.rutas.find((ruta) => ruta.producto === crema?.id
          && ruta.etapas.some((etapa) => etapa.tipo === "mantequilla"))?.id ?? ""));
      })
      .catch((causa) => {
        if (vigente) setError(mensajeErrorProceso(causa, "No se pudieron cargar productos y rutas de descremado."));
      });
    return () => { vigente = false; };
  }, []);

  const etapas = opciones?.etapas ?? [];
  // Con una sola etapa activa no se pregunta: se elige sola.
  const etapa = etapas.length === 1 ? String(etapas[0].id) : etapaElegida;
  const origen = puesto.origenes.find((item) => item.id === Number(silo));
  const libres = puesto.descremadoras.filter((item) => item.estado === "disponible" && item.motivos_para_tomar.length === 0);
  const maquina = libres.find((item) => item.equipo_id === Number(equipo));
  const destinoDescremada = puesto.destinos_descremada.find((item) => item.id === Number(tkDescremada));
  const destinoCrema = puesto.destinos_crema.find((item) => item.id === Number(tkCrema));
  const rutas = opciones?.rutas ?? [];
  const rutasDescremada = rutas.filter((ruta) => ruta.producto === Number(productoDescremada)
    && ruta.etapas.some((e) => e.tipo === "estandarizacion"));
  const rutasCrema = rutas.filter((ruta) => ramaCrema === "despacho_directo"
    ? ruta.producto === Number(productoCrema) && ruta.destino_final === "despacho_directo"
    : ruta.producto === Number(productoCrema) && ruta.etapas.some((e) => ["mantequilla", "estandarizacion"].includes(e.tipo)));
  const sinEspecificacion = [
    opciones?.productos_descremada.find((item) => item.id === Number(productoDescremada)),
    opciones?.productos_crema.find((item) => item.id === Number(productoCrema)),
  ].filter((item) => item && !item.tiene_especificacion_silo_vigente);
  const bloqueos = opciones?.bloqueos ?? [];
  const excedeDescremada = Boolean(destinoDescremada && Number(planDescremada) > Number(destinoDescremada.libre_l));
  const excedeCrema = Boolean(destinoCrema && Number(planCrema) > Number(destinoCrema.libre_l));
  const completo = Boolean(
    opciones && bloqueos.length === 0 && sinEspecificacion.length === 0 && etapa
    && origen?.analisis && !origen.motivo && maquina && Number(litros) > 0
    && destinoDescremada && destinoCrema && rutaDescremada && rutaCrema
    && sugerencia && planConfirmado && Number(planDescremada) > 0 && Number(planCrema) > 0,
  );

  /* Cambiar litros o productos invalida el reparto: se vuelve a calcular. */
  const invalidarPlan = () => {
    setSugerencia(null);
    setPlanDescremada("");
    setPlanCrema("");
    setPlanConfirmado(false);
  };

  const calcular = async () => {
    if (!origen?.analisis || !(Number(litros) > 0)) {
      setError("Elige el silo de origen y los litros antes de calcular.");
      return;
    }
    setCalculando(true);
    setError("");
    try {
      const propuesta = await sugerirBalanceDescremacion({
        analisis_entrada: origen.analisis.id, litros_entrada: Number(litros),
        producto_descremada: Number(productoDescremada), producto_crema: Number(productoCrema),
      });
      setSugerencia(propuesta);
      setPlanDescremada(propuesta.litros_descremada_sugeridos);
      setPlanCrema(propuesta.litros_crema_sugeridos);
      setPlanConfirmado(false);
    } catch (causa) {
      setError(mensajeErrorProceso(causa, "No se pudo calcular la sugerencia de reparto."));
    } finally {
      setCalculando(false);
    }
  };

  const revisar = (evento: FormEvent) => {
    evento.preventDefault();
    if (completo) setRevisando(true);
  };

  const confirmar = async () => {
    if (enviando.current || !origen || !maquina || !destinoDescremada || !destinoCrema) return;
    enviando.current = true;
    setGuardando(true);
    setError("");
    try {
      const corrida = await prepararDescremado({
        etapa: Number(etapa), equipo: maquina.equipo_id, silo_entera: origen.id,
        litros_entrada: Number(litros),
        silo_descremada: destinoDescremada.id, estanque_crema: destinoCrema.id,
        producto_descremada: Number(productoDescremada), producto_crema: Number(productoCrema),
        litros_descremada_plan: Number(planDescremada), litros_crema_plan: Number(planCrema),
        plan_confirmado: true,
        ruta_descremada: Number(rutaDescremada), ruta_crema: Number(rutaCrema),
        destino_descremada: "estandarizacion", destino_crema: ramaCrema,
      });
      alPreparar(corrida.ejecucion_codigo);
    } catch (causa) {
      setError(mensajeErrorProceso(causa, "No se pudo preparar el descremado."));
      setRevisando(false);
    } finally {
      enviando.current = false;
      setGuardando(false);
    }
  };

  return (
    <div className="fixed inset-0 z-[70] overflow-y-auto bg-slate-950/45 p-4" role="dialog" aria-modal="true" aria-labelledby={idTitulo}>
      <form onSubmit={revisar} className="mx-auto my-8 max-w-3xl space-y-5 rounded-2xl bg-white p-6 shadow-xl">
        <div className="flex items-start justify-between gap-4">
          <div>
            <p className="text-xs font-bold uppercase tracking-wider text-emerald-700">Puesto de Descremado</p>
            <h2 id={idTitulo} className="mt-1 text-2xl font-bold text-slate-900">Preparar descremado</h2>
            <p className="mt-2 text-sm text-slate-600">Reserva el silo y los dos TK y toma la descremadora. El descremado se inicia después, desde la tarjeta.</p>
          </div>
          <button type="button" onClick={alCerrar} disabled={guardando} className="rounded-lg p-2 hover:bg-slate-100" aria-label="Cerrar"><X className="h-5 w-5" /></button>
        </div>

        <fieldset className="grid gap-4 sm:grid-cols-2" disabled={revisando}>
          <Campo texto="Silo de origen">
            <select required value={silo} onChange={(e) => { setSilo(e.target.value); invalidarPlan(); }} className={control}>
              <option value="">Seleccionar…</option>
              {puesto.origenes.map((item) => (
                <option key={item.id} value={item.id} disabled={Boolean(item.motivo)}>
                  {item.codigo} · {cantidad(item.saldo_l, "L")}{item.motivo ? " · no disponible" : ""}
                </option>
              ))}
            </select>
          </Campo>
          <div className="rounded-xl bg-slate-50 px-4 py-3 text-sm text-slate-700">
            <span className="block text-xs text-slate-500">Composición que se usará</span>
            {origen?.analisis
              ? `${origen.analisis.grasa} % MG · ${origen.analisis.sng} % SNG · análisis del ${new Date(origen.analisis.tomado_en).toLocaleString("es-CL")}`
              : "—"}
          </div>
          {origen?.motivo && <p role="alert" className="rounded-xl bg-red-50 px-4 py-3 text-sm text-red-800 sm:col-span-2">{origen.motivo}</p>}
          {siloInicial !== undefined && !puesto.origenes.some((item) => item.id === siloInicial) && (
            <p className="rounded-xl bg-amber-50 px-4 py-3 text-sm text-amber-900 sm:col-span-2">El silo elegido no tiene leche para descremar.</p>
          )}
          {etapas.length > 1 && (
            <Campo texto="Etapa de descremación">
              <select required value={etapaElegida} onChange={(e) => setEtapaElegida(e.target.value)} className={control}>
                <option value="">Seleccionar…</option>
                {etapas.map((item) => <option key={item.id} value={item.id}>{item.nombre}</option>)}
              </select>
            </Campo>
          )}
          <Campo texto="Descremadora">
            <select required value={equipo} onChange={(e) => setEquipo(e.target.value)} className={control}>
              <option value="">Seleccionar…</option>
              {libres.map((item) => <option key={item.equipo_id} value={item.equipo_id}>{item.codigo} · {item.nombre}</option>)}
            </select>
          </Campo>
          <Campo texto="Litros de entrada">
            <input required type="number" min="1" step="0.01" max={origen?.saldo_l} value={litros} onChange={(e) => { setLitros(e.target.value); invalidarPlan(); }} className={control} />
          </Campo>
          <Campo texto="Producto · leche descremada">
            <select required value={productoDescremada} onChange={(e) => { setProductoDescremada(e.target.value); setRutaDescremada(""); invalidarPlan(); }} className={control}>
              <option value="">Seleccionar…</option>
              {(opciones?.productos_descremada ?? []).map((item) => <option key={item.id} value={item.id}>{item.nombre}</option>)}
            </select>
          </Campo>
          <Campo texto="TK de leche descremada">
            <select required value={tkDescremada} onChange={(e) => setTkDescremada(e.target.value)} className={control}>
              <option value="">Seleccionar…</option>
              {puesto.destinos_descremada.map((item) => <option key={item.id} value={item.id}>{item.codigo} · {cantidad(item.libre_l, "L")} libres</option>)}
            </select>
          </Campo>
          <Campo texto="Ruta de la leche descremada">
            <select required value={rutaDescremada} onChange={(e) => setRutaDescremada(e.target.value)} className={control}>
              <option value="">Seleccionar…</option>
              {rutasDescremada.map((ruta) => <option key={ruta.id} value={ruta.id}>{ruta.producto_nombre} · {ruta.proceso_nombre}</option>)}
            </select>
          </Campo>
          <Campo texto="Producto · crema">
            <select required value={productoCrema} onChange={(e) => { setProductoCrema(e.target.value); setRutaCrema(""); invalidarPlan(); }} className={control}>
              <option value="">Seleccionar…</option>
              {(opciones?.productos_crema ?? []).map((item) => <option key={item.id} value={item.id}>{item.nombre}</option>)}
            </select>
          </Campo>
          <Campo texto="TK de crema">
            <select required value={tkCrema} onChange={(e) => setTkCrema(e.target.value)} className={control}>
              <option value="">Seleccionar…</option>
              {puesto.destinos_crema.map((item) => <option key={item.id} value={item.id}>{item.codigo} · {cantidad(item.libre_l, "L")} libres</option>)}
            </select>
          </Campo>
          <Campo texto="Destino de la crema">
            <select required value={ramaCrema} onChange={(e) => { setRamaCrema(e.target.value as DestinoRamaCrema); setRutaCrema(""); }} className={control}>
              <option value="siguiente_proceso">Mantequilla / siguiente proceso</option>
              <option value="estandarizacion">Estandarización</option>
              <option value="despacho_directo">Despacho directo</option>
            </select>
          </Campo>
          <Campo texto="Ruta de la crema">
            <select required value={rutaCrema} onChange={(e) => setRutaCrema(e.target.value)} className={control}>
              <option value="">Seleccionar…</option>
              {rutasCrema.map((ruta) => <option key={ruta.id} value={ruta.id}>{ruta.producto_nombre} · {ruta.proceso_nombre}</option>)}
            </select>
          </Campo>
        </fieldset>
        {libres.length === 0 && <p className="rounded-xl bg-amber-50 p-3 text-sm text-amber-900">No hay descremadoras disponibles: todas están preparadas, en curso o en CIP.</p>}

        <section aria-label="Reparto planificado" className="rounded-2xl border border-sky-200 bg-sky-50 p-4">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <h3 className="font-semibold text-slate-900">Reparto planificado</h3>
              <p className="text-xs text-slate-600">El sistema sugiere por balance de materia grasa; el operador confirma o ajusta. Estos litros se reservan en los TK.</p>
            </div>
            <button type="button" disabled={calculando || revisando || !origen?.analisis || !productoDescremada || !productoCrema} onClick={() => void calcular()} className="rounded-xl border border-sky-700 bg-white px-4 py-2 text-sm font-semibold text-sky-800 disabled:opacity-50">{calculando ? "Calculando…" : "Calcular sugerencia"}</button>
          </div>
          {sugerencia && (
            <fieldset className="mt-4 grid gap-3 sm:grid-cols-2" disabled={revisando}>
              <Campo texto="Descremada planificada (L)">
                <input required type="number" min="0.01" step="0.01" value={planDescremada} onChange={(e) => { setPlanDescremada(e.target.value); setPlanConfirmado(false); }} className={control} />
              </Campo>
              <Campo texto="Crema planificada (L)">
                <input required type="number" min="0.01" step="0.01" value={planCrema} onChange={(e) => { setPlanCrema(e.target.value); setPlanConfirmado(false); }} className={control} />
              </Campo>
              <p className="text-xs text-slate-600">Referencia descremada: {sugerencia.grasa_descremada_objetivo} % MG</p>
              <p className="text-xs text-slate-600">Referencia crema: {sugerencia.grasa_crema_objetivo} % MG</p>
              {(excedeDescremada || excedeCrema) && (
                <p className="rounded-xl bg-amber-50 px-3 py-2 text-sm text-amber-900 sm:col-span-2">El plan supera la capacidad libre de {[excedeDescremada && destinoDescremada?.codigo, excedeCrema && destinoCrema?.codigo].filter(Boolean).join(" y ")}: «Preparar» lo va a rechazar.</p>
              )}
              <label className="flex items-start gap-3 rounded-xl bg-white p-3 text-sm text-slate-700 sm:col-span-2">
                <input type="checkbox" className="mt-1" checked={planConfirmado} onChange={(e) => setPlanConfirmado(e.target.checked)} />
                <span>Confirmo que revisé los volúmenes sugeridos y que estos serán los volúmenes reservados en los TK.</span>
              </label>
            </fieldset>
          )}
        </section>

        {sinEspecificacion.length > 0 && (
          <div className="rounded-xl bg-amber-50 px-4 py-3 text-sm text-amber-900">
            <p>Falta una especificación de silo vigente para: {sinEspecificacion.map((item) => item?.nombre).join(" y ")}.</p>
            <p className="mt-1">Solicita a Calidad configurarla en <Link to="/maestros?seccion=especificaciones" className="font-semibold underline">Maestros · Especificaciones</Link>.</p>
          </div>
        )}
        {bloqueos.map((bloqueo) => <p key={bloqueo.codigo} className="rounded-xl bg-amber-50 px-4 py-3 text-sm text-amber-900">{bloqueo.mensaje}</p>)}
        {error && !revisando && <p role="alert" className="rounded-xl bg-red-50 px-4 py-3 text-sm text-red-800">{error}</p>}

        {revisando && origen && maquina && destinoDescremada && destinoCrema ? (
          <ConfirmarAccion
            titulo="Preparar el descremado"
            filas={[
              { etiqueta: "Origen", valor: `${origen.codigo} · ${cantidad(litros, "L")}` },
              { etiqueta: "Composición", valor: origen.analisis ? `${origen.analisis.grasa} % MG · ${origen.analisis.sng} % SNG` : "—" },
              { etiqueta: "Descremadora", valor: maquina.nombre },
              { etiqueta: "Leche descremada", valor: `${destinoDescremada.codigo} · ${cantidad(planDescremada, "L")}` },
              { etiqueta: "Crema", valor: `${destinoCrema.codigo} · ${cantidad(planCrema, "L")}` },
            ]}
            textoConfirmar="Preparar descremado"
            ocupado={guardando}
            error={error}
            onConfirmar={() => void confirmar()}
            onVolver={() => setRevisando(false)}
          />
        ) : (
          <div className="flex justify-end gap-3">
            <button type="button" onClick={alCerrar} className="rounded-xl border border-slate-300 px-4 py-2.5 text-sm font-semibold text-slate-700">Cancelar</button>
            <button type="submit" disabled={!completo} className="rounded-xl bg-emerald-700 px-5 py-2.5 text-sm font-semibold text-white disabled:opacity-40">Revisar y confirmar</button>
          </div>
        )}
      </form>
    </div>
  );
}

function Campo({ texto, children }: { texto: string; children: ReactNode }) {
  return <label className="text-sm font-medium text-slate-700">{texto}{children}</label>;
}
