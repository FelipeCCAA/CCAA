import { useMemo, useState } from "react";
import { isAxiosError } from "axios";

import { registrarEnvase, type SolicitudEnvase } from "../../services/produccion.service";
import { mensajeErrorProceso } from "../../services/errores-proceso";
import { obtenerSesion } from "../../services/sesion";
import { clavePedidoPendiente } from "../Envasado/pendientes";

const campo = "w-full rounded-xl border border-slate-300 bg-white px-3 py-2 text-sm";
const fechaLocal = (fecha: Date) => {
  const desplazada = new Date(fecha.getTime() - fecha.getTimezoneOffset() * 60_000);
  return desplazada.toISOString().slice(0, 16);
};

export default function FormularioEnvase({
  loteId,
  formatoId,
  formatoKg,
  formatoNombre,
  maximoUnidadLogisticaKg,
  tipoUnidadLogistica,
  cantidadDisponible,
  materiales,
  equipos,
  alGuardar,
}: {
  loteId: number;
  formatoId: number;
  formatoKg: number;
  formatoNombre: string;
  maximoUnidadLogisticaKg: number;
  tipoUnidadLogistica: "pallet" | "big_bag";
  cantidadDisponible: number;
  materiales: Array<{
    codigo: string;
    nombre: string;
    unidad: string;
    cantidad_por_kg: string;
    stock_disponible: string;
  }>;
  equipos: Array<{ id: number; codigo: string; nombre: string }>;
  alGuardar: () => void;
}) {
  const [equipo, setEquipo] = useState("");
  const [codigo, setCodigo] = useState("");
  const maximoUnidades = Math.floor(
    Math.min(maximoUnidadLogisticaKg, cantidadDisponible) / formatoKg,
  );
  const [unidades, setUnidades] = useState(String(maximoUnidades));
  const [inicio, setInicio] = useState(() => fechaLocal(new Date(Date.now() - 60 * 60_000)));
  const [termino, setTermino] = useState(() => fechaLocal(new Date()));
  const [observacion, setObservacion] = useState("");
  const [sellado, setSellado] = useState("conforme");
  const [rotulado, setRotulado] = useState("conforme");
  const [integridad, setIntegridad] = useState("conforme");
  const [mensaje, setMensaje] = useState("");
  const [guardando, setGuardando] = useState(false);
  const actorId = obtenerSesion()?.usuario.id;
  const clavePendiente = actorId === undefined ? null : clavePedidoPendiente(actorId, loteId);
  const [pendiente, setPendiente] = useState<SolicitudEnvase | null>(() => {
    try {
      const guardado = clavePendiente ? sessionStorage.getItem(clavePendiente) : null;
      if (!guardado) return null;
      const pedido = JSON.parse(guardado) as SolicitudEnvase;
      return pedido.lote === loteId && pedido.operacion_id && pedido.pallets_datos?.length
        ? pedido : null;
    } catch { return null; }
  });
  const [operacionId, setOperacionId] = useState(() => pendiente?.operacion_id ?? crypto.randomUUID());
  const kg = useMemo(() => Number(unidades || 0) * formatoKg, [formatoKg, unidades]);
  const valido = Boolean(
    equipo && codigo.trim() && Number(unidades) > 0 && kg <= maximoUnidadLogisticaKg
    && kg <= cantidadDisponible
    && inicio && termino && new Date(termino) > new Date(inicio),
  );

  async function enviar(datos: SolicitudEnvase, reintento = false) {
    setGuardando(true); setMensaje("");
    setPendiente(datos);
    try { if (clavePendiente) sessionStorage.setItem(clavePendiente, JSON.stringify(datos)); } catch { /* Almacenamiento no disponible. */ }
    try {
      const registro = await registrarEnvase(datos);
      try { if (clavePendiente) sessionStorage.removeItem(clavePendiente); } catch { /* Almacenamiento no disponible. */ }
      setPendiente(null);
      const nombreUnidad = tipoUnidadLogistica === "big_bag" ? "Big Bag" : "Pallet";
      const pallet = datos.pallets_datos[0];
      const estado = registro.pallets.every((item) => item.estado === "pendiente_calidad")
        ? "Quedó en cuarentena de Calidad." : "Consulta el estado actual en el historial.";
      setMensaje(`${nombreUnidad} ${pallet.codigo} confirmado: ${pallet.unidades} unidad(es), ${pallet.kg_neto} kg. ${estado}`);
      setOperacionId(crypto.randomUUID());
      const saldoSiguiente = Math.max(cantidadDisponible - pallet.kg_neto, 0);
      const maximoSiguiente = Math.floor(
        Math.min(maximoUnidadLogisticaKg, saldoSiguiente) / formatoKg,
      );
      setCodigo(""); setUnidades(String(maximoSiguiente)); setObservacion(""); alGuardar();
    } catch (error) {
      if (!reintento && isAxiosError(error) && error.response && error.response.status < 500) {
        // El primer intento recibió una respuesta concluyente y se puede corregir.
        try { if (clavePendiente) sessionStorage.removeItem(clavePendiente); } catch { /* Almacenamiento no disponible. */ }
        setPendiente(null);
        setOperacionId(crypto.randomUUID());
        setMensaje(mensajeErrorProceso(error, "No se pudo registrar el pallet."));
      } else {
        // Un rechazo posterior no resuelve si el intento anterior quedó guardado.
        setMensaje(reintento && isAxiosError(error) && error.response
          ? `El reintento fue rechazado: ${mensajeErrorProceso(error, "revisa el historial")}. El cierre anterior podría existir. Consulta el historial o pide buscar la operación ${datos.operacion_id} antes de crear otra.`
          : "No se pudo confirmar el cierre. Reintenta el mismo registro; sus datos quedaron guardados en esta sesión.");
      }
    } finally { setGuardando(false); }
  }

  function guardar(evento: React.FormEvent) {
    evento.preventDefault();
    if (!valido || pendiente) return;
    void enviar({
      operacion_id: operacionId,
      lote: loteId, equipo: Number(equipo), formato: formatoId,
      inicio: new Date(inicio).toISOString(), termino: new Date(termino).toISOString(),
      observacion: observacion.trim(),
      controles: { sellado, rotulado, integridad_envase: integridad },
      pallets_datos: [{ codigo: codigo.trim(), unidades: Number(unidades), kg_neto: kg }],
    });
  }

  if (pendiente) return <section className="rounded-xl border border-amber-300 bg-amber-50 p-4">
    <h3 className="font-bold text-amber-950">Cierre pendiente de confirmación</h3>
    <p className="mt-2 text-sm text-amber-900">{pendiente.pallets_datos.map((p) => `${p.codigo} · ${p.unidades} unidad(es) · ${p.kg_neto} kg`).join(" | ")}. Se conservaron la clave y todos los datos del pedido.</p>
    <button type="button" disabled={guardando} onClick={() => void enviar(pendiente, true)} className="mt-3 rounded-xl bg-amber-800 px-4 py-2 text-sm font-semibold text-white disabled:opacity-50">{guardando ? "Comprobando…" : "Reintentar el mismo cierre"}</button>
    {mensaje && <p className="mt-3 text-sm text-amber-900">{mensaje}</p>}
  </section>;

  return <form onSubmit={guardar} className="rounded-xl border border-emerald-200 bg-emerald-50/50 p-4">
    <h3 className="text-sm font-bold text-slate-900">Envasar en {tipoUnidadLogistica === "big_bag" ? "Big Bag" : "pallet"} · {formatoNombre}</h3>
    <p className="mt-1 text-xs text-slate-600">Registra el período y los controles reales. Máximo {maximoUnidadLogisticaKg} kg por {tipoUnidadLogistica === "big_bag" ? "Big Bag" : "pallet"}: hasta {maximoUnidades} unidad(es).</p>
    <p className="mt-2 text-xs font-semibold text-emerald-800">
      Saldo utilizable: {cantidadDisponible} kg · máximo {maximoUnidades} unidades completas en este pallet.
    </p>
    <div className="mt-3 grid gap-3 sm:grid-cols-3">
      <select required className={campo} value={equipo} onChange={(e) => setEquipo(e.target.value)}><option value="">Envasadora…</option>{equipos.map((item) => <option key={item.id} value={item.id}>{item.codigo} · {item.nombre}</option>)}</select>
      <input required className={campo} placeholder={tipoUnidadLogistica === "big_bag" ? "Código Big Bag" : "Código pallet"} value={codigo} onChange={(e) => setCodigo(e.target.value)} />
      <input required className={campo} type="number" min="1" max={maximoUnidades} step="1" value={unidades} onChange={(e) => setUnidades(e.target.value)} />
    </div>
    <div className="mt-3 grid gap-3 sm:grid-cols-2">
      <label className="text-xs font-semibold text-slate-600">Inicio real<input required className={`mt-1 ${campo}`} type="datetime-local" value={inicio} onChange={(e) => setInicio(e.target.value)} /></label>
      <label className="text-xs font-semibold text-slate-600">Término real<input required className={`mt-1 ${campo}`} type="datetime-local" value={termino} onChange={(e) => setTermino(e.target.value)} /></label>
    </div>
    <div className="mt-3 grid gap-3 sm:grid-cols-3">
      <Control etiqueta="Sellado" valor={sellado} cambiar={setSellado} />
      <Control etiqueta="Rotulado / lote" valor={rotulado} cambiar={setRotulado} />
      <Control etiqueta="Integridad del envase" valor={integridad} cambiar={setIntegridad} />
    </div>
    <label className="mt-3 block text-xs font-semibold text-slate-600">Observación del turno<textarea className={`mt-1 min-h-20 ${campo}`} value={observacion} onChange={(e) => setObservacion(e.target.value)} placeholder="Paradas, cambio de rollo, rechazo de sacos u otra novedad…" /></label>
    <div className="mt-3 flex flex-wrap items-center gap-3"><span className={`text-sm font-bold ${kg > maximoUnidadLogisticaKg ? "text-red-700" : "text-emerald-800"}`}>{unidades || 0} × {formatoKg} kg = {kg} kg</span><button disabled={!valido || guardando} className="rounded-xl bg-emerald-700 px-4 py-2 text-sm font-semibold text-white disabled:opacity-50">{guardando ? "Registrando…" : `Crear ${tipoUnidadLogistica === "big_bag" ? "Big Bag" : "pallet"}`}</button></div>
    <div className="mt-3 rounded-xl border border-slate-200 bg-white p-3">
      <p className="text-xs font-bold uppercase tracking-wide text-slate-600">Materiales que descontará esta operación</p>
      <ul className="mt-2 space-y-1 text-xs text-slate-600">
        {materiales.map((item) => {
          const requerido = Number(item.cantidad_por_kg) * kg;
          const suficiente = requerido <= Number(item.stock_disponible);
          return <li key={item.codigo} className="flex justify-between gap-3"><span>{item.nombre}</span><span className={suficiente ? "text-emerald-700" : "font-semibold text-red-700"}>{requerido.toLocaleString("es-CL", { maximumFractionDigits: 3 })} {item.unidad} · stock {Number(item.stock_disponible).toLocaleString("es-CL", { maximumFractionDigits: 3 })}</span></li>;
        })}
      </ul>
    </div>
    {mensaje && <p className="mt-3 text-sm text-slate-700">{mensaje}</p>}
  </form>;
}

function Control({ etiqueta, valor, cambiar }: { etiqueta: string; valor: string; cambiar: (valor: string) => void }) {
  return <label className="text-xs font-semibold text-slate-600">{etiqueta}<select className={`mt-1 ${campo}`} value={valor} onChange={(e) => cambiar(e.target.value)}><option value="conforme">Conforme</option><option value="observado">Observado</option><option value="no_conforme">No conforme</option></select></label>;
}
