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


const ACCIONES_SOLO_BORRADOR = new Set([
  "crear-borrador",
  "guardar-borrador",
  "descartar-borrador",
]);


function segmentosRuta(url: string): string[] {
  const ruta = url
    .replace(/^[a-z][a-z\d+.-]*:\/\/[^/]+/i, "")
    .split(/[?#]/, 1)[0]
    .replace(/^\/+|\/+$/g, "");
  const segmentos = ruta.split("/").filter(Boolean);
  return segmentos[0] === "api" ? segmentos.slice(1) : segmentos;
}


/*
  Crear, guardar o descartar un borrador no altera saldos ni listados
  operativos. Se invalida solamente su lectura `mi-borrador`; confirmar queda
  fuera porque sí mueve el documento al flujo real.
*/
export function recursoDeEscrituraSoloBorrador(url?: string): string | null {
  if (!url) return null;
  const segmentos = segmentosRuta(url);
  const accion = segmentos.at(-1);
  if (!accion || !ACCIONES_SOLO_BORRADOR.has(accion)) return null;

  const tieneId = accion !== "crear-borrador";
  const fin = segmentos.length - (tieneId ? 2 : 1);
  if (fin < 1) return null;
  return segmentos.slice(0, fin).join("/");
}


export function esLecturaMiBorrador(url: string, recurso: string): boolean {
  const segmentos = segmentosRuta(url);
  return segmentos.at(-1) === "mi-borrador"
    && segmentos.slice(0, -1).join("/") === recurso;
}
