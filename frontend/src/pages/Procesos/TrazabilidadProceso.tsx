import { useState } from "react";
import {
  ArrowRight,
  Beaker,
  Clock3,
  Factory,
  GitBranch,
  MapPin,
  Search,
  Truck,
} from "lucide-react";

import { ErrorState } from "../../components/ui/PageState";
import {
  obtenerGenealogia,
  type Genealogia,
  type TipoReferenciaTrazabilidad,
} from "../../services/procesos.service";
import { mensajeErrorProceso } from "../../services/errores-proceso";
import ArbolGenealogia from "./ArbolGenealogia";

export default function TrazabilidadProceso() {
  const [referencia, setReferencia] = useState("");
  const [tipoReferencia, setTipoReferencia] =
    useState<TipoReferenciaTrazabilidad>("lote");
  const [direccion, setDireccion] = useState<"atras" | "adelante">("atras");
  const [genealogia, setGenealogia] = useState<Genealogia | null>(null);
  const [error, setError] = useState("");

  const buscar = async (evento: React.FormEvent) => {
    evento.preventDefault();
    if (!referencia.trim()) {
      setError("Escribe la referencia que quieres rastrear.");
      return;
    }

    setError("");
    try {
      setGenealogia(
        await obtenerGenealogia(referencia, direccion, tipoReferencia),
      );
    } catch (errorConsulta) {
      setGenealogia(null);
      setError(
        mensajeErrorProceso(
          errorConsulta,
          `No existe la referencia «${referencia.trim()}» o no tiene una relación productiva trazable.`,
        ),
      );
    }
  };

  return (
    <>
      {error && <ErrorState mensaje={error} />}
    <section id="trazabilidad" className="scroll-mt-24 rounded-2xl border border-slate-200 bg-white p-6">
      <div className="flex items-center gap-3"><GitBranch className="h-5 w-5 text-green-700" /><div><h2 className="text-lg font-semibold">Trazabilidad visual</h2><p className="mt-1 text-xs text-slate-600">Carga el detalle solamente al seleccionar un lote, una corrida/ejecución o una salida.</p></div></div>
      <form onSubmit={buscar} className="mt-5 flex flex-col gap-3 sm:flex-row">
        <select aria-label="Tipo de referencia" value={tipoReferencia} onChange={(e) => setTipoReferencia(e.target.value as TipoReferenciaTrazabilidad)} className="rounded-xl border border-slate-300 bg-white px-4 py-2.5"><option value="lote">Lote o pallet</option><option value="ejecucion">Corrida / ejecución</option><option value="salida">Salida de proceso</option></select>
        <input aria-label="Referencia de trazabilidad" value={referencia} onChange={(e) => setReferencia(e.target.value)} placeholder={tipoReferencia === "lote" ? "Código de lote o pallet" : tipoReferencia === "ejecucion" ? "Código o ID de corrida" : "ID de salida"} className="flex-1 rounded-xl border border-slate-300 px-4 py-2.5" />
        <select value={direccion} onChange={(e) => setDireccion(e.target.value as "atras" | "adelante")} className="rounded-xl border border-slate-300 bg-white px-4 py-2.5"><option value="atras">Hacia atrás</option><option value="adelante">Hacia adelante</option></select>
        <button className="inline-flex items-center justify-center gap-2 rounded-xl bg-green-700 px-5 py-2.5 font-semibold text-white"><Search className="h-4 w-4" />Buscar</button>
      </form>
      {genealogia && (
        <div className="mt-5 grid gap-3 sm:grid-cols-3">
          <div className="rounded-xl border border-emerald-200 bg-emerald-50 p-4"><p className="text-xs font-semibold uppercase tracking-wide text-emerald-700">Referencia</p><p className="mt-1 font-bold text-emerald-950">{genealogia.foco.codigo}</p><p className="mt-1 text-xs text-emerald-800">{genealogia.foco.tipo.replaceAll("_", " ")}</p></div>
          <div className="rounded-xl border border-sky-200 bg-sky-50 p-4"><p className="flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wide text-sky-700"><MapPin className="h-3.5 w-3.5" />Ubicación actual</p><p className="mt-1 font-bold text-sky-950">{genealogia.ubicacion_actual.codigo}</p><p className="mt-1 text-xs text-sky-800">{genealogia.ubicacion_actual.detalle || "Última ubicación registrada"}</p></div>
          <div className="rounded-xl border border-violet-200 bg-violet-50 p-4"><p className="text-xs font-semibold uppercase tracking-wide text-violet-700">Genealogía</p><p className="mt-1 font-bold text-violet-950">{genealogia.nodos.length} lote(s)</p><p className="mt-1 text-xs text-violet-800">{genealogia.enlaces.length} transformación(es) cuantificadas</p></div>
        </div>
      )}
      {genealogia?.flujo && (
        <div className="mt-6">
          <h3 className="text-sm font-semibold uppercase tracking-wide text-slate-600">
            Línea completa del lote
          </h3>
          <div className="mt-3 grid items-stretch gap-3 lg:grid-cols-[1fr_auto_1fr_auto_1fr]">
            <div className="rounded-xl border border-slate-200 p-4">
              <div className="flex items-center gap-2 font-semibold text-slate-800">
                <Truck className="h-4 w-4 text-green-700" /> {genealogia.flujo.origenes_externos.length ? "Recepción externa" : "Recepción"}
              </div>
              {genealogia.flujo.origenes_externos.length ? <ul className="mt-2 space-y-2 text-xs text-slate-600">{genealogia.flujo.origenes_externos.map((item) => <li key={item.lote_id}><b>{item.material}</b><br />Lote {item.lote_codigo} · {Number(item.cantidad).toLocaleString("es-CL")} {item.unidad}{item.proveedor ? ` · ${item.proveedor}` : ""}</li>)}</ul> : <><p className="mt-2 text-sm text-slate-600">
                {genealogia.flujo.recepciones.length} origen(es) de recepción
              </p>
              <ul className="mt-2 max-h-48 space-y-1 overflow-y-auto text-xs text-slate-600">
                {genealogia.flujo.recepciones.map((item) => (
                  <li key={`${item.id}-${item.silo_codigo}`}>
                    {item.fecha} · guía {item.guia || "—"} · {item.silo_codigo}
                    {item.litros_atribuidos !== null && ` · ${Number(item.litros_atribuidos).toLocaleString("es-CL")} L atribuidos`}
                    {` · ${item.trazabilidad === "confirmada" ? "Confirmado FIFO" : "Inferido"}`}
                  </li>
                ))}
              </ul>
              <p className="mt-2 text-xs text-slate-600">{genealogia.flujo.nota_recepciones}</p>
              {Number(genealogia.flujo.litros_no_atribuibles) > 0 && (
                <p className="mt-2 text-xs font-semibold text-amber-700">
                  {Number(genealogia.flujo.litros_no_atribuibles).toLocaleString("es-CL")} L sin recepción histórica atribuible
                </p>
              )}</>}
            </div>
            <ArrowRight className="m-auto hidden h-5 w-5 text-slate-300 lg:block" />
            <div className="rounded-xl border border-green-200 bg-green-50/50 p-4">
              <div className="flex items-center gap-2 font-semibold text-slate-800">
                <Beaker className="h-4 w-4 text-green-700" /> {genealogia.flujo.estandarizacion ? "Estandarización" : "Calidad de origen"}
              </div>
              {genealogia.flujo.estandarizacion ? <><p className="mt-2 text-sm font-medium">{genealogia.flujo.estandarizacion.vale_codigo}</p>
              <p className="mt-1 text-xs text-slate-600">
                {genealogia.flujo.estandarizacion.silos_origen.map((item) => item.codigo).join(" + ")}
                {" → "}{genealogia.flujo.estandarizacion.silo_destino}
              </p>
              <p className="mt-2 text-xs text-slate-600">
                Proceso {genealogia.flujo.estandarizacion.ejecucion_codigo || "sin ID"}
              </p></> : <><p className="mt-2 text-sm font-medium">{genealogia.flujo.origenes_externos[0]?.estado_calidad || "Sin origen externo"}</p><p className="mt-2 text-xs text-slate-600">Solo un lote vigente y liberado puede alimentar la torre.</p></>}
            </div>
            <ArrowRight className="m-auto hidden h-5 w-5 text-slate-300 lg:block" />
            <div className="rounded-xl border border-slate-200 p-4">
              <div className="flex items-center gap-2 font-semibold text-slate-800">
                <Factory className="h-4 w-4 text-green-700" /> Producción
              </div>
              <p className="mt-2 text-sm font-medium">{genealogia.flujo.produccion.lote_codigo}</p>
              <p className="mt-1 text-xs text-slate-600">
                {genealogia.flujo.produccion.producto} · {genealogia.flujo.produccion.linea || "sin línea"} · {genealogia.flujo.produccion.equipo || "sin máquina"}
              </p>
              <p className="mt-2 text-xs text-slate-600">
                Proceso {genealogia.flujo.produccion.ejecucion_codigo || "sin ID"}
              </p>
            </div>
          </div>
          {genealogia.flujo.cadena_procesos.length > 0 && (
            <div className="mt-4 rounded-xl border border-violet-200 bg-violet-50/40 p-4">
              <p className="text-sm font-semibold text-violet-950">Transformaciones relacionadas</p>
              <div className="mt-3 flex gap-2 overflow-x-auto pb-2">
                {genealogia.flujo.cadena_procesos.map((ejecucion, indice) => (
                  <div key={ejecucion.id} className="flex shrink-0 items-center gap-2">
                    {indice > 0 && <ArrowRight className="h-4 w-4 text-violet-300" />}
                    <article className="w-56 rounded-lg border border-violet-200 bg-white p-3 text-xs">
                      <p className="font-bold text-slate-900">{ejecucion.etapa}</p>
                      <p className="mt-1 text-violet-700">{ejecucion.codigo}</p>
                      <p className="mt-1 text-slate-500">{ejecucion.equipo || "Sin equipo"} · {ejecucion.estado}</p>
                      {ejecucion.salidas.map((salida) => (
                        <p key={salida.id} className="mt-2 rounded bg-slate-50 px-2 py-1 text-slate-600">
                          {Number(salida.cantidad).toLocaleString("es-CL")} {salida.unidad} · {salida.clase} → {salida.destino}
                        </p>
                      ))}
                    </article>
                  </div>
                ))}
              </div>
            </div>
          )}
          <div className="mt-3 grid gap-3 lg:grid-cols-2">
            <div className="rounded-xl border border-sky-200 bg-sky-50/60 p-4">
              <p className="text-sm font-semibold text-sky-900">Calidad · {genealogia.flujo.calidad.estado}</p>
              <p className="mt-1 text-xs text-sky-700">{genealogia.flujo.calidad.autorizada_por ? `Firmado por ${genealogia.flujo.calidad.autorizada_por}` : "Sin firma de liberación"}</p>
            </div>
            <div className="rounded-xl border border-amber-200 bg-amber-50/60 p-4">
              <p className="text-sm font-semibold text-amber-900">Envase, inventario y despacho</p>
              {genealogia.flujo.pallets.length === 0 ? <p className="mt-1 text-xs text-amber-700">Sin pallets registrados.</p> : <ul className="mt-2 space-y-1 text-xs text-amber-800">{genealogia.flujo.pallets.map((p) => <li key={p.id}>{p.codigo} · {p.kg_neto} kg · {p.ubicacion ? `ubicación ${p.ubicacion}` : p.estado}{p.cliente ? ` · cliente ${p.cliente} (${p.despacho})` : ""}</li>)}</ul>}
            </div>
          </div>
        </div>
      )}
      {genealogia && <div className="mt-5"><ArbolGenealogia genealogia={genealogia} direccion={direccion} /></div>}
      {genealogia && (
        <div className="mt-6 border-t border-slate-200 pt-5">
          <div className="flex items-center gap-2"><Clock3 className="h-4 w-4 text-slate-600" /><h3 className="font-semibold text-slate-900">Línea temporal operacional</h3></div>
          {genealogia.timeline.length === 0 ? <p className="mt-3 rounded-xl bg-slate-50 px-4 py-6 text-center text-sm text-slate-600">No existen hechos con fecha registrados para esta cadena.</p> : <ol className="mt-4 space-y-3 border-l-2 border-slate-200 pl-5">{genealogia.timeline.map((hecho, indice) => <li key={`${hecho.fecha_hora}-${hecho.categoria}-${indice}`} className="relative rounded-xl border border-slate-200 p-4"><span className="absolute -left-[1.68rem] top-5 h-3 w-3 rounded-full border-2 border-white bg-emerald-600" /><div className="flex flex-wrap items-start justify-between gap-2"><div><p className="font-semibold text-slate-900">{hecho.titulo}</p><p className="mt-1 text-xs text-slate-600">{hecho.detalle}</p></div><time className="text-xs font-medium text-slate-500">{new Date(hecho.fecha_hora).toLocaleString("es-CL")}</time></div><div className="mt-2 flex flex-wrap gap-2 text-xs text-slate-600">{hecho.cantidad !== null && hecho.unidad && <span className="rounded-full bg-emerald-50 px-2 py-1 font-semibold text-emerald-800">{Number(hecho.cantidad).toLocaleString("es-CL")} {hecho.unidad}</span>}{hecho.equipo && <span>Equipo: {hecho.equipo}</span>}{hecho.responsable && <span>Responsable: {hecho.responsable}</span>}{hecho.estado && <span>Estado: {hecho.estado.replaceAll("_", " ")}</span>}</div></li>)}</ol>}
        </div>
      )}
    </section>
    </>
  );
}
