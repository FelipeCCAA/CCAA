import { useState } from "react";

import {
  decidirInspeccion,
  obtenerInspecciones,
} from "../../services/inventario.service";

import { obtenerSesion } from "../../services/sesion";

import { Aviso, Estado, Tarjeta, Vacio } from "./componentes";
import NoConformidades from "./NoConformidades";
import { claseCelda, claseEncabezado, useCarga } from "./utilidades";


/*
  Calidad de materiales: la cuarentena.

  Un material marcado «requiere Calidad» entra a una ubicación de cuarentena y
  **no se puede consumir** hasta que alguien de Calidad lo decida. Es la misma
  idea que la liberación del lote de producción, un nivel más atrás: lo que
  entra a la planta también se libera.

  Los estados cerrados no vuelven a la bandeja. Lo que sigue abierto es lo que
  tiene producción esperando.
*/

const CERRADAS = ["aprobada", "observada", "rechazada", "bloqueada"];


function Calidad() {

  const inspecciones = useCarga(obtenerInspecciones);
  const [error, setError] = useState("");

  const sesion = obtenerSesion();
  const area = sesion?.usuario.perfil?.area;
  const puedeDecidir =
    area === "calidad" ||
    sesion?.usuario.rol === "calidad" ||
    sesion?.usuario.rol === "admin";

  const decidir = async (id: number, decision: string, observaciones = "") => {
    setError("");

    try {
      await decidirInspeccion(id, decision, observaciones);
      await inspecciones.recargar();
    } catch {
      setError("No se pudo registrar la decisión.");
    }
  };

  const lista = inspecciones.datos ?? [];
  const abiertas = lista.filter((i) => !CERRADAS.includes(i.estado));
  const cerradas = lista.filter((i) => CERRADAS.includes(i.estado));

  const tabla = (filas: typeof lista, conAcciones: boolean) => (
    <div className="overflow-x-auto">
      <table className="w-full">

        <thead className="bg-slate-50">
          <tr>
            <th className={claseEncabezado}>Material</th>
            <th className={claseEncabezado}>Lote</th>
            <th className={claseEncabezado}>Estado</th>
            <th className={claseEncabezado}></th>
          </tr>
        </thead>

        <tbody>
          {filas.map((i) => (
            <tr key={i.id} className="border-t border-slate-100">

              <td className={`${claseCelda} font-medium text-slate-800`}>
                {i.insumo_nombre}
              </td>

              <td className={`${claseCelda} text-slate-600`}>{i.lote_codigo}</td>

              <td className={claseCelda}>
                <Estado valor={i.estado} />
              </td>

              <td className={`${claseCelda} text-right`}>
                {conAcciones && puedeDecidir && (
                  <div className="flex justify-end gap-2">
                    <button
                      onClick={() => void decidir(i.id, "aprobada")}
                      className="rounded-lg bg-green-700 px-3 py-1.5 text-xs font-semibold text-white"
                    >
                      Liberar
                    </button>
                    <button
                      onClick={() =>
                        void decidir(i.id, "rechazada", "Rechazo desde la bandeja")
                      }
                      className="rounded-lg bg-red-50 px-3 py-1.5 text-xs font-semibold text-red-700"
                    >
                      Rechazar
                    </button>
                  </div>
                )}
              </td>

            </tr>
          ))}
        </tbody>

      </table>
    </div>
  );

  return (
    <div className="space-y-8">

      {error && <Aviso>{error}</Aviso>}

      <Tarjeta
        titulo="En cuarentena"
        descripcion="Material recibido que producción no puede usar hasta que Calidad lo libere."
        sinRelleno
      >
        {inspecciones.error ? (
          <div className="p-5">
            <Aviso>{inspecciones.error}</Aviso>
          </div>
        ) : inspecciones.cargando ? (
          <Vacio>Cargando…</Vacio>
        ) : abiertas.length === 0 ? (
          <Vacio>Nada en cuarentena.</Vacio>
        ) : (
          tabla(abiertas, true)
        )}
      </Tarjeta>

      <Tarjeta
        titulo="Decididas"
        descripcion="El histórico no se edita: una decisión de Calidad es un registro."
        sinRelleno
      >
        {cerradas.length === 0 ? (
          <Vacio>Todavía no hay decisiones registradas.</Vacio>
        ) : (
          tabla(cerradas.slice(0, 20), false)
        )}
      </Tarjeta>

      <NoConformidades />

    </div>
  );
}


export default Calidad;
