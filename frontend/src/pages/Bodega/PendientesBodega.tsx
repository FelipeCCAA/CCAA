import { useState } from "react";

import ConfirmarAccion from "../../components/operacion/ConfirmarAccion";
import { Tarjeta, Vacio } from "../../components/seccion/componentes";
import { mensajeDe } from "../../components/seccion/utilidades";
import { cantidad } from "../../services/formato";
import {
  decidirAjuste, type AjustePendiente, type PalletPorUbicar, type PendientesBodega as Pendientes,
} from "../../services/inventario.service";

/*
  Lo que Bodega tiene que resolver. Cada fila lleva su acción; lo que decide
  otra área (Calidad, Compras) se muestra sin botón, para que se sepa que está
  y a quién le toca.
*/
export default function PendientesBodega({ datos, usuarioId, onUbicar, onCambio }: {
  datos: Pendientes;
  usuarioId: number | undefined;
  onUbicar: (pallet: PalletPorUbicar) => void;
  onCambio: (mensaje: string) => void;
}) {
  const [decision, setDecision] = useState<{ ajuste: AjustePendiente; aprobar: boolean } | null>(null);
  const [ocupado, setOcupado] = useState(false);
  const [error, setError] = useState("");

  const decidir = async () => {
    if (!decision) return;
    setOcupado(true);
    setError("");
    try {
      await decidirAjuste(decision.ajuste.id, decision.aprobar ? "aprobar" : "rechazar");
      onCambio(`Ajuste de ${decision.ajuste.insumo_nombre} ${decision.aprobar ? "aprobado y aplicado" : "rechazado"}.`);
      setDecision(null);
    } catch (causa) {
      setError(mensajeDe(causa, "No se pudo registrar la decisión."));
    } finally {
      setOcupado(false);
    }
  };

  if (datos.total === 0) {
    return <Tarjeta titulo="Pendientes"><Vacio>No hay nada pendiente en bodega.</Vacio></Tarjeta>;
  }

  return (
    <div className="space-y-4">
      {datos.pallets_por_ubicar.length > 0 && (
        <Tarjeta titulo={`Pallets liberados por ubicar (${datos.pallets_por_ubicar.length})`} descripcion="Calidad los liberó y siguen en cuarentena: muévelos a una ubicación disponible para poder despacharlos." sinRelleno>
          <ul className="divide-y divide-slate-100">
            {datos.pallets_por_ubicar.map((p) => (
              <li key={p.existencia_id} className="flex flex-wrap items-center justify-between gap-3 px-5 py-3 text-sm">
                <span><strong className="font-mono">{p.pallet_codigo}</strong> · {p.producto_nombre} · lote {p.lote_codigo} · {cantidad(p.kg_neto, "kg")} · en {p.ubicacion_codigo}</span>
                <button type="button" onClick={() => onUbicar(p)} className="rounded-xl bg-green-700 px-4 py-2 text-sm font-semibold text-white hover:bg-green-800">Ubicar</button>
              </li>
            ))}
          </ul>
        </Tarjeta>
      )}

      {datos.ajustes_pendientes.length > 0 && (
        <Tarjeta titulo={`Ajustes por aprobar (${datos.ajustes_pendientes.length})`} descripcion="Un ajuste lo aprueba una persona distinta de quien lo pidió." sinRelleno>
          <ul className="divide-y divide-slate-100">
            {datos.ajustes_pendientes.map((a) => (
              <li key={a.id} className="flex flex-wrap items-center justify-between gap-3 px-5 py-3 text-sm">
                <span>
                  {a.tipo_etiqueta} de <strong>{cantidad(a.cantidad, a.unidad)}</strong> · {a.insumo_nombre} · lote {a.lote_codigo} · {a.ubicacion_codigo}
                  <span className="block text-slate-600">«{a.motivo}» — pidió {a.solicitante_nombre}</span>
                </span>
                {a.solicitante_id === usuarioId ? (
                  <span className="text-slate-600">Lo aprueba otra persona</span>
                ) : (
                  <span className="flex gap-2">
                    <button type="button" onClick={() => setDecision({ ajuste: a, aprobar: true })} className="rounded-xl bg-green-700 px-4 py-2 font-semibold text-white hover:bg-green-800">Aprobar</button>
                    <button type="button" onClick={() => setDecision({ ajuste: a, aprobar: false })} className="rounded-xl border border-slate-300 px-4 py-2 font-medium text-slate-700 hover:bg-slate-100">Rechazar</button>
                  </span>
                )}
              </li>
            ))}
          </ul>
          {decision && (
            <div className="border-t border-slate-200 p-5">
              <ConfirmarAccion
                titulo={decision.aprobar ? "Aprobar y aplicar el ajuste" : "Rechazar el ajuste"}
                filas={[
                  { etiqueta: "Material", valor: `${decision.ajuste.insumo_nombre} · lote ${decision.ajuste.lote_codigo}` },
                  { etiqueta: "Ubicación", valor: decision.ajuste.ubicacion_codigo },
                  { etiqueta: "Ajuste", valor: `${decision.ajuste.tipo_etiqueta}: ${cantidad(decision.ajuste.cantidad, decision.ajuste.unidad)}` },
                  { etiqueta: "Motivo", valor: decision.ajuste.motivo },
                ]}
                advertencia={decision.aprobar ? "Aprobar mueve el saldo de inmediato." : undefined}
                textoConfirmar={decision.aprobar ? "Aprobar" : "Rechazar"}
                peligro={!decision.aprobar}
                ocupado={ocupado}
                error={error}
                onConfirmar={() => void decidir()}
                onVolver={() => { setDecision(null); setError(""); }}
              />
            </div>
          )}
        </Tarjeta>
      )}

      {datos.material_en_cuarentena.length > 0 && (
        <Tarjeta titulo={`Material en cuarentena (${datos.material_en_cuarentena.length})`} descripcion="Lo decide Calidad. Aparece para que sepas qué no se puede usar todavía." sinRelleno>
          <ul className="divide-y divide-slate-100">
            {datos.material_en_cuarentena.map((m) => (
              <li key={m.existencia_id} className="px-5 py-3 text-sm">{m.insumo_nombre} · lote {m.lote_codigo} · {cantidad(m.cantidad, m.unidad)} · en {m.ubicacion_codigo}</li>
            ))}
          </ul>
        </Tarjeta>
      )}

      {datos.bajo_minimo.length > 0 && (
        <Tarjeta titulo={`Bajo el mínimo (${datos.bajo_minimo.length})`} descripcion="Disponible igual o menor que el stock mínimo. Avísale a Compras." sinRelleno>
          <ul className="divide-y divide-slate-100">
            {datos.bajo_minimo.map((m) => (
              <li key={m.insumo_id} className="px-5 py-3 text-sm">{m.codigo} · {m.nombre}: {cantidad(m.disponible, m.unidad)} disponibles, mínimo {cantidad(m.stock_minimo, m.unidad)}</li>
            ))}
          </ul>
        </Tarjeta>
      )}
    </div>
  );
}
