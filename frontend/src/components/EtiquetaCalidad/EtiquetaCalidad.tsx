import {
  CheckCircle2,
  XCircle,
  HelpCircle,
  FileWarning,
} from "lucide-react";

import type { CalidadLote, ResultadoCalidad } from "../../services/produccion.service";


/*
  El veredicto de calidad de un lote.

  El color nunca carga solo el significado: cada resultado lleva su icono y
  su etiqueta escrita, para que se distinga sin depender de verlo. Los
  colores de estado (verde, rojo, ámbar) están reservados a esto y no se
  reutilizan para identificar productos ni series.
*/

const ESTILO: Record<
  ResultadoCalidad,
  { icono: typeof CheckCircle2; clases: string }
> = {
  conforme: { icono: CheckCircle2, clases: "bg-green-50 text-green-700" },
  no_conforme: { icono: XCircle, clases: "bg-red-50 text-red-700" },
  sin_analisis: { icono: HelpCircle, clases: "bg-amber-50 text-amber-700" },
  sin_especificacion: { icono: FileWarning, clases: "bg-slate-100 text-slate-600" },
};


function EtiquetaCalidad({ calidad }: { calidad: CalidadLote }) {

  const estilo = ESTILO[calidad.resultado];
  const Icono = estilo.icono;

  // Qué se salió de rango, para no dejar el veredicto sin explicación.
  const detalle = calidad.desviaciones
    .map(
      (d) =>
        `${d.parametro} ${d.valor} (rango ${d.min ?? "—"}–${d.max ?? "—"}, ${d.desvio})`,
    )
    .join(" · ");

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


export default EtiquetaCalidad;
