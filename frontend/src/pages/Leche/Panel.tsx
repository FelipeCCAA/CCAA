import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import {
  AlertTriangle, ArrowDownToLine, Beaker, Droplets, Plus, ShieldCheck,
  Truck, Warehouse, type LucideIcon,
} from "lucide-react";

import {
  obtenerOcupacion, obtenerResumen, obtenerVehiculos,
  type Ocupacion, type ResumenRecepcion, type Vehiculo,
} from "../../services/recepcion.service";
import {
  obtenerCargasPendientes, type CargaEsperada,
} from "../../services/recoleccion.service";
import { puedeEscribir } from "../../services/sesion";
import FormularioRecepcion from "./FormularioRecepcion";

/*
  El turno de un vistazo.

  Sustituye a los dos tableros que la pantalla anterior mostraba uno encima del
  otro: cuatro indicadores y una tira de seis pasos, que partían el mismo dato
  de dos formas distintas y no coincidían —los pasos 4 y 5 eran la vista 3—.
  Aquí hay **una sola partición**, y cada casilla es un enlace a la pestaña
  donde se hace ese trabajo: un contador que no lleva a ninguna parte obliga a
  buscar a mano lo que acaba de anunciar.

  Los números vienen de `resumen/`, que **cuenta sobre el total**. Los de antes
  se calculaban sobre la página cargada: pasadas cincuenta recepciones dejaban
  de decir la verdad, y al filtrar la tabla mostraban ceros en el resto.

  Cada fuente carga por su cuenta. Con un `Promise.all` que las junte, un
  endpoint caído deja el panel entero en blanco; aquí lo que falla se calla y
  el resto sigue sirviendo.
*/

const formato = new Intl.NumberFormat("es-CL", { maximumFractionDigits: 0 });


function Paso({
  a, etiqueta, valor, detalle, icono: Icono, tono = "slate",
}: {
  a: string;
  etiqueta: string;
  valor: number | string;
  detalle: string;
  icono: LucideIcon;
  tono?: "slate" | "sky" | "violet" | "emerald" | "rose";
}) {
  const tonos = {
    slate: "bg-slate-100 text-slate-600",
    sky: "bg-sky-50 text-sky-700",
    violet: "bg-violet-50 text-violet-700",
    emerald: "bg-emerald-50 text-emerald-700",
    rose: "bg-rose-50 text-rose-700",
  };

  return (
    <Link
      to={a}
      className="block rounded-2xl border border-slate-200 bg-white p-5 transition hover:border-slate-300 hover:shadow-sm"
    >
      <div className="flex items-start justify-between gap-4">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.12em] text-slate-400">
            {etiqueta}
          </p>
          <p className="mt-2 text-2xl font-semibold tabular-nums text-slate-900">
            {valor}
          </p>
          <p className="mt-1 text-xs text-slate-500">{detalle}</p>
        </div>
        <span className={`rounded-xl p-2.5 ${tonos[tono]}`}>
          <Icono className="h-5 w-5" strokeWidth={1.8} />
        </span>
      </div>
    </Link>
  );
}


function Panel() {
  const [resumen, setResumen] = useState<ResumenRecepcion | null>(null);
  const [ocupacion, setOcupacion] = useState<Ocupacion | null>(null);
  const [enCamino, setEnCamino] = useState<CargaEsperada[]>([]);
  const [vehiculos, setVehiculos] = useState<Vehiculo[]>([]);
  const [formulario, setFormulario] = useState(false);

  const puedeEditar = puedeEscribir("recepcion");

  const cargar = () => {
    void obtenerResumen().then(setResumen).catch(() => setResumen(null));
    void obtenerOcupacion().then(setOcupacion).catch(() => setOcupacion(null));
    void obtenerCargasPendientes().then(setEnCamino).catch(() => setEnCamino([]));
  };

  useEffect(() => {
    const t = setTimeout(cargar, 0);
    void obtenerVehiculos().then(setVehiculos).catch(() => setVehiculos([]));

    return () => clearTimeout(t);
  }, []);

  const n = (estado: string) => resumen?.por_estado[estado] ?? 0;
  const descuadrados = (ocupacion?.silos ?? []).filter((s) => s.negativo || s.excedido);

  return (
    <div className="space-y-6">

      <div className="flex flex-wrap items-center justify-between gap-3">
        <h2 className="font-semibold text-slate-900">El turno ahora</h2>
        {puedeEditar && (
          <button
            type="button"
            onClick={() => setFormulario(true)}
            className="inline-flex h-11 items-center gap-2 rounded-xl bg-emerald-700 px-5 text-sm font-semibold text-white transition hover:bg-emerald-800"
          >
            <Plus className="h-4 w-4" />
            Registrar llegada
          </button>
        )}
      </div>

      {/* Un saldo de silo imposible se dice arriba y en rojo. Antes era una
          nota pequeña dentro de una tarjeta entre diecinueve, mientras el
          indicador de alertas contaba otra cosa y decía «1». */}
      {descuadrados.length > 0 && (
        <Link
          to="silos"
          className="flex items-start gap-3 rounded-2xl border border-rose-200 bg-rose-50 px-5 py-4 text-sm text-rose-800 transition hover:border-rose-300"
        >
          <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
          <span>
            <strong>
              {descuadrados.length}{" "}
              {descuadrados.length === 1 ? "silo descuadrado" : "silos descuadrados"}
            </strong>{" "}
            ({descuadrados.map((s) => s.codigo).join(", ")}). El volumen en
            planta que se muestre está mal mientras no cuadre el libro de
            movimientos.
          </span>
        </Link>
      )}

      {/* Una sola partición del flujo, y cada casilla lleva a su pestaña. */}
      <section className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <Paso
          a="en-camino" etiqueta="En camino" valor={enCamino.length}
          detalle={`${formato.format(enCamino.reduce((s, c) => s + Number(c.litros), 0))} L cerrados en predio`}
          icono={Truck}
        />
        <Paso
          a="muestreo" etiqueta="Por muestrear" valor={n("registrada")}
          detalle="Llegaron y esperan muestra" icono={Beaker} tono="sky"
        />
        <Paso
          a="calidad" etiqueta="Calidad decide" valor={n("muestreada") + n("retenida")}
          detalle={`${n("retenida")} retenida${n("retenida") === 1 ? "" : "s"}`}
          icono={ShieldCheck} tono={n("retenida") > 0 ? "rose" : "violet"}
        />
        <Paso
          a="descarga" etiqueta="Silo y descarga"
          valor={(resumen?.liberadas_sin_silo ?? 0) + (resumen?.liberadas_con_silo ?? 0)}
          detalle={`${resumen?.liberadas_sin_silo ?? 0} sin silo · ${resumen?.liberadas_con_silo ?? 0} listas`}
          icono={ArrowDownToLine} tono="emerald"
        />
      </section>

      <section className="grid grid-cols-1 gap-4 sm:grid-cols-2">
        <Paso
          a="silos" etiqueta="Volumen en planta"
          valor={`${formato.format(ocupacion?.litros_totales ?? 0)} L`}
          detalle={`${ocupacion?.silos.length ?? 0} silos y estanques`}
          icono={Droplets} tono="emerald"
        />
        <Paso
          a="historial" etiqueta="Ya en silo"
          valor={n("descargada") + n("cerrada")}
          detalle={`de ${resumen?.total ?? 0} recepciones registradas`}
          icono={Warehouse}
        />
      </section>

      {formulario && (
        <FormularioRecepcion
          vehiculos={vehiculos}
          alCerrar={() => setFormulario(false)}
          alGuardar={cargar}
        />
      )}

    </div>
  );
}


export default Panel;
