export interface ComponentesBalanceMantequilla {
  mantequilla: string | number;
  suero: string | number;
  merma: string | number;
  reproceso: string | number;
}

function aMilesimas(valor: string | number): number {
  const numero = typeof valor === "number" ? valor : Number(valor || 0);
  return Number.isFinite(numero) ? Math.round(numero * 1_000) : 0;
}

export function calcularBalanceMantequilla(
  kgCrema: string | number,
  componentes: ComponentesBalanceMantequilla,
) {
  const entrada = aMilesimas(kgCrema);
  const clasificado = Object.values(componentes)
    .reduce((total, valor) => total + aMilesimas(valor), 0);
  const diferencia = entrada - clasificado;

  return {
    entrada: entrada / 1_000,
    clasificado: clasificado / 1_000,
    diferencia: diferencia / 1_000,
    cuadrado: diferencia === 0,
    excedido: diferencia < 0,
  };
}
