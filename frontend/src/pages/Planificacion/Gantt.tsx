import { useRef, useState } from "react";
import { Trash2 } from "lucide-react";

import {
  colorDeBloque,
  COLOR_FAMILIA,
  DIAS,
  ESTADO_EQUIPO,
  type Bloque,
} from "../../services/planificacion.service";

import type { Equipo } from "../../services/maestros.service";


/*
  Carta de programación de la **semana completa**: equipos × 168 horas.

  Antes se dibujaba un día a la vez, y el motivo era real: la semana entera
  comprimida al ancho de la pantalla dejaba los bloques de media hora en dos
  píxeles. La salida no era volver al día, sino **dejar de comprimir**: cada
  hora ocupa un ancho fijo y la grilla se desplaza en horizontal.

  Lo que arregla, y es la razón por la que se pidió: **en planta se trabaja de
  noche y hay corridas que cruzan la medianoche**. Con una vista por día, esa
  corrida se veía partida en dos pantallas distintas y no había forma de mirar
  el turno completo. Aquí la noche del lunes al martes son dos bloques
  contiguos que se leen de corrido, con la franja nocturna sombreada detrás.

  La columna de equipos queda fija al desplazar: sin ella, a la altura del
  jueves ya no se sabe qué máquina es cada fila.

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
  puedeEditar: boolean;
  /* Se pasa el id del equipo: es lo que guarda el bloque. */
  alCrear: (equipo: number, dia: number, hora: number) => void;
  alBorrar: (bloque: Bloque) => void;
}

const HORAS_DIA = 24;
const DIAS_SEMANA = 7;
const TOTAL_HORAS = HORAS_DIA * DIAS_SEMANA;

/*
  Ancho fijo por hora, en píxeles. Es la decisión que hace legible la semana:
  con un porcentaje del ancho disponible, media hora medía dos píxeles. A 30
  px/hora, media hora son quince — se ve y se puede apuntar con el ratón.
*/
const PX_HORA = 30;

/* La franja de noche que se sombrea. En planta el turno de noche es lo que
   obligó a mirar la semana de corrido, así que se marca. */
const NOCHE_DESDE = 20;
const NOCHE_HASTA = 6;

const esNoche = (hora: number) => hora >= NOCHE_DESDE || hora < NOCHE_HASTA;


function Gantt({ bloques, equipos, puedeEditar, alCrear, alBorrar }: Props) {

  const [encima, setEncima] = useState<number | null>(null);
  const scroller = useRef<HTMLDivElement>(null);

  const irAlDia = (dia: number) => {
    scroller.current?.scrollTo({
      left: dia * HORAS_DIA * PX_HORA,
      behavior: "smooth",
    });
  };

  return (
    <div>

      {/* Saltar a un día: la semana entera son 5.040 px, y buscar el jueves
          arrastrando es peor que pedirlo. No cambia de vista — mueve la que
          hay, así que el contexto de los días vecinos no se pierde. */}
      <div className="mb-3 flex flex-wrap items-center gap-1">
        <span className="mr-1 text-xs text-slate-400">Ir a</span>
        {DIAS.map((nombre, i) => (
          <button
            key={nombre}
            type="button"
            onClick={() => irAlDia(i)}
            className="rounded-lg px-2.5 py-1 text-xs text-slate-500 hover:bg-slate-100 hover:text-slate-800"
          >
            {nombre.slice(0, 3)}
          </button>
        ))}
      </div>

      <div ref={scroller} className="overflow-x-auto">

        <div style={{ width: 160 + TOTAL_HORAS * PX_HORA }}>

          {/* Cabecera: los días y, debajo, las horas */}

          <div className="flex border-b border-slate-200">

            <div className="sticky left-0 z-20 w-40 shrink-0 bg-white px-3 py-2 text-xs font-medium text-slate-400">
              Equipo
            </div>

            <div>

              <div className="flex">
                {DIAS.map((nombre) => (
                  <div
                    key={nombre}
                    style={{ width: HORAS_DIA * PX_HORA }}
                    className="border-l-2 border-slate-300 px-2 py-1.5 text-xs font-semibold text-slate-600"
                  >
                    {nombre}
                  </div>
                ))}
              </div>

              <div className="flex">
                {Array.from({ length: TOTAL_HORAS }, (_, i) => {
                  const hora = i % HORAS_DIA;

                  return (
                    <div
                      key={i}
                      style={{ width: PX_HORA }}
                      className={`py-1 text-center text-[10px] ${
                        hora === 0 ? "border-l-2 border-slate-300" : "border-l border-slate-100"
                      } ${esNoche(hora) ? "text-slate-400" : "text-slate-500"}`}
                    >
                      {hora}
                    </div>
                  );
                })}
              </div>

            </div>

          </div>

          {/* Una fila por equipo */}

          {equipos.map((equipo) => {

            const suyos = bloques.filter((b) => b.equipo === equipo.id);

            return (
              <div
                key={equipo.id}
                className="flex border-b border-slate-100 last:border-0"
              >

                <div className="sticky left-0 z-20 w-40 shrink-0 border-r border-slate-200 bg-white px-3 py-3">

                  <p className="text-sm text-slate-700">{equipo.nombre}</p>

                  {/* Solo los evaporadores restan del balance: un mismo código
                      aparece también en la línea que lo recibe, y sumar ambos
                      contaría la leche dos veces. */}
                  {equipo.consume_leche && (
                    <p className="text-[10px] text-slate-400">consume leche</p>
                  )}

                </div>

                {/* El ancho va explícito: los hijos de esta fila son la
                    rejilla y los bloques, y los dos están posicionados en
                    absoluto —no aportan ancho—. Sin esto la fila medía lo que
                    la pantalla y la grilla no se desplazaba. */}
                <div
                  className="relative h-14"
                  style={{ width: TOTAL_HORAS * PX_HORA }}
                >

                  {/* Rejilla de fondo, recesiva. La noche va sombreada: es lo
                      que permite ver de un vistazo qué corridas cruzan la
                      medianoche. */}
                  <div className="absolute inset-0 flex">
                    {Array.from({ length: TOTAL_HORAS }, (_, i) => {
                      const dia = Math.floor(i / HORAS_DIA);
                      const hora = i % HORAS_DIA;

                      return (
                        <button
                          key={i}
                          type="button"
                          disabled={!puedeEditar}
                          onClick={() => alCrear(equipo.id, dia, hora)}
                          title={
                            puedeEditar
                              ? `Programar en ${equipo.nombre} · ${DIAS[dia]} a las ${hora}:00`
                              : undefined
                          }
                          style={{ width: PX_HORA }}
                          className={`${
                            hora === 0 ? "border-l-2 border-slate-300" : "border-l border-slate-100"
                          } ${esNoche(hora) ? "bg-slate-50/80" : ""} disabled:cursor-default enabled:hover:bg-green-50`}
                        />
                      );
                    })}
                  </div>

                  {/* Los bloques, posicionados sobre la línea de tiempo
                      completa: la hora absoluta es día × 24 + hora. */}
                  {suyos.map((bloque) => {

                    const inicio = bloque.dia * HORAS_DIA + Number(bloque.hora_inicio);
                    const fin = bloque.dia * HORAS_DIA + Number(bloque.hora_fin);
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
                          left: inicio * PX_HORA,
                          width: (fin - inicio) * PX_HORA,
                          backgroundColor: color,
                          // Anillo de superficie: separa dos bloques contiguos
                          // sin necesidad de un hueco que falsee la duración.
                          boxShadow: "0 0 0 2px #fff",
                          backgroundImage: trama
                            ? "repeating-linear-gradient(45deg, rgba(255,255,255,.35) 0 3px, transparent 3px 7px)"
                            : undefined,
                        }}
                        title={`${DIAS[bloque.dia]} · ${etiqueta} · ${bloque.hora_inicio} a ${bloque.hora_fin}${
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

        <span className="ml-2 flex items-center gap-1.5 text-xs text-slate-600">
          <span className="h-3 w-3 rounded-sm bg-slate-100" />
          Noche ({NOCHE_DESDE}:00–{NOCHE_HASTA}:00)
        </span>

      </div>

      {bloques.length === 0 && (
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
