import { useEffect, useMemo, useState } from "react";
import axios from "axios";

import { obtenerEquipos, type Equipo } from "../../services/maestros.service";
import { registrarEnvase } from "../../services/produccion.service";

const campo = "w-full rounded-xl border border-slate-300 bg-white px-3 py-2 text-sm";
const FORMATO_KG = 25;
const MAXIMO_KG = 500;

export default function FormularioEnvase({ loteId, alGuardar }: { loteId: number; alGuardar: () => void }) {
  const [equipos, setEquipos] = useState<Equipo[]>([]);
  const [equipo, setEquipo] = useState("");
  const [codigo, setCodigo] = useState("");
  const [unidades, setUnidades] = useState("20");
  const [mensaje, setMensaje] = useState("");
  const [guardando, setGuardando] = useState(false);
  const kg = useMemo(() => Number(unidades || 0) * FORMATO_KG, [unidades]);
  const valido = Boolean(equipo && codigo.trim() && Number(unidades) > 0 && kg <= MAXIMO_KG);

  useEffect(() => {
    void obtenerEquipos()
      .then((lista) => setEquipos(lista.filter((item) => item.activo && ["envasadora", "linea", "torre"].includes(item.tipo))))
      .catch(() => setMensaje("No se pudieron cargar las envasadoras."));
  }, []);

  async function guardar(evento: React.FormEvent) {
    evento.preventDefault();
    if (!valido) return;
    setGuardando(true); setMensaje("");
    try {
      const termino = new Date();
      const inicio = new Date(termino.getTime() - 60_000);
      await registrarEnvase({
        lote: loteId, equipo: Number(equipo), formato_kg: FORMATO_KG,
        inicio: inicio.toISOString(), termino: termino.toISOString(),
        pallets_datos: [{ codigo: codigo.trim(), unidades: Number(unidades), kg_neto: kg }],
      });
      setMensaje(`Pallet ${codigo.trim()} creado: ${unidades} sacos, ${kg} kg. Quedó en cuarentena de Calidad.`);
      setCodigo(""); setUnidades("20"); alGuardar();
    } catch (error) {
      const datos = axios.isAxiosError(error) ? error.response?.data : null;
      setMensaje(datos ? Object.values(datos as Record<string, string | string[]>).flat().join(" ") : "No se pudo registrar el pallet.");
    } finally { setGuardando(false); }
  }

  return <form onSubmit={guardar} className="rounded-xl border border-emerald-200 bg-emerald-50/50 p-4">
    <h3 className="text-sm font-bold text-slate-900">Envasar en pallet · sacos de 25 kg</h3>
    <p className="mt-1 text-xs text-slate-600">Máximo 500 kg por pallet: hasta 20 sacos.</p>
    <div className="mt-3 grid gap-3 sm:grid-cols-3">
      <select required className={campo} value={equipo} onChange={(e) => setEquipo(e.target.value)}><option value="">Envasadora…</option>{equipos.map((item) => <option key={item.id} value={item.id}>{item.codigo} · {item.nombre}</option>)}</select>
      <input required className={campo} placeholder="Código pallet" value={codigo} onChange={(e) => setCodigo(e.target.value)} />
      <input required className={campo} type="number" min="1" max="20" step="1" value={unidades} onChange={(e) => setUnidades(e.target.value)} />
    </div>
    <div className="mt-3 flex flex-wrap items-center gap-3"><span className={`text-sm font-bold ${kg > MAXIMO_KG ? "text-red-700" : "text-emerald-800"}`}>{unidades || 0} × 25 kg = {kg} kg</span><button disabled={!valido || guardando} className="rounded-xl bg-emerald-700 px-4 py-2 text-sm font-semibold text-white disabled:opacity-50">{guardando ? "Registrando…" : "Crear pallet"}</button></div>
    {mensaje && <p className="mt-3 text-sm text-slate-700">{mensaje}</p>}
  </form>;
}
