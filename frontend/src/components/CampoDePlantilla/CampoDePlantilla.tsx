import type { CampoPlantilla as Campo } from "../../services/calidad.service";


/*
  Dibuja UN campo de una plantilla.

  Vive aquí y no dentro de un formulario porque lo usan dos: el expediente del
  lote y los registros de máquina. Son el mismo contrato —`plantilla` es un
  dato, no código (MODELO_DATOS.md §2.6)— y una segunda implementación
  acabaría dibujando distinto el mismo campo.

  El tipo `lista` **no se dibuja**: cae al input por defecto. Hay una prueba en
  `maestros` que impide declararlo en una plantilla hasta que se implemente,
  porque si no una lectura horaria se convertiría en un cuadro de texto libre
  sin que nadie lo note.
*/

function CampoDePlantilla({
  campo,
  valor,
  alCambiar,
  deshabilitado,
}: {
  campo: Campo;
  valor: unknown;
  alCambiar: (valor: unknown) => void;
  deshabilitado: boolean;
}) {

  const base =
    "w-full rounded-xl border border-slate-200 px-3 py-2 text-sm text-slate-800 " +
    "focus:border-green-500 focus:outline-none disabled:bg-slate-50 disabled:text-slate-500";

  const texto = valor === null || valor === undefined ? "" : String(valor);

  // Un campo `objeto` sin subcampos declarados no debería existir: el backend
  // lo rechaza al guardar la plantilla. Si llegara uno, se avisa en vez de
  // dibujar un cuadro de JSON que nadie en planta puede completar.
  if (campo.tipo === "objeto" && !campo.campos?.length) {
    return (
      <p className="text-xs text-amber-700">
        El campo «{campo.etiqueta}» no declara sus subcampos y no se puede dibujar.
      </p>
    );
  }

  if (campo.tipo === "booleano") {
    return (
      <label className="flex items-center gap-2 text-sm text-slate-700">

        <input
          type="checkbox"
          checked={valor === true}
          disabled={deshabilitado}
          onChange={(e) => alCambiar(e.target.checked)}
          className="h-4 w-4 rounded border-slate-300 text-green-600 focus:ring-green-500"
        />

        Sí

      </label>
    );
  }

  if (campo.tipo === "enum") {
    return (
      <select
        value={texto}
        disabled={deshabilitado}
        onChange={(e) => alCambiar(e.target.value)}
        className={base}
      >
        <option value="">Sin seleccionar</option>

        {(campo.valores || []).map((v) => (
          <option key={v} value={v}>{v}</option>
        ))}

      </select>
    );
  }

  const tipoHtml =
    campo.tipo === "entero" || campo.tipo === "decimal"
      ? "number"
      : campo.tipo === "fecha"
        ? "date"
        : campo.tipo === "fechaHora"
          ? "datetime-local"
          : campo.tipo === "hora"
            ? "time"
            : "text";

  return (
    <input
      type={tipoHtml}
      step={campo.tipo === "decimal" ? "any" : undefined}
      value={texto}
      disabled={deshabilitado}
      onChange={(e) => {
        const bruto = e.target.value;

        // Los números viajan como números: el backend coteja contra el
        // análisis y "28" en texto no se compara con 28.
        if (tipoHtml === "number") {
          alCambiar(bruto === "" ? "" : Number(bruto));
        } else {
          alCambiar(bruto);
        }
      }}
      className={base}
    />
  );
}


export default CampoDePlantilla;
