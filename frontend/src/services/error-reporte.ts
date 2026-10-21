/** Las descargas Axios reciben incluso los errores JSON como Blob. */
export async function mensajeErrorReporte(error: unknown, respaldo: string): Promise<string> {
  const respuesta = (error as { response?: { status?: number; data?: unknown } } | null)?.response;
  if (respuesta?.status !== 400) return respaldo;
  let datos = respuesta.data;
  if (datos instanceof Blob) {
    try { datos = JSON.parse(await datos.text()); } catch { return respaldo; }
  }
  if (datos && typeof datos === "object" && "code" in datos && "detail" in datos
    && datos.code === "REPORTE_DEMASIADO_GRANDE" && typeof datos.detail === "string") {
    return datos.detail;
  }
  return respaldo;
}
