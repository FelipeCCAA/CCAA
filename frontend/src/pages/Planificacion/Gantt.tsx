import { useRef, useState } from "react";
import { GripVertical, Trash2 } from "lucide-react";

import { colorDeBloque, DIAS, type Bloque } from "../../services/planificacion.service";
import type { Equipo } from "../../services/maestros.service";

interface Props {
  bloques: Bloque[];
  equipos: Equipo[];
  puedeEditar: boolean;
  alCrear: (equipo: number, dia: number, hora: number) => void;
  alBorrar: (bloque: Bloque) => void;
  alMover: (bloque: Bloque, inicioAbsoluto: number, finAbsoluto: number) => Promise<void>;
}

type Edicion = {
  bloque: Bloque; modo: "mover" | "inicio" | "fin"; x: number;
  inicio: number; fin: number; actualInicio: number; actualFin: number;
};

const TOTAL_HORAS = 168;
const PASO = 0.5;
const ANCHO_INTERVALO = 56;

function absoluto(bloque: Bloque, extremo: "inicio" | "fin") {
  const fecha = extremo === "inicio" ? bloque.fecha_hora_inicio : bloque.fecha_hora_fin;
  if (fecha && bloque.fecha_hora_inicio) {
    const base = new Date(bloque.fecha_hora_inicio);
    base.setHours(0, 0, 0, 0);
    base.setDate(base.getDate() - bloque.dia);
    return (new Date(fecha).getTime() - base.getTime()) / 3_600_000;
  }
  return bloque.dia * 24 + Number(extremo === "inicio" ? bloque.hora_inicio : bloque.hora_fin);
}

export default function Gantt({ bloques, equipos, puedeEditar, alCrear, alBorrar, alMover }: Props) {
  const [zoom, setZoom] = useState<1 | 2 | 4 | 8>(4);
  const [edicion, setEdicion] = useState<Edicion | null>(null);
  const scroller = useRef<HTMLDivElement>(null);
  const pxHora = ANCHO_INTERVALO / zoom;
  const ancho = TOTAL_HORAS * pxHora;

  const iniciar = (evento: React.PointerEvent, bloque: Bloque, modo: Edicion["modo"]) => {
    if (!puedeEditar) return;
    evento.preventDefault();
    evento.stopPropagation();
    evento.currentTarget.setPointerCapture(evento.pointerId);
    const inicio = absoluto(bloque, "inicio");
    const fin = absoluto(bloque, "fin");
    setEdicion({ bloque, modo, x: evento.clientX, inicio, fin, actualInicio: inicio, actualFin: fin });
  };

  const mover = (evento: React.PointerEvent) => {
    if (!edicion) return;
    const delta = Math.round(((evento.clientX - edicion.x) / pxHora) / PASO) * PASO;
    let inicio = edicion.inicio;
    let fin = edicion.fin;
    if (edicion.modo === "mover") {
      const duracion = fin - inicio;
      inicio = Math.max(0, Math.min(TOTAL_HORAS - duracion, inicio + delta));
      fin = inicio + duracion;
    } else if (edicion.modo === "inicio") {
      inicio = Math.max(0, Math.min(fin - PASO, inicio + delta));
    } else {
      fin = Math.min(TOTAL_HORAS, Math.max(inicio + PASO, fin + delta));
    }
    setEdicion({ ...edicion, actualInicio: inicio, actualFin: fin });
  };

  const terminar = async () => {
    if (!edicion) return;
    const pendiente = edicion;
    setEdicion(null);
    if (pendiente.actualInicio !== pendiente.inicio || pendiente.actualFin !== pendiente.fin) {
      await alMover(pendiente.bloque, pendiente.actualInicio, pendiente.actualFin);
    }
  };

  return <div onPointerMove={mover} onPointerUp={() => void terminar()} onPointerCancel={() => setEdicion(null)}>
    <div className="mb-3 flex flex-wrap items-center justify-between gap-3">
      <div className="flex flex-wrap gap-1">
        {DIAS.map((dia, indice) => <button key={dia} type="button" onClick={() => scroller.current?.scrollTo({ left: indice * 24 * pxHora, behavior: "smooth" })} className="rounded-lg px-2.5 py-1 text-xs text-slate-600 hover:bg-slate-100">{dia.slice(0, 3)}</button>)}
      </div>
      <div className="flex items-center gap-1" aria-label="Zoom temporal">
        <span className="mr-1 text-xs text-slate-600">Zoom</span>
        {([1, 2, 4, 8] as const).map((valor) => <button key={valor} type="button" onClick={() => setZoom(valor)} className={`rounded-lg px-2.5 py-1 text-xs font-semibold ${zoom === valor ? "bg-emerald-700 text-white" : "bg-slate-100 text-slate-600"}`}>{valor} h</button>)}
      </div>
    </div>

    <div ref={scroller} className="overflow-x-auto rounded-xl border border-slate-200">
      <div style={{ width: 160 + ancho }}>
        <div className="flex border-b border-slate-200 bg-white">
          <div className="sticky left-0 z-30 w-40 shrink-0 border-r border-slate-200 bg-white px-3 py-3 text-xs font-semibold text-slate-600">Recurso</div>
          <div style={{ width: ancho }}>
            <div className="flex">{DIAS.map((dia) => <div key={dia} style={{ width: 24 * pxHora }} className="border-l-2 border-slate-300 px-2 py-1 text-xs font-semibold text-slate-700">{dia}</div>)}</div>
            <div className="flex">{Array.from({ length: TOTAL_HORAS / zoom }, (_, indice) => { const hora = indice * zoom; return <div key={hora} style={{ width: ANCHO_INTERVALO }} className="border-l border-slate-200 py-1 text-center text-[10px] text-slate-600">{hora % 24}:00</div>; })}</div>
          </div>
        </div>

        {equipos.map((equipo) => <div key={equipo.id} className="flex border-b border-slate-100 last:border-0">
          <div className="sticky left-0 z-20 w-40 shrink-0 border-r border-slate-200 bg-white px-3 py-3"><p className="text-sm font-medium text-slate-700">{equipo.nombre}</p>{equipo.consume_leche && <p className="text-[10px] text-sky-700">consume leche</p>}</div>
          <div className="relative h-14" style={{ width: ancho }}>
            <div className="absolute inset-0 flex">{Array.from({ length: TOTAL_HORAS / zoom }, (_, indice) => { const inicio = indice * zoom; const noche = inicio % 24 >= 20 || inicio % 24 < 6; return <button key={inicio} type="button" disabled={!puedeEditar} onClick={() => alCrear(equipo.id, Math.floor(inicio / 24), inicio % 24)} style={{ width: ANCHO_INTERVALO }} className={`border-l border-slate-100 ${noche ? "bg-slate-50" : ""} enabled:hover:bg-emerald-50`} aria-label={`Programar ${equipo.nombre} ${DIAS[Math.floor(inicio / 24)]} ${inicio % 24}:00`} />; })}</div>
            {bloques.filter((bloque) => bloque.equipo === equipo.id).map((bloque) => {
              const activa = edicion?.bloque.id === bloque.id;
              const inicio = activa ? edicion.actualInicio : absoluto(bloque, "inicio");
              const fin = activa ? edicion.actualFin : absoluto(bloque, "fin");
              const etiqueta = bloque.tipo_actividad_nombre || bloque.codigo_texto || bloque.estado_equipo;
              return <div key={bloque.id} className="absolute top-2 bottom-2 flex select-none items-center justify-center rounded text-white shadow-sm" style={{ left: inicio * pxHora, width: Math.max(8, (fin - inicio) * pxHora), backgroundColor: bloque.color || colorDeBloque(bloque), touchAction: "none" }} title={`${etiqueta} · ${bloque.horas.toLocaleString("es-CL")} h`}>
                {puedeEditar && <button type="button" onPointerDown={(e) => iniciar(e, bloque, "inicio")} className="absolute inset-y-0 left-0 w-2 cursor-ew-resize rounded-l bg-black/15" aria-label="Cambiar inicio" />}
                <button type="button" disabled={!puedeEditar} onPointerDown={(e) => iniciar(e, bloque, "mover")} className="flex h-full min-w-0 flex-1 cursor-grab items-center justify-center gap-1 px-2 active:cursor-grabbing"><GripVertical className="h-3 w-3 shrink-0 opacity-70" /><span className="truncate text-[11px] font-semibold">{etiqueta}</span></button>
                {puedeEditar && <button type="button" onPointerDown={(e) => iniciar(e, bloque, "fin")} className="absolute inset-y-0 right-0 w-2 cursor-ew-resize rounded-r bg-black/15" aria-label="Cambiar término" />}
                {puedeEditar && <button type="button" onClick={(e) => { e.stopPropagation(); alBorrar(bloque); }} className="absolute -right-2 -top-2 rounded-full bg-white p-0.5 text-slate-600 shadow hover:text-red-600" aria-label={`Eliminar ${etiqueta}`}><Trash2 className="h-3 w-3" /></button>}
              </div>;
            })}
          </div>
        </div>)}
      </div>
    </div>
    <p className="mt-3 text-xs text-slate-600">Arrastra el centro para mover; usa los bordes para cambiar duración. Los cambios se ajustan a 30 minutos y recalculan el balance en el servidor.</p>
  </div>;
}
