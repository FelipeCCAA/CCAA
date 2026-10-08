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


/*
  Caché de lecturas: una respuesta sirve durante `duracionMs`, se guardan como
  máximo `maxima`, y dos lecturas simultáneas de la misma clave comparten la
  petición. Pura —sin axios ni navegador— para poder probarla con un reloj
  manual.

  `vaciar()` existe para la recarga que pide una persona («Actualizar»): quien
  la pulsa sabe que el dato cambió en otra sesión —la segunda firma de Calidad
  se registra en otro navegador—, y esa escritura no vacía esta caché. Sin
  vaciarla, el botón devolvía la respuesta guardada y no cambiaba nada durante
  diez segundos. Vacía también las lecturas en camino: una que salió antes del
  cambio traería el dato viejo.
*/
export class CacheLecturas<R> {
  private readonly duracionMs: number;
  private readonly maxima: number;
  private readonly reloj: () => number;
  private readonly guardadas = new Map<string, { vence: number; respuesta: R; url: string }>();
  private readonly pendientes = new Map<string, Promise<R>>();

  constructor(duracionMs: number, maxima: number, reloj: () => number = () => Date.now()) {
    this.duracionMs = duracionMs;
    this.maxima = maxima;
    this.reloj = reloj;
  }

  leer(clave: string, url: string, pedir: () => Promise<R>): Promise<R> {
    const guardada = this.guardadas.get(clave);
    if (guardada && guardada.vence > this.reloj()) return Promise.resolve(guardada.respuesta);
    const pendiente = this.pendientes.get(clave);
    if (pendiente) return pendiente;

    const solicitud: Promise<R> = pedir()
      .then((respuesta) => {
        // Si alguien vació la caché mientras esta iba en camino, su respuesta
        // es anterior al cambio: se entrega a quien la pidió, pero no se guarda.
        if (this.pendientes.get(clave) === solicitud) {
          if (this.guardadas.size >= this.maxima) {
            const primera = this.guardadas.keys().next().value;
            if (primera !== undefined) this.guardadas.delete(primera);
          }
          this.guardadas.set(clave, { vence: this.reloj() + this.duracionMs, respuesta, url });
        }
        return respuesta;
      })
      .finally(() => {
        if (this.pendientes.get(clave) === solicitud) this.pendientes.delete(clave);
      });
    this.pendientes.set(clave, solicitud);
    return solicitud;
  }

  /* Borra las respuestas guardadas cuya URL cumple el criterio. */
  quitar(criterio: (url: string) => boolean): void {
    for (const [clave, guardada] of this.guardadas) {
      if (criterio(guardada.url)) this.guardadas.delete(clave);
    }
  }

  vaciar(): void {
    this.guardadas.clear();
    this.pendientes.clear();
  }
}
