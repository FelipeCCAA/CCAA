import { useCallback, useEffect, useRef, useState } from "react";


/*
  Utilidades compartidas de la sección de abastecimiento.

  Van separadas de `componentes.tsx` porque el recargado en caliente de Vite
  solo funciona si un archivo exporta **o** componentes **o** otras cosas. No
  es un capricho del linter: mezclarlos hace que editar una constante recargue
  la página entera y se pierda el estado del formulario que estabas probando.
*/


/*
  El motivo que dio el backend, o uno por defecto.

  Los servicios de inventario responden `{"error": "..."}` y el resto de la
  API `{"detail": "..."}`; se leen los dos. Vale la pena: los motivos que
  manda este módulo son concretos —«Stock insuficiente de Bolsa 25 kg. Faltan
  3400», «El solicitante no puede aprobar su propia solicitud»— y taparlos con
  un «no se pudo» obliga a adivinar qué corregir.
*/
export function mensajeDe(error: unknown, porDefecto: string): string {
  const datos = (error as { response?: { data?: unknown } })?.response?.data;

  if (datos && typeof datos === "object") {
    const { error: motivo, detail } = datos as {
      error?: string;
      detail?: string;
    };

    if (motivo ?? detail) return motivo ?? detail ?? porDefecto;
    const partes = Object.entries(datos as Record<string, unknown>).flatMap(
      ([campo, valor]) => {
        const valores = Array.isArray(valor) ? valor : [valor];
        return valores.map((item) => `${campo}: ${String(item)}`);
      },
    );
    return partes.length ? partes.join(" · ") : porDefecto;
  }

  return porDefecto;
}


/** Formato chileno. Los saldos llevan hasta tres decimales, como el modelo. */
export function numero(valor: string | number | null | undefined): string {
  if (valor === null || valor === undefined || valor === "") {
    return "—";
  }

  return Number(valor).toLocaleString("es-CL", { maximumFractionDigits: 3 });
}


/*
  Carga de una sección.

  Cada pestaña trae **lo suyo**, y no hay un `Promise.all` que las junte: con
  uno solo, un endpoint caído deja la pantalla entera en blanco —y en este
  módulo los permisos son por área, así que a un usuario de Compras le van a
  fallar cosas de Bodega de forma perfectamente normal—.
*/
export function useCarga<T>(traer: () => Promise<T>) {
  const [datos, setDatos] = useState<T | null>(null);
  const [cargando, setCargando] = useState(true);
  const [error, setError] = useState("");

  // La función se guarda en una referencia y no en las dependencias: casi
  // todas las pestañas pasan una función del módulo —estable— pero alguna
  // pasa una flecha en línea, y esa cambia de identidad en cada render. Con
  // ella en las dependencias, el efecto volvería a pedir los datos para
  // siempre.
  const traerRef = useRef(traer);

  useEffect(() => {
    traerRef.current = traer;
  });

  const recargar = useCallback(async () => {
    setCargando(true);

    try {
      setDatos(await traerRef.current());
      setError("");
    } catch {
      setError("No se pudo cargar esta sección.");
    } finally {
      setCargando(false);
    }
  }, []);

  useEffect(() => {
    // Diferido con `setTimeout`, como en `Registros` y en el panel de
    // inocuidad: llamar a `setState` dentro del cuerpo de un efecto encadena
    // renders y el linter lo rechaza.
    const t = setTimeout(() => void recargar(), 0);

    return () => clearTimeout(t);
  }, [recargar]);

  return { datos, cargando, error, recargar };
}


export const claseCampo =
  "rounded-xl border border-slate-300 bg-white px-4 py-2.5 text-sm outline-none focus:border-green-600";

export const claseBoton =
  "rounded-xl bg-green-700 px-5 py-2.5 text-sm font-semibold text-white hover:bg-green-800 disabled:opacity-40";

export const claseEncabezado =
  "px-5 py-3 text-left text-xs font-semibold uppercase tracking-wide text-slate-600";

export const claseCelda = "px-5 py-3 text-sm";
