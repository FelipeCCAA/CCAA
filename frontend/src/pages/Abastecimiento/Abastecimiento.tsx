import { NavLink, Outlet } from "react-router-dom";


/*
  Abastecimiento y Bodega.

  Antes era **una** página con trece secciones apiladas en un solo scroll:
  formularios y tablas intercalados, sin filtros, y un `Promise.all` con diez
  endpoints que dejaba la pantalla en blanco si uno fallaba. Encontrar algo
  exigía recordar a qué altura estaba.

  Ahora es una sección con pestañas, y el orden de las pestañas **es el ciclo
  del material**: se compra, llega, Calidad lo libera, entra a stock, se pide
  desde planta y se consume. Esa es la forma en que la gente piensa el
  problema, y por eso ordena mejor que agrupar por tabla.

      Panel · Materiales · Stock · Bodegas
      Compras · Proveedores · Recepción · Calidad · Pedidos · MRP

  Cada pestaña carga lo suyo (ver `useCarga`). En este módulo los permisos son
  **por área** —Bodega, Compras, Calidad—, así que a cualquiera le van a
  fallar cosas de un área que no es la suya de forma perfectamente normal; con
  una carga común, eso vaciaba la pantalla entera.
*/

const PESTANAS = [
  { a: "", texto: "Panel", exacta: true },
  { a: "materiales", texto: "Materiales" },
  { a: "stock", texto: "Stock" },
  { a: "producto-terminado", texto: "Producto terminado" },
  { a: "bodegas", texto: "Bodegas" },
  { a: "compras", texto: "Compras" },
  { a: "proveedores", texto: "Proveedores" },
  { a: "recepcion", texto: "Recepción" },
  { a: "calidad", texto: "Calidad" },
  { a: "pedidos", texto: "Pedidos" },
  { a: "mrp", texto: "MRP" },
];


function Abastecimiento() {

  return (
    <div className="px-8 py-10">

      <div className="mx-auto max-w-7xl">

        <header className="mb-6">

          <p className="text-sm font-semibold uppercase tracking-wider text-green-700">
            Cadena de suministro
          </p>

          <h1 className="mt-2 text-3xl font-bold text-slate-800">
            Abastecimiento y Bodega
          </h1>

          <p className="mt-2 max-w-3xl text-slate-600">
            Del pedido al consumo: compras, recepción, liberación de Calidad,
            stock por lote y ubicación, y el material que baja a producción.
          </p>

        </header>

        <nav className="mb-8 flex gap-1 overflow-x-auto border-b border-slate-200">

          {PESTANAS.map(({ a, texto, exacta }) => (
            <NavLink
              key={texto}
              to={a}
              end={exacta}
              className={({ isActive }) =>
                `whitespace-nowrap border-b-2 px-4 py-3 text-sm font-medium transition-colors ${
                  isActive
                    ? "border-green-700 text-green-800"
                    : "border-transparent text-slate-600 hover:text-slate-800"
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


export default Abastecimiento;
