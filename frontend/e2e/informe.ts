/*
  Arma el informe legible a partir del registro que dejaron las pruebas.

  Corre como `globalTeardown`, o sea una vez y en el proceso principal — que es
  el único sitio donde se ve la corrida entera. Un `afterAll` dentro del archivo
  de pruebas no sirve: vive en el worker, y el worker se reinicia con cada
  fallo (ver `hallazgos.ts`).

  El informe se agrupa POR REGLA, no por pantalla
  -----------------------------------------------
  El menú lateral aparece en las treinta pantallas internas: un contraste flojo
  ahí produce treinta hallazgos idénticos. Por pantalla, eso se lee como treinta
  problemas y desanima antes de empezar. Por regla dice la verdad —«un arreglo,
  treinta pantallas»— y ordena el trabajo por lo que de verdad cuesta.

  La lista de pantallas afectadas se conserva igual, porque es lo único que
  distingue un defecto del marco común de uno de una pantalla concreta.
*/

import fs from "node:fs";
import path from "node:path";

import { RUTA_INFORME } from "./constantes";
import { leer, type Hallazgo } from "./hallazgos";

/** Gravedad de mayor a menor, para encabezar el informe con lo que más duele. */
const GRAVEDAD = ["critical", "serious", "moderate", "minor"];

/*
  Clases de utilidad con un tono al final (`text-slate-400`, `bg-green-600`).

  Contarlas es lo que convierte el informe en trabajo estimable: 550 fallos de
  contraste asustan, pero si 346 de ellos son `text-slate-400` la pregunta deja
  de ser «cuántos elementos hay que revisar» y pasa a ser «qué dos tonos hay que
  oscurecer». Una lista de 550 selectores no permite ver eso.
*/
const CLASE_CON_TONO = /^(?:text|bg|border|placeholder|ring|divide)-[a-z]+-\d{2,3}$/;


/** Las clases de utilidad que más se repiten entre los elementos afectados. */
function clasesRepetidas(nodos: Hallazgo["nodos"]): [string, number][] {
  const cuenta = new Map<string, number>();

  for (const nodo of nodos) {
    const atributo = nodo.html.match(/class="([^"]*)"/);
    if (!atributo) continue;

    /*
      Solo las clases SIN variante (`text-slate-400`, no `hover:text-slate-800`).

      axe mide el estado en reposo, así que una clase de `hover:` o `focus:`
      describe un color que en esa medición no se dibujó nunca. Contándolas, el
      informe atribuía 146 fallos a `text-slate-800` —un tono que sobre blanco
      contrasta de sobra— cuando el color que fallaba era el `text-slate-500`
      del mismo elemento. Una pista que apunta al sitio equivocado es peor que
      ninguna: manda a cambiar el color que no era.
    */
    const vistas = new Set(
      atributo[1].split(/\s+/).filter((c) => CLASE_CON_TONO.test(c)),
    );

    for (const clase of vistas) {
      cuenta.set(clase, (cuenta.get(clase) ?? 0) + 1);
    }
  }

  return [...cuenta.entries()].sort((a, b) => b[1] - a[1]).slice(0, 5);
}

const posicion = (gravedad: string) => {
  const i = GRAVEDAD.indexOf(gravedad);
  /* Una gravedad desconocida va al final y no al principio: `indexOf` devuelve
     -1, que ordenado tal cual la pondría por delante de «critical». */
  return i === -1 ? GRAVEDAD.length : i;
};


export default function escribirInforme(): void {
  const eventos = leer();

  const hallazgos = eventos.filter((e): e is Hallazgo => e.tipo === "hallazgo");
  const auditadas = new Set(
    eventos.filter((e) => e.tipo === "pantalla").map((e) => e.pantalla),
  );

  const porRegla = new Map<string, Hallazgo[]>();
  for (const hallazgo of hallazgos) {
    const previos = porRegla.get(hallazgo.regla) ?? [];
    previos.push(hallazgo);
    porRegla.set(hallazgo.regla, previos);
  }

  const nodosDe = (lista: Hallazgo[]) => lista.reduce((t, h) => t + h.nodos.length, 0);

  const reglas = [...porRegla.entries()].sort(([, a], [, b]) => {
    const orden = posicion(a[0].gravedad) - posicion(b[0].gravedad);
    return orden !== 0 ? orden : nodosDe(b) - nodosDe(a);
  });

  const totalNodos = nodosDe(hallazgos);

  const lineas: string[] = [
    "# Auditoría de accesibilidad — CCAA",
    "",
    "Generado por `e2e/accesibilidad.spec.ts` (axe-core sobre Chromium).",
    "",
    "Cubre lo que una máquina puede comprobar: contraste, etiquetas, nombres",
    "accesibles, encabezados de tabla, orden de títulos y tamaño de objetivo",
    "táctil. **No** dice si una pantalla se entiende ni si el flujo tiene",
    "demasiados pasos: eso lo contesta ver a un operario usándola.",
    "",
    "## Resumen",
    "",
    `- Pantallas auditadas: **${auditadas.size}**`,
    `- Reglas incumplidas: **${reglas.length}**`,
    `- Elementos afectados: **${totalNodos}**`,
    "",
  ];

  if (reglas.length > 0) {
    lineas.push(
      "| Regla | Gravedad | Elementos | Pantallas |",
      "|---|---|---|---|",
      ...reglas.map(([regla, lista]) => {
        const pantallas = new Set(lista.map((h) => h.pantalla)).size;
        return `| \`${regla}\` | ${lista[0].gravedad} | ${nodosDe(lista)} | ${pantallas} |`;
      }),
      "",
    );
  } else {
    lineas.push(
      auditadas.size === 0
        ? "> No se auditó ninguna pantalla. El informe está vacío porque la corrida no llegó\n" +
          "> a medir, no porque no haya defectos."
        : "> Ninguna regla incumplida.",
      "",
    );
  }

  for (const [regla, lista] of reglas) {
    const pantallas = [...new Set(lista.map((h) => h.pantalla))];
    const nodos = lista.flatMap((h) => h.nodos);
    const ejemplo = lista[0];
    const clases = clasesRepetidas(nodos);

    lineas.push(
      `## \`${regla}\` — ${ejemplo.gravedad}`,
      "",
      ejemplo.descripcion,
      "",
      `- Elementos afectados: **${nodos.length}** en **${pantallas.length}** pantalla(s)`,
      `- Referencia: ${ejemplo.ayuda}`,
      "",
      pantallas.length > 8
        ? `Aparece en ${pantallas.length} de las pantallas auditadas.`
        : `Pantallas: ${pantallas.join(" · ")}`,
      "",
    );

    /*
      No se afirma que las clases sean la causa: se dice cuántos elementos las
      llevan. La diferencia importa — un `text-slate-400` sobre fondo oscuro
      contrasta de sobra, y presentar la lista como «la causa» invitaría a un
      reemplazo global que rompe justamente esos casos.
    */
    if (clases.length > 0) {
      lineas.push(
        "Clases que más se repiten entre los elementos afectados:",
        "",
        ...clases.map(([clase, n]) => `- \`${clase}\` — ${n} de ${nodos.length} elementos`),
        "",
      );
    }

    lineas.push("Ejemplos:", "");

    for (const n of ejemplo.nodos.slice(0, 3)) {
      lineas.push(`- \`${n.selector}\``);
      if (n.detalle) {
        lineas.push(`  ${n.detalle}`);
      }
      lineas.push("  ```html", `  ${n.html}`, "  ```");
    }

    lineas.push("");
  }

  fs.mkdirSync(path.dirname(RUTA_INFORME), { recursive: true });
  fs.writeFileSync(RUTA_INFORME, lineas.join("\n"), "utf8");

  console.log(
    `\n  Informe: ${RUTA_INFORME} — ` +
      `${reglas.length} regla(s), ${totalNodos} elemento(s), ${auditadas.size} pantalla(s).\n`,
  );
}
