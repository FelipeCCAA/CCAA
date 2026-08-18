import { useEffect, useMemo, useState } from "react";
import axios from "axios";
import { Beaker, Layers3, Plus, Trash2, Truck, X } from "lucide-react";

import { registrarLlegadaCamion, type Vehiculo } from "../../services/recepcion.service";
import { obtenerCargasPendientes, type CargaEsperada } from "../../services/recoleccion.service";

interface Props {
  vehiculos: Vehiculo[];
  alCerrar: () => void;
  alGuardar: () => void;
}

interface ModuloFormulario {
  clave: number;
  modulo: string;
  litros: string;
  carga_recoleccion?: number;
}

const hoy = () => new Date().toISOString().slice(0, 10);
const nuevoModulo = (clave: number, numero: number): ModuloFormulario => ({
  clave,
  modulo: `Módulo ${numero}`,
  litros: "",
});

function FormularioRecepcion({ vehiculos, alCerrar, alGuardar }: Props) {
  const [fecha, setFecha] = useState(hoy());
  const [hora, setHora] = useState("");
  const [guia, setGuia] = useState("");
  const [vehiculo, setVehiculo] = useState("");
  const [procedencia, setProcedencia] = useState("");
  const [tipoLeche, setTipoLeche] = useState("Entera");
  const [turno, setTurno] = useState("");
  const [observacion, setObservacion] = useState("");
  const [cargasEsperadas, setCargasEsperadas] = useState<CargaEsperada[]>([]);
  const [cargaSeleccionada, setCargaSeleccionada] = useState("");
  const [modulos, setModulos] = useState<ModuloFormulario[]>([nuevoModulo(1, 1)]);
  const [siguienteClave, setSiguienteClave] = useState(2);
  const [guardando, setGuardando] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    void obtenerCargasPendientes().then(setCargasEsperadas).catch(() => setCargasEsperadas([]));
  }, []);

  const litrosTotales = useMemo(
    () => modulos.reduce((total, modulo) => total + (Number(modulo.litros) || 0), 0),
    [modulos],
  );

  const cambiarModulo = (clave: number, campo: "modulo" | "litros", valor: string) => {
    setModulos((actuales) => actuales.map((item) =>
      item.clave === clave ? { ...item, [campo]: valor } : item,
    ));
  };

  const agregarModulo = () => {
    setModulos((actuales) => [...actuales, nuevoModulo(siguienteClave, actuales.length + 1)]);
    setSiguienteClave((actual) => actual + 1);
  };

  const quitarModulo = (clave: number) => {
    setModulos((actuales) => actuales.filter((item) => item.clave !== clave));
  };

  const agregarCargaEsperada = () => {
    const carga = cargasEsperadas.find((item) => item.id === Number(cargaSeleccionada));
    if (!carga || modulos.some((item) => item.carga_recoleccion === carga.id)) return;
    setVehiculo(String(carga.vehiculo));
    setGuia((actual) => actual || carga.codigo);
    setModulos((actuales) => {
      const vacioInicial = actuales.length === 1 && !actuales[0].litros;
      const nuevo = {
        clave: siguienteClave,
        modulo: carga.modulo,
        litros: carga.litros,
        carga_recoleccion: carga.id,
      };
      return vacioInicial ? [{ ...nuevo, clave: actuales[0].clave }] : [...actuales, nuevo];
    });
    setSiguienteClave((actual) => actual + 1);
    setCargaSeleccionada("");
  };

  const enviar = async (evento: React.FormEvent<HTMLFormElement>) => {
    evento.preventDefault();
    setError("");
    setGuardando(true);
    try {
      await registrarLlegadaCamion({
        fecha,
        hora: hora || undefined,
        guia: guia || undefined,
        vehiculo: Number(vehiculo),
        procedencia: procedencia || undefined,
        tipo_leche: tipoLeche,
        turno: turno || undefined,
        observacion: observacion || undefined,
        modulos: modulos.map(({ modulo, litros, carga_recoleccion }) => ({
          modulo,
          litros,
          carga_recoleccion,
        })),
      });
      alGuardar();
      alCerrar();
    } catch (fallo) {
      if (axios.isAxiosError(fallo) && fallo.response?.data) {
        const datos = fallo.response.data;
        setError(typeof datos === "object"
          ? Object.entries(datos).map(([campo, detalle]) => `${campo}: ${detalle}`).join(" · ")
          : "No se pudo registrar la llegada.");
      } else setError("No se pudo conectar con el servidor.");
      setGuardando(false);
    }
  };

  const etiqueta = "mb-1.5 block text-xs font-semibold text-slate-600";
  const campo = "h-11 w-full rounded-xl border border-slate-200 bg-white px-3.5 text-sm text-slate-800 outline-none focus:border-emerald-500 focus:ring-4 focus:ring-emerald-500/10";

  return (
    <div className="fixed inset-0 z-50 overflow-y-auto bg-slate-950/55 p-3 backdrop-blur-[2px] sm:p-6">
      <div className="mx-auto w-full max-w-5xl overflow-hidden rounded-3xl bg-slate-50 shadow-2xl">
        <div className="flex items-center justify-between border-b border-slate-200 bg-white px-6 py-5 sm:px-8">
          <div><p className="text-xs font-bold uppercase tracking-[0.16em] text-emerald-700">Etapa 1 · Recepción</p><h2 className="mt-1 text-xl font-semibold text-slate-950">Registrar llegada del camión</h2><p className="mt-1 text-xs text-slate-600">Los datos generales se ingresan una vez; abajo se separan sus módulos o estanques.</p></div>
          <button type="button" onClick={alCerrar} className="rounded-xl border border-slate-200 p-2 text-slate-600 hover:bg-slate-50" aria-label="Cerrar"><X className="h-5 w-5" /></button>
        </div>

        <form onSubmit={enviar}>
          <div className="space-y-5 p-5 sm:p-8">
            {cargasEsperadas.length > 0 && (
              <section className="rounded-2xl border border-emerald-200 bg-emerald-50 p-5">
                <p className="text-sm font-semibold text-emerald-900">Cargas esperadas desde Recolección</p>
                <div className="mt-3 flex flex-col gap-2 sm:flex-row">
                  <select className={`${campo} flex-1 border-emerald-200`} value={cargaSeleccionada} onChange={(e) => setCargaSeleccionada(e.target.value)}>
                    <option value="">Seleccionar un módulo cargado</option>
                    {cargasEsperadas.map((carga) => <option key={carga.id} value={carga.id}>{carga.vehiculo_placa} · {carga.modulo} · {carga.predio} · {Number(carga.litros).toLocaleString("es-CL")} L</option>)}
                  </select>
                  <button type="button" onClick={agregarCargaEsperada} disabled={!cargaSeleccionada} className="h-11 rounded-xl bg-emerald-700 px-5 text-sm font-semibold text-white disabled:opacity-40">Agregar al camión</button>
                </div>
              </section>
            )}

            <section className="rounded-2xl border border-slate-200 bg-white p-5 sm:p-6">
              <div className="mb-5 flex items-center gap-3"><span className="rounded-xl bg-emerald-50 p-2 text-emerald-700"><Truck className="h-5 w-5" /></span><div><h3 className="font-semibold text-slate-900">Datos generales del camión / estanque</h3><p className="text-xs text-slate-600">Se guardan una sola vez y aplican a todos los módulos declarados.</p></div></div>
              <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
                <div><label className={etiqueta}>Fecha *</label><input type="date" className={campo} value={fecha} onChange={(e) => setFecha(e.target.value)} required /></div>
                <div><label className={etiqueta}>Hora de llegada</label><input type="time" className={campo} value={hora} onChange={(e) => setHora(e.target.value)} /></div>
                <div><label className={etiqueta}>Guía / recepción</label><input className={campo} value={guia} onChange={(e) => setGuia(e.target.value)} placeholder="Ej. GR-2048" /></div>
                <div><label className={etiqueta}>Turno</label><select className={campo} value={turno} onChange={(e) => setTurno(e.target.value)}><option value="">Seleccionar</option><option value="A">Turno A</option><option value="B">Turno B</option><option value="C">Turno C</option></select></div>
                <div className="sm:col-span-2"><label className={etiqueta}>Camión *</label><select className={campo} value={vehiculo} onChange={(e) => setVehiculo(e.target.value)} required><option value="">Seleccionar camión</option>{vehiculos.map((item) => <option key={item.id} value={item.id}>{item.placa}{item.transportista ? ` · ${item.transportista}` : ""}</option>)}</select></div>
                <div><label className={etiqueta}>Procedencia</label><select className={campo} value={procedencia} onChange={(e) => setProcedencia(e.target.value)}><option value="">Seleccionar</option><option value="Nestlé">Nestlé</option><option value="P. Unión">P. Unión</option></select></div>
                <div><label className={etiqueta}>Tipo de leche *</label><select className={campo} value={tipoLeche} onChange={(e) => setTipoLeche(e.target.value)} required><option value="Entera">Entera</option><option value="Descremada">Descremada</option></select></div>
              </div>
            </section>

            <section className="rounded-2xl border border-violet-200 bg-white p-5 sm:p-6">
              <div className="flex flex-wrap items-center justify-between gap-3"><div className="flex items-center gap-3"><span className="rounded-xl bg-violet-50 p-2 text-violet-700"><Layers3 className="h-5 w-5" /></span><div><h3 className="font-semibold text-slate-900">Módulos o estanques del camión</h3><p className="text-xs text-slate-600">Cada uno tiene sus litros y luego su propia crioscopía.</p></div></div><div className="rounded-xl bg-violet-50 px-4 py-2 text-right"><p className="text-[10px] font-bold uppercase tracking-wider text-violet-500">Total camión</p><p className="font-semibold text-violet-900">{litrosTotales.toLocaleString("es-CL")} L</p></div></div>
              <div className="mt-5 space-y-3">
                {modulos.map((item, indice) => (
                  <div key={item.clave} className="grid gap-3 rounded-2xl bg-slate-50 p-4 sm:grid-cols-[auto_1fr_1fr_auto] sm:items-end">
                    <span className="flex h-9 w-9 items-center justify-center rounded-full bg-violet-700 text-sm font-bold text-white">{indice + 1}</span>
                    <div><label className={etiqueta}>Módulo / compartimiento *</label><input className={campo} value={item.modulo} onChange={(e) => cambiarModulo(item.clave, "modulo", e.target.value)} required /></div>
                    <div><label className={etiqueta}>Litros del módulo *</label><input type="number" min="0.01" step="0.01" className={campo} value={item.litros} onChange={(e) => cambiarModulo(item.clave, "litros", e.target.value)} required /></div>
                    <button type="button" onClick={() => quitarModulo(item.clave)} disabled={modulos.length === 1} className="flex h-11 w-11 items-center justify-center rounded-xl text-rose-600 hover:bg-rose-50 disabled:opacity-25" aria-label="Quitar módulo"><Trash2 className="h-4 w-4" /></button>
                  </div>
                ))}
              </div>
              <button type="button" onClick={agregarModulo} className="mt-4 inline-flex h-10 items-center gap-2 rounded-xl border border-violet-200 px-4 text-sm font-semibold text-violet-700 hover:bg-violet-50"><Plus className="h-4 w-4" />Agregar otro módulo</button>
            </section>

            <section className="grid gap-3 rounded-2xl border border-sky-200 bg-sky-50 p-5 sm:grid-cols-[auto_1fr]"><Beaker className="h-5 w-5 text-sky-700" /><div><p className="text-sm font-semibold text-sky-900">Cómo seguirá el análisis</p><p className="mt-1 text-xs leading-5 text-sky-700">Temperatura, acidez, pH, Delvo, inhibidores y organoléptico corresponden al camión/estanque completo. Solo la crioscopía se registrará de forma independiente para cada módulo.</p></div></section>

            <div><label className={etiqueta}>Observaciones generales</label><textarea className={`${campo} h-auto py-3`} rows={3} value={observacion} onChange={(e) => setObservacion(e.target.value)} /></div>
          </div>

          {error && <div className="mx-5 mb-5 rounded-xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700 sm:mx-8">{error}</div>}
          <div className="flex items-center justify-between gap-3 border-t border-slate-200 bg-white px-6 py-5 sm:px-8"><p className="hidden text-xs text-slate-600 sm:block">Se crearán {modulos.length} módulos bajo una misma llegada.</p><div className="ml-auto flex gap-3"><button type="button" onClick={alCerrar} className="h-11 rounded-xl px-5 text-sm font-semibold text-slate-600 hover:bg-slate-100">Cancelar</button><button type="submit" disabled={guardando} className="h-11 rounded-xl bg-emerald-700 px-6 text-sm font-semibold text-white hover:bg-emerald-800 disabled:opacity-60">{guardando ? "Registrando…" : `Registrar camión y ${modulos.length} módulo${modulos.length === 1 ? "" : "s"}`}</button></div></div>
        </form>
      </div>
    </div>
  );
}

export default FormularioRecepcion;
