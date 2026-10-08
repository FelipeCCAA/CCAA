import type { DescremadoraPuesto, RevisionCierreDescremado } from "./descremado.service.ts";

/* Un solo mapa de «dónde se resuelve» para los puestos (Desviación 17). */
export { moduloDeResolver } from "./puesto-secado.ts";

export interface AccionDescremadora {
  tipo: "preparar" | "iniciar" | "cerrar" | "ninguna";
  habilitada: boolean;
  motivo: string | null;
}

/*
  Qué botón lleva la tarjeta de una descremadora. Solo traduce lo que mandó
  el servidor: estado y motivos los calcula `estado_puesto_descremado` con
  las mismas reglas que deciden al preparar (`motivo_equipo_no_habilitado`) y
  al iniciar (`motivos_tipados_para_iniciar_descremacion`). Los avisos no
  entran aquí a propósito: avisan, no deshabilitan.

  La única regla propia es espejo de `cerrar_descremacion`: la ejecución
  pasa a `pendiente_control`, y eso solo se permite desde `ejecucion`.
  Ofrecer las salidas sobre una pausada o bloqueada es ofrecer algo que el
  servidor rechaza.
*/
export function accionDeDescremadora(fila: DescremadoraPuesto): AccionDescremadora {
  switch (fila.estado) {
    case "disponible": {
      const motivo = fila.motivos_para_tomar[0] ?? null;
      return { tipo: "preparar", habilitada: motivo === null, motivo };
    }
    case "preparada": {
      const motivo = fila.motivos_para_iniciar[0] ?? null;
      return { tipo: "iniciar", habilitada: motivo === null && fila.corrida?.id != null, motivo };
    }
    case "en_curso": {
      const estado = fila.corrida?.ejecucion_estado;
      if (estado === "pausada") {
        return { tipo: "cerrar", habilitada: false, motivo: "La corrida está pausada: reanúdala antes de registrar las salidas." };
      }
      if (estado === "bloqueada") {
        return { tipo: "cerrar", habilitada: false, motivo: "La corrida está bloqueada: resuelve el bloqueo antes de registrar las salidas." };
      }
      return { tipo: "cerrar", habilitada: fila.corrida?.id != null, motivo: null };
    }
    default:
      return { tipo: "ninguna", habilitada: false, motivo: null };
  }
}

/*
  La corrida que «Cancelar preparación» soltaría, o `null`. Espejo de
  `cancelar_preparacion_descremacion`: corrida en `borrador` con la ejecución
  en `preparacion` —o en `borrador`, las heredadas del modal anterior, que
  solo aparecen en el historial—. Los motivos que impiden iniciar no impiden
  cancelar: suelen ser justo la razón.
*/
export function corridaCancelable(
  corrida: { id: number | null; estado: string | null; ejecucion_estado: string } | null | undefined,
): number | null {
  if (!corrida || corrida.id === null || corrida.estado !== "borrador") return null;
  return ["borrador", "preparacion"].includes(corrida.ejecucion_estado) ? corrida.id : null;
}

/* La situación de una corrida («Preparada», «En la descremadora»…) no se
   calcula aquí: la sirve el servidor (`situacion_etiqueta`) con la misma
   tabla que filtra el historial (`SITUACIONES_DESCREMACION`). */

export interface AvisosCierre {
  /* Avisos de una revisión que corresponde a lo tecleado; nunca de una vieja. */
  avisos: string[];
  /* Lo que el panel dice en vez de la lista, o `null` si hay avisos que mostrar. */
  mensaje: string | null;
  /* ¿La revisión corresponde a lo que se va a cerrar? */
  vigente: boolean;
  /* Qué repite la confirmación: los límites vigentes, o que se calculan al cerrar. */
  advertencia: string | undefined;
}

const SE_CALCULAN_AL_CERRAR = "Los avisos no alcanzaron a revisarse con lo registrado: el servidor los calcula al cerrar.";

/*
  Qué dice el panel de avisos del cierre. «Sin avisos» es una afirmación del
  servidor, así que solo se dice con una revisión en la mano: si la consulta
  falló o va en camino tras una tecla, la revisión anterior ya no habla de lo
  que se va a cerrar y no se muestra. Los avisos no deciden nada —el servidor
  los vuelve a calcular y los guarda al cerrar—, pero un «sin avisos» falso
  confirma un cierre que sí los tenía.
*/
export function avisosDeCierre({ revision, error, pendiente }: {
  revision: RevisionCierreDescremado | null;
  error: boolean;
  pendiente: boolean;
}): AvisosCierre {
  if (pendiente) {
    return { avisos: [], mensaje: "Revisando avisos…", vigente: false, advertencia: SE_CALCULAN_AL_CERRAR };
  }
  if (error || !revision) {
    return {
      avisos: [],
      mensaje: error ? "No se pudieron revisar los avisos; el servidor los vuelve a calcular al cerrar." : "Revisando avisos…",
      vigente: false,
      advertencia: SE_CALCULAN_AL_CERRAR,
    };
  }
  const limites = revision.avisos_limites.map((aviso) => aviso.mensaje);
  const avisos = [...limites, ...revision.avisos_balance];
  return {
    avisos,
    mensaje: avisos.length ? null : "Sin avisos con lo registrado.",
    vigente: true,
    advertencia: limites.length ? limites.join(" ") : undefined,
  };
}
