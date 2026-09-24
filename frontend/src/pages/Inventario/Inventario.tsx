import { useState } from "react";

import { useCarga } from "../../components/seccion/utilidades";
import { cantidad } from "../../services/formato";
import {
  buscarExistencias, buscarMovimientos, buscarMovimientosProductoTerminado, buscarProductoTerminado,
  obtenerCatalogosInventario, obtenerUbicaciones,
  type Existencia, type ExistenciaProductoTerminado, type FiltrosInventario, type MovimientoInventario, type MovimientoProductoTerminado,
} from "../../services/inventario.service";
import ReworkInventario from "./ReworkInventario";
import TablaConsulta from "./TablaConsulta";

type Pestana = "materiales" | "producto" | "movimientos" | "movimientos-pallets" | "rework";

const PESTANAS: { id: Pestana; texto: string }[] = [
  { id: "materiales", texto: "Materiales" },
  { id: "producto", texto: "Producto terminado" },
  { id: "movimientos", texto: "Movimientos de materiales" },
  { id: "movimientos-pallets", texto: "Movimientos de pallets" },
  { id: "rework", texto: "Rework" },
];

const fechaHora = (iso: string) =>
  new Date(iso).toLocaleString("es-CL", { dateStyle: "short", timeStyle: "short" });

const SOLO_CON_SALDO: FiltrosInventario = { con_saldo: true };

type Opcion = { valor: string; etiqueta: string };
const aEstados = (opciones: Opcion[] | undefined) =>
  (opciones ?? []).map((o) => ({ valor: o.valor, texto: o.etiqueta }));

/* La etiqueta que sirve el catálogo, o el código crudo si el catálogo no
   cargó o no trae ese valor: mejor mostrar el código que una celda vacía. */
const etiquetaDe = (opciones: Opcion[] | undefined, valor: string) =>
  opciones?.find((o) => o.valor === valor)?.etiqueta ?? valor;

/*
  Consulta de solo lectura. Los movimientos se registran en los puestos de
  Bodega y Despacho; aquí se mira qué hay, dónde y qué pasó.
*/
export default function Inventario() {
  const [pestana, setPestana] = useState<Pestana>("producto");
  const ubicaciones = useCarga(obtenerUbicaciones);
  // Auxiliares: si fallan, la consulta igual carga, sin esos desplegables.
  const catalogos = useCarga(obtenerCatalogosInventario);
  const lista = ubicaciones.datos ?? [];
  const opciones = catalogos.datos;

  return (
    <div className="px-4 py-8 sm:px-8">
      <div className="mx-auto max-w-7xl space-y-6">
        <header>
          <p className="text-sm font-semibold uppercase tracking-wider text-green-700">Consulta</p>
          <h1 className="mt-1 text-3xl font-bold text-slate-900">Existencias</h1>
          <p className="mt-2 max-w-2xl text-slate-600">Qué hay, dónde está y qué se movió. Para registrar un movimiento, usa los puestos de Bodega o Despacho.</p>
        </header>

        <div role="tablist" aria-label="Consultas de inventario" className="flex gap-1 overflow-x-auto border-b border-slate-200">
          {PESTANAS.map((p) => (
            <button key={p.id} type="button" role="tab" aria-selected={pestana === p.id} onClick={() => setPestana(p.id)}
              className={`whitespace-nowrap border-b-2 px-4 py-3 text-sm font-medium ${pestana === p.id ? "border-green-700 text-green-800" : "border-transparent text-slate-600 hover:text-slate-800"}`}>
              {p.texto}
            </button>
          ))}
        </div>

        <div role="tabpanel">
          {pestana === "materiales" && (
            <TablaConsulta<Existencia>
              titulo="Materiales"
              cargar={buscarExistencias}
              filtrosFijos={SOLO_CON_SALDO}
              clave={(f) => f.id}
              ubicaciones={lista}
              etiquetaBusqueda="Material o lote"
              vacio="No hay material con saldo que coincida."
              estados={aEstados(opciones?.estado_calidad)}
              columnas={[
                { titulo: "Material", celda: (f) => <>{f.insumo_nombre}<span className="block text-xs text-slate-600">{f.insumo_codigo}</span></> },
                { titulo: "Lote", celda: (f) => <span className="font-mono">{f.lote_codigo}</span> },
                { titulo: "Ubicación", celda: (f) => `${f.ubicacion_codigo} · ${f.bodega_nombre}` },
                { titulo: "Calidad", celda: (f) => etiquetaDe(opciones?.estado_calidad, f.estado_calidad) },
                { titulo: "Físico", numerica: true, celda: (f) => cantidad(f.cantidad_fisica, f.unidad) },
                { titulo: "Disponible", numerica: true, celda: (f) => cantidad(f.cantidad_disponible, f.unidad) },
              ]}
            />
          )}
          {pestana === "producto" && (
            <TablaConsulta<ExistenciaProductoTerminado>
              titulo="Producto terminado"
              cargar={buscarProductoTerminado}
              clave={(f) => f.id}
              ubicaciones={lista}
              etiquetaBusqueda="Pallet, lote o producto"
              vacio="No hay pallets que coincidan."
              estados={aEstados(opciones?.estado_pallet)}
              columnas={[
                { titulo: "Pallet", celda: (f) => <span className="font-mono">{f.pallet_codigo}</span> },
                { titulo: "Producto", celda: (f) => f.producto_nombre },
                { titulo: "Unidad", celda: (f) => f.tipo_unidad_logistica_etiqueta },
                { titulo: "Lote", celda: (f) => <span className="font-mono">{f.lote_codigo}</span> },
                { titulo: "Ubicación", celda: (f) => f.ubicacion_codigo },
                { titulo: "Estado", celda: (f) => etiquetaDe(opciones?.estado_pallet, f.estado_inventario) },
                { titulo: "Peso", numerica: true, celda: (f) => cantidad(f.kg_neto, "kg") },
              ]}
            />
          )}
          {pestana === "movimientos" && (
            <TablaConsulta<MovimientoInventario>
              titulo="Movimientos de materiales"
              cargar={buscarMovimientos}
              clave={(f) => f.id}
              ubicaciones={lista}
              conFechas
              etiquetaBusqueda="Material o lote"
              vacio="No hay movimientos que coincidan."
              estados={aEstados(opciones?.tipo_movimiento)}
              etiquetaEstado="Tipo"
              columnas={[
                { titulo: "Fecha", celda: (f) => fechaHora(f.fecha) },
                { titulo: "Tipo", celda: (f) => f.tipo_etiqueta },
                { titulo: "Material", celda: (f) => <>{f.insumo_nombre}<span className="block font-mono text-xs text-slate-600">{f.lote_codigo}</span></> },
                { titulo: "Origen → destino", celda: (f) => `${f.origen_codigo ?? "—"} → ${f.destino_codigo ?? "—"}` },
                { titulo: "Cantidad", numerica: true, celda: (f) => cantidad(f.cantidad, f.unidad) },
                { titulo: "Usuario", celda: (f) => f.usuario_nombre },
              ]}
            />
          )}
          {pestana === "movimientos-pallets" && (
            <TablaConsulta<MovimientoProductoTerminado>
              titulo="Movimientos de pallets"
              cargar={buscarMovimientosProductoTerminado}
              clave={(f) => f.id}
              ubicaciones={lista}
              conFechas
              etiquetaBusqueda="Pallet o lote"
              vacio="No hay movimientos de pallets que coincidan."
              estados={aEstados(opciones?.tipo_movimiento_pallet)}
              etiquetaEstado="Tipo"
              columnas={[
                { titulo: "Fecha", celda: (f) => fechaHora(f.registrado_en) },
                { titulo: "Tipo", celda: (f) => f.tipo_etiqueta },
                { titulo: "Pallet", celda: (f) => <>{f.pallet_codigo}<span className="block font-mono text-xs text-slate-600">{f.lote_codigo}</span></> },
                { titulo: "Origen → destino", celda: (f) => `${f.origen_codigo ?? "—"} → ${f.destino_codigo ?? "—"}` },
                { titulo: "Peso", numerica: true, celda: (f) => cantidad(f.kg_neto, "kg") },
                { titulo: "Usuario", celda: (f) => f.registrado_por_nombre },
              ]}
            />
          )}
          {pestana === "rework" && <ReworkInventario />}
        </div>
      </div>
    </div>
  );
}
