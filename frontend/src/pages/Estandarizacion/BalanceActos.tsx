import { useRef, useState } from "react";
import { Tarjeta } from "../../components/seccion/componentes";
import { mensajeDe } from "../../components/seccion/utilidades";
import { cantidad } from "../../services/formato";
import { puedeEscribir } from "../../services/sesion";
import { registrarActoVale, type EntradaActoVale, type TipoActo, type ValeEstandarizacion } from "../../services/estandarizacion.service";
import type { Silo } from "../../services/recepcion.service";
import { errorPrecisionLitros, validarActo } from "./balance";

const ETIQUETA: Record<TipoActo, string> = {
  medicion: "Registrar volumen medido", documental: "Rectificación documental",
  adicion: "Registrar adición física", retiro: "Registrar retiro físico",
};
const CAMPOS = [
  ["observaciones", "Observaciones"], ["volumen", "Volumen planificado (L)"],
  ["litros_entera", "Litros de entera"], ["litros_descremada", "Litros de descremada"],
  ["litros_crema", "Litros de crema"],
] as const;
const litros = (valor: string | null | undefined) => cantidad(valor, "L", 2);
const control = "mt-1 w-full rounded-lg border border-slate-300 bg-white px-3 py-2";

export default function BalanceActos({ vale, silos, onActualizado }: {
  vale: ValeEstandarizacion; silos: Silo[]; onActualizado: (vale: ValeEstandarizacion) => void;
}) {
  const produccion = puedeEscribir("produccion");
  const medicion = puedeEscribir("estandarizacion") || puedeEscribir("calidad");
  const [tipo, setTipo] = useState<TipoActo>(medicion ? "medicion" : "documental");
  const [motivo, setMotivo] = useState("");
  const [volumen, setVolumen] = useState("");
  const [silo, setSilo] = useState("");
  const [campo, setCampo] = useState<(typeof CAMPOS)[number][0]>("observaciones");
  const [nuevo, setNuevo] = useState("");
  const [confirmado, setConfirmado] = useState(false);
  const [ocupado, setOcupado] = useState(false);
  const [error, setError] = useState("");
  const [exito, setExito] = useState("");
  // Un reintento del mismo acto conserva su UUID, incluso si se perdió la respuesta.
  const intento = useRef<{ firma: string; clave: string } | null>(null);
  const fisico = tipo === "adicion" || tipo === "retiro";
  const balance = vale.balance;
  const habilitado = Boolean(vale.ejecutado_en) && vale.estado !== "anulado";
  const tipos = (Object.keys(ETIQUETA) as TipoActo[]).filter((valor) => valor === "medicion" ? medicion : produccion);

  const guardar = async (evento: React.FormEvent) => {
    evento.preventDefault();
    if (ocupado) return;
    setError(""); setExito("");
    const datos: Omit<EntradaActoVale, "clave"> = {
      tipo, motivo: motivo.trim(),
      ...(tipo === "medicion" ? { volumen_medido: volumen } : {}),
      ...(fisico ? { litros: volumen, silo_contraparte: Number(silo) } : {}),
      ...(tipo === "documental" ? { rectificacion: { [campo]: nuevo } } : {}),
    };
    const invalido = validarActo(datos) || (tipo === "documental" && campo !== "observaciones"
      ? errorPrecisionLitros({ [campo]: nuevo }) : "");
    if (invalido) { setError(invalido); return; }
    if (fisico && !confirmado) { setError("Confirma la autorización de Producción, el origen, destino y litros de esta corrección."); return; }
    const firma = JSON.stringify(datos);
    if (intento.current?.firma !== firma) intento.current = { firma, clave: crypto.randomUUID() };
    setOcupado(true);
    try {
      const actualizado = await registrarActoVale(vale.id, { ...datos, clave: intento.current.clave });
      onActualizado(actualizado);
      intento.current = null;
      setMotivo(""); setVolumen(""); setNuevo(""); setConfirmado(false);
      setExito(fisico ? "Movimiento registrado. Reagita, toma una nueva muestra y espera liberación de Calidad." : "Acto registrado en el historial del vale.");
    } catch (e) {
      setError(mensajeDe(e, "No se pudo registrar el acto. Puedes reintentar conservando sus datos."));
    } finally { setOcupado(false); }
  };

  return <Tarjeta titulo="Balance y actos del vale" descripcion="La receta ejecutada se conserva. Cada medición, rectificación y movimiento queda en el historial.">
    {balance ? <>
      <dl className="grid gap-4 sm:grid-cols-4">
        {[["Componentes originales", balance.componentes], ["Volumen ejecutado", balance.volumen_ejecutado],
          ["Volumen medido", balance.volumen_medido], ["Diferencia registrada", balance.diferencia]].map(([label, valor]) => <div key={label}>
            <dt className="text-xs text-slate-600">{label}</dt><dd className="mt-1 text-lg font-semibold">{litros(valor)}</dd>
          </div>)}
      </dl>
      <p className="mt-3 text-xs text-slate-600">Medición y diferencia corresponden al momento de su registro; después de un movimiento puede ser necesario medir nuevamente.</p>
      <p className={`mt-4 rounded-xl border p-3 text-sm ${balance.pendiente ? "border-amber-300 bg-amber-50 text-amber-900" : "border-slate-200 bg-slate-50 text-slate-700"}`}>
        {balance.pendiente ? "Balance pendiente: liberación y despacho bloqueados. Revisa la diferencia y registra el acto que corresponda." : "Balance sin diferencia pendiente. La liberación requiere además la decisión de Calidad."}
      </p>
    </> : <p className="text-sm text-slate-600">Balance no disponible. Actualiza el vale antes de decidir su liberación.</p>}
    {habilitado && tipos.length > 0 && <form onSubmit={guardar} className="mt-5 border-t border-slate-200 pt-4">
      <fieldset disabled={ocupado} className="grid gap-3 sm:grid-cols-2">
        <legend className="mb-3 text-sm font-semibold">Registrar un acto</legend>
        <label className="text-sm">Acción<select className={control} value={tipo} onChange={(e) => { setTipo(e.target.value as TipoActo); setVolumen(""); setConfirmado(false); setError(""); }}>
          {tipos.map((valor) => <option key={valor} value={valor}>{ETIQUETA[valor]}</option>)}
        </select></label>
        {tipo !== "documental" && <label className="text-sm">{tipo === "medicion" ? "Volumen medido del vale (L)" : "Litros del movimiento"}
          <input required type="number" min={fisico ? "0.01" : "0"} step="0.01" value={volumen} onChange={(e) => setVolumen(e.target.value)} className={control} />
        </label>}
        {tipo === "medicion" && <p className="text-xs text-slate-600 sm:col-span-2">La medición corresponde a este vale; no al saldo previo del silo. Precisión: 0,01 L, sin redondeo automático.</p>}
        {fisico && <>
          <label className="text-sm">Silo {tipo === "adicion" ? "de origen" : "de destino"}<select required className={control} value={silo} onChange={(e) => setSilo(e.target.value)}>
            <option value="">Selecciona</option>{silos.filter((item) => item.id !== vale.silo_destino).map((item) => <option key={item.id} value={item.id}>{item.codigo}</option>)}
          </select></label>
          <p className="self-center text-sm text-amber-900">El movimiento exige reagitación, nueva muestra y nueva liberación de Calidad.</p>
          <p className="text-sm text-amber-900 sm:col-span-2">No realices movimientos si el sistema informa un bloqueo; registra cualquier diferencia medida para revisión.</p>
          <label className="text-sm sm:col-span-2"><input required type="checkbox" checked={confirmado} onChange={(e) => setConfirmado(e.target.checked)} className="mr-2" />Confirmo la autorización de Producción, el origen, destino y litros de esta corrección.</label>
        </>}
        {tipo === "documental" && <>
          <label className="text-sm">Campo<select value={campo} onChange={(e) => { setCampo(e.target.value as typeof campo); setNuevo(""); }} className={control}>
            {CAMPOS.map(([valor, etiqueta]) => <option key={valor} value={valor}>{etiqueta}</option>)}
          </select></label>
          <label className="text-sm">Valor anterior (registro original)<input readOnly value={vale[campo] ?? ""} className={`${control} bg-slate-50`} /></label>
          <label className="text-sm">Valor nuevo<input required value={nuevo} onChange={(e) => setNuevo(e.target.value)} className={control} type={campo === "observaciones" ? "text" : "number"} step={campo === "observaciones" ? undefined : "0.01"} min={campo === "observaciones" ? undefined : "0"} /></label>
          <p className="text-xs text-slate-600 sm:col-span-2">Esta rectificación conserva el original y no mueve existencias ni resuelve una diferencia física.</p>
        </>}
        <label className="text-sm sm:col-span-2">Motivo<textarea required minLength={5} value={motivo} onChange={(e) => setMotivo(e.target.value)} className={control} /></label>
        <button className="rounded-xl bg-emerald-700 px-4 py-3 text-sm font-semibold text-white disabled:opacity-50 sm:col-span-2" disabled={ocupado}>{ocupado ? "Registrando…" : ETIQUETA[tipo]}</button>
      </fieldset>
    </form>}
    {error && <p role="alert" className="mt-3 text-sm text-rose-700">{error}</p>}
    {exito && <p role="status" className="mt-3 text-sm text-emerald-800">{exito}</p>}
    <h3 className="mt-5 text-sm font-semibold">Historial de actos</h3>
    {!vale.actos?.length ? <p className="mt-2 text-sm text-slate-500">Sin actos registrados.</p> : <ol className="mt-3 space-y-3">
      {vale.actos.map((acto) => <li key={acto.clave} className="rounded-xl border border-slate-200 p-3 text-sm">
        <p className="font-semibold">{ETIQUETA[acto.tipo]}{acto.litros !== null ? ` · ${litros(acto.litros)}` : ""}{acto.volumen_medido !== null ? ` · ${litros(acto.volumen_medido)}` : ""}</p>
        <p className="mt-1">{acto.motivo}</p>
        {acto.silo_contraparte && <p>Silo contraparte: {silos.find((item) => item.id === acto.silo_contraparte)?.codigo ?? acto.silo_contraparte}</p>}
        {Object.entries(acto.rectificacion ?? {}).map(([nombre, cambio]) => <p key={nombre}>{nombre}: {Array.isArray(cambio)
          ? `${String(cambio[0] ?? "—")} → ${String(cambio[1] ?? "—")}` : String(cambio ?? "—")}</p>)}
        <p className="mt-1 text-xs text-slate-500">{acto.usuario_nombre} · {new Date(acto.creado_en).toLocaleString("es-CL")} · {acto.clave}</p>
      </li>)}
    </ol>}
  </Tarjeta>;
}
