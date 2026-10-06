import { useCallback, useEffect, useId, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { ArrowRight, Beaker, Factory, X } from "lucide-react";

import EstadoEquipo from "../../components/EstadoEquipo/EstadoEquipo";
import ConfirmarAccion, { type FilaResumen } from "../../components/operacion/ConfirmarAccion";
import {
  confirmarBorradorLote,
  crearBorradorLote,
  descartarBorradorLote,
  guardarBorradorLote,
  obtenerBorradorLote,
  obtenerOpcionesInicioProduccion,
  sugerirCodigoLote,
  type BorradorLote,
  type DatosBorradorLote,
  type EquipoInicioProduccion,
  type ValeDisponible,
} from "../../services/produccion.service";
import {
  obtenerEjecucionesOperativas,
  type DestinoConcentrado,
  type EjecucionOperativa,
} from "../../services/procesos.service";
import { ocupacionesPorEquipo } from "../../services/disponibilidad-equipos";
import { esErrorDeEquipo, mensajeErrorProceso } from "../../services/errores-proceso";
import { useBorrador } from "../../hooks/useBorrador";
import { cantidad } from "../../services/formato";
import { destinosDelConcentrado } from "../../services/puesto-evaporacion";


/*
  Apertura de un proceso de producción.

  El lote se abre cuando la corrida empieza, no cuando termina. Por eso aquí
  no se piden los kilos: se declaran al marcar el lote como producido, que es
  cuando se saben. Exigirlos al abrir obligaba a registrar el lote al final
  del día, y con él toda su trazabilidad — que entonces ya era documentación
  retroactiva.

  La leche se selecciona por su vale liberado. El vale trae los silos y el RC
  desde Estandarización; Producción no vuelve a escoger ese origen.

  El código identifica la corrida, no el producto: CCAA + año + día juliano +
  sigla del equipo + correlativo del día (p. ej. CCAA6232E1-01). Queda
  editable: el histórico de planta trae códigos con otra forma y hay que
  poder registrarlos.

  Los parámetros de calidad no están aquí: se miden sobre el producto
  terminado, así que se cargan desde la ficha del lote una vez cerrada la
  producción. Pedirlos al abrir invita a rellenarlos con lo que se espera en
  vez de con lo que se midió.
*/

interface Props {
  alCerrar: () => void;
  alGuardar: () => void;
  /* "evaporacion": el formulario se abre desde el puesto de Evaporación,
     sobre un evaporador ya elegido. "resto" (por defecto): el camino actual
     desde Producción, que ahora excluye los evaporadores — se abren en su
     propio puesto. */
  modo?: "evaporacion" | "resto";
  equipoInicial?: number;
  destinos?: DestinoConcentrado[];
}


const hoy = () => new Date().toISOString().slice(0, 10);

/*
  Ruta de producto → tipo de máquina. Vive a nivel de módulo porque
  `reanudarBorrador` necesita evaluarla contra el vale que guardó el
  borrador, antes de que el cuerpo del componente recalcule sus valores
  derivados para el render.
*/
const RUTA_POR_FAMILIA: Record<string, { ruta: string; tipos: string[]; ayuda: string }> = {
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

/*
  Mismo filtro de máquinas en los dos lugares que lo necesitan: el que pinta
  el desplegable y el que valida, al reanudar un borrador, si la máquina que
  quedó guardada todavía es válida para el modo y el vale actuales. Una sola
  función evita que las dos reglas se desalineen — que es justo el defecto
  que se corrige aquí: un borrador cruzado entre Producción y el puesto de
  Evaporación podía confirmarse con una máquina que el modo actual ya no
  ofrece.
*/
function equiposCompatiblesDe(
  equipos: EquipoInicioProduccion[],
  modo: "evaporacion" | "resto",
  familia: string | undefined,
): EquipoInicioProduccion[] {
  const ruta = familia ? RUTA_POR_FAMILIA[familia] : null;
  return equipos.filter((item) => {
    if (!item.activo) return false;
    if (modo === "evaporacion") return item.tipo === "evaporador";
    return item.tipo !== "evaporador" && (!ruta || ruta.tipos.includes(item.tipo));
  });
}


function FormularioLote({ alCerrar, alGuardar, modo = "resto", equipoInicial, destinos = [] }: Props) {

  const [codigoLote, setCodigoLote] = useState("");
  const [fecha, setFecha] = useState(hoy());
  const [op, setOp] = useState("");
  const [orden, setOrden] = useState("");
  const [linea, setLinea] = useState("");
  const [equipo, setEquipo] = useState(equipoInicial ? String(equipoInicial) : "");
  const [turno, setTurno] = useState("");
  const [observacion, setObservacion] = useState("");
  const [siloDestino, setSiloDestino] = useState("");
  const [paso, setPaso] = useState<"datos" | "resumen">("datos");
  /* Distingue un borrador recién reanudado para avisar, solo en ese caso,
     que la disponibilidad del silo de destino pudo cambiar desde que se
     guardó. */
  const [vieneDeBorrador, setVieneDeBorrador] = useState(false);
  const idLinea = useId();
  const idSiloDestino = useId();
  const idSiloDestinoAyuda = useId();

  /* Una vez que el operador escribe el código, la sugerencia deja de pisarlo:
     lo que escribió a mano gana. */
  const [codigoEditado, setCodigoEditado] = useState(false);
  const codigoEditadoRef = useRef(false);
  const [notaCodigo, setNotaCodigo] = useState("");

  const [vales, setVales] = useState<ValeDisponible[]>([]);
  const [vale, setVale] = useState("");
  const [litros, setLitros] = useState("");
  const [equipos, setEquipos] = useState<EquipoInicioProduccion[]>([]);
  const [ejecuciones, setEjecuciones] = useState<EjecucionOperativa[]>([]);
  const [ordenes, setOrdenes] = useState<Awaited<ReturnType<typeof obtenerOpcionesInicioProduccion>>["ordenes"]>([]);

  const [guardando, setGuardando] = useState(false);
  /* `error` es del paso de datos: validación y autoguardado. `errorEnvio` es
     del resumen y solo lo ve `ConfirmarAccion`; separarlos evita que un
     aviso de autoguardado ya resuelto se vea «colgado» en la pantalla de
     confirmación, o que un rechazo de la confirmación aparezca en un paso
     que el operador ya dejó atrás. */
  const [error, setError] = useState("");
  const [errorEnvio, setErrorEnvio] = useState("");
  const [tocado, setTocado] = useState(false);
  const [borradorPendiente, setBorradorPendiente] = useState<BorradorLote | null>(null);
  const [descartando, setDescartando] = useState(false);
  const [errorBorrador, setErrorBorrador] = useState("");

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
    activo: tocado && borradorPendiente === null,
    crear: crearBorradorLote,
    actualizar: guardarBorradorLote,
    alError: (error) => setError(mensajeErrorProceso(error, "No se pudo autoguardar el borrador.")),
  });
  const { reanudar } = borrador;

  useEffect(() => {
    let vigente = true;
    void obtenerBorradorLote().then((guardado) => {
      if (!vigente) return;
      setBorradorPendiente(guardado);
    }).catch(() => {
      if (vigente) setError("No se pudo consultar el borrador.");
    });
    return () => { vigente = false; };
  }, []);

  /* «Continuar» y «Descartar» son dos botones explícitos, no un diálogo nativo:
     un `window.confirm` pone la opción destructiva en «Cancelar», que es la
     tecla por defecto y la que gana el foco — justo al revés de lo que debería
     costar más confirmar. */
  const reanudarBorrador = (guardado: BorradorLote) => {
    setCodigoLote(guardado.codigo_lote_propuesto);
    setCodigoEditado(Boolean(guardado.codigo_lote_propuesto));
    setVale(guardado.vale == null ? "" : String(guardado.vale));
    setLitros(
      guardado.litros_estandarizados_borrador == null
        ? "" : String(guardado.litros_estandarizados_borrador)
    );

    /* El borrador es uno por usuario y lo comparten los dos caminos que
       abren un lote: Producción y el puesto de Evaporación. Si lo que
       quedó guardado no es válido para el modo o el vale con que se
       reanuda — un evaporador en "resto", o cualquier otra máquina en
       "evaporacion" —, se descarta en vez de arrastrarlo: de lo contrario
       viajaría intacto hasta `confirmar-borrador/` sin pasar nunca por el
       filtro del desplegable. */
    const valeGuardado = vales.find((item) => item.id === guardado.vale);
    const compatiblesDelBorrador = equiposCompatiblesDe(equipos, modo, valeGuardado?.producto_familia);
    const equipoValido = guardado.equipo != null
      && compatiblesDelBorrador.some((item) => item.id === guardado.equipo);
    const equipoFinal = equipoValido ? String(guardado.equipo) : (equipoInicial ? String(equipoInicial) : "");
    fijarEquipo(equipoFinal, compatiblesDelBorrador);
    /* `fijarEquipo` ya soltó la línea si la máquina final no es una torre;
       solo si lo es tiene sentido restaurar la que trajo el borrador. */
    const equipoFinalEsTorre = compatiblesDelBorrador.find((item) => String(item.id) === equipoFinal)?.tipo === "torre";
    if (equipoFinalEsTorre) setLinea(guardado.linea);
    setSiloDestino("");
    setVieneDeBorrador(true);

    setOrden(guardado.orden == null ? "" : String(guardado.orden));
    setFecha(guardado.fecha);
    setOp(guardado.op);
    setTurno(guardado.turno);
    setObservacion(guardado.observacion);
    reanudar(guardado.id);
    setBorradorPendiente(null);
  };

  const descartarPendiente = async () => {
    if (!borradorPendiente || descartando) return;
    setErrorBorrador("");
    setDescartando(true);
    try {
      await descartarBorradorLote(borradorPendiente.id);
      setBorradorPendiente(null);
    } catch (error) {
      setErrorBorrador(mensajeErrorProceso(error, "No se pudo descartar el borrador."));
      setDescartando(false);
    }
  };

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

      /* La petición puede haber comenzado antes de que el operador escribiera.
         Se consulta el ref al resolver para no sobrescribir su código con una
         sugerencia tardía. */
      if (!codigoEditadoRef.current) {
        setCodigoLote(sugerencia.codigo ?? "");
        setNotaCodigo(sugerencia.motivo ?? "");
      }
    } catch {
      // Sin sugerencia el campo queda libre: se escribe a mano.
      setNotaCodigo("");
    }
  }, [equipo, fecha, codigoEditado]);

  useEffect(() => {
    const temporizador = setTimeout(sugerir, 0);

    return () => clearTimeout(temporizador);
  }, [sugerir]);

  const revisar = (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    if (guardando) return;

    if (esEvaporador && !siloDestino) {
      setError("Elige el silo de destino del concentrado.");
      return;
    }

    setError("");
    setPaso("resumen");
  };

  const confirmarEnvio = async () => {
    if (guardando) return;

    setErrorEnvio("");
    setGuardando(true);

    try {

      const borradorId = await borrador.guardarAhora({ propagarError: true });
      if (borradorId === null) throw new Error("El borrador no alcanzó a guardarse.");
      await confirmarBorradorLote(borradorId, esEvaporador ? Number(siloDestino) : undefined);
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
      setErrorEnvio(mensaje);

      setGuardando(false);

    }
  };

  const etiquetaCampo = "mb-1.5 block text-sm font-medium text-slate-700";
  const campo =
    "w-full rounded-xl border border-slate-300 bg-white px-4 py-3 outline-none focus:border-green-600";
  const valeSeleccionado = vales.find((item) => item.id === Number(vale));
  const ruta = valeSeleccionado ? RUTA_POR_FAMILIA[valeSeleccionado.producto_familia] : null;
  /* En el puesto de Evaporación el formulario solo ofrece evaporadores; en
     el resto se excluyen, porque esos lotes se abren desde su propio puesto. */
  const equiposCompatibles = equiposCompatiblesDe(equipos, modo, valeSeleccionado?.producto_familia);
  /* Mismo criterio sobre los vales: en evaporación solo los que van a un
     evaporador; en el resto, la familia polvo se excluye porque esa leche
     solo va a evaporador. */
  const valesVisibles = vales.filter((item) => {
    if (modo === "evaporacion") return RUTA_POR_FAMILIA[item.producto_familia]?.tipos.includes("evaporador") ?? false;
    return item.producto_familia !== "polvo";
  });
  const ocupaciones = ocupacionesPorEquipo(ejecuciones);
  /* De `equiposCompatibles`, no de la lista completa: así una máquina que el
     modo actual no ofrece —un evaporador en "resto", cualquier otra cosa en
     "evaporacion"— nunca queda "seleccionada" aunque el estado `equipo`
     arrastre un id inválido (lo que `reanudarBorrador` ya evita, pero esta
     es la garantía que no depende de que ese otro camino esté siempre
     impecable). */
  const equipoSeleccionado = equiposCompatibles.find((item) => item.id === Number(equipo));
  const ocupacionSeleccionada = equipoSeleccionado
    ? ocupaciones.get(equipoSeleccionado.id)
    : undefined;
  const ordenesCompatibles = ordenes.filter((item) => item.producto === valeSeleccionado?.producto);
  const advertenciaAseo = equipoSeleccionado?.advertencia_aseo ?? "";
  const esEvaporador = equipoSeleccionado?.tipo === "evaporador";
  const esTorre = equipoSeleccionado?.tipo === "torre";
  const soloHayEvaporadores = modo === "resto"
    && valeSeleccionado?.producto_familia === "liquido"
    && equiposCompatibles.length === 0;
  /* El silo del que el lote saca la leche no se ofrece como destino: la
     corrida lo rechazaría (`CorridaCondensacion.clean`, origen == destino). */
  const destinosOfrecidos = destinosDelConcentrado(destinos, valeSeleccionado?.silo_destino_codigo);
  const destinoSeleccionado = destinosOfrecidos.find((item) => String(item.id) === siloDestino);
  const titulo = modo === "evaporacion" ? "Abrir lote y preparar evaporación" : "Abrir lote desde vale";
  /* Solo tiene sentido mientras el destino sigue sin elegirse: en cuanto el
     operador escoge uno, ya no es "lo que quedó del borrador". */
  const avisoSiloDestino = vieneDeBorrador && !siloDestino;

  /* Fija el equipo y, en el mismo gesto, la línea que le corresponde: si la
     máquina elegida no es una torre, la línea no tiene nada que decir y se
     suelta ahí mismo — no en un efecto que la corrija después del render,
     porque eso es un segundo paso reactivo para algo que ya se sabe en el
     momento del cambio. */
  const fijarEquipo = (id: string, compatibles: EquipoInicioProduccion[]) => {
    setEquipo(id);
    const elegido = compatibles.find((item) => String(item.id) === id);
    if (elegido?.tipo !== "torre") setLinea("");
  };

  /* Mismo criterio con el silo de destino: si los litros que se escriben ya
     no caben en el que estaba elegido, se suelta en el propio cambio de
     litros, sea que venga del campo de litros o de un vale que trae los
     suyos. */
  const litrosCambian = (valor: string) => {
    setLitros(valor);
    if (!siloDestino) return;
    const litrosNumero = valor === "" ? null : Number(valor);
    if (litrosNumero === null) return;
    const destino = destinos.find((item) => String(item.id) === siloDestino);
    if (destino && Number(destino.libre_l) < litrosNumero) setSiloDestino("");
  };

  const filasResumen = (): FilaResumen[] => [
    { etiqueta: "Vale", valor: valeSeleccionado ? `${valeSeleccionado.codigo} · ${valeSeleccionado.producto_nombre}` : "—" },
    { etiqueta: "Máquina", valor: equipoSeleccionado ? `${equipoSeleccionado.nombre} · ${equipoSeleccionado.tipo_etiqueta}` : "—" },
    { etiqueta: "Orden", valor: ordenes.find((item) => item.id === Number(orden))?.codigo ?? "—" },
    {
      etiqueta: "Origen → destino",
      valor: valeSeleccionado
        ? `${valeSeleccionado.silo_entera_codigo}` +
          `${valeSeleccionado.silo_descremada_codigo ? ` + ${valeSeleccionado.silo_descremada_codigo}` : ""}` +
          ` → ${esEvaporador ? (destinoSeleccionado?.codigo ?? "—") : valeSeleccionado.silo_destino_codigo}`
        : "—",
    },
    { etiqueta: "Código de lote", valor: codigoLote },
    { etiqueta: "Litros", valor: cantidad(litros, "L") },
  ];

  return (
    <div className="fixed inset-0 z-50 flex items-start justify-center overflow-y-auto bg-slate-900/40 p-4 sm:p-8">

      <div className="w-full max-w-3xl rounded-2xl bg-white shadow-xl">

        <div className="flex items-center justify-between border-b border-slate-200 px-6 py-5">

          <div>

            <h2 className="text-lg font-semibold text-slate-800">

              {titulo}

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

        {borradorPendiente ? (
          <div className="px-6 py-6">
            <div className="rounded-2xl border border-amber-200 bg-amber-50 p-6">
              <h3 className="font-semibold text-amber-950">Tienes un lote sin abrir</h3>
              <p className="mt-2 text-sm leading-6 text-amber-900">
                Se guardó automáticamente el {new Intl.DateTimeFormat("es-CL", {
                  dateStyle: "short", timeStyle: "short",
                }).format(new Date(borradorPendiente.actualizado_en))}. Puedes continuarlo
                o descartarlo. No ha abierto el proceso ni descontado leche.
              </p>
              {errorBorrador && (
                <div className="mt-4 rounded-xl bg-red-50 px-4 py-3 text-sm text-red-700">
                  {errorBorrador}
                </div>
              )}
              <div className="mt-5 flex flex-wrap gap-3">
                <button
                  type="button"
                  autoFocus
                  disabled={descartando}
                  onClick={() => reanudarBorrador(borradorPendiente)}
                  className="h-10 rounded-xl bg-amber-700 px-5 text-sm font-semibold text-white hover:bg-amber-800 disabled:cursor-not-allowed disabled:opacity-60"
                >
                  Continuar borrador
                </button>
                <button
                  type="button"
                  disabled={descartando}
                  onClick={descartarPendiente}
                  className="h-10 rounded-xl border border-red-300 px-5 text-sm font-semibold text-red-800 hover:bg-red-50 disabled:cursor-not-allowed disabled:opacity-60"
                >
                  {descartando ? "Descartando…" : "Descartar borrador"}
                </button>
                <button type="button" onClick={alCerrar} className="h-10 px-4 text-sm font-semibold text-slate-600">Cerrar</button>
              </div>
            </div>
          </div>
        ) : paso === "resumen" ? (
          <div className="px-6 py-6">
            <ConfirmarAccion
              titulo="Revisa antes de abrir el lote"
              filas={filasResumen()}
              textoConfirmar={guardando ? "Abriendo…" : "Abrir lote"}
              ocupado={guardando}
              error={errorEnvio}
              onConfirmar={() => void confirmarEnvio()}
              onVolver={() => { setPaso("datos"); setErrorEnvio(""); }}
            />
          </div>
        ) : (
        <form
          onSubmit={revisar}
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
                  /* El destino elegido puede ser justo el silo del nuevo vale,
                     que ya no se ofrece: se suelta en el mismo cambio. */
                  if (siloDestino && !destinosDelConcentrado(destinos, elegido?.silo_destino_codigo)
                    .some((item) => String(item.id) === siloDestino)) setSiloDestino("");

                  /* En el puesto de Evaporación la máquina viene elegida desde
                     la tarjeta: cambiar de vale no debe soltarla si sigue
                     siendo compatible. En el resto, el tipo de máquina
                     depende de la familia del vale, así que corresponde
                     volver a elegir. */
                  const compatiblesDelNuevoVale = equiposCompatiblesDe(equipos, modo, elegido?.producto_familia);
                  if (modo === "evaporacion") {
                    const sigueSiendoValida = compatiblesDelNuevoVale.some((item) => String(item.id) === equipo);
                    fijarEquipo(sigueSiendoValida ? equipo : (equipoInicial ? String(equipoInicial) : ""), compatiblesDelNuevoVale);
                  } else {
                    fijarEquipo("", compatiblesDelNuevoVale);
                  }

                  setOrden("");
                  litrosCambian(elegido?.litros_disponibles ?? "");
                }}
                required
              >

                <option value="">Selecciona un vale con saldo…</option>

                {valesVisibles.map((item) => (

                  <option key={item.id} value={item.id}>

                    {item.codigo} · {item.producto_nombre} · {cantidad(item.litros_disponibles, "L")}

                  </option>

                ))}

              </select>

              {valesVisibles.length === 0 && (
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
              {soloHayEvaporadores && (
                <p className="mt-2 text-xs text-amber-700">
                  Los productos que van a evaporador se abren en el puesto de Evaporación.{" "}
                  <Link to="/produccion/evaporacion" className="font-medium underline">Ir al puesto de Evaporación</Link>
                </p>
              )}

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

            {esTorre && (
              <div>

                <label htmlFor={idLinea} className={etiquetaCampo}>Línea *</label>

                <select
                  id={idLinea}
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
            )}

            <div className="sm:col-span-2">

              <label className={etiquetaCampo}>Máquina / equipo *</label>

              <select
                className={campo}
                value={equipo}
                onChange={(e) => fijarEquipo(e.target.value, equiposCompatibles)}
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
              {valeSeleccionado && equiposCompatibles.length === 0 && !soloHayEvaporadores && <p className="mt-1.5 text-xs text-amber-700">No hay una máquina activa configurada para esta familia. Revísala en Maestros.</p>}
              {advertenciaAseo && <div className="mt-3 rounded-xl border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-800"><strong>Advertencia de aseo (no bloquea):</strong> {advertenciaAseo}</div>}

            </div>

            {esEvaporador && (
              <div className="sm:col-span-2">

                <label htmlFor={idSiloDestino} className={etiquetaCampo}>Silo de destino del concentrado *</label>

                <select
                  id={idSiloDestino}
                  className={campo}
                  value={siloDestino}
                  onChange={(e) => setSiloDestino(e.target.value)}
                  aria-describedby={(destinosOfrecidos.length === 0 || avisoSiloDestino) ? idSiloDestinoAyuda : undefined}
                  required
                >
                  <option value="">Selecciona un silo…</option>
                  {destinosOfrecidos.map((item) => {
                    const litrosNumero = litros === "" ? null : Number(litros);
                    const sinCapacidad = litrosNumero !== null && Number(item.libre_l) < litrosNumero;
                    return (
                      <option key={item.id} value={item.id} disabled={sinCapacidad}>
                        {item.codigo} · libre {cantidad(item.libre_l, "L")}{sinCapacidad ? " · sin capacidad" : ""}
                      </option>
                    );
                  })}
                </select>
                {destinosOfrecidos.length === 0 ? (
                  <p id={idSiloDestinoAyuda} className="mt-1.5 text-xs text-amber-700">
                    No hay silos disponibles para recibir el concentrado.
                  </p>
                ) : avisoSiloDestino ? (
                  <p id={idSiloDestinoAyuda} className="mt-1.5 text-xs text-amber-700">
                    Vuelve a elegir el silo de destino: la disponibilidad pudo cambiar.
                  </p>
                ) : null}

              </div>
            )}

            <div className="sm:col-span-2">

              <label className={etiquetaCampo}>Código de lote *</label>

              <input
                className={campo}
                value={codigoLote}
                onChange={(e) => {
                  codigoEditadoRef.current = true;
                  setCodigoLote(e.target.value);
                  setCodigoEditado(true);
                }}
                placeholder="CCAA6232E1-01"
                required
              />

              <p className="mt-1.5 text-xs text-slate-600">

                {notaCodigo ||
                  "Se propone con el año, el día juliano, la sigla del equipo " +
                    "y el correlativo del día. Identifica la corrida, no el " +
                    "producto, y se puede cambiar."}

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
                  onChange={(e) => litrosCambian(e.target.value)}
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
                  Vale {valeSeleccionado.codigo} · RC objetivo {cantidad(valeSeleccionado.rc_objetivo, undefined, 4)}
                  {valeSeleccionado.rc_real != null
                    ? ` · RC liberado ${cantidad(valeSeleccionado.rc_real, undefined, 4)}`
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
              disabled={Boolean(ocupacionSeleccionada) || !equipoSeleccionado?.habilitado}
              className="rounded-xl bg-green-700 px-6 py-3 text-sm font-semibold text-white hover:bg-green-800 disabled:opacity-60"
            >

              Revisar

            </button>

          </div>

        </form>
        )}

      </div>

    </div>
  );
}


export default FormularioLote;
