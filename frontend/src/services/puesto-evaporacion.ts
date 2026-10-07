import type { DestinoConcentrado, EvaporadorPuesto } from "./procesos.service.ts";

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
    /* Esperando Calidad la máquina está libre: `pendiente_control` no ocupa
       el equipo, lo que espera es el concentrado. La tarjeta sigue diciendo
       «Esperando Calidad», pero se puede abrir el lote siguiente. */
    case "disponible":
    case "esperando_calidad":
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

/*
  Destinos que se ofrecen para el concentrado de un vale: todos menos el silo
  del que el lote saca la leche (`silo_destino_codigo` del vale).
  `CorridaCondensacion.clean` rechaza origen == destino, así que ofrecerlo
  —aunque fuese deshabilitado— es ofrecer lo que el servidor rechaza.
*/
export function destinosDelConcentrado(
  destinos: DestinoConcentrado[],
  siloOrigenCodigo: string | undefined,
): DestinoConcentrado[] {
  if (!siloOrigenCodigo) return destinos;
  return destinos.filter((destino) => destino.codigo !== siloOrigenCodigo);
}
