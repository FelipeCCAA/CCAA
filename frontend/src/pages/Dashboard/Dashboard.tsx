import {
  Package,
  Droplets,
  AlertTriangle,
  ClipboardCheck,
  CheckCircle2,
  XCircle,
} from "lucide-react";


/*
  Datos de ejemplo.

  Por ahora están escritos aquí directamente porque el backend todavía no
  expone un endpoint del panel. Cuando exista, esto se reemplaza por una
  llamada con `api` (ver services/api.ts) y el resto del componente no cambia.
*/

const indicadores = [
  {
    etiqueta: "Kilos producidos",
    valor: "48.320",
    unidad: "kg",
    detalle: "Mes en curso",
    icono: Package,
  },
  {
    etiqueta: "Litros recepcionados",
    valor: "612.450",
    unidad: "L",
    detalle: "Silos 1-8, TK LD y TK Crema",
    icono: Droplets,
  },
  {
    etiqueta: "Recepciones retenidas",
    valor: "3",
    unidad: "",
    detalle: "Pendientes de liberación",
    icono: AlertTriangle,
    alerta: true,
  },
  {
    etiqueta: "Liberaciones pendientes",
    valor: "7",
    unidad: "",
    detalle: "Checklist de calidad incompleto",
    icono: ClipboardCheck,
    alerta: true,
  },
];


const ultimosLotes = [
  {
    lote: "L-2607-014",
    producto: "Leche entera en polvo",
    mandante: "Nestlé",
    kilos: "12.500",
    linea: "E1",
    conforme: true,
  },
  {
    lote: "L-2607-013",
    producto: "Leche descremada en polvo",
    mandante: "P. Unión",
    kilos: "9.800",
    linea: "E2",
    conforme: true,
  },
  {
    lote: "L-2607-012",
    producto: "Crema",
    mandante: "Nestlé",
    kilos: "4.220",
    linea: "E1",
    conforme: false,
  },
  {
    lote: "L-2607-011",
    producto: "Leche entera en polvo",
    mandante: "Nestlé",
    kilos: "11.300",
    linea: "E2",
    conforme: true,
  },
];


function Dashboard() {
  return (
    <div className="px-8 py-10">

      <div className="mx-auto max-w-7xl">

        {/* Encabezado */}

        <header className="mb-10">

          <h1 className="text-3xl font-bold text-slate-800">

            Panel general

          </h1>

          <p className="mt-2 text-slate-500">

            Resumen de producción, recepción y calidad de la planta.

          </p>

        </header>

        {/* Indicadores */}

        <section className="grid grid-cols-1 gap-6 sm:grid-cols-2 xl:grid-cols-4">

          {indicadores.map((indicador) => {

            const Icono = indicador.icono;

            return (

              <div
                key={indicador.etiqueta}
                className="rounded-2xl border border-slate-200 bg-white p-6"
              >

                <div className="flex items-start justify-between">

                  <p className="text-sm font-medium text-slate-500">

                    {indicador.etiqueta}

                  </p>

                  <span
                    className={
                      indicador.alerta
                        ? "rounded-lg bg-amber-50 p-2 text-amber-600"
                        : "rounded-lg bg-slate-100 p-2 text-slate-600"
                    }
                  >

                    <Icono className="h-5 w-5" />

                  </span>

                </div>

                <p className="mt-4 text-3xl font-bold text-slate-900">

                  {indicador.valor}

                  {indicador.unidad && (

                    <span className="ml-1 text-lg font-medium text-slate-400">

                      {indicador.unidad}

                    </span>

                  )}

                </p>

                <p className="mt-1 text-sm text-slate-400">

                  {indicador.detalle}

                </p>

              </div>

            );

          })}

        </section>

        {/* Últimos lotes */}

        <section className="mt-10 rounded-2xl border border-slate-200 bg-white">

          <div className="border-b border-slate-200 px-6 py-5">

            <h2 className="text-lg font-semibold text-slate-800">

              Últimos lotes producidos

            </h2>

          </div>

          <div className="overflow-x-auto">

            <table className="w-full text-left text-sm">

              <thead className="text-slate-500">

                <tr>

                  <th className="px-6 py-3 font-medium">Lote</th>
                  <th className="px-6 py-3 font-medium">Producto</th>
                  <th className="px-6 py-3 font-medium">Mandante</th>
                  <th className="px-6 py-3 font-medium">Kilos</th>
                  <th className="px-6 py-3 font-medium">Línea</th>
                  <th className="px-6 py-3 font-medium">Calidad</th>

                </tr>

              </thead>

              <tbody>

                {ultimosLotes.map((lote) => (

                  <tr
                    key={lote.lote}
                    className="border-t border-slate-100"
                  >

                    <td className="px-6 py-4 font-medium text-slate-800">

                      {lote.lote}

                    </td>

                    <td className="px-6 py-4 text-slate-600">

                      {lote.producto}

                    </td>

                    <td className="px-6 py-4 text-slate-600">

                      {lote.mandante}

                    </td>

                    <td className="px-6 py-4 text-slate-600">

                      {lote.kilos} kg

                    </td>

                    <td className="px-6 py-4 text-slate-600">

                      {lote.linea}

                    </td>

                    <td className="px-6 py-4">

                      {lote.conforme ? (

                        <span className="inline-flex items-center gap-1.5 rounded-full bg-green-50 px-3 py-1 text-xs font-medium text-green-700">

                          <CheckCircle2 className="h-4 w-4" />

                          Conforme

                        </span>

                      ) : (

                        <span className="inline-flex items-center gap-1.5 rounded-full bg-red-50 px-3 py-1 text-xs font-medium text-red-700">

                          <XCircle className="h-4 w-4" />

                          No conforme

                        </span>

                      )}

                    </td>

                  </tr>

                ))}

              </tbody>

            </table>

          </div>

        </section>

      </div>

    </div>
  );
}


export default Dashboard;
