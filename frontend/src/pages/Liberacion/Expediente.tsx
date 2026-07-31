import { useCallback, useEffect, useState } from "react";
import {
  AlertTriangle,
  Database,
  ArrowLeft,
  Check,
  CircleDashed,
  FileWarning,
  Lock,
  ShieldCheck,
} from "lucide-react";
import axios from "axios";

import {
  conceder,
  liberar,
  obtenerExpediente,
  type EstadoDocumento,
  type Expediente as ExpedienteTipo,
} from "../../services/calidad.service";

import { kilos } from "../../services/produccion.service";
import { puedeEscribir } from "../../services/sesion";

import FormularioDinamico from "./FormularioDinamico";


/*
  El expediente de liberación de un lote.

  Muestra los tres cosas que deciden si el producto sale: el checklist
  documental, el veredicto del laboratorio y los motivos que lo bloquean.

  Nada de esto se guarda: el backend lo recalcula en cada llamada. Por eso,
  después de tocar un formulario, se vuelve a pedir el expediente entero en
  vez de actualizar el estado a mano — cualquier atajo aquí acabaría
  mostrando un avance que ya no es cierto.
*/

interface Props {
  loteId: number;
  alVolver: () => void;
}



const ESTILO_CALIDAD: Record<string, string> = {
  conforme: "bg-green-50 text-green-700",
  no_conforme: "bg-red-50 text-red-700",
  sin_analisis: "bg-slate-100 text-slate-600",
  sin_especificacion: "bg-slate-100 text-slate-600",
};


function IconoDocumento({ estado }: { estado: EstadoDocumento }) {

  if (estado.observado) {
    return <FileWarning className="h-5 w-5 shrink-0 text-amber-600" />;
  }

  // Se distingue del visto manual a propósito: uno dice que alguien lo
  // afirmó, el otro que el sistema tiene el registro.
  if (estado.cumplido_por_dato) {
    return <Database className="h-5 w-5 shrink-0 text-green-600" />;
  }

  if (estado.completo) {
    return <Check className="h-5 w-5 shrink-0 text-green-600" />;
  }

  return <CircleDashed className="h-5 w-5 shrink-0 text-slate-300" />;
}


function Expediente({ loteId, alVolver }: Props) {

  const [expediente, setExpediente] = useState<ExpedienteTipo | null>(null);
  const [cargando, setCargando] = useState(true);
  const [error, setError] = useState("");

  const [abierto, setAbierto] = useState<EstadoDocumento | null>(null);

  const [motivo, setMotivo] = useState("");
  const [pidiendoMotivo, setPidiendoMotivo] = useState(false);
  const [firmando, setFirmando] = useState(false);

  const puedeFirmar = puedeEscribir("calidad");

  const cargar = useCallback(async () => {

    setCargando(true);
    setError("");

    try {
      setExpediente(await obtenerExpediente(loteId));
    } catch {
      setError("No se pudo cargar el expediente.");
    } finally {
      setCargando(false);
    }

  }, [loteId]);

  // Diferido para no actualizar el estado dentro del propio efecto.
  useEffect(() => {

    const temporizador = setTimeout(cargar, 0);

    return () => clearTimeout(temporizador);

  }, [cargar]);

  const firmar = async (viaConcesion: boolean) => {

    setError("");
    setFirmando(true);

    try {

      if (viaConcesion) {
        await conceder(loteId, motivo);
      } else {
        await liberar(loteId);
      }

      setPidiendoMotivo(false);
      setMotivo("");
      await cargar();

    } catch (e) {

      // El 409 trae los bloqueos: es el rechazo que vale, el del servidor.
      if (axios.isAxiosError(e) && e.response?.status === 409) {
        const bloqueos = (e.response.data as { bloqueos?: string[] }).bloqueos;
        setError(bloqueos?.join(" ") || "No se puede liberar este lote.");
      } else if (axios.isAxiosError(e) && e.response?.status === 400) {
        const datos = e.response.data as Record<string, string[]>;
        setError(Object.values(datos).flat().join(" "));
      } else {
        setError("No se pudo firmar la liberación.");
      }

    } finally {
      setFirmando(false);
    }
  };

  if (cargando) {
    return <p className="text-sm text-slate-500">Cargando expediente…</p>;
  }

  if (!expediente) {
    return (
      <div>
        <button onClick={alVolver} className="text-sm text-green-700 hover:underline">
          ← Volver
        </button>
        <p className="mt-4 text-sm text-red-600">{error || "No se encontró el lote."}</p>
      </div>
    );
  }

  const { lote, decision, liberacion, discrepancias, prellenado } = expediente;
  const avance = decision.avance;
  const calidad = decision.calidad;

  return (
    <div className="space-y-6">

      {/* Cabecera */}

      <div>

        <button
          onClick={alVolver}
          className="flex items-center gap-1.5 text-sm font-medium text-slate-500 hover:text-slate-800"
        >
          <ArrowLeft className="h-4 w-4" />
          Volver al listado
        </button>

        <div className="mt-3 flex flex-wrap items-start justify-between gap-4">

          <div>

            <h1 className="text-2xl font-semibold text-slate-800">
              {lote.codigo_lote}
            </h1>

            <p className="mt-1 text-sm text-slate-500">
              {lote.producto_nombre} · {lote.mandante_nombre} · {lote.fecha} ·{" "}
              {kilos(lote.kg_producidos)}
            </p>

          </div>

          {liberacion && liberacion.liberado && (

            <div className="rounded-2xl border border-slate-200 bg-white px-5 py-3 text-right">

              <p className="flex items-center justify-end gap-1.5 text-sm font-semibold text-slate-800">
                <ShieldCheck className="h-4 w-4 text-green-600" />
                {liberacion.estado_etiqueta}
              </p>

              <p className="mt-0.5 text-xs text-slate-500">
                {liberacion.autorizada_por_nombre || "—"}
              </p>

              {liberacion.concesion && (
                <p className="mt-1 max-w-xs text-xs text-amber-700">
                  {liberacion.motivo_concesion}
                </p>
              )}

            </div>

          )}

        </div>

      </div>

      {/* Estado de calidad y avance */}

      <div className="grid gap-4 sm:grid-cols-2">

        <div className="rounded-2xl border border-slate-200 bg-white p-5">

          <p className="text-sm text-slate-500">Calidad del lote</p>

          <div className="mt-2 flex items-center gap-2">

            <span
              className={`rounded-full px-3 py-1 text-sm font-medium ${
                ESTILO_CALIDAD[calidad?.resultado || "sin_analisis"]
              }`}
            >
              {calidad?.etiqueta || "Sin análisis"}
            </span>

            {calidad && calidad.evaluados > 0 && (
              <span className="text-xs text-slate-400">
                {calidad.evaluados} análisis
              </span>
            )}

          </div>

          {calidad && calidad.desviaciones.length > 0 && (

            <ul className="mt-3 space-y-1 text-sm text-red-700">
              {calidad.desviaciones.map((d, i) => (
                <li key={i}>
                  · {d.parametro}: {d.valor} (rango {d.min ?? "—"} a {d.max ?? "—"})
                </li>
              ))}
            </ul>

          )}

        </div>

        <div className="rounded-2xl border border-slate-200 bg-white p-5">

          <div className="flex items-baseline justify-between">
            <p className="text-sm text-slate-500">Avance documental</p>
            <p className="text-sm text-slate-500">
              {avance?.completados ?? 0} de {avance?.total ?? 0}
            </p>
          </div>

          <div className="mt-3 h-2.5 w-full overflow-hidden rounded-full bg-slate-100">
            <div
              className={`h-full rounded-full ${
                avance?.completo ? "bg-green-600" : "bg-slate-400"
              }`}
              style={{ width: `${avance?.pct ?? 0}%` }}
            />
          </div>

          <p className="mt-2 text-sm text-slate-600">{avance?.pct ?? 0}%</p>

        </div>

      </div>

      {/* Checklist */}

      <div className="rounded-2xl border border-slate-200 bg-white">

        <div className="border-b border-slate-200 px-5 py-4">
          <h2 className="font-medium text-slate-800">Checklist de liberación</h2>
          <p className="mt-0.5 text-xs text-slate-500">
            Los exige la familia «{lote.familia}» del producto
          </p>
        </div>

        {(!avance || avance.detalle.length === 0) && (
          <p className="px-5 py-6 text-sm text-slate-500">
            No hay documentos configurados para esta familia de producto.
          </p>
        )}

        <ul className="divide-y divide-slate-100">

          {avance?.detalle.map((estado) => {

            const suyas = discrepancias[String(estado.documento.id)] || [];

            return (

              <li key={estado.documento.id}>

                <button
                  type="button"
                  onClick={() => setAbierto(estado)}
                  className="flex w-full items-center gap-3 px-5 py-4 text-left hover:bg-slate-50"
                >

                  <IconoDocumento estado={estado} />

                  <div className="min-w-0 flex-1">

                    <p className="truncate text-sm font-medium text-slate-800">
                      {estado.documento.nombre}
                    </p>

                    <p className="mt-0.5 text-xs text-slate-500">

                      {estado.observado
                        ? "Observado: bloquea la liberación"
                        : estado.cumplido_por_dato
                        ? "Lo cumple el registro del sistema, no una casilla"
                        : estado.completo
                          ? `Completado por ${estado.registro?.completado_por_nombre || "—"}`
                          : estado.iniciado
                            ? `En borrador · faltan ${estado.faltantes.length || 0} campo(s)`
                            : estado.documento.campos > 0
                              ? `${estado.documento.campos} campos por llenar`
                              : "Sin completar · solo atestación"}

                    </p>

                  </div>

                  {suyas.length > 0 && (
                    <span
                      className="flex items-center gap-1 rounded-full bg-amber-50 px-2 py-0.5 text-[11px] font-medium text-amber-700"
                      title="No cuadra con el análisis o la especificación"
                    >
                      <AlertTriangle className="h-3 w-3" />
                      {suyas.length}
                    </span>
                  )}

                </button>

              </li>
            );
          })}

        </ul>

      </div>

      {/* Decisión */}

      <div className="rounded-2xl border border-slate-200 bg-white p-5">

        <h2 className="font-medium text-slate-800">Liberación</h2>

        {decision.bloqueos.length > 0 && (

          <ul className="mt-3 space-y-1.5">
            {decision.bloqueos.map((bloqueo, i) => (
              <li key={i} className="flex items-start gap-2 text-sm text-slate-600">
                <Lock className="mt-0.5 h-3.5 w-3.5 shrink-0 text-slate-400" />
                {bloqueo}
              </li>
            ))}
          </ul>

        )}

        {decision.permitido && (
          <p className="mt-3 text-sm text-green-700">
            El lote cumple todo lo exigido: checklist completo y calidad conforme.
          </p>
        )}

        {error && (
          <p className="mt-3 rounded-xl bg-red-50 px-4 py-3 text-sm text-red-700">
            {error}
          </p>
        )}

        {/* Motivo de la concesión */}

        {pidiendoMotivo && (

          <div className="mt-4 rounded-xl bg-amber-50 p-4">

            <label className="block text-sm font-medium text-amber-900">
              Motivo de la concesión
            </label>

            <p className="mt-1 text-xs text-amber-800">
              Queda como marca permanente del lote. Quien lea el expediente dentro
              de dos años tiene que entender por qué salió este producto.
            </p>

            <textarea
              rows={3}
              value={motivo}
              onChange={(e) => setMotivo(e.target.value)}
              className="mt-2 w-full rounded-xl border border-amber-200 bg-white px-3 py-2 text-sm text-slate-800 focus:border-amber-500 focus:outline-none"
            />

            <div className="mt-3 flex items-center gap-2">

              <button
                type="button"
                disabled={firmando || motivo.trim().length < 10}
                onClick={() => void firmar(true)}
                title={
                  motivo.trim().length < 10
                    ? "El motivo debe tener al menos 10 caracteres"
                    : ""
                }
                className="rounded-xl bg-amber-600 px-4 py-2 text-sm font-medium text-white hover:bg-amber-700 disabled:opacity-50"
              >
                Confirmar concesión
              </button>

              <button
                type="button"
                onClick={() => setPidiendoMotivo(false)}
                className="rounded-xl px-4 py-2 text-sm font-medium text-amber-800 hover:bg-amber-100"
              >
                Cancelar
              </button>

            </div>

          </div>

        )}

        {puedeFirmar && !pidiendoMotivo && (

          <div className="mt-4 flex flex-wrap gap-2">

            <button
              type="button"
              disabled={!decision.permitido || firmando}
              onClick={() => void firmar(false)}
              className="flex items-center gap-1.5 rounded-xl bg-green-600 px-5 py-2.5 text-sm font-medium text-white hover:bg-green-700 disabled:opacity-40"
            >
              <ShieldCheck className="h-4 w-4" />
              Liberar
            </button>

            {decision.via_concesion && (

              <button
                type="button"
                disabled={firmando}
                onClick={() => setPidiendoMotivo(true)}
                className="flex items-center gap-1.5 rounded-xl border border-amber-300 bg-amber-50 px-5 py-2.5 text-sm font-medium text-amber-800 hover:bg-amber-100"
              >
                <AlertTriangle className="h-4 w-4" />
                Liberar bajo concesión
              </button>

            )}

          </div>

        )}

        {!puedeFirmar && (
          <p className="mt-4 text-sm text-slate-500">
            Tu rol no autoriza liberaciones. Puedes consultar el expediente.
          </p>
        )}

      </div>

      {abierto && (
        <FormularioDinamico
          loteId={loteId}
          estado={abierto}
          prellenado={prellenado[String(abierto.documento.id)] || {}}
          discrepancias={discrepancias[String(abierto.documento.id)] || []}
          puedeEditar={puedeFirmar}
          alCerrar={() => setAbierto(null)}
          alGuardar={() => {
            setAbierto(null);
            void cargar();
          }}
        />
      )}

    </div>
  );
}


export default Expediente;
