import { useState } from "react";
import { AlertTriangle, Warehouse } from "lucide-react";

import {
  crearBodega,
  crearUbicacion,
  obtenerBodegas,
  obtenerCatalogosInventario,
  obtenerUbicaciones,
  type UbicacionInventario,
} from "../../services/inventario.service";

import { obtenerSesion } from "../../services/sesion";

import { Aviso, Estado, Tarjeta, Vacio } from "../../components/seccion/componentes";
import {
  claseBoton,
  claseCampo,
  claseCelda,
  claseEncabezado,
  mensajeDe,
  useCarga,
} from "../../components/seccion/utilidades";


/*
  Bodegas y ubicaciones: dónde vive el material.

  No estaban en ninguna parte —ni pantalla ni admin de Django, solo endpoints—
  y eso bloqueaba el módulo entero: sin una ubicación no entra nada a bodega,
  y el desplegable del formulario de ingreso salía vacío sin explicar por qué.

  El **tipo** de la ubicación no es una etiqueta. `registrar_entrada` manda a
  cuarentena lo que requiere Calidad y a disponible lo que no, y rechaza la
  entrada si no coincide. Una bodega sin ubicación de cuarentena no puede
  recibir nada que pase por Calidad — por eso la pantalla lo avisa en vez de
  dejar que se descubra al primer ingreso rechazado.
*/

/* Qué significa cada tipo. Las **etiquetas** vienen del backend; esto es la
   explicación, que es de la pantalla y no del catálogo. Un tipo nuevo aparece
   igual en el desplegable, solo que sin descripción. */
const QUE_ES: Record<string, string> = {
  disponible: "Material liberado, listo para consumir.",
  cuarentena: "Recién recibido, esperando a Calidad.",
  rechazado: "Lo que Calidad no aprobó.",
  produccion: "Entregado a planta.",
};

function Bodegas() {

  const bodegas = useCarga(obtenerBodegas);
  const ubicaciones = useCarga(obtenerUbicaciones);
  const catalogos = useCarga(obtenerCatalogosInventario);

  const [error, setError] = useState("");
  const [nuevaBodega, setNuevaBodega] = useState({
    codigo: "",
    nombre: "",
    area: "bodega",
  });
  const [nuevaUbicacion, setNuevaUbicacion] = useState({
    bodega: "",
    codigo: "",
    tipo: "disponible",
    descripcion: "",
  });

  const sesion = obtenerSesion();
  const area = sesion?.usuario.perfil?.area;
  const puedeEditar = area === "bodega" || sesion?.usuario.rol === "admin";

  const guardarBodega = async (evento: React.FormEvent) => {
    evento.preventDefault();
    setError("");

    try {
      await crearBodega(nuevaBodega);
      setNuevaBodega({ codigo: "", nombre: "", area: "bodega" });
      await bodegas.recargar();
    } catch (e) {
      setError(mensajeDe(e, "No se pudo crear la bodega: revisa que el código no esté repetido."));
    }
  };

  const guardarUbicacion = async (evento: React.FormEvent) => {
    evento.preventDefault();
    setError("");

    try {
      await crearUbicacion({
        ...nuevaUbicacion,
        bodega: Number(nuevaUbicacion.bodega),
      });
      setNuevaUbicacion({
        bodega: nuevaUbicacion.bodega,
        codigo: "",
        tipo: "disponible",
        descripcion: "",
      });
      await ubicaciones.recargar();
    } catch (e) {
      setError(
        mensajeDe(e, "No se pudo crear la ubicación: el código ya existe en esa bodega."),
      );
    }
  };

  const lista = ubicaciones.datos ?? [];

  const deBodega = (id: number) => lista.filter((u) => u.bodega === id);

  /* Sin cuarentena, la bodega no recibe nada que pase por Calidad; sin
     disponible, nada de lo que no pasa. Se avisa antes del primer rechazo. */
  const leFalta = (u: UbicacionInventario[]) =>
    [
      u.some((x) => x.tipo === "disponible" && x.activo) ? null : "disponible",
      u.some((x) => x.tipo === "cuarentena" && x.activo) ? null : "cuarentena",
    ].filter(Boolean) as string[];

  return (
    <div className="space-y-8">

      {error && <Aviso>{error}</Aviso>}

      {puedeEditar && (
        <div className="grid items-start gap-8 xl:grid-cols-2">

          <Tarjeta
            titulo="Nueva bodega"
            descripcion="El lugar físico. Una planta puede tener varias: central, de envases, de químicos."
          >
            <form onSubmit={guardarBodega} className="grid gap-3 sm:grid-cols-2">

              <input
                required
                placeholder="Código"
                value={nuevaBodega.codigo}
                onChange={(e) =>
                  setNuevaBodega({ ...nuevaBodega, codigo: e.target.value })
                }
                className={claseCampo}
              />

              <input
                required
                placeholder="Nombre"
                value={nuevaBodega.nombre}
                onChange={(e) =>
                  setNuevaBodega({ ...nuevaBodega, nombre: e.target.value })
                }
                className={claseCampo}
              />

              <select
                value={nuevaBodega.area}
                onChange={(e) =>
                  setNuevaBodega({ ...nuevaBodega, area: e.target.value })
                }
                className={`${claseCampo} sm:col-span-2`}
              >
                {(catalogos.datos?.area ?? []).map((o) => (
                  <option key={o.valor} value={o.valor}>
                    {o.etiqueta}
                  </option>
                ))}
              </select>

              <button className={`${claseBoton} sm:col-span-2`}>
                Crear bodega
              </button>

            </form>
          </Tarjeta>

          <Tarjeta
            titulo="Nueva ubicación"
            descripcion="El tipo decide qué puede entrar. No es una etiqueta: el sistema rechaza la entrada si no corresponde."
          >
            <form onSubmit={guardarUbicacion} className="grid gap-3">

              <select
                required
                value={nuevaUbicacion.bodega}
                onChange={(e) =>
                  setNuevaUbicacion({ ...nuevaUbicacion, bodega: e.target.value })
                }
                className={claseCampo}
              >
                <option value="">Bodega…</option>
                {(bodegas.datos ?? []).map((b) => (
                  <option key={b.id} value={b.id}>
                    {b.codigo} · {b.nombre}
                  </option>
                ))}
              </select>

              <div className="grid gap-3 sm:grid-cols-2">
                <input
                  required
                  placeholder="Código (p. ej. DISP-1)"
                  value={nuevaUbicacion.codigo}
                  onChange={(e) =>
                    setNuevaUbicacion({ ...nuevaUbicacion, codigo: e.target.value })
                  }
                  className={claseCampo}
                />

                <select
                  value={nuevaUbicacion.tipo}
                  onChange={(e) =>
                    setNuevaUbicacion({ ...nuevaUbicacion, tipo: e.target.value })
                  }
                  className={claseCampo}
                >
                  {(catalogos.datos?.tipo_ubicacion ?? []).map((o) => (
                    <option key={o.valor} value={o.valor}>
                      {o.etiqueta}
                    </option>
                  ))}
                </select>
              </div>

              <p className="text-sm text-slate-500">
                {QUE_ES[nuevaUbicacion.tipo]}
              </p>

              <button className={claseBoton} disabled={!nuevaUbicacion.bodega}>
                Crear ubicación
              </button>

            </form>
          </Tarjeta>

        </div>
      )}

      <Tarjeta
        titulo="Bodegas y sus ubicaciones"
        descripcion="Una bodega necesita al menos una ubicación disponible y una de cuarentena para poder recibir material."
        sinRelleno
      >
        {bodegas.error ? (
          <div className="p-5">
            <Aviso>{bodegas.error}</Aviso>
          </div>
        ) : bodegas.cargando ? (
          <Vacio>Cargando…</Vacio>
        ) : (bodegas.datos ?? []).length === 0 ? (
          <Vacio>
            Todavía no hay bodegas. Sin una bodega con sus ubicaciones no se
            puede ingresar material.
          </Vacio>
        ) : (
          <div className="divide-y divide-slate-100">
            {(bodegas.datos ?? []).map((b) => {
              const suyas = deBodega(b.id);
              const faltan = leFalta(suyas);

              return (
                <div key={b.id} className="p-5">

                  <div className="flex flex-wrap items-center justify-between gap-3">
                    <p className="flex items-center gap-2 font-medium text-slate-800">
                      <Warehouse className="h-4 w-4 text-slate-400" />
                      {b.nombre}
                      <span className="text-sm font-normal text-slate-400">
                        {b.codigo}
                      </span>
                    </p>

                    {faltan.length > 0 && (
                      <p className="flex items-center gap-1.5 rounded-lg bg-amber-50 px-3 py-1.5 text-xs font-medium text-amber-800">
                        <AlertTriangle className="h-3.5 w-3.5" />
                        Sin ubicación de {faltan.join(" ni de ")}: no puede
                        recibir {faltan.includes("cuarentena")
                          ? "material que pase por Calidad"
                          : "material liberado"}
                      </p>
                    )}
                  </div>

                  {suyas.length === 0 ? (
                    <p className="mt-3 text-sm text-slate-400">
                      Sin ubicaciones.
                    </p>
                  ) : (
                    <table className="mt-4 w-full">
                      <thead>
                        <tr>
                          <th className={claseEncabezado}>Ubicación</th>
                          <th className={claseEncabezado}>Tipo</th>
                          <th className={claseEncabezado}>Descripción</th>
                          <th className={claseEncabezado}>Estado</th>
                        </tr>
                      </thead>
                      <tbody>
                        {suyas.map((u) => (
                          <tr key={u.id} className="border-t border-slate-100">
                            <td className={`${claseCelda} font-medium text-slate-800`}>
                              {u.codigo}
                            </td>
                            <td className={claseCelda}>
                              <Estado valor={u.tipo} />
                            </td>
                            <td className={`${claseCelda} text-slate-500`}>
                              {u.descripcion || "—"}
                            </td>
                            <td className={`${claseCelda} text-slate-500`}>
                              {u.activo ? "activa" : "inactiva"}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  )}

                </div>
              );
            })}
          </div>
        )}
      </Tarjeta>

    </div>
  );
}


export default Bodegas;
