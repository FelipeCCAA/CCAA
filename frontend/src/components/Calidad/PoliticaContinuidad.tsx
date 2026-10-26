import { useEffect, useState } from "react";
import { obtenerPoliticaContinuidad } from "../../services/calidad.service";
import { mensajePoliticaContinuidad, type PoliticaContinuidad as Politica } from "../../services/continuidad-calidad";

export default function PoliticaContinuidad() {
  const [politica, setPolitica] = useState<Politica | null>(null);
  useEffect(() => {
    let vigente = true;
    void obtenerPoliticaContinuidad().then((datos) => { if (vigente) setPolitica(datos); }).catch(() => { /* No asumir habilitación sin respuesta del servidor. */ });
    return () => { vigente = false; };
  }, []);
  const mensaje = mensajePoliticaContinuidad(politica);
  if (!mensaje) return null;
  return <aside role="status" className="m-4 rounded-xl border border-amber-300 bg-amber-50 px-4 py-3 text-sm font-medium text-amber-950">{mensaje}</aside>;
}
