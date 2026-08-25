export class LimitadorSolicitudes {
  private activas = 0;
  private readonly cola: Array<() => void> = [];
  private readonly maximas: number;

  constructor(maximas: number) {
    if (maximas < 1) throw new Error("El límite debe ser mayor que cero.");
    this.maximas = maximas;
  }

  adquirir(): Promise<() => void> {
    return new Promise((resolver) => {
      const iniciar = () => {
        this.activas += 1;
        let liberada = false;
        resolver(() => {
          if (liberada) return;
          liberada = true;
          this.activas -= 1;
          this.cola.shift()?.();
        });
      };
      if (this.activas < this.maximas) iniciar();
      else this.cola.push(iniciar);
    });
  }
}


export function claveGet(
  url: string, params: unknown, credencial: string | null,
): string {
  return `${credencial ?? "anon"}|${url}|${JSON.stringify(params ?? {})}`;
}
