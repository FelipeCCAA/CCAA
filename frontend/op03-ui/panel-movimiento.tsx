// Fixture de navegador: monta el componente real sin rutas ni servicios reales.
import { useState } from "react";
import { createRoot } from "react-dom/client";
import PanelMovimiento from "../src/pages/Bodega/PanelMovimiento";
import type { Existencia, UbicacionInventario } from "../src/services/inventario.service";
import "../src/index.css";

const existencia: Existencia = {
  id: 51, lote: 10, lote_codigo: "LOTE-TEST", insumo_nombre: "Sacos de prueba",
  ubicacion: 1, ubicacion_codigo: "BOD-A", ubicacion_tipo: "disponible", bodega_nombre: "Bodega simulada",
  estado_calidad: "aprobado", cantidad_fisica: "100.000", cantidad_reservada: "75.000",
  cantidad_disponible: "25.000", unidad: "un", insumo_codigo: "SACO-TEST", lote_utilizable: true,
};
const destino: UbicacionInventario = {
  id: 2, codigo: "BOD-B", bodega: 1, bodega_nombre: "Bodega simulada", tipo: "disponible",
  tipo_etiqueta: "Disponible", descripcion: "Solo datos sintéticos", activo: true,
};

export default function Fixture() {
  const [hecho, setHecho] = useState("");
  return <main className="mx-auto max-w-3xl p-8">
    <p className="mb-4">Prueba aislada OP-03. No conecta con datos de planta.</p>
    {hecho ? <p role="status">{hecho}</p> : <PanelMovimiento
      accion={{ tipo: "reubicar-material", existencia }} ubicaciones={[destino]} insumos={[]}
      onCerrar={() => undefined} onHecho={setHecho}
    />}
  </main>;
}

createRoot(document.getElementById("root")!).render(<Fixture />);
