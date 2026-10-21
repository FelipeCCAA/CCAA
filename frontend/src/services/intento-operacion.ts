export interface IntentoOperacion<T extends object> {
  firma: string;
  carga: T & { operacion_id: string };
}

/** Reusa la misma clave para la misma carga; una carga corregida abre otra operación. */
export function prepararIntentoOperacion<T extends object>(
  anterior: IntentoOperacion<T> | null,
  datos: T,
  generarUuid: () => string = () => crypto.randomUUID(),
): IntentoOperacion<T> {
  const firma = JSON.stringify(datos);
  if (anterior?.firma === firma) return anterior;
  return {
    firma,
    carga: { ...datos, operacion_id: generarUuid() } as T & { operacion_id: string },
  };
}
