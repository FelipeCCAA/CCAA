import { useEffect, useMemo, useRef, useState, type FormEvent } from "react";
import { X } from "lucide-react";

import ConfirmarAccion from "../../components/operacion/ConfirmarAccion";
import { mensajeErrorProceso } from "../../services/errores-proceso";
import { cantidad } from "../../services/formato";
import { prepararContinuacion } from "../../services/procesos.service";
import {
  obtenerOpcionesSecadoExterno, prepararSecadoExterno,
  type ConcentradoPuesto, type OpcionesSecadoExterno, type TorrePuesto,
} from "../../services/secado.service";

type Fuente = "concentrado" | "externa";
const campo = "mt-1 w-full rounded-xl border border-slate-300 bg-white px-3 py-2.5 text-sm outline-none focus:border-amber-600";

/*
  Tomar alimentación para una torre: fuente → torre → cantidad → resumen.
  Las dos fuentes **preparan** y nada más; iniciar es otro paso, en la
  tarjeta, con las mismas reglas para las dos. Las opciones vienen del
  servidor: los concentrados con el saldo que `preparar-continuacion`
  aceptará, y solo las torres que el puesto da por disponibles.
*/
export default function TomarConcentrado({ torres, concentrados, torreInicial, alCerrar, alPreparar }: {
  torres: TorrePuesto[];
  concentrados: ConcentradoPuesto[];
  torreInicial?: number;
  alCerrar: () => void;
  alPreparar: (mensaje: string) => void;
}) {
  const [fuente, setFuente] = useState<Fuente>("concentrado");
  const [salidaId, setSalidaId] = useState("");
  const [torre, setTorre] = useState(torreInicial ? String(torreInicial) : "");
  const [valor, setValor] = useState("");
  const [opciones, setOpciones] = useState<OpcionesSecadoExterno | null>(null);
  const [orden, setOrden] = useState("");
  const [existencia, setExistencia] = useState("");
  const [codigoLote, setCodigoLote] = useState("");
  const [revisando, setRevisando] = useState(false);
  const [guardando, setGuardando] = useState(false);
  const [error, setError] = useState("");
  const enviando = useRef(false);

  useEffect(() => {
    if (fuente !== "externa" || opciones) return;
    const controller = new AbortController();
    // Diferido como en el modal anterior: StrictMode monta dos veces y el
    // segundo montaje no debe heredar la promesa que el primero canceló.
    const tarea = window.setTimeout(() => {
      obtenerOpcionesSecadoExterno(controller.signal)
        .then(setOpciones)
        .catch((causa) => {
          if (!controller.signal.aborted) setError(mensajeErrorProceso(causa, "No se pudieron cargar las materias primas para Secado."));
        });
    }, 0);
    return () => { window.clearTimeout(tarea); controller.abort(); };
  }, [fuente, opciones]);

  const libres = torres.filter((item) => item.estado === "disponible");
  const torreElegida = libres.find((item) => item.equipo_id === Number(torre));
  const concentrado = concentrados.find((item) => item.salida_id === Number(salidaId));
  const ordenElegida = opciones?.ordenes.find((item) => item.id === Number(orden));
  const existencias = useMemo(
    () => (opciones?.existencias ?? []).filter((item) => !ordenElegida || item.insumo_id === ordenElegida.insumo_origen_id),
    [opciones, ordenElegida],
  );
  const existenciaElegida = existencias.find((item) => item.id === Number(existencia));
  const unidad = fuente === "concentrado" ? concentrado?.unidad ?? "" : "kg";
  const maximo = fuente === "concentrado" ? concentrado?.disponible : existenciaElegida?.cantidad_disponible;
  const completo = Boolean(torreElegida) && Number(valor) > 0 && (
    fuente === "concentrado" ? Boolean(concentrado) : Boolean(ordenElegida && existenciaElegida && codigoLote.trim())
  );

  const filas = fuente === "concentrado"
    ? [
      { etiqueta: "Fuente", valor: "Concentrado liberado" },
      { etiqueta: "Concentrado", valor: concentrado ? `Lote ${concentrado.lote_codigo} · ${concentrado.silo}` : "—" },
      { etiqueta: "Torre", valor: torreElegida?.nombre ?? "—" },
      { etiqueta: "Cantidad", valor: cantidad(valor, unidad) },
    ]
    : [
      { etiqueta: "Fuente", valor: "Alimentación externa" },
      { etiqueta: "Orden", valor: ordenElegida ? `${ordenElegida.codigo} · ${ordenElegida.producto_nombre}` : "—" },
      { etiqueta: "Lote externo", valor: existenciaElegida ? `${existenciaElegida.insumo_nombre} · ${existenciaElegida.lote_codigo}` : "—" },
      { etiqueta: "Lote de salida", valor: codigoLote.trim() || "—" },
      { etiqueta: "Torre", valor: torreElegida?.nombre ?? "—" },
      { etiqueta: "Cantidad", valor: cantidad(valor, "kg") },
    ];

  const revisar = (evento: FormEvent) => {
    evento.preventDefault();
    if (completo) setRevisando(true);
  };

  const confirmar = async () => {
    if (enviando.current || !torreElegida) return;
    enviando.current = true;
    setGuardando(true);
    setError("");
    try {
      if (fuente === "concentrado" && concentrado) {
        await prepararContinuacion(concentrado.salida_id, {
          etapa: concentrado.etapa_id, equipo: torreElegida.equipo_id, cantidad: Number(valor),
        });
        alPreparar(`${torreElegida.nombre} preparada con el lote ${concentrado.lote_codigo}.`);
      } else {
        const corrida = await prepararSecadoExterno({
          orden: Number(orden), existencia: Number(existencia), equipo: torreElegida.equipo_id,
          codigo_lote: codigoLote.trim(), cantidad: Number(valor),
        });
        alPreparar(`${torreElegida.nombre} preparada con alimentación externa; lote de salida ${corrida.lote_codigo}.`);
      }
    } catch (causa) {
      setError(mensajeErrorProceso(causa, "No se pudo preparar la torre."));
      setRevisando(false);
    } finally {
      enviando.current = false;
      setGuardando(false);
    }
  };

  return (
    <div className="fixed inset-0 z-[70] overflow-y-auto bg-slate-950/45 p-4" role="dialog" aria-modal="true" aria-labelledby="titulo-tomar-concentrado">
      <form onSubmit={revisar} className="mx-auto my-8 max-w-3xl space-y-5 rounded-2xl bg-white p-6 shadow-xl">
        <div className="flex items-start justify-between gap-4">
          <div>
            <p className="text-xs font-bold uppercase tracking-wider text-amber-700">Puesto de Secado</p>
            <h2 id="titulo-tomar-concentrado" className="mt-1 text-2xl font-bold text-slate-900">Tomar concentrado</h2>
            <p className="mt-2 text-sm text-slate-600">Deja la torre preparada. El secado se inicia después, desde la tarjeta de la torre.</p>
          </div>
          <button type="button" onClick={alCerrar} disabled={guardando} className="rounded-lg p-2 hover:bg-slate-100" aria-label="Cerrar"><X className="h-5 w-5" /></button>
        </div>

        <fieldset className="flex flex-wrap gap-4 text-sm font-medium text-slate-700" disabled={revisando}>
          <legend className="mb-2 text-sm font-semibold text-slate-900">Fuente</legend>
          <label className="inline-flex items-center gap-2"><input type="radio" name="fuente" checked={fuente === "concentrado"} onChange={() => { setFuente("concentrado"); setValor(""); }} />Concentrado liberado</label>
          <label className="inline-flex items-center gap-2"><input type="radio" name="fuente" checked={fuente === "externa"} onChange={() => { setFuente("externa"); setValor(""); }} />Alimentación externa</label>
        </fieldset>

        <fieldset className="grid gap-4 sm:grid-cols-2" disabled={revisando}>
          {fuente === "concentrado" ? (
            concentrados.length === 0
              ? <p className="rounded-xl bg-amber-50 p-3 text-sm text-amber-900 sm:col-span-2">No hay concentrados liberados con saldo cuya siguiente etapa sea Secado.</p>
              : (
                <label className="text-sm font-medium text-slate-700 sm:col-span-2">Concentrado
                  <select required value={salidaId} onChange={(e) => { setSalidaId(e.target.value); setValor(concentrados.find((c) => c.salida_id === Number(e.target.value))?.disponible ?? ""); }} className={campo}>
                    <option value="">Seleccionar…</option>
                    {concentrados.map((item) => <option key={item.salida_id} value={item.salida_id}>{item.lote_codigo} · {item.producto} · {item.silo} · {cantidad(item.disponible, item.unidad)}</option>)}
                  </select>
                </label>
              )
          ) : (
            <>
              <label className="text-sm font-medium text-slate-700">Orden / producto
                <select required value={orden} onChange={(e) => { setOrden(e.target.value); setExistencia(""); }} className={campo}>
                  <option value="">Seleccionar…</option>
                  {(opciones?.ordenes ?? []).map((item) => <option key={item.id} value={item.id}>{item.codigo} · {item.producto_nombre}</option>)}
                </select>
              </label>
              <label className="text-sm font-medium text-slate-700">Lote externo liberado
                <select required value={existencia} onChange={(e) => setExistencia(e.target.value)} disabled={!orden} className={campo}>
                  <option value="">Seleccionar…</option>
                  {existencias.map((item) => <option key={item.id} value={item.id}>{item.insumo_nombre} · {item.lote_codigo} · {cantidad(item.cantidad_disponible, item.unidad)}</option>)}
                </select>
              </label>
              <label className="text-sm font-medium text-slate-700">Código lote de salida
                <input required value={codigoLote} onChange={(e) => setCodigoLote(e.target.value)} className={campo} />
              </label>
            </>
          )}
          <label className="text-sm font-medium text-slate-700">Torre
            <select required value={torre} onChange={(e) => setTorre(e.target.value)} className={campo}>
              <option value="">Seleccionar…</option>
              {libres.map((item) => <option key={item.equipo_id} value={item.equipo_id}>{item.codigo} · {item.nombre}</option>)}
            </select>
          </label>
          <label className="text-sm font-medium text-slate-700">Cantidad <span className="text-slate-500">({unidad || "—"})</span>
            <input required type="number" min="0.001" step="0.001" max={maximo} value={valor} onChange={(e) => setValor(e.target.value)} className={campo} />
          </label>
        </fieldset>
        {libres.length === 0 && <p className="rounded-xl bg-amber-50 p-3 text-sm text-amber-900">No hay torres disponibles: todas están preparadas o en curso.</p>}

        {error && !revisando && <p role="alert" className="rounded-xl bg-red-50 px-4 py-3 text-sm text-red-800">{error}</p>}
        {revisando ? (
          <ConfirmarAccion
            titulo="Preparar la torre con esta alimentación"
            filas={filas}
            textoConfirmar="Preparar torre"
            ocupado={guardando}
            error={error}
            onConfirmar={() => void confirmar()}
            onVolver={() => setRevisando(false)}
          />
        ) : (
          <div className="flex justify-end gap-3">
            <button type="button" onClick={alCerrar} className="rounded-xl border border-slate-300 px-4 py-2.5 text-sm font-semibold text-slate-700">Cancelar</button>
            <button type="submit" disabled={!completo} className="rounded-xl bg-amber-700 px-5 py-2.5 text-sm font-semibold text-white disabled:opacity-40">Revisar y confirmar</button>
          </div>
        )}
      </form>
    </div>
  );
}
