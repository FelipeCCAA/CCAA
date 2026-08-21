import { useCallback, useEffect, useState } from "react";

import {
  DIAS,
  obtenerContraste,
  type Contraste as ContrasteTipo,
  type Desviacion,
} from "../../services/planificacion.service";


/*
  Lo planificado frente a lo que realmente pasó.

  Los dos lados se miden con datos distintos, y esa es toda la idea: el plan
  sale del programa y del balance; lo real, del libro mayor de silos y de los
  lotes. Si el lado real se copiara del plan, la tabla siempre cuadraría y no
  serviría para nada.
*/

interface Props {
  semanaId: number;
}


const miles = new Intl.NumberFormat("es-CL", { maximumFractionDigits: 0 });

const numero = (v: number) => (v ? miles.format(Math.round(v)) : "—");


function Delta({ desviacion }: { desviacion: Desviacion }) {

  const { diferencia, pct } = desviacion;

  if (!diferencia) {
    return <span className="text-slate-600">—</span>;
  }

  // El signo importa más que el color: por debajo de lo planificado no es
  // "malo" ni "bueno" sin contexto, es una diferencia que alguien tiene que
  // mirar.
  const signo = diferencia > 0 ? "+" : "−";

  return (
    <span className={diferencia > 0 ? "text-blue-700" : "text-amber-700"}>
      {signo}
      {miles.format(Math.abs(Math.round(diferencia)))}
      {pct !== null && (
        <span className="ml-1 text-[11px] text-slate-600">
          ({signo}
          {Math.abs(pct)}%)
        </span>
      )}
    </span>
  );
}


function Tarjeta({
  titulo,
  unidad,
  desviacion,
}: {
  titulo: string;
  unidad: string;
  desviacion: Desviacion;
}) {
  return (
    <div className="rounded-2xl border border-slate-200 bg-white p-5">

      <p className="text-sm text-slate-600">{titulo}</p>

      <p className="mt-2 text-2xl font-semibold text-slate-800">
        {numero(desviacion.real)}
        <span className="ml-1 text-sm font-normal text-slate-600">{unidad}</span>
      </p>

      <p className="mt-1 text-sm text-slate-600">
        planificado {numero(desviacion.plan)} ·{" "}
        <Delta desviacion={desviacion} />
      </p>

    </div>
  );
}


function Contraste({ semanaId }: Props) {

  const [datos, setDatos] = useState<ContrasteTipo | null>(null);
  const [cargando, setCargando] = useState(true);
  const [error, setError] = useState("");

  const cargar = useCallback(async () => {

    setCargando(true);
    setError("");

    try {
      setDatos(await obtenerContraste(semanaId));
    } catch {
      setError("No se pudo cargar el contraste.");
    } finally {
      setCargando(false);
    }

  }, [semanaId]);

  useEffect(() => {

    const temporizador = setTimeout(cargar, 0);

    return () => clearTimeout(temporizador);

  }, [cargar]);

  if (cargando) {
    return <p className="text-sm text-slate-600">Cargando contraste…</p>;
  }

  if (error || !datos) {
    return <p className="text-sm text-red-600">{error}</p>;
  }

  const { resumen, dias } = datos;

  return (
    <div className="space-y-6">

      <div className="grid gap-4 sm:grid-cols-3">
        <Tarjeta
          titulo="Leche recibida"
          unidad="L"
          desviacion={resumen.leche_recibida}
        />
        <Tarjeta
          titulo="Leche consumida"
          unidad="L"
          desviacion={resumen.leche_consumida}
        />
        <Tarjeta titulo="Producción" unidad="kg" desviacion={resumen.kilos} />
      </div>

      <div className="overflow-hidden rounded-2xl border border-slate-200 bg-white">

        <div className="overflow-x-auto">

          <table className="w-full min-w-[760px] text-sm">

            <thead className="border-b border-slate-200 bg-slate-50 text-left text-xs uppercase tracking-wide text-slate-600">
              <tr>
                <th className="px-5 py-3 font-medium">Día</th>
                <th className="px-5 py-3 text-right font-medium">Leche recibida</th>
                <th className="px-5 py-3 text-right font-medium">Leche consumida</th>
                <th className="px-5 py-3 text-right font-medium">Kilos</th>
                <th className="px-5 py-3 text-right font-medium">Lotes</th>
              </tr>
            </thead>

            <tbody className="divide-y divide-slate-100">

              {dias.map((fila) => (
                <tr
                  key={fila.dia}
                  className={fila.hubo_actividad ? "" : "text-slate-600"}
                >

                  <td className="px-5 py-3">
                    <span className="text-slate-700">{DIAS[fila.dia]}</span>
                    <span className="block text-[11px] text-slate-600">
                      {fila.fecha}
                    </span>
                  </td>

                  <td className="px-5 py-3 text-right tabular-nums">
                    {numero(fila.leche_recibida.real)}
                    <span className="block text-[11px]">
                      <Delta desviacion={fila.leche_recibida} />
                    </span>
                  </td>

                  <td className="px-5 py-3 text-right tabular-nums">
                    {numero(fila.leche_consumida.real)}
                    <span className="block text-[11px]">
                      <Delta desviacion={fila.leche_consumida} />
                    </span>
                  </td>

                  <td className="px-5 py-3 text-right tabular-nums">
                    {numero(fila.kilos.real)}
                    <span className="block text-[11px]">
                      <Delta desviacion={fila.kilos} />
                    </span>
                  </td>

                  <td className="px-5 py-3 text-right text-slate-600">
                    {fila.lotes.length || "—"}
                  </td>

                </tr>
              ))}

            </tbody>

          </table>

        </div>

      </div>

      <p className="text-xs text-slate-600">
        La leche recibida cuenta solo las recepciones <strong>descargadas</strong> al
        silo: una registrada todavía no entró. La consumida sale de las salidas
        del libro mayor de cada lote, que es un dato distinto del plan — si se
        copiara del programa, el contraste siempre cuadraría.
      </p>

    </div>
  );
}


export default Contraste;
