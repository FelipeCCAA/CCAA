/*
  Qué máquinas ofrece el formulario de lote. Una sola función para el
  desplegable y para validar, al reanudar un borrador, si la máquina guardada
  sigue valiendo (antes vivía dentro de `FormularioLote`).

  En Producción (`resto`) no se ofrecen evaporadores —se abren en el puesto de
  Evaporación— ni torres —un lote en torre nace solo desde el puesto de
  Secado—, aunque la familia no tenga ruta o la ruta las nombre: el servidor
  rechaza las dos (`exigir_apertura_fuera_de_secado`).
*/
export function equiposCompatiblesDe<T extends { activo: boolean; tipo: string }>(
  equipos: T[],
  modo: "evaporacion" | "resto",
  tiposRuta: readonly string[] | null,
): T[] {
  return equipos.filter((item) => {
    if (!item.activo) return false;
    if (modo === "evaporacion") return item.tipo === "evaporador";
    if (item.tipo === "evaporador" || item.tipo === "torre") return false;
    return !tiposRuta || tiposRuta.includes(item.tipo);
  });
}
