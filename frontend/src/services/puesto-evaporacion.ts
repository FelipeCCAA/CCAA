import type { EvaporadorPuesto } from "./procesos.service.ts";

/*
  Qué botón lleva la tarjeta de un evaporador. Solo traduce lo que mandó el
  servidor: el estado y los motivos los calcula `estado_puesto_evaporacion`
  con la misma función que decide al iniciar. Recalcularlos aquí sería una
  segunda implementación, y la que se equivoca primero es la de la pantalla.
*/
export function accionDeEvaporador(fila: EvaporadorPuesto): {
  tipo: "abrir" | "iniciar" | "cerrar" | "ninguna";
  habilitada: boolean;
  motivo: string | null;
} {
  switch (fila.estado) {
    case "disponible":
      return { tipo: "abrir", habilitada: true, motivo: null };
    case "preparada": {
      const motivo = fila.motivos_para_iniciar[0] ?? null;
      return { tipo: "iniciar", habilitada: motivo === null, motivo };
    }
    case "en_curso":
      return { tipo: "cerrar", habilitada: true, motivo: null };
    default:
      return { tipo: "ninguna", habilitada: false, motivo: null };
  }
}
