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
  const pendiente = useRef(false);
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
    pendiente.current = false;
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
      pendiente.current = true;
      await enCurso.current.catch(() => undefined);
      if (pendiente.current) {
        pendiente.current = false;
        return persistir(opciones);
      }
      return idRef.current;
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
    if (pendiente.current) {
      pendiente.current = false;
      return persistir(opciones);
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
