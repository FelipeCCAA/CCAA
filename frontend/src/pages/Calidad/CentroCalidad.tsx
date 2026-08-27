import { Link } from "react-router-dom";
import { ClipboardCheck, FlaskConical, ShieldAlert, Sparkles } from "lucide-react";

import { buscarExpedientes, type FilaExpediente } from "../../services/calidad.service";
import { decidirInspeccion, obtenerInspecciones } from "../../services/inventario.service";
import { obtenerAseos } from "../../services/aseos.service";
import { obtenerSesion } from "../../services/sesion";
import { Aviso, Estado, Indicador, Tarjeta, Vacio } from "../../components/seccion/componentes";
import { useCarga } from "../../components/seccion/utilidades";

const INSPECCIONES_CERRADAS = ["aprobada", "observada", "rechazada", "bloqueada"];
const LIBERACIONES_CERRADAS = ["liberado", "liberado_concesion", "rechazado"];

function CentroCalidad() {
  // Tres lecturas independientes y acotadas: el centro carga únicamente lo
  // que Calidad necesita, no todas las tablas de Inventario ni el histórico
  // completo de Producción.
  const expedientes = useCarga(async () => (await buscarExpedientes({ pagina: 1 })).resultados);
  const inspecciones = useCarga(obtenerInspecciones);
  const aseos = useCarga(obtenerAseos);
  const sesion = obtenerSesion();
  const puedeDecidir = ["calidad", "admin"].includes(sesion?.usuario.rol ?? "")
    || sesion?.usuario.perfil?.area === "calidad";

  const lotes = (expedientes.datos ?? []) as FilaExpediente[];
  const porRevisar = lotes.filter((fila) => !LIBERACIONES_CERRADAS.includes(fila.liberacion?.estado ?? "pendiente"));
  const liberados = lotes.filter((fila) => fila.liberacion?.estado === "liberado" || fila.liberacion?.estado === "liberado_concesion");
  const rechazados = lotes.filter((fila) => fila.liberacion?.estado === "rechazado");
  const materiales = inspecciones.datos ?? [];
  const materialesPendientes = materiales.filter((item) => !INSPECCIONES_CERRADAS.includes(item.estado));
  const aseosPendientes = (aseos.datos ?? []).filter((aseo) => aseo.verificacion !== "conforme");

  const decidirMaterial = async (id: number, estado: "aprobada" | "rechazada") => {
    await decidirInspeccion(id, estado, estado === "rechazada" ? "Rechazado por Calidad" : "Liberado por Calidad");
    await inspecciones.recargar();
  };

  return (
    <div className="mx-auto max-w-7xl space-y-7 px-8 py-10">
      <header>
        <p className="text-sm font-semibold uppercase tracking-wider text-emerald-700">Calidad</p>
        <h1 className="mt-2 text-3xl font-bold text-slate-800">Centro de calidad</h1>
        <p className="mt-2 max-w-3xl text-slate-600">Una sola bandeja para verificar la producción, liberar materiales de embalaje y revisar los aseos que respaldan cada fase.</p>
      </header>

      <section className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <Indicador etiqueta="Lotes por revisar" valor={porRevisar.length} Icono={FlaskConical} tono={porRevisar.length ? "alerta" : "normal"} />
        <Indicador etiqueta="Materiales en cuarentena" valor={materialesPendientes.length} Icono={ShieldAlert} tono={materialesPendientes.length ? "alerta" : "normal"} />
        <Indicador etiqueta="Lotes liberados" valor={liberados.length} Icono={ClipboardCheck} />
        <Indicador etiqueta="Aseos por verificar" valor={aseosPendientes.length} Icono={Sparkles} tono={aseosPendientes.length ? "alerta" : "normal"} />
      </section>

      <section className="grid items-start gap-7 xl:grid-cols-3">
      <Tarjeta titulo="Productos que requieren aprobación" descripcion="Cada lote toma automáticamente su checklist por familia y fase. Abre el expediente para analizar, verificar y liberar o rechazar.">
        {expedientes.error ? <Aviso>No se pudo cargar la cola de productos.</Aviso> : porRevisar.length === 0 ? <Vacio>No hay lotes pendientes de Calidad.</Vacio> : (
          <div className="space-y-3">
            {porRevisar.map((fila) => (
              <Link key={fila.lote.id} to={`/liberacion?lote=${fila.lote.id}`} className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-slate-200 px-4 py-3 hover:bg-slate-50">
                <div>
                  <p className="font-medium text-slate-800">{fila.lote.producto_nombre} · {fila.lote.codigo_lote}</p>
                  <p className="text-sm text-slate-600">Análisis: {fila.calidad?.etiqueta ?? "sin análisis"} · Checklist: {fila.avance.completados}/{fila.avance.total}</p>
                  {fila.bloqueos.length > 0 && <p className="mt-1 text-xs text-amber-700">{fila.bloqueos[0]}</p>}
                </div>
                <Estado valor={fila.liberacion?.estado ?? "pendiente"} />
              </Link>
            ))}
          </div>
        )}
      </Tarjeta>

      <Tarjeta titulo="Insumos por confirmar para Bodega" descripcion="Bolsas, etiquetas e insumos en cuarentena. Al liberarlos quedan disponibles para Producción; al rechazarlos van a la ubicación de rechazados.">
        {inspecciones.error ? <Aviso>No se pudo cargar la cuarentena.</Aviso> : materialesPendientes.length === 0 ? <Vacio>No hay materiales esperando decisión.</Vacio> : (
          <div className="space-y-3">
            {materialesPendientes.map((item) => (
              <div key={item.id} className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-amber-200 bg-amber-50/40 px-4 py-3">
                <div><p className="font-medium text-slate-800">{item.insumo_nombre} · lote {item.lote_codigo}</p><p className="text-sm text-slate-600">Estado: {item.estado}</p></div>
                {puedeDecidir && <div className="flex gap-2"><button onClick={() => void decidirMaterial(item.id, "aprobada")} className="rounded-lg bg-emerald-700 px-3 py-1.5 text-xs font-semibold text-white">Liberar</button><button onClick={() => void decidirMaterial(item.id, "rechazada")} className="rounded-lg bg-red-50 px-3 py-1.5 text-xs font-semibold text-red-700">Rechazar</button></div>}
              </div>
            ))}
          </div>
        )}
      </Tarjeta>

        <Tarjeta titulo="Aseos que requieren verificación" descripcion="No bloquean la operación por ahora, pero advierten antes de usar el silo o la máquina asociada.">
          {aseos.error ? <Aviso>No se pudieron cargar los aseos.</Aviso> : aseosPendientes.length === 0 ? <Vacio>Sin aseos pendientes de verificación.</Vacio> : <div className="space-y-2">{aseosPendientes.slice(0, 12).map((aseo) => <Link key={aseo.id} to="/inocuidad/aseos" className="flex items-center justify-between rounded-xl bg-slate-50 px-4 py-3 text-sm hover:bg-slate-100"><span>{aseo.objetivo_nombre} · {aseo.tipo_aseo_etiqueta}</span><Estado valor={aseo.verificacion} /></Link>)}</div>}
        </Tarjeta>
      </section>

      <Tarjeta titulo="Historial de Calidad" descripcion="Liberados y rechazados quedan visibles para trazabilidad; Bodega no puede modificar estas decisiones.">
        {liberados.length + rechazados.length === 0 ? <Vacio>Sin decisiones recientes.</Vacio> : <div className="grid gap-2 md:grid-cols-2">{[...liberados, ...rechazados].slice(0, 12).map((fila) => <div key={fila.lote.id} className="flex items-center justify-between rounded-xl bg-slate-50 px-4 py-3 text-sm"><span>{fila.lote.producto_nombre} · {fila.lote.codigo_lote}</span><Estado valor={fila.liberacion?.estado ?? "pendiente"} /></div>)}</div>}
      </Tarjeta>
    </div>
  );
}

export default CentroCalidad;
