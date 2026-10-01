import { useEffect, useRef, useState, type FormEvent } from "react";

import { claseBoton, claseCampo } from "../seccion/utilidades";

/*
  Campo de búsqueda por código con el foco puesto.

  Un lector de código de barras en modo teclado escribe el código y manda
  Enter: con el foco aquí, escanear ya es buscar. Después de cada búsqueda el
  texto queda seleccionado para que el siguiente escaneo lo reemplace.
*/
export default function BuscadorCodigo({ etiqueta, ayuda, ocupado = false, onBuscar, comoFormulario = true }: {
  etiqueta: string;
  ayuda?: string;
  ocupado?: boolean;
  onBuscar: (texto: string) => void;
  /*
    Por defecto este control es su propio <form> (así manda Enter). Pero un
    <form> no puede anidarse dentro de otro: HTML lo invalida y el navegador
    dispara el submit del formulario exterior, no el de este buscador — en
    la hoja de carga eso cerraba el paso y perdía cliente, transportista y
    patente. Con `comoFormulario={false}` se renderiza como un <div> y el
    Enter se captura a mano en el campo, sin perder el atajo del escáner.
  */
  comoFormulario?: boolean;
}) {
  const [texto, setTexto] = useState("");
  const campo = useRef<HTMLInputElement>(null);

  useEffect(() => {
    campo.current?.focus();
  }, []);

  const buscar = () => {
    const limpio = texto.trim();
    if (limpio) onBuscar(limpio);
    campo.current?.select();
  };

  const enviar = (evento: FormEvent) => {
    evento.preventDefault();
    buscar();
  };

  const contenido = (
    <>
      <label className="flex min-w-0 flex-1 flex-col gap-1.5 text-sm">
        <span className="font-medium text-slate-700">{etiqueta}</span>
        <input
          ref={campo}
          type="search"
          value={texto}
          onChange={(evento) => setTexto(evento.target.value)}
          onKeyDown={comoFormulario ? undefined : (evento) => {
            if (evento.key === "Enter") {
              evento.preventDefault();
              buscar();
            }
          }}
          autoComplete="off"
          spellCheck={false}
          placeholder="Escanea o escribe el código"
          className={`${claseCampo} text-base`}
        />
        {ayuda && <span className="text-xs text-slate-600">{ayuda}</span>}
      </label>
      <button
        type={comoFormulario ? "submit" : "button"}
        onClick={comoFormulario ? undefined : buscar}
        disabled={ocupado || !texto.trim()}
        className={claseBoton}
      >
        {ocupado ? "Buscando…" : "Buscar"}
      </button>
    </>
  );

  if (!comoFormulario) {
    return <div role="search" className="flex flex-wrap items-end gap-3">{contenido}</div>;
  }

  return (
    <form role="search" onSubmit={enviar} className="flex flex-wrap items-end gap-3">
      {contenido}
    </form>
  );
}
