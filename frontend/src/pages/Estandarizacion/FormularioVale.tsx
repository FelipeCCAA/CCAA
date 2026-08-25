import { useEffect, useState } from "react";
import { Calculator, CheckCircle2, X } from "lucide-react";

import {
  confirmarBorradorVale, crearBorradorVale, descartarBorradorVale,
  guardarBorradorVale, obtenerBorradorVale,
  type DatosBorradorVale, type EntradaCalculo, type Mezcla,
  type ValeEstandarizacion,
} from "../../services/estandarizacion.service";
import type { Producto } from "../../services/produccion.service";
import type { Silo } from "../../services/recepcion.service";
import { mensajeDe } from "../../components/seccion/utilidades";
import { useBorrador } from "../../hooks/useBorrador";

/*
  Nuevo vale, en dos tiempos: **primero se calcula, después se guarda**.

  El botón de crear no aparece hasta que hay una mezcla posible, y por una
  razón concreta: el cálculo puede decir que **el RC pedido no se alcanza** con
  las dos leches que hay —pasa de verdad, RC 0,422 exige entera de al menos
  ~3,63 % de grasa—. Dejar guardar igual crearía un vale que nadie puede
  cumplir, y el operador lo descubriría después de transferir sesenta mil
  litros.

  El cálculo lo hace el backend. No se reproduce aquí: una segunda
  implementación puede diferir de la que manda, justo en el número con el que
  se abre una válvula.
*/

const hoy = () => new Date().toISOString().slice(0, 10);

const inicial = {
  codigo: "",
  fecha: hoy(),
  producto: "",
  rc_objetivo: "",
  volumen: "",
  silo_entera: "",
  silo_descremada: "",
  silo_destino: "",
  entera_grasa: "",
  entera_sng: "",
  entera_disponible: "",
  descremada_grasa: "",
  descremada_sng: "",
  descremada_disponible: "",
  observaciones: "",
};


function FormularioVale({
  productos,
  silos,
  onCerrar,
  onCalcular,
  onConfirmado,
}: {
  productos: Producto[];
  silos: Silo[];
  onCerrar: () => void;
  onCalcular: (datos: EntradaCalculo) => Promise<Mezcla>;
  onConfirmado: (vale: ValeEstandarizacion) => Promise<void>;
}) {
  const [datos, setDatos] = useState(inicial);
  const [mezcla, setMezcla] = useState<Mezcla | null>(null);
  const [ocupado, setOcupado] = useState(false);
  const [error, setError] = useState("");
  const [tocado, setTocado] = useState(false);

  const numeroONull = (valor: string) => valor === "" ? null : Number(valor);
  const datosBorrador: DatosBorradorVale = {
    codigo_propuesto: datos.codigo,
    fecha: datos.fecha,
    producto: numeroONull(datos.producto),
    rc_objetivo: numeroONull(datos.rc_objetivo),
    volumen: numeroONull(datos.volumen),
    silo_entera: numeroONull(datos.silo_entera),
    silo_descremada: numeroONull(datos.silo_descremada),
    silo_destino: numeroONull(datos.silo_destino),
    entera_grasa: numeroONull(datos.entera_grasa),
    entera_sng: numeroONull(datos.entera_sng),
    descremada_grasa: numeroONull(datos.descremada_grasa),
    descremada_sng: numeroONull(datos.descremada_sng),
    litros_entera: mezcla?.posible ? mezcla.entera : null,
    litros_descremada: mezcla?.posible ? mezcla.descremada : null,
    observaciones: datos.observaciones,
  };
  const borrador = useBorrador({
    datos: datosBorrador,
    activo: tocado,
    crear: crearBorradorVale,
    actualizar: guardarBorradorVale,
    alError: () => setError("No se pudo autoguardar el borrador."),
  });
  const { reanudar } = borrador;

  useEffect(() => {
    let vigente = true;
    void obtenerBorradorVale().then(async (guardado) => {
      if (!vigente || !guardado) return;
      if (!window.confirm("Tienes un vale sin confirmar. ¿Quieres continuarlo?")) {
        await descartarBorradorVale(guardado.id);
        return;
      }
      setDatos({
        ...inicial,
        codigo: guardado.codigo_propuesto,
        fecha: guardado.fecha,
        producto: guardado.producto == null ? "" : String(guardado.producto),
        rc_objetivo: guardado.rc_objetivo ?? "",
        volumen: guardado.volumen ?? "",
        silo_entera: guardado.silo_entera == null ? "" : String(guardado.silo_entera),
        silo_descremada: guardado.silo_descremada == null ? "" : String(guardado.silo_descremada),
        silo_destino: guardado.silo_destino == null ? "" : String(guardado.silo_destino),
        entera_grasa: guardado.entera_grasa ?? "",
        entera_sng: guardado.entera_sng ?? "",
        descremada_grasa: guardado.descremada_grasa ?? "",
        descremada_sng: guardado.descremada_sng ?? "",
        observaciones: guardado.observaciones,
      });
      reanudar(guardado.id);
    }).catch((e) => {
      if (vigente) setError(mensajeDe(e, "No se pudo consultar el borrador."));
    });
    return () => { vigente = false; };
  }, [reanudar]);

  const cambiar = (campo: keyof typeof inicial, valor: string) => {
    setTocado(true);
    setDatos((previo) => ({ ...previo, [campo]: valor }));
    // Cambiar cualquier dato invalida el cálculo anterior: dejarlo en pantalla
    // ofrecería crear el vale con cantidades de otra composición.
    setMezcla(null);
  };

  const seleccionarOrigen = (
    campo: "silo_entera" | "silo_descremada",
    disponible: "entera_disponible" | "descremada_disponible",
    valor: string,
  ) => {
    setTocado(true);
    const silo = silos.find((item) => item.id === Number(valor));
    setDatos((previo) => ({
      ...previo,
      [campo]: valor,
      [disponible]: silo?.litros_disponibles ?? "",
    }));
    setMezcla(null);
  };

  const silosEntera = silos.filter(
    (silo) => silo.tipo === "silo" && Number(silo.litros_disponibles ?? 0) > 0,
  );
  const silosDescremada = silos.filter(
    (silo) => silo.tipo === "tk_ld" && Number(silo.litros_disponibles ?? 0) > 0,
  );
  const silosDestino = silos.filter(
    (silo) => silo.tipo === "silo" && ![datos.silo_entera, datos.silo_descremada].includes(String(silo.id)),
  );

  const calcular = async (e: React.FormEvent) => {
    e.preventDefault();
    setTocado(true);
    setOcupado(true);
    setError("");

    try {
      setMezcla(
        await onCalcular({
          entera_grasa: Number(datos.entera_grasa),
          entera_sng: Number(datos.entera_sng),
          entera_disponible: Number(datos.entera_disponible || 0),
          descremada_grasa: Number(datos.descremada_grasa),
          descremada_sng: Number(datos.descremada_sng),
          descremada_disponible: Number(datos.descremada_disponible || 0),
          rc_objetivo: Number(datos.rc_objetivo),
          volumen: Number(datos.volumen),
        }),
      );
    } catch (e) {
      setError(mensajeDe(e, "No se pudo calcular la mezcla."));
    } finally {
      setOcupado(false);
    }
  };

  const guardar = async () => {
    if (!mezcla?.posible) return;

    setOcupado(true);
    setError("");

    try {
      const borradorId = await borrador.guardarAhora();
      if (borradorId === null) throw new Error("El borrador no alcanzó a guardarse.");
      const confirmado = await confirmarBorradorVale(borradorId);
      borrador.reiniciar();
      await onConfirmado(confirmado);
    } catch (e) {
      setError(mensajeDe(e, "No se pudo crear el vale."));
    } finally {
      setOcupado(false);
    }
  };

  return (
    <div className="fixed inset-0 z-[70] flex items-start justify-center overflow-y-auto bg-slate-950/45 p-4">
      <form
        onSubmit={calcular}
        className="my-6 w-full max-w-3xl rounded-2xl bg-white p-6"
      >

        <div className="flex items-center justify-between">
          <div>
            <p className="text-xs font-semibold uppercase tracking-wider text-emerald-700">
              Estandarización
            </p>
            <h2 className="mt-1 text-xl font-semibold">Nuevo vale</h2>
          </div>
          <button
            type="button"
            onClick={onCerrar}
            className="rounded-lg p-2 text-slate-600 hover:bg-slate-100"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        <div className="mt-5 grid gap-4 sm:grid-cols-3">

          <Campo label="Código de vale">
            <input
              required value={datos.codigo}
              onChange={(e) => cambiar("codigo", e.target.value)}
              className="control"
            />
          </Campo>

          <Campo label="Fecha">
            <input
              required type="date" value={datos.fecha}
              onChange={(e) => cambiar("fecha", e.target.value)}
              className="control"
            />
          </Campo>

          <Campo label="Producto">
            <select
              required value={datos.producto}
              onChange={(e) => cambiar("producto", e.target.value)}
              className="control bg-white"
            >
              <option value="">Selecciona</option>
              {productos.map((p) => (
                <option key={p.id} value={p.id}>{p.nombre}</option>
              ))}
            </select>
          </Campo>

          <Campo label="RC objetivo">
            <input
              required type="number" step="0.0001" min="0.0001"
              placeholder="0.2010"
              value={datos.rc_objetivo}
              onChange={(e) => cambiar("rc_objetivo", e.target.value)}
              className="control"
            />
          </Campo>

          <Campo label="Volumen a preparar (L)">
            <input
              required type="number" step="0.01" min="0.01"
              value={datos.volumen}
              onChange={(e) => cambiar("volumen", e.target.value)}
              className="control"
            />
          </Campo>

          <Campo label="Silo de destino">
            <select
              required value={datos.silo_destino}
              onChange={(e) => cambiar("silo_destino", e.target.value)}
              className="control bg-white"
            >
              <option value="">Selecciona</option>
              {silosDestino.map((s) => (
                <option key={s.id} value={s.id}>{s.codigo} · {Number(s.capacidad_disponible ?? s.capacidad_l).toLocaleString("es-CL")} L libres</option>
              ))}
            </select>
          </Campo>

        </div>

        <Bloque titulo="Leche entera">
          <Campo label="Silo">
            <select
              required value={datos.silo_entera}
              onChange={(e) => seleccionarOrigen("silo_entera", "entera_disponible", e.target.value)}
              className="control bg-white"
            >
              <option value="">Selecciona</option>
              {silosEntera.map((s) => (
                <option key={s.id} value={s.id}>{s.codigo} · {Number(s.litros_disponibles).toLocaleString("es-CL")} L disponibles</option>
              ))}
            </select>
          </Campo>
          <Numero
            label="Materia grasa %" valor={datos.entera_grasa}
            onChange={(v) => cambiar("entera_grasa", v)}
          />
          <Numero
            label="Sólidos no grasos %" valor={datos.entera_sng}
            onChange={(v) => cambiar("entera_sng", v)}
          />
          <Numero
            label="Disponible en silo (L)" valor={datos.entera_disponible} opcional soloLectura
            onChange={(v) => cambiar("entera_disponible", v)}
          />
        </Bloque>

        <Bloque titulo="Leche descremada">
          <Campo label="Estanque">
            <select
              value={datos.silo_descremada}
              onChange={(e) => seleccionarOrigen("silo_descremada", "descremada_disponible", e.target.value)}
              className="control bg-white"
            >
              <option value="">Sin estanque declarado</option>
              {silosDescremada.map((s) => (
                <option key={s.id} value={s.id}>{s.codigo} · {Number(s.litros_disponibles).toLocaleString("es-CL")} L disponibles</option>
              ))}
            </select>
          </Campo>
          <Numero
            label="Materia grasa %" valor={datos.descremada_grasa}
            onChange={(v) => cambiar("descremada_grasa", v)}
          />
          <Numero
            label="Sólidos no grasos %" valor={datos.descremada_sng}
            onChange={(v) => cambiar("descremada_sng", v)}
          />
          <Numero
            label="Disponible en TK (L)" valor={datos.descremada_disponible} opcional soloLectura
            onChange={(v) => cambiar("descremada_disponible", v)}
          />
        </Bloque>

        <Campo label="Observaciones" ancho>
          <textarea
            value={datos.observaciones}
            onChange={(e) => cambiar("observaciones", e.target.value)}
            className="control"
          />
        </Campo>

        {error && (
          <p className="mt-4 rounded-xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700">
            {error}
          </p>
        )}

        {mezcla && (
          <div
            className={`mt-4 rounded-xl border px-4 py-3 text-sm ${
              mezcla.posible
                ? "border-emerald-200 bg-emerald-50 text-emerald-900"
                : "border-amber-200 bg-amber-50 text-amber-900"
            }`}
          >
            {mezcla.posible ? (
              <>
                <p className="font-medium">
                  {mezcla.entera.toLocaleString("es-CL")} L de entera +{" "}
                  {mezcla.descremada.toLocaleString("es-CL")} L de descremada
                </p>
                <p className="mt-1">
                  RC esperado {mezcla.rc_esperado?.toFixed(4)} ·{" "}
                  {mezcla.grasa_esperada}% MG · {mezcla.sng_esperado}% SNG
                </p>
                {mezcla.avisos.map((aviso) => (
                  <p key={aviso} className="mt-1 text-amber-800">⚠ {aviso}</p>
                ))}
              </>
            ) : (
              <p>{mezcla.motivo}</p>
            )}
          </div>
        )}

        <div className="mt-6 flex flex-wrap gap-3">
          <p className="w-full text-xs text-slate-500">
            {borrador.estado === "guardando" ? "Guardando borrador…" :
              borrador.estado === "error" ? "No se pudo autoguardar." :
                borrador.id ? "Borrador guardado. El código se reserva al confirmar." :
                  "Los cambios se guardarán automáticamente."}
          </p>
          <button
            type="submit"
            disabled={ocupado}
            className="flex items-center gap-2 rounded-xl border border-slate-300 px-5 py-3 text-sm font-medium disabled:opacity-40"
          >
            <Calculator className="h-4 w-4" />
            Calcular mezcla
          </button>

          {/* Solo con una mezcla posible. Un vale que nadie puede cumplir se
              descubriría después de transferir. */}
          {mezcla?.posible && (
            <button
              type="button"
              onClick={() => void guardar()}
              disabled={ocupado}
              className="flex flex-1 items-center justify-center gap-2 rounded-xl bg-emerald-700 px-5 py-3 text-sm font-medium text-white disabled:opacity-40"
            >
              <CheckCircle2 className="h-4 w-4" />
              Crear vale
            </button>
          )}
        </div>

      </form>
    </div>
  );
}


function Campo({
  label, ancho = false, children,
}: { label: string; ancho?: boolean; children: React.ReactNode }) {
  return (
    <label className={`text-sm text-slate-600 ${ancho ? "mt-4 block" : ""}`}>
      {label}
      <div className="mt-1 [&_.control]:w-full [&_.control]:rounded-xl [&_.control]:border [&_.control]:border-slate-200 [&_.control]:px-3 [&_.control]:py-2.5">
        {children}
      </div>
    </label>
  );
}


function Numero({
  label, valor, onChange, opcional = false, soloLectura = false,
}: {
  label: string;
  valor: string;
  onChange: (valor: string) => void;
  opcional?: boolean;
  soloLectura?: boolean;
}) {
  return (
    <Campo label={label}>
      <input
        required={!opcional}
        type="number"
        step="0.01"
        min="0"
        value={valor}
        readOnly={soloLectura}
        onChange={(e) => onChange(e.target.value)}
        className={`control ${soloLectura ? "bg-slate-50 text-slate-600" : ""}`}
      />
    </Campo>
  );
}


function Bloque({
  titulo, children,
}: { titulo: string; children: React.ReactNode }) {
  return (
    <fieldset className="mt-5 rounded-xl border border-slate-200 p-4">
      <legend className="px-2 text-sm font-semibold text-slate-700">
        {titulo}
      </legend>
      <div className="grid gap-4 sm:grid-cols-4">{children}</div>
    </fieldset>
  );
}


export default FormularioVale;
