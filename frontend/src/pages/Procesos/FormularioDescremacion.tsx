import { useEffect, useMemo, useState } from "react";
import { X } from "lucide-react";

import { mensajeDe } from "../../components/seccion/utilidades";
import {
  obtenerEquipos, obtenerProductosMaestros, obtenerSilosMaestros,
  type Equipo, type ProductoMaestro, type Silo,
} from "../../services/maestros.service";
import {
  crearDescremacion, crearEjecucion, iniciarDescremacion, obtenerEtapas,
  type CorridaDescremacion, type EtapaProceso,
} from "../../services/procesos.service";
import { listarAnalisisSilo, type AnalisisSilo } from "../../services/recepcion.service";

const control = "mt-1 w-full rounded-xl border border-slate-300 bg-white px-3 py-2.5";

export default function FormularioDescremacion({
  siloOrigen, onCerrar, onCreada,
}: {
  siloOrigen: number;
  onCerrar: () => void;
  onCreada: (corrida: CorridaDescremacion) => Promise<void>;
}) {
  const [etapas, setEtapas] = useState<EtapaProceso[]>([]);
  const [equipos, setEquipos] = useState<Equipo[]>([]);
  const [silos, setSilos] = useState<Silo[]>([]);
  const [productos, setProductos] = useState<ProductoMaestro[]>([]);
  const [analisis, setAnalisis] = useState<AnalisisSilo[]>([]);
  const [ocupado, setOcupado] = useState(true);
  const [error, setError] = useState("");
  const [datos, setDatos] = useState({
    codigo: `DES-${new Date().toISOString().replace(/\D/g, "").slice(0, 12)}`,
    etapa: "", equipo: "", analisis: "", litros: "",
    silo_descremada: "", estanque_crema: "",
    producto_descremada: "", producto_crema: "",
  });

  useEffect(() => {
    let vigente = true;
    Promise.all([
      obtenerEtapas(), obtenerEquipos(), obtenerSilosMaestros(), listarAnalisisSilo(siloOrigen),
      obtenerProductosMaestros(),
    ]).then(([paginaEtapas, maquinas, estanques, muestras, catalogoProductos]) => {
      if (!vigente) return;
      const etapasDes = paginaEtapas.results.filter((item) => item.tipo === "descremacion" && item.activa);
      const validos = muestras.filter((item) => item.estado === "confirmado" && item.vigente);
      setEtapas(etapasDes);
      setEquipos(maquinas.filter((item) => item.activo));
      setSilos(estanques.filter((item) => item.activo));
      setProductos(catalogoProductos.filter((item) => item.activo));
      setAnalisis(validos);
      setDatos((actual) => ({
        ...actual,
        etapa: etapasDes[0] ? String(etapasDes[0].id) : "",
        analisis: validos[0] ? String(validos[0].id) : "",
        producto_descremada: String(
          catalogoProductos.find((item) => item.activo && item.tipo === "descremada")?.id ?? "",
        ),
        producto_crema: String(
          catalogoProductos.find((item) => item.activo && item.familia === "crema")?.id ?? "",
        ),
      }));
    }).catch((e) => setError(mensajeDe(e, "No se pudieron cargar los datos de descremación.")))
      .finally(() => { if (vigente) setOcupado(false); });
    return () => { vigente = false; };
  }, [siloOrigen]);

  const muestra = analisis.find((item) => item.id === Number(datos.analisis));
  const destinoDescremada = useMemo(
    () => silos.filter((item) => item.tipo === "tk_ld" && item.id !== siloOrigen),
    [silos, siloOrigen],
  );
  const destinosCrema = useMemo(
    () => silos.filter((item) => item.tipo === "tk_crema" && item.id !== siloOrigen),
    [silos, siloOrigen],
  );
  const productosDescremada = productos.filter((item) => item.tipo === "descremada");
  const productosCrema = productos.filter((item) => item.familia === "crema");

  const guardar = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!muestra?.grasa || !muestra.sng) return;
    setOcupado(true);
    setError("");
    try {
      const ejecucion = await crearEjecucion({
        codigo: datos.codigo.trim(), etapa: Number(datos.etapa), equipo: Number(datos.equipo),
      });
      const corrida = await crearDescremacion({
        ejecucion: ejecucion.id, silo_entera: siloOrigen,
        analisis_entrada: muestra.id, litros_entrada: Number(datos.litros),
        grasa_entrada: Number(muestra.grasa), sng_entrada: Number(muestra.sng),
        silo_descremada: Number(datos.silo_descremada),
        estanque_crema: Number(datos.estanque_crema),
        producto_descremada: Number(datos.producto_descremada),
        producto_crema: Number(datos.producto_crema),
      });
      await onCreada(await iniciarDescremacion(corrida.id));
    } catch (e) {
      setError(mensajeDe(e, "No se pudo crear e iniciar la descremación."));
    } finally {
      setOcupado(false);
    }
  };

  return (
    <div className="fixed inset-0 z-[80] flex items-start justify-center overflow-y-auto bg-slate-950/45 p-4">
      <form onSubmit={guardar} className="my-8 w-full max-w-3xl rounded-2xl bg-white p-6 shadow-xl">
        <div className="flex items-center justify-between"><div><p className="text-xs font-semibold uppercase tracking-wide text-emerald-700">Nueva operación</p><h2 className="mt-1 text-xl font-semibold">Iniciar descremación</h2></div><button type="button" onClick={onCerrar} className="rounded-lg p-2 hover:bg-slate-100"><X className="h-5 w-5" /></button></div>
        <div className="mt-5 grid gap-4 sm:grid-cols-2">
          <Campo texto="Código de ejecución"><input required value={datos.codigo} onChange={(e) => setDatos({ ...datos, codigo: e.target.value })} className={control} /></Campo>
          <Campo texto="Etapa de descremación"><select required value={datos.etapa} onChange={(e) => setDatos({ ...datos, etapa: e.target.value })} className={control}><option value="">Seleccionar…</option>{etapas.map((item) => <option key={item.id} value={item.id}>{item.nombre}</option>)}</select></Campo>
          <Campo texto="Equipo"><select required value={datos.equipo} onChange={(e) => setDatos({ ...datos, equipo: e.target.value })} className={control}><option value="">Seleccionar…</option>{equipos.map((item) => <option key={item.id} value={item.id}>{item.nombre}</option>)}</select></Campo>
          <Campo texto="Análisis vigente del origen"><select required value={datos.analisis} onChange={(e) => setDatos({ ...datos, analisis: e.target.value })} className={control}><option value="">Seleccionar…</option>{analisis.map((item) => <option key={item.id} value={item.id}>{new Date(item.tomado_en).toLocaleString("es-CL")} · {item.grasa}% MG</option>)}</select></Campo>
          <Campo texto="Litros de entrada"><input required type="number" min="0.01" step="0.01" value={datos.litros} onChange={(e) => setDatos({ ...datos, litros: e.target.value })} className={control} /></Campo>
          <Campo texto="Destino leche descremada"><select required value={datos.silo_descremada} onChange={(e) => setDatos({ ...datos, silo_descremada: e.target.value })} className={control}><option value="">Seleccionar…</option>{destinoDescremada.map((item) => <option key={item.id} value={item.id}>{item.codigo}</option>)}</select></Campo>
          <Campo texto="Destino crema"><select required value={datos.estanque_crema} onChange={(e) => setDatos({ ...datos, estanque_crema: e.target.value })} className={control}><option value="">Seleccionar…</option>{destinosCrema.map((item) => <option key={item.id} value={item.id}>{item.codigo}</option>)}</select></Campo>
          <Campo texto="Producto intermedio · descremada"><select required value={datos.producto_descremada} onChange={(e) => setDatos({ ...datos, producto_descremada: e.target.value })} className={control}><option value="">Seleccionar…</option>{productosDescremada.map((item) => <option key={item.id} value={item.id}>{item.nombre}</option>)}</select></Campo>
          <Campo texto="Producto intermedio · crema"><select required value={datos.producto_crema} onChange={(e) => setDatos({ ...datos, producto_crema: e.target.value })} className={control}><option value="">Seleccionar…</option>{productosCrema.map((item) => <option key={item.id} value={item.id}>{item.nombre}</option>)}</select></Campo>
          <div className="rounded-xl bg-slate-50 px-4 py-3 text-sm text-slate-600"><span className="block text-xs">Composición congelada</span>{muestra ? `${muestra.grasa}% MG · ${muestra.sng}% SNG` : "Selecciona un análisis"}</div>
        </div>
        {etapas.length === 0 && <p className="mt-4 rounded-xl bg-amber-50 px-4 py-3 text-sm text-amber-800">Falta configurar una etapa activa de tipo Descremación.</p>}
        {analisis.length === 0 && <p className="mt-4 rounded-xl bg-amber-50 px-4 py-3 text-sm text-amber-800">El silo no tiene un análisis confirmado vigente.</p>}
        {error && <p className="mt-4 rounded-xl bg-rose-50 px-4 py-3 text-sm text-rose-700">{error}</p>}
        <div className="mt-6 flex justify-end gap-3"><button type="button" onClick={onCerrar} className="px-4 py-2.5 text-sm text-slate-600">Cancelar</button><button disabled={ocupado || !muestra || etapas.length === 0} className="rounded-xl bg-emerald-700 px-5 py-2.5 text-sm font-semibold text-white disabled:opacity-40">{ocupado ? "Preparando…" : "Crear e iniciar"}</button></div>
      </form>
    </div>
  );
}

function Campo({ texto, children }: { texto: string; children: React.ReactNode }) {
  return <label className="text-sm text-slate-600">{texto}{children}</label>;
}
