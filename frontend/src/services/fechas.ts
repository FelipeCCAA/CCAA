/**
 * La fecha local de `momento` como AAAA-MM-DD.
 *
 * `toISOString()` da la fecha UTC: en Chile (UTC-3) desde las 21:00 ya es
 * mañana. Se arma con los componentes locales para que un documento del
 * turno de noche lleve el día en que ocurrió.
 */
export function fechaLocalISO(momento: Date = new Date()): string {
  const anio = momento.getFullYear();
  const mes = String(momento.getMonth() + 1).padStart(2, "0");
  const dia = String(momento.getDate()).padStart(2, "0");
  return `${anio}-${mes}-${dia}`;
}
