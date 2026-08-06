import { useState } from "react";
import axios from "axios";
import { ArrowRight, FlaskConical, Layers3, Truck, Warehouse, X } from "lucide-react";

import { crearRecepcion, type Vehiculo } from "../../services/recepcion.service";


interface Props {
  vehiculos: Vehiculo[];
  alCerrar: () => void;
  alGuardar: () => void;
}

const hoy = () => new Date().toISOString().slice(0, 10);


function FormularioRecepcion({ vehiculos, alCerrar, alGuardar }: Props) {
  const [fecha, setFecha] = useState(hoy());
  const [hora, setHora] = useState("");
  const [guia, setGuia] = useState("");
  const [vehiculo, setVehiculo] = useState("");
  const [modulo, setModulo] = useState("");
  const [procedencia, setProcedencia] = useState("");
  const [tipoLeche, setTipoLeche] = useState("Entera");
  const [litros, setLitros] = useState("");
  const [turno, setTurno] = useState("");
  const [observacion, setObservacion] = useState("");
  const [guardando, setGuardando] = useState(false);
  const [error, setError] = useState("");

  const enviar = async (evento: React.FormEvent<HTMLFormElement>) => {
    evento.preventDefault();
    setError("");
    setGuardando(true);

    try {
      await crearRecepcion({
        fecha,
        hora: hora || undefined,
        guia: guia || undefined,
        vehiculo: vehiculo ? Number(vehiculo) : undefined,
        modulo: modulo || undefined,
        procedencia: procedencia || undefined,
        tipo_leche: tipoLeche,
        litros,
        turno: turno || undefined,
        observacion: observacion || undefined,
      });
      alGuardar();
      alCerrar();
    } catch (error) {
      if (axios.isAxiosError(error) && error.response) {
        const datos = error.response.data;
        setError(
          typeof datos === "object" && datos !== null
            ? Object.entries(datos).map(([campo, errores]) => `${campo}: ${errores}`).join(" · ")
            : "No se pudo registrar la llegada.",
        );
      } else {
        setError("No se pudo conectar con el servidor.");
      }
      setGuardando(false);
    }
  };

  const etiqueta = "mb-1.5 block text-xs font-semibold text-slate-600";
  const campo = "h-11 w-full rounded-xl border border-slate-200 bg-white px-3.5 text-sm text-slate-800 outline-none transition placeholder:text-slate-300 focus:border-emerald-500 focus:ring-4 focus:ring-emerald-500/10";

  return (
    <div className="fixed inset-0 z-50 overflow-y-auto bg-slate-950/50 p-3 backdrop-blur-[2px] sm:p-6">
      <div className="mx-auto w-full max-w-4xl overflow-hidden rounded-3xl bg-[#f7f9f8] shadow-2xl shadow-slate-950/20">
        <div className="flex items-center justify-between border-b border-slate-200 bg-white px-6 py-5 sm:px-8">
          <div><p className="text-xs font-semibold uppercase tracking-[0.14em] text-emerald-700">Etapa 1 · Llegada</p><h2 className="mt-1 text-xl font-semibold tracking-tight text-slate-950">Registrar módulo recibido</h2></div>
          <button type="button" onClick={alCerrar} className="rounded-xl border border-slate-200 p-2 text-slate-400 transition hover:bg-slate-50 hover:text-slate-700" aria-label="Cerrar"><X className="h-5 w-5" /></button>
        </div>

        <form onSubmit={enviar}>
          <div className="space-y-5 p-5 sm:p-8">
            <div className="rounded-2xl border border-blue-200 bg-blue-50 px-5 py-4 text-sm text-blue-800">
              <p className="font-semibold">Registra una fila por cada módulo del camión.</p>
              <p className="mt-1 text-xs leading-5 text-blue-700">Si el camión trae más de un módulo, repite la guía y el vehículo indicando Módulo 1, Módulo 2, etc. Cada uno recibirá su propia muestra y decisión.</p>
            </div>

            <section className="rounded-2xl border border-slate-200 bg-white p-5 sm:p-6">
              <div className="mb-5 flex items-center gap-3"><span className="rounded-xl bg-emerald-50 p-2 text-emerald-700"><Truck className="h-5 w-5" /></span><div><h3 className="font-semibold text-slate-900">Ingreso del camión</h3><p className="text-xs text-slate-400">Datos compartidos por la carga transportada</p></div></div>
              <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
                <div><label className={etiqueta}>Fecha *</label><input aria-label="Fecha" type="date" className={campo} value={fecha} onChange={(e) => setFecha(e.target.value)} required /></div>
                <div><label className={etiqueta}>Hora de llegada</label><input aria-label="Hora de llegada" type="time" className={campo} value={hora} onChange={(e) => setHora(e.target.value)} /></div>
                <div><label className={etiqueta}>Guía / recolección</label><input aria-label="Guía o recolección" className={campo} value={guia} onChange={(e) => setGuia(e.target.value)} placeholder="Ej. GR-2048" /></div>
                <div className="sm:col-span-2"><label className={etiqueta}>Camión *</label><select aria-label="Camión" className={campo} value={vehiculo} onChange={(e) => setVehiculo(e.target.value)} required><option value="">Seleccionar camión</option>{vehiculos.map((item) => <option key={item.id} value={item.id}>{item.placa}{item.transportista ? ` · ${item.transportista}` : ""}</option>)}</select></div>
                <div><label className={etiqueta}>Turno</label><select aria-label="Turno" className={campo} value={turno} onChange={(e) => setTurno(e.target.value)}><option value="">Seleccionar</option><option value="A">Turno A</option><option value="B">Turno B</option><option value="C">Turno C</option></select></div>
              </div>
            </section>

            <section className="rounded-2xl border border-slate-200 bg-white p-5 sm:p-6">
              <div className="mb-5 flex items-center gap-3"><span className="rounded-xl bg-violet-50 p-2 text-violet-700"><Layers3 className="h-5 w-5" /></span><div><h3 className="font-semibold text-slate-900">Módulo recibido</h3><p className="text-xs text-slate-400">Esta será la unidad que se muestrea, aprueba y descarga</p></div></div>
              <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
                <div><label className={etiqueta}>Identificador del módulo *</label><input aria-label="Identificador del módulo" className={campo} value={modulo} onChange={(e) => setModulo(e.target.value)} placeholder="Ej. Módulo 1" required /></div>
                <div><label className={etiqueta}>Procedencia</label><select aria-label="Procedencia" className={campo} value={procedencia} onChange={(e) => setProcedencia(e.target.value)}><option value="">Seleccionar</option><option value="Nestlé">Nestlé</option><option value="P. Unión">P. Unión</option></select></div>
                <div><label className={etiqueta}>Tipo de leche *</label><select aria-label="Tipo de leche" className={campo} value={tipoLeche} onChange={(e) => setTipoLeche(e.target.value)} required><option value="Entera">Entera</option><option value="Descremada">Descremada</option></select></div>
                <div><label className={etiqueta}>Litros declarados *</label><input aria-label="Litros declarados" type="number" step="0.01" min="0.01" className={campo} value={litros} onChange={(e) => setLitros(e.target.value)} placeholder="0" required /></div>
              </div>
            </section>

            <section className="rounded-2xl border border-slate-200 bg-white p-5 sm:p-6"><label className={etiqueta}>Observaciones del ingreso</label><textarea aria-label="Observaciones del ingreso" className={`${campo} h-auto py-3`} rows={3} value={observacion} onChange={(e) => setObservacion(e.target.value)} placeholder="Estado del sello, temperatura de origen u otra información…" /></section>

            <div className="grid gap-2 rounded-2xl border border-slate-200 bg-white p-4 sm:grid-cols-[1fr_auto_1fr_auto_1fr] sm:items-center">
              <div className="flex items-center gap-2 text-xs font-semibold text-slate-700"><Truck className="h-4 w-4 text-emerald-600" />Llegada</div><ArrowRight className="hidden h-4 w-4 text-slate-300 sm:block" /><div className="flex items-center gap-2 text-xs font-medium text-slate-500"><FlaskConical className="h-4 w-4" />Muestra y Calidad</div><ArrowRight className="hidden h-4 w-4 text-slate-300 sm:block" /><div className="flex items-center gap-2 text-xs font-medium text-slate-500"><Warehouse className="h-4 w-4" />Asignación de silo</div>
            </div>
          </div>

          {error && <div className="mx-5 mb-5 rounded-xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700 sm:mx-8">{error}</div>}
          <div className="flex items-center justify-end gap-3 border-t border-slate-200 bg-white px-6 py-5 sm:px-8"><button type="button" onClick={alCerrar} className="h-11 rounded-xl px-5 text-sm font-semibold text-slate-600 transition hover:bg-slate-100">Cancelar</button><button type="submit" disabled={guardando} className="h-11 rounded-xl bg-emerald-700 px-6 text-sm font-semibold text-white shadow-sm transition hover:bg-emerald-800 disabled:cursor-wait disabled:opacity-60">{guardando ? "Registrando…" : "Registrar y enviar a muestreo"}</button></div>
        </form>
      </div>
    </div>
  );
}


export default FormularioRecepcion;
