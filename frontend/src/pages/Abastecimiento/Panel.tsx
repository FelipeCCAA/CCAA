import { Link } from "react-router-dom";
import {
  AlertTriangle,
  Bell,
  Boxes,
  ClipboardCheck,
  PackageCheck,
  ShieldAlert,
} from "lucide-react";

import {
  obtenerAjustes,
  obtenerAlertas,
  obtenerExistencias,
  obtenerInspecciones,
  obtenerMRQ,
  obtenerNotificaciones,
  type Alerta,
} from "../../services/inventario.service";

import { Aviso, Indicador, Tarjeta, Vacio } from "../../components/seccion/componentes";
import { numero, useCarga } from "../../components/seccion/utilidades";


/*
  Panel de abastecimiento: qué está mal y qué me toca.

  El backend ya calculaba las alertas —stock mínimo, punto de reposición,
  próximo a vencer, cuarentena atrasada— en cada operación de stock, y las
  guardaba en `Alerta`. **No había pantalla que las mostrara**: ni siquiera
  estaban expuestas en el servicio del frontend. Se calculaban y se tiraban.

  Lo mismo con los pendientes. El sistema sabe cuántas inspecciones esperan a
  Calidad y cuántos ajustes esperan una segunda firma; había que entrar a la
  pestaña correcta y contar a ojo.
*/

const ORDEN_SEVERIDAD: Record<string, number> = {
  critica: 0,
  advertencia: 1,
  info: 2,
};

const ESTILO_SEVERIDAD: Record<string, string> = {
  critica: "border-red-200 bg-red-50 text-red-800",
  advertencia: "border-amber-200 bg-amber-50 text-amber-800",
  info: "border-slate-200 bg-slate-50 text-slate-700",
};

/* Estados que significan «ya se decidió». Lo que no está aquí, espera a
   alguien — y es lo que el panel cuenta como pendiente. */
const INSPECCION_CERRADA = ["aprobada", "observada", "rechazada", "bloqueada"];
const MRQ_CERRADA = ["entregada", "rechazada", "cancelada"];


function FilaAlerta({ alerta }: { alerta: Alerta }) {
  const estilo = ESTILO_SEVERIDAD[alerta.severidad] ?? ESTILO_SEVERIDAD.info;

  return (
    <div className={`flex items-start gap-3 rounded-xl border px-4 py-3 ${estilo}`}>

      <ShieldAlert className="mt-0.5 h-4 w-4 shrink-0" />

      <div className="min-w-0">
        <p className="text-sm font-medium">
          {alerta.insumo_nombre ?? alerta.lote_codigo ?? alerta.tipo}
        </p>
        <p className="mt-0.5 text-sm opacity-90">{alerta.mensaje}</p>
      </div>

    </div>
  );
}


function Panel() {

  const alertas = useCarga(obtenerAlertas);
  const existencias = useCarga(obtenerExistencias);
  const inspecciones = useCarga(obtenerInspecciones);
  const mrq = useCarga(obtenerMRQ);
  const ajustes = useCarga(obtenerAjustes);
  const notificaciones = useCarga(obtenerNotificaciones);

  const listaAlertas = [...(alertas.datos ?? [])].sort(
    (a, b) =>
      (ORDEN_SEVERIDAD[a.severidad] ?? 9) - (ORDEN_SEVERIDAD[b.severidad] ?? 9),
  );

  const disponible = (existencias.datos ?? []).reduce(
    (suma, e) => suma + Number(e.cantidad_disponible),
    0,
  );

  const enCuarentena = (existencias.datos ?? [])
    .filter((e) => e.estado_calidad === "pendiente")
    .reduce((suma, e) => suma + Number(e.cantidad_fisica), 0);

  const inspeccionesAbiertas = (inspecciones.datos ?? []).filter(
    (i) => !INSPECCION_CERRADA.includes(i.estado),
  );

  const mrqAbiertas = (mrq.datos ?? []).filter(
    (m) => !MRQ_CERRADA.includes(m.estado),
  );

  const ajustesPendientes = (ajustes.datos ?? []).filter(
    (a) => a.estado === "pendiente",
  );

  /* Lo que espera a una persona, con el enlace a donde se resuelve. Un
     pendiente sin salida obliga a buscar la pestaña a mano. */
  const pendientes = [
    {
      cuantos: inspeccionesAbiertas.length,
      texto: "lote(s) esperando decisión de Calidad",
      a: "calidad",
    },
    {
      cuantos: ajustesPendientes.length,
      texto: "ajuste(s) de inventario esperando una segunda firma",
      a: "stock",
    },
    {
      cuantos: mrqAbiertas.length,
      texto: "solicitud(es) de material sin entregar",
      a: "pedidos",
    },
  ].filter((p) => p.cuantos > 0);

  return (
    <div className="space-y-8">

      <section className="grid gap-5 sm:grid-cols-2 xl:grid-cols-4">

        <Indicador
          etiqueta="Stock disponible"
          valor={numero(disponible)}
          Icono={Boxes}
        />
        <Indicador
          etiqueta="En cuarentena"
          valor={numero(enCuarentena)}
          Icono={AlertTriangle}
          tono={enCuarentena > 0 ? "alerta" : "normal"}
        />
        <Indicador
          etiqueta="Inspecciones pendientes"
          valor={inspeccionesAbiertas.length}
          Icono={ClipboardCheck}
          tono={inspeccionesAbiertas.length > 0 ? "alerta" : "normal"}
        />
        <Indicador
          etiqueta="Pedidos abiertos"
          valor={mrqAbiertas.length}
          Icono={PackageCheck}
        />

      </section>

      {/* `items-start` para que cada tarjeta mida lo suyo: sin esto la de
          alertas se estira hasta igualar la columna de la derecha y aparece
          un vacío enorme debajo de «sin alertas». */}
      <div className="grid items-start gap-8 xl:grid-cols-2">

        <Tarjeta
          titulo="Alertas vigentes"
          descripcion="Las calcula el sistema en cada movimiento. No se cierran a mano: se apagan arreglando lo que las causó."
        >
          {alertas.error ? (
            <Aviso>{alertas.error}</Aviso>
          ) : alertas.cargando ? (
            <Vacio>Cargando…</Vacio>
          ) : listaAlertas.length === 0 ? (
            <Vacio>Sin alertas. Todo dentro de sus límites.</Vacio>
          ) : (
            <div className="space-y-3">
              {listaAlertas.map((a) => (
                <FilaAlerta key={a.id} alerta={a} />
              ))}
            </div>
          )}
        </Tarjeta>

        <div className="space-y-8">

          <Tarjeta
            titulo="Lo que está esperando"
            descripcion="Documentos detenidos hasta que alguien decida."
          >
            {pendientes.length === 0 ? (
              <Vacio>Nada pendiente de decisión.</Vacio>
            ) : (
              <ul className="space-y-3">
                {pendientes.map((p) => (
                  <li key={p.a}>
                    <Link
                      to={p.a}
                      className="flex items-center gap-3 rounded-xl bg-slate-50 px-4 py-3 text-sm text-slate-700 hover:bg-slate-100"
                    >
                      <span className="rounded-lg bg-white px-2.5 py-1 font-bold text-slate-900">
                        {p.cuantos}
                      </span>
                      {p.texto}
                    </Link>
                  </li>
                ))}
              </ul>
            )}
          </Tarjeta>

          <Tarjeta titulo="Notificaciones">
            {notificaciones.error ? (
              <Aviso>{notificaciones.error}</Aviso>
            ) : (notificaciones.datos ?? []).length === 0 ? (
              <Vacio>Sin notificaciones.</Vacio>
            ) : (
              <div className="space-y-3">
                {(notificaciones.datos ?? []).slice(0, 6).map((n) => (
                  <div key={n.id} className="rounded-xl bg-slate-50 px-4 py-3">
                    <p className="flex items-center gap-2 text-sm font-medium text-slate-800">
                      <Bell className="h-3.5 w-3.5 text-slate-600" />
                      {n.titulo}
                    </p>
                    <p className="mt-1 text-sm text-slate-600">{n.mensaje}</p>
                  </div>
                ))}
              </div>
            )}
          </Tarjeta>

        </div>

      </div>

    </div>
  );
}


export default Panel;
