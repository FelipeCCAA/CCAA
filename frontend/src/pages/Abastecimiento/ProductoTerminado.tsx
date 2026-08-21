import { useState } from "react";

import { Aviso, Estado, Tarjeta, Vacio } from "../../components/seccion/componentes";
import { claseBoton, claseCampo, claseCelda, claseEncabezado, numero, useCarga } from "../../components/seccion/utilidades";
import {
  autorizarDespacho, crearDespacho, ejecutarDespacho, ingresarPallet,
  obtenerClientesDespacho, obtenerDespachos, obtenerProductoTerminado, obtenerUbicaciones,
} from "../../services/inventario.service";
import { obtenerPallets } from "../../services/produccion.service";

function mensaje(error: unknown) {
  const candidato = error as { response?: { data?: { detail?: string } } };
  return candidato.response?.data?.detail || "No fue posible completar la operación.";
}

export default function ProductoTerminado() {
  const stock = useCarga(obtenerProductoTerminado);
  const ubicaciones = useCarga(obtenerUbicaciones);
  const clientes = useCarga(obtenerClientesDespacho);
  const despachos = useCarga(obtenerDespachos);
  const pallets = useCarga(async () => (await obtenerPallets()).results);
  const [error, setError] = useState("");
  const [ingreso, setIngreso] = useState({ pallet: "", ubicacion: "" });
  const [salida, setSalida] = useState({ numero: "", cliente: "", pallets: [] as number[] });

  const refrescar = () => Promise.all([stock.recargar(), despachos.recargar(), pallets.recargar()]);

  async function guardarIngreso(evento: React.FormEvent) {
    evento.preventDefault(); setError("");
    try {
      await ingresarPallet(Number(ingreso.pallet), Number(ingreso.ubicacion));
      setIngreso({ pallet: "", ubicacion: "" }); await refrescar();
    } catch (e) { setError(mensaje(e)); }
  }

  async function guardarDespacho(evento: React.FormEvent) {
    evento.preventDefault(); setError("");
    try {
      await crearDespacho({ numero: salida.numero, cliente: Number(salida.cliente), pallet_ids: salida.pallets });
      setSalida({ numero: "", cliente: "", pallets: [] }); await refrescar();
    } catch (e) { setError(mensaje(e)); }
  }

  async function cambiar(id: number, accion: "autorizar" | "ejecutar") {
    setError("");
    try { await (accion === "autorizar" ? autorizarDespacho(id) : ejecutarDespacho(id)); await refrescar(); }
    catch (e) { setError(mensaje(e)); }
  }

  const disponibles = stock.datos ?? [];
  const liberados = (pallets.datos ?? []).filter((p) => p.estado === "liberado");

  return <div className="space-y-6">
    {error && <Aviso>{error}</Aviso>}
    <div className="grid gap-6 xl:grid-cols-2">
      <Tarjeta titulo="Ingreso de producto terminado" descripcion="Solo admite pallets con liberación vigente de Calidad.">
        <form onSubmit={guardarIngreso} className="grid gap-3 sm:grid-cols-2">
          <select className={claseCampo} required value={ingreso.pallet} onChange={(e) => setIngreso({ ...ingreso, pallet: e.target.value })}>
            <option value="">Pallet liberado…</option>{liberados.map((p) => <option key={p.id} value={p.id}>{p.codigo} · {p.kg_neto} kg</option>)}
          </select>
          <select className={claseCampo} required value={ingreso.ubicacion} onChange={(e) => setIngreso({ ...ingreso, ubicacion: e.target.value })}>
            <option value="">Ubicación…</option>{(ubicaciones.datos ?? []).filter((u) => u.activo && u.tipo === "disponible").map((u) => <option key={u.id} value={u.id}>{u.bodega_nombre}/{u.codigo}</option>)}
          </select>
          <button className={claseBoton} type="submit">Ingresar pallet</button>
        </form>
      </Tarjeta>
      <Tarjeta titulo="Solicitud de despacho" descripcion="La autorización y la salida física son firmas separadas.">
        <form onSubmit={guardarDespacho} className="space-y-3">
          <div className="grid gap-3 sm:grid-cols-2"><input className={claseCampo} required placeholder="Nº despacho" value={salida.numero} onChange={(e) => setSalida({ ...salida, numero: e.target.value })}/><select className={claseCampo} required value={salida.cliente} onChange={(e) => setSalida({ ...salida, cliente: e.target.value })}><option value="">Cliente…</option>{(clientes.datos ?? []).map((c) => <option key={c.id} value={c.id}>{c.nombre}</option>)}</select></div>
          <div className="max-h-32 space-y-1 overflow-auto rounded-xl border border-slate-200 p-3">{disponibles.map((e) => <label key={e.id} className="flex gap-2 text-sm"><input type="checkbox" checked={salida.pallets.includes(e.pallet)} onChange={() => setSalida({ ...salida, pallets: salida.pallets.includes(e.pallet) ? salida.pallets.filter((id) => id !== e.pallet) : [...salida.pallets, e.pallet] })}/>{e.pallet_codigo} · {e.producto_nombre} · {e.kg_neto} kg</label>)}</div>
          <button className={claseBoton} disabled={!salida.pallets.length} type="submit">Crear borrador</button>
        </form>
      </Tarjeta>
    </div>
    <Tarjeta titulo="Stock por pallet" descripcion="Cada pallet tiene una sola ubicación vigente; el saldo no se edita.">
      {!disponibles.length ? <Vacio>No hay producto terminado en inventario.</Vacio> : <div className="overflow-x-auto"><table className="w-full"><thead><tr><th className={claseEncabezado}>Pallet</th><th className={claseEncabezado}>Lote / producto</th><th className={claseEncabezado}>Ubicación</th><th className={claseEncabezado}>Kg</th></tr></thead><tbody>{disponibles.map((e) => <tr key={e.id}><td className={claseCelda}>{e.pallet_codigo}</td><td className={claseCelda}>{e.lote_codigo} · {e.producto_nombre}</td><td className={claseCelda}>{e.ubicacion_codigo}</td><td className={claseCelda}>{numero(e.kg_neto)}</td></tr>)}</tbody></table></div>}
    </Tarjeta>
    <Tarjeta titulo="Despachos" descripcion="Calidad se vuelve a comprobar al autorizar y al ejecutar.">
      <div className="space-y-3">{(despachos.datos ?? []).map((d) => <div key={d.id} className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-slate-200 p-4"><div><div className="font-semibold text-slate-800">{d.numero} · {d.cliente_nombre}</div><div className="text-sm text-slate-600">{d.detalles.length} pallet(s) · {d.detalles.reduce((s, x) => s + Number(x.kg_neto), 0).toLocaleString("es-CL")} kg</div></div><div className="flex items-center gap-2"><Estado valor={d.estado}/>{d.estado === "borrador" && <button className={claseBoton} onClick={() => cambiar(d.id, "autorizar")}>Autorizar</button>}{d.estado === "autorizado" && <button className={claseBoton} onClick={() => cambiar(d.id, "ejecutar")}>Confirmar salida</button>}</div></div>)}</div>
    </Tarjeta>
  </div>;
}
