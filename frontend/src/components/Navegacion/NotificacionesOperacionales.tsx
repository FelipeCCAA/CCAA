import { useEffect, useState } from "react";
import { Bell, ChevronDown, ChevronRight } from "lucide-react";
import { Link } from "react-router-dom";

import {
  marcarNotificacionLeida,
  obtenerNotificacionesNoLeidas,
  type Notificacion,
} from "../../services/inventario.service";
import { rutaDeNotificacion } from "../../services/notificaciones-operacionales";

/*
  Antes esto pintaba hasta 4 tarjetas fijas debajo del menú, dentro del mismo
  `aside`: con el `nav` en `flex-1 overflow-y-auto`, esas tarjetas le quitaban
  la altura que les sobraba y en una pantalla de 1024×768 el menú de
  Producción podía quedar sin ningún enlace visible. Ahora es un control
  colapsable, cerrado por defecto: cuando no hay aviso abierto, solo ocupa una
  fila como cualquier otro enlace del menú.
*/
export default function NotificacionesOperacionales({ alNavegar }: {
  alNavegar: () => void;
}) {
  const [notificaciones, setNotificaciones] = useState<Notificacion[]>([]);
  const [abierto, setAbierto] = useState(false);

  useEffect(() => {
    let vigente = true;
    obtenerNotificacionesNoLeidas()
      .then((datos) => {
        if (vigente) setNotificaciones(datos);
      })
      .catch(() => {
        if (vigente) setNotificaciones([]);
      });
    return () => { vigente = false; };
  }, []);

  if (notificaciones.length === 0) return null;

  const atender = (notificacion: Notificacion) => {
    setNotificaciones((actuales) => actuales.filter((item) => item.id !== notificacion.id));
    void marcarNotificacionLeida(notificacion.id).catch(() => undefined);
    alNavegar();
  };

  return <section className="border-t border-slate-100 px-3 py-2">
    <button
      type="button"
      onClick={() => setAbierto((valor) => !valor)}
      aria-expanded={abierto}
      aria-controls="handoffs-lista"
      className="flex min-h-11 w-full items-center gap-2 rounded-xl px-2 text-left focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-emerald-600 hover:bg-amber-50"
    >
      <Bell className="h-4 w-4 shrink-0 text-amber-700" aria-hidden="true" />
      <span id="handoffs-titulo" className="flex-1 truncate text-[10px] font-bold uppercase tracking-[0.16em] text-slate-600">Trabajo recibido</span>
      <span className="rounded-full bg-amber-100 px-2 py-0.5 text-[10px] font-bold text-amber-900">{notificaciones.length}</span>
      <ChevronDown
        className={`h-4 w-4 shrink-0 text-slate-500 transition-transform ${abierto ? "rotate-180" : ""}`}
        aria-hidden="true"
      />
    </button>
    {abierto && (
      <div id="handoffs-lista" aria-labelledby="handoffs-titulo" className="mt-2 space-y-2">
        {notificaciones.slice(0, 4).map((notificacion) => <Link
          key={notificacion.id}
          to={rutaDeNotificacion(notificacion)}
          onClick={() => atender(notificacion)}
          className="group flex items-start gap-2 rounded-xl border border-amber-100 bg-amber-50/70 px-3 py-2.5 text-left focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-emerald-600"
        >
          <span className="min-w-0">
            <span className="block text-xs font-semibold text-slate-900">{notificacion.titulo}</span>
            <span className="mt-0.5 line-clamp-2 block text-[11px] leading-4 text-slate-600">{notificacion.mensaje}</span>
          </span>
          <ChevronRight className="mt-1 h-4 w-4 shrink-0 text-slate-400 group-hover:text-emerald-700" aria-hidden="true" />
        </Link>)}
        {notificaciones.length > 4 && <p className="mt-2 px-1 text-[11px] text-slate-500">+{notificaciones.length - 4} tareas adicionales en sus bandejas.</p>}
      </div>
    )}
  </section>;
}
