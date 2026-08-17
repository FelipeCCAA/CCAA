import { useEffect, useState } from "react";
import { Timer } from "lucide-react";

/*
  Cuánto lleva agitando y cuánto falta para cumplir el mínimo del
  procedimiento.

  **Cuenta desde los minutos que informó el servidor, no desde
  `agitacion_desde` contra el reloj del navegador.** Los dos relojes no
  coinciden —el del PC de planta se ha visto corrido varios minutos— y el que
  manda es el del servidor, que es el que calcula si ya agitó lo suficiente.
  Con el reloj local, la pantalla habilitaría el formulario antes de tiempo y
  el operador tomaría una muestra que el servidor va a marcar con aviso, o
  —peor— quedaría esperando de más creyendo que el sistema falla.

  Aquí solo se le suman los segundos transcurridos **desde que llegó la
  respuesta**, que sí es un intervalo local y no una hora absoluta.

  El contador se reinicia **remontando el componente**: quien lo usa le pasa
  `key={minutos_agitando}`, así que cada dato nuevo del servidor lo arranca de
  cero. Es la forma idiomática de reponer estado en React —reiniciarlo desde un
  efecto encadena renders— y además deja el reinicio a la vista de quien lee el
  llamado, en vez de escondido dentro.
*/
function Cronometro({
  minutosAlCargar,
  minutosExigidos,
}: {
  minutosAlCargar: number | null;
  minutosExigidos: number | null;
}) {
  const [segundos, setSegundos] = useState(0);

  useEffect(() => {
    const tic = setInterval(() => setSegundos((v) => v + 1), 1000);

    return () => clearInterval(tic);
  }, []);

  if (minutosAlCargar === null) {
    return null;
  }

  const minutos = minutosAlCargar + segundos / 60;

  // Sin el dato del backend no se afirma nada: mostrar un mínimo inventado
  // sería exactamente la copia que este componente existe para evitar.
  if (minutosExigidos === null) {
    return (
      <Marco tono="slate">
        Agitando hace {minutos.toFixed(0)} min. No se pudo leer el mínimo del
        procedimiento; muestrear antes solo deja aviso.
      </Marco>
    );
  }

  const faltan = Math.max(0, minutosExigidos - minutos);

  if (faltan <= 0) {
    return (
      <Marco tono="emerald">
        Agitando hace {minutos.toFixed(0)} min — cumplidos los{" "}
        {minutosExigidos} del procedimiento.
      </Marco>
    );
  }

  const porcentaje = Math.min(100, (minutos / minutosExigidos) * 100);

  return (
    <Marco tono="indigo">
      <span className="font-medium">
        Faltan {Math.ceil(faltan)} min de agitación
      </span>{" "}
      — antes de los {minutosExigidos} la mezcla no es homogénea y la muestra
      puede no medir el silo. Se puede muestrear igual; queda registrado.
      <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-white/60">
        <div
          className="h-full rounded-full bg-indigo-500 transition-all"
          style={{ width: `${porcentaje}%` }}
        />
      </div>
    </Marco>
  );
}


const TONOS = {
  slate: "border-slate-200 bg-slate-50 text-slate-600",
  indigo: "border-indigo-200 bg-indigo-50 text-indigo-800",
  emerald: "border-emerald-200 bg-emerald-50 text-emerald-800",
};


function Marco({
  tono,
  children,
}: {
  tono: keyof typeof TONOS;
  children: React.ReactNode;
}) {
  return (
    <div className={`rounded-xl border px-4 py-3 text-sm ${TONOS[tono]}`}>
      <div className="flex items-start gap-2">
        <Timer className="mt-0.5 h-4 w-4 shrink-0" />
        <div className="flex-1">{children}</div>
      </div>
    </div>
  );
}


export default Cronometro;
