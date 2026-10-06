import { bandejaDeSecado } from "./secado-proceso.ts";
import type { TorrePuesto } from "./secado.service.ts";

export interface AccionTorre {
  tipo: "tomar" | "iniciar" | "cerrar" | "ninguna";
  habilitada: boolean;
  motivo: string | null;
}

/*
  Qué botón lleva la tarjeta de una torre. Solo traduce lo que mandó el
  servidor: estado y motivos los calcula `estado_puesto_secado` con la misma
  función que decide al iniciar (`motivos_para_iniciar_secado`). Los avisos
  no entran aquí a propósito: avisan, no deshabilitan.

  La única regla propia es la de una corrida bloqueada, que es espejo de
  `cerrar_secado` (solo cierra `ejecucion` o `pausada`): ofrecer el balance
  sobre una bloqueada es ofrecer algo que el servidor rechaza.
*/
export function accionDeTorre(fila: TorrePuesto): AccionTorre {
  switch (fila.estado) {
    case "disponible":
      return { tipo: "tomar", habilitada: true, motivo: null };
    case "preparada": {
      const motivo = fila.motivos_para_iniciar[0] ?? null;
      return { tipo: "iniciar", habilitada: motivo === null && fila.corrida?.id != null, motivo };
    }
    case "en_curso":
      if (fila.corrida?.ejecucion_estado === "bloqueada") {
        return {
          tipo: "cerrar",
          habilitada: false,
          motivo: "La corrida está bloqueada: resuelve el bloqueo antes de cerrar.",
        };
      }
      return { tipo: "cerrar", habilitada: fila.corrida?.id != null, motivo: null };
    default:
      return { tipo: "ninguna", habilitada: false, motivo: null };
  }
}

const SITUACION = {
  activas: "En la torre",
  calidad: "Esperando Calidad",
  terminadas: "Terminada",
  historial: "Cancelada",
} as const;

/* Cómo se nombra una corrida en «Corridas de hoy» y en el historial. La
   clasificación es `bandejaDeSecado` y nada más: una sola regla. */
export function situacionDeCorrida(estado: string, estadoCalidad?: string): string {
  return SITUACION[bandejaDeSecado(estado, estadoCalidad)];
}
