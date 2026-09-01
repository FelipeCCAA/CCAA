import { useMemo, useState } from "react";
import { X } from "lucide-react";

import {
  cerrarCondensacion,
  type CorridaCondensacion,
} from "../../services/procesos.service";

const campo = "mt-1 w-full rounded-xl border border-slate-300 px-3 py-2.5 text-sm outline-none focus:border-blue-600";

function mensajeDe(error: unknown) {
  const datos = (error as { response?: { data?: unknown } }).response?.data;
  if (typeof datos === "string") return datos;
  if (datos && typeof datos === "object") {
    return Object.values(datos as Record<string, unknown>).flat().map(String).join(" ");
  }
  return "No se pudo cerrar la evaporación.";
}

export default function CierreCondensacion({ corrida, onCerrar, onCerrada }: {
  corrida: CorridaCondensacion;
  onCerrar: () => void;
  onCerrada: (corrida: CorridaCondensacion) => void | Promise<void>;
}) {
  const [datos, setDatos] = useState({
    litros_precondensado: "", flujo_promedio: "", densidad_salida: "",
    solidos_salida: "", temperatura_salida: "", vacio_promedio: "",
    presion_promedio: "",
  });
  const [ocupado, setOcupado] = useState(false);
  const [error, setError] = useState("");
  const rendimiento = useMemo(() => {
    const entrada = Number(corrida.litros_entrada);
    const salida = Number(datos.litros_precondensado);
    return entrada > 0 && salida > 0 ? (salida / entrada) * 100 : null;
  }, [corrida.litros_entrada, datos.litros_precondensado]);

  const guardar = async (evento: React.FormEvent) => {
    evento.preventDefault();
    setError("");
    if (Number(datos.litros_precondensado) > Number(corrida.litros_entrada)) {
      setError("La salida no puede superar los litros de entrada.");
      return;
    }
    setOcupado(true);
    try {
      const opcionales = Object.fromEntries(
        Object.entries(datos)
          .filter(([clave, valor]) => clave !== "litros_precondensado" && valor !== "")
          .map(([clave, valor]) => [clave, Number(valor)]),
      );
      await onCerrada(await cerrarCondensacion(corrida.id, {
        litros_precondensado: Number(datos.litros_precondensado),
        ...opcionales,
      }));
    } catch (e) {
      setError(mensajeDe(e));
    } finally {
      setOcupado(false);
    }
  };

  return <div className="fixed inset-0 z-[80] flex items-start justify-center overflow-y-auto bg-slate-950/45 p-4">
    <form onSubmit={guardar} className="my-8 w-full max-w-3xl rounded-2xl bg-white p-6 shadow-xl">
      <div className="flex items-start justify-between gap-4">
        <div><p className="text-xs font-bold uppercase tracking-wide text-blue-700">{corrida.ejecucion_codigo}</p><h2 className="mt-1 text-xl font-bold text-slate-900">Cerrar evaporación</h2><p className="mt-2 text-sm text-slate-600">{corrida.silo_origen_codigo} → {corrida.silo_destino_codigo} · entrada {Number(corrida.litros_entrada).toLocaleString("es-CL")} L</p></div>
        <button type="button" onClick={onCerrar} className="rounded-lg p-2 hover:bg-slate-100" aria-label="Cerrar"><X className="h-5 w-5" /></button>
      </div>
      <div className="mt-6 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        <Etiqueta texto="Precondensado obtenido (L)"><input required min="0.01" max={corrida.litros_entrada} step="0.01" type="number" value={datos.litros_precondensado} onChange={(e) => setDatos({ ...datos, litros_precondensado: e.target.value })} className={campo} /></Etiqueta>
        <Etiqueta texto="Sólidos de salida (%)"><input min="0" step="0.01" type="number" value={datos.solidos_salida} onChange={(e) => setDatos({ ...datos, solidos_salida: e.target.value })} className={campo} /></Etiqueta>
        <Etiqueta texto="Densidad de salida"><input min="0" step="0.001" type="number" value={datos.densidad_salida} onChange={(e) => setDatos({ ...datos, densidad_salida: e.target.value })} className={campo} /></Etiqueta>
        <Etiqueta texto="Temperatura de salida (°C)"><input step="0.01" type="number" value={datos.temperatura_salida} onChange={(e) => setDatos({ ...datos, temperatura_salida: e.target.value })} className={campo} /></Etiqueta>
        <Etiqueta texto="Flujo promedio"><input min="0" step="0.01" type="number" value={datos.flujo_promedio} onChange={(e) => setDatos({ ...datos, flujo_promedio: e.target.value })} className={campo} /></Etiqueta>
        <Etiqueta texto="Vacío promedio"><input step="0.01" type="number" value={datos.vacio_promedio} onChange={(e) => setDatos({ ...datos, vacio_promedio: e.target.value })} className={campo} /></Etiqueta>
        <Etiqueta texto="Presión promedio"><input step="0.01" type="number" value={datos.presion_promedio} onChange={(e) => setDatos({ ...datos, presion_promedio: e.target.value })} className={campo} /></Etiqueta>
      </div>
      {rendimiento !== null && <p className="mt-4 rounded-xl bg-blue-50 px-4 py-3 text-sm text-blue-900">Rendimiento volumétrico de referencia: <b>{rendimiento.toLocaleString("es-CL", { maximumFractionDigits: 1 })}%</b>. El balance queda registrado con entrada y salida reales.</p>}
      {error && <p className="mt-4 rounded-xl bg-rose-50 px-4 py-3 text-sm text-rose-700">{error}</p>}
      <div className="mt-6 flex justify-end gap-3"><button type="button" onClick={onCerrar} className="px-4 py-2.5 text-sm text-slate-600">Cancelar</button><button disabled={ocupado} className="rounded-xl bg-blue-700 px-5 py-2.5 text-sm font-semibold text-white disabled:opacity-40">{ocupado ? "Cerrando…" : "Registrar salida y enviar a Calidad"}</button></div>
    </form>
  </div>;
}

function Etiqueta({ texto, children }: { texto: string; children: React.ReactNode }) {
  return <label className="text-sm font-medium text-slate-700">{texto}{children}</label>;
}
