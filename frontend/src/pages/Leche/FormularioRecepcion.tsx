import { useEffect, useState } from "react";
import axios from "axios";
import {
  Clock3, Layers3, Plus, Scale, SprayCan, Trash2, Truck, Warehouse, X,
} from "lucide-react";

import {
  obtenerCatalogosFlujo, registrarLlegadaCamion,
  type CatalogosFlujoRecepcion, type Vehiculo,
} from "../../services/recepcion.service";
import { obtenerCargasPendientes, type CargaEsperada } from "../../services/recoleccion.service";

interface Props {
  vehiculos: Vehiculo[];
  alCerrar: () => void;
  alGuardar: () => void;
}

interface ModuloFormulario {
  clave: number;
  numero: number;
  crioscopia: string;
  carga_recoleccion?: number;
}

const hoy = () => new Date().toISOString().slice(0, 10);
const nuevoModulo = (clave: number, numero: number): ModuloFormulario => ({
  clave,
  numero,
  crioscopia: "",
});

/* Tri-estado: "" viaja como "no se registró" (null), distinto de "No". */
function SelectTriEstado({
  className, valor, onChange, etiqueta,
}: {
  className: string;
  valor: "" | "true" | "false";
  onChange: (valor: "" | "true" | "false") => void;
  etiqueta: string;
}) {
  return (
    <select
      aria-label={etiqueta}
      className={className}
      value={valor}
      onChange={(e) => onChange(e.target.value as "" | "true" | "false")}
    >
      <option value="">Sin registrar</option>
      <option value="true">Sí</option>
      <option value="false">No</option>
    </select>
  );
}

function Encabezado({
  icono: Icono, tono, titulo, detalle,
}: {
  icono: typeof Truck;
  tono: string;
  titulo: string;
  detalle: string;
}) {
  return (
    <div className="mb-5 flex items-center gap-3">
      <span className={`rounded-xl p-2 ${tono}`}><Icono className="h-5 w-5" /></span>
      <div><h3 className="font-semibold text-slate-900">{titulo}</h3><p className="text-xs text-slate-600">{detalle}</p></div>
    </div>
  );
}

function FormularioRecepcion({ vehiculos, alCerrar, alGuardar }: Props) {
  // Identificación
  const [fecha, setFecha] = useState(hoy());
  const [hora, setHora] = useState("");
  const [guia, setGuia] = useState("");
  const [vehiculo, setVehiculo] = useState("");
  const [procedencia, setProcedencia] = useState("");
  const [turno, setTurno] = useState("");

  // Destino
  const [tipoLeche, setTipoLeche] = useState("Entera");
  const [certificada, setCertificada] = useState<"" | "true" | "false">("");
  const [uso, setUso] = useState("");
  const [usoNumero, setUsoNumero] = useState("");

  // Cantidades
  const [litros, setLitros] = useState("");
  const [kgRomana, setKgRomana] = useState("");

  // Módulos
  const [cargasEsperadas, setCargasEsperadas] = useState<CargaEsperada[]>([]);
  const [modulos, setModulos] = useState<ModuloFormulario[]>([nuevoModulo(1, 1)]);
  const [siguienteClave, setSiguienteClave] = useState(2);

  // Tiempos
  const [horaPrograma, setHoraPrograma] = useState("");
  const [horaArriboPorteria, setHoraArriboPorteria] = useState("");
  const [horaIngreso, setHoraIngreso] = useState("");
  const [horaInicioDescarga, setHoraInicioDescarga] = useState("");
  const [horaTerminoDescarga, setHoraTerminoDescarga] = useState("");
  const [horaInicioCip, setHoraInicioCip] = useState("");
  const [horaTerminoCip, setHoraTerminoCip] = useState("");
  const [horaSalida, setHoraSalida] = useState("");

  // Higiene del camión
  const [lavadoRuedas, setLavadoRuedas] = useState<"" | "true" | "false">("");
  const [relavado, setRelavado] = useState<"" | "true" | "false">("");
  const [recambioDilucion, setRecambioDilucion] = useState("");
  const [phCamion, setPhCamion] = useState("");

  const [observacion, setObservacion] = useState("");

  const [catalogos, setCatalogos] = useState<CatalogosFlujoRecepcion | null>(null);
  const [guardando, setGuardando] = useState(false);
  const [error, setError] = useState("");

  // Los catálogos de los desplegables se sirven desde el backend y van
  // aparte: si este endpoint falla, el resto del formulario sigue usable.
  useEffect(() => {
    void obtenerCatalogosFlujo().then(setCatalogos).catch(() => setCatalogos(null));
    void obtenerCargasPendientes().then(setCargasEsperadas).catch(() => setCargasEsperadas([]));
  }, []);

  const muestraNumeroDeUso = Boolean(uso && catalogos?.usos_numerados.includes(uso));

  const cambiarUso = (valor: string) => {
    setUso(valor);
    if (!catalogos?.usos_numerados.includes(valor)) setUsoNumero("");
  };

  const numerosDisponibles = (claveActual: number) => {
    const usados = new Set(
      modulos.filter((item) => item.clave !== claveActual).map((item) => item.numero),
    );
    return [1, 2, 3, 4].filter((n) => !usados.has(n));
  };

  const cargasDisponibles = (claveActual: number) => {
    const usadas = new Set(
      modulos
        .filter((item) => item.clave !== claveActual && item.carga_recoleccion)
        .map((item) => item.carga_recoleccion),
    );
    return cargasEsperadas.filter((carga) => !usadas.has(carga.id));
  };

  const cambiarModulo = (
    clave: number,
    cambios: Partial<Pick<ModuloFormulario, "numero" | "crioscopia" | "carga_recoleccion">>,
  ) => {
    setModulos((actuales) => actuales.map((item) =>
      item.clave === clave ? { ...item, ...cambios } : item,
    ));
  };

  const agregarModulo = () => {
    if (modulos.length >= 4) return;
    const usados = new Set(modulos.map((item) => item.numero));
    const numero = [1, 2, 3, 4].find((n) => !usados.has(n));
    if (numero === undefined) return;
    setModulos((actuales) => [...actuales, nuevoModulo(siguienteClave, numero)]);
    setSiguienteClave((actual) => actual + 1);
  };

  const quitarModulo = (clave: number) => {
    setModulos((actuales) => actuales.filter((item) => item.clave !== clave));
  };

  const enviar = async (evento: React.FormEvent<HTMLFormElement>) => {
    evento.preventDefault();
    setError("");
    setGuardando(true);
    try {
      const cabecera = {
        fecha,
        hora: hora || undefined,
        guia: guia || undefined,
        vehiculo: Number(vehiculo),
        procedencia: procedencia || undefined,
        tipo_leche: tipoLeche,
        turno: turno || undefined,
        kg_romana: kgRomana || undefined,
        certificada: certificada === "" ? undefined : certificada === "true",
        uso: uso || undefined,
        uso_numero: muestraNumeroDeUso && usoNumero ? Number(usoNumero) : undefined,
        hora_programa: horaPrograma || undefined,
        hora_arribo_porteria: horaArriboPorteria || undefined,
        hora_ingreso: horaIngreso || undefined,
        hora_inicio_descarga: horaInicioDescarga || undefined,
        hora_termino_descarga: horaTerminoDescarga || undefined,
        hora_inicio_cip: horaInicioCip || undefined,
        hora_termino_cip: horaTerminoCip || undefined,
        hora_salida: horaSalida || undefined,
        lavado_ruedas: lavadoRuedas === "" ? undefined : lavadoRuedas === "true",
        relavado: relavado === "" ? undefined : relavado === "true",
        recambio_dilucion: recambioDilucion || undefined,
        ph_camion: phCamion || undefined,
        observacion: observacion || undefined,
      };

      await registrarLlegadaCamion({
        ...cabecera,
        litros,
        modulos: modulos.map(({ numero, crioscopia, carga_recoleccion }) => ({
          numero,
          crioscopia: crioscopia || undefined,
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
          <div><p className="text-xs font-bold uppercase tracking-[0.16em] text-emerald-700">Etapa 1 · Recepción</p><h2 className="mt-1 text-xl font-semibold text-slate-950">Registrar llegada del camión</h2><p className="mt-1 text-xs text-slate-600">Un registro por camión, con la crioscopía de cada módulo aparte.</p></div>
          <button type="button" onClick={alCerrar} className="rounded-xl border border-slate-200 p-2 text-slate-600 hover:bg-slate-50" aria-label="Cerrar"><X className="h-5 w-5" /></button>
        </div>

        <form onSubmit={enviar}>
          <div className="space-y-5 p-5 sm:p-8">

            <section className="rounded-2xl border border-slate-200 bg-white p-5 sm:p-6">
              <Encabezado icono={Truck} tono="bg-emerald-50 text-emerald-700" titulo="Identificación" detalle="Fecha, guía y camión que llega." />
              <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
                <div><label className={etiqueta}>Fecha *</label><input type="date" className={campo} value={fecha} onChange={(e) => setFecha(e.target.value)} required /></div>
                <div><label className={etiqueta}>Hora de llegada</label><input type="time" className={campo} value={hora} onChange={(e) => setHora(e.target.value)} /></div>
                <div><label className={etiqueta}>Guía / recepción</label><input className={campo} value={guia} onChange={(e) => setGuia(e.target.value)} placeholder="Ej. GR-2048" /></div>
                <div><label className={etiqueta}>Turno</label><select className={campo} value={turno} onChange={(e) => setTurno(e.target.value)}><option value="">Seleccionar</option><option value="A">Turno A</option><option value="B">Turno B</option><option value="C">Turno C</option></select></div>
                <div className="sm:col-span-2"><label className={etiqueta}>Camión *</label><select className={campo} value={vehiculo} onChange={(e) => setVehiculo(e.target.value)} required><option value="">Seleccionar camión</option>{vehiculos.map((item) => <option key={item.id} value={item.id}>{item.placa}{item.transportista ? ` · ${item.transportista}` : ""}</option>)}</select></div>
                <div><label className={etiqueta}>Procedencia</label><select className={campo} value={procedencia} onChange={(e) => setProcedencia(e.target.value)}><option value="">Seleccionar</option>{(catalogos?.procedencias ?? []).map((op) => <option key={op.valor} value={op.valor}>{op.etiqueta}</option>)}</select></div>
              </div>
            </section>

            <section className="rounded-2xl border border-blue-200 bg-white p-5 sm:p-6">
              <Encabezado icono={Warehouse} tono="bg-blue-50 text-blue-700" titulo="Destino" detalle="A qué va la leche de este camión." />
              <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
                <div><label className={etiqueta}>Tipo de leche *</label><select className={campo} value={tipoLeche} onChange={(e) => setTipoLeche(e.target.value)} required><option value="Entera">Entera</option><option value="Descremada">Descremada</option></select></div>
                <div><label className={etiqueta}>Leche certificada</label><SelectTriEstado className={campo} valor={certificada} onChange={setCertificada} etiqueta="Leche certificada" /></div>
                <div><label className={etiqueta}>Uso</label><select className={campo} value={uso} onChange={(e) => cambiarUso(e.target.value)}><option value="">Seleccionar</option>{(catalogos?.usos ?? []).map((op) => <option key={op.valor} value={op.valor}>{op.etiqueta}</option>)}</select></div>
                {muestraNumeroDeUso && (
                  <div><label className={etiqueta}>N° de destino *</label><input type="number" min="1" step="1" className={campo} value={usoNumero} onChange={(e) => setUsoNumero(e.target.value)} required /></div>
                )}
              </div>
              {/* El silo de destino no se pide aquí: `silo` es de solo lectura en el
                  registro del camión y se asigna después, cuando Calidad libera la
                  recepción (acción «Asignar silo»). */}
            </section>

            <section className="rounded-2xl border border-amber-200 bg-white p-5 sm:p-6">
              <Encabezado icono={Scale} tono="bg-amber-50 text-amber-700" titulo="Cantidades" detalle="Litros y el pesaje real en romana." />
              <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
                <div><label className={etiqueta}>Litros *</label><input type="number" min="0.01" step="0.01" className={campo} value={litros} onChange={(e) => setLitros(e.target.value)} required /></div>
                <div><label className={etiqueta}>Kg romana</label><input type="number" min="0" step="0.01" className={campo} value={kgRomana} onChange={(e) => setKgRomana(e.target.value)} /></div>
                <div className="sm:col-span-2 flex items-end"><p className="text-xs text-slate-600">Los kg de guía se calculan solos desde los litros (columna I del formato); se verán en la ficha del camión una vez registrado, junto a la diferencia contra la romana.</p></div>
              </div>
            </section>

            <section className="rounded-2xl border border-violet-200 bg-white p-5 sm:p-6">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <Encabezado icono={Layers3} tono="bg-violet-50 text-violet-700" titulo="Módulos" detalle="Un número (1 a 4) y su crioscopía; litros y destino son del camión." />
              </div>
              <div className="space-y-3">
                {modulos.map((item, indice) => (
                  <div key={item.clave} className="grid gap-3 rounded-2xl bg-slate-50 p-4 sm:grid-cols-[auto_auto_1fr_1fr_auto] sm:items-end">
                    <span className="flex h-9 w-9 items-center justify-center rounded-full bg-violet-700 text-sm font-bold text-white">{indice + 1}</span>
                    <div><label className={etiqueta}>N° de módulo *</label><select className={campo} value={item.numero} onChange={(e) => cambiarModulo(item.clave, { numero: Number(e.target.value) })} required>{numerosDisponibles(item.clave).map((n) => <option key={n} value={n}>Módulo {n}</option>)}</select></div>
                    <div><label className={etiqueta}>Crioscopía (°C)</label><input type="number" step="any" className={campo} value={item.crioscopia} onChange={(e) => cambiarModulo(item.clave, { crioscopia: e.target.value })} /></div>
                    <div>
                      <label className={etiqueta}>Carga de Recolección (opcional)</label>
                      <select
                        className={campo}
                        value={item.carga_recoleccion ?? ""}
                        onChange={(e) => cambiarModulo(item.clave, {
                          carga_recoleccion: e.target.value ? Number(e.target.value) : undefined,
                        })}
                      >
                        <option value="">Sin vincular</option>
                        {cargasDisponibles(item.clave).map((carga) => (
                          <option key={carga.id} value={carga.id}>
                            {carga.vehiculo_placa} · {carga.predio || carga.modulo} · {Number(carga.litros).toLocaleString("es-CL")} L
                          </option>
                        ))}
                      </select>
                    </div>
                    <button type="button" onClick={() => quitarModulo(item.clave)} disabled={modulos.length === 1} className="flex h-11 w-11 items-center justify-center rounded-xl text-rose-600 hover:bg-rose-50 disabled:opacity-25" aria-label="Quitar módulo"><Trash2 className="h-4 w-4" /></button>
                  </div>
                ))}
              </div>
              <button type="button" onClick={agregarModulo} disabled={modulos.length >= 4} className="mt-4 inline-flex h-10 items-center gap-2 rounded-xl border border-violet-200 px-4 text-sm font-semibold text-violet-700 hover:bg-violet-50 disabled:opacity-40"><Plus className="h-4 w-4" />Agregar otro módulo</button>
            </section>

            <section className="rounded-2xl border border-sky-200 bg-white p-5 sm:p-6">
              <Encabezado icono={Clock3} tono="bg-sky-50 text-sky-700" titulo="Tiempos" detalle="Las ocho marcas horarias del formato." />
              <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
                <div><label className={etiqueta}>Hora programa</label><input type="time" className={campo} value={horaPrograma} onChange={(e) => setHoraPrograma(e.target.value)} /></div>
                <div><label className={etiqueta}>Arribo a portería</label><input type="time" className={campo} value={horaArriboPorteria} onChange={(e) => setHoraArriboPorteria(e.target.value)} /></div>
                <div><label className={etiqueta}>Hora de ingreso</label><input type="time" className={campo} value={horaIngreso} onChange={(e) => setHoraIngreso(e.target.value)} /></div>
                <div><label className={etiqueta}>Inicio de descarga</label><input type="time" className={campo} value={horaInicioDescarga} onChange={(e) => setHoraInicioDescarga(e.target.value)} /></div>
                <div><label className={etiqueta}>Término de descarga</label><input type="time" className={campo} value={horaTerminoDescarga} onChange={(e) => setHoraTerminoDescarga(e.target.value)} /></div>
                <div><label className={etiqueta}>Inicio del lavado CIP</label><input type="time" className={campo} value={horaInicioCip} onChange={(e) => setHoraInicioCip(e.target.value)} /></div>
                <div><label className={etiqueta}>Término del lavado CIP</label><input type="time" className={campo} value={horaTerminoCip} onChange={(e) => setHoraTerminoCip(e.target.value)} /></div>
                <div><label className={etiqueta}>Hora de salida</label><input type="time" className={campo} value={horaSalida} onChange={(e) => setHoraSalida(e.target.value)} /></div>
              </div>
            </section>

            <section className="rounded-2xl border border-teal-200 bg-white p-5 sm:p-6">
              <Encabezado icono={SprayCan} tono="bg-teal-50 text-teal-700" titulo="Higiene del camión" detalle="Lavado de ruedas, recambio de dilución y pH del enjuague." />
              <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
                <div><label className={etiqueta}>Lavado de ruedas</label><SelectTriEstado className={campo} valor={lavadoRuedas} onChange={setLavadoRuedas} etiqueta="Lavado de ruedas" /></div>
                <div><label className={etiqueta}>Vuelve a lavarse e ingresa</label><SelectTriEstado className={campo} valor={relavado} onChange={setRelavado} etiqueta="Vuelve a lavarse e ingresa" /></div>
                <div><label className={etiqueta}>Cambio de dilución</label><select className={campo} value={recambioDilucion} onChange={(e) => setRecambioDilucion(e.target.value)}><option value="">Sin registrar</option>{(catalogos?.recambios_dilucion ?? []).map((op) => <option key={op.valor} value={op.valor}>{op.etiqueta}</option>)}</select></div>
                <div><label className={etiqueta}>pH del camión</label><input type="number" step="0.01" min="0" max="14" className={campo} value={phCamion} onChange={(e) => setPhCamion(e.target.value)} placeholder="Del enjuague, no de la leche" /></div>
              </div>
            </section>

            <div><label className={etiqueta}>Observaciones generales</label><textarea className={`${campo} h-auto py-3`} rows={3} value={observacion} onChange={(e) => setObservacion(e.target.value)} /></div>
          </div>

          {error && <div className="mx-5 mb-5 rounded-xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700 sm:mx-8">{error}</div>}
          <div className="flex items-center justify-between gap-3 border-t border-slate-200 bg-white px-6 py-5 sm:px-8"><p className="hidden text-xs text-slate-600 sm:block">Se registrará {modulos.length} módulo{modulos.length === 1 ? "" : "s"} bajo este camión.</p><div className="ml-auto flex gap-3"><button type="button" onClick={alCerrar} className="h-11 rounded-xl px-5 text-sm font-semibold text-slate-600 hover:bg-slate-100">Cancelar</button><button type="submit" disabled={guardando} className="h-11 rounded-xl bg-emerald-700 px-6 text-sm font-semibold text-white hover:bg-emerald-800 disabled:opacity-60">{guardando ? "Registrando…" : "Registrar camión"}</button></div></div>
        </form>
      </div>
    </div>
  );
}

export default FormularioRecepcion;
