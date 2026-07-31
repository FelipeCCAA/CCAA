import api from "./api";

import type { Pagina } from "./produccion.service";


/*
  Registro de auditoría: quién cambió qué, cuándo, y de qué a qué.

  Solo lectura. No hay funciones para crear, editar ni borrar porque el
  backend tampoco expone esos endpoints: un registro de auditoría que se puede
  modificar no prueba nada.
*/

export interface RegistroAuditoria {
  id: number;
  fecha_hora: string;
  usuario: number | null;
  /* Copia del nombre al momento del cambio: sobrevive al borrado del
     usuario. */
  usuario_nombre: string;
  accion: "creacion" | "modificacion" | "borrado";
  accion_etiqueta: string;
  /* 'produccion.Lote' */
  modelo: string;
  etiqueta_modelo: string;
  objeto_id: string;
  objeto_desc: string;
  /* {campo: [antes, después]} */
  cambios: Record<string, [unknown, unknown]>;
  ip: string | null;
  origen: string;
}


export interface FiltrosAuditoria {
  modelos: { valor: string; etiqueta: string }[];
  usuarios: string[];
  acciones: { valor: string; etiqueta: string }[];
  apps_auditadas: string[];
}


export interface ConsultaAuditoria {
  usuario?: string;
  modelo?: string;
  accion?: string;
  objeto?: string;
  desde?: string;
  hasta?: string;
  buscar?: string;
  pagina?: number;
}


export async function buscarAuditoria(
  consulta: ConsultaAuditoria = {},
): Promise<Pagina<RegistroAuditoria>> {

  const { data } = await api.get<Pagina<RegistroAuditoria>>(
    "auditoria/registros/",
    {
      // axios omite los `undefined`, así que un filtro vacío no viaja.
      params: {
        usuario: consulta.usuario || undefined,
        modelo: consulta.modelo || undefined,
        accion: consulta.accion || undefined,
        objeto: consulta.objeto || undefined,
        desde: consulta.desde || undefined,
        hasta: consulta.hasta || undefined,
        buscar: consulta.buscar || undefined,
        page: consulta.pagina && consulta.pagina > 1 ? consulta.pagina : undefined,
      },
    },
  );

  return data;
}


export async function obtenerFiltrosAuditoria(): Promise<FiltrosAuditoria> {
  const { data } = await api.get<FiltrosAuditoria>("auditoria/filtros/");

  return data;
}
