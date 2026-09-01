import { useEffect, useState } from "react";
import { X } from "lucide-react";
import axios from "axios";

import {
  crearBloque,
  obtenerOrdenesPlan,
  type CodigoProduccion,
  type OrdenProduccionPlan,
  type TipoActividadPlan,
} from "../../services/planificacion.service";

import type { Equipo, Mandante } from "../../services/maestros.service";
import { obtenerClientesDespacho, type ClienteDespacho } from "../../services/inventario.service";


/*
  Alta de un bloque del programa.

  El bloque es un tramo de horas en un equipo, no una celda pintada: por eso
  se piden inicio y fin en vez de "cuántas casillas". Admite medias horas
  porque así se programa en planta.

  El solapamiento lo rechaza el servidor, que es quien ve los demás bloques
  del mismo equipo y día. Aquí solo se muestra su motivo.
*/

interface Props {
  semanaId: number;
  /* Id del equipo en el maestro. */
  equipo: number;
  equipos: Equipo[];
  dia: number;
  horaInicio: number;
  codigos: CodigoProduccion[];
  tiposActividad: TipoActividadPlan[];
  mandantes: Mandante[];
  alCerrar: () => void;
  alGuardar: () => void;
}


const claseCampo =
  "w-full rounded-xl border border-slate-200 px-3 py-2 text-sm text-slate-800 " +
  "focus:border-green-500 focus:outline-none";


function FormularioBloque({
  semanaId,
  equipo,
  equipos,
  dia,
  horaInicio,
  codigos,
  tiposActividad,
  mandantes,
  alCerrar,
  alGuardar,
}: Props) {

  const produccion = tiposActividad.find((item) => item.codigo === "produccion");
  const [tipoActividad, setTipoActividad] = useState<number | null>(produccion?.id ?? tiposActividad[0]?.id ?? null);
  const [inicio, setInicio] = useState(String(horaInicio));
  const [fin, setFin] = useState(String(Math.min(horaInicio + 4, 24)));
  const [codigo, setCodigo] = useState<string>("");
  const [kg, setKg] = useState("");
  const [observacion, setObservacion] = useState("");
  const [origen, setOrigen] = useState("");
  const [orden, setOrden] = useState("");
  const [cliente, setCliente] = useState("");
  const [ordenes, setOrdenes] = useState<OrdenProduccionPlan[]>([]);
  const [clientes, setClientes] = useState<ClienteDespacho[]>([]);
  const actividad = tiposActividad.find((item) => item.id === tipoActividad);
  const esProduccion = actividad?.codigo === "produccion";

  const [guardando, setGuardando] = useState(false);
  const [error, setError] = useState("");

  const suyo = equipos.find((e) => e.id === equipo);
  const nombreEquipo = suyo?.nombre ?? "Equipo";

  useEffect(() => {
    void Promise.all([obtenerOrdenesPlan(), obtenerClientesDespacho()])
      .then(([ordenesCargadas, clientesCargados]) => { setOrdenes(ordenesCargadas); setClientes(clientesCargados); })
      .catch(() => undefined);
  }, []);

  const guardar = async () => {

    setError("");
    setGuardando(true);

    try {

      await crearBloque({
        semana: semanaId,
        equipo,
        dia,
        hora_inicio: Number(inicio),
        hora_fin: Number(fin),
        tipo: esProduccion ? "produccion" : "estado",
        tipo_actividad: tipoActividad,
        codigo: esProduccion ? Number(codigo) || null : null,
        estado_equipo: esProduccion ? "" : "X",
        cantidad_kg: kg ? Number(kg) : null,
        origen_leche: origen ? Number(origen) : null,
        orden_produccion: orden ? Number(orden) : null,
        cliente: cliente ? Number(cliente) : null,
        observacion,
      });

      alGuardar();

    } catch (e) {

      if (axios.isAxiosError(e) && e.response?.data) {
        const datos = e.response.data as Record<string, string[] | string>;
        setError([...new Set(Object.values(datos).flat())].join(" "));
      } else {
        setError("No se pudo guardar el bloque.");
      }

    } finally {
      setGuardando(false);
    }
  };

  const listo =
    Number(fin) > Number(inicio) &&
    Boolean(tipoActividad) && (!esProduccion || Boolean(codigo));

  return (
    <div className="fixed inset-0 z-50 flex items-start justify-center overflow-y-auto bg-slate-900/40 p-4">

      <div className="my-8 w-full max-w-lg rounded-2xl bg-white shadow-xl">

        <div className="flex items-start justify-between gap-4 border-b border-slate-200 px-6 py-5">

          <div>
            <h2 className="text-lg font-semibold text-slate-800">
              Programar bloque
            </h2>
            <p className="mt-0.5 text-sm text-slate-600">{nombreEquipo}</p>
          </div>

          <button
            type="button"
            onClick={alCerrar}
            aria-label="Cerrar"
            className="rounded-lg p-1 text-slate-600 hover:bg-slate-100 hover:text-slate-600"
          >
            <X className="h-5 w-5" />
          </button>

        </div>

        <div className="space-y-4 px-6 py-5">

          <div>
            <label className="mb-1 block text-xs font-medium text-slate-600">Tipo de actividad</label>
            <select value={tipoActividad ?? ""} onChange={(e) => setTipoActividad(Number(e.target.value))} className={claseCampo}>
              <option value="">Elegir…</option>
              {tiposActividad.map((item) => <option key={item.id} value={item.id}>{item.nombre}</option>)}
            </select>
          </div>

          <div className="grid grid-cols-2 gap-4">

            <div>
              <label className="mb-1 block text-xs font-medium text-slate-600">
                Hora de inicio
              </label>
              <input
                type="number"
                min="0"
                max="24"
                step="0.5"
                value={inicio}
                onChange={(e) => setInicio(e.target.value)}
                className={claseCampo}
              />
            </div>

            <div>
              <label className="mb-1 block text-xs font-medium text-slate-600">
                Hora de término
              </label>
              <input
                type="number"
                min="0"
                max="24"
                step="0.5"
                value={fin}
                onChange={(e) => setFin(e.target.value)}
                className={claseCampo}
              />
            </div>

          </div>

          {esProduccion ? (
            <>
              <div>
                <label className="mb-1 block text-xs font-medium text-slate-600">
                  Código de producción
                </label>
                <select
                  value={codigo}
                  onChange={(e) => {
                    setCodigo(e.target.value);
                    const seleccionado = codigos.find((item) => item.id === Number(e.target.value));
                    if (seleccionado?.mandante) setOrigen(String(seleccionado.mandante));
                  }}
                  className={claseCampo}
                >
                  <option value="">Elegir…</option>
                  {codigos.map((c) => (
                    <option key={c.id} value={c.id}>
                      {c.codigo} · {c.categoria_etiqueta} · {c.rendimiento_lh} L/h
                    </option>
                  ))}
                </select>

                {codigos.length === 0 && (
                  <p className="mt-1 text-xs text-amber-700">
                    No hay códigos cargados. Se cargan desde Administración.
                  </p>
                )}
              </div>

              <div>
                <label className="mb-1 block text-xs font-medium text-slate-600">Orden de producción <span className="font-normal">opcional</span></label>
                <select value={orden} onChange={(e) => setOrden(e.target.value)} className={claseCampo}><option value="">Sin orden asociada</option>{ordenes.map((item) => <option key={item.id} value={item.id}>{item.codigo} · {item.producto_nombre}</option>)}</select>
              </div>

              <div>
                <label className="mb-1 block text-xs font-medium text-slate-600">
                  Kilos objetivo
                  <span className="ml-1 font-normal text-slate-600">opcional</span>
                </label>
                <input
                  type="number"
                  min="0"
                  value={kg}
                  onChange={(e) => setKg(e.target.value)}
                  className={claseCampo}
                />
              </div>
            </>
          ) : actividad && <p className="rounded-xl border border-slate-200 px-4 py-3 text-sm text-slate-600">Se programará <strong style={{ color: actividad.color }}>{actividad.nombre}</strong> como intervalo auditable del recurso.</p>}

          {(actividad?.requiere_origen || esProduccion) && <div><label className="mb-1 block text-xs font-medium text-slate-600">Origen / propietario de la leche</label><select required={actividad?.requiere_origen} value={origen} onChange={(e) => setOrigen(e.target.value)} className={claseCampo}><option value="">Derivar del producto</option>{mandantes.filter((item) => item.activo).map((item) => <option key={item.id} value={item.id}>{item.nombre}</option>)}</select></div>}

          {actividad?.codigo === "despacho" && <div><label className="mb-1 block text-xs font-medium text-slate-600">Cliente</label><select value={cliente} onChange={(e) => setCliente(e.target.value)} className={claseCampo}><option value="">Sin cliente asociado</option>{clientes.filter((item) => item.activo).map((item) => <option key={item.id} value={item.id}>{item.codigo} · {item.nombre}</option>)}</select></div>}

          <div>
            <label className="mb-1 block text-xs font-medium text-slate-600">
              Observación
            </label>
            <textarea
              rows={2}
              value={observacion}
              onChange={(e) => setObservacion(e.target.value)}
              className={claseCampo}
            />
          </div>

          {esProduccion && (
            <p className="text-xs text-slate-600">
              Solo los evaporadores restan del balance de leche. Un bloque en
              una línea se programa igual, pero su leche ya la contó el
              evaporador que la alimenta.
            </p>
          )}

          {error && (
            <p className="rounded-xl bg-red-50 px-4 py-3 text-sm text-red-700">
              {error}
            </p>
          )}

        </div>

        <div className="flex justify-end gap-2 border-t border-slate-200 px-6 py-4">

          <button
            type="button"
            onClick={alCerrar}
            className="rounded-xl px-4 py-2 text-sm font-medium text-slate-600 hover:bg-slate-100"
          >
            Cancelar
          </button>

          <button
            type="button"
            disabled={guardando || !listo}
            onClick={() => void guardar()}
            className="rounded-xl bg-green-600 px-4 py-2 text-sm font-medium text-white hover:bg-green-700 disabled:opacity-50"
          >
            {guardando ? "Guardando…" : "Agregar bloque"}
          </button>

        </div>

      </div>

    </div>
  );
}


export default FormularioBloque;
