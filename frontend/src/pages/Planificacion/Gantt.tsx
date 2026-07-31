import { useState } from "react";
import { Trash2 } from "lucide-react";

import {
  colorDeBloque,
  COLOR_FAMILIA,
  ESTADO_EQUIPO,
  type Bloque,
} from "../../services/planificacion.service";

import type { Equipo } from "../../services/maestros.service";


/*
  Carta de programación de un día: equipos × horas.

  Se dibuja un día a la vez y no la semana entera. La grilla completa son 7
  días × 24 horas × 7 equipos, y comprimida a un ancho de pantalla los bloques
  de media hora quedan en dos píxeles: ilegible. Con un día por vista cada
  hora tiene sitio para su rótulo.

  El código de producción va SIEMPRE escrito dentro del bloque. No es
  decoración: el verificador de paleta marcó el verde de Colún en 2,74:1
  contra el fondo, por debajo del mínimo, y la etiqueta visible es la
  compensación que exige. Sin ella, la identidad quedaría solo en el color.
*/

interface Props {
  bloques: Bloque[];
  /* Del maestro, ya ordenados. Antes era una lista escrita en el código y
     agregar una máquina exigía desplegar. */
  equipos: Equipo[];
  dia: number;
  puedeEditar: boolean;
  /* Se pasa el id del equipo: es lo que guarda el bloque. */
  alCrear: (equipo: number, hora: number) => void;
  alBorrar: (bloque: Bloque) => void;
}


/* Se muestran las 24 horas: en planta se produce de noche. */
const HORAS = Array.from({ length: 24 }, (_, i) => i);


function Gantt({ bloques, equipos, dia, puedeEditar, alCrear, alBorrar }: Props) {

  const [encima, setEncima] = useState<number | null>(null);

  const delDia = bloques.filter((b) => b.dia === dia);

  return (
    <div className="overflow-x-auto">

      <div className="min-w-[900px]">

        {/* Regla de horas */}

        <div className="flex border-b border-slate-200">

          <div className="w-40 shrink-0 px-3 py-2 text-xs font-medium text-slate-400">
            Equipo
          </div>

          <div className="relative flex-1">

            <div className="flex">
              {HORAS.map((h) => (
                <div
                  key={h}
                  className="flex-1 border-l border-slate-100 py-2 text-center text-[10px] text-slate-400"
                >
                  {h}
                </div>
              ))}
            </div>

          </div>

        </div>

        {/* Una fila por equipo */}

        {equipos.map((equipo) => {

          const suyos = delDia.filter((b) => b.equipo === equipo.id);

          return (
            <div
              key={equipo.id}
              className="flex border-b border-slate-100 last:border-0"
            >

              <div className="w-40 shrink-0 px-3 py-3">

                <p className="text-sm text-slate-700">{equipo.nombre}</p>

                {/* Solo los evaporadores restan del balance: un mismo código
                    aparece también en la línea que lo recibe, y sumar ambos
                    contaría la leche dos veces. */}
                {equipo.consume_leche && (
                  <p className="text-[10px] text-slate-400">consume leche</p>
                )}

              </div>

              <div className="relative h-14 flex-1">

                {/* Rejilla de fondo, recesiva */}
                <div className="absolute inset-0 flex">
                  {HORAS.map((h) => (
                    <button
                      key={h}
                      type="button"
                      disabled={!puedeEditar}
                      onClick={() => alCrear(equipo.id, h)}
                      title={
                        puedeEditar
                          ? `Programar en ${equipo.nombre} a las ${h}:00`
                          : undefined
                      }
                      className="flex-1 border-l border-slate-100 disabled:cursor-default enabled:hover:bg-green-50/60"
                    />
                  ))}
                </div>

                {/* Los bloques, posicionados sobre la rejilla */}
                {suyos.map((bloque) => {

                  const inicio = Number(bloque.hora_inicio);
                  const fin = Number(bloque.hora_fin);
                  const color = colorDeBloque(bloque);
                  const esEstado = bloque.tipo === "estado";
                  const trama = esEstado && ESTADO_EQUIPO[bloque.estado_equipo]?.trama;

                  const etiqueta = esEstado
                    ? bloque.estado_equipo
                    : bloque.codigo_texto ?? "";

                  return (
                    <div
                      key={bloque.id}
                      onMouseEnter={() => setEncima(bloque.id)}
                      onMouseLeave={() => setEncima(null)}
                      className="group absolute top-2 bottom-2 flex items-center justify-center rounded px-1"
                      style={{
                        left: `${(inicio / 24) * 100}%`,
                        width: `${((fin - inicio) / 24) * 100}%`,
                        backgroundColor: color,
                        // Anillo de superficie: separa dos bloques contiguos
                        // sin necesidad de un hueco que falsee la duración.
                        boxShadow: "0 0 0 2px #fff",
                        backgroundImage: trama
                          ? "repeating-linear-gradient(45deg, rgba(255,255,255,.35) 0 3px, transparent 3px 7px)"
                          : undefined,
                      }}
                      title={`${etiqueta} · ${inicio}:00 a ${fin}:00${
                        bloque.cantidad_kg ? ` · ${bloque.cantidad_kg} kg` : ""
                      }${bloque.observacion ? ` · ${bloque.observacion}` : ""}`}
                    >

                      <span className="truncate text-[11px] font-semibold text-white">
                        {etiqueta}
                      </span>

                      {puedeEditar && encima === bloque.id && (
                        <button
                          type="button"
                          onClick={(e) => {
                            e.stopPropagation();
                            alBorrar(bloque);
                          }}
                          aria-label={`Quitar ${etiqueta}`}
                          className="absolute -top-2 -right-2 rounded-full bg-white p-0.5 text-slate-500 shadow hover:text-red-600"
                        >
                          <Trash2 className="h-3 w-3" />
                        </button>
                      )}

                    </div>
                  );
                })}

              </div>

            </div>
          );
        })}

      </div>

      {/* Leyenda: con dos o más categorías la identidad nunca queda solo en
          el color. */}

      <div className="mt-4 flex flex-wrap items-center gap-x-5 gap-y-2 border-t border-slate-100 pt-3">

        <span className="text-xs font-medium text-slate-500">Producción</span>

        {Object.entries(COLOR_FAMILIA).map(([familia, meta]) => (
          <span key={familia} className="flex items-center gap-1.5 text-xs text-slate-600">
            <span
              className="h-3 w-3 rounded-sm"
              style={{ backgroundColor: meta.color }}
            />
            {familia} · {meta.etiqueta}
          </span>
        ))}

        <span className="ml-2 text-xs font-medium text-slate-500">Equipo</span>

        {Object.entries(ESTADO_EQUIPO).map(([clave, meta]) => (
          <span key={clave} className="flex items-center gap-1.5 text-xs text-slate-600">
            <span
              className="h-3 w-3 rounded-sm"
              style={{
                backgroundColor: meta.color,
                backgroundImage: meta.trama
                  ? "repeating-linear-gradient(45deg, rgba(255,255,255,.35) 0 3px, transparent 3px 7px)"
                  : undefined,
              }}
            />
            {clave} · {meta.etiqueta}
          </span>
        ))}

      </div>

      {delDia.length === 0 && (
        <p className="mt-4 text-sm text-slate-500">
          {puedeEditar
            ? "Sin programar. Haz clic en una hora para agregar un bloque."
            : "Sin programar."}
        </p>
      )}

    </div>
  );
}


export default Gantt;
