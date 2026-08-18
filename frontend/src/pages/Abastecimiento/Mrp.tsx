import { Fragment, useState } from "react";
import { Link } from "react-router-dom";
import { AlertTriangle, CalendarClock, FileOutput, Play } from "lucide-react";

import {
  calcularMRP,
  ejecutarMRPSemana,
  esperarEjecucionMRP,
  obtenerEjecucionesMRP,
  solicitarCompraDesdeMRP,
  type EjecucionMRP,
  type ResultadoMRP,
} from "../../services/inventario.service";

import {
  obtenerProductosMaestros,
  type ProductoMaestro,
} from "../../services/maestros.service";

import { obtenerSemanas } from "../../services/planificacion.service";

import { Aviso, Tarjeta, Vacio } from "../../components/seccion/componentes";
import {
  claseBoton,
  claseCampo,
  claseCelda,
  claseEncabezado,
  mensajeDe,
  numero,
  useCarga,
} from "../../components/seccion/utilidades";


/*
  MRP.

  Hay dos, y responden preguntas distintas:

  - El **semanal** explota el programa publicado bloque por bloque, cada uno a
    su fecha, y deja la cadena entera de la resta: necesidad bruta, lo que hay,
    lo que ya viene en camino, lo que falta de verdad y cuándo hay que
    pedirlo. Es el que sirve para comprar.

  - El **simulador**: «si produzco 20.000 kg de esto, qué necesito». Explota la
    receta vigente hoy y sirve para cotizar o para decidir si se puede correr
    un lote.

  El semanal estaba escrito y probado en el backend desde hacía tiempo y **no
  se podía ejecutar desde ninguna pantalla**. Este es el botón que faltaba.
*/

/** Una semana en borrador todavía se mueve; comprar contra ella es comprar
    contra algo que nadie firmó. El backend lo rechaza y aquí ni se ofrece. */
const PUBLICADA = "publicada";


function TablaSemanal({ ejecucion }: { ejecucion: EjecucionMRP }) {

  const [detalle, setDetalle] = useState<number | null>(null);

  if (ejecucion.resultados.length === 0) {
    return (
      <Vacio>
        La explosión no arrojó necesidades: o la semana no tiene bloques de
        producción, o sus productos no tienen receta con insumos.
      </Vacio>
    );
  }

  // Lo que hay que pedir primero encabeza: es una lista para actuar, no un
  // informe. A igual fecha, primero lo de mayor cantidad.
  const filas = [...ejecucion.resultados].sort(
    (a, b) =>
      a.fecha_sugerida_orden.localeCompare(b.fecha_sugerida_orden) ||
      Number(b.compra_sugerida) - Number(a.compra_sugerida),
  );

  return (
    <div className="overflow-x-auto">
      <table className="w-full">

        <thead className="bg-slate-50">
          <tr>
            <th className={claseEncabezado}>Material</th>
            <th className={claseEncabezado}>Necesidad bruta</th>
            <th className={claseEncabezado}>Disponible</th>
            <th className={claseEncabezado}>Ya pedido</th>
            <th className={claseEncabezado}>Falta</th>
            <th className={claseEncabezado}>Comprar</th>
            <th className={claseEncabezado}>Pedir antes de</th>
          </tr>
        </thead>

        <tbody>
          {filas.map((r) => {
            const falta = Number(r.necesidad_neta) > 0;
            const abierto = detalle === r.id;

            return (
              <Fragment key={r.id}>

                <tr
                  onClick={() => setDetalle(abierto ? null : r.id)}
                  className="cursor-pointer border-t border-slate-100 hover:bg-slate-50"
                  title="Ver de dónde sale el número"
                >
                  <td className={`${claseCelda} font-medium text-slate-800`}>
                    {r.insumo_nombre}
                  </td>
                  <td className={`${claseCelda} text-slate-600`}>
                    {numero(r.necesidad_bruta)}
                  </td>
                  <td className={`${claseCelda} text-slate-600`}>
                    {numero(r.disponible_proyectado)}
                  </td>
                  <td className={`${claseCelda} text-slate-600`}>
                    {numero(r.recepciones_programadas)}
                  </td>
                  <td className={claseCelda}>
                    <span
                      className={
                        falta ? "font-semibold text-amber-700" : "text-slate-600"
                      }
                    >
                      {numero(r.necesidad_neta)}
                    </span>
                  </td>
                  <td className={`${claseCelda} font-semibold text-green-700`}>
                    {numero(r.compra_sugerida)}
                  </td>
                  <td className={claseCelda}>
                    <span className={falta ? "text-slate-700" : "text-slate-600"}>
                      {r.fecha_sugerida_orden}
                    </span>
                  </td>
                </tr>

                {/* De dónde sale la cifra. Un número de compra que no se puede
                    reconstruir no se firma — y la cantidad sugerida casi nunca
                    es la neta: la suben el mínimo y el múltiplo del proveedor. */}
                {abierto && (
                  <tr className="border-t border-slate-100 bg-slate-50">
                    <td colSpan={7} className="px-5 py-4">
                      <p className="text-sm text-slate-600">
                        Requerido el <strong>{r.fecha_requerida}</strong>.{" "}
                        {r.explicacion.formula && (
                          <>
                            Fórmula: <code>{r.explicacion.formula}</code>.{" "}
                          </>
                        )}
                        {r.explicacion.proveedor ? (
                          <>
                            Proveedor <strong>{r.explicacion.proveedor}</strong>,
                            compra mínima {r.explicacion.minimo}, múltiplo{" "}
                            {r.explicacion.multiplo}.
                          </>
                        ) : (
                          <span className="text-amber-700">
                            Sin proveedor principal: la cantidad sugerida es la
                            neta sin redondear y la fecha usa el plazo de
                            reposición del material.
                          </span>
                        )}
                      </p>
                    </td>
                  </tr>
                )}

              </Fragment>
            );
          })}
        </tbody>

      </table>
    </div>
  );
}


function Mrp() {

  const ejecuciones = useCarga(obtenerEjecucionesMRP);
  const semanas = useCarga(obtenerSemanas);
  const productos = useCarga(obtenerProductosMaestros);

  const [semana, setSemana] = useState("");
  const [corriendo, setCorriendo] = useState(false);
  const [error, setError] = useState("");
  const [reciente, setReciente] = useState<EjecucionMRP | null>(null);

  const [solicitando, setSolicitando] = useState(false);
  const [solicitud, setSolicitud] = useState("");

  const [producto, setProducto] = useState("");
  const [kilos, setKilos] = useState("");
  const [simulacion, setSimulacion] = useState<ResultadoMRP | null>(null);

  const solicitar = async (ejecucion: number) => {
    setError("");
    setSolicitando(true);

    try {
      const creada = await solicitarCompraDesdeMRP(ejecucion);
      setSolicitud(creada.numero);
    } catch (e) {
      setError(
        mensajeDe(e, "No se pudo generar la solicitud de compra."),
      );
    } finally {
      setSolicitando(false);
    }
  };

  const publicadas = (semanas.datos ?? []).filter((s) => s.estado === PUBLICADA);

  const terminados = (productos.datos ?? []).filter(
    (p: ProductoMaestro) => p.naturaleza === "terminado",
  );

  /*
    El cálculo ya no ocurre dentro de la petición: ocupaba un worker de
    Gunicorn de principio a fin y con workers `sync` tres cálculos dejaban al
    resto de la planta esperando. La petición devuelve la ejecución en cola y
    aquí se pregunta cómo va hasta que termina.

    Lo que el usuario ve es lo mismo que antes —pulsa y espera— pero el
    servidor queda libre mientras tanto.
  */
  const correr = async () => {
    setError("");
    setCorriendo(true);

    try {
      const encolada = await ejecutarMRPSemana(Number(semana));

      // Se muestra ya, en cola: sin esto la pantalla no da señal de vida
      // durante todo el cálculo y se pulsa el botón otra vez.
      setReciente(encolada);

      const terminada = await esperarEjecucionMRP(encolada.id);
      setReciente(terminada);

      if (terminada.estado === "fallida") {
        setError(
          terminada.error ||
            "El cálculo falló. Revisa la ejecución en el historial.",
        );
      } else if (!terminada.terminada) {
        setError(
          "El cálculo está tardando más de lo normal. Sigue en curso: " +
            "consúltalo en el historial en unos minutos.",
        );
      }

      await ejecuciones.recargar();
    } catch (e) {
      setError(
        mensajeDe(
          e,
          "No se pudo ejecutar el MRP. La semana tiene que estar publicada.",
        ),
      );
    } finally {
      setCorriendo(false);
    }
  };

  const simular = async (evento: React.FormEvent) => {
    evento.preventDefault();
    setError("");

    try {
      setSimulacion(await calcularMRP(Number(producto), Number(kilos)));
    } catch (e) {
      setError(
        mensajeDe(
          e,
          "No se pudo calcular. Revisa que el producto tenga una receta vigente con insumos declarados.",
        ),
      );
    }
  };

  // La última ejecución guardada, mientras no se corra una en esta visita.
  const aMostrar = reciente ?? (ejecuciones.datos ?? [])[0] ?? null;

  return (
    <div className="space-y-8">

      {error && <Aviso>{error}</Aviso>}

      {/* La solicitud queda en borrador: alguien la envía a aprobación y
          alguien distinto la aprueba. El MRP calcula, no compra. */}
      {solicitud && (
        <div className="rounded-2xl border border-green-200 bg-green-50 px-5 py-4 text-sm text-green-800">
          Solicitud <strong>{solicitud}</strong> creada en borrador.{" "}
          <Link to="../compras" className="font-medium underline">
            Ir a compras
          </Link>{" "}
          para enviarla a aprobación.
        </div>
      )}

      <Tarjeta
        titulo="MRP semanal"
        descripcion="Explota el programa publicado bloque por bloque, cada uno con la receta vigente a su fecha, y calcula qué comprar y cuándo pedirlo."
        acciones={
          <div className="flex shrink-0 gap-2">
            <select
              value={semana}
              onChange={(e) => setSemana(e.target.value)}
              className={claseCampo}
            >
              <option value="">Semana publicada…</option>
              {publicadas.map((s) => (
                <option key={s.id} value={s.id}>
                  {s.codigo} · {s.fecha_inicio}
                </option>
              ))}
            </select>

            <button
              type="button"
              disabled={!semana || corriendo}
              onClick={() => void correr()}
              className={`${claseBoton} flex items-center gap-2`}
            >
              <Play className="h-4 w-4" />
              {corriendo ? "Ejecutando…" : "Ejecutar"}
            </button>
          </div>
        }
        sinRelleno
      >
        {semanas.error ? (
          <div className="p-5">
            <Aviso>No se pudo cargar el plan: {semanas.error}</Aviso>
          </div>
        ) : publicadas.length === 0 && !semanas.cargando ? (
          <Vacio>
            No hay ninguna semana publicada. El MRP solo corre sobre un plan
            firmado: uno en borrador todavía se mueve.
          </Vacio>
        ) : aMostrar ? (
          <>
            <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-100 px-5 py-3">

              <p className="flex items-center gap-2 text-sm text-slate-600">
                <CalendarClock className="h-4 w-4 text-slate-600" />
                Corte {aMostrar.fecha_corte} · horizonte hasta{" "}
                {aMostrar.horizonte_hasta}
                {reciente && (
                  <span className="ml-2 rounded-full bg-green-50 px-2 py-0.5 text-xs font-medium text-green-700">
                    recién ejecutado
                  </span>
                )}
              </p>

              {/* El eslabón que faltaba. Sin esto, el cálculo terminaba en la
                  pantalla y alguien volvía a teclear las cantidades en otro
                  formulario — que es donde se pierde el «para cuándo». */}
              {aMostrar.resultados.some((r) => Number(r.compra_sugerida) > 0) && (
                <button
                  type="button"
                  disabled={solicitando}
                  onClick={() => void solicitar(aMostrar.id)}
                  className="flex shrink-0 items-center gap-2 rounded-xl border border-green-700 px-4 py-2 text-sm font-semibold text-green-800 hover:bg-green-50 disabled:opacity-40"
                >
                  <FileOutput className="h-4 w-4" />
                  {solicitando ? "Generando…" : "Generar solicitud de compra"}
                </button>
              )}

            </div>
            <TablaSemanal ejecucion={aMostrar} />
          </>
        ) : (
          <Vacio>
            Todavía no se ha ejecutado el MRP sobre ninguna semana. Elige una
            arriba y ejecútalo.
          </Vacio>
        )}
      </Tarjeta>

      {(ejecuciones.datos ?? []).length > 1 && (
        <Tarjeta
          titulo="Ejecuciones anteriores"
          descripcion="Cada ejecución queda guardada con sus resultados: es lo que permite preguntarse después por qué se compró lo que se compró."
          sinRelleno
        >
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead className="bg-slate-50">
                <tr>
                  <th className={claseEncabezado}>Ejecutada</th>
                  <th className={claseEncabezado}>Corte</th>
                  <th className={claseEncabezado}>Horizonte</th>
                  <th className={claseEncabezado}>Materiales</th>
                </tr>
              </thead>
              <tbody>
                {(ejecuciones.datos ?? []).map((e) => (
                  <tr key={e.id} className="border-t border-slate-100">
                    <td className={`${claseCelda} text-slate-600`}>
                      {e.creada_en?.slice(0, 10)}
                    </td>
                    <td className={`${claseCelda} text-slate-600`}>
                      {e.fecha_corte}
                    </td>
                    <td className={`${claseCelda} text-slate-600`}>
                      {e.horizonte_hasta}
                    </td>
                    <td className={`${claseCelda} text-slate-600`}>
                      {e.resultados.length}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Tarjeta>
      )}

      <Tarjeta
        titulo="Simulador"
        descripcion="Qué material hace falta para una cantidad dada, con la receta vigente hoy. Multinivel: si el producto lleva un intermedio, el material de ese intermedio también cuenta."
      >
        <form onSubmit={simular} className="flex flex-col gap-3 md:flex-row">

          <select
            required
            value={producto}
            onChange={(e) => setProducto(e.target.value)}
            className={`${claseCampo} flex-1`}
          >
            <option value="">Producto…</option>
            {terminados.map((p) => (
              <option key={p.id} value={p.id}>
                {p.nombre}
              </option>
            ))}
          </select>

          <input
            required
            type="number"
            min="0.001"
            step="0.001"
            placeholder="Kilos a producir"
            value={kilos}
            onChange={(e) => setKilos(e.target.value)}
            className={claseCampo}
          />

          <button className={claseBoton}>Calcular</button>

        </form>

        {simulacion && (
          <div className="mt-6">

            {/* Una lista incompleta se parece demasiado a una completa, y con
                ella se emite una orden de compra corta. */}
            {!simulacion.receta_completa && (
              <p className="mb-4 flex items-start gap-2 rounded-xl bg-amber-50 px-4 py-3 text-sm text-amber-800">
                <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
                La receta no se pudo explotar hasta el final: hay un producto
                intermedio sin receta propia o un ciclo. Esta lista está
                incompleta.
              </p>
            )}

            {simulacion.materiales.length === 0 ? (
              <Vacio>La receta vigente de este producto no declara insumos.</Vacio>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full">

                  <thead className="bg-slate-50">
                    <tr>
                      <th className={claseEncabezado}>Material</th>
                      <th className={claseEncabezado}>Requerido</th>
                      <th className={claseEncabezado}>En stock</th>
                      <th className={claseEncabezado}>Faltante</th>
                      <th className={claseEncabezado}>Envases a pedir</th>
                    </tr>
                  </thead>

                  <tbody>
                    {simulacion.materiales.map((m) => (
                      <tr key={m.insumo} className="border-t border-slate-100">
                        <td className={`${claseCelda} font-medium text-slate-800`}>
                          {m.insumo}
                        </td>
                        <td className={`${claseCelda} text-slate-600`}>
                          {numero(m.requerido)} {m.unidad}
                        </td>
                        <td className={`${claseCelda} text-slate-600`}>
                          {numero(m.stock)} {m.unidad}
                        </td>
                        <td className={claseCelda}>
                          <span
                            className={
                              Number(m.faltante) > 0
                                ? "font-semibold text-amber-700"
                                : "text-slate-600"
                            }
                          >
                            {numero(m.faltante)} {m.unidad}
                          </span>
                        </td>
                        <td className={`${claseCelda} font-semibold text-green-700`}>
                          {m.envases_a_pedir}
                        </td>
                      </tr>
                    ))}
                  </tbody>

                </table>
              </div>
            )}

          </div>
        )}
      </Tarjeta>

    </div>
  );
}


export default Mrp;
