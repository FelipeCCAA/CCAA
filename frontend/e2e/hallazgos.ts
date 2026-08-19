/*
  Acumulación de hallazgos en disco.

  Por qué en disco y no en un arreglo del módulo
  ----------------------------------------------
  Playwright reinicia el proceso worker después de cada prueba que falla, para
  que una prueba rota no contamine a la siguiente. Eso vacía cualquier variable
  de módulo. En una suite normal da igual —los fallos son la excepción—, pero
  esta auditoría existe precisamente para encontrar fallos: aquí el reinicio es
  el caso normal, no el raro.

  Acumulando en memoria, el informe salía con los hallazgos de la última prueba
  y decía «1 pantalla auditada» después de recorrer tres. Peor que un informe
  incompleto: uno que se ve completo.

  Se escribe una línea JSON por evento (JSONL) porque es a prueba de reinicios:
  cada anotación es un `append` cerrado en sí mismo, así que matar el proceso a
  mitad pierde como mucho la última línea, no el archivo.
*/

import fs from "node:fs";
import path from "node:path";

import { RUTA_HALLAZGOS } from "./constantes";

export interface Nodo {
  selector: string;
  html: string;
  /** Motivo concreto según axe; para el contraste, los colores y la razón. */
  detalle?: string;
}

export interface Hallazgo {
  tipo: "hallazgo";
  pantalla: string;
  ruta: string;
  regla: string;
  gravedad: string;
  descripcion: string;
  ayuda: string;
  nodos: Nodo[];
}

/** Marca de que una pantalla llegó a auditarse, tenga o no defectos. */
export interface PantallaAuditada {
  tipo: "pantalla";
  pantalla: string;
  ruta: string;
}

export type Evento = Hallazgo | PantallaAuditada;


/** Vacía el registro. Lo llama `globalSetup`, antes de la primera prueba. */
export function limpiar(): void {
  fs.mkdirSync(path.dirname(RUTA_HALLAZGOS), { recursive: true });
  fs.writeFileSync(RUTA_HALLAZGOS, "", "utf8");
}


export function anotar(evento: Evento): void {
  fs.mkdirSync(path.dirname(RUTA_HALLAZGOS), { recursive: true });
  fs.appendFileSync(RUTA_HALLAZGOS, `${JSON.stringify(evento)}\n`, "utf8");
}


export function leer(): Evento[] {
  if (!fs.existsSync(RUTA_HALLAZGOS)) {
    return [];
  }

  return fs
    .readFileSync(RUTA_HALLAZGOS, "utf8")
    .split("\n")
    .filter((linea) => linea.trim() !== "")
    /* Una línea truncada por un corte a mitad de escritura se descarta en vez
       de reventar el informe entero por su culpa. */
    .flatMap((linea) => {
      try {
        return [JSON.parse(linea) as Evento];
      } catch {
        return [];
      }
    });
}
