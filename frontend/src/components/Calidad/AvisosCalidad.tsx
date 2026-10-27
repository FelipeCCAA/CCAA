export default function AvisosCalidad({ avisos }: { avisos?: string[] }) {
  if (!avisos?.length) return null;
  return <div role="note" aria-label="Avisos de Calidad" className="mt-3 rounded-xl border border-amber-300 bg-amber-50 p-3 text-sm text-amber-950">
    <p className="font-semibold">Calidad pendiente</p>
    <ul className="mt-1 space-y-1">{avisos.map((aviso, indice) => <li key={`${indice}:${aviso}`}>{aviso}</li>)}</ul>
    <p className="mt-2 text-xs">La liberación final sigue siendo obligatoria antes del despacho.</p>
  </div>;
}
