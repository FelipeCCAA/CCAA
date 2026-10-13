import { cantidad } from "./formato.ts";
import type {
  CremaPendienteCalidad, MantequeraPuesto, PuestoMantequilla, RevisionCierreMantequilla,
} from "./mantequilla.service.ts";

/* Un solo mapa de «dónde se resuelve» para los puestos. */
export { moduloDeResolver } from "./puesto-secado.ts";
/* La misma regla que `cancelar_preparacion_mantequilla` y que Descremado:
   corrida `borrador` con la ejecución en `borrador` o `preparacion`. Se
   reexporta en vez de copiarse. */
export { corridaCancelable } from "./puesto-descremado.ts";

export interface AccionMantequera {
  tipo: "preparar" | "iniciar" | "cerrar" | "ninguna";
  habilitada: boolean;
  motivo: string | null;
}

/*
  Qué botón lleva la tarjeta de una mantequera. Solo traduce lo que mandó el
  servidor: estado y motivos los calcula `estado_puesto_mantequilla` con las
  mismas reglas que deciden al preparar (`motivo_equipo_no_habilitado`) y al
  iniciar (`motivos_tipados_para_iniciar_mantequilla`). Los avisos no entran
  aquí a propósito: avisan, no deshabilitan.

  La única regla propia es espejo de `cerrar_mantequilla`: la ejecución pasa
  a `pendiente_control`, y eso solo se permite desde `ejecucion`.
*/
export function accionDeMantequera(fila: MantequeraPuesto): AccionMantequera {
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
        return { tipo: "cerrar", habilitada: false, motivo: "La corrida está pausada: reanúdala antes de registrar el balance." };
      }
      if (estado === "bloqueada") {
        return { tipo: "cerrar", habilitada: false, motivo: "La corrida está bloqueada: resuelve el bloqueo antes de registrar el balance." };
      }
      return { tipo: "cerrar", habilitada: fila.corrida?.id != null, motivo: null };
    }
    default:
      return { tipo: "ninguna", habilitada: false, motivo: null };
  }
}

export type FranjaBalance = "completo" | "incompleto" | "excedido" | "revisando" | "sin_revision";

export interface EstadoBalance {
  franja: FranjaBalance;
  titulo: string;
  detalle: string | null;
  /* Las otras reglas de lo tecleado (suero sin lote, reproceso sin motivo). */
  errores: string[];
  /* «Cerrar y enviar a Calidad» solo con una revisión de lo tecleado que cuadra y sin errores. */
  puedeCerrar: boolean;
}

/*
  Qué franja y qué texto pinta el cierre a partir de la respuesta de
  `revisar-cierre/`. No hay aritmética: el servidor decide si cuadra y cuánto
  falta (`balance_mantequilla`), y el cliente solo lee el signo de la
  diferencia para decir «incompleto» o «excedido». Una revisión en camino o
  fallida no habla de lo que se va a cerrar: no habilita nada.
*/
export function estadoDelBalance(
  revision: RevisionCierreMantequilla | null, pendiente: boolean, error = false,
): EstadoBalance {
  if (pendiente || (!revision && !error)) {
    return { franja: "revisando", titulo: "Revisando el balance…", detalle: null, errores: [], puedeCerrar: false };
  }
  if (!revision) {
    return {
      franja: "sin_revision", titulo: "No se pudo revisar el balance",
      detalle: "El servidor lo vuelve a decidir al cerrar.", errores: [], puedeCerrar: false,
    };
  }
  const errores = Object.values(revision.errores);
  const clasificados = `${cantidad(revision.clasificado_kg, "kg")} de ${cantidad(revision.entrada_kg, "kg")} clasificados.`;
  if (revision.cuadra) {
    return { franja: "completo", titulo: "Balance completo", detalle: clasificados, errores, puedeCerrar: errores.length === 0 };
  }
  const excedido = Number(revision.diferencia_kg) < 0;
  return {
    franja: excedido ? "excedido" : "incompleto",
    titulo: excedido ? "Balance excedido" : "Balance incompleto",
    detalle: revision.mensaje ?? clasificados,
    errores,
    puedeCerrar: false,
  };
}

export const MENSAJE_CREMA_SIN_SALDO =
  "La crema pedida no tiene saldo disponible para mantequilla: la tomaron otras corridas preparadas o en curso.";

export type CremaPedida =
  | { tipo: "ofrecida"; codigo: string }
  | { tipo: "pendiente"; codigo: string; crema: CremaPendienteCalidad }
  | { tipo: "sin_saldo"; codigo: null };

/*
  Qué pasa con la crema que llegó por `?crema=` («Preparar en Mantequilla»).
  Solo lee las dos listas del puesto: `cremas` es lo que «Preparar» acepta y
  `cremas_pendientes_calidad` explica las que esperan a Calidad. Una crema
  que no está en ninguna no tiene saldo para mantequilla —la tomaron otras
  corridas—, y decirlo evita un formulario con la crema en blanco y sin razón.
*/
export function cremaPedida(
  puesto: Pick<PuestoMantequilla, "cremas" | "cremas_pendientes_calidad">, cremaId: number | undefined,
): CremaPedida | null {
  if (cremaId === undefined) return null;
  const ofrecida = puesto.cremas.find((item) => item.id === cremaId);
  if (ofrecida) return { tipo: "ofrecida", codigo: ofrecida.codigo };
  const pendiente = puesto.cremas_pendientes_calidad.find((item) => item.id === cremaId);
  if (pendiente) return { tipo: "pendiente", codigo: pendiente.codigo, crema: pendiente };
  return { tipo: "sin_saldo", codigo: null };
}
