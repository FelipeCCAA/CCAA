import type { PlantaAhora } from "./procesos.service";

const RUTAS_ETAPA: Record<string, string> = {
  recepcion: "/leche",
  estandarizacion: "/estandarizacion",
  descremacion: "/procesos?seccion=descremacion",
  evaporacion: "/produccion/evaporacion",
  condensacion: "/produccion/evaporacion",
  secado: "/produccion/secado",
  envasado: "/envasado",
  mantequilla: "/procesos?seccion=mantequilla",
  transferencia: "/produccion",
  otro: "/produccion",
};

export function rutaDeEtapa(tipo: string): string {
  return RUTAS_ETAPA[tipo] ?? "/produccion";
}

/*
  Etapas cuyo inicio es de su puesto: espejo de `MENSAJES_INICIO_EN_PUESTO`
  (`backend/procesos/servicios.py`). La bandeja genérica no ofrece iniciarlas
  (`acciones_permitidas`) y enlaza al puesto con este texto. Reanudar una
  pausada sigue en la bandeja: no es iniciar.
*/
const PUESTOS_QUE_INICIAN: Record<string, string> = {
  secado: "Secado",
  descremacion: "Descremado",
};

export function textoIniciarEnPuesto(etapaTipo: string, estado: string): string | null {
  const puesto = PUESTOS_QUE_INICIAN[etapaTipo];
  return puesto && estado === "preparacion" ? `Iniciar en el puesto de ${puesto}` : null;
}

export function totalEsperandoCalidad(
  indicadores: PlantaAhora["indicadores"] | null | undefined,
): number {
  if (!indicadores) return 0;
  return indicadores.esperando_calidad + indicadores.producto_pendiente_calidad;
}
