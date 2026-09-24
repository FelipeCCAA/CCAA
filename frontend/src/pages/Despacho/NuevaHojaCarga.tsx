import { useState, type FormEvent } from "react";

import BuscadorCodigo from "../../components/operacion/BuscadorCodigo";
import CampoEtiquetado from "../../components/operacion/CampoEtiquetado";
import ConfirmarAccion from "../../components/operacion/ConfirmarAccion";
import { claseBoton, claseCampo, mensajeDe } from "../../components/seccion/utilidades";
import { buscarPalletPorCodigo, identificarGranel, leerCantidadChilena, totalesCarga } from "../../services/despacho-reglas";
import { cantidad } from "../../services/formato";
import {
  crearDespacho, type ClienteDespacho, type ExistenciaProductoTerminado, type GranelDisponible,
} from "../../services/inventario.service";

/*
  Una hoja de carga es un camión: un cliente, un transporte y varios pallets.
  El número lo asigna el sistema al guardar; la guía del SII es opcional.
*/
export default function NuevaHojaCarga({ clientes, disponibles, graneles, onCreada, onFallo, onCerrar }: {
  clientes: ClienteDespacho[];
  disponibles: ExistenciaProductoTerminado[];
  graneles: GranelDisponible[];
  onCreada: (mensaje: string) => void;
  /* Un pallet o un granel pueden habérselos llevado otra hoja entre que se
     cargó la lista y que se guardó esta; recargar lo disponible después de
     un rechazo es lo que hace que la segunda vuelta ya no lo ofrezca. */
  onFallo?: () => void;
  onCerrar: () => void;
}) {
  const [cliente, setCliente] = useState("");
  const [transportista, setTransportista] = useState("");
  const [patente, setPatente] = useState("");
  const [guia, setGuia] = useState("");
  const [elegidos, setElegidos] = useState<number[]>([]);
  const [granel, setGranel] = useState<Record<number, string>>({});
  const [paso, setPaso] = useState<"datos" | "resumen">("datos");
  const [aviso, setAviso] = useState("");
  const [error, setError] = useState("");
  const [ocupado, setOcupado] = useState(false);

  const pallets = disponibles.filter((p) => elegidos.includes(p.pallet));
  const granelElegido = graneles
    .filter((g) => granel[g.id] !== undefined)
    .map((g) => ({ salida: g, cantidad: leerCantidadChilena(granel[g.id]) }));
  const totales = totalesCarga(
    pallets,
    granelElegido.map((g) => ({ cantidad: g.cantidad ?? 0, unidad: g.salida.unidad })),
  );
  const clienteElegido = clientes.find((c) => String(c.id) === cliente);

  const alternar = (pallet: number) =>
    setElegidos((actual) => (actual.includes(pallet) ? actual.filter((id) => id !== pallet) : [...actual, pallet]));

  const escanear = (codigo: string) => {
    const encontrado = buscarPalletPorCodigo(disponibles, codigo);
    if (!encontrado) {
      setAviso(`El pallet ${codigo} no está disponible para cargar: no existe, no está liberado en una ubicación disponible o ya está en otra hoja.`);
      return;
    }
    setAviso(elegidos.includes(encontrado.pallet) ? `${encontrado.pallet_codigo} ya estaba en la hoja.` : `${encontrado.pallet_codigo} agregado.`);
    if (!elegidos.includes(encontrado.pallet)) setElegidos((actual) => [...actual, encontrado.pallet]);
  };

  const revisar = (evento: FormEvent) => {
    evento.preventDefault();
    if (!clienteElegido) return setError("Elige el cliente.");
    if (pallets.length === 0 && granelElegido.length === 0) return setError("Agrega al menos un pallet o un granel.");
    const malo = granelElegido.find((g) => g.cantidad === null || g.cantidad > Number(g.salida.cantidad_disponible));
    if (malo) return setError(`La cantidad de ${malo.salida.producto_nombre} debe ser mayor que cero y hasta ${cantidad(malo.salida.cantidad_disponible, malo.salida.unidad)}.`);
    setError("");
    setPaso("resumen");
  };

  const guardar = async () => {
    setOcupado(true);
    setError("");
    try {
      const hoja = await crearDespacho({
        cliente: Number(cliente),
        pallet_ids: pallets.map((p) => p.pallet),
        // La validación en `revisar()` ya descartó cualquier cantidad nula
        // antes de dejar avanzar hasta este paso; el `?? 0` es solo para que
        // el tipo cierre, no una cantidad que vaya a viajar de verdad.
        graneles: granelElegido.map((g) => ({ salida: g.salida.id, cantidad: g.cantidad ?? 0 })),
        transportista: transportista.trim(), patente: patente.trim().toUpperCase(), guia_despacho: guia.trim(),
      });
      onCreada(`Hoja ${hoja.numero} creada en borrador con ${totales.pallets} pallets.`);
    } catch (causa) {
      setError(mensajeDe(causa, "No se pudo crear la hoja de carga."));
      onFallo?.();
    } finally {
      setOcupado(false);
    }
  };

  return (
    <section aria-labelledby="nueva-hoja-titulo" className="rounded-2xl border border-green-200 bg-white p-5 shadow-sm">
      <div className="mb-4 flex items-start justify-between gap-4">
        <h2 id="nueva-hoja-titulo" className="text-lg font-semibold text-slate-900">Nueva hoja de carga</h2>
        <button type="button" onClick={onCerrar} className="text-sm font-medium text-slate-600 hover:text-slate-900">Cerrar</button>
      </div>

      {paso === "resumen" ? (
        <ConfirmarAccion
          titulo="Revisa la hoja antes de guardarla"
          filas={[
            { etiqueta: "Cliente", valor: clienteElegido?.nombre ?? "—" },
            { etiqueta: "Transporte", valor: [transportista.trim(), patente.trim().toUpperCase()].filter(Boolean).join(" · ") || "—" },
            { etiqueta: "Guía de despacho", valor: guia.trim() || "Sin guía" },
            { etiqueta: "Pallets", valor: pallets.map((p) => p.pallet_codigo).join(", ") || "—" },
            ...(granelElegido.length > 0
              ? [{
                  etiqueta: "Graneles",
                  valor: granelElegido
                    .map((g) => `${g.salida.producto_nombre} · ${identificarGranel(g.salida, { silo: g.salida.silo_codigo })} · ${cantidad(g.cantidad ?? 0, g.salida.unidad)}`)
                    .join(", "),
                }]
              : []),
            { etiqueta: "Total", valor: `${totales.pallets} pallets · ${cantidad(totales.kg, "kg")}${totales.litros ? ` · ${cantidad(totales.litros, "L")}` : ""}` },
          ]}
          advertencia="Queda en borrador: la salida se ejecuta después de autorizarla."
          textoConfirmar="Guardar hoja"
          ocupado={ocupado}
          error={error}
          onConfirmar={() => void guardar()}
          onVolver={() => { setPaso("datos"); setError(""); }}
        />
      ) : (
        <form onSubmit={revisar} className="space-y-5">
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <CampoEtiquetado etiqueta="Cliente">
              <select value={cliente} onChange={(e) => setCliente(e.target.value)} className={claseCampo}>
                <option value="">Elige el cliente…</option>
                {clientes.filter((c) => c.activo).map((c) => <option key={c.id} value={c.id}>{c.nombre}</option>)}
              </select>
            </CampoEtiquetado>
            <CampoEtiquetado etiqueta="Transportista">
              <input value={transportista} onChange={(e) => setTransportista(e.target.value)} className={claseCampo} />
            </CampoEtiquetado>
            <CampoEtiquetado etiqueta="Patente">
              <input value={patente} onChange={(e) => setPatente(e.target.value)} className={claseCampo} autoComplete="off" />
            </CampoEtiquetado>
            <CampoEtiquetado etiqueta="Guía de despacho (opcional)" ayuda="La del SII, si ya está emitida.">
              <input value={guia} onChange={(e) => setGuia(e.target.value)} className={claseCampo} autoComplete="off" />
            </CampoEtiquetado>
          </div>

          <BuscadorCodigo etiqueta="Agregar pallet por código" onBuscar={escanear} />
          {aviso && <p role="status" className="text-sm text-slate-700">{aviso}</p>}

          <fieldset className="rounded-xl border border-slate-200">
            <legend className="px-2 text-sm font-medium text-slate-700">Pallets disponibles ({disponibles.length})</legend>
            {disponibles.length === 0 ? (
              <p className="px-4 py-3 text-sm text-slate-600">No hay pallets liberados en ubicaciones disponibles sin otra hoja.</p>
            ) : (
              <ul className="max-h-80 divide-y divide-slate-100 overflow-y-auto">
                {disponibles.map((p) => (
                  <li key={p.id}>
                    <label className="flex cursor-pointer flex-wrap items-center gap-3 px-4 py-2 text-sm hover:bg-slate-50">
                      <input type="checkbox" checked={elegidos.includes(p.pallet)} onChange={() => alternar(p.pallet)} className="h-4 w-4" />
                      <span className="font-mono">{p.pallet_codigo}</span>
                      <span className="text-slate-700">{p.producto_nombre} · lote {p.lote_codigo}</span>
                      <span className="ml-auto tabular-nums text-slate-700">{cantidad(p.kg_neto, "kg")} · {p.ubicacion_codigo}</span>
                    </label>
                  </li>
                ))}
              </ul>
            )}
          </fieldset>

          {graneles.length > 0 && (
            <fieldset className="rounded-xl border border-slate-200">
              <legend className="px-2 text-sm font-medium text-slate-700">Graneles liberados</legend>
              <ul className="divide-y divide-slate-100">
                {graneles.map((g) => (
                  <li key={g.id} className="flex flex-wrap items-center gap-3 px-4 py-2 text-sm">
                    <label className="flex items-center gap-3">
                      <input type="checkbox" checked={granel[g.id] !== undefined} className="h-4 w-4"
                        onChange={() => setGranel((actual) => {
                          const copia = { ...actual };
                          if (copia[g.id] !== undefined) delete copia[g.id]; else copia[g.id] = String(g.cantidad_disponible).replace(".", ","); // coma decimal: «12.345» se leería como miles
                          return copia;
                        })} />
                      {g.producto_nombre} · {identificarGranel(g)} · hasta {cantidad(g.cantidad_disponible, g.unidad)}
                    </label>
                    {granel[g.id] !== undefined && (
                      <input aria-label={`Cantidad de ${g.producto_nombre} (${g.unidad})`} inputMode="decimal" value={granel[g.id]}
                        onChange={(e) => setGranel((actual) => ({ ...actual, [g.id]: e.target.value }))} className={`${claseCampo} ml-auto w-32`} />
                    )}
                  </li>
                ))}
              </ul>
            </fieldset>
          )}

          <div className="sticky bottom-0 flex flex-wrap items-center justify-between gap-3 rounded-xl bg-slate-900 px-5 py-3 text-white">
            <p className="text-sm font-semibold tabular-nums" aria-live="polite">
              {totales.pallets} pallets · {cantidad(totales.kg, "kg")}{totales.litros ? ` · ${cantidad(totales.litros, "L")}` : ""}
            </p>
            <button type="submit" className={claseBoton}>Revisar hoja</button>
          </div>
          {error && <p role="alert" className="rounded-xl bg-red-50 px-4 py-2 text-sm text-red-800">{error}</p>}
        </form>
      )}
    </section>
  );
}
