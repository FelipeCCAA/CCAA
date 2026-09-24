import { Fragment, useEffect, useId, useRef } from "react";

export interface FilaResumen {
  etiqueta: string;
  valor: string;
}

/*
  Resumen y confirmación de una operación irreversible.

  El foco va al panel y no al botón de confirmar: un lector de código manda
  Enter al final de cada escaneo, y con el foco en «Confirmar» un escaneo de
  más ejecutaría la operación.

  Es una región con nombre y no un `alertdialog`: se dibuja en línea, sin
  atrapar el foco ni cerrarse con Escape, y ese rol le anunciaría al lector de
  pantalla un modal que no existe.
*/
export default function ConfirmarAccion({
  titulo, filas, advertencia, textoConfirmar, peligro = false, ocupado = false, error = "",
  onConfirmar, onVolver,
}: {
  titulo: string;
  filas: FilaResumen[];
  advertencia?: string;
  textoConfirmar: string;
  peligro?: boolean;
  ocupado?: boolean;
  error?: string;
  onConfirmar: () => void;
  onVolver: () => void;
}) {
  const id = useId();
  const panel = useRef<HTMLElement>(null);

  useEffect(() => {
    panel.current?.focus();
  }, []);

  return (
    <section
      ref={panel}
      tabIndex={-1}
      role="region"
      aria-labelledby={`${id}-titulo`}
      className="rounded-2xl border-2 border-slate-300 bg-slate-50 p-5 outline-none focus:border-slate-500"
    >
      <h3 id={`${id}-titulo`} className="text-base font-semibold text-slate-900">{titulo}</h3>
      <dl className="mt-3 grid gap-x-6 gap-y-2 text-sm sm:grid-cols-[auto_1fr]">
        {filas.map((fila) => (
          <Fragment key={fila.etiqueta}>
            <dt className="text-slate-600">{fila.etiqueta}</dt>
            <dd className="font-medium tabular-nums text-slate-900">{fila.valor}</dd>
          </Fragment>
        ))}
      </dl>
      {advertencia && <p className="mt-3 rounded-xl bg-amber-50 px-4 py-2 text-sm text-amber-900">{advertencia}</p>}
      {error && <p role="alert" className="mt-3 rounded-xl bg-red-50 px-4 py-2 text-sm text-red-800">{error}</p>}
      <div className="mt-4 flex flex-wrap gap-3">
        <button
          type="button"
          disabled={ocupado}
          onClick={onConfirmar}
          className={`rounded-xl px-5 py-2.5 text-sm font-semibold text-white disabled:opacity-40 ${
            peligro ? "bg-red-700 hover:bg-red-800" : "bg-green-700 hover:bg-green-800"
          }`}
        >
          {ocupado ? "Registrando…" : textoConfirmar}
        </button>
        <button
          type="button"
          disabled={ocupado}
          onClick={onVolver}
          className="rounded-xl border border-slate-300 bg-white px-5 py-2.5 text-sm font-medium text-slate-700 hover:bg-slate-100 disabled:opacity-40"
        >
          Volver y corregir
        </button>
      </div>
    </section>
  );
}
