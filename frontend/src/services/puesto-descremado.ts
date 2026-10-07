import type { DescremadoraPuesto } from "./descremado.service.ts";

/* Un solo mapa de «dónde se resuelve» para los puestos (Desviación 17). */
export { moduloDeResolver } from "./puesto-secado.ts";

export interface AccionDescremadora {
  tipo: "preparar" | "iniciar" | "cerrar" | "ninguna";
  habilitada: boolean;
  motivo: string | null;
}

/*
  Qué botón lleva la tarjeta de una descremadora. Solo traduce lo que mandó
  el servidor: estado y motivos los calcula `estado_puesto_descremado` con
  las mismas reglas que deciden al preparar (`motivo_equipo_no_habilitado`) y
  al iniciar (`motivos_tipados_para_iniciar_descremacion`). Los avisos no
  entran aquí a propósito: avisan, no deshabilitan.

  La única regla propia es espejo de `cerrar_descremacion`: la ejecución
  pasa a `pendiente_control`, y eso solo se permite desde `ejecucion`.
  Ofrecer las salidas sobre una pausada o bloqueada es ofrecer algo que el
  servidor rechaza.
*/
export function accionDeDescremadora(fila: DescremadoraPuesto): AccionDescremadora {
  switch (fila.estado) {
    case "disponible": {
      const motivo = fila.motivos_para_tomar[0] ?? null;
      return { tipo: "preparar", habilitada: motivo === null, motivo };
    }
    case "preparada": {
      const motivo = fila.motivos_para_iniciar[0] ?? null;
      return { tipo: "iniciar", habilitada: motivo === null && fila.corrida?.id != null, motivo };
    }
    case "en_curso": {
      const estado = fila.corrida?.ejecucion_estado;
      if (estado === "pausada") {
        return { tipo: "cerrar", habilitada: false, motivo: "La corrida está pausada: reanúdala antes de registrar las salidas." };
      }
      if (estado === "bloqueada") {
        return { tipo: "cerrar", habilitada: false, motivo: "La corrida está bloqueada: resuelve el bloqueo antes de registrar las salidas." };
      }
      return { tipo: "cerrar", habilitada: fila.corrida?.id != null, motivo: null };
    }
    default:
      return { tipo: "ninguna", habilitada: false, motivo: null };
  }
}

/*
  La corrida que «Cancelar preparación» soltaría, o `null`. Espejo de
  `cancelar_preparacion_descremacion`: corrida en `borrador` con la ejecución
  en `preparacion` —o en `borrador`, las heredadas del modal anterior, que
  solo aparecen en el historial—. Los motivos que impiden iniciar no impiden
  cancelar: suelen ser justo la razón.
*/
export function corridaCancelable(
  corrida: { id: number | null; estado: string | null; ejecucion_estado: string } | null | undefined,
): number | null {
  if (!corrida || corrida.id === null || corrida.estado !== "borrador") return null;
  return ["borrador", "preparacion"].includes(corrida.ejecucion_estado) ? corrida.id : null;
}

/* Cómo se nombra una corrida en «Corridas de hoy» y en el historial. Un
   estado que no se distingue lleva la etiqueta del servidor. */
export function situacionDeCorrida(estado: string, estadoEjecucion: string, etiqueta?: string): string {
  switch (estado) {
    case "borrador":
      return ["borrador", "preparacion"].includes(estadoEjecucion) ? "Preparada" : etiqueta ?? estado;
    case "en_curso":
      return "En la descremadora";
    case "cerrada":
      return estadoEjecucion === "pendiente_control" ? "Esperando Calidad" : "Terminada";
    case "anulada":
      return "Anulada";
    default:
      return etiqueta ?? estado;
  }
}
