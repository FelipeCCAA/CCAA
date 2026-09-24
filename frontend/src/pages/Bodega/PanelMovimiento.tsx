import { useState, type FormEvent } from "react";
import { X } from "lucide-react";

import CampoEtiquetado from "../../components/operacion/CampoEtiquetado";
import ConfirmarAccion, { type FilaResumen } from "../../components/operacion/ConfirmarAccion";
import { claseBoton, claseCampo, mensajeDe } from "../../components/seccion/utilidades";
import { ajustePorConteo, leerCantidad, tiposDeDestino } from "../../services/bodega-reglas";
import { cantidad } from "../../services/formato";
import {
  crearAjuste, ingresarMaterial, ingresarPallet, registrarSalida, transferirPallet, trasladarExistencia,
  type Existencia, type ExistenciaProductoTerminado, type Insumo, type PalletPorUbicar, type UbicacionInventario,
} from "../../services/inventario.service";

export type AccionBodega =
  | { tipo: "recibir" }
  | { tipo: "reubicar-material" | "consumir" | "contar"; existencia: Existencia }
  | { tipo: "reubicar-pallet"; pallet: ExistenciaProductoTerminado }
  | { tipo: "ubicar-liberado"; pallet: PalletPorUbicar };

const TITULOS: Record<AccionBodega["tipo"], string> = {
  recibir: "Recibir material",
  "reubicar-material": "Reubicar material",
  consumir: "Consumir material",
  contar: "Ajustar por conteo",
  "reubicar-pallet": "Reubicar pallet",
  "ubicar-liberado": "Ubicar pallet liberado",
};

/*
  Un movimiento en tres pasos: qué (viene elegido desde la ficha o el
  pendiente), adónde y cuánto, y resumen antes de registrar. Al terminar
  entrega el mensaje del movimiento con el saldo que dejó.
*/
export default function PanelMovimiento({ accion, ubicaciones, insumos, onCerrar, onHecho }: {
  accion: AccionBodega;
  ubicaciones: UbicacionInventario[];
  insumos: Insumo[];
  onCerrar: () => void;
  onHecho: (mensaje: string) => void;
}) {
  const [paso, setPaso] = useState<"datos" | "resumen">("datos");
  const [destino, setDestino] = useState("");
  const [texto, setTexto] = useState("");
  const [motivo, setMotivo] = useState("");
  const [insumoId, setInsumoId] = useState("");
  const [codigoLote, setCodigoLote] = useState("");
  const [vencimiento, setVencimiento] = useState("");
  const [ocupado, setOcupado] = useState(false);
  const [error, setError] = useState("");

  const existencia = "existencia" in accion ? accion.existencia : null;
  const insumo = insumos.find((item) => String(item.id) === insumoId) ?? null;
  const unidad = existencia?.unidad ?? insumo?.unidad ?? "kg";
  const origenId =
    existencia?.ubicacion ?? (accion.tipo === "reubicar-pallet" ? accion.pallet.ubicacion : null);
  const tipos = tiposDeDestino(accion.tipo, {
    origenTipo: existencia?.ubicacion_tipo,
    requiereCalidad: insumo?.requiere_calidad,
  });
  const destinos = ubicaciones.filter((u) => u.activo && u.id !== origenId && tipos.includes(u.tipo));
  const pideDestino = tipos.length > 0;
  const pideCantidad = accion.tipo === "recibir" || accion.tipo === "reubicar-material" || accion.tipo === "consumir";
  const destinoElegido = ubicaciones.find((u) => String(u.id) === destino);
  const numero = leerCantidad(texto);
  const conteo = accion.tipo === "contar" && existencia ? ajustePorConteo(existencia.cantidad_fisica, texto.replace(",", ".")) : null;

  const validar = (): string => {
    if (accion.tipo === "recibir") {
      if (!insumo) return "Elige el material.";
      if (!codigoLote.trim()) return "Escribe el lote del proveedor.";
      if (insumo.requiere_vencimiento && !vencimiento) return "Este material exige fecha de vencimiento.";
    }
    if (pideDestino && !destinoElegido) return "Elige la ubicación de destino.";
    if (pideCantidad && numero === null) return "Escribe una cantidad mayor que cero.";
    if (pideCantidad && existencia && numero !== null && numero > Number(existencia.cantidad_disponible)) {
      return `Hay ${cantidad(existencia.cantidad_disponible, unidad)} disponibles en esa ubicación.`;
    }
    if (accion.tipo === "contar") {
      if (texto.trim() === "" || !Number.isFinite(Number(texto.replace(",", ".")))) return "Escribe cuánto contaste.";
      if (!conteo) return "Lo contado coincide con el sistema: no hay nada que ajustar.";
      if (!motivo.trim()) return "El ajuste necesita un motivo.";
    }
    return "";
  };

  const revisar = (evento: FormEvent) => {
    evento.preventDefault();
    const problema = validar();
    setError(problema);
    if (!problema) setPaso("resumen");
  };

  const resumen = (): FilaResumen[] => {
    const hacia = destinoElegido ? `${destinoElegido.codigo} · ${destinoElegido.bodega_nombre}` : "—";
    switch (accion.tipo) {
      case "recibir":
        return [
          { etiqueta: "Material", valor: insumo ? `${insumo.codigo} · ${insumo.nombre}` : "—" },
          { etiqueta: "Lote del proveedor", valor: codigoLote.trim() },
          { etiqueta: "Cantidad", valor: cantidad(numero, unidad) },
          { etiqueta: "Destino", valor: hacia },
          ...(vencimiento ? [{ etiqueta: "Vencimiento", valor: vencimiento }] : []),
        ];
      case "reubicar-material":
      case "consumir":
        return [
          { etiqueta: "Material", valor: accion.existencia.insumo_nombre },
          { etiqueta: "Lote", valor: accion.existencia.lote_codigo },
          { etiqueta: "Desde", valor: accion.existencia.ubicacion_codigo },
          ...(accion.tipo === "reubicar-material" ? [{ etiqueta: "Hacia", valor: hacia }] : []),
          { etiqueta: "Cantidad", valor: cantidad(numero, unidad) },
          ...(motivo.trim() ? [{ etiqueta: "Motivo", valor: motivo.trim() }] : []),
        ];
      case "contar":
        return [
          { etiqueta: "Material", valor: accion.existencia.insumo_nombre },
          { etiqueta: "Lote", valor: accion.existencia.lote_codigo },
          { etiqueta: "Ubicación", valor: accion.existencia.ubicacion_codigo },
          { etiqueta: "En sistema", valor: cantidad(accion.existencia.cantidad_fisica, unidad) },
          { etiqueta: "Contado", valor: cantidad(texto.replace(",", "."), unidad) },
          { etiqueta: "Ajuste", valor: conteo ? `${conteo.tipo === "positivo" ? "+" : "−"}${cantidad(conteo.cantidad, unidad)}` : "—" },
          { etiqueta: "Motivo", valor: motivo.trim() },
        ];
      case "reubicar-pallet":
        return [
          { etiqueta: "Pallet", valor: accion.pallet.pallet_codigo },
          { etiqueta: "Producto", valor: `${accion.pallet.producto_nombre} · lote ${accion.pallet.lote_codigo}` },
          { etiqueta: "Desde", valor: accion.pallet.ubicacion_codigo },
          { etiqueta: "Hacia", valor: hacia },
          { etiqueta: "Peso", valor: cantidad(accion.pallet.kg_neto, "kg") },
        ];
      case "ubicar-liberado":
        return [
          { etiqueta: "Pallet", valor: accion.pallet.pallet_codigo },
          { etiqueta: "Producto", valor: `${accion.pallet.producto_nombre} · lote ${accion.pallet.lote_codigo}` },
          { etiqueta: "Desde", valor: `${accion.pallet.ubicacion_codigo} (cuarentena)` },
          { etiqueta: "Hacia", valor: hacia },
          { etiqueta: "Peso", valor: cantidad(accion.pallet.kg_neto, "kg") },
        ];
    }
  };

  const ejecutar = async (): Promise<string> => {
    const idDestino = Number(destino);
    switch (accion.tipo) {
      case "recibir": {
        const m = await ingresarMaterial({
          insumo: Number(insumoId), codigo_lote: codigoLote.trim(), ubicacion: idDestino,
          cantidad: numero ?? 0, vencimiento: vencimiento || undefined,
        });
        return `Ingreso registrado: ${cantidad(m.cantidad, unidad)} de ${m.insumo_nombre} en ${m.destino_codigo}. Saldo del lote ahí: ${cantidad(m.saldo_posterior, unidad)}.`;
      }
      case "reubicar-material": {
        const m = await trasladarExistencia({
          existencia: accion.existencia.id, destino: idDestino, cantidad: numero ?? 0, motivo: motivo.trim(),
        });
        return `Traslado registrado: ${cantidad(m.cantidad, unidad)} de ${m.insumo_nombre}, de ${m.origen_codigo} a ${m.destino_codigo}.`;
      }
      case "consumir": {
        const m = await registrarSalida({
          existencia: accion.existencia.id, cantidad: numero ?? 0, tipo: "consumo", motivo: motivo.trim(),
        });
        return `Consumo registrado: ${cantidad(m.cantidad, unidad)} de ${m.insumo_nombre}. Quedan ${cantidad(m.saldo_posterior, unidad)} en ${m.origen_codigo}.`;
      }
      case "contar": {
        const a = await crearAjuste({
          existencia: accion.existencia.id, tipo: conteo!.tipo, cantidad: conteo!.cantidad, motivo: motivo.trim(),
        });
        return `Ajuste ${a.tipo} de ${cantidad(a.cantidad, unidad)} enviado a aprobación. Lo aprueba otra persona.`;
      }
      case "reubicar-pallet": {
        const e = await transferirPallet(accion.pallet.id, idDestino, motivo.trim());
        return `Pallet ${e.pallet_codigo} movido a ${e.ubicacion_codigo}.`;
      }
      case "ubicar-liberado": {
        const e = await ingresarPallet(accion.pallet.pallet_id, idDestino);
        return `Pallet ${e.pallet_codigo} ubicado en ${e.ubicacion_codigo}. Ya está disponible para despacho.`;
      }
    }
  };

  const confirmar = async () => {
    setOcupado(true);
    setError("");
    try {
      onHecho(await ejecutar());
    } catch (causa) {
      setError(mensajeDe(causa, "No se pudo registrar el movimiento."));
    } finally {
      setOcupado(false);
    }
  };

  return (
    <section aria-labelledby="panel-movimiento-titulo" className="rounded-2xl border border-green-200 bg-white p-5 shadow-sm">
      <div className="mb-4 flex items-start justify-between gap-4">
        <div>
          <p className="text-xs font-semibold uppercase tracking-wider text-green-700">
            Paso {paso === "datos" ? "2" : "3"} de 3
          </p>
          <h2 id="panel-movimiento-titulo" className="text-lg font-semibold text-slate-900">{TITULOS[accion.tipo]}</h2>
        </div>
        <button type="button" onClick={onCerrar} aria-label="Cerrar sin registrar" className="rounded-lg p-2 text-slate-600 hover:bg-slate-100">
          <X className="h-5 w-5" />
        </button>
      </div>

      {paso === "resumen" ? (
        <ConfirmarAccion
          titulo="Revisa antes de registrar"
          filas={resumen()}
          advertencia={accion.tipo === "contar" ? "El ajuste queda pendiente hasta que otra persona lo apruebe." : undefined}
          textoConfirmar={accion.tipo === "contar" ? "Enviar ajuste" : "Registrar movimiento"}
          ocupado={ocupado}
          error={error}
          onConfirmar={() => void confirmar()}
          onVolver={() => { setPaso("datos"); setError(""); }}
        />
      ) : (
        <form onSubmit={revisar} className="grid gap-4 sm:grid-cols-2">
          {accion.tipo === "recibir" && (
            <>
              <CampoEtiquetado etiqueta="Material">
                <select value={insumoId} onChange={(e) => { setInsumoId(e.target.value); setDestino(""); }} className={claseCampo}>
                  <option value="">Elige el material…</option>
                  {insumos.map((i) => <option key={i.id} value={i.id}>{i.codigo} · {i.nombre} ({i.unidad})</option>)}
                </select>
              </CampoEtiquetado>
              <CampoEtiquetado etiqueta="Lote del proveedor">
                <input value={codigoLote} onChange={(e) => setCodigoLote(e.target.value)} className={claseCampo} autoComplete="off" />
              </CampoEtiquetado>
              {insumo?.requiere_vencimiento && (
                <CampoEtiquetado etiqueta="Vencimiento">
                  <input type="date" value={vencimiento} onChange={(e) => setVencimiento(e.target.value)} className={claseCampo} />
                </CampoEtiquetado>
              )}
            </>
          )}

          {existencia && (
            <p className="rounded-xl bg-slate-50 px-4 py-3 text-sm text-slate-700 sm:col-span-2">
              {existencia.insumo_nombre} · lote {existencia.lote_codigo} · en {existencia.ubicacion_codigo}:{" "}
              <strong>{cantidad(existencia.cantidad_fisica, unidad)}</strong> físicas,{" "}
              {cantidad(existencia.cantidad_disponible, unidad)} disponibles
            </p>
          )}

          {pideDestino && (
            <CampoEtiquetado
              etiqueta="Destino"
              ayuda={destinos.length === 0 ? "No hay ubicaciones válidas para este movimiento; créalas en Configuración." : undefined}
            >
              <select value={destino} onChange={(e) => setDestino(e.target.value)} className={claseCampo}>
                <option value="">Elige la ubicación…</option>
                {destinos.map((u) => <option key={u.id} value={u.id}>{u.codigo} · {u.bodega_nombre} ({u.tipo_etiqueta})</option>)}
              </select>
            </CampoEtiquetado>
          )}

          {pideCantidad && (
            <CampoEtiquetado etiqueta={`Cantidad (${unidad})`}>
              <input inputMode="decimal" value={texto} onChange={(e) => setTexto(e.target.value)} className={claseCampo} autoComplete="off" />
            </CampoEtiquetado>
          )}

          {accion.tipo === "contar" && (
            <CampoEtiquetado etiqueta={`Cantidad contada (${unidad})`} ayuda="Lo que hay en la estantería, no la diferencia.">
              <input inputMode="decimal" value={texto} onChange={(e) => setTexto(e.target.value)} className={claseCampo} autoComplete="off" />
            </CampoEtiquetado>
          )}

          {accion.tipo !== "recibir" && accion.tipo !== "ubicar-liberado" && (
            <CampoEtiquetado etiqueta={accion.tipo === "contar" ? "Motivo" : "Motivo (opcional)"}>
              <input value={motivo} onChange={(e) => setMotivo(e.target.value)} className={claseCampo} />
            </CampoEtiquetado>
          )}

          {error && <p role="alert" className="rounded-xl bg-red-50 px-4 py-2 text-sm text-red-800 sm:col-span-2">{error}</p>}

          <div className="sm:col-span-2">
            <button type="submit" className={claseBoton}>Revisar</button>
          </div>
        </form>
      )}
    </section>
  );
}
