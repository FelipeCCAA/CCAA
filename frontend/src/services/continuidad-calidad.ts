export interface PoliticaContinuidad {
  avisos_intermedios: boolean;
  mensaje: string;
}

export const MENSAJE_CONTINUIDAD = "Producción con Calidad pendiente: se puede continuar; la liberación final sigue siendo obligatoria.";

export function mensajePoliticaContinuidad(politica?: PoliticaContinuidad | null): string | null {
  return politica?.avisos_intermedios === true ? MENSAJE_CONTINUIDAD : null;
}

export function puedeContinuarPendiente(editable: boolean, vale: { continuidad_pendiente_disponible?: boolean }): boolean {
  return editable && vale.continuidad_pendiente_disponible === true;
}

export function payloadContinuidadPendiente() {
  return { motivo: "Continuidad operacional con Calidad pendiente" };
}

export function sufijoAvisosCalidad(avisos?: string[]): string {
  return avisos?.length ? ` · ${avisos.join(" · ")}` : "";
}
