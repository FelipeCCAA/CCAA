import { useCallback, useEffect, useRef, useState } from "react";

import { borradorCambio, huellaBorrador } from "./borrador-control";

interface DocumentoConId { id: number }

interface Opciones<T, R extends DocumentoConId> {
  datos: T;
  activo: boolean;
  crear: (datos: T) => Promise<R>;
  actualizar: (id: number, datos: T) => Promise<R>;
  alError?: () => void;
  demora?: number;
}

export function useBorrador<T, R extends DocumentoConId>({
  datos, activo, crear, actualizar, alError, demora = 2000,
}: Opciones<T, R>) {
  const [id, setId] = useState<number | null>(null);
  const [estado, setEstado] = useState<"sin_cambios" | "guardando" | "guardado" | "error">("sin_cambios");
  const datosRef = useRef(datos);
  const huella = huellaBorrador(datos);
  const huellaRef = useRef(huella);
  const ultimaGuardada = useRef<string | null>(null);
  const idRef = useRef<number | null>(null);
  const enCurso = useRef<Promise<R> | null>(null);
  const crearRef = useRef(crear);
  const actualizarRef = useRef(actualizar);
  const errorRef = useRef(alError);

  datosRef.current = datos;
  huellaRef.current = huella;
  crearRef.current = crear;
  actualizarRef.current = actualizar;
  errorRef.current = alError;

  const reanudar = useCallback((documentoId: number) => {
    idRef.current = documentoId;
    setId(documentoId);
    setEstado("guardado");
  }, []);

  const reiniciar = useCallback(() => {
    idRef.current = null;
    ultimaGuardada.current = null;
    setId(null);
    setEstado("sin_cambios");
  }, []);

  const guardarAhora = useCallback(async function persistir(
    opciones: { propagarError?: boolean } = {},
  ): Promise<number | null> {
    if (!activo) return idRef.current;
    if (!borradorCambio(ultimaGuardada.current, huellaRef.current)) {
      return idRef.current;
    }
    if (enCurso.current) {
      await enCurso.current.catch(() => undefined);
      /* No basta con esperar la escritura que estaba en curso: mientras se
         resolvía pudo cambiar otro campo. Se vuelve a comparar la huella y,
         si corresponde, se persiste la versión más reciente antes de dejar
         continuar a quien pidió guardar ahora. */
      return persistir(opciones);
    }

    setEstado("guardando");
    const huellaEnviada = huellaRef.current;
    const solicitud = idRef.current === null
      ? crearRef.current(datosRef.current)
      : actualizarRef.current(idRef.current, datosRef.current);
    enCurso.current = solicitud;
    try {
      const documento = await solicitud;
      idRef.current = documento.id;
      ultimaGuardada.current = huellaEnviada;
      setId(documento.id);
      setEstado("guardado");
    } catch (error) {
      setEstado("error");
      errorRef.current?.();
      if (opciones.propagarError) throw error;
    } finally {
      enCurso.current = null;
    }
    return idRef.current;
  }, [activo]);

  useEffect(() => {
    if (!activo || !borradorCambio(ultimaGuardada.current, huella)) return;
    const temporizador = window.setTimeout(() => { void guardarAhora(); }, demora);
    return () => window.clearTimeout(temporizador);
  }, [activo, demora, guardarAhora, huella]);

  return { id, estado, guardarAhora, reanudar, reiniciar };
}
