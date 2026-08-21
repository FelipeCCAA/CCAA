import { useCallback, useEffect, useState } from "react";
import { History, Search } from "lucide-react";

import {
  buscarAuditoria,
  obtenerFiltrosAuditoria,
  type ConsultaAuditoria,
  type FiltrosAuditoria,
  type RegistroAuditoria,
} from "../../services/auditoria.service";


/*
  Registro de auditoría.

  Responde la pregunta que hace un auditor: quién cambió esto, cuándo, y qué
  decía antes. Por eso cada fila muestra el **diff** —campo, valor anterior,
  valor nuevo— y no solo «alguien modificó un lote».

  Es de solo lectura para todos los roles, incluida Administración. Un
  registro que alguien puede editar no prueba nada, y esconderlo a los demás
  ocultaría justo el rastro de quien más poder tiene para cambiar cosas.
*/

const POR_PAGINA = 50;


const ESTILO_ACCION: Record<string, string> = {
  creacion: "bg-green-50 text-green-700",
  modificacion: "bg-blue-50 text-blue-700",
  borrado: "bg-red-50 text-red-700",
};


/** Un valor del diff, en algo legible. */
function comoTexto(valor: unknown): string {
  if (valor === null || valor === undefined || valor === "") {
    return "—";
  }

  if (typeof valor === "object") {
    return JSON.stringify(valor);
  }

  return String(valor);
}


/*
  Separa un valor del diff en su par [antes, después].

  El backend siempre guarda pares, pero esto no lo da por hecho. Un registro
  con otra forma —de una versión anterior, o de un modelo con un JSONField que
  contenga una lista— haría fallar la desestructuración, y como esto se dibuja
  dentro del `map` de la tabla, el fallo se lleva por delante la pantalla
  entera. Ya pasó una vez: las altas se guardaban planas y desestructurar un
  número dejó la página en blanco.

  Un registro de auditoría que no se puede leer es peor que uno feo.
*/
function par(valor: unknown): [unknown, unknown] {
  if (Array.isArray(valor) && valor.length === 2) {
    return [valor[0], valor[1]];
  }

  // Forma inesperada: se muestra como valor único, sin inventar un anterior.
  return [undefined, valor];
}


function Diff({ registro }: { registro: RegistroAuditoria }) {

  const campos = Object.entries(registro.cambios ?? {});

  if (campos.length === 0) {
    return <span className="text-slate-600">—</span>;
  }

  return (
    <ul className="space-y-1">
      {campos.map(([campo, valor]) => {

        const [antes, despues] = par(valor);
        // En un alta no hay valor anterior: mostrar "— → x" es ruido.
        const soloDespues = antes === null || antes === undefined;

        return (
          <li key={campo} className="text-sm">

            <span className="text-slate-600">{campo}</span>

            {soloDespues ? (
              <span className="ml-2 text-slate-800">{comoTexto(despues)}</span>
            ) : (
              <>
                <span className="ml-2 text-slate-600 line-through">
                  {comoTexto(antes)}
                </span>
                <span className="mx-1.5 text-slate-300">→</span>
                <span className="text-slate-800">{comoTexto(despues)}</span>
              </>
            )}

          </li>
        );
      })}
    </ul>
  );
}


function Auditoria() {

  const [registros, setRegistros] = useState<RegistroAuditoria[]>([]);
  const [total, setTotal] = useState(0);
  const [pagina, setPagina] = useState(1);

  const [filtros, setFiltros] = useState<FiltrosAuditoria | null>(null);
  const [consulta, setConsulta] = useState<ConsultaAuditoria>({});

  const [cargando, setCargando] = useState(true);
  const [error, setError] = useState("");

  const cargar = useCallback(async () => {

    setCargando(true);
    setError("");

    try {
      const datos = await buscarAuditoria({ ...consulta, pagina });
      setRegistros(datos.results);
      setTotal(datos.count);
    } catch {
      setError("No se pudo cargar el registro de auditoría.");
    } finally {
      setCargando(false);
    }

  }, [consulta, pagina]);

  useEffect(() => {
    // Espera a que el usuario deje de escribir antes de consultar.
    const temporizador = setTimeout(cargar, 250);

    return () => clearTimeout(temporizador);
  }, [cargar]);

  useEffect(() => {
    obtenerFiltrosAuditoria()
      .then(setFiltros)
      // Sin filtros el listado igual se ve; solo no se puede acotar.
      .catch(() => setFiltros(null));
  }, []);

  const cambiar = (campo: keyof ConsultaAuditoria, valor: string) => {
    setConsulta((c) => ({ ...c, [campo]: valor }));
    setPagina(1);
  };

  const control =
    "rounded-xl border border-slate-300 bg-white px-4 py-2.5 text-sm outline-none focus:border-green-600";

  const encabezado =
    "px-4 py-3 text-left text-xs font-semibold uppercase tracking-wide text-slate-600";

  const ultimaPagina = Math.max(1, Math.ceil(total / POR_PAGINA));

  return (
    <div className="px-8 py-10">

      <div className="mx-auto max-w-7xl">

        <header className="mb-8">

          <h1 className="flex items-center gap-3 text-3xl font-bold text-slate-800">
            <History className="h-7 w-7 text-slate-600" />
            Auditoría
          </h1>

          <p className="mt-2 max-w-3xl text-slate-600">
            Quién cambió qué, cuándo, y qué decía antes. Se registra todo lo que
            escribe en la base: la aplicación, el admin y los procesos internos.
            Nadie puede modificar este registro, tampoco Administración.
          </p>

        </header>

        {/* Filtros */}

        <section className="mb-6 flex flex-wrap items-center gap-3">

          <div className="relative">

            <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-600" />

            <input
              className={`${control} w-64 pl-9`}
              placeholder="Buscar por registro…"
              value={consulta.buscar ?? ""}
              onChange={(e) => cambiar("buscar", e.target.value)}
            />

          </div>

          <select
            className={control}
            value={consulta.modelo ?? ""}
            onChange={(e) => cambiar("modelo", e.target.value)}
          >
            <option value="">Todo el sistema</option>
            {(filtros?.modelos ?? []).map((m) => (
              <option key={m.valor} value={m.valor}>
                {m.etiqueta}
              </option>
            ))}
          </select>

          <select
            className={control}
            value={consulta.usuario ?? ""}
            onChange={(e) => cambiar("usuario", e.target.value)}
          >
            <option value="">Todos los usuarios</option>
            {(filtros?.usuarios ?? []).map((u) => (
              <option key={u} value={u}>
                {u}
              </option>
            ))}
          </select>

          <select
            className={control}
            value={consulta.accion ?? ""}
            onChange={(e) => cambiar("accion", e.target.value)}
          >
            <option value="">Toda acción</option>
            {(filtros?.acciones ?? []).map((a) => (
              <option key={a.valor} value={a.valor}>
                {a.etiqueta}
              </option>
            ))}
          </select>

          <input
            type="date"
            className={control}
            value={consulta.desde ?? ""}
            onChange={(e) => cambiar("desde", e.target.value)}
            title="Desde"
          />

          <input
            type="date"
            className={control}
            value={consulta.hasta ?? ""}
            onChange={(e) => cambiar("hasta", e.target.value)}
            title="Hasta"
          />

          <span className="ml-auto text-sm text-slate-600">
            {cargando
              ? "Cargando…"
              : `${total.toLocaleString("es-CL")} cambio${total === 1 ? "" : "s"}`}
          </span>

        </section>

        {error && (
          <div className="mb-6 rounded-2xl border border-red-200 bg-red-50 px-6 py-4 text-sm text-red-700">
            {error}
          </div>
        )}

        <section className="rounded-2xl border border-slate-200 bg-white">

          {!cargando && registros.length === 0 ? (

            <p className="px-6 py-10 text-center text-sm text-slate-600">
              {total === 0 && Object.keys(consulta).length === 0
                ? "Todavía no hay cambios registrados."
                : "Ningún cambio coincide con los filtros."}
            </p>

          ) : (

            <div className="overflow-x-auto">

              <table className="w-full">

                <thead className="bg-slate-50">
                  <tr>
                    <th className={encabezado}>Cuándo</th>
                    <th className={encabezado}>Quién</th>
                    <th className={encabezado}>Qué</th>
                    <th className={encabezado}>Cambios</th>
                  </tr>
                </thead>

                <tbody>

                  {registros.map((r) => (

                    <tr key={r.id} className="border-t border-slate-100 align-top">

                      <td className="px-4 py-3 text-sm whitespace-nowrap text-slate-600">
                        {new Date(r.fecha_hora).toLocaleString("es-CL", {
                          dateStyle: "short",
                          timeStyle: "short",
                        })}
                      </td>

                      <td className="px-4 py-3 text-sm">
                        <span className="text-slate-800">
                          {r.usuario_nombre || "sistema"}
                        </span>
                        <span className="ml-2 text-xs text-slate-600">
                          {r.origen}
                        </span>
                      </td>

                      <td className="px-4 py-3 text-sm">

                        <span
                          className={`rounded-full px-2 py-0.5 text-xs font-medium ${
                            ESTILO_ACCION[r.accion] ?? "bg-slate-100 text-slate-600"
                          }`}
                        >
                          {r.accion_etiqueta}
                        </span>

                        <div className="mt-1 text-slate-800">{r.objeto_desc}</div>

                        <div className="text-xs text-slate-600">
                          {r.etiqueta_modelo}
                        </div>

                      </td>

                      <td className="px-4 py-3">
                        <Diff registro={r} />
                      </td>

                    </tr>

                  ))}

                </tbody>

              </table>

            </div>

          )}

        </section>

        {ultimaPagina > 1 && (

          <div className="mt-4 flex items-center justify-center gap-3">

            <button
              type="button"
              disabled={pagina <= 1}
              onClick={() => setPagina((p) => p - 1)}
              className="rounded-xl border border-slate-200 px-4 py-2 text-sm font-medium text-slate-600 hover:bg-slate-50 disabled:opacity-40"
            >
              Anterior
            </button>

            <span className="text-sm text-slate-600">
              Página {pagina} de {ultimaPagina}
            </span>

            <button
              type="button"
              disabled={pagina >= ultimaPagina}
              onClick={() => setPagina((p) => p + 1)}
              className="rounded-xl border border-slate-200 px-4 py-2 text-sm font-medium text-slate-600 hover:bg-slate-50 disabled:opacity-40"
            >
              Siguiente
            </button>

          </div>

        )}

      </div>

    </div>
  );
}


export default Auditoria;
