import { ArrowDown, CircleDot } from "lucide-react";

import type { Genealogia, NodoGenealogia } from "../../services/procesos.service";


/*
  La genealogía de un lote, dibujada como lo que es: un árbol.

  Antes se mostraban los nodos como tarjetas sueltas y **los enlaces se
  ignoraban**. Eso responde «estos lotes tienen algo que ver» y deja sin
  responder la única pregunta que importa en una trazabilidad: *qué salió de
  qué*. Con seis tarjetas en pantalla no hay forma de saber cuál vino de cuál.

  Se dibuja por niveles desde el lote consultado. La dirección cambia el
  sentido de la flecha, no la estructura:

  - **hacia atrás**: de qué lotes salió este (sus ingredientes)
  - **hacia adelante**: qué lotes salieron de este (su descendencia)

  Un nivel con varios lotes es normal y significativo: una mezcla tiene varios
  orígenes, y un secado da producto principal más coproductos.
*/

function porNiveles(genealogia: Genealogia): NodoGenealogia[][] {
  const porId = new Map(genealogia.nodos.map((n) => [n.id, n]));

  /* Se recorre desde la raíz siguiendo los enlaces. Un lote puede aparecer por
     dos caminos —una mezcla que vuelve a juntarse— y se queda en el nivel más
     cercano, que es donde primero se alcanza. */
  const nivelDe = new Map<number, number>([[genealogia.raiz, 0]]);
  const frontera = [genealogia.raiz];

  while (frontera.length > 0) {
    const actual = frontera.shift()!;
    const nivel = nivelDe.get(actual)!;

    for (const enlace of genealogia.enlaces) {
      const vecino =
        enlace.destino === actual
          ? enlace.origen
          : enlace.origen === actual
            ? enlace.destino
            : null;

      if (vecino === null || nivelDe.has(vecino)) {
        continue;
      }

      nivelDe.set(vecino, nivel + 1);
      frontera.push(vecino);
    }
  }

  const niveles: NodoGenealogia[][] = [];

  for (const [id, nivel] of nivelDe) {
    const nodo = porId.get(id);

    if (!nodo) continue;

    (niveles[nivel] ??= []).push(nodo);
  }

  return niveles.filter(Boolean);
}


function Nodo({ nodo, esRaiz }: { nodo: NodoGenealogia; esRaiz: boolean }) {
  return (
    <div
      className={`rounded-xl border px-4 py-3 ${
        esRaiz
          ? "border-green-600 bg-green-50"
          : "border-slate-200 bg-white"
      }`}
    >
      <p className="flex items-center gap-2 font-semibold text-slate-800">
        {esRaiz && <CircleDot className="h-4 w-4 shrink-0 text-green-700" />}
        {nodo.codigo}
      </p>
      <p className="mt-1 text-sm text-slate-600">
        {nodo.producto} · {nodo.fecha}
      </p>
    </div>
  );
}


export default function ArbolGenealogia({
  genealogia,
  direccion,
}: {
  genealogia: Genealogia;
  direccion: "atras" | "adelante";
}) {

  const niveles = porNiveles(genealogia);

  if (niveles.length <= 1) {
    return (
      <p className="rounded-xl bg-slate-50 px-4 py-8 text-center text-sm text-slate-600">
        Este lote no tiene lotes {direccion === "atras" ? "de origen" : "derivados"}{" "}
        registrados. Aparece cuando entra o sale de una ejecución de proceso.
      </p>
    );
  }

  return (
    <div className="space-y-1">
      {niveles.map((nivel, indice) => (
        <div key={indice}>

          {indice > 0 && (
            <div className="flex items-center gap-2 py-2 pl-4 text-xs text-slate-600">
              <ArrowDown className="h-3.5 w-3.5" />
              {direccion === "atras" ? "salió de" : "dio origen a"}
            </div>
          )}

          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {nivel.map((nodo) => (
              <Nodo
                key={nodo.id}
                nodo={nodo}
                esRaiz={nodo.id === genealogia.raiz}
              />
            ))}
          </div>

        </div>
      ))}
    </div>
  );
}
