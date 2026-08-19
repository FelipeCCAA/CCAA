import { useCallback, useEffect, useState } from "react";
import axios from "axios";
import {
  AlertTriangle, ArrowDownToLine, Beaker, CheckCircle2, ChevronLeft,
  ChevronRight, Clock3, Search, ShieldCheck, Truck, Warehouse,
} from "lucide-react";

import {
  buscarRecepciones, descargarRecepcion, obtenerCatalogosFlujo, obtenerSilos,
  type CatalogosFlujoRecepcion,
  type Recepcion as RecepcionTipo, type ResponsableRecepcion, type Silo,
} from "../../services/recepcion.service";
import { puedeEscribir } from "../../services/sesion";
import AccionRecepcion, { type AccionFlujo } from "./AccionRecepcion";

/*
  La tabla de recepciones, compartida por las cuatro pestañas de trabajo.

  Las cuatro se diferencian **solo en qué estados piden**; el botón de
  «siguiente paso» ya se deduce del estado de cada fila, así que una sola
  tabla las sirve. Cuatro copias divergirían, y lo primero que divergen son
  los botones de acción — que es justo lo que el operador usa sin leer.

  Los estados se piden **al servidor**, no se filtran aquí. La versión anterior
  se traía una página de cincuenta y repartía en el cliente: con más
  recepciones que eso, las pestañas mostraban un subconjunto silencioso.
*/

const formato = new Intl.NumberFormat("es-CL", { maximumFractionDigits: 0 });
const formatoDecimal = new Intl.NumberFormat("es-CL", { maximumFractionDigits: 2 });
const POR_PAGINA = 50;

/* Un dato ausente se muestra como «—», nunca como 0: confundir "no medido"
   con "cero" es justo lo que producía horas facturables fantasma en el
   formato de origen. */
function celda(valor: string | number | null | undefined, sufijo = ""): string {
  if (valor === null || valor === undefined || valor === "") return "—";
  const numero = Number(valor);
  return Number.isNaN(numero)
    ? String(valor)
    : `${formatoDecimal.format(numero)}${sufijo}`;
}

const ESTILO_ESTADO: Record<string, string> = {
  registrada: "border-slate-200 bg-slate-50 text-slate-700",
  muestreada: "border-sky-200 bg-sky-50 text-sky-700",
  analizada: "border-indigo-200 bg-indigo-50 text-indigo-700",
  liberada: "border-emerald-200 bg-emerald-50 text-emerald-700",
  retenida: "border-amber-200 bg-amber-50 text-amber-800",
  descargada: "border-blue-200 bg-blue-50 text-blue-700",
  cerrada: "border-slate-200 bg-slate-100 text-slate-600",
};


function formatearFecha(fecha: string) {
  const [anio, mes, dia] = fecha.split("-").map(Number);
  if (!anio || !mes || !dia) return fecha;

  return new Intl.DateTimeFormat("es-CL", {
    day: "2-digit", month: "short",
  }).format(new Date(anio, mes - 1, dia));
}


export interface Vacio {
  titulo: string;
  detalle: string;
}


function TablaRecepciones({
  estados,
  titulo,
  descripcion,
  vacio,
}: {
  estados: string;
  titulo: string;
  descripcion: string;
  vacio: Vacio;
}) {
  const [filas, setFilas] = useState<RecepcionTipo[]>([]);
  const [total, setTotal] = useState(0);
  const [pagina, setPagina] = useState(1);
  const [busqueda, setBusqueda] = useState("");
  const [termino, setTermino] = useState("");
  const [silos, setSilos] = useState<Silo[]>([]);
  const [responsables, setResponsables] = useState<ResponsableRecepcion[]>([]);
  const [catalogos, setCatalogos] = useState<CatalogosFlujoRecepcion | null>(null);
  const [cargando, setCargando] = useState(true);
  const [error, setError] = useState("");
  const [accion, setAccion] = useState<{
    tipo: AccionFlujo;
    recepcion: RecepcionTipo;
  } | null>(null);

  const puedeEditar = puedeEscribir("recepcion");
  const puedeDecidirCalidad = puedeEditar || puedeEscribir("calidad");

  const cargar = useCallback(async () => {
    setCargando(true);

    try {
      const datos = await buscarRecepciones({ estado: estados, q: termino, pagina });
      setFilas(datos.results);
      setTotal(datos.count);
      setError("");
    } catch {
      setError("No se pudo cargar esta pestaña.");
    } finally {
      setCargando(false);
    }
  }, [estados, termino, pagina]);

  useEffect(() => {
    const t = setTimeout(() => void cargar(), 0);

    return () => clearTimeout(t);
  }, [cargar]);

  useEffect(() => {
    // Los silos solo alimentan el modal de asignación: van aparte para que un
    // fallo suyo no vacíe la tabla.
    void obtenerSilos().then(setSilos).catch(() => setSilos([]));
    void obtenerCatalogosFlujo()
      .then((datos) => {
        setResponsables(datos.responsables_recepcion);
        setCatalogos(datos);
      })
      .catch(() => {
        setResponsables([]);
        setCatalogos(null);
      });
  }, []);

  const etiquetaUso = (r: RecepcionTipo): string => {
    if (!r.uso) return "—";
    const opcion = catalogos?.usos.find((op) => op.valor === r.uso);
    const base = opcion?.etiqueta ?? r.uso;
    return r.uso_numero ? `${base} N°${r.uso_numero}` : base;
  };

  // La búsqueda espera a que el usuario deje de teclear: cada pulsación es una
  // consulta a la base, no un filtro sobre lo que ya está en memoria.
  useEffect(() => {
    const t = setTimeout(() => {
      setTermino(busqueda);
      setPagina(1);
    }, 350);

    return () => clearTimeout(t);
  }, [busqueda]);

  const descargar = async (recepcion: RecepcionTipo) => {
    const confirmado = window.confirm(
      `¿Confirmas la descarga de ${formato.format(Number(recepcion.litros))} L ` +
        `en ${recepcion.silo_codigo}?\n\n` +
        "Actualizará el saldo del silo y quedará registrada en auditoría.",
    );
    if (!confirmado) return;

    try {
      await descargarRecepcion(recepcion.id);
      await cargar();
    } catch (e) {
      const detalle = axios.isAxiosError(e) ? e.response?.data?.detail : null;
      setError(detalle || "No se pudo registrar la descarga.");
    }
  };

  const ultimaPagina = Math.max(1, Math.ceil(total / POR_PAGINA));

  return (
    <section className="overflow-hidden rounded-2xl border border-slate-200 bg-white">

      <div className="border-b border-slate-200 px-5 py-5">

        <div className="flex flex-wrap items-center justify-between gap-4">
          <div>
            <h2 className="font-semibold text-slate-900">{titulo}</h2>
            <p className="mt-1 text-sm text-slate-600">{descripcion}</p>
          </div>
          <span className="text-xs font-medium text-slate-600">
            {cargando ? "Actualizando…" : `${formato.format(total)} registros`}
          </span>
        </div>

        {/* La búsqueda va en las cuatro pestañas: la del turno sirve para
            encontrar un camión concreto, y la del historial es la que más se
            usa. */}
        <label className="relative mt-4 block max-w-md">
          <Search className="pointer-events-none absolute left-3 top-3 h-4 w-4 text-slate-600" />
          <input
            className="h-10 w-full rounded-xl border border-slate-200 bg-white pl-9 pr-3 text-sm outline-none focus:border-emerald-500"
            placeholder="Buscar guía, muestra, camión o silo"
            value={busqueda}
            onChange={(e) => setBusqueda(e.target.value)}
          />
        </label>

      </div>

      {error && (
        <p className="border-b border-rose-100 bg-rose-50 px-5 py-3 text-sm text-rose-700">
          {error}
        </p>
      )}

      {!cargando && filas.length === 0 ? (
        <div className="px-6 py-16 text-center">
          <span className="mx-auto flex h-11 w-11 items-center justify-center rounded-full bg-slate-100 text-slate-600">
            <Truck className="h-5 w-5" />
          </span>
          <p className="mt-4 text-sm font-medium text-slate-700">{vacio.titulo}</p>
          <p className="mt-1 text-xs text-slate-600">{vacio.detalle}</p>
        </div>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full min-w-[1400px] text-left text-sm">

            <thead className="bg-slate-50/80 text-[11px] font-semibold uppercase tracking-[0.08em] text-slate-600">
              <tr>
                <th className="px-5 py-3">Ingreso</th>
                <th className="px-5 py-3">Camión</th>
                <th className="px-5 py-3">Origen</th>
                <th className="px-5 py-3">Volumen</th>
                <th className="px-5 py-3">Kg romana</th>
                <th className="px-5 py-3">Diferencia</th>
                <th className="px-5 py-3">TS</th>
                <th className="px-5 py-3">Uso</th>
                <th className="px-5 py-3">Horas a pagar</th>
                <th className="px-5 py-3">Muestra / calidad</th>
                <th className="px-5 py-3">Destino</th>
                <th className="px-5 py-3">Estado</th>
                <th className="px-5 py-3 text-right">Siguiente paso</th>
              </tr>
            </thead>

            <tbody className="divide-y divide-slate-100">
              {filas.map((r) => (
                <tr key={r.id} className="transition hover:bg-slate-50/70">

                  <td className="px-5 py-4">
                    <p className="font-semibold text-slate-800">
                      {formatearFecha(r.fecha)}{" "}
                      <span className="font-normal text-slate-600">
                        {r.hora?.slice(0, 5) || "—"}
                      </span>
                    </p>
                    <p className="mt-1 text-xs text-slate-600">
                      Guía {r.guia || "sin informar"}
                    </p>
                  </td>

                  <td className="px-5 py-4">
                    <p className="font-semibold text-slate-800">
                      {r.vehiculo_placa || "Sin camión"}
                    </p>
                    <p className="mt-1 text-xs text-slate-600">
                      Turno {r.turno || "—"} · {r.modulos.length}{" "}
                      {r.modulos.length === 1 ? "módulo" : "módulos"}
                    </p>
                  </td>

                  <td className="px-5 py-4">
                    <p className="text-slate-700">{r.procedencia || "—"}</p>
                    <p className="mt-1 text-xs text-slate-600">{r.tipo_leche}</p>
                  </td>

                  <td className="px-5 py-4 font-semibold tabular-nums text-slate-800">
                    {formato.format(Number(r.litros))} L
                  </td>

                  <td className="px-5 py-4 tabular-nums text-slate-700">
                    {celda(r.kg_romana, " kg")}
                  </td>

                  <td className="px-5 py-4 tabular-nums text-slate-700">
                    {celda(r.diferencia_kg, " kg")}
                  </td>

                  <td className="px-5 py-4 tabular-nums text-slate-700">
                    {celda(r.solidos_totales, "%")}
                  </td>

                  <td className="px-5 py-4 text-slate-700">
                    {etiquetaUso(r)}
                  </td>

                  <td className="px-5 py-4 tabular-nums text-slate-700">
                    {celda(r.horas_a_pagar, " h")}
                  </td>

                  <td className="px-5 py-4">
                    {r.estado === "registrada" ? (
                      <span className="inline-flex items-center gap-1.5 text-xs font-medium text-slate-600">
                        <Clock3 className="h-3.5 w-3.5" />Sin muestra
                      </span>
                    ) : r.estado === "muestreada" ? (
                      <span className="text-xs">
                        <span className="block font-semibold text-sky-700">
                          {r.codigo_muestra}
                        </span>
                        <span className="mt-1 block text-slate-600">
                          Esperando decisión
                        </span>
                      </span>
                    ) : r.evaluacion.motivos.length > 0 ? (
                      <span
                        className="inline-flex items-center gap-1.5 text-xs font-semibold text-rose-700"
                        title={r.evaluacion.motivos.join(" · ")}
                      >
                        <AlertTriangle className="h-3.5 w-3.5" />
                        {r.evaluacion.motivos.length} alerta
                        {r.evaluacion.motivos.length === 1 ? "" : "s"}
                      </span>
                    ) : (
                      <span className="inline-flex items-center gap-1.5 text-xs font-medium text-emerald-700">
                        <CheckCircle2 className="h-3.5 w-3.5" />Aprobada
                      </span>
                    )}
                  </td>

                  <td className="px-5 py-4">
                    <span className="inline-flex items-center gap-1.5 text-slate-700">
                      <Warehouse className="h-3.5 w-3.5 text-slate-600" />
                      {r.silo_codigo || "Sin asignar"}
                    </span>
                  </td>

                  <td className="px-5 py-4">
                    <span
                      className={`inline-flex rounded-full border px-2.5 py-1 text-xs font-semibold ${
                        ESTILO_ESTADO[r.estado] ?? ESTILO_ESTADO.registrada
                      }`}
                      title={r.motivo || undefined}
                    >
                      {r.estado_etiqueta}
                    </span>
                  </td>

                  <td className="px-5 py-4 text-right">
                    {puedeEditar && r.estado === "registrada" ? (
                      <button
                        type="button"
                        onClick={() => setAccion({ tipo: "muestra", recepcion: r })}
                        className="inline-flex items-center gap-1.5 rounded-lg bg-sky-50 px-3 py-2 text-xs font-semibold text-sky-700 transition hover:bg-sky-100"
                      >
                        <Beaker className="h-3.5 w-3.5" />Tomar muestra
                      </button>
                    ) : puedeDecidirCalidad && ["muestreada", "retenida"].includes(r.estado) ? (
                      <button
                        type="button"
                        onClick={() => setAccion({ tipo: "calidad", recepcion: r })}
                        className="inline-flex items-center gap-1.5 rounded-lg bg-violet-50 px-3 py-2 text-xs font-semibold text-violet-700 transition hover:bg-violet-100"
                      >
                        <ShieldCheck className="h-3.5 w-3.5" />
                        {r.estado === "retenida" ? "Reanalizar" : "Evaluar"}
                      </button>
                    ) : puedeEditar && r.estado === "liberada" && !r.silo ? (
                      <button
                        type="button"
                        onClick={() => setAccion({ tipo: "silo", recepcion: r })}
                        className="inline-flex items-center gap-1.5 rounded-lg bg-blue-50 px-3 py-2 text-xs font-semibold text-blue-700 transition hover:bg-blue-100"
                      >
                        <Warehouse className="h-3.5 w-3.5" />Asignar silo
                      </button>
                    ) : puedeEditar && r.estado === "liberada" && r.silo ? (
                      <button
                        type="button"
                        onClick={() => void descargar(r)}
                        className="inline-flex items-center gap-1.5 rounded-lg bg-emerald-50 px-3 py-2 text-xs font-semibold text-emerald-700 transition hover:bg-emerald-100"
                      >
                        <ArrowDownToLine className="h-3.5 w-3.5" />Descargar
                      </button>
                    ) : (
                      <span className="text-xs text-slate-300">—</span>
                    )}
                  </td>

                </tr>
              ))}
            </tbody>

          </table>
        </div>
      )}

      {ultimaPagina > 1 && (
        <div className="flex items-center justify-between border-t border-slate-200 px-5 py-4">
          <button
            type="button"
            onClick={() => setPagina((v) => Math.max(1, v - 1))}
            disabled={pagina <= 1}
            className="inline-flex items-center gap-1 rounded-lg px-3 py-2 text-sm font-medium text-slate-600 hover:bg-slate-100 disabled:opacity-30"
          >
            <ChevronLeft className="h-4 w-4" />Anterior
          </button>
          <span className="text-xs font-medium text-slate-600">
            Página {pagina} de {ultimaPagina}
          </span>
          <button
            type="button"
            onClick={() => setPagina((v) => Math.min(ultimaPagina, v + 1))}
            disabled={pagina >= ultimaPagina}
            className="inline-flex items-center gap-1 rounded-lg px-3 py-2 text-sm font-medium text-slate-600 hover:bg-slate-100 disabled:opacity-30"
          >
            Siguiente<ChevronRight className="h-4 w-4" />
          </button>
        </div>
      )}

      {accion && (
        <AccionRecepcion
          accion={accion.tipo}
          recepcion={accion.recepcion}
          silos={silos}
          responsables={responsables}
          alCerrar={() => setAccion(null)}
          alGuardar={cargar}
        />
      )}

    </section>
  );
}


export default TablaRecepciones;
