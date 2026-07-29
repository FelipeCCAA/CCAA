import { useEffect, useState } from "react";

import {
  Package,
  Layers,
  ShieldCheck,
  AlertTriangle,
  CheckCircle2,
  XCircle,
  HelpCircle,
  FileWarning,
} from "lucide-react";

import GraficoBarras from "../../components/GraficoBarras/GraficoBarras";

import {
  obtenerLotes,
  obtenerResumen,
  type Lote,
  type ResultadoCalidad,
  type Resumen,
} from "../../services/produccion.service";


const formato = new Intl.NumberFormat("es-CL", { maximumFractionDigits: 0 });


/*
  Cada resultado de calidad con su icono y su color.

  El color nunca carga solo el significado: siempre va con icono y con la
  etiqueta escrita, para que se distinga sin depender de verlo.
*/
const ESTILO_CALIDAD: Record<
  ResultadoCalidad,
  { icono: typeof CheckCircle2; clases: string }
> = {
  conforme: {
    icono: CheckCircle2,
    clases: "bg-green-50 text-green-700",
  },
  no_conforme: {
    icono: XCircle,
    clases: "bg-red-50 text-red-700",
  },
  sin_analisis: {
    icono: HelpCircle,
    clases: "bg-amber-50 text-amber-700",
  },
  sin_especificacion: {
    icono: FileWarning,
    clases: "bg-slate-100 text-slate-600",
  },
};


function EtiquetaCalidad({ calidad }: { calidad: Lote["calidad"] }) {

  const estilo = ESTILO_CALIDAD[calidad.resultado];
  const Icono = estilo.icono;

  const detalle = calidad.desviaciones
    .map((d) => `${d.parametro} ${d.valor} (${d.desvio})`)
    .join(", ");

  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full px-3 py-1 text-xs font-medium ${estilo.clases}`}
      title={detalle || undefined}
    >

      <Icono className="h-4 w-4" />

      {calidad.etiqueta}

    </span>
  );
}


function Tarjeta({
  etiqueta,
  valor,
  unidad,
  detalle,
  icono: Icono,
  alerta = false,
}: {
  etiqueta: string;
  valor: string;
  unidad?: string;
  detalle: string;
  icono: typeof Package;
  alerta?: boolean;
}) {
  return (
    <div className="rounded-2xl border border-slate-200 bg-white p-6">

      <div className="flex items-start justify-between">

        <p className="text-sm font-medium text-slate-500">{etiqueta}</p>

        <span
          className={
            alerta
              ? "rounded-lg bg-amber-50 p-2 text-amber-600"
              : "rounded-lg bg-slate-100 p-2 text-slate-600"
          }
        >

          <Icono className="h-5 w-5" />

        </span>

      </div>

      <p className="mt-4 text-3xl font-bold text-slate-900">

        {valor}

        {unidad && (

          <span className="ml-1 text-lg font-medium text-slate-400">

            {unidad}

          </span>

        )}

      </p>

      <p className="mt-1 text-sm text-slate-400">{detalle}</p>

    </div>
  );
}


function Dashboard() {

  const [resumen, setResumen] = useState<Resumen | null>(null);
  const [lotes, setLotes] = useState<Lote[]>([]);
  const [cargando, setCargando] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {

    let vigente = true;

    async function cargar() {

      try {

        const [datosResumen, datosLotes] = await Promise.all([
          obtenerResumen(),
          obtenerLotes(),
        ]);

        // Si el usuario salió de la pantalla mientras cargaba, no se toca
        // el estado de un componente que ya no existe.
        if (!vigente) return;

        setResumen(datosResumen);
        setLotes(datosLotes);

      } catch (error) {

        console.error("Error cargando el panel:", error);

        if (vigente) {
          setError("No se pudieron cargar los datos. ¿Está corriendo el servidor?");
        }

      } finally {

        if (vigente) setCargando(false);

      }

    }

    cargar();

    return () => {
      vigente = false;
    };

  }, []);


  if (cargando) {

    return (
      <div className="px-8 py-10">

        <p className="text-slate-400">Cargando…</p>

      </div>
    );

  }

  if (error || !resumen) {

    return (
      <div className="px-8 py-10">

        <div className="max-w-xl rounded-2xl border border-red-200 bg-red-50 px-6 py-5">

          <p className="font-medium text-red-800">No se pudo cargar el panel</p>

          <p className="mt-1 text-sm text-red-700">{error}</p>

        </div>

      </div>
    );

  }

  const { calidad } = resumen;

  return (
    <div className="px-8 py-10">

      <div className="mx-auto max-w-7xl">

        {/* Encabezado */}

        <header className="mb-10">

          <h1 className="text-3xl font-bold text-slate-800">

            Panel general

          </h1>

          <p className="mt-2 text-slate-500">

            Resumen de producción y calidad de la planta.

          </p>

        </header>

        {/* Indicadores */}

        <section className="grid grid-cols-1 gap-6 sm:grid-cols-2 xl:grid-cols-4">

          <Tarjeta
            etiqueta="Kilos producidos"
            valor={formato.format(resumen.kg_producidos)}
            unidad="kg"
            detalle="Total registrado"
            icono={Package}
          />

          <Tarjeta
            etiqueta="Lotes"
            valor={formato.format(resumen.lotes)}
            detalle="Sin contar los anulados"
            icono={Layers}
          />

          {/*
            El cumplimiento NUNCA se muestra solo: siempre con la cobertura
            al lado. Un 100 % sobre 2 de 40 lotes no es una buena noticia.
          */}
          <Tarjeta
            etiqueta="Cumplimiento de calidad"
            valor={
              calidad.cumplimiento === null
                ? "—"
                : `${formato.format(calidad.cumplimiento)}%`
            }
            detalle={
              calidad.cobertura === null
                ? "Sin lotes evaluados"
                : `Sobre ${calidad.evaluados} de ${resumen.lotes} lotes · ${calidad.cobertura}% de cobertura`
            }
            icono={ShieldCheck}
            alerta={calidad.cobertura !== null && calidad.cobertura < 80}
          />

          <Tarjeta
            etiqueta="Lotes no conformes"
            valor={formato.format(calidad.no_conforme)}
            detalle={`${calidad.sin_analisis} sin análisis · ${calidad.sin_especificacion} sin especificación`}
            icono={AlertTriangle}
            alerta={calidad.no_conforme > 0}
          />

        </section>

        {/* Gráficos */}

        <section className="mt-10 grid grid-cols-1 gap-6 lg:grid-cols-2">

          <GraficoBarras
            titulo="Kilos por producto"
            subtitulo="Suma de los lotes registrados"
            datos={resumen.kg_por_producto}
          />

          <GraficoBarras
            titulo="Kilos por mandante"
            subtitulo="Distribución de la producción según empresa"
            datos={resumen.kg_por_mandante}
          />

        </section>

        {/* Últimos lotes */}

        <section className="mt-10 rounded-2xl border border-slate-200 bg-white">

          <div className="border-b border-slate-200 px-6 py-5">

            <h2 className="text-lg font-semibold text-slate-800">

              Últimos lotes producidos

            </h2>

            <p className="mt-1 text-sm text-slate-400">

              El resultado de calidad se evalúa contra la especificación
              vigente a la fecha de cada lote.

            </p>

          </div>

          {lotes.length === 0 ? (

            <p className="px-6 py-8 text-sm text-slate-400">

              Todavía no hay lotes registrados.

            </p>

          ) : (

            <div className="overflow-x-auto">

              <table className="w-full text-left text-sm">

                <thead className="text-slate-500">

                  <tr>

                    <th className="px-6 py-3 font-medium">Lote</th>
                    <th className="px-6 py-3 font-medium">Producto</th>
                    <th className="px-6 py-3 font-medium">Mandante</th>
                    <th className="px-6 py-3 font-medium">Fecha</th>
                    <th className="px-6 py-3 font-medium">Kilos</th>
                    <th className="px-6 py-3 font-medium">Línea</th>
                    <th className="px-6 py-3 font-medium">Calidad</th>

                  </tr>

                </thead>

                <tbody>

                  {lotes.map((lote) => (

                    <tr key={lote.id} className="border-t border-slate-100">

                      <td className="px-6 py-4 font-medium text-slate-800">

                        {lote.codigo_lote}

                      </td>

                      <td className="px-6 py-4 text-slate-600">

                        {lote.producto_nombre}

                      </td>

                      <td className="px-6 py-4 text-slate-600">

                        {lote.mandante_nombre}

                      </td>

                      <td className="px-6 py-4 text-slate-600">

                        {lote.fecha}

                      </td>

                      <td className="px-6 py-4 text-slate-600">

                        {formato.format(Number(lote.kg_producidos))} kg

                      </td>

                      <td className="px-6 py-4 text-slate-600">

                        {lote.linea || "—"}

                      </td>

                      <td className="px-6 py-4">

                        <EtiquetaCalidad calidad={lote.calidad} />

                      </td>

                    </tr>

                  ))}

                </tbody>

              </table>

            </div>

          )}

        </section>

      </div>

    </div>
  );
}


export default Dashboard;
