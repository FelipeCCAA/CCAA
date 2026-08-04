import { useEffect, useState } from "react";
import { AlertTriangle, ClipboardList, CalendarClock, type LucideIcon } from "lucide-react";

import { EmptyState, ErrorState, PageLoader } from "../../components/ui/PageState";
import StatusBadge from "../../components/ui/StatusBadge";
import { obtenerOrdenesTrabajo, obtenerResumenMantenimiento, type OrdenTrabajo, type ResumenMantenimiento } from "../../services/mantenimiento.service";

export default function Mantenimiento() {
  const [resumen, setResumen] = useState<ResumenMantenimiento | null>(null);
  const [ordenes, setOrdenes] = useState<OrdenTrabajo[]>([]);
  const [cargando, setCargando] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    Promise.all([obtenerResumenMantenimiento(), obtenerOrdenesTrabajo()])
      .then(([datos, pagina]) => { setResumen(datos); setOrdenes(pagina.results); })
      .catch(() => setError("No se pudo cargar el tablero de mantenimiento."))
      .finally(() => setCargando(false));
  }, []);

  const indicadores: { titulo: string; valor: number; icono: LucideIcon }[] = [
    { titulo: "Órdenes abiertas", valor: resumen?.ordenes_abiertas ?? 0, icono: ClipboardList },
    { titulo: "Planes vencidos", valor: resumen?.planes_vencidos ?? 0, icono: CalendarClock },
    { titulo: "Fallas críticas", valor: resumen?.fallas_criticas_abiertas ?? 0, icono: AlertTriangle },
  ];

  return <main className="px-6 py-8 lg:px-10"><div className="mx-auto max-w-7xl space-y-8">
    <header><p className="text-sm font-semibold uppercase tracking-wider text-green-700">Activos</p><h1 className="mt-2 text-3xl font-bold text-slate-900">Mantenimiento</h1><p className="mt-2 text-slate-500">Planes preventivos, fallas, órdenes de trabajo y disponibilidad de equipos.</p></header>
    {error && <ErrorState mensaje={error} />}
    {cargando ? <PageLoader /> : <>
      <section className="grid gap-4 md:grid-cols-3">
        {indicadores.map(({ titulo, valor, icono: Icono }) => <article key={titulo} className="rounded-2xl border border-slate-200 bg-white p-5"><div className="flex items-center justify-between"><div><p className="text-sm text-slate-500">{titulo}</p><p className="mt-2 text-3xl font-bold text-slate-900">{valor}</p></div><Icono className="h-6 w-6 text-green-700" /></div></article>)}
      </section>
      <section>{ordenes.length === 0 ? <EmptyState titulo="Sin órdenes de trabajo" detalle="Crea el primer plan preventivo u orden correctiva desde el módulo." /> : <div className="overflow-x-auto rounded-2xl border border-slate-200 bg-white"><table className="w-full text-left text-sm"><thead className="bg-slate-50 text-slate-500"><tr><th className="px-5 py-3">Orden</th><th className="px-5 py-3">Equipo</th><th className="px-5 py-3">Tipo</th><th className="px-5 py-3">Prioridad</th><th className="px-5 py-3">Estado</th></tr></thead><tbody>{ordenes.map((orden) => <tr key={orden.id} className="border-t border-slate-100"><td className="px-5 py-4 font-semibold">{orden.numero}</td><td className="px-5 py-4">{orden.equipo_nombre}</td><td className="px-5 py-4 capitalize">{orden.tipo}</td><td className="px-5 py-4">{orden.prioridad}</td><td className="px-5 py-4"><StatusBadge estado={orden.estado} etiqueta={orden.estado_etiqueta} /></td></tr>)}</tbody></table></div>}</section>
    </>}
  </div></main>;
}
