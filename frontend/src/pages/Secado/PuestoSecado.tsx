import { useState } from "react";
import { Plus, RefreshCw } from "lucide-react";

import { mensajeDe, useCarga } from "../../components/seccion/utilidades";
import { mensajeErrorProceso } from "../../services/errores-proceso";
import { cantidad } from "../../services/formato";
import { puedeOperarSecado } from "../../services/permisos-secado";
import { situacionDeCorrida } from "../../services/puesto-secado";
import {
  buscarSecados, cancelarPreparacionSecado, iniciarSecado, obtenerPuestoSecado, obtenerSecado,
  type CorridaSecado,
} from "../../services/secado.service";
import { obtenerSesion } from "../../services/sesion";
import TablaConsulta from "../Inventario/TablaConsulta";
import CierreSecado from "./CierreSecado";
import TarjetaTorre from "./TarjetaTorre";
import TomarConcentrado from "./TomarConcentrado";

/* `equipoId` ausente = abrir sin torre preelegida (botón del encabezado). */
type Tomando = { equipoId?: number } | null;

const fecha = (iso: string | null) => (iso ? new Date(iso).toLocaleString("es-CL") : "—");

/*
  Puesto de Secado: tomar el concentrado (o la alimentación externa) para una
  torre, iniciar y cerrar el balance, en una pantalla. Antes eran tres pasos
  en tres pantallas, y el inicio vivía en una bandeja genérica.
*/
export default function PuestoSecado() {
  const puesto = useCarga(obtenerPuestoSecado);
  const [tomando, setTomando] = useState<Tomando>(null);
  const [iniciando, setIniciando] = useState<number | null>(null);
  const [cerrando, setCerrando] = useState<CorridaSecado | null>(null);
  const [mensaje, setMensaje] = useState("");
  const [error, setError] = useState("");
  // Mismo criterio que el servidor (`puede_operar_tipo` con la etapa Secado).
  const puedeOperar = puedeOperarSecado(obtenerSesion()?.usuario);

  const iniciar = async (corridaId: number) => {
    setMensaje("");
    setError("");
    setIniciando(corridaId);
    try {
      const corrida = await iniciarSecado(corridaId);
      setMensaje(`Secado ${corrida.ejecucion_codigo} iniciado en ${corrida.equipo_nombre ?? "la torre"}.`);
      await puesto.recargar();
    } catch (causa) {
      setError(mensajeErrorProceso(causa, "No se pudo iniciar el secado."));
      await puesto.recargar();
    } finally {
      setIniciando(null);
    }
  };

  /* La tarjeta muestra el error en su confirmación: por eso aquí se relanza. */
  const cancelarPreparacion = async (corridaId: number, motivo: string) => {
    setMensaje("");
    setError("");
    const cancelada = await cancelarPreparacionSecado(corridaId, motivo);
    setMensaje(`Preparación ${cancelada.ejecucion_codigo} cancelada; la torre queda disponible.`);
    await puesto.recargar();
  };

  /* Etiqueta del servidor para un estado que el historial no nombra. */
  const etiquetaDe = (estado: string) => puesto.datos?.estados.find((o) => o.valor === estado)?.etiqueta;

  const prepararCierre = async (corridaId: number) => {
    setMensaje("");
    setError("");
    try {
      setCerrando(await obtenerSecado(corridaId));
    } catch (causa) {
      setError(mensajeDe(causa, "No se pudo cargar la corrida."));
    }
  };

  return (
    <main className="px-4 py-8 sm:px-8">
      <div className="mx-auto max-w-6xl space-y-6">
        <header className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <p className="text-sm font-semibold uppercase tracking-wider text-amber-700">Puesto de trabajo</p>
            <h1 className="mt-1 text-3xl font-bold text-slate-900">Secado</h1>
            <p className="mt-2 max-w-2xl text-slate-600">Toma el concentrado liberado para una torre; luego inicia el secado y registra el balance desde la tarjeta de la torre.</p>
            {!puedeOperar && <p className="mt-2 text-sm font-medium text-slate-600">Vista de consulta: las acciones las registra Secado.</p>}
          </div>
          <div className="flex items-center gap-2">
            <button type="button" onClick={() => void puesto.recargar()} aria-label="Actualizar" title="Actualizar" className="rounded-xl border border-slate-300 bg-white p-3 text-slate-600 hover:border-amber-400 hover:text-amber-700">
              <RefreshCw className="h-5 w-5" />
            </button>
            {puedeOperar && (
              <button type="button" onClick={() => { setMensaje(""); setTomando({}); }} className="inline-flex items-center gap-2 rounded-xl bg-amber-700 px-5 py-3 text-sm font-semibold text-white hover:bg-amber-800">
                <Plus className="h-5 w-5" />Tomar concentrado
              </button>
            )}
          </div>
        </header>

        {mensaje && <p role="status" className="rounded-xl border border-green-200 bg-green-50 px-4 py-3 text-sm text-green-900">{mensaje}</p>}
        {error && <p role="alert" className="rounded-xl bg-red-50 px-4 py-3 text-sm text-red-800">{error}</p>}
        {puesto.error && <p role="alert" className="text-sm text-red-800">{puesto.error}</p>}
        {puesto.cargando && !puesto.datos && <p className="text-sm text-slate-600">Cargando torres…</p>}

        <section aria-label="Torres" className="grid gap-4 md:grid-cols-2">
          <h2 className="sr-only">Torres</h2>
          {puesto.datos?.torres.map((fila) => (
            <TarjetaTorre
              key={fila.equipo_id}
              fila={fila}
              ocupado={iniciando !== null && iniciando === fila.corrida?.id}
              puedeOperar={puedeOperar}
              onTomar={(equipoId) => { setMensaje(""); setTomando({ equipoId }); }}
              onIniciar={(id) => void iniciar(id)}
              onCerrar={(id) => void prepararCierre(id)}
              onCancelar={cancelarPreparacion}
            />
          ))}
        </section>

        <section aria-label="Corridas de hoy" className="space-y-2">
          <h2 className="text-lg font-semibold text-slate-900">Corridas de hoy</h2>
          {puesto.datos && puesto.datos.corridas_de_hoy.length === 0 && <p className="text-sm text-slate-600">Hoy no hay corridas de secado iniciadas ni cerradas.</p>}
          {puesto.datos && puesto.datos.corridas_de_hoy.length > 0 && (
            <ul className="divide-y divide-slate-100 rounded-2xl border border-slate-200 bg-white">
              {puesto.datos.corridas_de_hoy.map((c) => (
                <li key={c.id} className="flex flex-wrap justify-between gap-2 px-5 py-3 text-sm">
                  <span>Lote <span className="font-mono">{c.lote_codigo}</span> · {c.equipo ?? "—"}</span>
                  <span className="text-slate-700">{situacionDeCorrida(c.estado, c.estado_calidad, etiquetaDe(c.estado))}</span>
                </li>
              ))}
            </ul>
          )}
        </section>

        <section aria-label="Historial de Secado" className="space-y-3">
          <h2 className="text-lg font-semibold text-slate-900">Historial</h2>
          <TablaConsulta<CorridaSecado>
            titulo="Historial de corridas de Secado"
            cargar={buscarSecados}
            clave={(f) => f.id}
            ubicaciones={[]}
            conUbicacion={false}
            conFechas
            etiquetaBusqueda="Lote, corrida o producto"
            vacio="No hay corridas que coincidan."
            estados={(puesto.datos?.estados ?? []).map((o) => ({ valor: o.valor, texto: o.etiqueta }))}
            columnas={[
              { titulo: "Lote", celda: (f) => <span className="font-mono">{f.lote_codigo}</span> },
              { titulo: "Torre", celda: (f) => f.equipo_nombre ?? "—" },
              { titulo: "Producto", celda: (f) => f.producto_nombre },
              { titulo: "Inicio", celda: (f) => fecha(f.iniciada_en) },
              { titulo: "Polvo", numerica: true, celda: (f) => cantidad(f.kg_polvo, "kg") },
              { titulo: "Situación", celda: (f) => situacionDeCorrida(f.estado, f.estado_calidad, f.estado_etiqueta) },
            ]}
          />
        </section>
      </div>

      {tomando !== null && puesto.datos && (
        <TomarConcentrado
          torres={puesto.datos.torres}
          concentrados={puesto.datos.concentrados}
          torreInicial={tomando.equipoId}
          alCerrar={() => setTomando(null)}
          alPreparar={(texto) => { setTomando(null); setMensaje(texto); void puesto.recargar(); }}
        />
      )}
      {cerrando && (
        <CierreSecado
          corrida={cerrando}
          alCerrar={() => setCerrando(null)}
          alCompletarse={(corrida) => {
            setCerrando(null);
            setMensaje(`Corrida ${corrida.ejecucion_codigo} cerrada; el polvo pasa a Calidad si la etapa lo exige.`);
            void puesto.recargar();
          }}
        />
      )}
    </main>
  );
}
