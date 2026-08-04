const estilos: Record<string, string> = {
  cerrada: "bg-emerald-50 text-emerald-800 ring-emerald-200",
  liberado: "bg-emerald-50 text-emerald-800 ring-emerald-200",
  ejecucion: "bg-blue-50 text-blue-800 ring-blue-200",
  preparacion: "bg-amber-50 text-amber-800 ring-amber-200",
  pendiente_control: "bg-amber-50 text-amber-800 ring-amber-200",
  bloqueada: "bg-red-50 text-red-800 ring-red-200",
  cancelada: "bg-slate-100 text-slate-600 ring-slate-200",
};

export default function StatusBadge({ estado, etiqueta }: { estado: string; etiqueta?: string }) {
  return (
    <span className={`inline-flex rounded-full px-2.5 py-1 text-xs font-semibold ring-1 ring-inset ${estilos[estado] ?? "bg-slate-50 text-slate-700 ring-slate-200"}`}>
      {etiqueta ?? estado.replaceAll("_", " ")}
    </span>
  );
}
