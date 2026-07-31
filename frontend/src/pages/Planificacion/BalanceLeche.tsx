import { AlertTriangle } from "lucide-react";

import {
  CATEGORIAS,
  DIAS,
  ORIGENES,
  type FilaBalance,
} from "../../services/planificacion.service";


/*
  Balance de leche de la semana.

  Nada de esta tabla está guardado salvo las tres filas de recepción, el
  stock del primer día y el trasvasije. El consumo sale del programa horario
  —horas de bloque en evaporador × rendimiento del código— y el stock se
  arrastra de un día al siguiente.

  Ese acoplamiento es la razón de ser de la herramienta: mover un bloque de
  evaporador cambia el consumo, y con él el stock proyectado del resto de la
  semana. Por eso no hay ningún número tecleado dos veces.
*/

interface Props {
  balance: FilaBalance[];
  fechas: string[];
  dias?: number;
}


const miles = new Intl.NumberFormat("es-CL", { maximumFractionDigits: 0 });

const litros = (v: number) => (v ? miles.format(Math.round(v)) : "—");


function Celda({
  valor,
  destacado = false,
  alarma = false,
}: {
  valor: number;
  destacado?: boolean;
  alarma?: boolean;
}) {
  return (
    <td
      className={`px-3 py-2 text-right tabular-nums ${
        alarma
          ? "font-semibold text-red-700"
          : destacado
            ? "font-medium text-slate-800"
            : "text-slate-600"
      }`}
    >
      {litros(valor)}
    </td>
  );
}


function BalanceLeche({ balance, fechas, dias = 6 }: Props) {

  const filas = balance.slice(0, dias);

  return (
    <div className="overflow-x-auto">

      <table className="w-full min-w-[720px] text-sm">

        <thead>
          <tr className="border-b border-slate-200 text-left">

            <th className="px-3 py-2 text-xs font-medium text-slate-400">
              Litros
            </th>

            {filas.map((fila) => (
              <th key={fila.dia} className="px-3 py-2 text-right">
                <span className="block text-slate-700">{DIAS[fila.dia]}</span>
                <span className="block text-[10px] font-normal text-slate-400">
                  {fechas[fila.dia]}
                </span>
              </th>
            ))}

          </tr>
        </thead>

        <tbody>

          <tr className="border-b border-slate-100">
            <td className="px-3 py-2 text-slate-500">Stock 8 AM</td>
            {filas.map((f) => (
              <Celda key={f.dia} valor={f.stock_inicial} />
            ))}
          </tr>

          {ORIGENES.map((origen) => (
            <tr key={origen.valor} className="border-b border-slate-100">
              <td className="px-3 py-2 text-slate-500">
                Recepción {origen.etiqueta}
              </td>
              {filas.map((f) => (
                <Celda key={f.dia} valor={f.recepciones[origen.valor]} />
              ))}
            </tr>
          ))}

          <tr className="border-b-2 border-slate-200 bg-slate-50">
            <td className="px-3 py-2 font-medium text-slate-700">
              Total disponible
            </td>
            {filas.map((f) => (
              <Celda key={f.dia} valor={f.total_disponible} destacado />
            ))}
          </tr>

          {/* Consumo: cada fila sale del programa, no se teclea */}

          {CATEGORIAS.map((categoria) => (
            <tr key={categoria.valor} className="border-b border-slate-100">
              <td className="px-3 py-2 text-slate-500">
                {categoria.etiqueta}
                <span className="ml-1 text-[10px] text-slate-400">
                  del programa
                </span>
              </td>
              {filas.map((f) => (
                <Celda
                  key={f.dia}
                  valor={f.consumo.por_categoria[categoria.valor] ?? 0}
                />
              ))}
            </tr>
          ))}

          <tr className="border-b border-slate-100">
            <td className="px-3 py-2 text-slate-500">
              Trasvasije
              <span className="ml-1 text-[10px] text-slate-400">manual</span>
            </td>
            {filas.map((f) => (
              <Celda key={f.dia} valor={f.consumo.trasvasije} />
            ))}
          </tr>

          <tr className="border-b-2 border-slate-200 bg-slate-50">
            <td className="px-3 py-2 font-medium text-slate-700">
              Total consumo
            </td>
            {filas.map((f) => (
              <Celda key={f.dia} valor={f.consumo.total} destacado />
            ))}
          </tr>

          <tr className="border-b border-slate-200">
            <td className="px-3 py-2 font-medium text-slate-800">
              Stock final
            </td>
            {filas.map((f) => (
              <Celda key={f.dia} valor={f.stock_final} destacado />
            ))}
          </tr>

          {/* Saldo por origen: un negativo es una alarma, no un número más */}

          {ORIGENES.map((origen) => (
            <tr key={origen.valor} className="border-b border-slate-100">
              <td className="px-3 py-2 text-slate-500">
                Saldo {origen.etiqueta}
              </td>
              {filas.map((f) => (
                <Celda
                  key={f.dia}
                  valor={f.stock_por_origen[origen.valor]}
                  alarma={f.origenes_negativos.includes(origen.valor)}
                />
              ))}
            </tr>
          ))}

        </tbody>

      </table>

      {filas.some((f) => f.origenes_negativos.length > 0) && (

        <p className="mt-3 flex items-start gap-2 rounded-xl bg-red-50 px-4 py-3 text-sm text-red-700">

          <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />

          <span>
            Hay saldos negativos por origen: se programó más leche de la que se
            espera recibir de ese mandante. No se recorta a cero a propósito —
            esconderlo haría que el error llegara a planta.
          </span>

        </p>

      )}

    </div>
  );
}


export default BalanceLeche;
