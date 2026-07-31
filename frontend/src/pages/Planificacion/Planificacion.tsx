import { useCallback, useEffect, useState } from "react";
import { AlertTriangle, CheckCircle2, Lock, Plus } from "lucide-react";
import axios from "axios";

import {
  borrarBloque,
  cerrarSemana,
  crearSemana,
  DIAS,
  obtenerCodigos,
  obtenerPrograma,
  obtenerSemanas,
  publicarSemana,
  reabrirSemana,
  type CodigoProduccion,
  type Programa,
  type Semana,
} from "../../services/planificacion.service";

import { obtenerEquipos, type Equipo } from "../../services/maestros.service";
import { puedeEscribir } from "../../services/sesion";

import BalanceLeche from "./BalanceLeche";
import Contraste from "./Contraste";
import FormularioBloque from "./FormularioBloque";
import Gantt from "./Gantt";


/*
  Planificación semanal de producción.

  Dos bloques acoplados, como el Excel que reemplaza: el programa horario
  genera el consumo del balance. Por eso, después de tocar un bloque se
  vuelve a pedir el programa entero en vez de recalcular aquí — la regla vive
  en el servidor y duplicarla en el navegador es garantizar que algún día
  digan cosas distintas.
*/

const ESTILO_ESTADO: Record<string, string> = {
  borrador: "bg-slate-100 text-slate-600",
  publicada: "bg-green-50 text-green-700",
  cerrada: "bg-blue-50 text-blue-700",
};


function lunesDeHoy(): string {
  const hoy = new Date();
  const dia = (hoy.getDay() + 6) % 7; // 0 = lunes
  hoy.setDate(hoy.getDate() - dia);

  return hoy.toISOString().slice(0, 10);
}


function Planificacion() {

  const [semanas, setSemanas] = useState<Semana[]>([]);
  const [semanaId, setSemanaId] = useState<number | null>(null);
  const [programa, setPrograma] = useState<Programa | null>(null);
  const [codigos, setCodigos] = useState<CodigoProduccion[]>([]);

  const [dia, setDia] = useState(0);
  const [vista, setVista] = useState<"programa" | "contraste">("programa");

  const [cargando, setCargando] = useState(true);
  const [error, setError] = useState("");
  const [firmando, setFirmando] = useState(false);

  const [nuevoBloque, setNuevoBloque] = useState<{
    equipo: number;
    hora: number;
  } | null>(null);

  /* Los equipos vienen del maestro: la Gantt dibuja una fila por cada uno. */
  const [equipos, setEquipos] = useState<Equipo[]>([]);

  const puedeEditar = puedeEscribir("produccion");

  const cargarSemanas = useCallback(async () => {
    try {
      const lista = await obtenerSemanas();
      setSemanas(lista);

      setSemanaId((actual) => actual ?? lista[0]?.id ?? null);
    } catch {
      setError("No se pudieron cargar las semanas.");
    }
  }, []);

  const cargarPrograma = useCallback(async () => {

    if (semanaId === null) {
      setPrograma(null);
      setCargando(false);
      return;
    }

    setCargando(true);
    setError("");

    try {
      setPrograma(await obtenerPrograma(semanaId));
    } catch {
      setError("No se pudo cargar el programa.");
    } finally {
      setCargando(false);
    }

  }, [semanaId]);

  useEffect(() => {
    const t = setTimeout(() => {
      void cargarSemanas();
      void obtenerCodigos().then(setCodigos).catch(() => undefined);
      // Sin equipos la Gantt no tiene filas que dibujar, pero la pantalla
      // sigue en pie y lo dice.
      void obtenerEquipos().then(setEquipos).catch(() => setEquipos([]));
    }, 0);

    return () => clearTimeout(t);
  }, [cargarSemanas]);

  useEffect(() => {
    const t = setTimeout(cargarPrograma, 0);

    return () => clearTimeout(t);
  }, [cargarPrograma]);

  const nuevaSemana = async () => {
    const inicio = lunesDeHoy();
    const anio = Number(inicio.slice(0, 4));
    const numero = semanas.filter((s) => s.anio === anio).length + 1;

    try {
      const creada = await crearSemana({
        codigo: `W${numero}`,
        anio,
        fecha_inicio: inicio,
      });

      await cargarSemanas();
      setSemanaId(creada.id);
    } catch (e) {
      setError(
        axios.isAxiosError(e) && e.response?.status === 400
          ? "Ya existe una semana con ese código este año."
          : "No se pudo crear la semana.",
      );
    }
  };

  const accion = async (fn: (id: number) => Promise<Semana>) => {
    if (semanaId === null) return;

    setError("");
    setFirmando(true);

    try {
      await fn(semanaId);
      await Promise.all([cargarSemanas(), cargarPrograma()]);
    } catch (e) {
      // El 409 trae los motivos: días sin balance, saldos negativos. Es el
      // rechazo que vale.
      if (axios.isAxiosError(e) && e.response?.status === 409) {
        const datos = e.response.data as { bloqueos?: string[]; detail?: string };
        setError(datos.bloqueos?.join(" ") || datos.detail || "No se pudo.");
      } else {
        setError("No se pudo completar la acción.");
      }
    } finally {
      setFirmando(false);
    }
  };

  const semana = programa?.semana;
  const editable = puedeEditar && semana?.estado === "borrador";

  return (
    <div className="space-y-6">

      {/* Cabecera */}

      <div className="flex flex-wrap items-end justify-between gap-4">

        <div>

          <h1 className="text-2xl font-semibold text-slate-800">
            Planificación semanal
          </h1>

          <p className="mt-1 text-sm text-slate-500">
            El programa horario genera el consumo del balance de leche.
          </p>

        </div>

        <div className="flex items-center gap-2">

          <select
            value={semanaId ?? ""}
            onChange={(e) => setSemanaId(Number(e.target.value))}
            className="rounded-xl border border-slate-200 px-3 py-2 text-sm text-slate-700 focus:border-green-500 focus:outline-none"
          >
            {semanas.length === 0 && <option value="">Sin semanas</option>}

            {semanas.map((s) => (
              <option key={s.id} value={s.id}>
                {s.codigo} · {s.anio} — {s.estado_etiqueta}
              </option>
            ))}
          </select>

          {puedeEditar && (
            <button
              type="button"
              onClick={() => void nuevaSemana()}
              className="flex items-center gap-1.5 rounded-xl bg-green-700 px-4 py-2 text-sm font-medium text-white hover:bg-green-800"
            >
              <Plus className="h-4 w-4" />
              Nueva semana
            </button>
          )}

        </div>

      </div>

      {error && (
        <p className="rounded-xl bg-red-50 px-4 py-3 text-sm text-red-700">{error}</p>
      )}

      {cargando && <p className="text-sm text-slate-500">Cargando…</p>}

      {!cargando && !semana && !error && (
        <p className="rounded-2xl border border-slate-200 bg-white px-5 py-8 text-center text-sm text-slate-500">
          Todavía no hay ninguna semana planificada.
        </p>
      )}

      {semana && programa && (
        <>

          {/* Estado y acciones */}

          <div className="flex flex-wrap items-center gap-3 rounded-2xl border border-slate-200 bg-white p-5">

            <span
              className={`rounded-full px-3 py-1 text-sm font-medium ${
                ESTILO_ESTADO[semana.estado]
              }`}
            >
              {semana.estado_etiqueta}
            </span>

            {semana.publicada_por_nombre && (
              <span className="text-sm text-slate-500">
                por {semana.publicada_por_nombre}
              </span>
            )}

            <div className="ml-auto flex flex-wrap gap-2">

              {puedeEditar && semana.estado === "borrador" && (
                <button
                  type="button"
                  disabled={firmando || !programa.publicable}
                  onClick={() => void accion(publicarSemana)}
                  title={
                    programa.publicable
                      ? "Comprometer el programa con planta"
                      : programa.bloqueos.join(" ")
                  }
                  className="flex items-center gap-1.5 rounded-xl bg-green-600 px-4 py-2 text-sm font-medium text-white hover:bg-green-700 disabled:opacity-40"
                >
                  <CheckCircle2 className="h-4 w-4" />
                  Publicar
                </button>
              )}

              {puedeEditar && semana.estado === "publicada" && (
                <>
                  <button
                    type="button"
                    disabled={firmando}
                    onClick={() => void accion(reabrirSemana)}
                    className="rounded-xl border border-slate-200 px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50"
                  >
                    Volver a borrador
                  </button>

                  <button
                    type="button"
                    disabled={firmando}
                    onClick={() => void accion(cerrarSemana)}
                    className="rounded-xl border border-blue-200 bg-blue-50 px-4 py-2 text-sm font-medium text-blue-700 hover:bg-blue-100"
                  >
                    Cerrar semana
                  </button>
                </>
              )}

            </div>

          </div>

          {/* Lo que impide publicar */}

          {semana.estado === "borrador" && programa.bloqueos.length > 0 && (

            <div className="rounded-2xl border border-slate-200 bg-white p-5">

              <p className="text-sm font-medium text-slate-700">
                Falta para poder publicar
              </p>

              <ul className="mt-2 space-y-1.5">
                {programa.bloqueos.map((bloqueo, i) => (
                  <li key={i} className="flex items-start gap-2 text-sm text-slate-600">
                    <Lock className="mt-0.5 h-3.5 w-3.5 shrink-0 text-slate-400" />
                    {bloqueo}
                  </li>
                ))}
              </ul>

            </div>

          )}

          {/* Pestañas */}

          <div className="flex gap-1 border-b border-slate-200">

            {(["programa", "contraste"] as const).map((v) => (
              <button
                key={v}
                type="button"
                onClick={() => setVista(v)}
                className={`px-4 py-2 text-sm font-medium ${
                  vista === v
                    ? "border-b-2 border-green-600 text-green-700"
                    : "text-slate-500 hover:text-slate-800"
                }`}
              >
                {v === "programa" ? "Programa y balance" : "Plan contra real"}
              </button>
            ))}

          </div>

          {vista === "programa" ? (
            <>

              {/* Carta Gantt */}

              <div className="rounded-2xl border border-slate-200 bg-white p-5">

                <div className="mb-4 flex flex-wrap items-center justify-between gap-3">

                  <h2 className="font-medium text-slate-800">Programa horario</h2>

                  <div className="flex flex-wrap gap-1">
                    {DIAS.map((nombre, i) => (
                      <button
                        key={nombre}
                        type="button"
                        onClick={() => setDia(i)}
                        className={`rounded-lg px-3 py-1.5 text-sm ${
                          dia === i
                            ? "bg-green-50 font-medium text-green-700"
                            : "text-slate-500 hover:bg-slate-50"
                        }`}
                      >
                        {nombre.slice(0, 3)}
                      </button>
                    ))}
                  </div>

                </div>

                <Gantt
                  bloques={programa.bloques}
                  equipos={equipos}
                  dia={dia}
                  puedeEditar={editable}
                  alCrear={(equipo, hora) => setNuevoBloque({ equipo, hora })}
                  alBorrar={async (bloque) => {
                    await borrarBloque(bloque.id);
                    await cargarPrograma();
                  }}
                />

                {!editable && puedeEditar && (
                  <p className="mt-3 flex items-center gap-1.5 text-xs text-slate-500">
                    <AlertTriangle className="h-3.5 w-3.5" />
                    Una semana {semana.estado_etiqueta.toLowerCase()} no se edita.
                    Vuelve a borrador para reprogramar.
                  </p>
                )}

              </div>

              {/* Balance */}

              <div className="rounded-2xl border border-slate-200 bg-white p-5">

                <h2 className="mb-1 font-medium text-slate-800">Balance de leche</h2>

                <p className="mb-4 text-xs text-slate-500">
                  El consumo sale del programa: horas de bloque en evaporador por
                  el rendimiento del código. No se teclea.
                </p>

                <BalanceLeche
                  balance={programa.balance}
                  fechas={programa.fechas}
                />

              </div>

            </>
          ) : (
            <Contraste semanaId={semana.id} />
          )}

        </>
      )}

      {nuevoBloque && semana && (
        <FormularioBloque
          semanaId={semana.id}
          equipo={nuevoBloque.equipo}
          equipos={equipos}
          horaInicio={nuevoBloque.hora}
          dia={dia}
          codigos={codigos}
          alCerrar={() => setNuevoBloque(null)}
          alGuardar={() => {
            setNuevoBloque(null);
            void cargarPrograma();
          }}
        />
      )}

    </div>
  );
}


export default Planificacion;
