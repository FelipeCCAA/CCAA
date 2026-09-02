import { useState } from "react";
import { AlertTriangle, CheckCircle2, RefreshCw } from "lucide-react";

import {
  obtenerDiagnosticoRutasProducto,
  type DiagnosticoRutasProducto,
} from "../../services/procesos.service";
import { mensajeErrorProceso } from "../../services/errores-proceso";

export default function DiagnosticoRutas() {
  const [diagnostico, setDiagnostico] = useState<DiagnosticoRutasProducto | null>(null);
  const [cargando, setCargando] = useState(false);
  const [error, setError] = useState("");

  const consultar = async () => {
    if (cargando) return;
    setCargando(true);
    setError("");
    try {
      setDiagnostico(await obtenerDiagnosticoRutasProducto());
    } catch (errorPeticion: unknown) {
      setError(mensajeErrorProceso(errorPeticion, "No se pudo verificar la configuración de rutas."));
    } finally {
      setCargando(false);
    }
  };

  const faltantes = diagnostico?.productos.filter((item) => !item.configurada) ?? [];

  return (
    <div className="mt-5 rounded-xl border border-slate-200 bg-slate-50 p-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <p className="font-semibold text-slate-900">Verificación previa de rutas</p>
          <p className="mt-1 text-sm text-slate-600">
            Detecta productos que quedarían bloqueados antes de abrir o transferir un lote.
          </p>
        </div>
        <button
          type="button"
          onClick={() => void consultar()}
          disabled={cargando}
          className="inline-flex items-center gap-2 rounded-xl border border-emerald-700 bg-white px-4 py-2 text-sm font-semibold text-emerald-800 disabled:opacity-60"
        >
          <RefreshCw className={`h-4 w-4 ${cargando ? "animate-spin" : ""}`} />
          {diagnostico ? "Volver a verificar" : "Verificar rutas"}
        </button>
      </div>

      {error && <p className="mt-3 rounded-lg bg-rose-50 px-3 py-2 text-sm text-rose-700">{error}</p>}
      {diagnostico?.completo && (
        <p className="mt-3 flex items-center gap-2 rounded-lg bg-emerald-50 px-3 py-2 text-sm font-medium text-emerald-800">
          <CheckCircle2 className="h-4 w-4" /> Todos los productos elaborables tienen una ruta activa.
        </p>
      )}
      {diagnostico && !diagnostico.completo && (
        <div className="mt-3 rounded-lg border border-amber-200 bg-amber-50 p-3 text-sm text-amber-900">
          <p className="flex items-center gap-2 font-semibold">
            <AlertTriangle className="h-4 w-4" /> {diagnostico.faltantes} producto(s) sin ruta activa
          </p>
          <ul className="mt-2 list-disc space-y-1 pl-5">
            {faltantes.map((item) => <li key={`${item.producto}-${item.sucursal}`}>{item.producto_nombre}</li>)}
          </ul>
          <p className="mt-2 text-xs">Administración debe completar la ruta antes de iniciar una operación nueva.</p>
        </div>
      )}
    </div>
  );
}
