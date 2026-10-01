import { fechaLocalISO } from "./fechas.ts";

/*
  Cómo se ordena el puesto de Despacho: por lo que falta hacer con cada hoja.
  «Despachada hoy» usa el día local de Chile, no el UTC: un camión que sale a
  las 22:00 salió hoy.
*/
export function agruparHojas<T extends { estado: string; despachado_en: string | null }>(hojas: T[], hoy: string) {
  return {
    borrador: hojas.filter((h) => h.estado === "borrador"),
    autorizada: hojas.filter((h) => h.estado === "autorizado"),
    despachadaHoy: hojas.filter(
      (h) => h.estado === "despachado" && h.despachado_en !== null && fechaLocalISO(new Date(h.despachado_en)) === hoy,
    ),
  };
}

export function totalesCarga(
  pallets: { kg_neto: string | number }[],
  graneles: { cantidad: string | number; unidad: string }[],
) {
  const suma = (valores: number[]) => Math.round(valores.reduce((a, b) => a + b, 0) * 1000) / 1000;
  // La unidad se compara sin distinguir mayúsculas: el backend manda "L" en
  // `granel-disponible` pero nada obliga a que siga siendo así en todas
  // partes, y un "l" o un "Kg" no tienen por qué perder su kilaje o sus
  // litros de la suma.
  const esKg = (unidad: string) => unidad.toLowerCase() === "kg";
  const esLitros = (unidad: string) => unidad.toLowerCase() === "l";
  return {
    pallets: pallets.length,
    kg: suma([
      ...pallets.map((p) => Number(p.kg_neto)),
      ...graneles.filter((g) => esKg(g.unidad)).map((g) => Number(g.cantidad)),
    ]),
    litros: suma(graneles.filter((g) => esLitros(g.unidad)).map((g) => Number(g.cantidad))),
  };
}

export function buscarPalletPorCodigo<T extends { pallet_codigo: string }>(pallets: T[], codigo: string): T | null {
  const buscado = codigo.trim().toUpperCase();
  return pallets.find((p) => p.pallet_codigo.toUpperCase() === buscado) ?? null;
}

/*
  Por qué un código escaneado no está entre los pallets cargables de la hoja.

  «No existe, no está liberado o ya está en otra hoja» no le dice al operador
  qué hacer distinto. `encontrado` es lo que devolvió una búsqueda aparte en
  bodega (`buscarProductoTerminado`, que no exige estar entre los cargables);
  `null` significa que ni siquiera eso lo encontró. El estado y la ubicación
  alcanzan para nombrar la causa; «ya está en otra hoja» no se puede nombrar
  sin un dato que el frontend no tiene, así que queda como aviso genérico.
*/
export function mensajePalletNoCargable(
  codigo: string,
  encontrado: { estado_inventario: string; ubicacion_tipo: string } | null,
): string {
  if (!encontrado) {
    return `El pallet ${codigo} no existe en bodega.`;
  }
  const porEstado: Record<string, string> = {
    cuarentena: `El pallet ${codigo} está en cuarentena y no se puede cargar.`,
    bloqueado: `El pallet ${codigo} está bloqueado y no se puede cargar.`,
    despachado: `El pallet ${codigo} ya fue despachado.`,
    anulado: `El pallet ${codigo} fue anulado.`,
  };
  if (encontrado.estado_inventario !== "disponible") {
    return porEstado[encontrado.estado_inventario] ?? `El pallet ${codigo} no se puede cargar.`;
  }
  if (encontrado.ubicacion_tipo !== "disponible") {
    return `El pallet ${codigo} está en una ubicación no disponible y no se puede cargar.`;
  }
  return `El pallet ${codigo} no está disponible para cargar (puede estar en otra hoja activa).`;
}

/*
  Cómo se identifica un granel en la hoja de carga.

  El lote es lo trazable — es lo que Calidad liberó y lo que se audita después
  del despacho—, así que manda cuando existe; la corrida queda como referencia
  secundaria porque sigue identificando la corrida de origen aunque el granel
  ya tenga lote. Un granel de despacho directo (sin lote) se identifica por su
  corrida sola. El silo, cuando se conoce, ubica físicamente el origen y solo
  se agrega si se pide: la lista de graneles por elegir no lo necesita, el
  resumen de ejecución sí.
*/
export function identificarGranel(
  granel: { lote_codigo: string | null; corrida_codigo: string },
  opciones: { silo?: string | null } = {},
): string {
  const base = granel.lote_codigo
    ? `lote ${granel.lote_codigo} · corrida ${granel.corrida_codigo}`
    : `corrida ${granel.corrida_codigo}`;
  return opciones.silo ? `${base} · ${opciones.silo}` : base;
}

/*
  Cantidad de granel tecleada a mano, en formato chileno: "8.000" es ocho mil,
  no ocho con tres decimales. Solo se quitan los puntos como separador de
  miles cuando el texto también trae una coma decimal, o cuando el texto
  entero no es otra cosa que grupos de tres dígitos separados por puntos
  ("8.000", "1.234.000") — un "1.234" sin coma es ambiguo en cualquier otro
  caso y se deja tal cual. Redondea a tres decimales, como el resto de las
  cantidades del módulo, y descarta lo que no sea un número positivo: una
  cantidad en cero o negativa no es un despacho.
*/
export function leerCantidadChilena(texto: string): number | null {
  const limpio = texto.trim();
  if (!limpio) return null;
  const soloMilesDePuntos = /^\d{1,3}(\.\d{3})+$/.test(limpio);
  const tieneComaDecimal = limpio.includes(",");
  const sinMiles = tieneComaDecimal || soloMilesDePuntos ? limpio.replace(/\./g, "") : limpio;
  const numero = Number(sinMiles.replace(",", "."));
  if (!Number.isFinite(numero) || numero <= 0) return null;
  return Math.round(numero * 1000) / 1000;
}
