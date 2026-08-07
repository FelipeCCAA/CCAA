import { NavLink, Outlet } from "react-router-dom";


/*
  Leche cruda: del predio al silo.

  Antes eran dos pantallas. **Recepción** apilaba en un solo scroll de 2.089 px
  —2,2 pantallas— cuatro indicadores, un tablero de seis pasos, diecinueve
  tarjetas de silo y, al final, la tabla con la que de verdad se trabaja: para
  tomar una muestra había que bajar dos pantallas, siempre. **Recolección** era
  una pantalla con un solo trabajo y el 60 % del alto vacío. Y las dos no se
  hablaban, aunque el modelo ya las une (`CargaModulo.recepcion_planta`).

  Ahora es una sección con pestañas, y el orden de las pestañas **es el viaje
  de la leche**: se recolecta en el predio, viaja, llega a planta, se muestrea,
  Calidad decide, se asigna silo y se descarga.

      Panel · Rutas · En camino
      Muestreo · Calidad · Silo y descarga · Silos · Historial

  El criterio que las separa no es «tipos de dato» sino **el trabajo de una
  persona**: quien muestrea abre Muestreo y ve una tabla y un botón; Calidad
  abre Calidad. Antes los cuatro roles veían exactamente lo mismo y cada uno
  tenía que encontrar su parte.

  Cada pestaña pide **solo sus estados** al servidor. No es una optimización:
  es lo que arregla los contadores, que se calculaban sobre la página cargada
  y por eso dejaban de decir la verdad pasadas cincuenta recepciones.
*/

const PESTANAS = [
  { a: "", texto: "Panel", exacta: true },
  { a: "rutas", texto: "Rutas" },
  { a: "en-camino", texto: "En camino" },
  { a: "muestreo", texto: "Muestreo" },
  { a: "calidad", texto: "Calidad" },
  { a: "descarga", texto: "Silo y descarga" },
  { a: "silos", texto: "Silos" },
  { a: "historial", texto: "Historial" },
];


function Leche() {

  return (
    <div className="px-8 py-8">

      <div className="mx-auto max-w-[1480px]">

        <header className="mb-6">

          <p className="text-sm font-semibold uppercase tracking-wider text-emerald-700">
            Operación · Leche cruda
          </p>

          <h1 className="mt-2 text-3xl font-bold text-slate-800">
            Recolección y recepción
          </h1>

          <p className="mt-2 max-w-3xl text-slate-500">
            Del predio al silo: rutas y controles en origen, llegada a planta,
            decisión de Calidad y descarga.
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
                    ? "border-emerald-700 text-emerald-800"
                    : "border-transparent text-slate-500 hover:text-slate-800"
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


export default Leche;
