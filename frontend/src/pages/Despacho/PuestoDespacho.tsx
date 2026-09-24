import { useState } from "react";
import { Plus } from "lucide-react";

import { Vacio } from "../../components/seccion/componentes";
import { claseBoton, useCarga } from "../../components/seccion/utilidades";
import { agruparHojas } from "../../services/despacho-reglas";
import { fechaLocalISO } from "../../services/fechas";
import { cantidad } from "../../services/formato";
import {
  buscarDespachos, obtenerCatalogosInventario, obtenerClientesDespacho, obtenerGranelDisponible,
  obtenerHojasVigentes, obtenerPalletsCargables, type Despacho,
} from "../../services/inventario.service";
import { puedeAutorizarDespacho, puedeDespachar } from "../../services/permisos-despacho";
import { obtenerSesion } from "../../services/sesion";
import TablaConsulta from "../Inventario/TablaConsulta";
import HojaDeCarga from "./HojaDeCarga";
import NuevaHojaCarga from "./NuevaHojaCarga";

function Grupo({ titulo, hojas, autoriza, vacio, onCambio }: {
  titulo: string; hojas: Despacho[]; autoriza: boolean; vacio: string; onCambio: (m: string) => void;
}) {
  return (
    <section aria-label={titulo} className="space-y-3">
      <h2 className="text-lg font-semibold text-slate-900">{titulo} ({hojas.length})</h2>
      {hojas.length === 0 ? <Vacio>{vacio}</Vacio> : hojas.map((h) => <HojaDeCarga key={h.id} hoja={h} autoriza={autoriza} onCambio={onCambio} />)}
    </section>
  );
}

const fechaHora = (iso: string) =>
  new Date(iso).toLocaleString("es-CL", { dateStyle: "short", timeStyle: "short" });

/* Abre en las hojas que falta sacar: lo primero que se decide al llegar un camión. */
export default function PuestoDespacho() {
  const usuario = obtenerSesion()?.usuario;
  const crea = puedeDespachar(usuario);
  const autoriza = puedeAutorizarDespacho(usuario);
  const hojas = useCarga(obtenerHojasVigentes);
  const clientes = useCarga(obtenerClientesDespacho);
  const disponibles = useCarga(obtenerPalletsCargables);
  const graneles = useCarga(obtenerGranelDisponible);
  const catalogos = useCarga(obtenerCatalogosInventario);
  const [nueva, setNueva] = useState(false);
  const [mensaje, setMensaje] = useState("");

  const cambio = (texto: string) => {
    setMensaje(texto);
    setNueva(false);
    void hojas.recargar();
    void disponibles.recargar();
    void graneles.recargar();
  };

  const grupos = agruparHojas(hojas.datos ?? [], fechaLocalISO());

  return (
    <div className="px-4 py-8 sm:px-8">
      <div className="mx-auto max-w-6xl space-y-6">
        <header className="flex flex-wrap items-end justify-between gap-4">
          <div>
            <p className="text-sm font-semibold uppercase tracking-wider text-green-700">Puesto de trabajo</p>
            <h1 className="mt-1 text-3xl font-bold text-slate-900">Despacho</h1>
            <p className="mt-2 max-w-2xl text-slate-600">Arma la hoja de carga del camión, autorízala y ejecuta la salida.</p>
          </div>
          {crea && !nueva && (
            <button type="button" onClick={() => { setNueva(true); setMensaje(""); }} className={`${claseBoton} inline-flex items-center gap-2`}>
              <Plus className="h-4 w-4" /> Nueva hoja de carga
            </button>
          )}
        </header>

        {mensaje && <p role="status" className="rounded-xl border border-green-200 bg-green-50 px-4 py-3 text-sm text-green-900">{mensaje}</p>}

        {nueva && (
          <>
            {(clientes.error || disponibles.error || graneles.error) && (
              <p role="alert" className="text-sm text-red-800">
                {[clientes.error && "clientes", disponibles.error && "pallets disponibles", graneles.error && "graneles"].filter(Boolean).join(", ")}: no se pudo cargar.
              </p>
            )}
            <NuevaHojaCarga
              clientes={clientes.datos ?? []}
              disponibles={disponibles.datos ?? []}
              graneles={graneles.datos ?? []}
              onCreada={cambio}
              onFallo={() => { void disponibles.recargar(); void graneles.recargar(); }}
              onCerrar={() => setNueva(false)}
            />
          </>
        )}

        {hojas.error && <p role="alert" className="text-sm text-red-800">{hojas.error}</p>}
        {hojas.cargando && !hojas.datos && <p className="text-sm text-slate-600">Cargando hojas de carga…</p>}

        <Grupo titulo="Autorizadas" hojas={grupos.autorizada} autoriza={autoriza} vacio="No hay hojas autorizadas esperando salida." onCambio={cambio} />
        <Grupo titulo="Borrador" hojas={grupos.borrador} autoriza={autoriza} vacio="No hay hojas en borrador." onCambio={cambio} />
        <Grupo titulo="Despachadas hoy" hojas={grupos.despachadaHoy} autoriza={false} vacio="Hoy no ha salido ninguna hoja." onCambio={cambio} />

        <section aria-label="Historial de despachos" className="space-y-3">
          <h2 className="text-lg font-semibold text-slate-900">Historial</h2>
          <TablaConsulta<Despacho>
            titulo="Historial de despachos"
            cargar={buscarDespachos}
            clave={(f) => f.id}
            ubicaciones={[]}
            conUbicacion={false}
            conFechas
            etiquetaBusqueda="Número, cliente, pallet o lote"
            vacio="No hay despachos que coincidan."
            estados={(catalogos.datos?.estado_despacho ?? []).map((o) => ({ valor: o.valor, texto: o.etiqueta }))}
            columnas={[
              { titulo: "Número", celda: (f) => <span className="font-mono">{f.numero}</span> },
              { titulo: "Fecha", celda: (f) => fechaHora(f.creado_en) },
              { titulo: "Cliente", celda: (f) => f.cliente_nombre },
              {
                titulo: "Estado",
                celda: (f) => catalogos.datos?.estado_despacho.find((o) => o.valor === f.estado)?.etiqueta ?? f.estado,
              },
              { titulo: "Pallets", numerica: true, celda: (f) => f.detalles.length },
              {
                titulo: "Kg",
                numerica: true,
                celda: (f) => cantidad(
                  f.detalles.reduce((suma, d) => suma + Number(d.kg_neto), 0),
                  "kg",
                ),
              },
              { titulo: "Motivo de cancelación", celda: (f) => f.motivo_cancelacion || "—" },
            ]}
          />
        </section>
      </div>
    </div>
  );
}
