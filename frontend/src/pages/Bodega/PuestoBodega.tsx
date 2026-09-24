import { NavLink, Outlet } from "react-router-dom";

const PESTANAS = [
  { a: "", texto: "Operar", exacta: true },
  { a: "recepcion", texto: "Recepción de compras" },
  { a: "configuracion", texto: "Configuración" },
];

/* El puesto abre en lo que hay que hacer, no en lo que hay guardado. */
export default function PuestoBodega() {
  return (
    <div className="px-4 py-8 sm:px-8">
      <div className="mx-auto max-w-6xl">
        <header className="mb-6">
          <p className="text-sm font-semibold uppercase tracking-wider text-green-700">Puesto de trabajo</p>
          <h1 className="mt-1 text-3xl font-bold text-slate-900">Bodega</h1>
          <p className="mt-2 max-w-2xl text-slate-600">Busca un pallet, lote o material y registra el movimiento. Lo pendiente del turno está debajo.</p>
        </header>
        <nav aria-label="Secciones de Bodega" className="mb-6 flex gap-1 overflow-x-auto border-b border-slate-200">
          {PESTANAS.map(({ a, texto, exacta }) => (
            <NavLink
              key={texto}
              to={a}
              end={exacta}
              className={({ isActive }) =>
                `whitespace-nowrap border-b-2 px-4 py-3 text-sm font-medium transition-colors ${
                  isActive ? "border-green-700 text-green-800" : "border-transparent text-slate-600 hover:text-slate-800"
                }`
              }
            >
              {texto}
            </NavLink>
          ))}
        </nav>
        <Outlet />
      </div>
    </div>
  );
}
