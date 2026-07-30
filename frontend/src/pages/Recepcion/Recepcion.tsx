import { useCallback, useEffect, useState } from "react";
import { Plus, AlertTriangle, ArrowDownToLine } from "lucide-react";
import axios from "axios";

import {
  buscarRecepciones,
  descargarRecepcion,
  ESTADOS_RECEPCION,
  obtenerOcupacion,
  obtenerSilos,
  obtenerVehiculos,
  type Ocupacion,
  type Recepcion as RecepcionTipo,
  type Silo,
  type Vehiculo,
} from "../../services/recepcion.service";

import { puedeEscribir } from "../../services/sesion";

import FormularioRecepcion from "./FormularioRecepcion";


const formato = new Intl.NumberFormat("es-CL", { maximumFractionDigits: 0 });

const POR_PAGINA = 50;


/* Colores de estado, reservados: nunca identifican otra cosa. */
const ESTILO_ESTADO: Record<string, string> = {
  registrada: "bg-slate-100 text-slate-600",
  muestreada: "bg-slate-100 text-slate-600",
  analizada: "bg-slate-100 text-slate-600",
  liberada: "bg-green-50 text-green-700",
  retenida: "bg-red-50 text-red-700",
  descargada: "bg-blue-50 text-blue-700",
  cerrada: "bg-slate-100 text-slate-500",
};


function BarraSilo({ ocupacion }: { ocupacion: Ocupacion["silos"][number] }) {

  // El ancho se recorta al 100 % para que la barra no se desborde, pero el
  // número y el aviso muestran el valor real.
  const ancho = Math.min(100, Math.max(0, ocupacion.pct));

  const color = ocupacion.negativo
    ? "bg-red-600"
    : ocupacion.excedido
      ? "bg-amber-500"
      : "bg-green-600";

  return (
    <div className="rounded-2xl border border-slate-200 bg-white p-5">

      <div className="flex items-baseline justify-between gap-2">

        <span className="font-medium text-slate-800">{ocupacion.codigo}</span>

        <span className="text-sm text-slate-500">{ocupacion.pct}%</span>

      </div>

      <div className="mt-3 h-2.5 w-full overflow-hidden rounded-full bg-slate-100">

        <div className={`h-full rounded-full ${color}`} style={{ width: `${ancho}%` }} />

      </div>

      <p className="mt-3 text-sm text-slate-600">

        {formato.format(ocupacion.litros)}

        <span className="text-slate-400">
          {" "}/ {formato.format(ocupacion.capacidad)} L
        </span>

      </p>

      {ocupacion.negativo && (

        <p className="mt-2 flex items-start gap-1.5 text-xs font-medium text-red-700">

          <AlertTriangle className="mt-px h-3.5 w-3.5 shrink-0" />

          Saldo negativo: el registro de movimientos está descuadrado.

        </p>

      )}

      {ocupacion.excedido && !ocupacion.negativo && (

        <p className="mt-2 flex items-start gap-1.5 text-xs font-medium text-amber-700">

          <AlertTriangle className="mt-px h-3.5 w-3.5 shrink-0" />

          Supera la capacidad declarada.

        </p>

      )}

    </div>
  );
}


function Recepcion() {

  const [ocupacion, setOcupacion] = useState<Ocupacion | null>(null);
  const [recepciones, setRecepciones] = useState<RecepcionTipo[]>([]);
  const [total, setTotal] = useState(0);
  const [pagina, setPagina] = useState(1);

  const [silos, setSilos] = useState<Silo[]>([]);
  const [vehiculos, setVehiculos] = useState<Vehiculo[]>([]);

  const [filtroEstado, setFiltroEstado] = useState("");
  const [filtroSilo, setFiltroSilo] = useState("");

  const [cargando, setCargando] = useState(true);
  const [error, setError] = useState("");
  const [formularioAbierto, setFormularioAbierto] = useState(false);

  const puedeEditar = puedeEscribir("recepcion");

  const cargar = useCallback(async () => {

    setCargando(true);
    setError("");

    try {

      const [datosOcupacion, pagina_] = await Promise.all([
        obtenerOcupacion(),
        buscarRecepciones({ estado: filtroEstado, silo: filtroSilo, pagina }),
      ]);

      setOcupacion(datosOcupacion);
      setRecepciones(pagina_.results);
      setTotal(pagina_.count);

    } catch (error) {

      console.error("Error cargando recepción:", error);
      setError("No se pudieron cargar los datos. ¿Está corriendo el servidor?");

    } finally {

      setCargando(false);

    }

  }, [filtroEstado, filtroSilo, pagina]);

  useEffect(() => {

    Promise.all([obtenerSilos(), obtenerVehiculos()])
      .then(([listaSilos, listaVehiculos]) => {
        setSilos(listaSilos);
        setVehiculos(listaVehiculos);
      })
      .catch((error) => console.error("Error cargando los maestros:", error));

  }, []);

  // Diferido: agrupa los cambios de filtro en una sola consulta y evita
  // actualizar el estado dentro del propio efecto.
  useEffect(() => {

    const temporizador = setTimeout(cargar, 150);

    return () => clearTimeout(temporizador);

  }, [cargar]);

  const descargar = async (recepcion: RecepcionTipo) => {

    const confirmado = window.confirm(
      `¿Descargar ${formato.format(Number(recepcion.litros))} L al silo ` +
        `${recepcion.silo_codigo}?\n\n` +
        "Se registrará el ingreso en el libro del silo y no se puede deshacer: " +
        "un error se corrige con un ajuste, que deja rastro.",
    );

    if (!confirmado) return;

    try {
      await descargarRecepcion(recepcion.id);
      cargar();
    } catch (error) {
      console.error("Error descargando:", error);

      const detalle = axios.isAxiosError(error)
        ? error.response?.data?.detail
        : null;

      setError(detalle || "No se pudo descargar la recepción.");
    }

  };

  const ultimaPagina = Math.max(1, Math.ceil(total / POR_PAGINA));

  const control =
    "rounded-xl border border-slate-300 bg-white px-4 py-2.5 text-sm outline-none focus:border-green-600";

  return (
    <div className="px-8 py-10">

      <div className="mx-auto max-w-7xl">

        {/* Encabezado */}

        <header className="mb-8 flex flex-wrap items-start justify-between gap-4">

          <div>

            <h1 className="text-3xl font-bold text-slate-800">

              Recepción y silos

            </h1>

            <p className="mt-2 text-slate-500">

              Llegada de leche y ocupación de los estanques. La ocupación es un
              saldo: ingresos menos consumo.

            </p>

          </div>

          {puedeEditar ? (

            <button
              type="button"
              onClick={() => setFormularioAbierto(true)}
              className="inline-flex items-center gap-2 rounded-xl bg-green-700 px-5 py-3 text-sm font-semibold text-white hover:bg-green-800"
            >

              <Plus className="h-5 w-5" />

              Nueva recepción

            </button>

          ) : (

            <p className="rounded-xl bg-slate-100 px-4 py-3 text-sm text-slate-500">

              Tu rol permite consultar, no registrar recepciones.

            </p>

          )}

        </header>

        {error && (

          <div className="mb-6 rounded-2xl border border-red-200 bg-red-50 px-6 py-4 text-sm text-red-700">

            {error}

          </div>

        )}

        {/* Ocupación */}

        <section className="mb-10">

          <h2 className="mb-4 text-lg font-semibold text-slate-800">

            Ocupación de silos y estanques

          </h2>

          {!ocupacion || ocupacion.silos.length === 0 ? (

            <p className="rounded-2xl border border-slate-200 bg-white px-6 py-8 text-sm text-slate-400">

              No hay silos registrados. Se dan de alta desde Administración.

            </p>

          ) : (

            <>

              <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">

                {ocupacion.silos.map((silo) => (

                  <BarraSilo key={silo.silo_id} ocupacion={silo} />

                ))}

              </div>

              <p className="mt-4 text-sm text-slate-500">

                Total en planta:{" "}
                <span className="font-medium text-slate-800">

                  {formato.format(ocupacion.litros_totales)} L

                </span>

              </p>

            </>

          )}

        </section>

        {/* Recepciones */}

        <section>

          <div className="mb-4 flex flex-wrap items-center gap-3">

            <h2 className="text-lg font-semibold text-slate-800">Recepciones</h2>

            <select
              className={control}
              value={filtroEstado}
              onChange={(e) => {
                setFiltroEstado(e.target.value);
                setPagina(1);
              }}
            >

              <option value="">Todos los estados</option>

              {ESTADOS_RECEPCION.map((e) => (

                <option key={e.valor} value={e.valor}>

                  {e.etiqueta}

                </option>

              ))}

            </select>

            <select
              className={control}
              value={filtroSilo}
              onChange={(e) => {
                setFiltroSilo(e.target.value);
                setPagina(1);
              }}
            >

              <option value="">Todos los silos</option>

              {silos.map((s) => (

                <option key={s.id} value={s.id}>

                  {s.codigo}

                </option>

              ))}

            </select>

            <span className="ml-auto text-sm text-slate-400">

              {cargando
                ? "Cargando…"
                : `${formato.format(total)} recepci${total === 1 ? "ón" : "ones"}`}

            </span>

          </div>

          <div className="rounded-2xl border border-slate-200 bg-white">

            {!cargando && recepciones.length === 0 ? (

              <p className="px-6 py-10 text-center text-sm text-slate-400">

                {total === 0 && !filtroEstado && !filtroSilo
                  ? "Todavía no hay recepciones registradas."
                  : "Ninguna recepción coincide con los filtros."}

              </p>

            ) : (

              <div className="overflow-x-auto">

                <table className="w-full text-left text-sm">

                  <thead className="text-slate-500">

                    <tr>

                      <th className="px-6 py-3 font-medium">Fecha</th>
                      <th className="px-6 py-3 font-medium">Guía</th>
                      <th className="px-6 py-3 font-medium">Camión</th>
                      <th className="px-6 py-3 font-medium">Procedencia</th>
                      <th className="px-6 py-3 font-medium">Tipo</th>
                      <th className="px-6 py-3 font-medium">Litros</th>
                      <th className="px-6 py-3 font-medium">Silo</th>
                      <th className="px-6 py-3 font-medium">Estado</th>
                      <th className="px-6 py-3 font-medium">Controles</th>
                      <th className="px-6 py-3"></th>

                    </tr>

                  </thead>

                  <tbody>

                    {recepciones.map((recepcion) => (

                      <tr key={recepcion.id} className="border-t border-slate-100">

                        <td className="px-6 py-4 text-slate-600">

                          {recepcion.fecha}

                          {recepcion.hora && (

                            <span className="text-slate-400"> {recepcion.hora.slice(0, 5)}</span>

                          )}

                        </td>

                        <td className="px-6 py-4 font-medium text-slate-800">

                          {recepcion.guia || "—"}

                        </td>

                        <td className="px-6 py-4 text-slate-600">

                          {recepcion.vehiculo_placa || "—"}

                        </td>

                        <td className="px-6 py-4 text-slate-600">

                          {recepcion.procedencia || "—"}

                        </td>

                        <td className="px-6 py-4 text-slate-600">

                          {recepcion.tipo_leche}

                        </td>

                        <td className="px-6 py-4 text-slate-600">

                          {formato.format(Number(recepcion.litros))} L

                        </td>

                        <td className="px-6 py-4 text-slate-600">

                          {recepcion.silo_codigo || "—"}

                        </td>

                        <td className="px-6 py-4">

                          <span
                            className={`inline-flex rounded-full px-3 py-1 text-xs font-medium ${
                              ESTILO_ESTADO[recepcion.estado] ?? "bg-slate-100 text-slate-600"
                            }`}
                            title={recepcion.motivo || undefined}
                          >

                            {recepcion.estado_etiqueta}

                          </span>

                        </td>

                        <td className="px-6 py-4">

                          {recepcion.evaluacion.motivos.length > 0 ? (

                            <span
                              className="inline-flex items-center gap-1.5 text-xs font-medium text-red-700"
                              title={recepcion.evaluacion.motivos.join(" · ")}
                            >

                              <AlertTriangle className="h-4 w-4" />

                              {recepcion.evaluacion.motivos.length} alerta
                              {recepcion.evaluacion.motivos.length === 1 ? "" : "s"}

                            </span>

                          ) : !recepcion.evaluacion.analizada ? (

                            /* Sin los controles decisivos no hay "sin alertas"
                               que valga: es que nadie los midió, y esta leche
                               no puede descargarse al silo. */
                            <span
                              className="inline-flex items-center gap-1.5 text-xs font-medium text-amber-700"
                              title={`Falta informar: ${recepcion.evaluacion.faltantes.join(", ")}`}
                            >

                              <AlertTriangle className="h-4 w-4" />

                              Sin analizar

                            </span>

                          ) : (

                            <span className="text-xs text-slate-400">Sin alertas</span>

                          )}

                        </td>

                        <td className="px-6 py-4 text-right">

                          {puedeEditar && recepcion.estado === "liberada" && (

                            <button
                              type="button"
                              onClick={() => descargar(recepcion)}
                              className="inline-flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-medium text-green-700 hover:bg-green-50"
                              title="Registrar el ingreso al silo"
                            >

                              <ArrowDownToLine className="h-4 w-4" />

                              Descargar

                            </button>

                          )}

                        </td>

                      </tr>

                    ))}

                  </tbody>

                </table>

              </div>

            )}

          </div>

          {ultimaPagina > 1 && (

            <div className="mt-6 flex items-center justify-between">

              <button
                type="button"
                onClick={() => setPagina((p) => Math.max(1, p - 1))}
                disabled={pagina <= 1}
                className="rounded-xl border border-slate-300 px-4 py-2 text-sm text-slate-600 disabled:opacity-40"
              >

                Anterior

              </button>

              <span className="text-sm text-slate-500">

                Página {pagina} de {ultimaPagina}

              </span>

              <button
                type="button"
                onClick={() => setPagina((p) => Math.min(ultimaPagina, p + 1))}
                disabled={pagina >= ultimaPagina}
                className="rounded-xl border border-slate-300 px-4 py-2 text-sm text-slate-600 disabled:opacity-40"
              >

                Siguiente

              </button>

            </div>

          )}

        </section>

      </div>

      {formularioAbierto && (

        <FormularioRecepcion
          silos={silos}
          vehiculos={vehiculos}
          alCerrar={() => setFormularioAbierto(false)}
          alGuardar={cargar}
        />

      )}

    </div>
  );
}


export default Recepcion;
