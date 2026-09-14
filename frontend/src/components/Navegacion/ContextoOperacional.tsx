import { ChevronRight, MapPin } from "lucide-react";
import { Link, useLocation } from "react-router-dom";

import { contextoOperacionalPara } from "../../services/navegacion-operacional";
import { obtenerSesion } from "../../services/sesion";

export default function ContextoOperacional() {
  const ubicacion = useLocation();
  const usuario = obtenerSesion()?.usuario;
  if (!usuario) return null;

  const contexto = contextoOperacionalPara(
    usuario,
    ubicacion.pathname,
    ubicacion.search,
    ubicacion.hash,
  );
  const estaEnInicio = contexto.actual.ruta === contexto.inicio.ruta;

  return (
    <div className="sticky top-16 z-30 border-b border-slate-200 bg-white/95 px-4 py-2.5 backdrop-blur md:top-0 md:px-8">
      <div className="mx-auto flex max-w-7xl items-center gap-2 text-xs text-slate-600" aria-label="Ubicación operacional">
        <MapPin className="h-4 w-4 shrink-0 text-emerald-700" aria-hidden="true" />
        <span className="font-semibold text-slate-800">{contexto.area}</span>
        <ChevronRight className="h-3.5 w-3.5 shrink-0 text-slate-400" aria-hidden="true" />
        <span>{contexto.grupo}</span>
        {!estaEnInicio && (
          <>
            <ChevronRight className="h-3.5 w-3.5 shrink-0 text-slate-400" aria-hidden="true" />
            <span className="truncate font-medium text-slate-800">{contexto.actual.etiqueta}</span>
            <Link
              to={contexto.inicio.ruta}
              className="ml-auto shrink-0 rounded-lg px-2.5 py-1.5 font-semibold text-emerald-800 hover:bg-emerald-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-emerald-600"
            >
              Volver a mi área
            </Link>
          </>
        )}
      </div>
    </div>
  );
}
