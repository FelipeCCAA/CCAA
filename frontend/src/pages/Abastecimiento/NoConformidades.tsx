import { useState } from "react";
import { CalendarX2, FileWarning, ShieldAlert } from "lucide-react";

import {
  cerrarNoConformidad,
  obtenerLiberacionesExcepcionales,
  obtenerNoConformidades,
  type NoConformidad,
} from "../../services/inventario.service";

import { obtenerSesion } from "../../services/sesion";

import { Aviso, Estado, Tarjeta, Vacio } from "./componentes";
import {
  claseBoton,
  claseCampo,
  claseCelda,
  claseEncabezado,
  mensajeDe,
  numero,
  useCarga,
} from "./utilidades";


/*
  No conformidades de material y las concesiones que las resuelven.

  Cerrar una no conformidad exige **decir qué se hizo con el material**. Antes
  `cerrada` era un booleano suelto: afirmaba que el asunto se acabó y no quién
  lo cerró, cuándo ni con qué acción — que es exactamente lo que un auditor
  pide de un material que Calidad rechazó.

  Y si el destino es liberación excepcional, exige la concesión enlazada y
  **vigente**. «Se liberó por concesión» sin poder mostrar cuál deja el
  material usado sin respaldo, que es peor que no documentarlo: parece que sí
  lo tiene.
*/

function Cierre({
  nc,
  alCerrar,
}: {
  nc: NoConformidad;
  alCerrar: (accion: string) => Promise<void>;
}) {
  const [accion, setAccion] = useState("");
  const [guardando, setGuardando] = useState(false);

  const enviar = async (evento: React.FormEvent) => {
    evento.preventDefault();
    setGuardando(true);
    await alCerrar(accion);
    setGuardando(false);
  };

  return (
    <form onSubmit={enviar} className="mt-4 grid gap-3">
      <textarea
        required
        rows={2}
        placeholder="Qué se hizo con el material"
        value={accion}
        onChange={(e) => setAccion(e.target.value)}
        className={claseCampo}
      />

      {nc.destino === "excepcional" && !nc.liberacion && (
        <p className="text-sm text-amber-800">
          El destino es liberación excepcional: enlaza primero la concesión que
          lo autoriza. Se crean en el administrador.
        </p>
      )}

      <button className={claseBoton} disabled={guardando}>
        {guardando ? "Cerrando…" : "Cerrar no conformidad"}
      </button>
    </form>
  );
}


function NoConformidades() {

  const noConformidades = useCarga(obtenerNoConformidades);
  const concesiones = useCarga(obtenerLiberacionesExcepcionales);

  const [error, setError] = useState("");
  const [abierta, setAbierta] = useState<number | null>(null);

  const sesion = obtenerSesion();
  const area = sesion?.usuario.perfil?.area;
  const puedeCerrar =
    area === "calidad" ||
    sesion?.usuario.rol === "calidad" ||
    sesion?.usuario.rol === "admin";

  const cerrar = async (nc: NoConformidad, accion: string) => {
    setError("");

    try {
      await cerrarNoConformidad(nc.id, accion);
      setAbierta(null);
      await noConformidades.recargar();
    } catch (e) {
      setError(mensajeDe(e, "No se pudo cerrar la no conformidad."));
    }
  };

  const lista = noConformidades.datos ?? [];
  const abiertas = lista.filter((n) => !n.cerrada);
  const cerradas = lista.filter((n) => n.cerrada);

  return (
    <div className="space-y-8">

      {error && <Aviso>{error}</Aviso>}

      <Tarjeta
        titulo="No conformidades abiertas"
        descripcion="Material que Calidad rechazó u observó, esperando qué se hace con él."
        sinRelleno
      >
        {noConformidades.error ? (
          <div className="p-5">
            <Aviso>{noConformidades.error}</Aviso>
          </div>
        ) : noConformidades.cargando ? (
          <Vacio>Cargando…</Vacio>
        ) : abiertas.length === 0 ? (
          <Vacio>Sin no conformidades abiertas.</Vacio>
        ) : (
          <div className="divide-y divide-slate-100">
            {abiertas.map((n) => (
              <div key={n.id} className="p-5">

                <div className="flex flex-wrap items-start justify-between gap-3">

                  <div className="min-w-0">
                    <p className="flex items-center gap-2 font-medium text-slate-800">
                      <FileWarning className="h-4 w-4 text-amber-600" />
                      {n.insumo_nombre}
                      <span className="text-sm font-normal text-slate-400">
                        lote {n.lote_codigo}
                      </span>
                      <Estado valor={n.destino} />
                    </p>
                    <p className="mt-1 text-sm text-slate-500">{n.descripcion}</p>

                    {n.destino === "excepcional" && (
                      <p
                        className={`mt-2 inline-flex items-center gap-1.5 rounded-lg px-2.5 py-1 text-xs font-medium ${
                          n.liberacion_vigente
                            ? "bg-green-50 text-green-800"
                            : "bg-amber-50 text-amber-800"
                        }`}
                      >
                        <ShieldAlert className="h-3.5 w-3.5" />
                        {n.liberacion === null
                          ? "sin concesión enlazada"
                          : n.liberacion_vigente
                            ? `concesión ${n.liberacion} vigente`
                            : `concesión ${n.liberacion} vencida o inactiva`}
                      </p>
                    )}
                  </div>

                  {puedeCerrar && (
                    <button
                      onClick={() => setAbierta(abierta === n.id ? null : n.id)}
                      className="shrink-0 rounded-lg border border-slate-200 px-3 py-1.5 text-xs font-medium text-slate-600 hover:bg-slate-50"
                    >
                      {abierta === n.id ? "Cancelar" : "Cerrar"}
                    </button>
                  )}

                </div>

                {abierta === n.id && (
                  <Cierre nc={n} alCerrar={(accion) => cerrar(n, accion)} />
                )}

              </div>
            ))}
          </div>
        )}
      </Tarjeta>

      <Tarjeta
        titulo="Concesiones"
        descripcion="Amparan una cantidad acotada de un lote que Calidad no aprobó, para un uso concreto y con vencimiento. El lote sigue bloqueado para todo lo demás: no entra al stock disponible ni lo toma el FEFO."
        sinRelleno
      >
        {concesiones.error ? (
          <div className="p-5">
            <Aviso>{concesiones.error}</Aviso>
          </div>
        ) : (concesiones.datos ?? []).length === 0 ? (
          <Vacio>
            Sin concesiones registradas. Se crean en el administrador de Django:
            autorizar el uso de material no aprobado lo decide Calidad.
          </Vacio>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead className="bg-slate-50">
                <tr>
                  <th className={claseEncabezado}>Material</th>
                  <th className={claseEncabezado}>Lote</th>
                  <th className={claseEncabezado}>Autorizado</th>
                  <th className={claseEncabezado}>Queda</th>
                  <th className={claseEncabezado}>Uso autorizado</th>
                  <th className={claseEncabezado}>Firmas</th>
                  <th className={claseEncabezado}>Vence</th>
                </tr>
              </thead>
              <tbody>
                {(concesiones.datos ?? []).map((c) => (
                  <tr key={c.id} className="border-t border-slate-100">
                    <td className={`${claseCelda} font-medium text-slate-800`}>
                      {c.insumo_nombre}
                    </td>
                    <td className={`${claseCelda} text-slate-600`}>
                      {c.lote_codigo}
                    </td>
                    <td className={`${claseCelda} text-slate-600`}>
                      {numero(c.cantidad)}
                    </td>

                    {/* Lo que todavía ampara. Una concesión agotada ya no
                        deja salir material aunque siga vigente. */}
                    <td className={claseCelda}>
                      <span
                        className={
                          Number(c.saldo) > 0
                            ? "font-medium text-green-700"
                            : "text-slate-400"
                        }
                      >
                        {numero(c.saldo)}
                      </span>
                    </td>
                    <td className={`${claseCelda} text-slate-500`}>
                      {c.uso_especifico}
                    </td>
                    <td className={`${claseCelda} text-slate-500`}>
                      {c.calidad_nombre}
                      {c.jefatura_nombre ? ` · ${c.jefatura_nombre}` : (
                        <span className="text-amber-700"> · falta jefatura</span>
                      )}
                    </td>
                    <td className={claseCelda}>
                      <span
                        className={
                          c.vigente
                            ? "text-slate-600"
                            : "inline-flex items-center gap-1 font-medium text-red-700"
                        }
                      >
                        {!c.vigente && <CalendarX2 className="h-3.5 w-3.5" />}
                        {c.vence_en?.slice(0, 10)}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Tarjeta>

      <Tarjeta titulo="Cerradas" sinRelleno>
        {cerradas.length === 0 ? (
          <Vacio>Todavía no hay no conformidades cerradas.</Vacio>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead className="bg-slate-50">
                <tr>
                  <th className={claseEncabezado}>Material</th>
                  <th className={claseEncabezado}>Destino</th>
                  <th className={claseEncabezado}>Qué se hizo</th>
                  <th className={claseEncabezado}>Cerró</th>
                </tr>
              </thead>
              <tbody>
                {cerradas.slice(0, 20).map((n) => (
                  <tr key={n.id} className="border-t border-slate-100">
                    <td className={`${claseCelda} font-medium text-slate-800`}>
                      {n.insumo_nombre}
                      <div className="text-xs font-normal text-slate-400">
                        lote {n.lote_codigo}
                      </div>
                    </td>
                    <td className={claseCelda}>
                      <Estado valor={n.destino} />
                    </td>
                    <td className={`${claseCelda} text-slate-600`}>
                      {n.accion_tomada}
                    </td>
                    <td className={`${claseCelda} text-slate-500`}>
                      {n.cerrada_por_nombre}
                      <div className="text-xs">{n.cerrada_en?.slice(0, 10)}</div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Tarjeta>

    </div>
  );
}


export default NoConformidades;
