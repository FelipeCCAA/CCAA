import { useEffect, useState } from "react";
import { Bell, ChevronRight } from "lucide-react";
import { Link } from "react-router-dom";

import {
  marcarNotificacionLeida,
  obtenerNotificaciones,
  type Notificacion,
} from "../../services/inventario.service";
import { rutaDeNotificacion } from "../../services/notificaciones-operacionales";

export default function NotificacionesOperacionales({ alNavegar }: {
  alNavegar: () => void;
}) {
  const [notificaciones, setNotificaciones] = useState<Notificacion[]>([]);

  useEffect(() => {
    let vigente = true;
    obtenerNotificaciones()
      .then((datos) => {
        if (vigente) setNotificaciones(datos.filter((item) => !item.leida_en));
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

  return <section className="border-t border-slate-100 px-3 py-4" aria-labelledby="handoffs-titulo">
    <div className="mb-2 flex items-center gap-2">
      <Bell className="h-4 w-4 text-amber-700" aria-hidden="true" />
      <p id="handoffs-titulo" className="text-[10px] font-bold uppercase tracking-[0.16em] text-slate-600">Trabajo recibido</p>
      <span className="ml-auto rounded-full bg-amber-100 px-2 py-0.5 text-[10px] font-bold text-amber-900">{notificaciones.length}</span>
    </div>
    <div className="space-y-2">
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
    </div>
    {notificaciones.length > 4 && <p className="mt-2 px-1 text-[11px] text-slate-500">+{notificaciones.length - 4} tareas adicionales en sus bandejas.</p>}
  </section>;
}
