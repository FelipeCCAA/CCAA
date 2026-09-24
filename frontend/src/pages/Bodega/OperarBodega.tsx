import { useState } from "react";
import { PackagePlus } from "lucide-react";

import BuscadorCodigo from "../../components/operacion/BuscadorCodigo";
import { Aviso, Tarjeta } from "../../components/seccion/componentes";
import { claseBoton, useCarga } from "../../components/seccion/utilidades";
import { cantidad } from "../../services/formato";
import {
  buscarExistencias, buscarProductoTerminado, obtenerCatalogosInventario, obtenerInsumos,
  obtenerPendientesBodega, obtenerUbicaciones,
  type Existencia, type ExistenciaProductoTerminado,
} from "../../services/inventario.service";
import { obtenerSesion } from "../../services/sesion";
import PanelMovimiento, { type AccionBodega } from "./PanelMovimiento";
import PendientesBodega from "./PendientesBodega";

interface Resultado {
  texto: string;
  pallets: ExistenciaProductoTerminado[];
  materiales: Existencia[];
  errores: string[];
}

/* Una acción trae siempre lo mismo, más un identificador que la distingue de
   la siguiente. Es lo que se usa como `key` del panel: cambiar de acción no
   debe arrastrar el paso, el destino o la cantidad de la anterior. */
function claveDeAccion(accion: AccionBodega): string {
  switch (accion.tipo) {
    case "recibir":
      return "recibir";
    case "reubicar-pallet":
      return `${accion.tipo}-${accion.pallet.id}`;
    case "ubicar-liberado":
      return `${accion.tipo}-${accion.pallet.existencia_id}`;
    default:
      return `${accion.tipo}-${accion.existencia.id}`;
  }
}

/* La etiqueta que sirve el catálogo, o el código crudo si el catálogo no
   cargó: mejor un código que un espacio en blanco. */
function etiquetaDe(lista: { valor: string; etiqueta: string }[] | undefined, valor: string): string {
  return lista?.find((opcion) => opcion.valor === valor)?.etiqueta ?? valor;
}

/* Paso 1 de cada movimiento: encontrar la cosa. Todo lo demás cuelga de aquí. */
export default function OperarBodega() {
  const usuarioId = obtenerSesion()?.usuario.id;
  const pendientes = useCarga(obtenerPendientesBodega);
  const ubicaciones = useCarga(obtenerUbicaciones);
  const insumos = useCarga(obtenerInsumos);
  // Auxiliar: solo rotula estados en pantalla. Si el catálogo no carga, se
  // muestra el código crudo en vez de vaciar toda la búsqueda.
  const catalogos = useCarga(obtenerCatalogosInventario);
  const [buscando, setBuscando] = useState(false);
  const [resultado, setResultado] = useState<Resultado | null>(null);
  const [accion, setAccion] = useState<AccionBodega | null>(null);
  const [hecho, setHecho] = useState("");

  const buscar = async (texto: string) => {
    setBuscando(true);
    setHecho("");
    // Por separado: si falla una búsqueda, la otra igual se muestra.
    const [pallets, materiales] = await Promise.allSettled([
      buscarProductoTerminado({ q: texto }),
      buscarExistencias({ q: texto, con_saldo: true }),
    ]);
    setResultado({
      texto,
      pallets: pallets.status === "fulfilled" ? pallets.value.results : [],
      materiales: materiales.status === "fulfilled" ? materiales.value.results : [],
      errores: [
        ...(pallets.status === "rejected" ? ["No se pudieron buscar pallets."] : []),
        ...(materiales.status === "rejected" ? ["No se pudo buscar material."] : []),
      ],
    });
    setBuscando(false);
  };

  const terminar = (mensaje: string) => {
    setAccion(null);
    setHecho(mensaje);
    setResultado(null);
    void pendientes.recargar();
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-end gap-4 rounded-2xl border border-slate-200 bg-white p-5">
        <div className="min-w-0 flex-1">
          <BuscadorCodigo
            etiqueta="Pallet, lote o material"
            ayuda="Escanea la etiqueta o escribe parte del código o del nombre."
            ocupado={buscando}
            onBuscar={(texto) => void buscar(texto)}
          />
        </div>
        <button type="button" onClick={() => { setAccion({ tipo: "recibir" }); setHecho(""); }} className={`${claseBoton} inline-flex items-center gap-2`}>
          <PackagePlus className="h-4 w-4" /> Recibir material
        </button>
      </div>

      {hecho && <p role="status" className="rounded-xl border border-green-200 bg-green-50 px-4 py-3 text-sm text-green-900">{hecho}</p>}

      {accion && (
        <PanelMovimiento
          key={claveDeAccion(accion)}
          accion={accion}
          ubicaciones={ubicaciones.datos ?? []}
          insumos={insumos.datos ?? []}
          onCerrar={() => setAccion(null)}
          onHecho={terminar}
        />
      )}
      {accion && ubicaciones.error && <Aviso>No se pudieron cargar las ubicaciones: {ubicaciones.error}</Aviso>}
      {accion?.tipo === "recibir" && insumos.error && <Aviso>No se pudieron cargar los materiales: {insumos.error}</Aviso>}

      {resultado && !accion && (
        <Tarjeta titulo={`Resultados para «${resultado.texto}»`} sinRelleno>
          {resultado.errores.map((e) => <p key={e} role="alert" className="px-5 pt-3 text-sm text-red-800">{e}</p>)}
          {resultado.pallets.length === 0 && resultado.materiales.length === 0 && resultado.errores.length === 0 && (
            <p className="px-5 py-4 text-sm text-slate-600">No hay pallets ni material con «{resultado.texto}».</p>
          )}
          <ul className="divide-y divide-slate-100">
            {resultado.pallets.map((p) => (
              <li key={`p-${p.id}`} className="flex flex-wrap items-center justify-between gap-3 px-5 py-4 text-sm">
                <span>
                  <strong className="font-mono">{p.pallet_codigo}</strong> · {p.producto_nombre} · lote {p.lote_codigo}
                  <span className="block text-slate-600">
                    {cantidad(p.kg_neto, "kg")} · en {p.ubicacion_codigo} · {etiquetaDe(catalogos.datos?.estado_pallet, p.estado_inventario)}
                  </span>
                </span>
                {p.estado_inventario === "disponible" && p.ubicacion_tipo === "disponible" && (
                  <button type="button" onClick={() => setAccion({ tipo: "reubicar-pallet", pallet: p })} className="rounded-xl border border-slate-300 px-4 py-2 font-medium text-slate-800 hover:bg-slate-100">Reubicar</button>
                )}
                {p.estado_inventario === "disponible" && p.ubicacion_tipo === "cuarentena" && (
                  <button
                    type="button"
                    onClick={() => setAccion({ tipo: "ubicar-liberado", pallet: {
                      existencia_id: p.id, pallet_id: p.pallet, pallet_codigo: p.pallet_codigo,
                      lote_codigo: p.lote_codigo, producto_nombre: p.producto_nombre,
                      kg_neto: p.kg_neto, ubicacion_codigo: p.ubicacion_codigo,
                    } })}
                    className="rounded-xl bg-green-700 px-4 py-2 font-semibold text-white hover:bg-green-800"
                  >Ubicar</button>
                )}
              </li>
            ))}
            {resultado.materiales.map((m) => (
              <li key={`m-${m.id}`} className="flex flex-wrap items-center justify-between gap-3 px-5 py-4 text-sm">
                <span>
                  {m.insumo_nombre} · lote <span className="font-mono">{m.lote_codigo}</span>
                  <span className="block text-slate-600">
                    {cantidad(m.cantidad_fisica, m.unidad)} en {m.ubicacion_codigo} ({m.bodega_nombre}) · {cantidad(m.cantidad_disponible, m.unidad)} disponibles · Calidad: {etiquetaDe(catalogos.datos?.estado_calidad, m.estado_calidad)}
                  </span>
                </span>
                <span className="flex flex-wrap gap-2">
                  <button type="button" onClick={() => setAccion({ tipo: "reubicar-material", existencia: m })} className="rounded-xl border border-slate-300 px-4 py-2 font-medium text-slate-800 hover:bg-slate-100">Reubicar</button>
                  {m.ubicacion_tipo === "disponible" && m.lote_utilizable && (
                    <button type="button" onClick={() => setAccion({ tipo: "consumir", existencia: m })} className="rounded-xl border border-slate-300 px-4 py-2 font-medium text-slate-800 hover:bg-slate-100">Consumir</button>
                  )}
                  <button type="button" onClick={() => setAccion({ tipo: "contar", existencia: m })} className="rounded-xl border border-slate-300 px-4 py-2 font-medium text-slate-800 hover:bg-slate-100">Ajustar por conteo</button>
                </span>
              </li>
            ))}
          </ul>
        </Tarjeta>
      )}

      <section aria-labelledby="pendientes-titulo" className="space-y-3">
        <h2 id="pendientes-titulo" className="text-lg font-semibold text-slate-900">
          Pendientes{pendientes.datos ? ` (${pendientes.datos.total})` : ""}
        </h2>
        {pendientes.error && <p role="alert" className="text-sm text-red-800">{pendientes.error}</p>}
        {pendientes.cargando && !pendientes.datos && <p className="text-sm text-slate-600">Cargando pendientes…</p>}
        {pendientes.datos && (
          <PendientesBodega
            datos={pendientes.datos}
            usuarioId={usuarioId}
            onUbicar={(pallet) => { setAccion({ tipo: "ubicar-liberado", pallet }); setHecho(""); }}
            onBuscar={(loteCodigo) => { setAccion(null); void buscar(loteCodigo); }}
            onCambio={terminar}
          />
        )}
      </section>
    </div>
  );
}
