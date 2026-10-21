/** Una desconexión o un 5xx no prueba que la operación haya sido revertida. */
export function resultadoDeEnvioIncierto(causa: unknown): boolean {
  const estado = (causa as { response?: { status?: unknown } } | null)?.response?.status;
  return typeof estado !== "number" || estado <= 0 || estado >= 500;
}
