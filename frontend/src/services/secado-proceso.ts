export type EstadoEjecucionSecado =
  | "preparacion"
  | "ejecucion"
  | "pausada"
  | "bloqueada"
  | "pendiente_control"
  | "cerrada"
  | "cancelada"
  | string;

export type BandejaSecado = "activas" | "calidad" | "terminadas" | "historial";

export interface ValoresBalanceSecado {
  kgAlimentacion: number;
  solidosEntradaPct: number;
  kgPolvo: number;
  kgFinos: number;
  kgMerma: number;
}

export interface BalanceSecado {
  kgRecuperados: number;
  kgSalidas: number;
  kgNoContabilizados: number;
  kgSolidosEntrada: number;
  rendimientoRecuperacionPct: number;
  esPosible: boolean;
}

const ESTADOS_ACTIVOS = new Set(["preparacion", "ejecucion", "pausada", "bloqueada"]);

export function bandejaDeSecado(
  estado: EstadoEjecucionSecado,
  estadoCalidad: string = "no_requerida",
): BandejaSecado {
  if (ESTADOS_ACTIVOS.has(estado)) return "activas";
  if (estadoCalidad === "pendiente" || estado === "pendiente_control") return "calidad";
  if (estado === "cerrada") return "terminadas";
  return "historial";
}

export function estadoFisicoSecado(estado: EstadoEjecucionSecado): string {
  if (estado === "preparacion") return "Equipo reservado";
  if (["ejecucion", "pausada", "bloqueada"].includes(estado)) return "Equipo ocupado";
  return "Equipo disponible";
}

export function siguienteAccionSecado(
  estado: EstadoEjecucionSecado,
  estadoCalidad: string = "no_requerida",
): string {
  if (estado === "preparacion") return "Iniciar la ejecución desde el flujo productivo";
  if (estado === "ejecucion" || estado === "pausada") return "Registrar balance y cerrar corrida";
  if (estado === "bloqueada") return "Resolver el bloqueo antes de continuar";
  if (estadoCalidad === "pendiente" || estado === "pendiente_control") return "Esperar decisión de Calidad";
  if (estadoCalidad === "rechazado") return "Resolver el rechazo informado por Calidad";
  if (estado === "cerrada") return "Revisar continuidad del lote en Calidad";
  return "Consultar el historial de la corrida";
}

export function calcularBalanceSecado(valores: ValoresBalanceSecado): BalanceSecado {
  const kgRecuperados = valores.kgPolvo + valores.kgFinos;
  const kgSalidas = kgRecuperados + valores.kgMerma;
  const kgNoContabilizados = valores.kgAlimentacion - kgSalidas;
  const kgSolidosEntrada = valores.kgAlimentacion * valores.solidosEntradaPct / 100;
  const rendimientoRecuperacionPct = valores.kgAlimentacion > 0
    ? kgRecuperados * 100 / valores.kgAlimentacion
    : 0;

  return {
    kgRecuperados,
    kgSalidas,
    kgNoContabilizados,
    kgSolidosEntrada,
    rendimientoRecuperacionPct,
    esPosible: valores.kgAlimentacion > 0 && kgSalidas <= valores.kgAlimentacion,
  };
}
