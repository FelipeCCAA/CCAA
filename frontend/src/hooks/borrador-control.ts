export function huellaBorrador(datos: unknown): string {
  return JSON.stringify(datos) ?? "undefined";
}

export function borradorCambio(ultimaGuardada: string | null, actual: string): boolean {
  return ultimaGuardada !== actual;
}
