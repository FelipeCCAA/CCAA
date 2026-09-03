import { useEffect, useState } from "react";
import { X } from "lucide-react";
import { Link } from "react-router-dom";

import EstadoEquipo from "../../components/EstadoEquipo/EstadoEquipo";
import { ocupacionesPorEquipo } from "../../services/disponibilidad-equipos";
import { esErrorDeEquipo, mensajeErrorProceso } from "../../services/errores-proceso";
import {
  crearMantequillaGuiada,
  obtenerOpcionesAltaMantequilla,
  type CorridaMantequilla,
  type EjecucionOperativa,
  type OpcionesAltaMantequilla,
} from "../../services/procesos.service";

const campo = "mt-1 w-full rounded-xl border border-slate-300 bg-white px-3 py-2.5 text-sm";

export default function NuevaMantequilla({
  ejecuciones,
  onCerrar,
  onCreada,
  alConflictoEquipo,
}: {
  ejecuciones: EjecucionOperativa[];
  onCerrar: () => void;
  onCreada: (corrida: CorridaMantequilla) => void | Promise<void>;
  alConflictoEquipo: () => Promise<void>;
}) {
  const [opciones, setOpciones] = useState<OpcionesAltaMantequilla | null>(null);
  const [datos, setDatos] = useState({ orden: "", crema: "", equipo: "", codigo: "", suero: "", kg: "" });
  const [error, setError] = useState("");
  const [guardando, setGuardando] = useState(false);

  useEffect(() => {
    void obtenerOpcionesAltaMantequilla()
      .then(setOpciones)
      .catch(() => setError("No se pudieron cargar las opciones de mantequilla."));
  }, []);

  const crema = opciones?.cremas.find((item) => item.id === Number(datos.crema));
  const ocupaciones = ocupacionesPorEquipo(ejecuciones);
  const equipoSeleccionado = opciones?.equipos.find((item) => item.id === Number(datos.equipo));
  const ocupacionSeleccionada = equipoSeleccionado ? ocupaciones.get(equipoSeleccionado.id) : undefined;
  const equipoBloqueado = Boolean(ocupacionSeleccionada || equipoSeleccionado?.ocupado_por);

  const guardar = async (evento: React.FormEvent) => {
    evento.preventDefault();
    if (guardando) return;
    setGuardando(true);
    setError("");
    try {
      await onCreada(await crearMantequillaGuiada({
        orden: Number(datos.orden),
        lote_crema: Number(datos.crema),
        equipo: Number(datos.equipo),
        codigo_lote_mantequilla: datos.codigo,
        ...(datos.suero ? { lote_suero: Number(datos.suero) } : {}),
        kg_crema: Number(datos.kg),
      }));
    } catch (errorPeticion: unknown) {
      const mensaje = mensajeErrorProceso(errorPeticion, "No se pudo crear la corrida.");
      if (esErrorDeEquipo(errorPeticion)) await alConflictoEquipo();
      setError(mensaje);
    } finally {
      setGuardando(false);
    }
  };

  return (
    <div className="fixed inset-0 z-[80] flex items-start justify-center overflow-y-auto bg-slate-950/45 p-4">
      <form onSubmit={guardar} className="my-8 w-full max-w-2xl rounded-2xl bg-white p-6 shadow-xl">
        <div className="flex justify-between gap-3">
          <div><p className="text-xs font-bold uppercase tracking-wide text-amber-700">Alta guiada</p><h2 className="mt-1 text-xl font-bold">Nueva corrida de mantequilla</h2><p className="mt-2 text-sm text-slate-600">Crema con saldo → línea de mantequilla → nuevo lote trazable.</p></div>
          <button type="button" onClick={onCerrar} className="h-fit rounded-lg p-2 hover:bg-slate-100" aria-label="Cerrar"><X className="h-5 w-5" /></button>
        </div>
        {!opciones && !error ? <p className="mt-6 text-sm text-slate-500">Cargando opciones…</p> : (
          <div className="mt-6 grid gap-4 sm:grid-cols-2">
            <Selector texto="Orden de mantequilla" valor={datos.orden} cambiar={(valor) => setDatos({ ...datos, orden: valor })}><option value="">Seleccionar OP…</option>{opciones?.ordenes.map((item) => <option key={item.id} value={item.id}>{item.codigo} · {item.producto}</option>)}</Selector>
            <Selector texto="Lote de crema" valor={datos.crema} cambiar={(valor) => setDatos({ ...datos, crema: valor, kg: "" })}><option value="">Seleccionar crema…</option>{opciones?.cremas.map((item) => <option key={item.id} value={item.id}>{item.codigo} · disponible {Number(item.disponible_kg).toLocaleString("es-CL")} kg</option>)}</Selector>
            <label className="text-sm font-medium text-slate-700">Crema a utilizar (kg)<input required min="0.001" max={crema?.disponible_kg} step="0.001" type="number" value={datos.kg} onChange={(evento) => setDatos({ ...datos, kg: evento.target.value })} className={campo} /></label>
            <Selector texto="Línea / equipo" valor={datos.equipo} cambiar={(valor) => setDatos({ ...datos, equipo: valor })}><option value="">Seleccionar línea…</option>{opciones?.equipos.map((item) => { const ocupacion = ocupaciones.get(item.id); const ocupadoPor = ocupacion?.ejecucion ?? item.ocupado_por; return <option key={item.id} value={item.id} disabled={Boolean(ocupadoPor)}>{item.nombre}{ocupadoPor ? ` · ocupado por ${ocupadoPor}` : " · disponible"}</option>; })}</Selector>
            {equipoSeleccionado && <div className="self-end pb-2"><EstadoEquipo estado={ocupacionSeleccionada?.estado ?? (equipoSeleccionado.ocupado_por ? "ejecucion" : undefined)} ejecucion={ocupacionSeleccionada?.ejecucion ?? equipoSeleccionado.ocupado_por ?? undefined} /></div>}
            <label className="text-sm font-medium text-slate-700">Código nuevo lote de mantequilla<input required value={datos.codigo} onChange={(evento) => setDatos({ ...datos, codigo: evento.target.value.toUpperCase() })} className={campo} /></label>
            <Selector texto="Lote de suero (si se medirá)" valor={datos.suero} cambiar={(valor) => setDatos({ ...datos, suero: valor })}><option value="">Sin suero declarado</option>{opciones?.sueros.map((item) => <option key={item.id} value={item.id}>{item.codigo} · {item.producto}</option>)}</Selector>
          </div>
        )}
        {opciones?.ordenes.length === 0 && <p className="mt-4 rounded-xl bg-amber-50 p-3 text-sm text-amber-800">No hay una OP de mantequilla programada. <Link to="/planificacion" className="font-semibold underline">Ir a Planificación</Link>.</p>}
        {opciones && opciones.cremas.length === 0 && opciones.cremas_pendientes_calidad.length === 0 && <p className="mt-4 rounded-xl bg-amber-50 p-3 text-sm text-amber-800">No existe crema producida con saldo disponible.</p>}
        {opciones && opciones.cremas_pendientes_calidad.length > 0 && <section className="mt-4 rounded-xl border border-violet-200 bg-violet-50 p-3"><p className="text-sm font-semibold text-violet-900">Crema no habilitada</p><div className="mt-2 space-y-1">{opciones.cremas_pendientes_calidad.map((item) => <p key={item.id} className="text-xs text-violet-800">{item.codigo} · {item.producto} · {item.estado_calidad === "rechazado" ? "Rechazada" : item.estado_calidad === "trazabilidad_incompleta" ? `Trazabilidad incompleta: origen ${item.etapa_origen}` : "Pendiente de liberación"}</p>)}</div><p className="mt-2 text-xs text-violet-700">Los lotes pendientes se gestionan en <Link to="/calidad" className="font-semibold underline">Calidad</Link>. Un lote con trazabilidad incompleta requiere revisión y no puede aprobarse automáticamente.</p></section>}
        {error && <p className="mt-4 rounded-xl bg-rose-50 p-3 text-sm text-rose-700">{error}</p>}
        <div className="mt-6 flex justify-end gap-3">
          <button type="button" onClick={onCerrar} className="px-4 py-2 text-sm text-slate-600">Cancelar</button>
          <button disabled={guardando || equipoBloqueado || !datos.orden || !datos.crema || !datos.equipo || !datos.codigo || !datos.kg} className="rounded-xl bg-amber-700 px-5 py-2.5 text-sm font-semibold text-white disabled:opacity-40">{guardando ? "Creando…" : "Crear corrida"}</button>
        </div>
      </form>
    </div>
  );
}

function Selector({ texto, valor, cambiar, children }: { texto: string; valor: string; cambiar: (valor: string) => void; children: React.ReactNode }) {
  return <label className="text-sm font-medium text-slate-700">{texto}<select required={texto !== "Lote de suero (si se medirá)"} value={valor} onChange={(evento) => cambiar(evento.target.value)} className={campo}>{children}</select></label>;
}
