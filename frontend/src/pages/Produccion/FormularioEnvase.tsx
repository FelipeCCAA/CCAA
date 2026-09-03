import { useEffect, useMemo, useState } from "react";

import { obtenerEquipos, type Equipo } from "../../services/maestros.service";
import { registrarEnvase } from "../../services/produccion.service";
import { mensajeErrorProceso } from "../../services/errores-proceso";

const campo = "w-full rounded-xl border border-slate-300 bg-white px-3 py-2 text-sm";
const fechaLocal = (fecha: Date) => {
  const desplazada = new Date(fecha.getTime() - fecha.getTimezoneOffset() * 60_000);
  return desplazada.toISOString().slice(0, 16);
};

export default function FormularioEnvase({
  loteId,
  formatoKg,
  formatoNombre,
  maximoPalletKg,
  alGuardar,
}: {
  loteId: number;
  formatoKg: number;
  formatoNombre: string;
  maximoPalletKg: number;
  alGuardar: () => void;
}) {
  const [equipos, setEquipos] = useState<Equipo[]>([]);
  const [equipo, setEquipo] = useState("");
  const [codigo, setCodigo] = useState("");
  const maximoUnidades = Math.floor(maximoPalletKg / formatoKg);
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
    && inicio && termino && new Date(termino) > new Date(inicio),
  );

  useEffect(() => {
    void obtenerEquipos()
      .then((lista) => setEquipos(lista.filter((item) => item.activo && ["envasadora", "linea"].includes(item.tipo))))
      .catch(() => setMensaje("No se pudieron cargar las envasadoras."));
  }, []);

  async function guardar(evento: React.FormEvent) {
    evento.preventDefault();
    if (!valido) return;
    setGuardando(true); setMensaje("");
    try {
      await registrarEnvase({
        operacion_id: operacionId,
        lote: loteId, equipo: Number(equipo), formato_kg: formatoKg,
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
      setCodigo(""); setUnidades(String(maximoUnidades)); setObservacion(""); alGuardar();
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
    {mensaje && <p className="mt-3 text-sm text-slate-700">{mensaje}</p>}
  </form>;
}

function Control({ etiqueta, valor, cambiar }: { etiqueta: string; valor: string; cambiar: (valor: string) => void }) {
  return <label className="text-xs font-semibold text-slate-600">{etiqueta}<select className={`mt-1 ${campo}`} value={valor} onChange={(e) => cambiar(e.target.value)}><option value="conforme">Conforme</option><option value="observado">Observado</option><option value="no_conforme">No conforme</option></select></label>;
}
