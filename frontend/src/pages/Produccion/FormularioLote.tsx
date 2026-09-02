import { useCallback, useEffect, useState } from "react";
import { ArrowRight, Beaker, Factory, X } from "lucide-react";

import EstadoEquipo from "../../components/EstadoEquipo/EstadoEquipo";
import {
  confirmarBorradorLote,
  crearBorradorLote,
  descartarBorradorLote,
  guardarBorradorLote,
  obtenerBorradorLote,
  obtenerOpcionesInicioProduccion,
  sugerirCodigoLote,
  type DatosBorradorLote,
  type EquipoInicioProduccion,
  type ValeDisponible,
} from "../../services/produccion.service";
import { obtenerEjecucionesOperativas, type EjecucionOperativa } from "../../services/procesos.service";
import { ocupacionesPorEquipo } from "../../services/disponibilidad-equipos";
import { esErrorDeEquipo, mensajeErrorProceso } from "../../services/errores-proceso";
import { useBorrador } from "../../hooks/useBorrador";


/*
  Apertura de un proceso de producción.

  El lote se abre cuando la corrida empieza, no cuando termina. Por eso aquí
  no se piden los kilos: se declaran al marcar el lote como producido, que es
  cuando se saben. Exigirlos al abrir obligaba a registrar el lote al final
  del día, y con él toda su trazabilidad — que entonces ya era documentación
  retroactiva.

  La leche se selecciona por su vale liberado. El vale trae los silos y el RC
  desde Estandarización; Producción no vuelve a escoger ese origen.

  El código se compone del año, el día juliano, el SKU del producto y el
  correlativo del día, y queda editable: el histórico de planta trae códigos
  con otra forma y hay que poder registrarlos.

  Los parámetros de calidad no están aquí: se miden sobre el producto
  terminado, así que se cargan desde la ficha del lote una vez cerrada la
  producción. Pedirlos al abrir invita a rellenarlos con lo que se espera en
  vez de con lo que se midió.
*/

interface Props {
  alCerrar: () => void;
  alGuardar: () => void;
}


const hoy = () => new Date().toISOString().slice(0, 10);


function FormularioLote({ alCerrar, alGuardar }: Props) {

  const [codigoLote, setCodigoLote] = useState("");
  const [fecha, setFecha] = useState(hoy());
  const [op, setOp] = useState("");
  const [orden, setOrden] = useState("");
  const [linea, setLinea] = useState("");
  const [equipo, setEquipo] = useState("");
  const [turno, setTurno] = useState("");
  const [observacion, setObservacion] = useState("");

  /* Una vez que el operador escribe el código, la sugerencia deja de pisarlo:
     lo que escribió a mano gana. */
  const [codigoEditado, setCodigoEditado] = useState(false);
  const [notaCodigo, setNotaCodigo] = useState("");

  const [vales, setVales] = useState<ValeDisponible[]>([]);
  const [vale, setVale] = useState("");
  const [litros, setLitros] = useState("");
  const [equipos, setEquipos] = useState<EquipoInicioProduccion[]>([]);
  const [ejecuciones, setEjecuciones] = useState<EjecucionOperativa[]>([]);
  const [ordenes, setOrdenes] = useState<Awaited<ReturnType<typeof obtenerOpcionesInicioProduccion>>["ordenes"]>([]);

  const [guardando, setGuardando] = useState(false);
  const [error, setError] = useState("");
  const [tocado, setTocado] = useState(false);

  const numeroONull = (valor: string) => valor === "" ? null : Number(valor);
  const datosBorrador: DatosBorradorLote = {
    codigo_lote_propuesto: codigoLote,
    vale: numeroONull(vale),
    litros_estandarizados_borrador: numeroONull(litros),
    equipo: numeroONull(equipo),
    orden: numeroONull(orden),
    fecha,
    op,
    linea,
    turno,
    observacion,
  };
  const borrador = useBorrador({
    datos: datosBorrador,
    activo: tocado,
    crear: crearBorradorLote,
    actualizar: guardarBorradorLote,
    alError: () => setError("No se pudo autoguardar el borrador."),
  });
  const { reanudar } = borrador;

  useEffect(() => {
    let vigente = true;
    void obtenerBorradorLote().then(async (guardado) => {
      if (!vigente || !guardado) return;
      if (!window.confirm("Tienes un lote sin abrir. ¿Quieres continuarlo?")) {
        await descartarBorradorLote(guardado.id);
        return;
      }
      setCodigoLote(guardado.codigo_lote_propuesto);
      setCodigoEditado(Boolean(guardado.codigo_lote_propuesto));
      setVale(guardado.vale == null ? "" : String(guardado.vale));
      setLitros(
        guardado.litros_estandarizados_borrador == null
          ? "" : String(guardado.litros_estandarizados_borrador)
      );
      setEquipo(guardado.equipo == null ? "" : String(guardado.equipo));
      setOrden(guardado.orden == null ? "" : String(guardado.orden));
      setFecha(guardado.fecha);
      setOp(guardado.op);
      setLinea(guardado.linea);
      setTurno(guardado.turno);
      setObservacion(guardado.observacion);
      reanudar(guardado.id);
    }).catch(() => {
      if (vigente) setError("No se pudo consultar el borrador.");
    });
    return () => { vigente = false; };
  }, [reanudar]);

  useEffect(() => {
    obtenerOpcionesInicioProduccion()
      .then((opciones) => {
        setVales(opciones.entradas);
        setEquipos(opciones.equipos);
        setOrdenes(opciones.ordenes);
      })
      .catch(() => {
        setVales([]);
        setEquipos([]);
        setOrdenes([]);
      });
    obtenerEjecucionesOperativas().then(setEjecuciones).catch(() => setEjecuciones([]));
  }, []);

  const sugerir = useCallback(async () => {
    if (!equipo || !fecha || codigoEditado) {
      return;
    }

    try {
      const sugerencia = await sugerirCodigoLote(Number(equipo), fecha);

      setCodigoLote(sugerencia.codigo ?? "");
      setNotaCodigo(sugerencia.motivo ?? "");
    } catch {
      // Sin sugerencia el campo queda libre: se escribe a mano.
      setNotaCodigo("");
    }
  }, [equipo, fecha, codigoEditado]);

  useEffect(() => {
    const temporizador = setTimeout(sugerir, 0);

    return () => clearTimeout(temporizador);
  }, [sugerir]);

  const enviar = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    if (guardando) return;

    setError("");
    setGuardando(true);

    try {

      const borradorId = await borrador.guardarAhora({ propagarError: true });
      if (borradorId === null) throw new Error("El borrador no alcanzó a guardarse.");
      await confirmarBorradorLote(borradorId);
      borrador.reiniciar();

      alGuardar();
      alCerrar();

    } catch (error) {

      const mensaje = mensajeErrorProceso(error, "No se pudo abrir el proceso o conectar con el servidor.");
      if (esErrorDeEquipo(error)) {
        try {
          setEjecuciones(await obtenerEjecucionesOperativas());
        } catch {
          // Se conserva el rechazo original; la disponibilidad podrá actualizarse al reabrir.
        }
      }
      setError(mensaje);

      setGuardando(false);

    }
  };

  const etiquetaCampo = "mb-1.5 block text-sm font-medium text-slate-700";
  const campo =
    "w-full rounded-xl border border-slate-300 bg-white px-4 py-3 outline-none focus:border-green-600";
  const valeSeleccionado = vales.find((item) => item.id === Number(vale));
  const rutaPorFamilia: Record<string, { ruta: string; tipos: string[]; ayuda: string }> = {
    polvo: {
      ruta: "Leche estandarizada → Evaporación → Torre Egron → Envasado 25 kg",
      tipos: ["evaporador"],
      ayuda: "Esta apertura inicia la evaporación. La torre Egron aparecerá después, únicamente cuando Calidad libere el concentrado.",
    },
    liquido: {
      ruta: "Leche estandarizada → Evaporación / concentración → Producto a granel",
      tipos: ["evaporador", "carga"],
      ayuda: "Selecciona el evaporador o punto de carga que ejecuta esta corrida.",
    },
    crema: {
      ruta: "Leche estandarizada → Separación / proceso → Envasado o granel",
      tipos: ["linea", "envasadora"],
      ayuda: "Selecciona solo la línea o envasadora de crema correspondiente.",
    },
    otro: {
      ruta: "Proceso definido para el producto → Envasado",
      tipos: ["linea", "envasadora", "carga"],
      ayuda: "Selecciona la máquina final definida para este producto.",
    },
  };
  const ruta = valeSeleccionado ? rutaPorFamilia[valeSeleccionado.producto_familia] : null;
  const equiposCompatibles = equipos.filter(
    (item) => item.activo && (!ruta || ruta.tipos.includes(item.tipo)),
  );
  const ocupaciones = ocupacionesPorEquipo(ejecuciones);
  const equipoSeleccionado = equipos.find((item) => item.id === Number(equipo));
  const ocupacionSeleccionada = equipoSeleccionado
    ? ocupaciones.get(equipoSeleccionado.id)
    : undefined;
  const ordenesCompatibles = ordenes.filter((item) => item.producto === valeSeleccionado?.producto);
  const advertenciaAseo = equipoSeleccionado?.advertencia_aseo ?? "";

  return (
    <div className="fixed inset-0 z-50 flex items-start justify-center overflow-y-auto bg-slate-900/40 p-4 sm:p-8">

      <div className="w-full max-w-3xl rounded-2xl bg-white shadow-xl">

        <div className="flex items-center justify-between border-b border-slate-200 px-6 py-5">

          <div>

            <h2 className="text-lg font-semibold text-slate-800">

              Abrir proceso de producción

            </h2>

            <p className="mt-0.5 text-sm text-slate-600">

              El lote queda en proceso. Los kilos se declaran al cerrarlo.

            </p>

          </div>

          <button
            type="button"
            onClick={alCerrar}
            className="rounded-lg p-1 text-slate-600 hover:bg-slate-100 hover:text-slate-700"
            aria-label="Cerrar"
          >

            <X className="h-5 w-5" />

          </button>

        </div>

        <form
          onSubmit={enviar}
          onChange={() => setTocado(true)}
          className="px-6 py-6"
        >

          <div className="grid grid-cols-1 gap-5 sm:grid-cols-3">

            <div className="sm:col-span-2">

              <label className={etiquetaCampo}>Vale estandarizado liberado *</label>

              <select
                className={campo}
                value={vale}
                onChange={(e) => {
                  const id = e.target.value;
                  const elegido = vales.find((item) => item.id === Number(id));
                  setVale(id);
                  setEquipo("");
                  setOrden("");
                  setLitros(elegido?.litros_disponibles ?? "");
                }}
                required
              >

                <option value="">Selecciona un vale con saldo…</option>

                {vales.map((item) => (

                  <option key={item.id} value={item.id}>

                    {item.codigo} · {item.producto_nombre} · {Number(item.litros_disponibles).toLocaleString("es-CL")} L

                  </option>

                ))}

              </select>

              {vales.length === 0 && (
                <p className="mt-1.5 text-xs text-amber-700">
                  No hay vales liberados con saldo. Libera uno en Estandarización.
                </p>
              )}
              {valeSeleccionado && (
                <p className="mt-2 text-sm text-slate-700">
                  Producto definido por el vale: <strong>{valeSeleccionado.producto_nombre}</strong>
                  {` · ${valeSeleccionado.mandante_nombre}`}
                </p>
              )}
              {ruta && <div className="mt-3 rounded-xl border border-blue-200 bg-blue-50 px-3 py-2 text-xs text-blue-800"><strong>Ruta del producto:</strong> {ruta.ruta}<br />{ruta.ayuda}</div>}

            </div>

            <div>

              <label className={etiquetaCampo}>Fecha *</label>

              <input
                type="date"
                className={campo}
                value={fecha}
                onChange={(e) => setFecha(e.target.value)}
                required
              />

            </div>

            <div>

              <label className={etiquetaCampo}>Línea *</label>

              <select
                className={campo}
                value={linea}
                onChange={(e) => setLinea(e.target.value)}
                required
              >

                <option value="">—</option>
                <option value="E1">E1</option>
                <option value="E2">E2</option>

              </select>

            </div>

            <div className="sm:col-span-2">

              <label className={etiquetaCampo}>Máquina / equipo *</label>

              <select
                className={campo}
                value={equipo}
                onChange={(e) => setEquipo(e.target.value)}
                required
              >
                <option value="">Selecciona una máquina…</option>
                {equiposCompatibles.map((item) => (
                  <option key={item.id} value={item.id} disabled={!item.habilitado || ocupaciones.has(item.id)}>
                    {item.nombre} · {item.tipo_etiqueta}{ocupaciones.has(item.id) ? ` · ${ocupaciones.get(item.id)?.disponibilidad} por ${ocupaciones.get(item.id)?.ejecucion}` : item.motivo_no_habilitado ? ` · ${item.motivo_no_habilitado}` : " · disponible"}
                  </option>
                ))}
              </select>
              {equipoSeleccionado && <div className="mt-2"><EstadoEquipo estado={ocupacionSeleccionada?.estado} ejecucion={ocupacionSeleccionada?.ejecucion} /></div>}
              {valeSeleccionado && equiposCompatibles.length === 0 && <p className="mt-1.5 text-xs text-amber-700">No hay una máquina activa configurada para esta familia. Revísala en Maestros.</p>}
              {advertenciaAseo && <div className="mt-3 rounded-xl border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-800"><strong>Advertencia de aseo (no bloquea):</strong> {advertenciaAseo}</div>}

            </div>

            <div className="sm:col-span-2">

              <label className={etiquetaCampo}>Código de lote *</label>

              <input
                className={campo}
                value={codigoLote}
                onChange={(e) => {
                  setCodigoLote(e.target.value);
                  setCodigoEditado(true);
                }}
                placeholder="CCAA6197LEP25-01"
                required
              />

              <p className="mt-1.5 text-xs text-slate-600">

                {notaCodigo ||
                  "Se propone con el año, el día juliano, el SKU del producto " +
                    "y el correlativo del día. Se puede cambiar."}

              </p>

            </div>

            <div>

              <label className={etiquetaCampo}>Turno</label>

              <select
                className={campo}
                value={turno}
                onChange={(e) => setTurno(e.target.value)}
              >

                <option value="">—</option>
                <option value="A">A</option>
                <option value="B">B</option>
                <option value="C">C</option>

              </select>

            </div>

            <div className="sm:col-span-2">

              <label className={etiquetaCampo}>Orden de producción *</label>

              <select
                className={campo}
                value={orden}
                onChange={(e) => {
                  const id = e.target.value;
                  const elegida = ordenes.find((item) => item.id === Number(id));
                  setOrden(id);
                  setOp(elegida?.codigo ?? "");
                }}
                required
                disabled={!valeSeleccionado}
              >
                <option value="">Selecciona una OP compatible…</option>
                {ordenesCompatibles.map((item) => <option key={item.id} value={item.id}>
                  {item.codigo} · {item.estado} · {Number(item.cantidad_planificada).toLocaleString("es-CL")} {item.unidad}
                </option>)}
              </select>
              {valeSeleccionado && ordenesCompatibles.length === 0 && <p className="mt-1.5 text-xs text-amber-700">No hay una OP programada para este producto. Créala o prográmala antes de abrir el lote.</p>}

            </div>

          </div>

          {/* Leche estandarizada */}

          <div className="mt-8 border-t border-slate-200 pt-6">

            <h3 className="text-sm font-semibold text-slate-800">

              Leche estandarizada

            </h3>

            <p className="mt-1 mb-5 text-sm text-slate-600">

              Selecciona el vale liberado. Los silos y el RC vienen
              precargados desde Estandarización y no se vuelven a digitar.

            </p>

            <div className="grid gap-4 sm:grid-cols-2">
              <div>
                <label className={etiquetaCampo}>Litros para esta corrida *</label>
                <input
                  type="number"
                  min="0.01"
                  step="0.01"
                  max={valeSeleccionado?.litros_disponibles}
                  className={campo}
                  value={litros}
                  onChange={(e) => setLitros(e.target.value)}
                  required
                  disabled={!valeSeleccionado}
                />
              </div>
            </div>

            {valeSeleccionado && (
              <div className="mt-5 rounded-2xl border border-green-200 bg-green-50/60 p-4">
                <div className="flex flex-wrap items-center gap-2 text-sm text-slate-700">
                  <Beaker className="h-4 w-4 text-green-700" />
                  <span>{valeSeleccionado.silo_entera_codigo}</span>
                  {valeSeleccionado.silo_descremada_codigo && (
                    <span>+ {valeSeleccionado.silo_descremada_codigo}</span>
                  )}
                  <ArrowRight className="h-4 w-4 text-slate-600" />
                  <strong>{valeSeleccionado.silo_destino_codigo}</strong>
                  <ArrowRight className="h-4 w-4 text-slate-600" />
                  <Factory className="h-4 w-4 text-green-700" />
                  <span>Producción</span>
                </div>
                <p className="mt-2 text-xs text-slate-600">
                  Vale {valeSeleccionado.codigo} · RC objetivo {valeSeleccionado.rc_objetivo}
                  {valeSeleccionado.rc_real != null
                    ? ` · RC liberado ${valeSeleccionado.rc_real.toFixed(4)}`
                    : ""}
                  {` · ${Number(valeSeleccionado.litros_disponibles).toLocaleString("es-CL")} L disponibles`}
                </p>
              </div>
            )}

          </div>

          <div className="mt-6">

            <label className={etiquetaCampo}>Observación</label>

            <textarea
              className={campo}
              rows={2}
              value={observacion}
              onChange={(e) => setObservacion(e.target.value)}
            />

          </div>

          {error && (

            <div className="mt-6 rounded-xl bg-red-50 px-4 py-3 text-sm text-red-700">

              {error}

            </div>

          )}

          <div className="mt-8 flex justify-end gap-3">

            <p className="mr-auto self-center text-xs text-slate-500">
              {borrador.estado === "guardando" ? "Guardando borrador…" :
                borrador.estado === "error" ? "No se pudo autoguardar." :
                  borrador.id ? "Borrador guardado. La leche aún no se descuenta." :
                    "Los cambios se guardarán automáticamente."}
            </p>

            <button
              type="button"
              onClick={alCerrar}
              className="rounded-xl px-5 py-3 text-sm font-medium text-slate-600 hover:bg-slate-100"
            >

              Cancelar

            </button>

            <button
              type="submit"
              disabled={guardando || Boolean(ocupacionSeleccionada) || !equipoSeleccionado?.habilitado}
              className="rounded-xl bg-green-700 px-6 py-3 text-sm font-semibold text-white hover:bg-green-800 disabled:opacity-60"
            >

              {guardando ? "Abriendo…" : "Abrir proceso"}

            </button>

          </div>

        </form>

      </div>

    </div>
  );
}


export default FormularioLote;
