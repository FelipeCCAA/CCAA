import { useEffect, useState } from "react";
import axios from "axios";
import { CheckCircle2, Plus, X } from "lucide-react";

import { obtenerVehiculos, type Vehiculo } from "../../services/recepcion.service";
import {
  agregarCarga, cerrarRuta, crearParada, crearRuta, obtenerRutas,
  registrarRecoleccion, type ParadaRuta, type RutaRecoleccion,
} from "../../services/recoleccion.service";
import { puedeEscribir } from "../../services/sesion";

const hoy = () => new Date().toISOString().slice(0, 10);
const fechaHoraLocal = () => {
  const valor = new Date();
  valor.setMinutes(valor.getMinutes() - valor.getTimezoneOffset());
  return valor.toISOString().slice(0, 16);
};
const estadoClase: Record<string, string> = {
  programada: "bg-slate-100 text-slate-600", en_curso: "bg-sky-50 text-sky-700",
  cerrada: "bg-emerald-50 text-emerald-700", pendiente: "bg-amber-50 text-amber-700",
  completada: "bg-emerald-50 text-emerald-700", no_cargada: "bg-rose-50 text-rose-700",
};

function Rutas() {
  const [rutas, setRutas] = useState<RutaRecoleccion[]>([]);
  const [vehiculos, setVehiculos] = useState<Vehiculo[]>([]);
  const [rutaId, setRutaId] = useState<number | null>(null);
  const [nuevaAbierta, setNuevaAbierta] = useState(false);
  const [paradaActiva, setParadaActiva] = useState<ParadaRuta | null>(null);
  const [guardando, setGuardando] = useState(false);
  const [error, setError] = useState("");
  const [rutaNueva, setRutaNueva] = useState({ codigo: `R-${hoy().replaceAll("-", "")}-`, fecha: hoy(), vehiculo: "" });
  const [paradaNueva, setParadaNueva] = useState({ proveedor: "", predio: "", sala: "" });
  const [visita, setVisita] = useState(() => {
    const correlativo = Date.now().toString().slice(-8);
    return { fecha_hora: fechaHoraLocal(), litros: "", temperatura: "", alcohol: "conforme" as "conforme" | "no_conforme", muestra: `M-${correlativo}`, carga: `C-${correlativo}`, modulo: "", estanque: "", litrosCarga: "", observacion: "" };
  });

  const editable = puedeEscribir("recepcion");
  const ruta = rutas.find((item) => item.id === rutaId) ?? null;

  const cargar = async () => {
    try {
      const [rutasData, vehiculosData] = await Promise.all([obtenerRutas(), obtenerVehiculos()]);
      setRutas(rutasData); setVehiculos(vehiculosData);
      setRutaId((actual) => actual && rutasData.some((item) => item.id === actual) ? actual : rutasData[0]?.id ?? null);
    } catch { setError("No se pudo cargar la programación de recolección."); }
  };
  useEffect(() => {
    const tarea = setTimeout(() => { void cargar(); }, 0);
    return () => clearTimeout(tarea);
  }, []);

  const detalleError = (e: unknown, base: string) => {
    if (!axios.isAxiosError(e)) return base;
    const datos = e.response?.data as Record<string, unknown> | undefined;
    if (!datos) return base;
    return String(datos.detail ?? Object.values(datos).flat().join(" "));
  };

  const guardarRuta = async (e: React.FormEvent) => {
    e.preventDefault(); setGuardando(true); setError("");
    try {
      const creada = await crearRuta({ ...rutaNueva, vehiculo: Number(rutaNueva.vehiculo) });
      setNuevaAbierta(false); await cargar(); setRutaId(creada.id);
    } catch (err) { setError(detalleError(err, "No se pudo crear la ruta.")); }
    finally { setGuardando(false); }
  };

  const guardarParada = async (e: React.FormEvent) => {
    e.preventDefault(); if (!ruta) return; setGuardando(true); setError("");
    try {
      await crearParada({ ruta: ruta.id, orden: ruta.paradas.length + 1, ...paradaNueva });
      setParadaNueva({ proveedor: "", predio: "", sala: "" }); await cargar();
    } catch (err) { setError(detalleError(err, "No se pudo agregar el predio.")); }
    finally { setGuardando(false); }
  };

  const guardarVisita = async (e: React.FormEvent) => {
    e.preventDefault(); if (!paradaActiva) return; setGuardando(true); setError("");
    try {
      const registro = await registrarRecoleccion({
        parada: paradaActiva.id, fecha_hora: new Date(visita.fecha_hora).toISOString(),
        litros_medidos: Number(visita.litros), temperatura: visita.temperatura ? Number(visita.temperatura) : undefined,
        alcohol: visita.alcohol, codigo_muestra: visita.alcohol === "conforme" ? visita.muestra : "",
        observacion: visita.observacion,
      });
      if (visita.alcohol === "conforme") await agregarCarga(registro.id, {
        codigo: visita.carga, modulo: visita.modulo, estanque_origen: visita.estanque,
        litros: Number(visita.litrosCarga || visita.litros),
      });
      setParadaActiva(null); await cargar();
    } catch (err) { setError(detalleError(err, "No se pudo registrar la visita.")); }
    finally { setGuardando(false); }
  };

  return <div className="space-y-6">
    {/* El título de la pantalla y los contadores del turno viven ahora en la
        cabecera de la sección y en el Panel. Repetirlos aquí empujaba la
        primera ruta media pantalla hacia abajo, que es el trabajo real. */}
    <header className="flex flex-wrap items-end justify-between gap-4"><div><h2 className="text-lg font-semibold text-slate-900">Rutas de recolección</h2><p className="mt-1 text-sm text-slate-600">Programación, controles en predio y cargas por módulo antes de llegar a recepción.</p></div>{editable && <button onClick={() => setNuevaAbierta(true)} className="flex items-center gap-2 rounded-xl bg-emerald-700 px-4 py-2.5 text-sm font-medium text-white"><Plus className="h-4 w-4"/>Nueva ruta</button>}</header>
    {error && <p className="rounded-xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700">{error}</p>}
    <div className="grid gap-6 xl:grid-cols-[320px_1fr]">
      <section className="rounded-2xl border border-slate-200 bg-white p-3"><h2 className="px-2 pb-3 pt-1 text-sm font-semibold">Rutas recientes</h2><div className="space-y-2">{rutas.map((item) => <button key={item.id} onClick={() => setRutaId(item.id)} className={`w-full rounded-xl border p-3 text-left ${rutaId === item.id ? "border-emerald-300 bg-emerald-50" : "border-transparent bg-slate-50"}`}><div className="flex justify-between gap-2"><span className="font-medium">{item.codigo}</span><span className={`rounded-full px-2 py-0.5 text-[11px] ${estadoClase[item.estado]}`}>{item.estado.replace("_", " ")}</span></div><p className="mt-1 text-xs text-slate-600">{item.fecha} · {item.vehiculo_placa} · {item.paradas.length} predios</p></button>)}</div></section>
      <section className="rounded-2xl border border-slate-200 bg-white p-5">{!ruta ? <p className="py-12 text-center text-sm text-slate-600">Crea o selecciona una ruta.</p> : <><div className="flex flex-wrap justify-between gap-3 border-b pb-4"><div><h2 className="font-semibold">{ruta.codigo} · {ruta.vehiculo_placa}</h2><p className="mt-1 text-xs text-slate-600">Cada predio debe quedar completado o no cargado.</p></div>{editable && !["cerrada","cancelada"].includes(ruta.estado) && <button onClick={() => void cerrarRuta(ruta.id).then(cargar).catch((e) => setError(detalleError(e,"No se pudo cerrar.")))} className="rounded-xl border px-3 py-2 text-xs">Cerrar ruta</button>}</div><div className="mt-4 space-y-3">{ruta.paradas.map((p) => <article key={p.id} className="flex flex-wrap items-center gap-3 rounded-xl border p-4"><span className="flex h-8 w-8 items-center justify-center rounded-full bg-slate-100 text-sm font-semibold">{p.orden}</span><div className="flex-1"><p className="font-medium">{p.predio}</p><p className="text-xs text-slate-600">{p.proveedor}{p.sala ? ` · ${p.sala}` : ""}</p></div><span className={`rounded-full px-2 py-1 text-xs ${estadoClase[p.estado]}`}>{p.estado.replace("_", " ")}</span>{editable && p.estado === "pendiente" && <button onClick={() => setParadaActiva(p)} className="rounded-lg bg-emerald-700 px-3 py-2 text-xs text-white">Registrar visita</button>}</article>)}</div>{editable && !["cerrada","cancelada"].includes(ruta.estado) && <form onSubmit={guardarParada} className="mt-5 grid gap-3 rounded-xl bg-slate-50 p-4 sm:grid-cols-4"><input required placeholder="Proveedor" value={paradaNueva.proveedor} onChange={(e)=>setParadaNueva({...paradaNueva,proveedor:e.target.value})} className="rounded-lg border px-3 py-2 text-sm"/><input required placeholder="Predio" value={paradaNueva.predio} onChange={(e)=>setParadaNueva({...paradaNueva,predio:e.target.value})} className="rounded-lg border px-3 py-2 text-sm"/><input placeholder="Sala" value={paradaNueva.sala} onChange={(e)=>setParadaNueva({...paradaNueva,sala:e.target.value})} className="rounded-lg border px-3 py-2 text-sm"/><button disabled={guardando} className="rounded-lg bg-slate-800 text-sm text-white">Agregar predio</button></form>}</>}</section>
    </div>
    {nuevaAbierta && <div className="fixed inset-0 z-[70] flex items-center justify-center bg-slate-950/45 p-4"><form onSubmit={guardarRuta} className="w-full max-w-lg rounded-2xl bg-white p-6"><ModalTitulo titulo="Nueva ruta" cerrar={() => setNuevaAbierta(false)}/><div className="mt-5 grid gap-4 sm:grid-cols-2"><Campo label="Código"><input required value={rutaNueva.codigo} onChange={(e)=>setRutaNueva({...rutaNueva,codigo:e.target.value})} className="control"/></Campo><Campo label="Fecha"><input required type="date" value={rutaNueva.fecha} onChange={(e)=>setRutaNueva({...rutaNueva,fecha:e.target.value})} className="control"/></Campo><Campo label="Camión" ancho><select required value={rutaNueva.vehiculo} onChange={(e)=>setRutaNueva({...rutaNueva,vehiculo:e.target.value})} className="control bg-white"><option value="">Selecciona</option>{vehiculos.map((v)=><option key={v.id} value={v.id}>{v.placa} · {v.transportista || v.numero}</option>)}</select></Campo></div><Boton guardando={guardando} texto="Crear ruta"/></form></div>}
    {paradaActiva && <div className="fixed inset-0 z-[70] flex items-center justify-center overflow-y-auto bg-slate-950/45 p-4"><form onSubmit={guardarVisita} className="my-6 w-full max-w-2xl rounded-2xl bg-white p-6"><ModalTitulo titulo={`Visita · ${paradaActiva.predio}`} cerrar={() => setParadaActiva(null)}/><div className="mt-5 grid gap-4 sm:grid-cols-2"><Campo label="Fecha y hora"><input required type="datetime-local" value={visita.fecha_hora} onChange={(e)=>setVisita({...visita,fecha_hora:e.target.value})} className="control"/></Campo><Campo label="Litros medidos"><input required type="number" min="0.01" step="0.01" value={visita.litros} onChange={(e)=>setVisita({...visita,litros:e.target.value})} className="control"/></Campo><Campo label="Temperatura °C"><input type="number" step="0.01" value={visita.temperatura} onChange={(e)=>setVisita({...visita,temperatura:e.target.value})} className="control"/></Campo><Campo label="Prueba de alcohol"><select value={visita.alcohol} onChange={(e)=>setVisita({...visita,alcohol:e.target.value as "conforme"|"no_conforme"})} className="control bg-white"><option value="conforme">Conforme · cargar</option><option value="no_conforme">No conforme · no cargar</option></select></Campo>{visita.alcohol === "conforme" && <><Campo label="Código de muestra"><input required value={visita.muestra} onChange={(e)=>setVisita({...visita,muestra:e.target.value})} className="control"/></Campo><Campo label="Código de carga"><input required value={visita.carga} onChange={(e)=>setVisita({...visita,carga:e.target.value})} className="control"/></Campo><Campo label="Módulo"><input required value={visita.modulo} onChange={(e)=>setVisita({...visita,modulo:e.target.value})} className="control"/></Campo><Campo label="Estanque de origen"><input value={visita.estanque} onChange={(e)=>setVisita({...visita,estanque:e.target.value})} className="control"/></Campo><Campo label="Litros cargados" ancho><input type="number" min="0.01" step="0.01" placeholder="Vacío = litros medidos" value={visita.litrosCarga} onChange={(e)=>setVisita({...visita,litrosCarga:e.target.value})} className="control"/></Campo></>}<Campo label="Observación" ancho><textarea value={visita.observacion} onChange={(e)=>setVisita({...visita,observacion:e.target.value})} className="control"/></Campo></div><Boton guardando={guardando} texto={visita.alcohol === "conforme" ? "Guardar muestra y carga" : "Registrar como no cargada"}/></form></div>}
  </div>;
}

function Campo({label,ancho=false,children}:{label:string;ancho?:boolean;children:React.ReactNode}) { return <label className={`text-sm text-slate-600 ${ancho ? "sm:col-span-2" : ""}`}>{label}<div className="mt-1 [&_.control]:w-full [&_.control]:rounded-xl [&_.control]:border [&_.control]:border-slate-200 [&_.control]:px-3 [&_.control]:py-2.5">{children}</div></label>; }
function ModalTitulo({titulo,cerrar}:{titulo:string;cerrar:()=>void}) { return <div className="flex items-center justify-between"><div><p className="text-xs font-semibold uppercase tracking-wider text-emerald-700">Recolección</p><h2 className="mt-1 text-xl font-semibold">{titulo}</h2></div><button type="button" onClick={cerrar} className="rounded-lg p-2 text-slate-600 hover:bg-slate-100"><X className="h-5 w-5"/></button></div>; }
function Boton({guardando,texto}:{guardando:boolean;texto:string}) { return <button disabled={guardando} className="mt-6 flex w-full items-center justify-center gap-2 rounded-xl bg-emerald-700 px-4 py-3 font-medium text-white disabled:opacity-50"><CheckCircle2 className="h-4 w-4"/>{texto}</button>; }

export default Rutas;
