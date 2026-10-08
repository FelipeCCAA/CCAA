import { useState } from "react";
import { useSearchParams } from "react-router-dom";
import { Plus, RefreshCw } from "lucide-react";

import CancelarPreparacion from "../../components/operacion/CancelarPreparacion";
import { mensajeDe, useCarga } from "../../components/seccion/utilidades";
import { mensajeErrorProceso } from "../../services/errores-proceso";
import { cantidad } from "../../services/formato";
import {
  buscarMantequillas, cancelarPreparacionMantequilla, iniciarMantequilla,
  obtenerMantequilla, obtenerPuestoMantequilla, type MantequeraPuesto,
} from "../../services/mantequilla.service";
import { puedeOperarMantequilla } from "../../services/permisos-mantequilla";
import type { CorridaMantequilla } from "../../services/procesos.service";
import { corridaCancelable } from "../../services/puesto-mantequilla";
import { obtenerSesion } from "../../services/sesion";
import TablaConsulta from "../Inventario/TablaConsulta";
import CierreMantequilla from "./CierreMantequilla";
import PrepararMantequilla from "./PrepararMantequilla";
import TarjetaMantequera from "./TarjetaMantequera";

type Cancelando = {
  id: number; codigo: string; advertencia: string; filas: { etiqueta: string; valor: string }[];
} | null;

const fecha = (iso: string | null) => (iso ? new Date(iso).toLocaleString("es-CL") : "—");
const advertenciaDe = (lote: string | null) =>
  `Se anulará el lote ${lote ?? "de salida"} y la mantequera quedará libre. No se mueve crema: entra a la mantequera recién al iniciar.`;

/*
  Puesto de Mantequilla: preparar una corrida sobre una mantequera (que la
  toma), iniciarla cuando el servidor lo permite, cancelar una preparación y
  registrar el balance, en una pantalla. Antes era una sección de /procesos
  con dos modales y un «Iniciar» que siempre se ofrecía.
*/
export default function PuestoMantequilla() {
  const puesto = useCarga(obtenerPuestoMantequilla);
  const [parametros, setParametros] = useSearchParams();
  const cremaPedida = Number(parametros.get("crema"));
  const cremaInicial = Number.isInteger(cremaPedida) && cremaPedida > 0 ? cremaPedida : undefined;
  const [preparando, setPreparando] = useState<{ equipoId?: number } | null>(null);
  const [iniciando, setIniciando] = useState<number | null>(null);
  const [cerrando, setCerrando] = useState<CorridaMantequilla | null>(null);
  const [cancelando, setCancelando] = useState<Cancelando>(null);
  const [versionHistorial, setVersionHistorial] = useState(0);
  const [mensaje, setMensaje] = useState("");
  const [error, setError] = useState("");
  // Mismo criterio que el servidor (`puede_operar_tipo` con la etapa Mantequilla).
  const puedeOperar = puedeOperarMantequilla(obtenerSesion()?.usuario);
  // «Preparar en Mantequilla» llega con `?crema=`: el formulario se abre solo, con esa crema.
  const formulario: { equipoId?: number } | null =
    preparando ?? (cremaInicial !== undefined && puedeOperar ? {} : null);

  const cerrarFormulario = () => {
    setPreparando(null);
    if (cremaInicial !== undefined) setParametros({}, { replace: true });
  };

  const iniciar = async (corridaId: number) => {
    setMensaje("");
    setError("");
    setIniciando(corridaId);
    try {
      const corrida = await iniciarMantequilla(corridaId);
      setMensaje(`Mantequilla ${corrida.ejecucion_codigo} iniciada en ${corrida.equipo_nombre ?? "la mantequera"}.`);
    } catch (causa) {
      setError(mensajeErrorProceso(causa, "No se pudo iniciar la mantequilla."));
    } finally {
      setIniciando(null);
      await puesto.recargar();
    }
  };

  const abrirCierre = async (corridaId: number) => {
    setMensaje("");
    setError("");
    try {
      setCerrando(await obtenerMantequilla(corridaId));
    } catch (causa) {
      setError(mensajeDe(causa, "No se pudo cargar la corrida."));
    }
  };

  const cancelarDesdeTarjeta = (fila: MantequeraPuesto) => {
    const corrida = fila.corrida;
    const id = corridaCancelable(corrida);
    if (!corrida || id === null) return;
    setCancelando({
      id, codigo: corrida.ejecucion_codigo, advertencia: advertenciaDe(corrida.lote_mantequilla),
      filas: [
        { etiqueta: "Mantequera", valor: fila.nombre },
        { etiqueta: "Crema", valor: `${corrida.lote_crema ?? "—"} · ${cantidad(corrida.kg_crema, "kg")}` },
        { etiqueta: "Lote de salida", valor: corrida.lote_mantequilla ?? "—" },
      ],
    });
  };

  const cancelarDesdeHistorial = (corrida: CorridaMantequilla) => {
    const id = corridaCancelable(corrida);
    if (id === null) return;
    setCancelando({
      id, codigo: corrida.ejecucion_codigo, advertencia: advertenciaDe(corrida.mantequilla_codigo),
      filas: [
        { etiqueta: "Mantequera", valor: corrida.equipo_nombre ?? "—" },
        { etiqueta: "Crema", valor: `${corrida.crema_codigo} · ${cantidad(corrida.kg_crema, "kg")}` },
        { etiqueta: "Lote de salida", valor: corrida.mantequilla_codigo },
      ],
    });
  };

  /* El modal muestra el error del servidor: por eso aquí se relanza. */
  const cancelar = async (motivo: string) => {
    if (!cancelando) return;
    const cancelada = await cancelarPreparacionMantequilla(cancelando.id, motivo);
    setCancelando(null);
    setMensaje(`Preparación ${cancelada.ejecucion_codigo} cancelada: el lote de salida quedó anulado y la mantequera libre.`);
    setVersionHistorial((version) => version + 1);
    await puesto.recargar();
  };

  return (
    <main className="px-4 py-8 sm:px-8">
      <div className="mx-auto max-w-6xl space-y-6">
        <header className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <p className="text-sm font-semibold uppercase tracking-wider text-amber-700">Puesto de trabajo</p>
            <h1 className="mt-1 text-3xl font-bold text-slate-900">Mantequilla</h1>
            <p className="mt-2 max-w-2xl text-slate-600">Prepara una corrida con crema liberada; luego inicia y registra el balance desde la tarjeta de la mantequera.</p>
            {!puedeOperar && <p className="mt-2 text-sm font-medium text-slate-600">Vista de consulta: las acciones las registra Condensación.</p>}
          </div>
          <div className="flex items-center gap-2">
            <button type="button" onClick={() => void puesto.recargar()} aria-label="Actualizar" title="Actualizar" className="rounded-xl border border-slate-300 bg-white p-3 text-slate-600 hover:border-amber-400 hover:text-amber-700">
              <RefreshCw className="h-5 w-5" />
            </button>
            {puedeOperar && (
              <button type="button" onClick={() => { setMensaje(""); setPreparando({}); }} className="inline-flex items-center gap-2 rounded-xl bg-amber-700 px-5 py-3 text-sm font-semibold text-white hover:bg-amber-800">
                <Plus className="h-5 w-5" />Preparar mantequilla
              </button>
            )}
          </div>
        </header>

        {mensaje && <p role="status" className="rounded-xl border border-green-200 bg-green-50 px-4 py-3 text-sm text-green-900">{mensaje}</p>}
        {error && <p role="alert" className="rounded-xl bg-red-50 px-4 py-3 text-sm text-red-800">{error}</p>}
        {puesto.error && <p role="alert" className="text-sm text-red-800">{puesto.error}</p>}
        {puesto.cargando && !puesto.datos && <p className="text-sm text-slate-600">Cargando mantequeras…</p>}
        {puesto.datos && puesto.datos.mantequeras.length === 0 && (
          <p className="rounded-xl bg-amber-50 px-4 py-3 text-sm text-amber-900">No hay mantequeras activas: créalas en Maestros › Máquinas con tipo «Mantequera».</p>
        )}

        <section aria-label="Mantequeras" className="grid gap-4 md:grid-cols-2">
          <h2 className="sr-only">Mantequeras</h2>
          {puesto.datos?.mantequeras.map((fila) => (
            <TarjetaMantequera
              key={fila.equipo_id}
              fila={fila}
              ocupado={iniciando !== null && iniciando === fila.corrida?.id}
              puedeOperar={puedeOperar}
              onPreparar={(equipoId) => { setMensaje(""); setPreparando({ equipoId }); }}
              onIniciar={(id) => void iniciar(id)}
              onCerrar={(id) => void abrirCierre(id)}
              onCancelar={cancelarDesdeTarjeta}
            />
          ))}
        </section>

        <section aria-label="Corridas de hoy" className="space-y-2">
          <h2 className="text-lg font-semibold text-slate-900">Corridas de hoy</h2>
          {puesto.datos && puesto.datos.corridas_de_hoy.length === 0 && <p className="text-sm text-slate-600">Hoy no hay corridas de mantequilla.</p>}
          {puesto.datos && puesto.datos.corridas_de_hoy.length > 0 && (
            <ul className="divide-y divide-slate-100 rounded-2xl border border-slate-200 bg-white">
              {puesto.datos.corridas_de_hoy.map((c) => (
                <li key={c.id} className="flex flex-wrap justify-between gap-2 px-5 py-3 text-sm">
                  <span><span className="font-mono">{c.ejecucion_codigo}</span> · {c.equipo ?? "—"} · {c.lote_crema} → {c.lote_mantequilla}</span>
                  <span className="text-slate-700">{c.situacion_etiqueta}</span>
                </li>
              ))}
            </ul>
          )}
        </section>

        <section aria-label="Historial de Mantequilla" className="space-y-3">
          <h2 className="text-lg font-semibold text-slate-900">Historial</h2>
          <TablaConsulta<CorridaMantequilla>
            key={versionHistorial}
            titulo="Historial de corridas de mantequilla"
            cargar={buscarMantequillas}
            clave={(f) => f.id}
            ubicaciones={[]}
            conUbicacion={false}
            conFechas
            etiquetaBusqueda="Corrida, lote u OP"
            vacio="No hay corridas que coincidan."
            estados={(puesto.datos?.estados ?? []).map((o) => ({ valor: o.valor, texto: o.etiqueta }))}
            columnas={[
              { titulo: "Corrida", celda: (f) => <span className="font-mono">{f.ejecucion_codigo}</span> },
              { titulo: "Mantequera", celda: (f) => f.equipo_nombre ?? "—" },
              { titulo: "Crema", celda: (f) => `${f.crema_codigo} · ${cantidad(f.kg_crema, "kg")}` },
              { titulo: "Lote de salida", celda: (f) => f.mantequilla_codigo },
              { titulo: "Inicio", celda: (f) => fecha(f.iniciada_en) },
              { titulo: "Situación", celda: (f) => f.situacion_etiqueta },
              {
                titulo: "Acción",
                celda: (f) => puedeOperar && corridaCancelable(f) !== null
                  ? <button type="button" onClick={() => cancelarDesdeHistorial(f)} className="text-xs font-semibold text-slate-700 underline">Cancelar preparación</button>
                  : null,
              },
            ]}
          />
        </section>
      </div>

      {formulario !== null && puesto.datos && (
        <PrepararMantequilla
          puesto={puesto.datos}
          cremaInicial={cremaInicial}
          equipoInicial={formulario.equipoId}
          alCerrar={cerrarFormulario}
          alPreparar={(codigo) => {
            cerrarFormulario();
            setMensaje(`Mantequilla ${codigo} preparada: la mantequera quedó tomada. Iníciala desde la tarjeta cuando el servidor lo permita.`);
            setVersionHistorial((version) => version + 1);
            void puesto.recargar();
          }}
        />
      )}
      {cerrando && (
        <CierreMantequilla
          corrida={cerrando}
          alCerrar={() => setCerrando(null)}
          alCompletarse={(corrida) => {
            setCerrando(null);
            setMensaje(`Corrida ${corrida.ejecucion_codigo} cerrada; la mantequilla pasa a Calidad.`);
            setVersionHistorial((version) => version + 1);
            void puesto.recargar();
          }}
        />
      )}
      {cancelando && (
        <CancelarPreparacion
          codigo={cancelando.codigo}
          filas={cancelando.filas}
          advertencia={cancelando.advertencia}
          alVolver={() => setCancelando(null)}
          alCancelar={cancelar}
        />
      )}
    </main>
  );
}
