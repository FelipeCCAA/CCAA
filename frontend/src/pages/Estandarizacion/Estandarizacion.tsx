import { useEffect, useMemo, useState } from "react";
import { Beaker, CheckCircle2, Droplets, Plus, Timer } from "lucide-react";

import {
  agitarVale, anularVale, calcularMezcla, crearVale, decidirVale,
  muestrearVale, obtenerCatalogos, obtenerVales, reagitarVale, transferirVale,
  type CatalogosEstandarizacion, type ValeEstandarizacion,
} from "../../services/estandarizacion.service";
import { obtenerProductos, type Producto } from "../../services/produccion.service";
import { obtenerSilos, type Silo } from "../../services/recepcion.service";
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
  const [silos, setSilos] = useState<Silo[]>([]);
  const [valeId, setValeId] = useState<number | null>(null);
  const [nuevoAbierto, setNuevoAbierto] = useState(false);
  const [muestra, setMuestra] = useState({ grasa: "", sng: "" });
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
      void obtenerCatalogos().then(setCatalogos).catch(() => setCatalogos(null));
      void obtenerProductos().then(setProductos).catch(() => setProductos([]));
      void obtenerSilos().then(setSilos).catch(() => setSilos([]));
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
          <p className="mt-1 max-w-2xl text-sm text-slate-500">
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
              onClick={() => setNuevoAbierto(true)}
              className="flex items-center gap-2 rounded-xl bg-emerald-700 px-4 py-2.5 text-sm font-medium text-white"
            >
              <Plus className="h-4 w-4" />
              Nuevo vale
            </button>
          )}
        </div>
      </header>

      {error && <Aviso>{error}</Aviso>}

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
            <p className="mt-4 text-sm text-slate-500">{texto}</p>
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
                onClick={() => setValeId(item.id)}
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
                <p className="mt-1 text-xs text-slate-500">
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
          onCerrar={() => setNuevoAbierto(false)}
          onCalcular={calcularMezcla}
          onGuardar={async (datos) => {
            const creado = await crearVale(datos);
            setNuevoAbierto(false);
            await cargar();
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
      <p className="text-xs text-slate-500">{etiqueta}</p>
      <p className="mt-1 text-lg font-semibold text-slate-900">{valor}</p>
      {pie && <p className="mt-0.5 text-xs text-slate-400">{pie}</p>}
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
