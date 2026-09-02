import {
  disponibilidadSegunEstado,
  type DisponibilidadEquipo,
} from "../../services/disponibilidad-equipos";

const ESTILOS: Record<DisponibilidadEquipo, string> = {
  disponible: "bg-emerald-100 text-emerald-800",
  reservado: "bg-amber-100 text-amber-900",
  ocupado: "bg-blue-100 text-blue-900",
};

export default function EstadoEquipo({
  estado,
  ejecucion,
}: {
  estado?: string | null;
  ejecucion?: string | null;
}) {
  const disponibilidad = disponibilidadSegunEstado(estado);
  const detalle = ejecucion && disponibilidad !== "disponible" ? ` · ${ejecucion}` : "";
  return (
    <span className={`inline-flex rounded-full px-2.5 py-1 text-xs font-bold uppercase ${ESTILOS[disponibilidad]}`}>
      {disponibilidad}{detalle}
    </span>
  );
}
