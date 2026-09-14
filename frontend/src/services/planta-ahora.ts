import type { PlantaAhora } from "./procesos.service";

const RUTAS_ETAPA: Record<string, string> = {
  recepcion: "/leche",
  estandarizacion: "/estandarizacion",
  descremacion: "/procesos?seccion=descremacion",
  evaporacion: "/produccion#evaporacion",
  condensacion: "/produccion#evaporacion",
  secado: "/secado",
  envasado: "/envasado",
  mantequilla: "/procesos?seccion=mantequilla",
  transferencia: "/produccion",
  otro: "/produccion",
};

export function rutaDeEtapa(tipo: string): string {
  return RUTAS_ETAPA[tipo] ?? "/produccion";
}

export function totalEsperandoCalidad(
  indicadores: PlantaAhora["indicadores"] | null | undefined,
): number {
  if (!indicadores) return 0;
  return indicadores.esperando_calidad + indicadores.producto_pendiente_calidad;
}
