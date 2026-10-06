/*
  Tipos de máquina sobre los que el servidor abre un lote desde un vale:
  espejo de `produccion.servicios.abre_desde_vale` (la regla de
  `exigir_apertura_fuera_de_secado`). Cualquier otro —torre, punto de carga,
  descremadora, otro— cae en Secado y se rechaza al confirmar. El servidor ya
  filtra `opciones-inicio` con esa regla; esta lista solo evita que una
  familia pida, ni por error, algo que el servidor no va a aceptar.
  `produccion.tests_lote_en_torre.test_abre_desde_vale_es_la_regla_de_la_guarda`
  fija el conjunto del lado del servidor.
*/
export const TIPOS_QUE_ABREN_DESDE_VALE: readonly string[] = ["evaporador", "envasadora", "linea"];

/*
  Ruta de producto → tipo de máquina. Vive aquí, y no en `FormularioLote`,
  porque `reanudarBorrador` la evalúa contra el vale que guardó el borrador
  y porque así se puede probar contra `TIPOS_QUE_ABREN_DESDE_VALE`.
*/
export const RUTA_POR_FAMILIA: Record<string, { ruta: string; tipos: string[]; ayuda: string }> = {
  polvo: {
    ruta: "Leche estandarizada → Evaporación → Torre Egron → Envasado 25 kg",
    tipos: ["evaporador"],
    ayuda: "Esta apertura inicia la evaporación. La torre Egron aparecerá después, únicamente cuando Calidad libere el concentrado.",
  },
  liquido: {
    ruta: "Leche estandarizada → Evaporación / concentración → Producto a granel",
    tipos: ["evaporador"],
    ayuda: "Selecciona el evaporador que ejecuta esta corrida.",
  },
  crema: {
    ruta: "Leche estandarizada → Separación / proceso → Envasado o granel",
    tipos: ["linea", "envasadora"],
    ayuda: "Selecciona solo la línea o envasadora de crema correspondiente.",
  },
  otro: {
    ruta: "Proceso definido para el producto → Envasado",
    tipos: ["linea", "envasadora"],
    ayuda: "Selecciona la máquina final definida para este producto.",
  },
};

export const tiposDeFamilia = (familia: string | undefined): string[] | null =>
  (familia ? RUTA_POR_FAMILIA[familia]?.tipos ?? null : null);

/*
  Qué máquinas ofrece el formulario de lote. Una sola función para el
  desplegable y para validar, al reanudar un borrador, si la máquina guardada
  sigue valiendo (antes vivía dentro de `FormularioLote`).

  En Producción (`resto`) no se ofrecen evaporadores —se abren en el puesto de
  Evaporación— ni nada que el servidor no abra desde un vale
  (`TIPOS_QUE_ABREN_DESDE_VALE`): ni torres —un lote en torre nace solo desde
  el puesto de Secado— ni puntos de carga, aunque la familia no tenga ruta o
  la ruta los nombre.
*/
export function equiposCompatiblesDe<T extends { activo: boolean; tipo: string }>(
  equipos: T[],
  modo: "evaporacion" | "resto",
  tiposRuta: readonly string[] | null,
): T[] {
  return equipos.filter((item) => {
    if (!item.activo) return false;
    if (modo === "evaporacion") return item.tipo === "evaporador";
    if (item.tipo === "evaporador" || !TIPOS_QUE_ABREN_DESDE_VALE.includes(item.tipo)) return false;
    return !tiposRuta || tiposRuta.includes(item.tipo);
  });
}
