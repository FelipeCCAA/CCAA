import { useState } from "react";
import { useSearchParams } from "react-router-dom";
import { Plus, RefreshCw } from "lucide-react";

import { mensajeDe, useCarga } from "../../components/seccion/utilidades";
import {
  buscarDescremaciones, cancelarPreparacionDescremado, iniciarDescremado,
  obtenerDescremacion, obtenerPuestoDescremado, type DescremadoraPuesto,
} from "../../services/descremado.service";
import { mensajeErrorProceso } from "../../services/errores-proceso";
import { cantidad } from "../../services/formato";
import { puedeOperarDescremado } from "../../services/permisos-descremado";
import type { CorridaDescremacion } from "../../services/procesos.service";
import { corridaCancelable } from "../../services/puesto-descremado";
import { obtenerSesion } from "../../services/sesion";
import TablaConsulta from "../Inventario/TablaConsulta";
import CancelarPreparacion from "./CancelarPreparacion";
import CierreDescremado from "./CierreDescremado";
import PrepararDescremado from "./PrepararDescremado";
import TarjetaDescremadora from "./TarjetaDescremadora";

type Cancelando = { id: number; codigo: string; filas: { etiqueta: string; valor: string }[] } | null;

const fecha = (iso: string | null) => (iso ? new Date(iso).toLocaleString("es-CL") : "—");

/*
  Puesto de Descremado: preparar el descremado de un silo (con sus reservas),
  iniciarlo cuando el servidor lo permite, cancelar una preparación y
  registrar las salidas, en una pantalla. Antes eran tres pasos en tres
  pantallas y un botón que preparaba e iniciaba a la vez.
*/
export default function PuestoDescremado() {
  const puesto = useCarga(obtenerPuestoDescremado);
  const [parametros, setParametros] = useSearchParams();
  const siloPedido = Number(parametros.get("silo"));
  const siloInicial = Number.isInteger(siloPedido) && siloPedido > 0 ? siloPedido : undefined;
  const [preparando, setPreparando] = useState<{ equipoId?: number } | null>(null);
  const [iniciando, setIniciando] = useState<number | null>(null);
  const [cerrando, setCerrando] = useState<CorridaDescremacion | null>(null);
  const [cancelando, setCancelando] = useState<Cancelando>(null);
  const [versionHistorial, setVersionHistorial] = useState(0);
  const [mensaje, setMensaje] = useState("");
  const [error, setError] = useState("");
  // Mismo criterio que el servidor (`puede_operar_tipo` con la etapa Descremación).
  const puedeOperar = puedeOperarDescremado(obtenerSesion()?.usuario);
  // «Descremar» del silo llega con `?silo=`: el formulario se abre solo, con ese silo.
  const formulario: { equipoId?: number } | null =
    preparando ?? (siloInicial !== undefined && puedeOperar ? {} : null);

  const cerrarFormulario = () => {
    setPreparando(null);
    if (siloInicial !== undefined) setParametros({}, { replace: true });
  };

  const iniciar = async (corridaId: number) => {
    setMensaje("");
    setError("");
    setIniciando(corridaId);
    try {
      const corrida = await iniciarDescremado(corridaId);
      setMensaje(`Descremado ${corrida.ejecucion_codigo} iniciado en ${corrida.equipo_nombre ?? "la descremadora"}.`);
    } catch (causa) {
      setError(mensajeErrorProceso(causa, "No se pudo iniciar el descremado."));
    } finally {
      setIniciando(null);
      await puesto.recargar();
    }
  };

  const abrirCierre = async (corridaId: number) => {
    setMensaje("");
    setError("");
    try {
      setCerrando(await obtenerDescremacion(corridaId));
    } catch (causa) {
      setError(mensajeDe(causa, "No se pudo cargar la corrida."));
    }
  };

  const cancelarDesdeTarjeta = (fila: DescremadoraPuesto) => {
    const corrida = fila.corrida;
    const id = corridaCancelable(corrida);
    if (!corrida || id === null) return;
    setCancelando({
      id, codigo: corrida.ejecucion_codigo,
      filas: [
        { etiqueta: "Descremadora", valor: fila.nombre },
        { etiqueta: "Origen", valor: `${corrida.silo_entera ?? "—"} · ${cantidad(corrida.litros_entrada, "L")}` },
        { etiqueta: "TK", valor: `${corrida.silo_descremada ?? "—"} y ${corrida.estanque_crema ?? "—"}` },
      ],
    });
  };

  const cancelarDesdeHistorial = (corrida: CorridaDescremacion) => {
    const id = corridaCancelable(corrida);
    if (id === null) return;
    setCancelando({
      id, codigo: corrida.ejecucion_codigo,
      filas: [
        { etiqueta: "Descremadora", valor: corrida.equipo_nombre ?? "—" },
        { etiqueta: "Origen", valor: `${corrida.silo_entera_codigo} · ${cantidad(corrida.litros_entrada, "L")}` },
      ],
    });
  };

  /* El modal muestra el error del servidor: por eso aquí se relanza. */
  const cancelar = async (motivo: string) => {
    if (!cancelando) return;
    const cancelada = await cancelarPreparacionDescremado(cancelando.id, motivo);
    setCancelando(null);
    setMensaje(`Preparación ${cancelada.ejecucion_codigo} cancelada; la descremadora y los TK quedan libres.`);
    setVersionHistorial((version) => version + 1);
    await puesto.recargar();
  };

  return (
    <main className="px-4 py-8 sm:px-8">
      <div className="mx-auto max-w-6xl space-y-6">
        <header className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <p className="text-sm font-semibold uppercase tracking-wider text-emerald-700">Puesto de trabajo</p>
            <h1 className="mt-1 text-3xl font-bold text-slate-900">Descremado</h1>
            <p className="mt-2 max-w-2xl text-slate-600">Prepara el descremado de un silo; luego inicia y registra las salidas desde la tarjeta de la descremadora.</p>
            {!puedeOperar && <p className="mt-2 text-sm font-medium text-slate-600">Vista de consulta: las acciones las registra Condensación.</p>}
          </div>
          <div className="flex items-center gap-2">
            <button type="button" onClick={() => void puesto.recargar()} aria-label="Actualizar" title="Actualizar" className="rounded-xl border border-slate-300 bg-white p-3 text-slate-600 hover:border-emerald-400 hover:text-emerald-700">
              <RefreshCw className="h-5 w-5" />
            </button>
            {puedeOperar && (
              <button type="button" onClick={() => { setMensaje(""); setPreparando({}); }} className="inline-flex items-center gap-2 rounded-xl bg-emerald-700 px-5 py-3 text-sm font-semibold text-white hover:bg-emerald-800">
                <Plus className="h-5 w-5" />Preparar descremado
              </button>
            )}
          </div>
        </header>

        {mensaje && <p role="status" className="rounded-xl border border-green-200 bg-green-50 px-4 py-3 text-sm text-green-900">{mensaje}</p>}
        {error && <p role="alert" className="rounded-xl bg-red-50 px-4 py-3 text-sm text-red-800">{error}</p>}
        {puesto.error && <p role="alert" className="text-sm text-red-800">{puesto.error}</p>}
        {puesto.cargando && !puesto.datos && <p className="text-sm text-slate-600">Cargando descremadoras…</p>}

        <section aria-label="Descremadoras" className="grid gap-4 md:grid-cols-2">
          <h2 className="sr-only">Descremadoras</h2>
          {puesto.datos?.descremadoras.map((fila) => (
            <TarjetaDescremadora
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
          {puesto.datos && puesto.datos.corridas_de_hoy.length === 0 && <p className="text-sm text-slate-600">Hoy no hay corridas de descremado.</p>}
          {puesto.datos && puesto.datos.corridas_de_hoy.length > 0 && (
            <ul className="divide-y divide-slate-100 rounded-2xl border border-slate-200 bg-white">
              {puesto.datos.corridas_de_hoy.map((c) => (
                <li key={c.id} className="flex flex-wrap justify-between gap-2 px-5 py-3 text-sm">
                  <span><span className="font-mono">{c.ejecucion_codigo}</span> · {c.equipo ?? "—"} · {c.silo_entera}</span>
                  <span className="text-slate-700">{c.situacion_etiqueta}</span>
                </li>
              ))}
            </ul>
          )}
        </section>

        <section aria-label="Historial de Descremado" className="space-y-3">
          <h2 className="text-lg font-semibold text-slate-900">Historial</h2>
          <TablaConsulta<CorridaDescremacion>
            key={versionHistorial}
            titulo="Historial de corridas de descremado"
            cargar={buscarDescremaciones}
            clave={(f) => f.id}
            ubicaciones={[]}
            conUbicacion={false}
            conFechas
            etiquetaBusqueda="Corrida, silo o TK"
            vacio="No hay corridas que coincidan."
            estados={(puesto.datos?.estados ?? []).map((o) => ({ valor: o.valor, texto: o.etiqueta }))}
            columnas={[
              { titulo: "Corrida", celda: (f) => <span className="font-mono">{f.ejecucion_codigo}</span> },
              { titulo: "Descremadora", celda: (f) => f.equipo_nombre ?? "—" },
              { titulo: "Origen", celda: (f) => `${f.silo_entera_codigo} · ${cantidad(f.litros_entrada, "L")}` },
              { titulo: "Destinos", celda: (f) => `${f.silo_descremada_codigo} + ${f.estanque_crema_codigo}` },
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
        <PrepararDescremado
          puesto={puesto.datos}
          siloInicial={siloInicial}
          equipoInicial={formulario.equipoId}
          alCerrar={cerrarFormulario}
          alPreparar={(codigo) => {
            cerrarFormulario();
            setMensaje(`Descremado ${codigo} preparado: las reservas quedaron tomadas. Inícialo desde la tarjeta cuando el servidor lo permita.`);
            setVersionHistorial((version) => version + 1);
            void puesto.recargar();
          }}
        />
      )}
      {cerrando && (
        <CierreDescremado
          corrida={cerrando}
          alCerrar={() => setCerrando(null)}
          alCompletarse={(corrida) => {
            setCerrando(null);
            setMensaje(`Corrida ${corrida.ejecucion_codigo} cerrada; las dos ramas pasan a Calidad si la etapa lo exige.`);
            setVersionHistorial((version) => version + 1);
            void puesto.recargar();
          }}
        />
      )}
      {cancelando && (
        <CancelarPreparacion
          codigo={cancelando.codigo}
          filas={cancelando.filas}
          alVolver={() => setCancelando(null)}
          alCancelar={cancelar}
        />
      )}
    </main>
  );
}
