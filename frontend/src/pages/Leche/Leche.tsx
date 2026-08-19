import { ArrowRight, Beaker, ChevronRight, FlaskConical, Truck, Warehouse } from "lucide-react";
import { Link, NavLink, Outlet } from "react-router-dom";


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

        <header className="mb-6 rounded-3xl bg-gradient-to-br from-emerald-950 via-emerald-900 to-teal-800 px-6 py-7 text-white shadow-sm sm:px-8">

          <p className="text-xs font-bold uppercase tracking-[0.18em] text-emerald-200">
            Flujo operativo · Leche cruda
          </p>

          <h1 className="mt-2 text-3xl font-bold tracking-tight text-white">
            Del camión a estandarización
          </h1>

          <p className="mt-2 max-w-3xl text-sm leading-6 text-emerald-100">
            Recepciona el camión, controla cada módulo, descarga en un silo y
            entrega la leche disponible directamente a Estandarización.
          </p>

          <div className="mt-6 grid gap-2 md:grid-cols-[1fr_auto_1fr_auto_1fr_auto_1fr] md:items-center">
            <Etapa icono={Truck} numero="1" titulo="Recepción" detalle="Datos del camión" />
            <ArrowRight className="hidden h-4 w-4 text-emerald-300 md:block" />
            <Etapa icono={Beaker} numero="2" titulo="Calidad" detalle="Camión + crioscopía por módulo" />
            <ArrowRight className="hidden h-4 w-4 text-emerald-300 md:block" />
            <Etapa icono={Warehouse} numero="3" titulo="Silo" detalle="Asignar y descargar" />
            <ArrowRight className="hidden h-4 w-4 text-emerald-300 md:block" />
            <Link to="/estandarizacion" className="group flex items-center gap-3 rounded-2xl border border-white/25 bg-white px-4 py-3 text-emerald-950 transition hover:bg-emerald-50">
              <FlaskConical className="h-5 w-5 text-emerald-700" />
              <span className="min-w-0 flex-1"><span className="block text-xs font-bold uppercase tracking-wide text-emerald-700">4 · Estandarización</span>{/* Sin el `/70`: la opacidad dejaba este texto en 4,36:1 sobre blanco,
                    por debajo del 4,5:1 exigido. El tono ya era correcto. */}
              <span className="block truncate text-xs text-emerald-900">Seleccionar silo disponible</span></span>
              <ChevronRight className="h-4 w-4 transition group-hover:translate-x-0.5" />
            </Link>
          </div>

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

function Etapa({ icono: Icono, numero, titulo, detalle }: { icono: typeof Truck; numero: string; titulo: string; detalle: string }) {
  return (
    <div className="flex items-center gap-3 rounded-2xl bg-white/10 px-4 py-3 ring-1 ring-white/10">
      <Icono className="h-5 w-5 text-emerald-200" />
      <span><span className="block text-xs font-bold uppercase tracking-wide text-emerald-200">{numero} · {titulo}</span><span className="block text-xs text-emerald-50/75">{detalle}</span></span>
    </div>
  );
}


export default Leche;
