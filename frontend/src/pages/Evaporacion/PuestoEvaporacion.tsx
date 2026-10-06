import { lazy, Suspense, useState } from "react";
import { Plus } from "lucide-react";

import { useCarga, mensajeDe } from "../../components/seccion/utilidades";
import { mensajeErrorProceso } from "../../services/errores-proceso";
import {
  iniciarCondensacion, obtenerCondensacion, obtenerPuestoEvaporacion, type CorridaCondensacion,
} from "../../services/procesos.service";
import CierreCondensacion from "../Procesos/CierreCondensacion";
import TarjetaEvaporador from "./TarjetaEvaporador";

const FormularioLote = lazy(() => import("../Produccion/FormularioLote"));

/* Qué evaporador tiene abierto el formulario de lote, si alguno. `equipoId`
   ausente es "abrir sin preelegir" -el botón del encabezado-, no `0`: un
   centinela numérico se confundiría con un id real si alguna vez existiera
   un equipo con esa clave. */
type AbriendoEn = { equipoId?: number } | null;

/*
  Puesto de Evaporación: abrir el lote (que también prepara la corrida),
  iniciarla y cerrarla, en una pantalla. Antes eran 5 pasos en 3 pantallas.
*/
export default function PuestoEvaporacion() {
  const puesto = useCarga(obtenerPuestoEvaporacion);
  const [abriendoEn, setAbriendoEn] = useState<AbriendoEn>(null);
  const [iniciando, setIniciando] = useState<number | null>(null);
  const [cerrando, setCerrando] = useState<CorridaCondensacion | null>(null);
  const [mensaje, setMensaje] = useState("");
  const [error, setError] = useState("");

  const iniciar = async (corridaId: number) => {
    setIniciando(corridaId);
    setError("");
    try {
      const corrida = await iniciarCondensacion(corridaId);
      setMensaje(`Evaporación ${corrida.ejecucion_codigo} iniciada.`);
      await puesto.recargar();
    } catch (causa) {
      setError(mensajeErrorProceso(causa, "No se pudo iniciar la evaporación."));
    } finally {
      setIniciando(null);
    }
  };

  const prepararCierre = async (corridaId: number) => {
    setError("");
    try {
      setCerrando(await obtenerCondensacion(corridaId));
    } catch (causa) {
      setError(mensajeDe(causa, "No se pudo cargar la corrida."));
    }
  };

  return (
    <div className="px-4 py-8 sm:px-8">
      <div className="mx-auto max-w-6xl space-y-6">
        <header className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <p className="text-sm font-semibold uppercase tracking-wider text-blue-700">Puesto de trabajo</p>
            <h1 className="mt-1 text-3xl font-bold text-slate-900">Evaporación</h1>
            <p className="mt-2 max-w-2xl text-slate-600">Abre el lote desde el vale y elige el destino del concentrado; luego inicia y cierra la corrida desde la tarjeta del evaporador.</p>
          </div>
          <button
            type="button"
            onClick={() => { setMensaje(""); setAbriendoEn({}); }}
            className="inline-flex items-center gap-2 rounded-xl bg-blue-700 px-5 py-3 text-sm font-semibold text-white hover:bg-blue-800"
          >
            <Plus className="h-5 w-5" />
            Abrir lote desde vale
          </button>
        </header>

        {mensaje && <p role="status" className="rounded-xl border border-green-200 bg-green-50 px-4 py-3 text-sm text-green-900">{mensaje}</p>}
        {error && <p role="alert" className="rounded-xl bg-red-50 px-4 py-3 text-sm text-red-800">{error}</p>}
        {puesto.error && <p role="alert" className="text-sm text-red-800">{puesto.error}</p>}
        {puesto.cargando && !puesto.datos && <p className="text-sm text-slate-600">Cargando evaporadores…</p>}

        <section aria-label="Evaporadores" className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          {puesto.datos?.evaporadores.map((fila) => (
            <TarjetaEvaporador
              key={fila.equipo_id}
              fila={fila}
              ocupado={iniciando === fila.corrida?.id}
              onAbrir={(equipoId) => { setMensaje(""); setAbriendoEn({ equipoId }); }}
              onIniciar={(id) => void iniciar(id)}
              onCerrar={(id) => void prepararCierre(id)}
            />
          ))}
        </section>

        <section aria-label="Corridas de hoy" className="space-y-2">
          <h2 className="text-lg font-semibold text-slate-900">Corridas de hoy</h2>
          {puesto.datos && puesto.datos.corridas_de_hoy.length === 0 && <p className="text-sm text-slate-600">Hoy no hay corridas de evaporación.</p>}
          <ul className="divide-y divide-slate-100 rounded-2xl border border-slate-200 bg-white">
            {puesto.datos?.corridas_de_hoy.map((c) => (
              <li key={c.id} className="flex flex-wrap justify-between gap-2 px-5 py-3 text-sm">
                <span><span className="font-mono">{c.codigo}</span> · {c.equipo ?? "—"}{c.lote_codigo ? ` · lote ${c.lote_codigo}` : ""}</span>
                <span className="text-slate-700">{c.estado_etiqueta}</span>
              </li>
            ))}
          </ul>
        </section>
      </div>

      {abriendoEn !== null && (
        <Suspense fallback={null}>
          <FormularioLote
            modo="evaporacion"
            equipoInicial={abriendoEn.equipoId}
            destinos={puesto.datos?.destinos ?? []}
            alCerrar={() => setAbriendoEn(null)}
            alGuardar={() => { setMensaje("Lote abierto y evaporación preparada."); void puesto.recargar(); }}
          />
        </Suspense>
      )}
      {cerrando && (
        <CierreCondensacion
          corrida={cerrando}
          onCerrar={() => setCerrando(null)}
          onCerrada={async (corrida) => {
            setCerrando(null);
            setMensaje(`Salida de ${corrida.ejecucion_codigo} registrada; pasa a Calidad.`);
            await puesto.recargar();
          }}
        />
      )}
    </div>
  );
}
