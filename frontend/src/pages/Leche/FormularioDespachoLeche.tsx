import { useRef, useState } from "react";
import { Truck, X } from "lucide-react";

import { mensajeDe } from "../../components/seccion/utilidades";
import { crearDespachoLeche, type DespachoLeche } from "../../services/recepcion.service";
import { formatoLitros, validarLitrosDespacho } from "./disponibilidad-silo";
import { resultadoDeEnvioIncierto } from "../../services/resultado-envio";

const control = "mt-1 w-full rounded-xl border border-slate-300 bg-white px-3 py-2.5";
const ahoraLocal = () => {
  const fecha = new Date();
  fecha.setMinutes(fecha.getMinutes() - fecha.getTimezoneOffset());
  return fecha.toISOString().slice(0, 16);
};

export default function FormularioDespachoLeche({ siloId, siloCodigo, disponible, onCerrar, onCreado, onActualizar }: {
  siloId: number;
  siloCodigo: string;
  disponible: number | null;
  onCerrar: () => void;
  onCreado: (despacho: DespachoLeche) => Promise<void>;
  onActualizar: () => Promise<void>;
}) {
  const [datos, setDatos] = useState({
    litros: "", destino: "", guia_despacho: "", patente: "", fecha_hora: ahoraLocal(),
  });
  const [intento, setIntento] = useState<{ firma: string; clave: string } | null>(null);
  const enviando = useRef(false);
  const [guardando, setGuardando] = useState(false);
  const [actualizando, setActualizando] = useState(false);
  const [incierto, setIncierto] = useState(false);
  const [confirmado, setConfirmado] = useState(false);
  const [error, setError] = useState("");

  const guardar = async (evento: React.FormEvent) => {
    evento.preventDefault();
    if (enviando.current) return;
    const fecha = new Date(datos.fecha_hora);
    if (Number.isNaN(fecha.getTime())) { setError("Indica una fecha y hora válidas."); return; }
    const carga = {
      silo: siloId, litros: Number(datos.litros), destino: datos.destino.trim(),
      guia_despacho: datos.guia_despacho.trim(), patente: datos.patente.trim(),
      fecha_hora: fecha.toISOString(),
    };
    const firma = JSON.stringify(carga);
    const reintento = intento?.firma === firma;
    // El POST vuelve a validar saldo/reservas en el servidor. Un reintento
    // idéntico puede recuperar una confirmación cuya respuesta se perdió.
    const problema = validarLitrosDespacho(datos.litros, reintento ? Number.MAX_VALUE : disponible);
    if (problema) { setError(problema); return; }
    const solicitud = intento && reintento ? intento : { firma, clave: crypto.randomUUID() };
    setIntento(solicitud);
    enviando.current = true;
    setGuardando(true);
    setError("");
    let respuestaRecibida = false;
    try {
      const despacho = await crearDespachoLeche({
        ...carga, operacion_id: solicitud.clave,
      });
      respuestaRecibida = true;
      setConfirmado(true);
      setIncierto(false);
      await onCreado(despacho);
    } catch (fallo) {
      if (!respuestaRecibida) setIncierto(resultadoDeEnvioIncierto(fallo));
      setError(respuestaRecibida
        ? "El despacho se confirmó, pero no pudimos actualizar la pantalla. Recupera el resultado de la misma operación."
        : mensajeDe(fallo, "No se pudo registrar el despacho."));
    } finally { setGuardando(false); enviando.current = false; }
  };

  const cerrar = () => {
    if ((incierto || confirmado) && !window.confirm("Cerrar esta pantalla no anula el despacho. Recupera el resultado de la misma operación antes de registrar otra. ¿Cerrar de todas formas?")) return;
    onCerrar();
  };

  const actualizar = async () => {
    setActualizando(true);
    setError("");
    try { await onActualizar(); }
    catch (fallo) { setError(mensajeDe(fallo, "No se pudo actualizar la disponibilidad.")); }
    finally { setActualizando(false); }
  };

  return (
    <div className="fixed inset-0 z-[80] flex items-start justify-center overflow-y-auto bg-slate-950/45 p-4">
      <form onSubmit={guardar} className="my-8 w-full max-w-2xl rounded-2xl bg-white p-6 shadow-xl">
        <div className="flex items-center justify-between"><div className="flex items-center gap-3"><span className="rounded-xl bg-emerald-50 p-2 text-emerald-700"><Truck className="h-5 w-5" /></span><div><p className="text-xs font-semibold uppercase tracking-wide text-emerald-700">Salida a granel</p><h2 className="text-xl font-semibold">Despachar desde {siloCodigo}</h2></div></div><button type="button" onClick={cerrar} disabled={guardando} aria-label="Cerrar despacho" className="rounded-lg p-2 hover:bg-slate-100"><X className="h-5 w-5" /></button></div>
        <p className="mt-4 rounded-xl bg-slate-50 px-4 py-3 text-sm text-slate-600">Disponible para esta salida: {disponible === null ? "desconocido; actualiza antes de operar" : `${formatoLitros.format(disponible)} L`}. Se exige análisis vigente, firma de visualización y liberación de inocuidad. Las reservas y el saldo se comprueban nuevamente al confirmar.</p>
        <button type="button" disabled={guardando || actualizando || incierto || confirmado} onClick={() => void actualizar()} className="mt-2 text-sm font-medium text-emerald-700 underline disabled:opacity-40">{actualizando ? "Actualizando…" : "Actualizar disponibilidad"}</button>
        {incierto && <p role="alert" className="mt-3 rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900">No sabemos si se confirmó. Reintenta la misma operación para recuperar el resultado antes de cambiar datos.</p>}
        <fieldset disabled={guardando || incierto || confirmado} className="mt-5 grid gap-4 sm:grid-cols-2">
          <Campo texto="Litros"><input required type="number" min="0.01" max={intento ? undefined : disponible ?? undefined} step="0.01" value={datos.litros} onChange={(e) => setDatos({ ...datos, litros: e.target.value })} className={control} /></Campo>
          <Campo texto="Fecha y hora"><input required type="datetime-local" value={datos.fecha_hora} onChange={(e) => setDatos({ ...datos, fecha_hora: e.target.value })} className={control} /></Campo>
          <Campo texto="Destino o cliente"><input required maxLength={160} value={datos.destino} onChange={(e) => setDatos({ ...datos, destino: e.target.value })} className={control} /></Campo>
          <Campo texto="Guía de despacho"><input required maxLength={60} value={datos.guia_despacho} onChange={(e) => setDatos({ ...datos, guia_despacho: e.target.value })} className={control} /></Campo>
          <Campo texto="Patente del vehículo"><input required maxLength={15} value={datos.patente} onChange={(e) => setDatos({ ...datos, patente: e.target.value.toUpperCase() })} className={control} /></Campo>
        </fieldset>
        {error && <p className="mt-4 rounded-xl bg-rose-50 px-4 py-3 text-sm text-rose-700">{error}</p>}
        <div className="mt-6 flex justify-end gap-3"><button type="button" onClick={cerrar} disabled={guardando} className="px-4 py-2.5 text-sm text-slate-600">Cerrar</button><button disabled={guardando || actualizando || (disponible === null && !intento)} className="rounded-xl bg-emerald-700 px-5 py-2.5 text-sm font-semibold text-white disabled:opacity-40">{guardando ? "Registrando…" : incierto || confirmado ? "Recuperar resultado" : "Confirmar despacho"}</button></div>
      </form>
    </div>
  );
}

function Campo({ texto, children }: { texto: string; children: React.ReactNode }) {
  return <label className="text-sm text-slate-600">{texto}{children}</label>;
}
