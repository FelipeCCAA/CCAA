import type { ReactNode } from "react";

/* Un campo con su etiqueta visible. Un `placeholder` no es una etiqueta:
   desaparece al escribir y el lector de pantalla no siempre lo anuncia. */
export default function CampoEtiquetado({ etiqueta, ayuda, children }: {
  etiqueta: string;
  ayuda?: string;
  children: ReactNode;
}) {
  return (
    <label className="flex min-w-0 flex-col gap-1.5 text-sm">
      <span className="font-medium text-slate-700">{etiqueta}</span>
      {children}
      {ayuda && <span className="text-xs text-slate-600">{ayuda}</span>}
    </label>
  );
}
