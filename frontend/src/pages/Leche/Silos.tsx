import { useEffect, useState } from "react";
import { AlertTriangle, Warehouse } from "lucide-react";

import {
  obtenerOcupacion, type Ocupacion, type OcupacionSilo,
} from "../../services/recepcion.service";

/*
  Los silos como herramienta, no como decoración.

  Antes eran diecinueve tarjetas presentes en todo momento —cinco filas, el
  43 % de la página— con quince de ellas en 0 L, empujando hacia abajo la
  tabla con la que se trabaja. Y no se podía hacer nada con ellas.

  Dos cambios de criterio:

  1. **Los saldos imposibles van primero y aparte.** Un silo en negativo no es
     un dato bajo: es un registro descuadrado, físicamente imposible. Estaba
     como una nota pequeña dentro de la tarjeta catorce mientras el indicador
     de arriba decía «Requieren atención: 1» contando otra cosa. Cuatro silos
     rotos no pueden leerse como uno.
  2. **Los vacíos se agrupan al final.** Un silo en cero no aporta nada a
     quien busca dónde descargar; ocultar quince tarjetas idénticas deja ver
     las cuatro que importan.
*/

const formato = new Intl.NumberFormat("es-CL", { maximumFractionDigits: 0 });


function Barra({ silo }: { silo: OcupacionSilo }) {
  const ancho = Math.min(100, Math.max(0, silo.pct));
  const color = silo.negativo
    ? "bg-rose-500"
    : silo.excedido || silo.pct >= 85
      ? "bg-amber-500"
      : "bg-emerald-600";

  return (
    <article className="rounded-2xl border border-slate-200 bg-white p-5">

      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <span className="rounded-xl bg-slate-100 p-2 text-slate-600">
            <Warehouse className="h-4 w-4" strokeWidth={1.8} />
          </span>
          <p className="font-semibold text-slate-900">{silo.codigo}</p>
        </div>
        <span
          className={`text-sm font-semibold ${
            silo.negativo ? "text-rose-700" : silo.excedido ? "text-amber-700" : "text-slate-700"
          }`}
        >
          {silo.pct}%
        </span>
      </div>

      <div className="mt-3 flex flex-wrap gap-2 text-xs">
        <span className={`rounded-full px-2.5 py-1 font-medium ${silo.estado === "bloqueado_calidad" || silo.estado === "en_cip" || silo.estado === "fuera_servicio" ? "bg-rose-50 text-rose-700" : "bg-emerald-50 text-emerald-700"}`}>{silo.estado_etiqueta}</span>
        {silo.producto_actual && <span className="rounded-full bg-slate-100 px-2.5 py-1 text-slate-600">{silo.producto_actual}</span>}
        {silo.temperatura_actual != null && <span className="rounded-full bg-sky-50 px-2.5 py-1 text-sky-700">{silo.temperatura_actual} °C</span>}
      </div>

      <div className="mt-5 h-2 overflow-hidden rounded-full bg-slate-100">
        <div className={`h-full rounded-full transition-[width] ${color}`} style={{ width: `${ancho}%` }} />
      </div>

      <div className="mt-3 flex items-baseline justify-between gap-3">
        <p className="text-sm font-semibold text-slate-800">
          {formato.format(silo.litros)} L
        </p>
        <p className="text-xs text-slate-600">
          de {formato.format(silo.capacidad)} L
        </p>
      </div>

    </article>
  );
}


function Silos() {
  const [ocupacion, setOcupacion] = useState<Ocupacion | null>(null);
  const [error, setError] = useState("");
  const [verVacios, setVerVacios] = useState(false);

  useEffect(() => {
    const t = setTimeout(() => {
      void obtenerOcupacion()
        .then(setOcupacion)
        .catch(() => setError("No se pudo cargar la ocupación de los silos."));
    }, 0);

    return () => clearTimeout(t);
  }, []);

  if (error) {
    return (
      <p className="rounded-2xl border border-rose-200 bg-rose-50 px-5 py-4 text-sm text-rose-700">
        {error}
      </p>
    );
  }

  if (!ocupacion) {
    return <p className="py-10 text-center text-sm text-slate-600">Cargando…</p>;
  }

  const descuadrados = ocupacion.silos.filter((s) => s.negativo || s.excedido);
  const conLeche = ocupacion.silos.filter((s) => !s.negativo && !s.excedido && s.litros > 0);
  const vacios = ocupacion.silos.filter((s) => !s.negativo && !s.excedido && s.litros <= 0);

  const capacidadTotal = ocupacion.silos.reduce((suma, s) => suma + s.capacidad, 0);
  const pctTotal = capacidadTotal > 0
    ? Math.round((ocupacion.litros_totales / capacidadTotal) * 100)
    : 0;

  return (
    <div className="space-y-6">

      {/* El aviso que antes estaba escondido dentro de una tarjeta entre
          diecinueve. Un saldo negativo es imposible: significa que salió más
          leche de la que entró, y eso hay que mirarlo antes que nada. */}
      {descuadrados.length > 0 && (
        <section className="rounded-2xl border border-rose-200 bg-rose-50 px-6 py-5">
          <h2 className="flex items-center gap-2 text-sm font-semibold text-rose-900">
            <AlertTriangle className="h-4 w-4" />
            {descuadrados.length === 1
              ? "Un silo con registro descuadrado"
              : `${descuadrados.length} silos con registro descuadrado`}
          </h2>
          <p className="mt-1 text-sm text-rose-800">
            Un saldo negativo significa que salió más leche de la que entró; uno
            por encima de la capacidad, que el silo no daba para lo que se
            descargó. En los dos casos el libro de movimientos no cuadra y el
            volumen disponible que se muestre está mal.
          </p>
          <div className="mt-3 flex flex-wrap gap-2">
            {descuadrados.map((s) => (
              <span
                key={s.silo_id}
                className="rounded-full bg-white px-3 py-1 text-xs font-medium text-rose-900"
              >
                {s.codigo}: {formato.format(s.litros)} L de {formato.format(s.capacidad)}
              </span>
            ))}
          </div>
        </section>
      )}

      <section className="rounded-2xl border border-slate-200 bg-white px-6 py-5">
        <div className="flex flex-wrap items-end justify-between gap-4">
          <div>
            <p className="text-xs font-semibold uppercase tracking-wide text-slate-600">
              Volumen disponible
            </p>
            <p className="mt-1 text-3xl font-semibold tabular-nums text-slate-900">
              {formato.format(ocupacion.litros_totales)} L
            </p>
          </div>
          <p className="text-sm text-slate-600">
            {pctTotal}% de {formato.format(capacidadTotal)} L ·{" "}
            {ocupacion.silos.length} unidades
          </p>
        </div>
      </section>

      {conLeche.length > 0 && (
        <section>
          <h2 className="mb-3 font-semibold text-slate-900">Con leche</h2>
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
            {conLeche.map((s) => <Barra key={s.silo_id} silo={s} />)}
          </div>
        </section>
      )}

      <section>
        <button
          type="button"
          onClick={() => setVerVacios((v) => !v)}
          className="text-sm font-medium text-slate-600 underline"
        >
          {verVacios ? "Ocultar" : "Ver"} los {vacios.length} vacíos
        </button>

        {verVacios && (
          <div className="mt-3 grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
            {vacios.map((s) => <Barra key={s.silo_id} silo={s} />)}
          </div>
        )}
      </section>

    </div>
  );
}


export default Silos;
