import { bandejaDeSecado } from "./secado-proceso.ts";
import type { TorrePuesto } from "./secado.service.ts";

export interface AccionTorre {
  tipo: "tomar" | "iniciar" | "cerrar" | "ninguna";
  habilitada: boolean;
  motivo: string | null;
}

/*
  Qué botón lleva la tarjeta de una torre. Solo traduce lo que mandó el
  servidor: estado y motivos los calcula `estado_puesto_secado` con las mismas
  reglas que deciden al preparar (`motivo_equipo_no_habilitado`) y al iniciar
  (`motivos_para_iniciar_secado`). Los avisos no entran aquí a propósito:
  avisan, no deshabilitan.

  La única regla propia es la de una corrida bloqueada, que es espejo de
  `cerrar_secado` (solo cierra `ejecucion` o `pausada`): ofrecer el balance
  sobre una bloqueada es ofrecer algo que el servidor rechaza.
*/
export function accionDeTorre(fila: TorrePuesto): AccionTorre {
  switch (fila.estado) {
    case "disponible": {
      const motivo = fila.motivos_para_tomar[0] ?? null;
      return { tipo: "tomar", habilitada: motivo === null, motivo };
    }
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

/*
  La corrida que «Cancelar preparación» soltaría, o `null` si la tarjeta no
  ofrece cancelar. Espejo de `cancelar_preparacion_secado`: solo una torre
  preparada, y por su corrida (`secados/{id}/cancelar-preparacion/`). Los
  motivos que impiden iniciar no impiden cancelar: suelen ser justo la razón.
*/
export function corridaCancelable(fila: TorrePuesto): number | null {
  return fila.estado === "preparada" ? fila.corrida?.id ?? null : null;
}

/* Cómo se nombra una corrida en «Corridas de hoy» y en el historial. La
   clasificación es `bandejaDeSecado` y nada más: una sola regla. Dentro de
   «activas», una preparada todavía no está en la torre. Un estado que el
   historial no distingue lleva la etiqueta que manda el servidor: llamarlo
   «Cancelada» sería afirmar algo que no se sabe. */
export function situacionDeCorrida(estado: string, estadoCalidad?: string, etiqueta?: string): string {
  switch (bandejaDeSecado(estado, estadoCalidad)) {
    case "activas":
      return estado === "preparacion" ? "Preparada" : "En la torre";
    case "calidad":
      return "Esperando Calidad";
    case "terminadas":
      return "Terminada";
    default:
      return estado === "cancelada" ? "Cancelada" : etiqueta ?? estado;
  }
}
