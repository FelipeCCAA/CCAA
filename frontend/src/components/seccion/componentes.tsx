import type { ReactNode } from "react";
import type { LucideIcon } from "lucide-react";


/*
  Piezas visuales compartidas de la sección de abastecimiento.

  Están aquí y no repetidas en cada pestaña por la misma razón que
  `CampoDePlantilla`: siete copias del mismo bloque divergen, y lo primero que
  divergen son los colores de estado — que es justamente lo que el usuario usa
  para decidir sin leer.

  Las funciones y constantes viven en `utilidades.ts`: este archivo exporta
  solo componentes, que es lo que el recargado en caliente necesita.
*/


/** Tarjeta con título y cuerpo. La unidad visual de toda la sección. */
export function Tarjeta({
  titulo,
  descripcion,
  acciones,
  children,
  sinRelleno = false,
}: {
  titulo?: string;
  descripcion?: string;
  acciones?: ReactNode;
  children: ReactNode;
  sinRelleno?: boolean;
}) {
  return (
    <section className="overflow-hidden rounded-2xl border border-slate-200 bg-white">

      {titulo && (
        <div className="flex items-start justify-between gap-4 border-b border-slate-200 px-5 py-4">
          <div>
            <h2 className="font-semibold text-slate-800">{titulo}</h2>
            {descripcion && (
              <p className="mt-1 max-w-2xl text-sm text-slate-600">{descripcion}</p>
            )}
          </div>
          {acciones}
        </div>
      )}

      <div className={sinRelleno ? "" : "p-5"}>{children}</div>

    </section>
  );
}


/** Indicador numérico del encabezado de una pestaña. */
export function Indicador({
  etiqueta,
  valor,
  Icono,
  tono = "normal",
}: {
  etiqueta: string;
  valor: string | number;
  Icono: LucideIcon;
  tono?: "normal" | "alerta";
}) {
  const color = tono === "alerta" ? "text-amber-600" : "text-green-700";

  return (
    <div className="rounded-2xl border border-slate-200 bg-white p-5">
      <Icono className={`h-5 w-5 ${color}`} />
      <p className="mt-4 text-sm text-slate-600">{etiqueta}</p>
      <p className="mt-1 text-2xl font-bold text-slate-900">{valor}</p>
    </div>
  );
}


/*
  Estado de un documento, con color.

  El mapa es explícito y no se deduce del texto: un estado que no esté aquí
  sale gris, que es lo correcto —un color inventado afirma algo sobre un
  estado que nadie clasificó—.
*/
const TONO_ESTADO: Record<string, string> = {
  // Bien
  aprobada: "bg-green-50 text-green-700",
  aprobado: "bg-green-50 text-green-700",
  completado: "bg-green-50 text-green-700",
  entregada: "bg-green-50 text-green-700",
  disponible: "bg-green-50 text-green-700",
  recepcion: "bg-green-50 text-green-700",
  // En curso
  enviada: "bg-blue-50 text-blue-700",
  preparada: "bg-blue-50 text-blue-700",
  parcial: "bg-blue-50 text-blue-700",
  en_curso: "bg-blue-50 text-blue-700",
  analisis: "bg-blue-50 text-blue-700",
  traslado: "bg-blue-50 text-blue-700",
  // Requiere atención
  pendiente: "bg-amber-50 text-amber-800",
  observada: "bg-amber-50 text-amber-800",
  muestra: "bg-amber-50 text-amber-800",
  cuarentena: "bg-amber-50 text-amber-800",
  merma: "bg-amber-50 text-amber-800",
  // Mal
  rechazada: "bg-red-50 text-red-700",
  rechazado: "bg-red-50 text-red-700",
  bloqueada: "bg-red-50 text-red-700",
  cancelada: "bg-red-50 text-red-700",
};


export function Estado({ valor }: { valor: string }) {
  const tono = TONO_ESTADO[valor] ?? "bg-slate-100 text-slate-600";

  return (
    <span
      className={`inline-block rounded-full px-2.5 py-0.5 text-xs font-medium ${tono}`}
    >
      {valor.replace(/_/g, " ")}
    </span>
  );
}


/** Mensaje de error de una sección. No tumba las demás. */
export function Aviso({ children }: { children: ReactNode }) {
  return (
    <div className="rounded-2xl border border-red-200 bg-red-50 px-5 py-4 text-sm text-red-700">
      {children}
    </div>
  );
}


/** Lo que se muestra cuando no hay nada que mostrar. */
export function Vacio({ children }: { children: ReactNode }) {
  return <p className="py-8 text-center text-sm text-slate-600">{children}</p>;
}
