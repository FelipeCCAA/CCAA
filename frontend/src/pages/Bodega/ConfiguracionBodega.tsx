import Bodegas from "../Abastecimiento/Bodegas";
import Materiales from "../Abastecimiento/Materiales";

/* Lo que se configura una vez y se consulta poco: detrás de una pestaña,
   no delante de los movimientos. */
export default function ConfiguracionBodega() {
  return (
    <div className="space-y-10">
      <Bodegas />
      <Materiales />
    </div>
  );
}
