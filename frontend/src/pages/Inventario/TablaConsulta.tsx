import { useCallback, useEffect, useMemo, useState, type FormEvent, type ReactNode } from "react";

import CampoEtiquetado from "../../components/operacion/CampoEtiquetado";
import { claseBoton, claseCampo, claseCelda, claseEncabezado } from "../../components/seccion/utilidades";
import type { Pagina } from "../../services/paginacion";
import type { FiltrosInventario, UbicacionInventario } from "../../services/inventario.service";

export interface Columna<T> {
  titulo: string;
  celda: (fila: T) => ReactNode;
  numerica?: boolean;
}

/*
  Una pestaña de consulta: filtros arriba, una página del servidor abajo, y
  su propio error. Los filtros viajan al servidor porque la lista está
  paginada: filtrar en el cliente sería filtrar solo la primera página.
*/
export default function TablaConsulta<T>({
  cargar, columnas, clave, estados, etiquetaEstado = "Estado", conFechas = false, ubicaciones, etiquetaBusqueda, vacio,
  filtrosFijos = {},
}: {
  cargar: (filtros: FiltrosInventario) => Promise<Pagina<T>>;
  columnas: Columna<T>[];
  clave: (fila: T) => string | number;
  estados: { valor: string; texto: string }[];
  etiquetaEstado?: string;
  conFechas?: boolean;
  ubicaciones: UbicacionInventario[];
  etiquetaBusqueda: string;
  vacio: string;
  filtrosFijos?: FiltrosInventario;
}) {
  const [borrador, setBorrador] = useState<FiltrosInventario>({});
  const [filtros, setFiltros] = useState<FiltrosInventario>({});
  const [pagina, setPagina] = useState(1);
  const [datos, setDatos] = useState<Pagina<T> | null>(null);
  const [cargando, setCargando] = useState(true);
  const [error, setError] = useState("");

  // filtrosFijos se compara por contenido: un objeto literal cambia de identidad en cada render.
  // Depender del objeto directamente volvería a recalcularlo en cada render, que es
  // justo lo que esto evita; se depende de su contenido serializado en su lugar.
  const claveFiltrosFijos = JSON.stringify(filtrosFijos);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  const filtrosFijosEstables = useMemo(() => filtrosFijos, [claveFiltrosFijos]);

  const traer = useCallback(async () => {
    setCargando(true);
    try {
      setDatos(await cargar({ ...filtrosFijosEstables, ...filtros, page: pagina }));
      setError("");
    } catch {
      setError("No se pudo cargar esta consulta.");
    } finally {
      setCargando(false);
    }
  }, [cargar, filtros, pagina, filtrosFijosEstables]);

  useEffect(() => {
    const t = setTimeout(() => void traer(), 0);
    return () => clearTimeout(t);
  }, [traer]);

  const aplicar = (evento: FormEvent) => {
    evento.preventDefault();
    setPagina(1);
    setFiltros(borrador);
  };

  const total = datos?.count ?? 0;
  const desde = total === 0 ? 0 : (pagina - 1) * 50 + 1;
  const hasta = Math.min(pagina * 50, total);

  return (
    <div className="space-y-4">
      <form onSubmit={aplicar} className="grid gap-3 rounded-2xl border border-slate-200 bg-white p-4 sm:grid-cols-2 lg:grid-cols-6">
        <div className="lg:col-span-2">
          <CampoEtiquetado etiqueta={etiquetaBusqueda}>
            <input type="search" value={borrador.q ?? ""} onChange={(e) => setBorrador({ ...borrador, q: e.target.value })} className={claseCampo} />
          </CampoEtiquetado>
        </div>
        {estados.length > 0 && (
          <CampoEtiquetado etiqueta={etiquetaEstado}>
            <select value={borrador.estado ?? ""} onChange={(e) => setBorrador({ ...borrador, estado: e.target.value })} className={claseCampo}>
              <option value="">Todos</option>
              {estados.map((s) => <option key={s.valor} value={s.valor}>{s.texto}</option>)}
            </select>
          </CampoEtiquetado>
        )}
        <CampoEtiquetado etiqueta="Ubicación">
          <select value={borrador.ubicacion ?? ""} onChange={(e) => setBorrador({ ...borrador, ubicacion: e.target.value ? Number(e.target.value) : "" })} className={claseCampo}>
            <option value="">Todas</option>
            {ubicaciones.map((u) => <option key={u.id} value={u.id}>{u.codigo} · {u.bodega_nombre}</option>)}
          </select>
        </CampoEtiquetado>
        {conFechas && (
          <>
            <CampoEtiquetado etiqueta="Desde">
              <input type="date" value={borrador.desde ?? ""} onChange={(e) => setBorrador({ ...borrador, desde: e.target.value })} className={claseCampo} />
            </CampoEtiquetado>
            <CampoEtiquetado etiqueta="Hasta">
              <input type="date" value={borrador.hasta ?? ""} onChange={(e) => setBorrador({ ...borrador, hasta: e.target.value })} className={claseCampo} />
            </CampoEtiquetado>
          </>
        )}
        <div className="flex items-end">
          <button type="submit" className={claseBoton}>Filtrar</button>
        </div>
      </form>

      {error && <p role="alert" className="rounded-xl bg-red-50 px-4 py-3 text-sm text-red-800">{error}</p>}

      <div className="overflow-x-auto rounded-2xl border border-slate-200 bg-white">
        <table className="min-w-full">
          <thead className="bg-slate-50">
            <tr>{columnas.map((c) => <th key={c.titulo} scope="col" className={`${claseEncabezado} ${c.numerica ? "text-right" : ""}`}>{c.titulo}</th>)}</tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {datos?.results.map((fila) => (
              <tr key={clave(fila)}>
                {columnas.map((c) => <td key={c.titulo} className={`${claseCelda} ${c.numerica ? "text-right tabular-nums" : ""}`}>{c.celda(fila)}</td>)}
              </tr>
            ))}
          </tbody>
        </table>
        {!cargando && datos && datos.results.length === 0 && <p className="px-5 py-4 text-sm text-slate-600">{vacio}</p>}
        {cargando && <p className="px-5 py-4 text-sm text-slate-600">Cargando…</p>}
      </div>

      <nav aria-label="Páginas" className="flex flex-wrap items-center justify-between gap-3 text-sm text-slate-700">
        <span>{total === 0 ? "Sin resultados" : `${desde}–${hasta} de ${total}`}</span>
        <span className="flex gap-2">
          <button type="button" disabled={!datos?.previous || cargando} onClick={() => setPagina((p) => p - 1)} className="rounded-xl border border-slate-300 px-4 py-2 disabled:opacity-40">Anterior</button>
          <button type="button" disabled={!datos?.next || cargando} onClick={() => setPagina((p) => p + 1)} className="rounded-xl border border-slate-300 px-4 py-2 disabled:opacity-40">Siguiente</button>
        </span>
      </nav>
    </div>
  );
}
