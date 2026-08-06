import { useCallback, useEffect, useMemo, useState } from "react";
import axios from "axios";
import {
  AlertTriangle,
  ArrowDownToLine,
  Beaker,
  CheckCircle2,
  ChevronLeft,
  ChevronRight,
  Clock3,
  Droplets,
  Plus,
  RefreshCw,
  Search,
  ShieldCheck,
  SlidersHorizontal,
  Truck,
  Warehouse,
  type LucideIcon,
} from "lucide-react";

import {
  buscarRecepciones,
  descargarRecepcion,
  ESTADOS_RECEPCION,
  obtenerOcupacion,
  obtenerSilos,
  obtenerVehiculos,
  type Ocupacion,
  type Recepcion as RecepcionTipo,
  type Silo,
  type Vehiculo,
} from "../../services/recepcion.service";
import { puedeEscribir } from "../../services/sesion";
import AccionRecepcion, { type AccionFlujo } from "./AccionRecepcion";
import FormularioRecepcion from "./FormularioRecepcion";


const formato = new Intl.NumberFormat("es-CL", { maximumFractionDigits: 0 });
const POR_PAGINA = 50;

const ESTILO_ESTADO: Record<string, string> = {
  registrada: "border-slate-200 bg-slate-50 text-slate-700",
  muestreada: "border-sky-200 bg-sky-50 text-sky-700",
  analizada: "border-indigo-200 bg-indigo-50 text-indigo-700",
  liberada: "border-emerald-200 bg-emerald-50 text-emerald-700",
  retenida: "border-amber-200 bg-amber-50 text-amber-800",
  descargada: "border-blue-200 bg-blue-50 text-blue-700",
  cerrada: "border-slate-200 bg-slate-100 text-slate-500",
};

const PASOS = [
  { etiqueta: "En espera", icono: Truck, contar: (r: RecepcionTipo) => r.estado === "registrada" },
  { etiqueta: "Muestra tomada", icono: Beaker, contar: (r: RecepcionTipo) => r.estado === "muestreada" },
  { etiqueta: "Retenida", icono: ShieldCheck, contar: (r: RecepcionTipo) => r.estado === "retenida" },
  { etiqueta: "Por asignar", icono: Warehouse, contar: (r: RecepcionTipo) => r.estado === "liberada" && !r.silo },
  { etiqueta: "Lista para descarga", icono: ArrowDownToLine, contar: (r: RecepcionTipo) => r.estado === "liberada" && Boolean(r.silo) },
  { etiqueta: "En silo", icono: CheckCircle2, contar: (r: RecepcionTipo) => ["descargada", "cerrada"].includes(r.estado) },
];

type VistaFlujo = "espera" | "calidad" | "asignacion" | "historial";

const VISTAS: { valor: VistaFlujo; etiqueta: string; descripcion: string }[] = [
  { valor: "espera", etiqueta: "1. Muestreo", descripcion: "Módulos recién recibidos" },
  { valor: "calidad", etiqueta: "2. Calidad", descripcion: "Muestras por decidir" },
  { valor: "asignacion", etiqueta: "3. Silo y descarga", descripcion: "Cargas aprobadas" },
  { valor: "historial", etiqueta: "4. Historial", descripcion: "Módulos descargados" },
];


function formatearFecha(fecha: string) {
  const [anio, mes, dia] = fecha.split("-").map(Number);
  if (!anio || !mes || !dia) return fecha;
  return new Intl.DateTimeFormat("es-CL", { day: "2-digit", month: "short" }).format(
    new Date(anio, mes - 1, dia),
  );
}


function Indicador({
  etiqueta,
  valor,
  detalle,
  icono: Icono,
  tono = "slate",
}: {
  etiqueta: string;
  valor: string;
  detalle: string;
  icono: LucideIcon;
  tono?: "slate" | "green" | "amber" | "blue";
}) {
  const tonos = {
    slate: "bg-slate-100 text-slate-600",
    green: "bg-emerald-50 text-emerald-700",
    amber: "bg-amber-50 text-amber-700",
    blue: "bg-blue-50 text-blue-700",
  };

  return (
    <article className="rounded-2xl border border-slate-200/80 bg-white p-5 shadow-[0_1px_2px_rgba(15,23,42,0.03)]">
      <div className="flex items-start justify-between gap-4">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.12em] text-slate-400">
            {etiqueta}
          </p>
          <p className="mt-2 text-2xl font-semibold tracking-tight text-slate-900">{valor}</p>
          <p className="mt-1 text-xs text-slate-500">{detalle}</p>
        </div>
        <span className={`rounded-xl p-2.5 ${tonos[tono]}`}>
          <Icono className="h-5 w-5" strokeWidth={1.8} />
        </span>
      </div>
    </article>
  );
}


function TarjetaSilo({ ocupacion }: { ocupacion: Ocupacion["silos"][number] }) {
  const ancho = Math.min(100, Math.max(0, ocupacion.pct));
  const alerta = ocupacion.negativo || ocupacion.excedido;
  const color = ocupacion.negativo
    ? "bg-rose-500"
    : ocupacion.excedido
      ? "bg-amber-500"
      : ocupacion.pct >= 85
        ? "bg-amber-500"
        : "bg-emerald-600";

  return (
    <article className="rounded-2xl border border-slate-200/80 bg-white p-5 shadow-[0_1px_2px_rgba(15,23,42,0.03)]">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <span className="rounded-xl bg-slate-100 p-2 text-slate-600">
            <Warehouse className="h-4 w-4" strokeWidth={1.8} />
          </span>
          <div>
            <p className="font-semibold text-slate-900">{ocupacion.codigo}</p>
            <p className="text-xs text-slate-400">Silo de almacenamiento</p>
          </div>
        </div>
        <span className={`text-sm font-semibold ${alerta ? "text-amber-700" : "text-slate-700"}`}>
          {ocupacion.pct}%
        </span>
      </div>

      <div className="mt-5 h-2 overflow-hidden rounded-full bg-slate-100">
        <div className={`h-full rounded-full transition-[width] ${color}`} style={{ width: `${ancho}%` }} />
      </div>

      <div className="mt-3 flex items-baseline justify-between gap-3">
        <p className="text-sm font-semibold text-slate-800">{formato.format(ocupacion.litros)} L</p>
        <p className="text-xs text-slate-400">de {formato.format(ocupacion.capacidad)} L</p>
      </div>

      {alerta && (
        <p className="mt-3 flex items-start gap-1.5 text-xs font-medium text-amber-700">
          <AlertTriangle className="mt-px h-3.5 w-3.5 shrink-0" />
          {ocupacion.negativo ? "Saldo inconsistente; revisar movimientos." : "Capacidad declarada superada."}
        </p>
      )}
    </article>
  );
}


function Recepcion() {
  const [ocupacion, setOcupacion] = useState<Ocupacion | null>(null);
  const [recepciones, setRecepciones] = useState<RecepcionTipo[]>([]);
  const [total, setTotal] = useState(0);
  const [pagina, setPagina] = useState(1);
  const [silos, setSilos] = useState<Silo[]>([]);
  const [vehiculos, setVehiculos] = useState<Vehiculo[]>([]);
  const [filtroEstado, setFiltroEstado] = useState("");
  const [filtroSilo, setFiltroSilo] = useState("");
  const [busqueda, setBusqueda] = useState("");
  const [cargando, setCargando] = useState(true);
  const [error, setError] = useState("");
  const [formularioAbierto, setFormularioAbierto] = useState(false);
  const [vista, setVista] = useState<VistaFlujo>("espera");
  const [accionActiva, setAccionActiva] = useState<{
    tipo: AccionFlujo;
    recepcion: RecepcionTipo;
  } | null>(null);

  const puedeEditar = puedeEscribir("recepcion");
  const puedeDecidirCalidad = puedeEditar || puedeEscribir("calidad");

  const cargar = useCallback(async () => {
    setCargando(true);
    setError("");

    try {
      const [datosOcupacion, pagina_] = await Promise.all([
        obtenerOcupacion(),
        buscarRecepciones({ estado: filtroEstado, silo: filtroSilo, pagina }),
      ]);
      setOcupacion(datosOcupacion);
      setRecepciones(pagina_.results);
      setTotal(pagina_.count);
    } catch (error) {
      console.error("Error cargando recepción:", error);
      setError("No pudimos actualizar la operación. Revisa la conexión e intenta nuevamente.");
    } finally {
      setCargando(false);
    }
  }, [filtroEstado, filtroSilo, pagina]);

  useEffect(() => {
    Promise.all([obtenerSilos(), obtenerVehiculos()])
      .then(([listaSilos, listaVehiculos]) => {
        setSilos(listaSilos);
        setVehiculos(listaVehiculos);
      })
      .catch((error) => console.error("Error cargando los maestros:", error));
  }, []);

  useEffect(() => {
    const temporizador = setTimeout(cargar, 150);
    return () => clearTimeout(temporizador);
  }, [cargar]);

  const descargar = async (recepcion: RecepcionTipo) => {
    const confirmado = window.confirm(
      `¿Confirmas la descarga de ${formato.format(Number(recepcion.litros))} L en ${recepcion.silo_codigo}?\n\n` +
        "Esta acción actualizará el saldo del silo y quedará registrada en auditoría.",
    );
    if (!confirmado) return;

    try {
      await descargarRecepcion(recepcion.id);
      cargar();
    } catch (error) {
      console.error("Error descargando:", error);
      const detalle = axios.isAxiosError(error) ? error.response?.data?.detail : null;
      setError(detalle || "No se pudo registrar la descarga.");
    }
  };

  const recepcionesVisibles = useMemo(() => {
    const termino = busqueda.trim().toLocaleLowerCase("es-CL");
    const enVista = recepciones.filter((recepcion) => {
      if (vista === "espera") return recepcion.estado === "registrada";
      if (vista === "calidad") return ["muestreada", "retenida"].includes(recepcion.estado);
      if (vista === "asignacion") return recepcion.estado === "liberada";
      return ["descargada", "cerrada"].includes(recepcion.estado);
    });
    if (!termino) return enVista;
    return enVista.filter((recepcion) =>
      [
        recepcion.guia,
        recepcion.modulo,
        recepcion.codigo_muestra,
        recepcion.vehiculo_placa,
        recepcion.procedencia,
        recepcion.silo_codigo,
      ]
        .filter(Boolean)
        .some((valor) => String(valor).toLocaleLowerCase("es-CL").includes(termino)),
    );
  }, [busqueda, recepciones, vista]);

  const cantidadVista = (valor: VistaFlujo) => recepciones.filter((recepcion) => {
    if (valor === "espera") return recepcion.estado === "registrada";
    if (valor === "calidad") return ["muestreada", "retenida"].includes(recepcion.estado);
    if (valor === "asignacion") return recepcion.estado === "liberada";
    return ["descargada", "cerrada"].includes(recepcion.estado);
  }).length;

  const capacidadTotal = ocupacion?.silos.reduce((suma, silo) => suma + silo.capacidad, 0) ?? 0;
  const litrosTotales = ocupacion?.litros_totales ?? 0;
  const ocupacionTotal = capacidadTotal > 0 ? Math.round((litrosTotales / capacidadTotal) * 100) : 0;
  const alertas = recepciones.filter(
    (recepcion) => recepcion.estado === "retenida" || recepcion.evaluacion.motivos.length > 0,
  ).length;
  const pendientes = recepciones.filter((recepcion) =>
    ["registrada", "muestreada", "analizada", "liberada"].includes(recepcion.estado),
  ).length;
  const ultimaPagina = Math.max(1, Math.ceil(total / POR_PAGINA));
  const control =
    "h-10 rounded-xl border border-slate-200 bg-white px-3 text-sm text-slate-700 outline-none transition focus:border-emerald-500 focus:ring-4 focus:ring-emerald-500/10";

  return (
    <div className="min-h-full bg-[#f6f8f7] px-4 py-6 sm:px-6 lg:px-8 lg:py-8">
      <div className="mx-auto max-w-[1480px]">
        <header className="mb-7 flex flex-wrap items-end justify-between gap-5">
          <div>
            <div className="mb-2 flex items-center gap-2 text-xs font-semibold uppercase tracking-[0.14em] text-emerald-700">
              <span>Operación</span>
              <span className="h-1 w-1 rounded-full bg-slate-300" />
              <span className="text-slate-400">Leche cruda</span>
            </div>
            <h1 className="text-3xl font-semibold tracking-tight text-slate-950">Recepción de leche</h1>
            <p className="mt-2 max-w-2xl text-sm leading-6 text-slate-500">
              Controla el ingreso, la evaluación de calidad y la descarga a silos desde una sola vista.
            </p>
          </div>

          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={cargar}
              disabled={cargando}
              className="inline-flex h-11 items-center gap-2 rounded-xl border border-slate-200 bg-white px-4 text-sm font-semibold text-slate-600 shadow-sm transition hover:border-slate-300 hover:text-slate-900 disabled:opacity-50"
            >
              <RefreshCw className={`h-4 w-4 ${cargando ? "animate-spin" : ""}`} />
              Actualizar
            </button>
            {puedeEditar && (
              <button
                type="button"
                onClick={() => setFormularioAbierto(true)}
                className="inline-flex h-11 items-center gap-2 rounded-xl bg-emerald-700 px-5 text-sm font-semibold text-white shadow-sm transition hover:bg-emerald-800 focus:outline-none focus:ring-4 focus:ring-emerald-700/15"
              >
                <Plus className="h-4 w-4" />
                Registrar llegada
              </button>
            )}
          </div>
        </header>

        {error && (
          <div className="mb-6 flex items-start gap-3 rounded-2xl border border-rose-200 bg-rose-50 px-5 py-4 text-sm text-rose-800">
            <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
            <div><p className="font-semibold">No se pudo cargar la información</p><p className="mt-0.5 text-rose-700">{error}</p></div>
          </div>
        )}

        <section className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
          <Indicador etiqueta="Recepciones" valor={formato.format(total)} detalle="Registros disponibles" icono={Truck} />
          <Indicador etiqueta="En proceso" valor={formato.format(pendientes)} detalle="Pendientes en esta vista" icono={Clock3} tono="blue" />
          <Indicador etiqueta="Volumen en planta" valor={`${formato.format(litrosTotales)} L`} detalle={`${ocupacionTotal}% de capacidad utilizada`} icono={Droplets} tono="green" />
          <Indicador etiqueta="Requieren atención" valor={formato.format(alertas)} detalle="Retenciones o controles fuera de rango" icono={AlertTriangle} tono={alertas ? "amber" : "slate"} />
        </section>

        <section className="mt-6 rounded-2xl border border-slate-200/80 bg-white px-5 py-5 shadow-[0_1px_2px_rgba(15,23,42,0.03)]">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <h2 className="font-semibold text-slate-900">Flujo del turno</h2>
              <p className="mt-0.5 text-xs text-slate-400">Estado actual de las recepciones visibles</p>
            </div>
            <p className="flex items-center gap-2 text-xs font-medium text-slate-500">
              <span className="h-2 w-2 rounded-full bg-emerald-500" /> Actualizado ahora
            </p>
          </div>
          <div className="mt-5 grid grid-cols-2 gap-2 md:grid-cols-3 xl:grid-cols-6">
            {PASOS.map(({ etiqueta, contar, icono: Icono }, indice) => {
              const cantidad = recepciones.filter(contar).length;
              return (
                <div key={etiqueta} className="relative rounded-xl bg-slate-50 px-4 py-3.5">
                  <div className="flex items-center justify-between gap-2">
                    <span className="rounded-lg bg-white p-1.5 text-slate-500 shadow-sm"><Icono className="h-4 w-4" /></span>
                    <span className="text-lg font-semibold text-slate-900">{cantidad}</span>
                  </div>
                  <p className="mt-2 text-xs font-medium text-slate-600">{indice + 1}. {etiqueta}</p>
                </div>
              );
            })}
          </div>
        </section>

        <section className="mt-6">
          <div className="mb-3 flex items-end justify-between gap-3">
            <div><h2 className="font-semibold text-slate-900">Silos y estanques</h2><p className="mt-1 text-xs text-slate-400">Capacidad disponible para descarga</p></div>
            {ocupacion && <p className="text-xs font-medium text-slate-500">{ocupacion.silos.length} unidades activas</p>}
          </div>
          {!ocupacion || ocupacion.silos.length === 0 ? (
            <div className="rounded-2xl border border-dashed border-slate-300 bg-white px-6 py-10 text-center text-sm text-slate-500">No hay silos activos configurados.</div>
          ) : (
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">{ocupacion.silos.map((silo) => <TarjetaSilo key={silo.silo_id} ocupacion={silo} />)}</div>
          )}
        </section>

        <section className="mt-7 overflow-hidden rounded-2xl border border-slate-200/80 bg-white shadow-[0_1px_2px_rgba(15,23,42,0.03)]">
          <div className="border-b border-slate-200 px-5 py-5">
            <div className="flex flex-wrap items-center justify-between gap-4">
              <div><h2 className="font-semibold text-slate-900">Recepciones</h2><p className="mt-1 text-xs text-slate-400">Seguimiento desde llegada hasta cierre</p></div>
              <span className="text-xs font-medium text-slate-400">{cargando ? "Actualizando…" : `${formato.format(total)} registros`}</span>
            </div>
            <div className="mt-5 grid gap-2 sm:grid-cols-2 xl:grid-cols-4">
              {VISTAS.map((item) => {
                const activa = vista === item.valor;
                return (
                  <button
                    key={item.valor}
                    type="button"
                    onClick={() => setVista(item.valor)}
                    className={`flex items-center justify-between rounded-xl border px-4 py-3 text-left transition ${activa ? "border-emerald-200 bg-emerald-50" : "border-slate-200 bg-white hover:bg-slate-50"}`}
                  >
                    <span><span className={`block text-sm font-semibold ${activa ? "text-emerald-800" : "text-slate-700"}`}>{item.etiqueta}</span><span className="mt-0.5 block text-[11px] text-slate-400">{item.descripcion}</span></span>
                    <span className={`rounded-full px-2 py-0.5 text-xs font-bold ${activa ? "bg-emerald-700 text-white" : "bg-slate-100 text-slate-500"}`}>{cantidadVista(item.valor)}</span>
                  </button>
                );
              })}
            </div>
            <div className="mt-4 flex flex-wrap gap-2">
              <label className="relative min-w-[220px] flex-1 lg:max-w-sm">
                <Search className="pointer-events-none absolute left-3 top-3 h-4 w-4 text-slate-400" />
                <input className={`${control} w-full pl-9`} placeholder="Buscar guía, módulo, muestra o camión" value={busqueda} onChange={(e) => setBusqueda(e.target.value)} />
              </label>
              <div className="relative"><SlidersHorizontal className="pointer-events-none absolute left-3 top-3 h-4 w-4 text-slate-400" /><select aria-label="Filtrar por estado" className={`${control} pl-9`} value={filtroEstado} onChange={(e) => { setFiltroEstado(e.target.value); setPagina(1); }}><option value="">Todos los estados</option>{ESTADOS_RECEPCION.map((estado) => <option key={estado.valor} value={estado.valor}>{estado.etiqueta}</option>)}</select></div>
              <select aria-label="Filtrar por silo" className={control} value={filtroSilo} onChange={(e) => { setFiltroSilo(e.target.value); setPagina(1); }}><option value="">Todos los silos</option>{silos.map((silo) => <option key={silo.id} value={silo.id}>{silo.codigo}</option>)}</select>
            </div>
          </div>

          {!cargando && recepcionesVisibles.length === 0 ? (
            <div className="px-6 py-16 text-center"><span className="mx-auto flex h-11 w-11 items-center justify-center rounded-full bg-slate-100 text-slate-400"><Truck className="h-5 w-5" /></span><p className="mt-4 text-sm font-medium text-slate-700">No encontramos recepciones</p><p className="mt-1 text-xs text-slate-400">Prueba cambiando los filtros o registra una nueva llegada.</p></div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full min-w-[1050px] text-left text-sm">
                <thead className="bg-slate-50/80 text-[11px] font-semibold uppercase tracking-[0.08em] text-slate-400"><tr><th className="px-5 py-3">Ingreso</th><th className="px-5 py-3">Módulo y transporte</th><th className="px-5 py-3">Origen</th><th className="px-5 py-3">Volumen</th><th className="px-5 py-3">Muestra / calidad</th><th className="px-5 py-3">Destino</th><th className="px-5 py-3">Estado</th><th className="px-5 py-3 text-right">Siguiente paso</th></tr></thead>
                <tbody className="divide-y divide-slate-100">
                  {recepcionesVisibles.map((recepcion) => (
                    <tr key={recepcion.id} className="transition hover:bg-slate-50/70">
                      <td className="px-5 py-4"><p className="font-semibold text-slate-800">{formatearFecha(recepcion.fecha)} <span className="font-normal text-slate-400">{recepcion.hora?.slice(0, 5) || "—"}</span></p><p className="mt-1 text-xs text-slate-400">Guía {recepcion.guia || "sin informar"}</p></td>
                      <td className="px-5 py-4"><p className="font-semibold text-slate-800">{recepcion.modulo || "Módulo sin identificar"}</p><p className="mt-1 text-xs text-slate-400">{recepcion.vehiculo_placa || "Sin camión"} · Turno {recepcion.turno || "—"}</p></td>
                      <td className="px-5 py-4"><p className="text-slate-700">{recepcion.procedencia || "—"}</p><p className="mt-1 text-xs text-slate-400">{recepcion.tipo_leche}</p></td>
                      <td className="px-5 py-4 font-semibold tabular-nums text-slate-800">{formato.format(Number(recepcion.litros))} L</td>
                      <td className="px-5 py-4">
                        {recepcion.estado === "registrada" ? <span className="inline-flex items-center gap-1.5 text-xs font-medium text-slate-500"><Clock3 className="h-3.5 w-3.5" />Sin muestra</span> : recepcion.estado === "muestreada" ? <span className="text-xs"><span className="block font-semibold text-sky-700">{recepcion.codigo_muestra}</span><span className="mt-1 block text-slate-400">Esperando decisión</span></span> : recepcion.evaluacion.motivos.length > 0 ? <span className="inline-flex items-center gap-1.5 text-xs font-semibold text-rose-700" title={recepcion.evaluacion.motivos.join(" · ")}><AlertTriangle className="h-3.5 w-3.5" />{recepcion.evaluacion.motivos.length} alerta{recepcion.evaluacion.motivos.length === 1 ? "" : "s"}</span> : <span className="inline-flex items-center gap-1.5 text-xs font-medium text-emerald-700"><CheckCircle2 className="h-3.5 w-3.5" />Aprobada</span>}
                      </td>
                      <td className="px-5 py-4"><span className="inline-flex items-center gap-1.5 text-slate-700"><Warehouse className="h-3.5 w-3.5 text-slate-400" />{recepcion.silo_codigo || "Sin asignar"}</span></td>
                      <td className="px-5 py-4"><span className={`inline-flex rounded-full border px-2.5 py-1 text-xs font-semibold ${ESTILO_ESTADO[recepcion.estado] ?? ESTILO_ESTADO.registrada}`} title={recepcion.motivo || undefined}>{recepcion.estado_etiqueta}</span></td>
                      <td className="px-5 py-4 text-right">
                        {puedeEditar && recepcion.estado === "registrada" ? <button type="button" onClick={() => setAccionActiva({ tipo: "muestra", recepcion })} className="inline-flex items-center gap-1.5 rounded-lg bg-sky-50 px-3 py-2 text-xs font-semibold text-sky-700 transition hover:bg-sky-100"><Beaker className="h-3.5 w-3.5" />Tomar muestra</button> : puedeDecidirCalidad && ["muestreada", "retenida"].includes(recepcion.estado) ? <button type="button" onClick={() => setAccionActiva({ tipo: "calidad", recepcion })} className="inline-flex items-center gap-1.5 rounded-lg bg-violet-50 px-3 py-2 text-xs font-semibold text-violet-700 transition hover:bg-violet-100"><ShieldCheck className="h-3.5 w-3.5" />{recepcion.estado === "retenida" ? "Reanalizar" : "Evaluar"}</button> : puedeEditar && recepcion.estado === "liberada" && !recepcion.silo ? <button type="button" onClick={() => setAccionActiva({ tipo: "silo", recepcion })} className="inline-flex items-center gap-1.5 rounded-lg bg-blue-50 px-3 py-2 text-xs font-semibold text-blue-700 transition hover:bg-blue-100"><Warehouse className="h-3.5 w-3.5" />Asignar silo</button> : puedeEditar && recepcion.estado === "liberada" && recepcion.silo ? <button type="button" onClick={() => descargar(recepcion)} className="inline-flex items-center gap-1.5 rounded-lg bg-emerald-50 px-3 py-2 text-xs font-semibold text-emerald-700 transition hover:bg-emerald-100"><ArrowDownToLine className="h-3.5 w-3.5" />Descargar</button> : <span className="text-xs text-slate-300">—</span>}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          {ultimaPagina > 1 && <div className="flex items-center justify-between border-t border-slate-200 px-5 py-4"><button type="button" onClick={() => setPagina((valor) => Math.max(1, valor - 1))} disabled={pagina <= 1} className="inline-flex items-center gap-1 rounded-lg px-3 py-2 text-sm font-medium text-slate-600 hover:bg-slate-100 disabled:opacity-30"><ChevronLeft className="h-4 w-4" />Anterior</button><span className="text-xs font-medium text-slate-500">Página {pagina} de {ultimaPagina}</span><button type="button" onClick={() => setPagina((valor) => Math.min(ultimaPagina, valor + 1))} disabled={pagina >= ultimaPagina} className="inline-flex items-center gap-1 rounded-lg px-3 py-2 text-sm font-medium text-slate-600 hover:bg-slate-100 disabled:opacity-30">Siguiente<ChevronRight className="h-4 w-4" /></button></div>}
        </section>
      </div>

      {formularioAbierto && <FormularioRecepcion vehiculos={vehiculos} alCerrar={() => setFormularioAbierto(false)} alGuardar={cargar} />}
      {accionActiva && <AccionRecepcion accion={accionActiva.tipo} recepcion={accionActiva.recepcion} silos={silos} alCerrar={() => setAccionActiva(null)} alGuardar={cargar} />}
    </div>
  );
}


export default Recepcion;
