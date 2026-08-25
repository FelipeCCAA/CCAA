import { useEffect, useMemo, useState } from "react";
import { Beaker, BookOpen, CheckCircle2, Droplets, Pencil, Plus, Timer } from "lucide-react";

import {
  agitarVale, anularVale, calcularMezcla, corregirMuestraVale, decidirVale,
  muestrearVale, obtenerCatalogos, obtenerGuiaRC, obtenerVales, reagitarVale,
  transferirVale, type CatalogosEstandarizacion, type GuiaRC,
  type ValeEstandarizacion,
} from "../../services/estandarizacion.service";
import { obtenerProductos, type Producto } from "../../services/produccion.service";
import type { Silo } from "../../services/recepcion.service";
import { puedeEscribir } from "../../services/sesion";
import { mensajeDe, numero } from "../../components/seccion/utilidades";
import { Aviso, Tarjeta, Vacio } from "../../components/seccion/componentes";
import Cronometro from "./Cronometro";
import FormularioVale from "./FormularioVale";

const TONO: Record<string, string> = {
  calculado: "bg-slate-100 text-slate-600",
  transferido: "bg-sky-50 text-sky-700",
  agitando: "bg-indigo-50 text-indigo-700",
  muestreado: "bg-amber-50 text-amber-800",
  corrigiendo: "bg-amber-50 text-amber-800",
  liberado: "bg-emerald-50 text-emerald-700",
  anulado: "bg-rose-50 text-rose-700",
};

const rc = (valor: number | string | null | undefined) =>
  valor === null || valor === undefined || valor === ""
    ? "—"
    : Number(valor).toFixed(4);


function Estandarizacion() {
  const [vales, setVales] = useState<ValeEstandarizacion[]>([]);
  const [catalogos, setCatalogos] = useState<CatalogosEstandarizacion | null>(null);
  const [productos, setProductos] = useState<Producto[]>([]);
  const [guiaRC, setGuiaRC] = useState<GuiaRC[]>([]);
  const [buscarRC, setBuscarRC] = useState("");
  const [preseleccion, setPreseleccion] = useState<GuiaRC | null>(null);
  const [silos, setSilos] = useState<Silo[]>([]);
  const [valeId, setValeId] = useState<number | null>(null);
  const [nuevoAbierto, setNuevoAbierto] = useState(false);
  const [muestra, setMuestra] = useState({ grasa: "", sng: "" });
  const [correccion, setCorreccion] = useState<{
    grasa: string; sng: string; motivo: string;
  } | null>(null);
  const [ocupado, setOcupado] = useState(false);
  const [error, setError] = useState("");
  const [historico, setHistorico] = useState(false);

  const editable = puedeEscribir("estandarizacion");
  const vale = vales.find((item) => item.id === valeId) ?? null;

  const resumen = useMemo(() => ({
    agitando: vales.filter((item) => item.estado === "agitando").length,
    porDecidir: vales.filter((item) => item.estado === "muestreado").length,
    corrigiendo: vales.filter((item) => item.estado === "corrigiendo").length,
  }), [vales]);
  const guiaFiltrada = useMemo(() => {
    const texto = buscarRC.trim().toLocaleLowerCase("es");
    if (!texto) return guiaRC;
    return guiaRC.filter((item) =>
      item.producto_nombre.toLocaleLowerCase("es").includes(texto)
      || item.rc_objetivo.includes(texto.replace(",", ".")),
    );
  }, [buscarRC, guiaRC]);

  const cargar = async (verHistorico = historico) => {
    try {
      const datos = await obtenerVales(verHistorico ? {} : { abiertos: true });
      setVales(datos);
      setValeId((actual) =>
        actual && datos.some((item) => item.id === actual)
          ? actual
          : datos[0]?.id ?? null,
      );
      setError("");
    } catch {
      setError("No se pudo cargar los vales de estandarización.");
    }
  };

  useEffect(() => {
    const tarea = setTimeout(() => {
      void cargar();
      /*
        Los auxiliares van por separado y degradan solos: con un `Promise.all`
        que los junte, un maestro caído dejaría la pantalla entera en blanco
        aunque los vales sí hubieran llegado.
      */
      void obtenerCatalogos().then((datos) => {
        setCatalogos(datos);
        setSilos(datos.silos);
      }).catch(() => {
        setCatalogos(null);
        setSilos([]);
      });
      void obtenerProductos().then(setProductos).catch(() => setProductos([]));
      void obtenerGuiaRC().then(setGuiaRC).catch(() => setGuiaRC([]));
    }, 0);

    return () => clearTimeout(tarea);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const ejecutar = async (
    accion: () => Promise<unknown>,
    porDefecto: string,
  ) => {
    setOcupado(true);
    setError("");

    try {
      await accion();
      await cargar();
    } catch (e) {
      setError(mensajeDe(e, porDefecto));
    } finally {
      setOcupado(false);
    }
  };

  const guardarMuestra = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!vale) return;

    await ejecutar(
      () => muestrearVale(vale.id, Number(muestra.grasa), Number(muestra.sng)),
      "No se pudo registrar la muestra.",
    );
    setMuestra({ grasa: "", sng: "" });
  };

  const guardarCorreccion = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!vale || !correccion) return;
    setOcupado(true);
    setError("");
    try {
      await corregirMuestraVale(
        vale.id, Number(correccion.grasa), Number(correccion.sng),
        correccion.motivo,
      );
      setCorreccion(null);
      await cargar();
    } catch (e) {
      setError(mensajeDe(e, "No se pudo corregir la muestra."));
    } finally {
      setOcupado(false);
    }
  };

  const anular = async () => {
    if (!vale) return;
    const motivo = window.prompt("¿Por qué se anula este vale?") ?? "";
    if (!motivo.trim()) return;

    await ejecutar(() => anularVale(vale.id, motivo), "No se pudo anular el vale.");
  };

  return (
    <div className="space-y-6">

      <header className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[.18em] text-emerald-700">
            Antes de condensar
          </p>
          <h1 className="mt-1 text-2xl font-semibold text-slate-900">
            Estandarización
          </h1>
          <p className="mt-1 max-w-2xl text-sm text-slate-600">
            La mezcla de leche entera y descremada hasta el RC que pide el
            producto. RC = materia grasa ÷ sólidos no grasos.
          </p>
        </div>

        <div className="flex items-center gap-2">
          <label className="flex items-center gap-2 text-sm text-slate-600">
            <input
              type="checkbox"
              checked={historico}
              onChange={(e) => {
                setHistorico(e.target.checked);
                void cargar(e.target.checked);
              }}
            />
            Ver cerrados
          </label>

          {editable && (
            <button
              onClick={() => { setPreseleccion(null); setNuevoAbierto(true); }}
              className="flex items-center gap-2 rounded-xl bg-emerald-700 px-4 py-2.5 text-sm font-medium text-white"
            >
              <Plus className="h-4 w-4" />
              Nuevo vale
            </button>
          )}
        </div>
      </header>

      {error && <Aviso>{error}</Aviso>}

      {(catalogos?.silos ?? []).some((silo) => Number(silo.litros_disponibles ?? 0) > 0) && (
        <div className="rounded-2xl border border-sky-200 bg-sky-50 px-5 py-4 text-sm text-sky-900">
          <p className="font-semibold">Leche recepcionada disponible para estandarizar</p>
          <p className="mt-1 text-xs text-sky-700">{catalogos?.silos.filter((silo) => Number(silo.litros_disponibles ?? 0) > 0).map((silo) => `${silo.codigo}: ${numero(silo.litros_disponibles)} L`).join(" · ")}</p>
        </div>
      )}

      <section className="rounded-2xl border border-slate-200 bg-white p-5">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h2 className="flex items-center gap-2 font-semibold text-slate-900">
              <BookOpen className="h-5 w-5 text-emerald-700" /> Guía rápida de RC
            </h2>
            <p className="mt-1 text-xs text-slate-600">
              Objetivos usados anteriormente por producto. “Usar RC” abre el vale precargado.
            </p>
          </div>
          <input
            value={buscarRC}
            onChange={(e) => setBuscarRC(e.target.value)}
            placeholder="Buscar producto o RC…"
            className="w-full rounded-xl border border-slate-200 px-3 py-2 text-sm sm:w-64"
          />
        </div>
        <div className="mt-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
          {guiaFiltrada.map((item) => (
            <article key={`${item.producto}-${item.rc_objetivo}`} className="rounded-xl bg-slate-50 p-4">
              <p className="text-xs text-slate-600">{item.producto_nombre}</p>
              <p className="mt-1 text-2xl font-semibold text-slate-900">RC {rc(item.rc_objetivo)}</p>
              <p className="mt-1 text-[11px] text-slate-500">
                Usado {item.usos} {item.usos === 1 ? "vez" : "veces"} · último {item.usado_por_ultima_vez}
              </p>
              {editable && (
                <button
                  type="button"
                  onClick={() => { setPreseleccion(item); setNuevoAbierto(true); }}
                  className="mt-3 text-xs font-semibold text-emerald-700"
                >
                  Usar este RC →
                </button>
              )}
            </article>
          ))}
          {guiaFiltrada.length === 0 && (
            <p className="text-sm text-slate-500">
              Aún no hay RC registrados que coincidan. Al crear vales aparecerán aquí.
            </p>
          )}
        </div>
      </section>

      <section className="grid gap-4 sm:grid-cols-3">
        {([
          ["En agitación", resumen.agitando, Timer],
          ["Por decidir", resumen.porDecidir, Beaker],
          ["En corrección", resumen.corrigiendo, Droplets],
        ] as const).map(([texto, valor, Icono]) => (
          <article
            key={texto}
            className="rounded-2xl border border-slate-200 bg-white p-5"
          >
            <Icono className="h-5 w-5 text-emerald-700" />
            <p className="mt-4 text-sm text-slate-600">{texto}</p>
            <p className="mt-1 text-2xl font-semibold">{valor}</p>
          </article>
        ))}
      </section>

      <div className="grid gap-6 xl:grid-cols-[320px_1fr]">

        <section className="rounded-2xl border border-slate-200 bg-white p-3">
          <h2 className="px-2 pb-3 pt-1 text-sm font-semibold">Vales</h2>

          <div className="space-y-2">
            {vales.length === 0 && <Vacio>No hay vales abiertos.</Vacio>}

            {vales.map((item) => (
              <button
                key={item.id}
                onClick={() => { setValeId(item.id); setCorreccion(null); }}
                className={`w-full rounded-xl border p-3 text-left ${
                  valeId === item.id
                    ? "border-emerald-300 bg-emerald-50"
                    : "border-transparent bg-slate-50"
                }`}
              >
                <div className="flex justify-between gap-2">
                  <span className="font-medium">{item.codigo}</span>
                  <span
                    className={`rounded-full px-2 py-0.5 text-[11px] ${TONO[item.estado]}`}
                  >
                    {item.estado}
                  </span>
                </div>
                <p className="mt-1 text-xs text-slate-600">
                  {item.fecha} · RC {rc(item.rc_objetivo)} ·{" "}
                  {numero(item.volumen)} L → {item.silo_destino_codigo}
                </p>
              </button>
            ))}
          </div>
        </section>

        <div className="space-y-6">
          {!vale ? (
            <Tarjeta>
              <Vacio>Crea o selecciona un vale.</Vacio>
            </Tarjeta>
          ) : (
            <>
              <Tarjeta
                titulo={`${vale.codigo} · ${vale.producto_nombre}`}
                descripcion={`Objetivo RC ${rc(vale.rc_objetivo)} sobre ${numero(vale.volumen)} L en ${vale.silo_destino_codigo}.`}
                acciones={
                  <span
                    className={`rounded-full px-3 py-1 text-xs font-medium ${TONO[vale.estado]}`}
                  >
                    {vale.estado}
                  </span>
                }
              >
                <div className="grid gap-4 sm:grid-cols-4">
                  <Dato
                    etiqueta={`Entera · ${vale.silo_entera_codigo}`}
                    valor={`${numero(vale.litros_entera)} L`}
                    pie={`${vale.entera_grasa}% MG · ${vale.entera_sng}% SNG`}
                  />
                  <Dato
                    etiqueta={`Descremada · ${vale.silo_descremada_codigo ?? "—"}`}
                    valor={`${numero(vale.litros_descremada)} L`}
                    pie={`${vale.descremada_grasa}% MG · ${vale.descremada_sng}% SNG`}
                  />
                  <Dato etiqueta="RC objetivo" valor={rc(vale.rc_objetivo)} />
                  <Dato
                    etiqueta="RC medido"
                    valor={rc(vale.rc_real)}
                    pie={
                      vale.grasa_real
                        ? `${vale.grasa_real}% MG · ${vale.sng_real}% SNG`
                        : "sin muestra"
                    }
                  />
                </div>

                {vale.muestreado_en && vale.avisos.length > 0 && (
                  <ul className="mt-4 space-y-2">
                    {vale.avisos.map((aviso) => (
                      <li
                        key={aviso}
                        className="rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800"
                      >
                        {aviso}
                      </li>
                    ))}
                  </ul>
                )}

                {vale.evaluacion && !vale.evaluacion.cumple && (
                  <p className="mt-4 rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800">
                    {vale.evaluacion.motivo}
                  </p>
                )}

                {vale.observaciones && (
                  <pre className="mt-4 whitespace-pre-wrap rounded-xl bg-slate-50 px-4 py-3 text-xs text-slate-600">
                    {vale.observaciones}
                  </pre>
                )}
              </Tarjeta>

              <Tarjeta
                titulo="Ciclo del vale"
                descripcion="Transferir · agitar · muestrear · decidir. Cada paso tiene su regla; el sistema no ofrece el siguiente hasta que corresponde."
              >
                {!editable ? (
                  <Vacio>Tu rol no registra vales de estandarización.</Vacio>
                ) : (
                  <div className="space-y-4">

                    {vale.estado === "calculado" && (
                      <Paso
                        texto="Conecta el circuito y transfiere las dos leches al silo de destino."
                        boton="Transferido"
                        ocupado={ocupado}
                        onClick={() =>
                          void ejecutar(
                            () => transferirVale(vale.id),
                            "No se pudo marcar la transferencia.",
                          )
                        }
                      />
                    )}

                    {vale.estado === "transferido" && (
                      <Paso
                        texto="La agitación arranca ahora y el reloj lo lleva el servidor."
                        boton="Iniciar agitación"
                        ocupado={ocupado}
                        onClick={() =>
                          void ejecutar(
                            () => agitarVale(vale.id),
                            "No se pudo iniciar la agitación.",
                          )
                        }
                      />
                    )}

                    {vale.estado === "agitando" && (
                      <>
                        {/* La `key` reinicia el contador con cada dato nuevo
                            del servidor: el componente cuenta segundos desde
                            que se montó, no desde una hora absoluta. */}
                        <Cronometro
                          key={vale.minutos_agitando ?? "sin-reloj"}
                          minutosAlCargar={vale.minutos_agitando}
                          minutosExigidos={catalogos?.minutos_agitacion ?? null}
                        />

                        <form
                          onSubmit={guardarMuestra}
                          className="grid gap-3 rounded-xl bg-slate-50 p-4 sm:grid-cols-[1fr_1fr_auto]"
                        >
                          <label className="text-sm text-slate-600">
                            Materia grasa %
                            <input
                              required type="number" step="0.01" min="0"
                              value={muestra.grasa}
                              onChange={(e) =>
                                setMuestra({ ...muestra, grasa: e.target.value })
                              }
                              className="mt-1 w-full rounded-lg border border-slate-200 px-3 py-2"
                            />
                          </label>

                          <label className="text-sm text-slate-600">
                            Sólidos no grasos %
                            <input
                              required type="number" step="0.01" min="0.01"
                              value={muestra.sng}
                              onChange={(e) =>
                                setMuestra({ ...muestra, sng: e.target.value })
                              }
                              className="mt-1 w-full rounded-lg border border-slate-200 px-3 py-2"
                            />
                          </label>

                          <button
                            disabled={ocupado}
                            className="self-end rounded-lg bg-emerald-700 px-4 py-2.5 text-sm font-medium text-white disabled:opacity-40"
                          >
                            Registrar muestra
                          </button>
                        </form>
                      </>
                    )}

                    {vale.estado === "muestreado" && (
                      <Paso
                        texto="El sistema compara el RC medido con el objetivo y decide: libera o manda a corregir. La decisión no se elige."
                        boton="Decidir"
                        ocupado={ocupado}
                        onClick={() =>
                          void ejecutar(
                            () => decidirVale(vale.id),
                            "No se pudo decidir el vale.",
                          )
                        }
                      />
                    )}

                    {vale.estado === "corrigiendo" && (
                      <Paso
                        texto="Agrega la leche que indica el motivo y vuelve a agitar. El reloj empieza otra vez: agregar leche deshace la mezcla."
                        boton="Reagitar"
                        ocupado={ocupado}
                        onClick={() =>
                          void ejecutar(
                            () => reagitarVale(vale.id),
                            "No se pudo reiniciar la agitación.",
                          )
                        }
                      />
                    )}

                    {["muestreado", "corrigiendo"].includes(vale.estado) && !correccion && (
                      <button
                        type="button"
                        onClick={() => setCorreccion({
                          grasa: vale.grasa_real ?? "",
                          sng: vale.sng_real ?? "",
                          motivo: "",
                        })}
                        className="inline-flex items-center gap-2 rounded-lg border border-amber-300 bg-amber-50 px-4 py-2.5 text-sm font-medium text-amber-800"
                      >
                        <Pencil className="h-4 w-4" />Corregir muestra anterior
                      </button>
                    )}

                    {correccion && ["muestreado", "corrigiendo"].includes(vale.estado) && (
                      <form onSubmit={guardarCorreccion} className="grid gap-3 rounded-xl border border-amber-200 bg-amber-50 p-4 sm:grid-cols-2">
                        <label className="text-sm text-slate-700">Materia grasa %<input required type="number" step="0.01" min="0" value={correccion.grasa} onChange={(e) => setCorreccion({ ...correccion, grasa: e.target.value })} className="mt-1 w-full rounded-lg border border-amber-200 px-3 py-2" /></label>
                        <label className="text-sm text-slate-700">SNG %<input required type="number" step="0.01" min="0.01" value={correccion.sng} onChange={(e) => setCorreccion({ ...correccion, sng: e.target.value })} className="mt-1 w-full rounded-lg border border-amber-200 px-3 py-2" /></label>
                        <label className="text-sm text-slate-700 sm:col-span-2">Motivo de la corrección *<textarea required minLength={5} value={correccion.motivo} onChange={(e) => setCorreccion({ ...correccion, motivo: e.target.value })} className="mt-1 w-full rounded-lg border border-amber-200 px-3 py-2" /></label>
                        <div className="flex justify-end gap-2 sm:col-span-2"><button type="button" onClick={() => setCorreccion(null)} className="px-3 py-2 text-sm text-slate-600">Cancelar</button><button disabled={ocupado} className="rounded-lg bg-amber-700 px-4 py-2 text-sm font-medium text-white disabled:opacity-50">Guardar y recalcular</button></div>
                      </form>
                    )}

                    {vale.estado === "liberado" && (
                      <p className="flex items-center gap-2 rounded-xl border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-800">
                        <CheckCircle2 className="h-4 w-4" />
                        Silo liberado. Avisa a Condensación.
                      </p>
                    )}

                    {!["liberado", "anulado"].includes(vale.estado) && (
                      <button
                        onClick={() => void anular()}
                        disabled={ocupado}
                        className="text-sm text-rose-700 underline disabled:opacity-40"
                      >
                        Anular vale
                      </button>
                    )}

                  </div>
                )}
              </Tarjeta>
            </>
          )}
        </div>
      </div>

      {nuevoAbierto && (
        <FormularioVale
          productos={productos}
          silos={silos}
          preseleccion={preseleccion}
          onCerrar={() => setNuevoAbierto(false)}
          onCalcular={calcularMezcla}
          onConfirmado={async (creado) => {
            setNuevoAbierto(false);
            await cargar();
            void obtenerGuiaRC().then(setGuiaRC).catch(() => undefined);
            setValeId(creado.id);
          }}
        />
      )}

    </div>
  );
}


function Dato({
  etiqueta, valor, pie,
}: { etiqueta: string; valor: string; pie?: string }) {
  return (
    <div className="rounded-xl bg-slate-50 px-4 py-3">
      <p className="text-xs text-slate-600">{etiqueta}</p>
      <p className="mt-1 text-lg font-semibold text-slate-900">{valor}</p>
      {pie && <p className="mt-0.5 text-xs text-slate-600">{pie}</p>}
    </div>
  );
}


function Paso({
  texto, boton, ocupado, onClick,
}: { texto: string; boton: string; ocupado: boolean; onClick: () => void }) {
  return (
    <div className="flex flex-wrap items-center justify-between gap-3 rounded-xl bg-slate-50 px-4 py-3">
      <p className="max-w-xl text-sm text-slate-600">{texto}</p>
      <button
        onClick={onClick}
        disabled={ocupado}
        className="rounded-lg bg-emerald-700 px-4 py-2.5 text-sm font-medium text-white disabled:opacity-40"
      >
        {boton}
      </button>
    </div>
  );
}


export default Estandarizacion;
