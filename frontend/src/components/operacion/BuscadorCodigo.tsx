import { useEffect, useRef, useState, type FormEvent } from "react";

import { claseBoton, claseCampo } from "../seccion/utilidades";

/*
  Campo de búsqueda por código con el foco puesto.

  Un lector de código de barras en modo teclado escribe el código y manda
  Enter: con el foco aquí, escanear ya es buscar. Después de cada búsqueda el
  texto queda seleccionado para que el siguiente escaneo lo reemplace.
*/
export default function BuscadorCodigo({ etiqueta, ayuda, ocupado = false, onBuscar }: {
  etiqueta: string;
  ayuda?: string;
  ocupado?: boolean;
  onBuscar: (texto: string) => void;
}) {
  const [texto, setTexto] = useState("");
  const campo = useRef<HTMLInputElement>(null);

  useEffect(() => {
    campo.current?.focus();
  }, []);

  const enviar = (evento: FormEvent) => {
    evento.preventDefault();
    const limpio = texto.trim();
    if (limpio) onBuscar(limpio);
    campo.current?.select();
  };

  return (
    <form role="search" onSubmit={enviar} className="flex flex-wrap items-end gap-3">
      <label className="flex min-w-0 flex-1 flex-col gap-1.5 text-sm">
        <span className="font-medium text-slate-700">{etiqueta}</span>
        <input
          ref={campo}
          type="search"
          value={texto}
          onChange={(evento) => setTexto(evento.target.value)}
          autoComplete="off"
          spellCheck={false}
          placeholder="Escanea o escribe el código"
          className={`${claseCampo} text-base`}
        />
        {ayuda && <span className="text-xs text-slate-600">{ayuda}</span>}
      </label>
      <button type="submit" disabled={ocupado || !texto.trim()} className={claseBoton}>
        {ocupado ? "Buscando…" : "Buscar"}
      </button>
    </form>
  );
}
