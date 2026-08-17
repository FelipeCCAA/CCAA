import { useCallback, useEffect, useState } from "react";
import { AlertTriangle, ArrowRight, Pencil, X } from "lucide-react";
import axios from "axios";

import {
  cambiarEstadoLote,
  editarLote,
  ETIQUETA_ESTADO,
  EXPLICACION_ESTADO,
  kilos,
  obtenerLote,
  TRANSICIONES,
  type EstadoLote,
  type LoteDetalle,
  type Parametro,
  type LoteEditado,
} from "../../services/produccion.service";

import EtiquetaCalidad from "../../components/EtiquetaCalidad/EtiquetaCalidad";
import FormularioAnalisis from "./FormularioAnalisis";
import PanelInocuidad from "./PanelInocuidad";
import PanelAsignacion from "./PanelAsignacion";


/*
  Ficha de un lote, con el cierre de producción.

  Es lo que faltaba para que el flujo cierre sin pasar por el admin de Django:
  un lote se queda `en_proceso` hasta que alguien declara que la producción
  terminó, y hasta entonces no llega a Calidad ni puede liberarse.

  Los pasos que se ofrecen salen de `TRANSICIONES`, que refleja lo que el
  backend acepta. Cerrado y anulado son finales y se avisa antes, porque no
  hay vuelta atrás: el histórico se audita.
*/

interface Props {
  loteId: number;
  puedeEditar: boolean;
  /* Vienen de la pantalla de Producción, que ya los pidió una vez. */
  parametros: Parametro[];
  alCerrar: () => void;
  alCambiar: () => void;
}



const ESTILO_ESTADO: Record<EstadoLote, string> = {
  en_proceso: "bg-blue-50 text-blue-700",
  producido: "bg-green-50 text-green-700",
  cerrado: "bg-slate-100 text-slate-600",
  anulado: "bg-red-50 text-red-700",
};


function Dato({ etiqueta, children }: { etiqueta: string; children: React.ReactNode }) {
  return (
    <div>
      <dt className="text-xs text-slate-400">{etiqueta}</dt>
      <dd className="mt-0.5 text-sm text-slate-800">{children}</dd>
    </div>
  );
}


const claseCampo =
  "w-full rounded-xl border border-slate-200 px-3 py-2 text-sm text-slate-800 " +
  "focus:border-green-500 focus:outline-none";


function Campo({
  etiqueta,
  children,
}: {
  etiqueta: string;
  children: React.ReactNode;
}) {
  return (
    <div>
      <label className="mb-1 block text-xs font-medium text-slate-600">
        {etiqueta}
      </label>
      {children}
    </div>
  );
}


/* Lo que el formulario edita. Se maneja como texto porque un input vacío es
   "" y no null, y convertirlo al enviar es más simple que al escribir. */
type Borrador = {
  codigo_lote: string;
  op: string;
  fecha: string;
  linea: string;
  turno: string;
  kg_producidos: string;
  bultos: string;
  hora_inicio: string;
  hora_termino: string;
  vencimiento: string;
  observacion: string;
};


function borradorDe(lote: LoteDetalle): Borrador {
  return {
    codigo_lote: lote.codigo_lote,
    op: lote.op ?? "",
    fecha: lote.fecha,
    linea: lote.linea ?? "",
    turno: lote.turno ?? "",
    /* Vacío cuando el lote sigue en proceso: los kilos se declaran al
       cerrarlo, y un "0" en el campo se guardaría como producción real. */
    kg_producidos: lote.kg_producidos ?? "",
    bultos: lote.bultos === null ? "" : String(lote.bultos),
    hora_inicio: lote.hora_inicio ?? "",
    hora_termino: lote.hora_termino ?? "",
    vencimiento: lote.vencimiento ?? "",
    observacion: lote.observacion ?? "",
  };
}


/** Solo lo que cambió: mandar el resto invitaría a pisar lo que no se tocó. */
function cambios(original: Borrador, actual: Borrador): LoteEditado {
  const salida: Record<string, unknown> = {};

  for (const clave of Object.keys(actual) as (keyof Borrador)[]) {
    if (actual[clave] === original[clave]) {
      continue;
    }

    const valor = actual[clave];

    if (clave === "bultos") {
      salida[clave] = valor === "" ? null : Number(valor);
    } else if (["hora_inicio", "hora_termino", "vencimiento"].includes(clave)) {
      salida[clave] = valor === "" ? null : valor;
    } else {
      salida[clave] = valor;
    }
  }

  return salida as LoteEditado;
}


function DetalleLote({
  loteId,
  puedeEditar,
  parametros,
  alCerrar,
  alCambiar,
}: Props) {

  const [lote, setLote] = useState<LoteDetalle | null>(null);
  const [cargando, setCargando] = useState(true);
  const [error, setError] = useState("");
  const [guardando, setGuardando] = useState(false);
  const [confirmando, setConfirmando] = useState<EstadoLote | null>(null);
  const [motivoAnulacion, setMotivoAnulacion] = useState("");

  /* Cerrar la producción es declarar cuánto se produjo: los kilos se piden
     aquí, que es cuando se saben. El backend los exige igual. */
  const [declarando, setDeclarando] = useState(false);
  const [kgCierre, setKgCierre] = useState("");

  const [editando, setEditando] = useState(false);
  const [borrador, setBorrador] = useState<Borrador | null>(null);
  const [original, setOriginal] = useState<Borrador | null>(null);

  const cargar = useCallback(async () => {

    setCargando(true);
    setError("");

    try {
      setLote(await obtenerLote(loteId));
    } catch {
      setError("No se pudo cargar el lote.");
    } finally {
      setCargando(false);
    }

  }, [loteId]);

  // Diferido para no actualizar el estado dentro del propio efecto.
  useEffect(() => {

    const temporizador = setTimeout(cargar, 0);

    return () => clearTimeout(temporizador);

  }, [cargar]);

  const cambiar = async (estado: EstadoLote, kgDeclarados?: string) => {

    setError("");
    setGuardando(true);

    try {

      setLote(await cambiarEstadoLote(
        loteId,
        estado,
        kgDeclarados,
        estado === "anulado" ? motivoAnulacion : undefined,
      ));
      setConfirmando(null);
      setMotivoAnulacion("");
      setDeclarando(false);
      setKgCierre("");
      alCambiar();

    } catch (e) {

      // El backend explica por qué la transición no vale; mostrar su mensaje
      // es más útil que uno genérico escrito aquí.
      if (axios.isAxiosError(e) && e.response?.status === 400) {
        const datos = e.response.data as Record<string, string[] | string>;
        setError(Object.values(datos).flat().join(" "));
      } else if (axios.isAxiosError(e) && e.response?.status === 403) {
        setError("Tu rol no permite cambiar el estado de un lote.");
      } else {
        setError("No se pudo cambiar el estado del lote.");
      }

    } finally {
      setGuardando(false);
    }
  };

  const abrirEdicion = () => {
    if (!lote) return;

    const inicial = borradorDe(lote);
    setOriginal(inicial);
    setBorrador(inicial);
    setEditando(true);
    setError("");
  };

  const guardarEdicion = async () => {
    if (!borrador || !original) return;

    const diferencias = cambios(original, borrador);

    if (Object.keys(diferencias).length === 0) {
      setEditando(false);
      return;
    }

    setError("");
    setGuardando(true);

    try {

      setLote(await editarLote(loteId, diferencias));
      setEditando(false);
      alCambiar();

    } catch (e) {

      // El backend explica por qué no deja: lote cerrado, o liberado. Su
      // mensaje dice además cómo desbloquearlo.
      if (axios.isAxiosError(e) && e.response?.status === 400) {
        const datos = e.response.data as Record<string, string[] | string>;
        setError([...new Set(Object.values(datos).flat())].join(" "));
      } else if (axios.isAxiosError(e) && e.response?.status === 403) {
        setError("Tu rol no permite editar lotes.");
      } else {
        setError("No se pudo guardar el lote.");
      }

    } finally {
      setGuardando(false);
    }
  };

  const escribir = (clave: keyof Borrador) => (valor: string) =>
    setBorrador((previo) => (previo ? { ...previo, [clave]: valor } : previo));

  const siguientes = lote ? TRANSICIONES[lote.estado] : [];
  const esFinal = lote !== null && siguientes.length === 0;

  // Un lote firmado por Calidad no se edita: cambiar lo que se produjo dejaría
  // esa firma respaldando otra cosa. El backend lo rechaza igual; esto evita
  // que alguien llene el formulario para descubrirlo al guardar.
  const liberado = lote?.liberacion?.liberado === true;
  const editable = puedeEditar && !esFinal && !liberado;

  return (
    <div className="fixed inset-0 z-50 flex items-start justify-center overflow-y-auto bg-slate-900/40 p-4">

      <div className="my-8 w-full max-w-2xl rounded-2xl bg-white shadow-xl">

        <div className="flex items-start justify-between gap-4 border-b border-slate-200 px-6 py-5">

          <div>

            <h2 className="text-lg font-semibold text-slate-800">
              {cargando ? "Cargando…" : lote?.codigo_lote}
            </h2>

            {lote && (
              <p className="mt-0.5 text-sm text-slate-500">
                {lote.producto_nombre} · {lote.mandante_nombre} · {lote.fecha}
              </p>
            )}

          </div>

          <button
            type="button"
            onClick={alCerrar}
            className="rounded-lg p-1 text-slate-400 hover:bg-slate-100 hover:text-slate-600"
            aria-label="Cerrar"
          >
            <X className="h-5 w-5" />
          </button>

        </div>

        {lote && (

          <div className="space-y-6 px-6 py-5">

            {/* Estado y calidad */}

            <div className="flex flex-wrap items-center gap-3">

              <span
                className={`rounded-full px-3 py-1 text-sm font-medium ${ESTILO_ESTADO[lote.estado]}`}
              >
                {lote.estado_etiqueta}
              </span>

              <EtiquetaCalidad calidad={lote.calidad} />

              {lote.calidad.evaluados > 0 && (
                <span className="text-xs text-slate-400">
                  {lote.calidad.evaluados} análisis
                </span>
              )}

            </div>

            {/* Datos del lote: lectura o edición */}

            {!editando || !borrador ? (

              <>

                <div className="flex items-start justify-between gap-4">

                  <dl className="grid flex-1 grid-cols-2 gap-4 sm:grid-cols-4">

                    <Dato etiqueta="Código">{lote.codigo_lote}</Dato>

                    <Dato etiqueta="Kilos">
                      {kilos(lote.kg_producidos)}
                    </Dato>

                    <Dato etiqueta="Bultos">{lote.bultos ?? "—"}</Dato>
                    <Dato etiqueta="Fecha">{lote.fecha}</Dato>
                    <Dato etiqueta="Línea">{lote.linea || "—"}</Dato>
                    <Dato etiqueta="Máquina">{lote.equipo_nombre || "—"}</Dato>
                    <Dato etiqueta="Turno">{lote.turno || "—"}</Dato>
                    <Dato etiqueta="OP">{lote.op || "—"}</Dato>
                    <Dato etiqueta="Vale de estandarización">
                      {lote.vale_codigo || "Carga histórica sin vale"}
                    </Dato>
                    <Dato etiqueta="Silo estandarizado">
                      {lote.silo_estandarizado_codigo || "—"}
                    </Dato>
                    <Dato etiqueta="ID del proceso">
                      {lote.ejecucion_codigo || "—"}
                    </Dato>
                    <Dato etiqueta="Inicio">{lote.hora_inicio || "—"}</Dato>
                    <Dato etiqueta="Término">{lote.hora_termino || "—"}</Dato>
                    <Dato etiqueta="Vencimiento">{lote.vencimiento || "—"}</Dato>

                  </dl>

                  {editable && (
                    <button
                      type="button"
                      onClick={abrirEdicion}
                      className="flex shrink-0 items-center gap-1.5 rounded-xl border border-slate-200 px-3 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50"
                    >
                      <Pencil className="h-4 w-4" />
                      Editar
                    </button>
                  )}

                </div>

                {liberado && (

                  <p className="rounded-xl bg-slate-50 px-4 py-3 text-sm text-slate-600">

                    <span className="font-medium text-slate-800">
                      {lote.liberacion?.estado_etiqueta}
                    </span>

                    {lote.liberacion?.autorizada_por_nombre
                      ? ` por ${lote.liberacion.autorizada_por_nombre}. `
                      : ". "}

                    Los datos del lote no se editan mientras la liberación esté
                    firmada: cambiarlos dejaría esa firma respaldando otra cosa.
                    Para corregirlos, Calidad debe retirar antes la liberación.

                  </p>

                )}

                {/* El material no se descontó de bodega. No impide nada —el
                    lote ya está producido— pero mientras no se resuelva, el
                    saldo de bodega está más alto de lo que corresponde. */}
                {lote.consumo_inventario?.pendiente && (

                  <p className="rounded-xl bg-amber-50 px-4 py-3 text-sm text-amber-800">

                    <span className="font-medium">
                      El material de este lote no se descontó de bodega.
                    </span>{" "}
                    Revisa que el producto tenga receta vigente y que el
                    material esté aprobado y con stock. Hasta entonces, el
                    saldo de bodega no refleja lo que esta corrida consumió.

                  </p>

                )}

                {esFinal && puedeEditar && (
                  <p className="text-sm text-slate-500">
                    Un lote {lote.estado_etiqueta.toLowerCase()} ya no se edita:
                    es un registro histórico.
                  </p>
                )}

                {lote.observacion && (
                  <p className="rounded-xl bg-slate-50 px-4 py-3 text-sm text-slate-600">
                    {lote.observacion}
                  </p>
                )}

              </>

            ) : (

              <div className="space-y-4 rounded-xl border border-slate-200 p-4">

                <div className="grid grid-cols-2 gap-4 sm:grid-cols-3">

                  <Campo etiqueta="Código de lote">
                    <input
                      type="text"
                      value={borrador.codigo_lote}
                      onChange={(e) => escribir("codigo_lote")(e.target.value)}
                      className={claseCampo}
                    />
                  </Campo>

                  <Campo etiqueta="OP">
                    <input
                      type="text"
                      value={borrador.op}
                      onChange={(e) => escribir("op")(e.target.value)}
                      className={claseCampo}
                    />
                  </Campo>

                  <Campo etiqueta="Fecha">
                    <input
                      type="date"
                      value={borrador.fecha}
                      onChange={(e) => escribir("fecha")(e.target.value)}
                      className={claseCampo}
                    />
                  </Campo>

                  <Campo etiqueta="Kilos producidos">
                    <input
                      type="number"
                      step="0.01"
                      min="0"
                      value={borrador.kg_producidos}
                      onChange={(e) => escribir("kg_producidos")(e.target.value)}
                      className={claseCampo}
                    />
                  </Campo>

                  <Campo etiqueta="Bultos">
                    <input
                      type="number"
                      min="0"
                      value={borrador.bultos}
                      onChange={(e) => escribir("bultos")(e.target.value)}
                      className={claseCampo}
                    />
                  </Campo>

                  <Campo etiqueta="Línea">
                    <select
                      value={borrador.linea}
                      onChange={(e) => escribir("linea")(e.target.value)}
                      className={claseCampo}
                    >
                      <option value="">Sin línea</option>
                      <option value="E1">E1</option>
                      <option value="E2">E2</option>
                    </select>
                  </Campo>

                  <Campo etiqueta="Turno">
                    <select
                      value={borrador.turno}
                      onChange={(e) => escribir("turno")(e.target.value)}
                      className={claseCampo}
                    >
                      <option value="">Sin turno</option>
                      <option value="A">A</option>
                      <option value="B">B</option>
                      <option value="C">C</option>
                    </select>
                  </Campo>

                  <Campo etiqueta="Hora de inicio">
                    <input
                      type="time"
                      value={borrador.hora_inicio}
                      onChange={(e) => escribir("hora_inicio")(e.target.value)}
                      className={claseCampo}
                    />
                  </Campo>

                  <Campo etiqueta="Hora de término">
                    <input
                      type="time"
                      value={borrador.hora_termino}
                      onChange={(e) => escribir("hora_termino")(e.target.value)}
                      className={claseCampo}
                    />
                  </Campo>

                  <Campo etiqueta="Vencimiento">
                    <input
                      type="date"
                      value={borrador.vencimiento}
                      onChange={(e) => escribir("vencimiento")(e.target.value)}
                      className={claseCampo}
                    />
                  </Campo>

                </div>

                <Campo etiqueta="Observación">
                  <textarea
                    rows={2}
                    value={borrador.observacion}
                    onChange={(e) => escribir("observacion")(e.target.value)}
                    className={claseCampo}
                  />
                </Campo>

                {/* El producto no se cambia aquí: cambiarlo convierte el lote
                    en otro producto y su calidad se reevalúa contra otra
                    especificación. Si se tecleó mal, es más honesto anular el
                    lote y registrarlo de nuevo. */}
                <p className="text-xs text-slate-500">
                  El producto no se edita: un lote de otro producto es otro lote.
                  Si se registró mal, anúlalo y créalo de nuevo.
                </p>

                <div className="flex gap-2">

                  <button
                    type="button"
                    disabled={guardando}
                    onClick={() => void guardarEdicion()}
                    className="rounded-xl bg-green-600 px-4 py-2 text-sm font-medium text-white hover:bg-green-700 disabled:opacity-50"
                  >
                    {guardando ? "Guardando…" : "Guardar cambios"}
                  </button>

                  <button
                    type="button"
                    onClick={() => {
                      setEditando(false);
                      setError("");
                    }}
                    className="rounded-xl px-4 py-2 text-sm font-medium text-slate-600 hover:bg-slate-100"
                  >
                    Cancelar
                  </button>

                </div>

              </div>

            )}

            {/* Desviaciones, si las hay */}

            {lote.calidad.desviaciones.length > 0 && (

              <div className="rounded-xl bg-red-50 px-4 py-3">

                <p className="text-sm font-medium text-red-800">
                  Parámetros fuera de especificación
                </p>

                <ul className="mt-1.5 space-y-1 text-sm text-red-700">
                  {lote.calidad.desviaciones.map((d, i) => (
                    <li key={i}>
                      · {d.parametro}: {d.valor} (rango {d.min ?? "—"} a {d.max ?? "—"})
                    </li>
                  ))}
                </ul>

              </div>

            )}

            {/* Leche asignada: de qué silos salió este lote */}

            <PanelAsignacion
              loteId={lote.id}
              puedeEditar={puedeEditar}
              alCambiar={alCambiar}
            />

            {/* Inocuidad: el PCC 1 y los PPRO deciden si se puede liberar */}

            <PanelInocuidad
              loteId={lote.id}
              puedeEditar={puedeEditar}
              alCambiar={alCambiar}
            />

            {/* Análisis */}

            <div className="border-t border-slate-200 pt-5">

              <h3 className="mb-2 text-sm font-medium text-slate-700">
                Análisis del lote
              </h3>

              {(lote.analisis ?? []).length === 0 ? (

                <p className="text-sm text-slate-500">
                  Todavía no hay análisis. Sin ellos el lote no puede liberarse.
                </p>

              ) : (

                <ul className="divide-y divide-slate-100 rounded-xl border border-slate-200">
                  {(lote.analisis ?? []).map((a) => (
                    <li key={a.id} className="px-4 py-2.5 text-sm">
                      <span className="text-slate-500">{a.fecha}</span>
                      {a.muestra && (
                        <span className="text-slate-400"> · {a.muestra}</span>
                      )}
                      <span className="ml-2 text-slate-700">
                        {Object.entries(a.valores)
                          .map(([k, v]) => `${k} ${v}`)
                          .join("  ·  ")}
                      </span>
                    </li>
                  ))}
                </ul>

              )}

              {/* Los parámetros se miden sobre el producto terminado: hasta
                  que la corrida no cierra no hay nada que analizar. */}

              {lote.estado === "en_proceso" ? (

                <p className="mt-3 text-xs text-slate-400">
                  Los análisis se cargan al cerrar la producción: se miden
                  sobre el producto terminado.
                </p>

              ) : puedeEditar && !esFinal ? (

                <FormularioAnalisis
                  loteId={lote.id}
                  fechaLote={lote.fecha}
                  parametros={parametros}
                  alGuardar={() => {
                    void cargar();
                    alCambiar();
                  }}
                />

              ) : null}

            </div>

            {error && (
              <p className="rounded-xl bg-red-50 px-4 py-3 text-sm text-red-700">
                {error}
              </p>
            )}

            {/* Cambio de estado */}

            <div className="border-t border-slate-200 pt-5">

              <h3 className="text-sm font-medium text-slate-700">
                Estado de la producción
              </h3>

              {esFinal && (
                <p className="mt-2 text-sm text-slate-500">
                  {lote.estado_etiqueta} es un estado final: el lote ya no cambia.
                </p>
              )}

              {!puedeEditar && !esFinal && (
                <p className="mt-2 text-sm text-slate-500">
                  Tu rol no permite cambiar el estado de un lote.
                </p>
              )}

              {/* Cierre de producción: declarar los kilos */}

              {declarando && (

                <div className="mt-3 rounded-xl bg-slate-50 p-4">

                  <p className="text-sm font-medium text-slate-800">

                    ¿Cuántos kilos produjo el lote?

                  </p>

                  <p className="mt-1 text-sm text-slate-600">

                    Cierra la producción. Desde aquí el lote llega a Calidad y
                    puede liberarse.

                  </p>

                  <div className="mt-3 flex flex-wrap items-center gap-2">

                    <input
                      type="number"
                      step="0.01"
                      min="0"
                      autoFocus
                      value={kgCierre}
                      onChange={(e) => setKgCierre(e.target.value)}
                      placeholder="Kilos"
                      className="w-40 rounded-xl border border-slate-300 px-3 py-2 text-sm tabular-nums text-slate-800 focus:border-green-600 focus:outline-none"
                    />

                    <button
                      type="button"
                      disabled={guardando || !kgCierre}
                      onClick={() => void cambiar("producido", kgCierre)}
                      className="rounded-xl bg-green-600 px-4 py-2 text-sm font-medium text-white hover:bg-green-700 disabled:opacity-50"
                    >
                      {guardando ? "Cerrando…" : "Cerrar producción"}
                    </button>

                    <button
                      type="button"
                      onClick={() => {
                        setDeclarando(false);
                        setKgCierre("");
                      }}
                      className="rounded-xl px-4 py-2 text-sm font-medium text-slate-600 hover:bg-slate-200"
                    >
                      Cancelar
                    </button>

                  </div>

                </div>

              )}

              {puedeEditar && !esFinal && !confirmando && !declarando && (

                <div className="mt-3 flex flex-wrap gap-2">

                  {siguientes.map((estado) => (

                    <button
                      key={estado}
                      type="button"
                      disabled={guardando}
                      onClick={() => {
                        // Cerrar la producción pide los kilos; los pasos sin
                        // vuelta atrás piden confirmación; el resto va directo.
                        if (estado === "producido" && lote.kg_producidos == null) {
                          setDeclarando(true);
                        } else if (TRANSICIONES[estado].length === 0) {
                          setConfirmando(estado);
                        } else {
                          void cambiar(estado);
                        }
                      }}
                      title={EXPLICACION_ESTADO[estado]}
                      className={`flex items-center gap-1.5 rounded-xl px-4 py-2.5 text-sm font-medium disabled:opacity-50 ${
                        estado === "anulado"
                          ? "border border-red-200 bg-red-50 text-red-700 hover:bg-red-100"
                          : "bg-green-600 text-white hover:bg-green-700"
                      }`}
                    >

                      <ArrowRight className="h-4 w-4" />

                      Marcar como {ETIQUETA_ESTADO[estado].toLowerCase()}

                    </button>

                  ))}

                </div>

              )}

              {/* Confirmación para los pasos sin vuelta atrás */}

              {confirmando && (

                <div className="mt-3 rounded-xl bg-amber-50 p-4">

                  <p className="flex items-start gap-2 text-sm font-medium text-amber-900">

                    <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />

                    ¿Marcar el lote como {ETIQUETA_ESTADO[confirmando].toLowerCase()}?

                  </p>

                  <p className="mt-1.5 text-sm text-amber-800">
                    {EXPLICACION_ESTADO[confirmando]}
                  </p>

                  {confirmando === "anulado" && (
                    <label className="mt-3 block text-sm font-medium text-amber-900">
                      Motivo obligatorio
                      <textarea
                        value={motivoAnulacion}
                        onChange={(e) => setMotivoAnulacion(e.target.value)}
                        rows={3}
                        placeholder="Explica por qué se anula este lote"
                        className="mt-1.5 w-full rounded-xl border border-amber-300 bg-white px-3 py-2 text-sm text-slate-800 outline-none focus:border-amber-600"
                      />
                    </label>
                  )}

                  <div className="mt-3 flex gap-2">

                    <button
                      type="button"
                      disabled={guardando || (confirmando === "anulado" && !motivoAnulacion.trim())}
                      onClick={() => void cambiar(confirmando)}
                      className="rounded-xl bg-amber-600 px-4 py-2 text-sm font-medium text-white hover:bg-amber-700 disabled:opacity-50"
                    >
                      Sí, {ETIQUETA_ESTADO[confirmando].toLowerCase()}
                    </button>

                    <button
                      type="button"
                      onClick={() => {
                        setConfirmando(null);
                        setMotivoAnulacion("");
                      }}
                      className="rounded-xl px-4 py-2 text-sm font-medium text-amber-800 hover:bg-amber-100"
                    >
                      Cancelar
                    </button>

                  </div>

                </div>

              )}

              {puedeEditar && lote.estado === "en_proceso" && (
                <p className="mt-3 text-xs text-slate-500">
                  Mientras el lote esté en proceso no aparece en Liberación de
                  producto: Calidad solo ve lo que ya terminó de producirse.
                </p>
              )}

            </div>

          </div>

        )}

      </div>

    </div>
  );
}


export default DetalleLote;
