import { useEffect, useId, useRef, useState, type FormEvent, type ReactNode } from "react";
import { X } from "lucide-react";
import { Link } from "react-router-dom";

import ConfirmarAccion from "../../components/operacion/ConfirmarAccion";
import { puedeAccederModulo } from "../../services/access-control";
import { mensajeErrorProceso } from "../../services/errores-proceso";
import { fechaLocalISO } from "../../services/fechas";
import { cantidad } from "../../services/formato";
import { prepararMantequilla, type PuestoMantequilla } from "../../services/mantequilla.service";
import { sugerirCodigoLote } from "../../services/produccion.service";
import { obtenerSesion } from "../../services/sesion";

const control = "mt-1 w-full rounded-xl border border-slate-300 bg-white px-3 py-2.5 text-sm outline-none focus:border-amber-600";
const ESTADO_CALIDAD = {
  pendiente: "pendiente de liberación",
  rechazado: "rechazada por Calidad",
  trazabilidad_incompleta: "con trazabilidad incompleta",
} as const;

/*
  «Preparar mantequilla»: crema → kg → OP → mantequera → mazada → código del
  lote de salida → confirmación. Cremas, órdenes, mantequeras y sueros vienen
  del puesto (`mantequillas/puesto/`), con las reglas que «Preparar» vuelve a
  aplicar; la ocupación no se calcula aquí. El código se sugiere con
  `codigo-sugerido/` (sigla de la mantequera y fecha de hoy) y queda
  editable. Preparar no inicia: la tarjeta habilita «Iniciar mantequilla»
  cuando el servidor lo permite.
*/
export default function PrepararMantequilla({ puesto, cremaInicial, equipoInicial, alCerrar, alPreparar }: {
  puesto: PuestoMantequilla;
  cremaInicial?: number;
  equipoInicial?: number;
  alCerrar: () => void;
  alPreparar: (codigo: string) => void;
}) {
  const libres = puesto.mantequeras.filter((item) => item.estado === "disponible" && item.motivos_para_tomar.length === 0);
  const [crema, setCrema] = useState(
    cremaInicial !== undefined && puesto.cremas.some((item) => item.id === cremaInicial) ? String(cremaInicial) : "",
  );
  const [kg, setKg] = useState("");
  const [orden, setOrden] = useState(puesto.ordenes.length === 1 ? String(puesto.ordenes[0].id) : "");
  const [equipo, setEquipo] = useState(
    equipoInicial !== undefined ? String(equipoInicial) : libres.length === 1 ? String(libres[0].equipo_id) : "",
  );
  const [suero, setSuero] = useState("");
  const [codigo, setCodigo] = useState("");
  const [notaCodigo, setNotaCodigo] = useState("");
  const codigoEditado = useRef(false);
  const [revisando, setRevisando] = useState(false);
  const [guardando, setGuardando] = useState(false);
  const [error, setError] = useState("");
  const enviando = useRef(false);
  const idTitulo = useId();

  useEffect(() => {
    if (!equipo) return;
    let vigente = true;
    // Diferido: un `setState` en el cuerpo del efecto encadena renders.
    const tarea = window.setTimeout(() => {
      sugerirCodigoLote(Number(equipo), fechaLocalISO())
        .then((sugerencia) => {
          // Una sugerencia tardía no pisa lo que el operador ya escribió.
          if (!vigente || codigoEditado.current) return;
          setCodigo(sugerencia.codigo ?? "");
          setNotaCodigo(sugerencia.motivo ?? "Sugerido por el sistema; puedes cambiarlo.");
        })
        .catch(() => {
          if (vigente) setNotaCodigo("Sin sugerencia: escribe el código del lote.");
        });
    }, 0);
    return () => { vigente = false; window.clearTimeout(tarea); };
  }, [equipo]);

  const elegida = puesto.cremas.find((item) => item.id === Number(crema));
  const pedidaPendiente = cremaInicial !== undefined
    ? puesto.cremas_pendientes_calidad.find((item) => item.id === cremaInicial)
    : undefined;
  const ordenElegida = puesto.ordenes.find((item) => item.id === Number(orden));
  const maquina = libres.find((item) => item.equipo_id === Number(equipo));
  const sueroElegido = puesto.sueros.find((item) => item.id === Number(suero));
  const excede = Boolean(elegida && Number(kg) > Number(elegida.disponible_kg));
  const completo = Boolean(elegida && Number(kg) > 0 && !excede && ordenElegida && maquina && codigo.trim());
  const usuario = obtenerSesion()?.usuario;

  const revisar = (evento: FormEvent) => {
    evento.preventDefault();
    if (completo) setRevisando(true);
  };

  const confirmar = async () => {
    if (enviando.current || !elegida || !ordenElegida || !maquina) return;
    enviando.current = true;
    setGuardando(true);
    setError("");
    try {
      const corrida = await prepararMantequilla({
        orden: ordenElegida.id, lote_crema: elegida.id, equipo: maquina.equipo_id,
        codigo_lote_mantequilla: codigo.trim(), kg_crema: Number(kg),
        ...(sueroElegido ? { lote_suero: sueroElegido.id } : {}),
      });
      alPreparar(corrida.ejecucion_codigo);
    } catch (causa) {
      setError(mensajeErrorProceso(causa, "No se pudo preparar la mantequilla."));
      setRevisando(false);
    } finally {
      enviando.current = false;
      setGuardando(false);
    }
  };

  return (
    <div className="fixed inset-0 z-[70] overflow-y-auto bg-slate-950/45 p-4" role="dialog" aria-modal="true" aria-labelledby={idTitulo}>
      <form onSubmit={revisar} className="mx-auto my-8 max-w-2xl space-y-5 rounded-2xl bg-white p-6 shadow-xl">
        <div className="flex items-start justify-between gap-4">
          <div>
            <p className="text-xs font-bold uppercase tracking-wider text-amber-700">Puesto de Mantequilla</p>
            <h2 id={idTitulo} className="mt-1 text-2xl font-bold text-slate-900">Preparar mantequilla</h2>
            <p className="mt-2 text-sm text-slate-600">Toma la mantequera y abre el lote de salida. La crema sale del TK cuando se inicia, desde la tarjeta.</p>
          </div>
          <button type="button" onClick={alCerrar} disabled={guardando} className="rounded-lg p-2 hover:bg-slate-100" aria-label="Cerrar"><X className="h-5 w-5" /></button>
        </div>

        {pedidaPendiente && (
          <p role="alert" className="rounded-xl bg-violet-50 px-4 py-3 text-sm text-violet-900">
            {pedidaPendiente.codigo} está {ESTADO_CALIDAD[pedidaPendiente.estado_calidad]}
            {pedidaPendiente.estado_calidad === "trazabilidad_incompleta" ? ` (origen ${pedidaPendiente.etapa_origen})` : ""}: no se puede preparar todavía.
            {puedeAccederModulo(usuario, "calidad") && <>{" "}<Link to="/calidad" className="font-semibold underline">Ir a Calidad</Link></>}
          </p>
        )}

        <fieldset className="grid gap-4 sm:grid-cols-2" disabled={revisando}>
          <Campo texto="Crema">
            <select required value={crema} onChange={(e) => setCrema(e.target.value)} className={control}>
              <option value="">Seleccionar…</option>
              {puesto.cremas.map((item) => (
                <option key={item.id} value={item.id}>
                  {item.codigo} · {cantidad(item.disponible_kg, "kg")} disponibles{item.tk ? ` · ${item.tk}` : ""}
                </option>
              ))}
            </select>
          </Campo>
          <Campo texto="Crema a utilizar (kg)">
            <input required type="number" min="0.001" step="0.001" max={elegida?.disponible_kg} value={kg} onChange={(e) => setKg(e.target.value)} className={control} />
          </Campo>
          <Campo texto="Orden de mantequilla">
            <select required value={orden} onChange={(e) => setOrden(e.target.value)} className={control}>
              <option value="">Seleccionar…</option>
              {puesto.ordenes.map((item) => <option key={item.id} value={item.id}>{item.codigo} · {item.producto}</option>)}
            </select>
          </Campo>
          <Campo texto="Mantequera">
            <select required value={equipo} onChange={(e) => setEquipo(e.target.value)} className={control}>
              <option value="">Seleccionar…</option>
              {libres.map((item) => <option key={item.equipo_id} value={item.equipo_id}>{item.codigo} · {item.nombre}</option>)}
            </select>
          </Campo>
          <Campo texto="Lote de suero / mazada (opcional)">
            <select value={suero} onChange={(e) => setSuero(e.target.value)} className={control}>
              <option value="">Sin recuperación de mazada</option>
              {puesto.sueros.map((item) => <option key={item.id} value={item.id}>{item.codigo} · {item.producto}</option>)}
            </select>
          </Campo>
          <Campo texto="Código del lote de mantequilla">
            <input required value={codigo} onChange={(e) => { codigoEditado.current = true; setCodigo(e.target.value.toUpperCase()); }} className={control} />
            {notaCodigo && <span className="mt-1 block text-xs font-normal text-slate-500">{notaCodigo}</span>}
          </Campo>
        </fieldset>
        {excede && elegida && <p className="rounded-xl bg-amber-50 px-4 py-3 text-sm text-amber-900">{elegida.codigo} tiene {cantidad(elegida.disponible_kg, "kg")} disponibles: «Preparar» lo va a rechazar.</p>}
        {libres.length === 0 && <p className="rounded-xl bg-amber-50 p-3 text-sm text-amber-900">No hay mantequeras disponibles: todas están preparadas, en curso o en CIP.</p>}
        {puesto.ordenes.length === 0 && (
          <p className="rounded-xl bg-amber-50 p-3 text-sm text-amber-900">
            No hay una OP de mantequilla programada.
            {puedeAccederModulo(usuario, "planificacion") && <>{" "}<Link to="/planificacion" className="font-semibold underline">Ir a Planificación</Link></>}
          </p>
        )}
        {puesto.cremas.length === 0 && !pedidaPendiente && <p className="rounded-xl bg-amber-50 p-3 text-sm text-amber-900">No hay crema liberada con saldo disponible.</p>}
        {error && !revisando && <p role="alert" className="rounded-xl bg-red-50 px-4 py-3 text-sm text-red-800">{error}</p>}

        {revisando && elegida && ordenElegida && maquina ? (
          <ConfirmarAccion
            titulo="Preparar la mantequilla"
            filas={[
              { etiqueta: "Crema", valor: `${elegida.codigo} · ${cantidad(kg, "kg")}${elegida.tk ? ` desde ${elegida.tk}` : ""}` },
              { etiqueta: "Orden", valor: `${ordenElegida.codigo} · ${ordenElegida.producto}` },
              { etiqueta: "Mantequera", valor: maquina.nombre },
              { etiqueta: "Mazada", valor: sueroElegido ? sueroElegido.codigo : "Sin recuperación" },
              { etiqueta: "Lote de salida", valor: codigo.trim() },
            ]}
            advertencia="La mantequera queda tomada hasta que se inicie o se cancele la preparación."
            textoConfirmar="Preparar mantequilla"
            ocupado={guardando}
            error={error}
            onConfirmar={() => void confirmar()}
            onVolver={() => setRevisando(false)}
          />
        ) : (
          <div className="flex justify-end gap-3">
            <button type="button" onClick={alCerrar} className="rounded-xl border border-slate-300 px-4 py-2.5 text-sm font-semibold text-slate-700">Cancelar</button>
            <button type="submit" disabled={!completo} className="rounded-xl bg-amber-700 px-5 py-2.5 text-sm font-semibold text-white disabled:opacity-40">Revisar y confirmar</button>
          </div>
        )}
      </form>
    </div>
  );
}

function Campo({ texto, children }: { texto: string; children: ReactNode }) {
  return <label className="text-sm font-medium text-slate-700">{texto}{children}</label>;
}
