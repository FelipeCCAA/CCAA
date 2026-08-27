import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { AlertTriangle, Beaker, FlaskConical, GitBranch, Truck, Warehouse } from "lucide-react";

import {
  obtenerDespachosLeche, obtenerOcupacion, reversarDespachoLeche, type DespachoLeche, type Ocupacion, type OcupacionSilo,
} from "../../services/recepcion.service";
import AnalisisSiloPanel from "./AnalisisSilo";
import FormularioDespachoLeche from "./FormularioDespachoLeche";

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


function AccionSilo({
  texto, icono: Icono, destino, bloqueado, onClick,
}: {
  texto: string;
  icono: typeof Beaker;
  destino?: string;
  bloqueado?: string;
  onClick?: () => void;
}) {
  const clase = "flex items-center justify-center gap-2 rounded-xl border px-4 py-3 text-sm font-semibold";
  if (bloqueado) {
    return <button type="button" disabled title={bloqueado} className={`${clase} cursor-not-allowed border-slate-200 bg-slate-100 text-slate-400`}><Icono className="h-4 w-4" />{texto}</button>;
  }
  if (destino) {
    return <Link to={destino} className={`${clase} border-emerald-200 bg-emerald-50 text-emerald-800`}><Icono className="h-4 w-4" />{texto}</Link>;
  }
  return <button type="button" onClick={onClick} className={`${clase} border-emerald-200 bg-emerald-50 text-emerald-800`}><Icono className="h-4 w-4" />{texto}</button>;
}


function Barra({
  silo, activo, onSelect,
}: {
  silo: OcupacionSilo;
  activo: boolean;
  onSelect: (silo: OcupacionSilo) => void;
}) {
  const ancho = Math.min(100, Math.max(0, silo.pct));
  const color = silo.negativo
    ? "bg-rose-500"
    : silo.excedido || silo.pct >= 85
      ? "bg-amber-500"
      : "bg-emerald-600";

  return (
    <button
      type="button"
      onClick={() => onSelect(silo)}
      aria-pressed={activo}
      className={`w-full rounded-2xl border bg-white p-5 text-left ${
        activo ? "border-slate-900 ring-1 ring-slate-900" : "border-slate-200"
      }`}
    >

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
        <span className="rounded-full bg-blue-50 px-2.5 py-1 font-medium text-blue-800">{silo.tipo_etiqueta}</span>
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

    </button>
  );
}


interface SilosProps {
  soloPrincipales?: boolean;
}

function Silos({ soloPrincipales = false }: SilosProps) {
  const [ocupacion, setOcupacion] = useState<Ocupacion | null>(null);
  const [error, setError] = useState("");
  const [verVacios, setVerVacios] = useState(false);
  // El análisis se pide aparte de la ocupación, y no en el mismo
  // `Promise.all`: si su endpoint cae, la pantalla de silos sigue
  // sirviendo para lo que sirve hoy.
  const [seleccionado, setSeleccionado] = useState<OcupacionSilo | null>(null);
  const [despachando, setDespachando] = useState(false);
  const [despachos, setDespachos] = useState<DespachoLeche[] | null>(null);

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

  const silos = soloPrincipales ? ocupacion.silos.slice(0, 8) : ocupacion.silos;
  const descuadrados = silos.filter((s) => s.negativo || s.excedido);
  const conLeche = silos.filter((s) => !s.negativo && !s.excedido && s.litros > 0);
  const vacios = silos.filter((s) => !s.negativo && !s.excedido && s.litros <= 0);
  const silosConLeche = conLeche.filter((s) => s.tipo === "silo");
  const tanquesProceso = silos.filter((s) => !s.negativo && !s.excedido && s.tipo !== "silo");
  const faltaTkCrema = !silos.some((s) => s.tipo === "tk_crema");

  const capacidadTotal = silos.reduce((suma, s) => suma + s.capacidad, 0);
  const pctTotal = capacidadTotal > 0
    ? Math.round((ocupacion.litros_totales / capacidadTotal) * 100)
    : 0;

  return (
    <div className="space-y-6">

      {soloPrincipales && (
        <header>
          <p className="text-xs font-semibold uppercase tracking-wider text-emerald-700">Recepción de leche</p>
          <h1 className="mt-1 text-3xl font-bold text-slate-900">Silos principales</h1>
          <p className="mt-2 text-sm text-slate-600">Vista rápida de los ocho silos de recepción. Selecciona uno para operar su flujo.</p>
        </header>
      )}

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
            {silos.length} de {ocupacion.silos.length} unidades
          </p>
        </div>
      </section>

      <section className="grid gap-3 rounded-2xl border border-slate-200 bg-slate-50 p-4 text-sm text-slate-700 md:grid-cols-4">
        <div><b>1. Silo de leche</b><br /><span className="text-slate-600">Recepción, muestra vigente y saldo disponible.</span></div>
        <div><b>2. Descremación</b><br /><span className="text-slate-600">Silo entero → TK descremada + estanque de crema.</span></div>
        <div><b>3. Estandarización</b><br /><span className="text-slate-600">Mezcla controlada → silo estandarizado.</span></div>
        <div><b>4. Producción</b><br /><span className="text-slate-600">Vale liberado → lote → Calidad → pallet.</span></div>
      </section>

      {seleccionado && (
        <>
          {despachando && <FormularioDespachoLeche siloId={seleccionado.silo_id} siloCodigo={seleccionado.codigo} disponible={seleccionado.litros} onCerrar={() => setDespachando(false)} onCreado={async () => { const nueva = await obtenerOcupacion(); setOcupacion(nueva); setSeleccionado(nueva.silos.find((item) => item.silo_id === seleccionado.silo_id) ?? null); setDespachos(null); setDespachando(false); }} />}
          <section className="rounded-2xl border border-slate-200 bg-white p-5">
            <div className="flex flex-wrap items-start justify-between gap-4">
              <div>
                <p className="text-xs font-semibold uppercase tracking-wide text-emerald-700">Operar {seleccionado.codigo} · {seleccionado.tipo_etiqueta}</p>
                <h2 className="mt-1 text-xl font-semibold text-slate-900">
                  {formato.format(seleccionado.litros)} L disponibles
                </h2>
                <p className="mt-1 text-sm text-slate-600">
                  {seleccionado.grasa ?? "—"}% MG · {seleccionado.sng ?? "—"}% SNG ·{" "}
                  {seleccionado.antiguedad_horas == null ? "sin antigüedad" : `${seleccionado.antiguedad_horas} h desde la leche más antigua`}
                </p>
                <p className={`mt-2 text-xs ${seleccionado.analisis_vigente ? "text-emerald-700" : "text-amber-700"}`}>
                  {seleccionado.analisis_vigente ? "Análisis vigente" : seleccionado.motivo_vigencia}
                </p>
              </div>
              <p className="rounded-full bg-slate-100 px-3 py-1 text-xs text-slate-600">
                Último aseo: {seleccionado.ultima_limpieza ?? "sin registro"}
              </p>
            </div>
            {seleccionado.motivos_no_disponible.length > 0 && (
              <div className="mt-4 rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-xs text-amber-800">
                {seleccionado.motivos_no_disponible.join(" · ")}
              </div>
            )}
            {seleccionado.tipo === "tk_ld" && (
              <div className="mt-4 rounded-xl border border-blue-200 bg-blue-50 px-4 py-3 text-xs text-blue-800">
                Este es el <strong>TK de leche descremada</strong>: se usa como insumo de la estandarización. No es el silo de entrada para una nueva descremación.
              </div>
            )}
            <div className="mt-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
              <AccionSilo texto="Tomar muestra" icono={Beaker} onClick={() => document.getElementById("analisis-silo")?.scrollIntoView({ behavior: "smooth" })} />
              <AccionSilo texto="Estandarizar" icono={FlaskConical} destino={`/estandarizacion?silo=${seleccionado.silo_id}`} bloqueado={seleccionado.motivos_no_disponible[0]} />
              {seleccionado.tipo === "silo" && <AccionSilo texto="Descremar" icono={GitBranch} destino={`/procesos?accion=descremar&silo=${seleccionado.silo_id}`} bloqueado={seleccionado.motivos_no_disponible[0]} />}
              <AccionSilo texto="Despachar" icono={Truck} onClick={() => setDespachando(true)} bloqueado={seleccionado.motivos_no_disponible[0]} />
            </div>
            <div className="mt-4">
              <button type="button" onClick={() => void obtenerDespachosLeche(seleccionado.silo_id).then(setDespachos).catch(() => setError("No se pudo cargar el historial de despachos."))} className="text-sm font-medium text-emerald-700 underline">Ver historial de despachos</button>
              {despachos && <div className="mt-3 space-y-2">{despachos.length === 0 ? <p className="text-sm text-slate-600">Sin despachos registrados.</p> : despachos.slice(0, 8).map((despacho) => <div key={despacho.id} className="rounded-xl bg-slate-50 px-3 py-2 text-xs text-slate-700"><span className="font-semibold">{despacho.guia_despacho}</span> · {Number(despacho.litros).toLocaleString("es-CL")} L · {despacho.destino}{despacho.anulado_en ? <span className="ml-2 text-amber-700">Reversado: {despacho.motivo_anulacion}</span> : <button type="button" onClick={() => { const motivo = window.prompt(`Motivo para reversar ${despacho.guia_despacho}:`); if (!motivo) return; void reversarDespachoLeche(despacho.id, motivo).then(async () => { const nueva = await obtenerOcupacion(); setOcupacion(nueva); setSeleccionado(nueva.silos.find((item) => item.silo_id === seleccionado.silo_id) ?? null); setDespachos(await obtenerDespachosLeche(seleccionado.silo_id)); }).catch(() => setError("No se pudo reversar el despacho.")); }} className="ml-3 font-semibold text-rose-700 underline">Reversar</button>}</div>)}</div>}
            </div>
          </section>
          <div id="analisis-silo">
            <AnalisisSiloPanel
              key={seleccionado.silo_id}
              siloId={seleccionado.silo_id}
              siloCodigo={seleccionado.codigo}
            />
          </div>
        </>
      )}

      {silosConLeche.length > 0 && (
        <section>
          <h2 className="mb-3 font-semibold text-slate-900">Silos de recepción con leche</h2>
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
            {silosConLeche.map((s) => (
              <Barra
                key={s.silo_id}
                silo={s}
                activo={seleccionado?.silo_id === s.silo_id}
                onSelect={(elegido) => {
                  setDespachos(null);
                  setSeleccionado((actual) =>
                    actual?.silo_id === elegido.silo_id ? null : elegido,
                  );
                }}
              />
            ))}
          </div>
        </section>
      )}

      {(tanquesProceso.length > 0 || faltaTkCrema) && (
        <section>
          <h2 className="mb-3 font-semibold text-slate-900">TK y estanques de proceso</h2>
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
            {tanquesProceso.map((s) => (
              <Barra key={s.silo_id} silo={s} activo={seleccionado?.silo_id === s.silo_id} onSelect={(elegido) => {
                setDespachos(null);
                setSeleccionado((actual) => actual?.silo_id === elegido.silo_id ? null : elegido);
              }} />
            ))}
            {faltaTkCrema && (
              <div className="rounded-2xl border border-dashed border-amber-300 bg-amber-50 p-5">
                <p className="font-semibold text-amber-900">TK de crema pendiente</p>
                <p className="mt-2 text-sm text-amber-800">La descremación necesita un estanque de crema. Falta cargarlo en Maestros antes de cerrar una corrida real.</p>
              </div>
            )}
          </div>
        </section>
      )}

      <section>
        <button
          type="button"
          onClick={() => setVerVacios((v) => !v)}
          className="text-sm font-medium text-slate-600 underline"
        >
          {verVacios ? "Ocultar" : "Ver"} los {vacios.filter((s) => s.tipo === "silo").length} silos vacíos
        </button>

        {verVacios && (
          <div className="mt-3 grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
            {vacios.filter((s) => s.tipo === "silo").map((s) => (
              <Barra
                key={s.silo_id}
                silo={s}
                activo={seleccionado?.silo_id === s.silo_id}
                onSelect={(elegido) => {
                  setDespachos(null);
                  setSeleccionado((actual) =>
                    actual?.silo_id === elegido.silo_id ? null : elegido,
                  );
                }}
              />
            ))}
          </div>
        )}
      </section>

    </div>
  );
}


export default Silos;
