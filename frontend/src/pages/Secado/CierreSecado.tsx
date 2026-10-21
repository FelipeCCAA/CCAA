import { useRef, useState, type FormEvent } from "react";
import { AlertTriangle, X } from "lucide-react";

import { mensajeErrorProceso } from "../../services/errores-proceso";
import { calcularBalanceSecado } from "../../services/secado-proceso";
import {
  cerrarSecado,
  type CierreSecado as DatosCierreSecado,
  type CorridaSecado,
} from "../../services/secado.service";
import { kgConocidosDeEntradas, requiereReferenciaMedicionKg } from "../../services/secado-operacion";
import { resultadoDeEnvioIncierto } from "../../services/resultado-envio";

const numero = (valor: string) => {
  const convertido = Number(valor);
  return Number.isFinite(convertido) ? convertido : 0;
};

const formato = new Intl.NumberFormat("es-CL", {
  minimumFractionDigits: 0,
  maximumFractionDigits: 3,
});

const campo = "mt-1 w-full rounded-xl border border-slate-300 bg-white px-3 py-2.5 text-sm outline-none focus:border-amber-600";

export default function CierreSecado({
  corrida,
  alCerrar,
  alCompletarse,
}: {
  corrida: CorridaSecado;
  alCerrar: () => void;
  alCompletarse: (corrida: CorridaSecado) => void;
}) {
  const [alimentacion, setAlimentacion] = useState(corrida.kg_alimentacion ?? (kgConocidosDeEntradas(corrida.entradas_alimentacion ?? [])?.toString() ?? ""));
  const [solidos, setSolidos] = useState("");
  const [polvo, setPolvo] = useState("");
  const [finos, setFinos] = useState("0");
  const [merma, setMerma] = useState("0");
  const [temperaturaSalida, setTemperaturaSalida] = useState("");
  const [guardando, setGuardando] = useState(false);
  const [error, setError] = useState("");
  const [incierto, setIncierto] = useState(false);
  const [confirmado, setConfirmado] = useState(false);
  const [referencia, setReferencia] = useState("");
  const enviando = useRef(false);
  const intento = useRef<{ firma: string; carga: DatosCierreSecado } | null>(null);

  const entradas = corrida.entradas_alimentacion ?? [];
  const requiereReferencia = requiereReferenciaMedicionKg(corrida);
  const kilosConocidos = kgConocidosDeEntradas(entradas);
  const alimentacionConocida = corrida.kg_alimentacion !== null ? corrida.kg_alimentacion : kilosConocidos === null ? null : String(kilosConocidos);

  const valores = {
    kgAlimentacion: numero(alimentacion),
    solidosEntradaPct: numero(solidos),
    kgPolvo: numero(polvo),
    kgFinos: numero(finos),
    kgMerma: numero(merma),
  };
  const balance = calcularBalanceSecado(valores);
  const formularioCompleto = valores.kgAlimentacion > 0
    && valores.solidosEntradaPct > 0
    && valores.solidosEntradaPct <= 100
    && valores.kgPolvo > 0
    && valores.kgFinos >= 0
    && valores.kgMerma >= 0;

  const guardar = async (evento: FormEvent) => {
    evento.preventDefault();
    if (enviando.current) return;
    if (!formularioCompleto || !balance.esPosible) {
      setError("Revisa el balance: las cantidades deben ser válidas y las salidas no pueden superar la alimentación.");
      return;
    }

    const controles: Record<string, number> = {};
    if (temperaturaSalida !== "") controles.temperatura_salida = numero(temperaturaSalida);
    if (requiereReferencia && !referencia.trim()) {
      setError("Registra el ticket o registro de la medición en kg para una alimentación en litros.");
      return;
    }
    const cargaBase = {
      kg_alimentacion: valores.kgAlimentacion,
      solidos_entrada_pct: valores.solidosEntradaPct,
      kg_polvo: valores.kgPolvo,
      kg_finos: valores.kgFinos,
      kg_merma: valores.kgMerma,
      controles,
      ...(requiereReferencia ? { referencia_medicion_kg: referencia.trim() } : {}),
    };
    const firma = JSON.stringify(cargaBase);
    if (!intento.current || intento.current.firma !== firma) {
      intento.current = { firma, carga: { ...cargaBase, operacion_id: crypto.randomUUID() } };
    }

    enviando.current = true;
    setGuardando(true);
    setError("");
    try {
      const cerrada = await cerrarSecado(corrida.id, intento.current.carga);
      setConfirmado(true);
      setIncierto(false);
      alCompletarse(cerrada);
    } catch (errorDesconocido) {
      const resultadoIncierto = resultadoDeEnvioIncierto(errorDesconocido);
      setIncierto(resultadoIncierto);
      if (!resultadoIncierto) intento.current = null;
      setError(mensajeErrorProceso(errorDesconocido, "No se pudo cerrar la corrida de Secado."));
    } finally {
      enviando.current = false;
      setGuardando(false);
    }
  };

  return (
    <div className="fixed inset-0 z-[70] overflow-y-auto bg-slate-950/45 p-4" role="dialog" aria-modal="true" aria-labelledby="titulo-cierre-secado">
      <form onSubmit={guardar} className="mx-auto my-6 max-w-4xl rounded-2xl bg-white p-6 shadow-xl">
        <div className="flex items-start justify-between gap-4">
          <div>
            <p className="text-xs font-bold uppercase tracking-wider text-amber-700">Cierre de torre</p>
            <h2 id="titulo-cierre-secado" className="mt-1 text-2xl font-bold text-slate-900">{corrida.lote_codigo} · {corrida.producto_nombre}</h2>
            <p className="mt-1 text-sm text-slate-600">{corrida.equipo_nombre ?? "Torre sin nombre"} · {corrida.ejecucion_codigo}</p>
          </div>
          <button type="button" onClick={alCerrar} disabled={guardando || incierto || confirmado} className="rounded-lg p-2 text-slate-600 hover:bg-slate-100 disabled:opacity-50" aria-label="Cerrar formulario"><X className="h-5 w-5" /></button>
        </div>

        <div className="mt-6 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          <label className="text-sm font-medium text-slate-700">Alimentación medida <span className="text-slate-500">(kg)</span><input required readOnly={alimentacionConocida !== null} type="number" min="0.001" step="0.001" value={alimentacionConocida ?? alimentacion} onChange={(e) => setAlimentacion(e.target.value)} disabled={incierto || confirmado} className={`${campo} ${alimentacionConocida !== null ? "bg-slate-100" : ""}`} />{alimentacionConocida !== null && <span className="mt-1 block text-xs font-normal text-slate-500">Cantidad en kg informada por el origen de la corrida.</span>}</label>
          <label className="text-sm font-medium text-slate-700">Sólidos de entrada <span className="text-slate-500">(%)</span><input required type="number" min="0.01" max="100" step="0.01" value={solidos} onChange={(e) => setSolidos(e.target.value)} disabled={incierto || confirmado} className={campo} /></label>
          <label className="text-sm font-medium text-slate-700">Polvo obtenido <span className="text-slate-500">(kg)</span><input required type="number" min="0.001" step="0.001" value={polvo} onChange={(e) => setPolvo(e.target.value)} disabled={incierto || confirmado} className={campo} /></label>
          <label className="text-sm font-medium text-slate-700">Finos recuperados <span className="text-slate-500">(kg)</span><input required type="number" min="0" step="0.001" value={finos} onChange={(e) => setFinos(e.target.value)} disabled={incierto || confirmado} className={campo} /></label>
          <label className="text-sm font-medium text-slate-700">Merma registrada <span className="text-slate-500">(kg)</span><input required type="number" min="0" step="0.001" value={merma} onChange={(e) => setMerma(e.target.value)} disabled={incierto || confirmado} className={campo} /></label>
          <label className="text-sm font-medium text-slate-700">Temperatura de salida <span className="text-slate-500">(°C)</span><input type="number" step="0.01" value={temperaturaSalida} onChange={(e) => setTemperaturaSalida(e.target.value)} disabled={incierto || confirmado} className={campo} /></label>
        </div>

        <section className="mt-5 rounded-2xl border border-slate-200 bg-slate-50 p-4" aria-label="Orígenes de alimentación">
          <h3 className="font-bold text-slate-900">Orígenes de alimentación</h3>
          {entradas.length ? <ul className="mt-2 space-y-2 text-sm text-slate-700">{entradas.map((entrada) => <li key={`${entrada.tipo_origen}-${entrada.origen_id}`} className="rounded-lg bg-white p-3"><strong>{entrada.codigo}</strong> · {entrada.tipo_origen} · {Number(entrada.cantidad).toLocaleString("es-CL")} {entrada.unidad} · Calidad: {entrada.estado_calidad}</li>)}</ul> : <p className="mt-2 text-sm text-slate-600">El servidor no informó el detalle de los orígenes de esta corrida.</p>}
          {requiereReferencia && <label className="mt-3 block text-sm font-medium text-slate-700">Ticket o registro de medición (kg medidos)<input required maxLength={120} value={referencia} onChange={(e) => setReferencia(e.target.value)} disabled={incierto || confirmado} placeholder="Identificador del ticket o registro" className={campo} /><span className="mt-1 block text-xs font-normal text-slate-500">La alimentación ingresada arriba debe ser el peso medido en kg. No se convierte el volumen del origen.</span></label>}
        </section>

        <section className={`mt-6 rounded-2xl border p-4 ${balance.esPosible ? "border-slate-200 bg-slate-50" : "border-red-200 bg-red-50"}`} aria-live="polite">
          <div className="flex items-center justify-between gap-3">
            <h3 className="font-bold text-slate-900">Resumen del balance</h3>
            {!balance.esPosible && <span className="inline-flex items-center gap-1 text-xs font-semibold text-red-700"><AlertTriangle className="h-4 w-4" /> Balance imposible</span>}
          </div>
          <div className="mt-3 grid gap-3 text-sm sm:grid-cols-2 lg:grid-cols-5">
            <Dato etiqueta="Alimentación" valor={`${formato.format(valores.kgAlimentacion)} kg`} />
            <Dato etiqueta="Sólidos estimados" valor={`${formato.format(balance.kgSolidosEntrada)} kg`} />
            <Dato etiqueta="Polvo + finos" valor={`${formato.format(balance.kgRecuperados)} kg`} />
            <Dato etiqueta="Diferencia total" valor={`${formato.format(balance.kgNoContabilizados)} kg`} alerta={balance.kgNoContabilizados < 0} />
            <Dato etiqueta="Rendimiento" valor={`${formato.format(balance.rendimientoRecuperacionPct)} %`} />
          </div>
        </section>

        {error && <p className="mt-4 rounded-xl bg-red-50 px-4 py-3 text-sm text-red-800" role="alert">{error}</p>}

        <div className="mt-6 flex flex-wrap justify-end gap-3">
          {incierto && <p className="mr-auto w-full rounded-xl bg-amber-50 p-3 text-sm text-amber-900" role="alert">No sabemos si se cerró. Recupera el resultado de esta misma operación antes de cambiar datos.</p>}
          <button type="button" onClick={alCerrar} disabled={guardando || incierto || confirmado} className="rounded-xl border border-slate-300 px-4 py-2.5 text-sm font-semibold text-slate-700 disabled:opacity-50">Cancelar</button>
          <button type="submit" disabled={guardando || confirmado || !formularioCompleto || !balance.esPosible || (requiereReferencia && !referencia.trim())} className="rounded-xl bg-amber-700 px-5 py-2.5 text-sm font-semibold text-white hover:bg-amber-800 disabled:cursor-not-allowed disabled:opacity-50">{guardando ? "Cerrando corrida…" : incierto ? "Recuperar resultado" : confirmado ? "Cierre confirmado" : "Confirmar balance y cerrar"}</button>
        </div>
      </form>
    </div>
  );
}

function Dato({ etiqueta, valor, alerta = false }: { etiqueta: string; valor: string; alerta?: boolean }) {
  return <p className={`rounded-xl bg-white p-3 ${alerta ? "text-red-800" : "text-slate-800"}`}><span className="block text-xs text-slate-500">{etiqueta}</span><strong>{valor}</strong></p>;
}
