import { useEffect, useMemo, useRef, useState, type FormEvent } from "react";
import { AlertTriangle, PackageOpen, X } from "lucide-react";

import { mensajeErrorProceso } from "../../services/errores-proceso";
import {
  iniciarSecadoExterno,
  obtenerOpcionesSecadoExterno,
  type CorridaSecado,
  type OpcionesSecadoExterno,
} from "../../services/secado.service";

const campo = "mt-1 w-full rounded-xl border border-slate-300 bg-white px-3 py-2.5 text-sm outline-none focus:border-amber-600";

export default function InicioSecadoExterno({
  alCerrar,
  alIniciar,
}: {
  alCerrar: () => void;
  alIniciar: (corrida: CorridaSecado) => void;
}) {
  const [opciones, setOpciones] = useState<OpcionesSecadoExterno | null>(null);
  const [orden, setOrden] = useState("");
  const [existencia, setExistencia] = useState("");
  const [equipo, setEquipo] = useState("");
  const [codigoLote, setCodigoLote] = useState("");
  const [cantidad, setCantidad] = useState("");
  const [error, setError] = useState("");
  const [guardando, setGuardando] = useState(false);
  const enviando = useRef(false);

  useEffect(() => {
    const controller = new AbortController();
    // StrictMode monta, limpia y vuelve a montar en desarrollo. Posponer la
    // lectura evita que el deduplicador reutilice en el segundo montaje la
    // promesa que el primero acaba de cancelar.
    const tarea = window.setTimeout(() => {
      obtenerOpcionesSecadoExterno(controller.signal)
        .then(setOpciones)
        .catch((e) => {
          if (!controller.signal.aborted) {
            setError(mensajeErrorProceso(e, "No se pudieron cargar las materias primas para Secado."));
          }
        });
    }, 0);
    return () => {
      window.clearTimeout(tarea);
      controller.abort();
    };
  }, []);

  const ordenSeleccionada = opciones?.ordenes.find((item) => item.id === Number(orden));
  const existencias = useMemo(
    () => (opciones?.existencias ?? []).filter(
      (item) => !ordenSeleccionada || item.insumo_id === ordenSeleccionada.insumo_origen_id,
    ),
    [opciones, ordenSeleccionada],
  );
  const existenciaSeleccionada = existencias.find((item) => item.id === Number(existencia));

  const guardar = async (evento: FormEvent) => {
    evento.preventDefault();
    if (enviando.current) return;
    enviando.current = true;
    setGuardando(true);
    setError("");
    try {
      alIniciar(await iniciarSecadoExterno({
        orden: Number(orden), existencia: Number(existencia), equipo: Number(equipo),
        codigo_lote: codigoLote.trim(), cantidad: Number(cantidad),
      }));
    } catch (e) {
      setError(mensajeErrorProceso(e, "No se pudo iniciar la corrida desde inventario."));
    } finally {
      enviando.current = false;
      setGuardando(false);
    }
  };

  return <div className="fixed inset-0 z-[70] overflow-y-auto bg-slate-950/45 p-4" role="dialog" aria-modal="true" aria-labelledby="titulo-secado-externo">
    <form onSubmit={guardar} className="mx-auto my-8 max-w-3xl rounded-2xl bg-white p-6 shadow-xl">
      <div className="flex items-start justify-between gap-4">
        <div><p className="text-xs font-bold uppercase tracking-wider text-amber-700">Alimentación externa</p><h2 id="titulo-secado-externo" className="mt-1 text-2xl font-bold text-slate-900">Iniciar corrida de Secado</h2><p className="mt-2 text-sm text-slate-600">Usa un lote recibido desde proveedor, ya liberado por Calidad y ubicado como disponible. El consumo queda ligado al lote de salida.</p></div>
        <button type="button" onClick={alCerrar} disabled={guardando} className="rounded-lg p-2 hover:bg-slate-100" aria-label="Cerrar"><X className="h-5 w-5" /></button>
      </div>

      {!opciones && !error ? <div className="mt-6 h-40 animate-pulse rounded-2xl bg-slate-100" /> : opciones && opciones.ordenes.length === 0 ? <div className="mt-6 flex gap-3 rounded-2xl border border-amber-200 bg-amber-50 p-4 text-sm text-amber-900"><AlertTriangle className="h-5 w-5 shrink-0" /><p>No hay órdenes con una ruta que comience en Secado y tenga una materia prima externa configurada. Administración debe configurar esa relación en Rutas productivas.</p></div> : opciones && <div className="mt-6 grid gap-4 sm:grid-cols-2">
        <label className="text-sm font-medium text-slate-700">Orden / producto<select required value={orden} onChange={(e) => { setOrden(e.target.value); setExistencia(""); }} className={campo}><option value="">Seleccionar…</option>{opciones.ordenes.map((item) => <option key={item.id} value={item.id}>{item.codigo} · {item.producto_nombre}</option>)}</select></label>
        <label className="text-sm font-medium text-slate-700">Lote externo liberado<select required value={existencia} onChange={(e) => setExistencia(e.target.value)} disabled={!orden} className={campo}><option value="">Seleccionar…</option>{existencias.map((item) => <option key={item.id} value={item.id}>{item.insumo_nombre} · {item.lote_codigo} · {Number(item.cantidad_disponible).toLocaleString("es-CL")} {item.unidad}</option>)}</select></label>
        <label className="text-sm font-medium text-slate-700">Torre<select required value={equipo} onChange={(e) => setEquipo(e.target.value)} className={campo}><option value="">Seleccionar…</option>{opciones.equipos.map((item) => <option key={item.id} value={item.id} disabled={!item.disponible}>{item.codigo} · {item.nombre}{item.disponible ? "" : " · ocupada"}</option>)}</select></label>
        <label className="text-sm font-medium text-slate-700">Código lote de salida<input required value={codigoLote} onChange={(e) => setCodigoLote(e.target.value)} className={campo} /></label>
        <label className="text-sm font-medium text-slate-700">Cantidad a alimentar <span className="text-slate-500">(kg)</span><input required type="number" min="0.001" max={existenciaSeleccionada?.cantidad_disponible} step="0.001" value={cantidad} onChange={(e) => setCantidad(e.target.value)} className={campo} /></label>
        <div className="rounded-xl bg-slate-50 p-3 text-sm text-slate-600"><PackageOpen className="mb-2 h-5 w-5 text-amber-700" />No se convierte litros a kg ni se aplican rendimientos ocultos. La cantidad indicada se descuenta exactamente del lote externo.</div>
      </div>}

      {error && <p className="mt-4 rounded-xl bg-red-50 px-4 py-3 text-sm text-red-800" role="alert">{error}</p>}
      <div className="mt-6 flex justify-end gap-3"><button type="button" onClick={alCerrar} disabled={guardando} className="rounded-xl border border-slate-300 px-4 py-2.5 text-sm font-semibold text-slate-700">Cancelar</button><button type="submit" disabled={guardando || !opciones || !orden || !existencia || !equipo || !codigoLote.trim() || Number(cantidad) <= 0} className="rounded-xl bg-amber-700 px-5 py-2.5 text-sm font-semibold text-white disabled:opacity-40">{guardando ? "Iniciando…" : "Confirmar e iniciar Secado"}</button></div>
    </form>
  </div>;
}
