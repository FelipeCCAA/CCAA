import { useCallback, useEffect, useState } from "react";
import { AlertTriangle, Plus, ShieldCheck, Trash2 } from "lucide-react";
import axios from "axios";

import {
  borrarLecturaControl,
  crearControl,
  crearLecturaControl,
  crearLecturaPpro,
  crearMonitoreo,
  editarMonitoreo,
  obtenerCatalogosInocuidad,
  obtenerControles,
  obtenerMonitoreos,
  type CatalogosInocuidad,
  type ControlProceso,
  type MonitoreoPpro,
} from "../../services/inocuidad.service";


/*
  Inocuidad del lote: el PCC 1 de uperización y los monitoreos PPRO.

  Va en la ficha del lote y no en una pantalla aparte porque es donde está el
  contexto: quien registra la lectura está mirando ese lote, y quien ve por
  qué no puede liberarlo necesita llegar al dato en un clic.

  El veredicto del PCC **no se escribe**: lo recalcula el backend desde las
  lecturas y el límite del propio control. Por eso corregir una lectura mal
  tecleada desbloquea el lote sin tocar nada más — y por eso la pantalla
  muestra el motivo con su valor y su límite, en vez de un «no cumple» que
  obligaría a buscar el problema a mano.
*/

interface Props {
  loteId: number;
  puedeEditar: boolean;
  /* Cambiar una lectura puede desbloquear la liberación: la ficha se entera. */
  alCambiar?: () => void;
}


function mensajeDe(e: unknown, porDefecto: string): string {
  if (axios.isAxiosError(e) && e.response) {
    const cuerpo = e.response.data as Record<string, string[] | string>;

    return (
      Object.entries(cuerpo)
        .map(([campo, msg]) =>
          campo === "non_field_errors" || campo === "detail"
            ? String(msg)
            : `${campo}: ${msg}`,
        )
        .join(" · ") || porDefecto
    );
  }

  return porDefecto;
}


function PanelInocuidad({ loteId, puedeEditar, alCambiar }: Props) {

  const [controles, setControles] = useState<ControlProceso[]>([]);
  const [monitoreos, setMonitoreos] = useState<MonitoreoPpro[]>([]);
  const [catalogos, setCatalogos] = useState<CatalogosInocuidad | null>(null);

  const [cargando, setCargando] = useState(true);
  const [error, setError] = useState("");
  const [guardando, setGuardando] = useState(false);

  /* Alta de un control y de sus lecturas. */
  const [nuevoControl, setNuevoControl] = useState(false);
  const [control, setControl] = useState({
    equipo: "",
    fecha: "",
    pcc1_temp_min: "",
    pcc1_caudal_max: "",
  });
  const [lectura, setLectura] = useState<Record<number, { hora: string; t: string; c: string }>>({});

  const [nuevoMonitoreo, setNuevoMonitoreo] = useState(false);
  const [monitoreo, setMonitoreo] = useState({ tipo: "", equipo: "", fecha: "" });
  const [lecturaPpro, setLecturaPpro] = useState<Record<number, string>>({});
  const [accion, setAccion] = useState<Record<number, string>>({});

  const cargar = useCallback(async () => {
    try {
      const [c, m] = await Promise.all([
        obtenerControles(loteId),
        obtenerMonitoreos(loteId),
      ]);
      setControles(c);
      setMonitoreos(m);
    } catch {
      setError("No se pudo cargar la inocuidad del lote.");
    } finally {
      setCargando(false);
    }
  }, [loteId]);

  useEffect(() => {
    const t = setTimeout(cargar, 0);

    return () => clearTimeout(t);
  }, [cargar]);

  useEffect(() => {
    // Los catálogos van aparte: si fallan, los registros igual se ven.
    obtenerCatalogosInocuidad()
      .then(setCatalogos)
      .catch(() => setCatalogos(null));
  }, []);

  const conError = async (accion: () => Promise<unknown>, porDefecto: string) => {
    setGuardando(true);
    setError("");

    try {
      await accion();
      await cargar();
      alCambiar?.();
    } catch (e) {
      setError(mensajeDe(e, porDefecto));
    } finally {
      setGuardando(false);
    }
  };

  const guardarControl = () =>
    conError(async () => {
      await crearControl({
        lote: loteId,
        equipo: Number(control.equipo),
        fecha: control.fecha,
        pcc1_temp_min: control.pcc1_temp_min || null,
        pcc1_caudal_max: control.pcc1_caudal_max || null,
      });
      setNuevoControl(false);
      setControl({ equipo: "", fecha: "", pcc1_temp_min: "", pcc1_caudal_max: "" });
    }, "No se pudo crear el control.");

  const guardarLectura = (id: number) => {
    const datos = lectura[id];

    if (!datos?.hora) {
      setError("La lectura necesita su hora.");
      return;
    }

    const valores: Record<string, number> = {};

    // Solo viaja lo que se midió: un campo vacío no es un cero.
    if (catalogos && datos.t) valores[catalogos.pcc1.temperatura] = Number(datos.t);
    if (catalogos && datos.c) valores[catalogos.pcc1.caudal] = Number(datos.c);

    return conError(async () => {
      await crearLecturaControl({ control: id, hora: datos.hora, valores });
      setLectura((l) => ({ ...l, [id]: { hora: "", t: "", c: "" } }));
    }, "No se pudo registrar la lectura.");
  };

  const campo =
    "rounded-xl border border-slate-200 px-3 py-2 text-sm text-slate-800 focus:border-green-500 focus:outline-none";

  if (cargando) {
    return <p className="text-sm text-slate-600">Cargando la inocuidad del lote…</p>;
  }

  const bloqueado =
    controles.some((c) => !c.pcc1.cumple) || monitoreos.some((m) => !m.resuelto);

  return (

    <div className="border-t border-slate-200 pt-5">

      <div className="flex items-start justify-between gap-3">

        <div>

          <h3 className="flex items-center gap-2 text-sm font-medium text-slate-700">
            <ShieldCheck className="h-4 w-4 text-slate-600" />
            Inocuidad
          </h3>

          <p className="mt-0.5 text-xs text-slate-600">
            PCC 1 de uperización y monitoreos PPRO. Lo que se registra aquí
            decide si el lote se puede liberar.
          </p>

        </div>

        {bloqueado && (
          <span className="shrink-0 rounded-full bg-red-50 px-3 py-1 text-xs font-medium text-red-700">
            Impide liberar
          </span>
        )}

      </div>

      {/* ------------------------------------------------ control de proceso */}

      <div className="mt-4">

        <h4 className="text-xs font-semibold uppercase tracking-wide text-slate-600">
          Control de proceso · PCC 1
        </h4>

        {controles.length === 0 ? (

          <p className="mt-2 text-sm text-slate-600">
            Sin controles registrados.
          </p>

        ) : (

          controles.map((c) => (

            <div key={c.id} className="mt-3 rounded-xl border border-slate-200 p-4">

              <div className="flex flex-wrap items-center gap-3">

                <span className="font-medium text-slate-800">{c.equipo_etiqueta}</span>

                <span className="text-sm text-slate-600">{c.fecha}</span>

                {c.pcc1.cumple ? (
                  <span className="rounded-full bg-green-50 px-2 py-0.5 text-xs font-medium text-green-700">
                    PCC 1 conforme
                  </span>
                ) : (
                  <span className="rounded-full bg-red-50 px-2 py-0.5 text-xs font-medium text-red-700">
                    PCC 1 incumplido
                  </span>
                )}

                <span className="ml-auto text-xs text-slate-600">
                  límite {c.pcc1_temp_min ?? "—"} °C · {c.pcc1_caudal_max ?? "—"} kg/h
                </span>

              </div>

              {/* Por qué no cumple, con su valor y su límite */}

              {c.pcc1.incumplimientos.length > 0 && (
                <ul className="mt-3 space-y-1 rounded-lg bg-red-50 px-3 py-2">
                  {c.pcc1.incumplimientos.map((i, n) => (
                    <li key={n} className="flex items-start gap-2 text-sm text-red-800">
                      <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
                      {i.descripcion}
                    </li>
                  ))}
                </ul>
              )}

              {c.pcc1.sin_lecturas && (
                <p className="mt-2 text-sm text-amber-700">
                  Sin lecturas: el punto crítico no vigiló nada.
                </p>
              )}

              {c.pcc1.sin_limites && (
                <p className="mt-2 text-sm text-amber-700">
                  Sin límites cargados: no hay contra qué comparar las lecturas.
                </p>
              )}

              {/* Lecturas */}

              {c.lecturas.length > 0 && (
                <ul className="mt-3 divide-y divide-slate-100">
                  {c.lecturas.map((l) => (
                    <li key={l.id} className="flex items-center gap-3 py-2 text-sm">
                      <span className="w-14 tabular-nums text-slate-600">{l.hora}</span>
                      <span className="text-slate-700">
                        {Object.entries(l.valores)
                          .map(([k, v]) => `${k} ${v}`)
                          .join("  ·  ") || "—"}
                      </span>
                      {puedeEditar && (
                        <button
                          type="button"
                          disabled={guardando}
                          onClick={() =>
                            void conError(
                              () => borrarLecturaControl(l.id),
                              "No se pudo quitar la lectura.",
                            )
                          }
                          title="Quitar esta lectura"
                          className="ml-auto rounded-lg p-1 text-slate-600 hover:bg-red-50 hover:text-red-600 disabled:opacity-50"
                        >
                          <Trash2 className="h-4 w-4" />
                        </button>
                      )}
                    </li>
                  ))}
                </ul>
              )}

              {puedeEditar && (
                <div className="mt-3 flex flex-wrap items-center gap-2">

                  <input
                    type="time"
                    className={campo}
                    value={lectura[c.id]?.hora ?? ""}
                    onChange={(e) =>
                      setLectura((l) => ({
                        ...l,
                        [c.id]: { ...(l[c.id] ?? { t: "", c: "" }), hora: e.target.value },
                      }))
                    }
                  />

                  <input
                    type="number"
                    step="any"
                    placeholder="T° DSI"
                    className={`${campo} w-28`}
                    value={lectura[c.id]?.t ?? ""}
                    onChange={(e) =>
                      setLectura((l) => ({
                        ...l,
                        [c.id]: { ...(l[c.id] ?? { hora: "", c: "" }), t: e.target.value },
                      }))
                    }
                  />

                  <input
                    type="number"
                    step="any"
                    placeholder="Caudal"
                    className={`${campo} w-28`}
                    value={lectura[c.id]?.c ?? ""}
                    onChange={(e) =>
                      setLectura((l) => ({
                        ...l,
                        [c.id]: { ...(l[c.id] ?? { hora: "", t: "" }), c: e.target.value },
                      }))
                    }
                  />

                  <button
                    type="button"
                    disabled={guardando}
                    onClick={() => void guardarLectura(c.id)}
                    className="rounded-xl bg-green-600 px-4 py-2 text-sm font-medium text-white hover:bg-green-700 disabled:opacity-50"
                  >
                    Agregar lectura
                  </button>

                </div>
              )}

            </div>

          ))

        )}

        {puedeEditar && catalogos && !nuevoControl && (
          <button
            type="button"
            onClick={() => setNuevoControl(true)}
            className="mt-3 flex items-center gap-1.5 rounded-xl border border-slate-200 px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50"
          >
            <Plus className="h-4 w-4" />
            Agregar control
          </button>
        )}

        {nuevoControl && catalogos && (
          <div className="mt-3 flex flex-wrap items-end gap-2 rounded-xl border border-slate-200 p-4">

            <select
              className={campo}
              value={control.equipo}
              onChange={(e) => setControl({ ...control, equipo: e.target.value })}
            >
              <option value="">Equipo…</option>
              {catalogos.equipo_control.map((o) => (
                <option key={o.valor} value={o.valor}>
                  {o.etiqueta}
                </option>
              ))}
            </select>

            <input
              type="date"
              className={campo}
              value={control.fecha}
              onChange={(e) => setControl({ ...control, fecha: e.target.value })}
            />

            <input
              type="number"
              step="any"
              placeholder="T° mínima"
              className={`${campo} w-32`}
              value={control.pcc1_temp_min}
              onChange={(e) => setControl({ ...control, pcc1_temp_min: e.target.value })}
            />

            <input
              type="number"
              step="any"
              placeholder="Caudal máximo"
              className={`${campo} w-36`}
              value={control.pcc1_caudal_max}
              onChange={(e) => setControl({ ...control, pcc1_caudal_max: e.target.value })}
            />

            <button
              type="button"
              disabled={guardando}
              onClick={() => void guardarControl()}
              className="rounded-xl bg-green-600 px-4 py-2 text-sm font-medium text-white hover:bg-green-700 disabled:opacity-50"
            >
              Crear
            </button>

            <button
              type="button"
              onClick={() => setNuevoControl(false)}
              className="rounded-xl px-4 py-2 text-sm font-medium text-slate-600 hover:bg-slate-100"
            >
              Cancelar
            </button>

            <p className="w-full text-xs text-slate-600">
              Los límites son los del formato de ese equipo: el VEB trabaja a
              80,0 °C y 14.175 kg/h; el Scheffers 2, a 81,2 °C y 17.100 kg/h.
              Se guardan en el control para poder auditarlo contra lo que regía
              ese día.
            </p>

          </div>
        )}

      </div>

      {/* ------------------------------------------------------------- PPRO */}

      <div className="mt-6">

        <h4 className="text-xs font-semibold uppercase tracking-wide text-slate-600">
          Monitoreos PPRO
        </h4>

        {monitoreos.length === 0 ? (

          <p className="mt-2 text-sm text-slate-600">Sin monitoreos registrados.</p>

        ) : (

          monitoreos.map((m) => (

            <div key={m.id} className="mt-3 rounded-xl border border-slate-200 p-4">

              <div className="flex flex-wrap items-center gap-3">

                <span className="font-medium text-slate-800">{m.tipo_etiqueta}</span>

                {/* La máquina se muestra porque es lo que distingue este
                    monitoreo del mismo chequeo hecho en otra: sin ella, dos
                    filas de la lista se leen idénticas. */}
                {m.equipo_etiqueta && (
                  <span className="text-sm text-slate-600">{m.equipo_etiqueta}</span>
                )}

                <span className="text-sm text-slate-600">{m.fecha}</span>

                {!m.tiene_no_ok ? (
                  <span className="rounded-full bg-green-50 px-2 py-0.5 text-xs font-medium text-green-700">
                    Todo OK
                  </span>
                ) : m.resuelto ? (
                  <span className="rounded-full bg-amber-50 px-2 py-0.5 text-xs font-medium text-amber-800">
                    No-OK con acción correctiva
                  </span>
                ) : (
                  <span className="rounded-full bg-red-50 px-2 py-0.5 text-xs font-medium text-red-700">
                    No-OK sin resolver
                  </span>
                )}

              </div>

              {m.lecturas.length > 0 && (
                <ul className="mt-3 flex flex-wrap gap-2">
                  {m.lecturas.map((l) => (
                    <li
                      key={l.id}
                      className={`rounded-lg px-2.5 py-1 text-xs ${
                        l.resultado === "ok"
                          ? "bg-slate-100 text-slate-600"
                          : "bg-red-50 font-medium text-red-700"
                      }`}
                    >
                      {l.hora} · {l.resultado_etiqueta}
                    </li>
                  ))}
                </ul>
              )}

              {puedeEditar && catalogos && (
                <div className="mt-3 flex flex-wrap items-center gap-2">

                  <input
                    type="time"
                    className={campo}
                    value={lecturaPpro[m.id] ?? ""}
                    onChange={(e) =>
                      setLecturaPpro((l) => ({ ...l, [m.id]: e.target.value }))
                    }
                  />

                  {catalogos.resultado_ppro.map((o) => (
                    <button
                      key={o.valor}
                      type="button"
                      disabled={guardando || !lecturaPpro[m.id]}
                      onClick={() =>
                        void conError(async () => {
                          await crearLecturaPpro({
                            monitoreo: m.id,
                            hora: lecturaPpro[m.id],
                            resultado: o.valor,
                          });
                          setLecturaPpro((l) => ({ ...l, [m.id]: "" }));
                        }, "No se pudo registrar la lectura.")
                      }
                      className={`rounded-xl px-4 py-2 text-sm font-medium disabled:opacity-40 ${
                        o.valor === "ok"
                          ? "border border-slate-200 text-slate-700 hover:bg-slate-50"
                          : "border border-red-200 bg-red-50 text-red-700 hover:bg-red-100"
                      }`}
                    >
                      {o.etiqueta}
                    </button>
                  ))}

                </div>
              )}

              {/* La acción correctiva: es lo que resuelve el incidente */}

              {m.tiene_no_ok && (
                <div className="mt-3">

                  <label className="mb-1 block text-xs font-medium text-slate-600">
                    Acción correctiva
                  </label>

                  {puedeEditar ? (
                    <div className="flex flex-wrap gap-2">
                      <textarea
                        rows={2}
                        className={`${campo} flex-1`}
                        value={accion[m.id] ?? m.accion_correctiva}
                        onChange={(e) =>
                          setAccion((a) => ({ ...a, [m.id]: e.target.value }))
                        }
                        placeholder="Qué se hizo con el producto y con el equipo"
                      />
                      <button
                        type="button"
                        disabled={guardando}
                        onClick={() =>
                          void conError(
                            () =>
                              editarMonitoreo(m.id, {
                                accion_correctiva: accion[m.id] ?? m.accion_correctiva,
                              }),
                            "No se pudo guardar la acción correctiva.",
                          )
                        }
                        className="self-start rounded-xl bg-green-600 px-4 py-2 text-sm font-medium text-white hover:bg-green-700 disabled:opacity-50"
                      >
                        Guardar
                      </button>
                    </div>
                  ) : (
                    <p className="text-sm text-slate-700">
                      {m.accion_correctiva || "—"}
                    </p>
                  )}

                  {!m.resuelto && (
                    <p className="mt-1 text-xs text-red-700">
                      Sin esto el lote no se libera. Lo que bloquea no es el
                      No-OK, sino que no conste qué se hizo.
                    </p>
                  )}

                </div>
              )}

            </div>

          ))

        )}

        {puedeEditar && catalogos && !nuevoMonitoreo && (
          <button
            type="button"
            onClick={() => setNuevoMonitoreo(true)}
            className="mt-3 flex items-center gap-1.5 rounded-xl border border-slate-200 px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50"
          >
            <Plus className="h-4 w-4" />
            Agregar monitoreo
          </button>
        )}

        {nuevoMonitoreo && catalogos && (
          <div className="mt-3 flex flex-wrap items-center gap-2 rounded-xl border border-slate-200 p-4">

            <select
              className={campo}
              value={monitoreo.tipo}
              onChange={(e) => setMonitoreo({ ...monitoreo, tipo: e.target.value })}
            >
              <option value="">Tipo…</option>
              {catalogos.tipo_ppro.map((o) => (
                <option key={o.valor} value={o.valor}>
                  {o.etiqueta}
                </option>
              ))}
            </select>

            {/* En qué máquina. Es lo que decide qué documento del checklist
                queda cumplido —el PPRO de las torres no es el de las
                Rovemas—, así que no es un dato de adorno. Queda opcional
                porque el detector de metales no cuelga de ninguna. */}
            <select
              className={campo}
              value={monitoreo.equipo}
              onChange={(e) => setMonitoreo({ ...monitoreo, equipo: e.target.value })}
            >
              <option value="">Sin equipo</option>
              {catalogos.equipo_ppro.map((o) => (
                <option key={o.valor} value={o.valor}>
                  {o.etiqueta}
                </option>
              ))}
            </select>

            <input
              type="date"
              className={campo}
              value={monitoreo.fecha}
              onChange={(e) => setMonitoreo({ ...monitoreo, fecha: e.target.value })}
            />

            <button
              type="button"
              disabled={guardando}
              onClick={() =>
                void conError(async () => {
                  await crearMonitoreo({
                    lote: loteId,
                    tipo: monitoreo.tipo,
                    equipo: monitoreo.equipo ? Number(monitoreo.equipo) : null,
                    fecha: monitoreo.fecha,
                  });
                  setNuevoMonitoreo(false);
                  setMonitoreo({ tipo: "", equipo: "", fecha: "" });
                }, "No se pudo crear el monitoreo.")
              }
              className="rounded-xl bg-green-600 px-4 py-2 text-sm font-medium text-white hover:bg-green-700 disabled:opacity-50"
            >
              Crear
            </button>

            <button
              type="button"
              onClick={() => setNuevoMonitoreo(false)}
              className="rounded-xl px-4 py-2 text-sm font-medium text-slate-600 hover:bg-slate-100"
            >
              Cancelar
            </button>

          </div>
        )}

      </div>

      {error && (
        <p className="mt-3 rounded-xl bg-red-50 px-4 py-3 text-sm text-red-700">
          {error}
        </p>
      )}

    </div>

  );
}


export default PanelInocuidad;
