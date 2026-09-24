import { useState } from "react";

import CampoEtiquetado from "../../components/operacion/CampoEtiquetado";
import ConfirmarAccion from "../../components/operacion/ConfirmarAccion";
import { claseCampo, mensajeDe } from "../../components/seccion/utilidades";
import { totalesCarga } from "../../services/despacho-reglas";
import { cantidad } from "../../services/formato";
import { autorizarDespacho, cancelarDespacho, ejecutarDespacho, type Despacho } from "../../services/inventario.service";

type Paso = "nada" | "ejecutar" | "cancelar";

/*
  Autorizar y ejecutar son pasos distintos y se ven distintos: autorizar es un
  visto bueno que se puede deshacer cancelando; ejecutar saca el producto del
  inventario y no tiene vuelta. Por eso ejecutar y cancelar pasan por resumen.
*/
export default function HojaDeCarga({ hoja, autoriza, onCambio }: {
  hoja: Despacho;
  autoriza: boolean;
  onCambio: (mensaje: string) => void;
}) {
  const [paso, setPaso] = useState<Paso>("nada");
  const [motivo, setMotivo] = useState("");
  const [ocupado, setOcupado] = useState(false);
  const [error, setError] = useState("");
  const totales = totalesCarga(hoja.detalles, hoja.detalles_granel);
  const activa = hoja.estado === "borrador" || hoja.estado === "autorizado";

  const correr = async (accion: () => Promise<Despacho>, mensaje: string) => {
    setOcupado(true);
    setError("");
    try {
      await accion();
      setPaso("nada");
      onCambio(mensaje);
    } catch (causa) {
      setError(mensajeDe(causa, "No se pudo registrar la operación."));
    } finally {
      setOcupado(false);
    }
  };

  const resumenCarga = [
    { etiqueta: "Cliente", valor: hoja.cliente_nombre },
    { etiqueta: "Transporte", valor: [hoja.transportista, hoja.patente].filter(Boolean).join(" · ") || "—" },
    { etiqueta: "Pallets", valor: hoja.detalles.map((d) => `${d.pallet_codigo} (${d.ubicacion_codigo ?? "sin ubicación"})`).join(", ") || "—" },
    { etiqueta: "Total", valor: `${totales.pallets} pallets · ${cantidad(totales.kg, "kg")}${totales.litros ? ` · ${cantidad(totales.litros, "L")}` : ""}` },
  ];

  return (
    <article className="rounded-2xl border border-slate-200 bg-white p-5">
      <header className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h3 className="font-mono text-lg font-semibold text-slate-900">{hoja.numero}</h3>
          <p className="text-sm text-slate-700">{hoja.cliente_nombre}</p>
          <p className="text-sm text-slate-600">
            {[hoja.transportista, hoja.patente, hoja.guia_despacho && `Guía ${hoja.guia_despacho}`].filter(Boolean).join(" · ") || "Sin datos de transporte"}
          </p>
        </div>
        <p className="text-right text-sm font-semibold tabular-nums text-slate-900">
          {totales.pallets} pallets<br />{cantidad(totales.kg, "kg")}
          {totales.litros > 0 && <><br />{cantidad(totales.litros, "L")}</>}
        </p>
      </header>

      <ul className="mt-3 divide-y divide-slate-100 rounded-xl border border-slate-100 text-sm">
        {hoja.detalles.map((d) => (
          <li key={d.id} className="flex flex-wrap justify-between gap-2 px-3 py-2">
            <span><span className="font-mono">{d.pallet_codigo}</span> · lote {d.lote_codigo}</span>
            <span className="tabular-nums text-slate-700">{cantidad(d.kg_neto, "kg")}{d.ubicacion_codigo ? ` · ${d.ubicacion_codigo}` : ""}</span>
          </li>
        ))}
        {hoja.detalles_granel.map((g) => (
          <li key={`g-${g.id}`} className="flex flex-wrap justify-between gap-2 px-3 py-2">
            <span>Granel {g.producto_nombre} · {g.corrida_codigo}</span>
            <span className="tabular-nums text-slate-700">{cantidad(g.cantidad, g.unidad)}</span>
          </li>
        ))}
      </ul>

      {activa && !autoriza && (
        <p className="mt-3 text-sm text-slate-600">
          {hoja.estado === "borrador" ? "Espera la autorización de quien tiene permiso para autorizar despachos." : "Autorizada: la ejecuta quien tiene permiso para autorizar despachos."}
        </p>
      )}

      {activa && autoriza && paso === "nada" && (
        <div className="mt-4 flex flex-wrap items-center gap-3">
          {hoja.estado === "borrador" && (
            <button type="button" disabled={ocupado} onClick={() => void correr(() => autorizarDespacho(hoja.id), `Hoja ${hoja.numero} autorizada.`)}
              className="rounded-xl border-2 border-blue-700 px-5 py-2.5 text-sm font-semibold text-blue-800 hover:bg-blue-50 disabled:opacity-40">
              Autorizar
            </button>
          )}
          {hoja.estado === "autorizado" && (
            <button type="button" onClick={() => setPaso("ejecutar")}
              className="rounded-xl bg-green-700 px-6 py-3 text-sm font-bold text-white hover:bg-green-800">
              Ejecutar salida
            </button>
          )}
          <button type="button" onClick={() => setPaso("cancelar")} className="ml-auto text-sm font-medium text-red-700 underline-offset-2 hover:underline">
            Cancelar hoja
          </button>
        </div>
      )}

      {paso === "ejecutar" && (
        <div className="mt-4">
          <ConfirmarAccion
            titulo={`Ejecutar la salida de ${hoja.numero}`}
            filas={resumenCarga}
            advertencia="Los pallets salen del inventario. No se puede deshacer."
            textoConfirmar="Confirmar salida"
            ocupado={ocupado}
            error={error}
            onConfirmar={() => void correr(() => ejecutarDespacho(hoja.id), `Salida de ${hoja.numero} registrada.`)}
            onVolver={() => { setPaso("nada"); setError(""); }}
          />
        </div>
      )}

      {paso === "cancelar" && (
        <div className="mt-4 space-y-3">
          <CampoEtiquetado etiqueta="Motivo de la cancelación">
            <input value={motivo} onChange={(e) => setMotivo(e.target.value)} className={claseCampo} />
          </CampoEtiquetado>
          <ConfirmarAccion
            titulo={`Cancelar ${hoja.numero}`}
            filas={[...resumenCarga, { etiqueta: "Motivo", valor: motivo.trim() || "— (obligatorio)" }]}
            advertencia="La hoja queda cancelada, no se borra. Sus pallets vuelven a poder cargarse."
            textoConfirmar="Cancelar hoja"
            peligro
            ocupado={ocupado}
            error={error}
            onConfirmar={() => {
              if (!motivo.trim()) { setError("Escribe el motivo de la cancelación."); return; }
              void correr(() => cancelarDespacho(hoja.id, motivo.trim()), `Hoja ${hoja.numero} cancelada.`);
            }}
            onVolver={() => { setPaso("nada"); setError(""); }}
          />
        </div>
      )}

      {paso === "nada" && error && <p role="alert" className="mt-3 rounded-xl bg-red-50 px-4 py-2 text-sm text-red-800">{error}</p>}
    </article>
  );
}
