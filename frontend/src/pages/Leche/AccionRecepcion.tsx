import { useMemo, useState } from "react";
import axios from "axios";
import { AlertTriangle, CheckCircle2, FlaskConical, TestTube2, Warehouse, X } from "lucide-react";

import {
  asignarSilo,
  CONTROLES_NUMERICOS,
  CONTROLES_OPCION,
  decidirCalidad,
  tomarMuestra,
  type Recepcion,
  type ResponsableRecepcion,
  type Silo,
} from "../../services/recepcion.service";


export type AccionFlujo = "muestra" | "calidad" | "silo";

interface Props {
  accion: AccionFlujo;
  recepcion: Recepcion;
  silos: Silo[];
  responsables: ResponsableRecepcion[];
  alCerrar: () => void;
  alGuardar: () => void;
}


function detalleError(error: unknown): string {
  if (!axios.isAxiosError(error) || !error.response?.data) return "No se pudo completar la acción.";
  const datos = error.response.data;
  if (typeof datos === "string") return datos;
  return Object.entries(datos)
    .map(([campo, valor]) => campo === "detail" ? String(valor) : `${campo}: ${valor}`)
    .join(" · ");
}


function AccionRecepcion({ accion, recepcion, silos, responsables, alCerrar, alGuardar }: Props) {
  const muestraSugerida = [recepcion.guia || `REC-${recepcion.id}`, recepcion.modulo || "M1"]
    .join("-")
    .replace(/\s+/g, "-")
    .toUpperCase();
  const [codigoMuestra, setCodigoMuestra] = useState(muestraSugerida);
  const [controles, setControles] = useState<Record<string, string>>(
    Object.fromEntries(
      Object.entries(recepcion.controles || {}).map(([clave, valor]) => [clave, String(valor)]),
    ),
  );
  const [responsable, setResponsable] = useState(
    recepcion.muestreado_por ? String(recepcion.muestreado_por) : "",
  );
  const [retencionManual, setRetencionManual] = useState(false);
  const [motivo, setMotivo] = useState("");
  const [silo, setSilo] = useState("");
  const [guardando, setGuardando] = useState(false);
  const [error, setError] = useState("");

  const silosCompatibles = useMemo(
    () => silos.filter((item) => item.activo && item.tipo === (recepcion.tipo_leche === "Descremada" ? "tk_ld" : "silo")),
    [recepcion.tipo_leche, silos],
  );

  const cambiarControl = (clave: string, valor: string) =>
    setControles((actuales) => ({ ...actuales, [clave]: valor }));

  const guardar = async (evento: React.FormEvent<HTMLFormElement>) => {
    evento.preventDefault();
    setGuardando(true);
    setError("");

    try {
      if (accion === "muestra") {
        await tomarMuestra(recepcion.id, codigoMuestra, Number(responsable));
      } else if (accion === "silo") {
        await asignarSilo(recepcion.id, Number(silo));
      } else {
        const medidos: Record<string, number | string> = {};
        for (const { clave } of CONTROLES_NUMERICOS) {
          const valor = controles[clave];
          if (valor?.trim() && !Number.isNaN(Number(valor))) medidos[clave] = Number(valor);
        }
        for (const { clave } of CONTROLES_OPCION) {
          if (controles[clave]) medidos[clave] = controles[clave];
        }
        await decidirCalidad(
          recepcion.id,
          medidos,
          retencionManual ? "retener" : undefined,
          retencionManual ? motivo : undefined,
        );
      }
      await alGuardar();
      alCerrar();
    } catch (error) {
      setError(detalleError(error));
      setGuardando(false);
    }
  };

  const configuracion = {
    muestra: { sobre: "Etapa 2 · Muestreo", titulo: "Identificar muestra", icono: TestTube2, boton: "Confirmar muestra" },
    calidad: { sobre: "Etapa 3 · Calidad", titulo: "Evaluar módulo", icono: FlaskConical, boton: "Guardar decisión" },
    silo: { sobre: "Etapa 4 · Destino", titulo: "Asignar silo", icono: Warehouse, boton: "Confirmar destino" },
  }[accion];
  const Icono = configuracion.icono;
  const etiqueta = "mb-1.5 block text-xs font-semibold text-slate-600";
  const campo = "h-11 w-full rounded-xl border border-slate-200 bg-white px-3.5 text-sm text-slate-800 outline-none transition focus:border-emerald-500 focus:ring-4 focus:ring-emerald-500/10";

  return (
    <div className="fixed inset-0 z-50 overflow-y-auto bg-slate-950/50 p-3 backdrop-blur-[2px] sm:p-6">
      <div className="mx-auto w-full max-w-2xl overflow-hidden rounded-3xl bg-white shadow-2xl shadow-slate-950/20">
        <div className="flex items-center justify-between border-b border-slate-200 px-6 py-5">
          <div className="flex items-center gap-3"><span className="rounded-xl bg-emerald-50 p-2.5 text-emerald-700"><Icono className="h-5 w-5" /></span><div><p className="text-[11px] font-bold uppercase tracking-[0.14em] text-emerald-700">{configuracion.sobre}</p><h2 className="mt-0.5 text-lg font-semibold text-slate-950">{configuracion.titulo}</h2></div></div>
          <button type="button" onClick={alCerrar} className="rounded-xl p-2 text-slate-600 hover:bg-slate-100" aria-label="Cerrar"><X className="h-5 w-5" /></button>
        </div>

        <form onSubmit={guardar}>
          <div className="p-6">
            <div className="mb-6 grid grid-cols-2 gap-3 rounded-2xl bg-slate-50 p-4 text-sm sm:grid-cols-4">
              <div><p className="text-[10px] font-semibold uppercase tracking-wider text-slate-600">Guía</p><p className="mt-1 font-semibold text-slate-800">{recepcion.guia || "—"}</p></div>
              <div><p className="text-[10px] font-semibold uppercase tracking-wider text-slate-600">Módulo</p><p className="mt-1 font-semibold text-slate-800">{recepcion.modulo || "—"}</p></div>
              <div><p className="text-[10px] font-semibold uppercase tracking-wider text-slate-600">Tipo</p><p className="mt-1 font-semibold text-slate-800">{recepcion.tipo_leche}</p></div>
              <div><p className="text-[10px] font-semibold uppercase tracking-wider text-slate-600">Volumen</p><p className="mt-1 font-semibold text-slate-800">{Number(recepcion.litros).toLocaleString("es-CL")} L</p></div>
            </div>

            {accion === "muestra" && <div className="space-y-4">
              <div><label className={etiqueta}>Código único de muestra *</label><input aria-label="Código de muestra" className={campo} value={codigoMuestra} onChange={(e) => setCodigoMuestra(e.target.value)} required /></div>
              <div><label className={etiqueta}>Responsable de realizar la prueba *</label><select aria-label="Responsable de la prueba" className={campo} value={responsable} onChange={(e) => setResponsable(e.target.value)} required><option value="">Seleccionar usuario de Recepción</option>{responsables.map((usuario) => <option key={usuario.id} value={usuario.id}>{usuario.nombre}{usuario.turno ? ` · ${usuario.turno}` : ""}</option>)}</select>{responsables.length === 0 && <p className="mt-2 text-xs text-amber-700">No hay usuarios activos asignados al área Recepción.</p>}</div>
              <p className="rounded-xl bg-blue-50 px-4 py-3 text-xs leading-5 text-blue-700">La crioscopía se registrará para este módulo. Los demás análisis se compartirán con todos los módulos del mismo camión.</p>
            </div>}

            {accion === "calidad" && <div className="space-y-5">
              <div><p className="mb-3 text-xs font-bold uppercase tracking-wider text-slate-600">Por camión completo</p><div className="grid grid-cols-2 gap-4 sm:grid-cols-3">{CONTROLES_NUMERICOS.filter((control) => control.clave !== "crioscopia").map((control) => <div key={control.clave}><label className={etiqueta}>{control.etiqueta} {control.unidad && <span className="font-normal text-slate-600">({control.unidad})</span>}</label><input aria-label={control.etiqueta} type="number" step="any" className={campo} value={controles[control.clave] ?? ""} onChange={(e) => cambiarControl(control.clave, e.target.value)} /></div>)}</div></div>
              <div className="grid gap-4 sm:grid-cols-3">{CONTROLES_OPCION.map((control) => <div key={control.clave}><label className={etiqueta}>{control.etiqueta}</label><select aria-label={control.etiqueta} className={campo} value={controles[control.clave] ?? ""} onChange={(e) => cambiarControl(control.clave, e.target.value)} required={control.clave === "delvo"}><option value="">Sin informar</option>{control.valores.map((valor) => <option key={valor} value={valor}>{valor}</option>)}</select></div>)}</div>
              <div className="rounded-2xl border border-violet-200 bg-violet-50 p-4"><p className="mb-3 text-xs font-bold uppercase tracking-wider text-violet-700">Solo para {recepcion.modulo || "este módulo"}</p>{CONTROLES_NUMERICOS.filter((control) => control.clave === "crioscopia").map((control) => <div key={control.clave}><label className={etiqueta}>{control.etiqueta} <span className="font-normal text-slate-600">({control.unidad})</span> *</label><input aria-label={control.etiqueta} required type="number" step="any" className={campo} value={controles[control.clave] ?? ""} onChange={(e) => cambiarControl(control.clave, e.target.value)} /></div>)}</div>
              <label className="flex cursor-pointer items-start gap-3 rounded-2xl border border-slate-200 p-4"><input type="checkbox" className="mt-0.5 h-4 w-4 accent-amber-600" checked={retencionManual} onChange={(e) => setRetencionManual(e.target.checked)} /><span><span className="block text-sm font-semibold text-slate-800">Retener por observación operacional</span><span className="mt-1 block text-xs leading-5 text-slate-600">Úsalo para sello roto, contaminación visible u otra condición no representada por un análisis.</span></span></label>
              {retencionManual && <div><label className={etiqueta}>Motivo de retención *</label><textarea aria-label="Motivo de retención" className={`${campo} h-auto py-3`} rows={2} value={motivo} onChange={(e) => setMotivo(e.target.value)} required /></div>}
              <div className="flex items-start gap-2 rounded-xl bg-blue-50 px-4 py-3 text-xs leading-5 text-blue-700"><CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0" />Los controles del camión se reutilizan en sus otros módulos; cada módulo exige su propia crioscopía antes de aprobarse.</div>
            </div>}

            {accion === "silo" && <div><label className={etiqueta}>Silo compatible *</label><select aria-label="Silo compatible" className={campo} value={silo} onChange={(e) => setSilo(e.target.value)} required><option value="">Seleccionar destino</option>{silosCompatibles.map((item) => <option key={item.id} value={item.id}>{item.codigo} · capacidad {Number(item.capacidad_l).toLocaleString("es-CL")} L</option>)}</select>{silosCompatibles.length === 0 ? <p className="mt-3 flex items-start gap-2 rounded-xl bg-amber-50 px-4 py-3 text-xs text-amber-700"><AlertTriangle className="h-4 w-4 shrink-0" />No hay silos activos compatibles con leche {recepcion.tipo_leche.toLowerCase()}.</p> : <p className="mt-2 text-xs text-slate-600">Solo se muestran destinos compatibles con {recepcion.tipo_leche.toLowerCase()}.</p>}</div>}

            {error && <div className="mt-5 rounded-xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700">{error}</div>}
          </div>

          <div className="flex justify-end gap-3 border-t border-slate-200 bg-slate-50 px-6 py-4"><button type="button" onClick={alCerrar} className="h-10 rounded-xl px-4 text-sm font-semibold text-slate-600 hover:bg-slate-200/60">Cancelar</button><button type="submit" disabled={guardando || (accion === "silo" && silosCompatibles.length === 0) || (accion === "muestra" && responsables.length === 0)} className="h-10 rounded-xl bg-emerald-700 px-5 text-sm font-semibold text-white hover:bg-emerald-800 disabled:opacity-50">{guardando ? "Guardando…" : configuracion.boton}</button></div>
        </form>
      </div>
    </div>
  );
}


export default AccionRecepcion;
