import { useState } from "react";
import { AlertTriangle, Ban, Milk, Truck } from "lucide-react";

import {
  crearRecoleccion,
  obtenerConductores,
  obtenerModulos,
  obtenerPredios,
  obtenerRecolecciones,
  registrarCarga,
  type Recoleccion as TipoRecoleccion,
} from "../../services/recoleccion.service";

import { obtenerVehiculosMaestros } from "../../services/maestros.service";

import {
  Aviso,
  Estado,
  Tarjeta,
  Vacio,
} from "../../components/seccion/componentes";
import {
  claseBoton,
  claseCampo,
  claseCelda,
  claseEncabezado,
  mensajeDe,
  numero,
  useCarga,
} from "../../components/seccion/utilidades";

import Maestros from "./Maestros";


/*
  Recolección de leche en predios.

  Es el primer eslabón de la cadena, y hasta ahora no existía: el sistema sabía
  de la leche recién cuando el camión llegaba a fábrica.

  La pantalla se organiza como se trabaja: una recolección es la salida del
  camión del día, y dentro van las cargas de cada predio que visita. La
  **prueba de alcohol** decide si esa leche sube o se queda, y el formulario lo
  refleja — al marcarla positiva, la casilla de «se cargó» se apaga sola y pide
  el motivo.

  Que la pantalla lo haga no reemplaza la regla del backend: `CargaPredio.clean()`
  la rechaza igual. Esto es para no ofrecer algo que el servidor va a negar.
*/

const VACIA = {
  predio: "",
  modulo: "",
  litros: "",
  temperatura: "",
  alcohol: "negativa",
  visual: "conforme",
  muestra_tomada: true,
  cargada: true,
  observaciones: "",
};

const PESTANAS = ["Recolecciones", "Maestros"] as const;


function FormularioCarga({
  recoleccion,
  alGuardar,
}: {
  recoleccion: TipoRecoleccion;
  alGuardar: () => Promise<void>;
}) {

  const predios = useCarga(obtenerPredios);
  const modulos = useCarga(obtenerModulos);

  const [datos, setDatos] = useState(VACIA);
  const [error, setError] = useState("");

  const predio = (predios.datos ?? []).find(
    (p) => String(p.id) === datos.predio,
  );

  /* La leche no conforme no sube al camión: ni por alcohol ni por evaluación
     visual. Se calcula aquí para que el formulario no ofrezca marcarla como
     cargada — el backend la rechaza igual, pero descubrirlo al enviar obliga a
     rehacerlo frente al estanque. */
  const puedeCargarse =
    datos.alcohol === "negativa" &&
    datos.visual === "conforme" &&
    !predio?.proveedor_bloqueado;

  const cargada = datos.cargada && puedeCargarse;

  const guardar = async (evento: React.FormEvent) => {
    evento.preventDefault();
    setError("");

    try {
      await registrarCarga({
        recoleccion: recoleccion.id,
        predio: Number(datos.predio),
        modulo: cargada ? Number(datos.modulo) : null,
        litros: datos.litros,
        temperatura: datos.temperatura,
        alcohol: datos.alcohol,
        visual: datos.visual,
        muestra_tomada: datos.muestra_tomada,
        cargada,
        observaciones: datos.observaciones,
      });
      setDatos(VACIA);
      await alGuardar();
    } catch (e) {
      setError(mensajeDe(e, "No se pudo registrar la carga."));
    }
  };

  return (
    <form onSubmit={guardar} className="mt-4 grid gap-3">

      {error && <Aviso>{error}</Aviso>}

      <div className="grid gap-3 sm:grid-cols-2">

        <select
          required
          value={datos.predio}
          onChange={(e) => setDatos({ ...datos, predio: e.target.value })}
          className={claseCampo}
        >
          <option value="">Predio…</option>
          {(predios.datos ?? [])
            .filter((p) => p.activo)
            .map((p) => (
              <option key={p.id} value={p.id}>
                {p.nombre} · {p.proveedor_nombre}
                {p.proveedor_bloqueado ? " (bloqueado)" : ""}
              </option>
            ))}
        </select>

        <select
          required={cargada}
          disabled={!cargada}
          value={cargada ? datos.modulo : ""}
          onChange={(e) => setDatos({ ...datos, modulo: e.target.value })}
          className={`${claseCampo} disabled:bg-slate-50 disabled:text-slate-400`}
        >
          <option value="">
            {cargada ? "Módulo…" : "Sin módulo: no se carga"}
          </option>
          {(modulos.datos ?? [])
            .filter((m) => m.activo)
            .map((m) => (
              <option key={m.id} value={m.id}>
                {m.vehiculo_placa} · módulo {m.numero}
              </option>
            ))}
        </select>

        <input
          required
          type="number"
          step="0.01"
          min="0.01"
          placeholder="Litros"
          value={datos.litros}
          onChange={(e) => setDatos({ ...datos, litros: e.target.value })}
          className={claseCampo}
        />

        <input
          required
          type="number"
          step="0.01"
          placeholder="Temperatura (°C) · objetivo ~4"
          value={datos.temperatura}
          onChange={(e) => setDatos({ ...datos, temperatura: e.target.value })}
          className={claseCampo}
        />

        <label className="text-sm text-slate-600">
          Prueba de alcohol
          <select
            value={datos.alcohol}
            onChange={(e) => setDatos({ ...datos, alcohol: e.target.value })}
            className={`${claseCampo} mt-1 w-full`}
          >
            <option value="negativa">Negativa (conforme)</option>
            <option value="positiva">Positiva (no conforme)</option>
          </select>
        </label>

        <label className="text-sm text-slate-600">
          Evaluación visual
          <select
            value={datos.visual}
            onChange={(e) => setDatos({ ...datos, visual: e.target.value })}
            className={`${claseCampo} mt-1 w-full`}
          >
            <option value="conforme">Conforme</option>
            <option value="no_conforme">No conforme</option>
          </select>
        </label>

      </div>

      {!puedeCargarse && (
        <p className="flex items-start gap-2 rounded-xl bg-amber-50 px-4 py-3 text-sm text-amber-800">
          <Ban className="mt-0.5 h-4 w-4 shrink-0" />
          {predio?.proveedor_bloqueado
            ? "El proveedor está bloqueado: no se le puede recolectar."
            : "Esta leche no sube al camión. Se registra igual, con su motivo, para poder reconstruir la desviación después."}
        </p>
      )}

      <textarea
        required={!puedeCargarse}
        rows={2}
        placeholder={
          puedeCargarse
            ? "Observaciones"
            : "Por qué no se cargó (obligatorio)"
        }
        value={datos.observaciones}
        onChange={(e) => setDatos({ ...datos, observaciones: e.target.value })}
        className={claseCampo}
      />

      <label className="flex items-center gap-2 text-sm text-slate-700">
        <input
          type="checkbox"
          checked={datos.muestra_tomada}
          onChange={(e) =>
            setDatos({ ...datos, muestra_tomada: e.target.checked })
          }
        />
        Muestra tomada
        <span className="text-xs text-slate-400">
          — se toma igual cuando la leche se rechaza: es lo que demuestra por qué
        </span>
      </label>

      <button className={claseBoton}>
        {puedeCargarse ? "Registrar carga" : "Registrar desviación"}
      </button>

    </form>
  );
}


function Recoleccion() {

  const recolecciones = useCarga(obtenerRecolecciones);
  const conductores = useCarga(obtenerConductores);
  const vehiculos = useCarga(obtenerVehiculosMaestros);

  const [pestana, setPestana] = useState<(typeof PESTANAS)[number]>(
    "Recolecciones",
  );
  const [error, setError] = useState("");
  const [abierta, setAbierta] = useState<number | null>(null);
  const [nueva, setNueva] = useState({
    codigo: "",
    fecha: new Date().toISOString().slice(0, 10),
    conductor: "",
    camion: "",
    carro: "",
  });

  const crear = async (evento: React.FormEvent) => {
    evento.preventDefault();
    setError("");

    try {
      await crearRecoleccion({
        codigo: nueva.codigo,
        fecha: nueva.fecha,
        conductor: Number(nueva.conductor),
        camion: Number(nueva.camion),
        carro: nueva.carro ? Number(nueva.carro) : null,
      });
      setNueva({ ...nueva, codigo: "" });
      await recolecciones.recargar();
    } catch (e) {
      setError(mensajeDe(e, "No se pudo crear la recolección."));
    }
  };

  const lista = recolecciones.datos ?? [];

  return (
    <div className="px-8 py-10">

      <div className="mx-auto max-w-7xl">

        <header className="mb-6">
          <p className="text-sm font-semibold uppercase tracking-wider text-green-700">
            Materia prima
          </p>
          <h1 className="mt-2 flex items-center gap-3 text-3xl font-bold text-slate-800">
            <Milk className="h-7 w-7 text-slate-400" />
            Recolección en predios
          </h1>
          <p className="mt-2 max-w-3xl text-slate-500">
            Lo que se mide frente al estanque antes de que la leche suba al
            camión. La prueba de alcohol decide si sube o se queda.
          </p>
        </header>

        <nav className="mb-8 flex gap-1 border-b border-slate-200">
          {PESTANAS.map((p) => (
            <button
              key={p}
              type="button"
              onClick={() => setPestana(p)}
              className={`border-b-2 px-4 py-3 text-sm font-medium transition-colors ${
                pestana === p
                  ? "border-green-700 text-green-800"
                  : "border-transparent text-slate-500 hover:text-slate-800"
              }`}
            >
              {p}
            </button>
          ))}
        </nav>

        {pestana === "Maestros" ? (
          <Maestros />
        ) : (
          <div className="space-y-8">

            {error && <Aviso>{error}</Aviso>}

            <Tarjeta
              titulo="Nueva recolección"
              descripcion="La salida del camión del día. Dentro van las cargas de cada predio que visita."
            >
              <form onSubmit={crear} className="grid gap-3 md:grid-cols-5">

                <input
                  required
                  placeholder="Código"
                  value={nueva.codigo}
                  onChange={(e) => setNueva({ ...nueva, codigo: e.target.value })}
                  className={claseCampo}
                />

                <input
                  required
                  type="date"
                  value={nueva.fecha}
                  onChange={(e) => setNueva({ ...nueva, fecha: e.target.value })}
                  className={claseCampo}
                />

                <select
                  required
                  value={nueva.conductor}
                  onChange={(e) =>
                    setNueva({ ...nueva, conductor: e.target.value })
                  }
                  className={claseCampo}
                >
                  <option value="">Conductor…</option>
                  {(conductores.datos ?? [])
                    .filter((c) => c.activo)
                    .map((c) => (
                      <option key={c.id} value={c.id}>
                        {c.nombre}
                      </option>
                    ))}
                </select>

                <select
                  required
                  value={nueva.camion}
                  onChange={(e) => setNueva({ ...nueva, camion: e.target.value })}
                  className={claseCampo}
                >
                  <option value="">Camión…</option>
                  {(vehiculos.datos ?? []).map((v) => (
                    <option key={v.id} value={v.id}>
                      {v.placa}
                    </option>
                  ))}
                </select>

                <select
                  value={nueva.carro}
                  onChange={(e) => setNueva({ ...nueva, carro: e.target.value })}
                  className={claseCampo}
                >
                  <option value="">Carro (opcional)…</option>
                  {(vehiculos.datos ?? [])
                    .filter((v) => String(v.id) !== nueva.camion)
                    .map((v) => (
                      <option key={v.id} value={v.id}>
                        {v.placa}
                      </option>
                    ))}
                </select>

                <button className={`${claseBoton} md:col-span-5`}>
                  Crear recolección
                </button>

              </form>
            </Tarjeta>

            <Tarjeta
              titulo="Recolecciones"
              descripcion="Los litros son los que efectivamente subieron al camión: se suman del detalle."
              sinRelleno
            >
              {recolecciones.error ? (
                <div className="p-5">
                  <Aviso>{recolecciones.error}</Aviso>
                </div>
              ) : recolecciones.cargando ? (
                <Vacio>Cargando…</Vacio>
              ) : lista.length === 0 ? (
                <Vacio>
                  Todavía no hay recolecciones. Antes de crear una necesitas al
                  menos un conductor y un camión, en la pestaña Maestros.
                </Vacio>
              ) : (
                <div className="divide-y divide-slate-100">
                  {lista.map((r) => (
                    <div key={r.id} className="p-5">

                      <div className="flex flex-wrap items-center justify-between gap-3">
                        <p className="flex flex-wrap items-center gap-2 font-medium text-slate-800">
                          <Truck className="h-4 w-4 text-slate-400" />
                          {r.codigo}
                          <Estado valor={r.estado} />
                          <span className="text-sm font-normal text-slate-500">
                            {r.fecha} · {r.conductor_nombre} · {r.camion_placa}
                            {r.carro_placa ? ` + ${r.carro_placa}` : ""}
                          </span>
                        </p>

                        <div className="flex items-center gap-3">
                          <span className="text-sm font-semibold text-green-700">
                            {numero(r.litros_cargados)} L
                          </span>
                          <button
                            onClick={() =>
                              setAbierta(abierta === r.id ? null : r.id)
                            }
                            className="rounded-lg border border-slate-200 px-3 py-1.5 text-xs font-medium text-slate-600 hover:bg-slate-50"
                          >
                            {abierta === r.id ? "Cerrar" : "Registrar carga"}
                          </button>
                        </div>
                      </div>

                      {r.predios_rechazados.length > 0 && (
                        <p className="mt-2 flex items-center gap-1.5 text-sm text-amber-800">
                          <AlertTriangle className="h-3.5 w-3.5" />
                          Leche dejada en: {r.predios_rechazados.join(", ")}
                        </p>
                      )}

                      {r.cargas.length > 0 && (
                        <table className="mt-4 w-full">
                          <thead>
                            <tr>
                              <th className={claseEncabezado}>Predio</th>
                              <th className={claseEncabezado}>Litros</th>
                              <th className={claseEncabezado}>Temp.</th>
                              <th className={claseEncabezado}>Alcohol</th>
                              <th className={claseEncabezado}>Módulo</th>
                              <th className={claseEncabezado}>Muestra</th>
                            </tr>
                          </thead>
                          <tbody>
                            {r.cargas.map((c) => (
                              <tr
                                key={c.id}
                                className={`border-t border-slate-100 ${
                                  c.cargada ? "" : "bg-amber-50/40"
                                }`}
                              >
                                <td className={`${claseCelda} text-slate-800`}>
                                  {c.predio_nombre}
                                  <div className="text-xs text-slate-400">
                                    {c.proveedor_nombre}
                                  </div>
                                </td>
                                <td className={`${claseCelda} text-slate-600`}>
                                  {numero(c.litros)}
                                </td>
                                <td className={`${claseCelda} text-slate-600`}>
                                  {numero(c.temperatura)} °C
                                </td>
                                <td className={claseCelda}>
                                  <Estado
                                    valor={
                                      c.alcohol === "negativa"
                                        ? "conforme"
                                        : "rechazada"
                                    }
                                  />
                                </td>
                                <td className={`${claseCelda} text-slate-600`}>
                                  {c.modulo_numero ?? (
                                    <span className="text-amber-800">
                                      no se cargó
                                    </span>
                                  )}
                                </td>
                                <td className={`${claseCelda} text-slate-500`}>
                                  {c.muestra_tomada ? "sí" : "no"}
                                </td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      )}

                      {abierta === r.id && (
                        <FormularioCarga
                          recoleccion={r}
                          alGuardar={recolecciones.recargar}
                        />
                      )}

                    </div>
                  ))}
                </div>
              )}
            </Tarjeta>

          </div>
        )}

      </div>

    </div>
  );
}


export default Recoleccion;
