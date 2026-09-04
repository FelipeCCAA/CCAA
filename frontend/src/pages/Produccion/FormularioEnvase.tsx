import { useMemo, useState } from "react";

import { registrarEnvase } from "../../services/produccion.service";
import { mensajeErrorProceso } from "../../services/errores-proceso";

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
  maximoPalletKg,
  cantidadDisponible,
  materiales,
  equipos,
  alGuardar,
}: {
  loteId: number;
  formatoId: number;
  formatoKg: number;
  formatoNombre: string;
  maximoPalletKg: number;
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
    Math.min(maximoPalletKg, cantidadDisponible) / formatoKg,
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
  const [operacionId, setOperacionId] = useState(() => crypto.randomUUID());
  const kg = useMemo(() => Number(unidades || 0) * formatoKg, [formatoKg, unidades]);
  const valido = Boolean(
    equipo && codigo.trim() && Number(unidades) > 0 && kg <= maximoPalletKg
    && kg <= cantidadDisponible
    && inicio && termino && new Date(termino) > new Date(inicio),
  );

  async function guardar(evento: React.FormEvent) {
    evento.preventDefault();
    if (!valido) return;
    setGuardando(true); setMensaje("");
    try {
      await registrarEnvase({
        operacion_id: operacionId,
        lote: loteId, equipo: Number(equipo), formato: formatoId,
        inicio: new Date(inicio).toISOString(), termino: new Date(termino).toISOString(),
        observacion: observacion.trim(),
        controles: { sellado, rotulado, integridad_envase: integridad },
        pallets_datos: [{ codigo: codigo.trim(), unidades: Number(unidades), kg_neto: kg }],
      });
      setMensaje(`Pallet ${codigo.trim()} creado: ${unidades} unidades, ${kg} kg. Quedó en cuarentena de Calidad.`);
      // La clave se conserva si falla la respuesta para que un reenvío no
      // duplique el pallet. Solo cambia después de un alta confirmada, porque
      // el siguiente pallet sí representa una operación física nueva.
      setOperacionId(crypto.randomUUID());
      const saldoSiguiente = Math.max(cantidadDisponible - kg, 0);
      const maximoSiguiente = Math.floor(
        Math.min(maximoPalletKg, saldoSiguiente) / formatoKg,
      );
      setCodigo(""); setUnidades(String(maximoSiguiente)); setObservacion(""); alGuardar();
    } catch (error) {
      /* El bloqueo de Calidad lo informa `lote.bloqueo_envasado`, calculado
         en el backend, **antes** de intentar el POST. Aquí solo se muestra lo
         que el servidor respondió: adivinarlo con un `includes` contra el
         texto del mensaje era una segunda fuente para el mismo hecho, y la
         frágil de las dos. */
      setMensaje(mensajeErrorProceso(error, "No se pudo registrar el pallet."));
    } finally { setGuardando(false); }
  }

  return <form onSubmit={guardar} className="rounded-xl border border-emerald-200 bg-emerald-50/50 p-4">
    <h3 className="text-sm font-bold text-slate-900">Envasar en pallet · {formatoNombre}</h3>
    <p className="mt-1 text-xs text-slate-600">Registra el período y los controles reales. Máximo {maximoPalletKg} kg por pallet: hasta {maximoUnidades} unidades.</p>
    <p className="mt-2 text-xs font-semibold text-emerald-800">
      Saldo utilizable: {cantidadDisponible} kg · máximo {maximoUnidades} unidades completas en este pallet.
    </p>
    <div className="mt-3 grid gap-3 sm:grid-cols-3">
      <select required className={campo} value={equipo} onChange={(e) => setEquipo(e.target.value)}><option value="">Envasadora…</option>{equipos.map((item) => <option key={item.id} value={item.id}>{item.codigo} · {item.nombre}</option>)}</select>
      <input required className={campo} placeholder="Código pallet" value={codigo} onChange={(e) => setCodigo(e.target.value)} />
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
    <div className="mt-3 flex flex-wrap items-center gap-3"><span className={`text-sm font-bold ${kg > maximoPalletKg ? "text-red-700" : "text-emerald-800"}`}>{unidades || 0} × {formatoKg} kg = {kg} kg</span><button disabled={!valido || guardando} className="rounded-xl bg-emerald-700 px-4 py-2 text-sm font-semibold text-white disabled:opacity-50">{guardando ? "Registrando…" : "Crear pallet"}</button></div>
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
