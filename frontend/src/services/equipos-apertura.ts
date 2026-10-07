/*
  Ruta de producto → tipo de máquina. Vive aquí, y no en `FormularioLote`,
  porque `reanudarBorrador` la evalúa contra el vale que guardó el borrador
  y porque así se puede probar contra los tipos que sirve el servidor.
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
  Evaporación— ni nada que el servidor no abra desde un vale: ni torres —un
  lote en torre nace solo desde el puesto de Secado— ni puntos de carga,
  descremadoras u «otro», aunque la familia no tenga ruta o la ruta los nombre.

  `tiposQueAbren` es `tipos_que_abren_desde_vale` de `opciones-inicio`: la
  regla de `produccion.servicios.abre_desde_vale`, servida. Antes había una
  copia aquí, y una copia ofrece tarde o temprano lo que el servidor rechaza.
*/
export function equiposCompatiblesDe<T extends { activo: boolean; tipo: string }>(
  equipos: T[],
  modo: "evaporacion" | "resto",
  tiposRuta: readonly string[] | null,
  tiposQueAbren: readonly string[],
): T[] {
  return equipos.filter((item) => {
    if (!item.activo) return false;
    if (modo === "evaporacion") return item.tipo === "evaporador";
    if (item.tipo === "evaporador" || !tiposQueAbren.includes(item.tipo)) return false;
    return !tiposRuta || tiposRuta.includes(item.tipo);
  });
}
