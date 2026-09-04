const ETIQUETAS: Record<string, string> = {
  ruta_producto: "Ruta del producto",
  equipo: "Equipo",
  etapa: "Etapa",
};

function textos(valor: unknown): string[] {
  if (Array.isArray(valor)) return valor.flatMap(textos);
  if (valor && typeof valor === "object") {
    return Object.entries(valor as Record<string, unknown>).flatMap(([campo, detalle]) => {
      const mensajes = textos(detalle);
      if (["detail", "error", "non_field_errors"].includes(campo)) return mensajes;
      const etiqueta = ETIQUETAS[campo] ?? campo.replaceAll("_", " ");
      return mensajes.map((mensaje) => `${etiqueta}: ${mensaje}`);
    });
  }
  if (valor === null || valor === undefined || valor === "") return [];
  return [String(valor)];
}

/** Traduce respuestas DRF sin ocultar la causa operacional entregada por Django. */
export function mensajeErrorProceso(error: unknown, respaldo: string): string {
  const datos = (error as { response?: { data?: unknown } })?.response?.data;
  const mensajes = textos(datos);
  return mensajes.length ? mensajes.join(" · ") : respaldo;
}

export function esErrorDeEquipo(error: unknown): boolean {
  const datos = (error as { response?: { data?: unknown } })?.response?.data;
  if (datos && typeof datos === "object" && "equipo" in datos) return true;
  const mensaje = textos(datos).join(" ").toLocaleLowerCase("es-CL");
  return /(equipo|máquina|linea|línea|torre|evaporador).*(ocupad|reservad)/.test(mensaje);
}

export function esConflictoVersion(error: unknown): boolean {
  const respuesta = (error as { response?: { status?: number; data?: unknown } })?.response;
  return Boolean(
    respuesta?.status === 409
    && respuesta.data
    && typeof respuesta.data === "object"
    && (respuesta.data as { code?: string }).code === "version_conflict"
  );
}
