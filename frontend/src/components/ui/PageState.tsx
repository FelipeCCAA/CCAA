export function PageLoader({ mensaje = "Cargando información…" }: { mensaje?: string }) {
  return (
    <div className="space-y-3" aria-live="polite">
      <p className="text-sm text-slate-500">{mensaje}</p>
      {[1, 2, 3].map((item) => <div key={item} className="h-16 animate-pulse rounded-xl bg-slate-100" />)}
    </div>
  );
}

export function EmptyState({ titulo, detalle }: { titulo: string; detalle: string }) {
  return (
    <div className="rounded-2xl border border-dashed border-slate-300 bg-slate-50 px-6 py-12 text-center">
      <p className="font-semibold text-slate-700">{titulo}</p>
      <p className="mt-2 text-sm text-slate-500">{detalle}</p>
    </div>
  );
}

export function ErrorState({ mensaje }: { mensaje: string }) {
  return <div className="rounded-xl bg-red-50 px-4 py-3 text-sm text-red-800">{mensaje}</div>;
}
