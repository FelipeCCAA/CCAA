import { Link, Outlet } from "react-router-dom";
import { LockKeyhole } from "lucide-react";

import { destinoInicial, puedeAccederModulo, type ModuloSistema } from "../../services/access-control";
import { obtenerSesion } from "../../services/sesion";

export function AccesoRestringido({ detalle = "Tu área no está autorizada para ingresar a este módulo." }: { detalle?: string }) {
  const usuario = obtenerSesion()?.usuario;
  return <main className="flex min-h-[70vh] items-center justify-center px-6 py-12">
    <section className="max-w-lg rounded-2xl border border-amber-200 bg-white p-8 text-center shadow-sm">
      <LockKeyhole className="mx-auto h-10 w-10 text-amber-600" />
      <h1 className="mt-4 text-2xl font-bold text-slate-900">Acceso restringido</h1>
      <p className="mt-2 text-sm text-slate-600">{detalle}</p>
      {usuario && <Link to={destinoInicial(usuario)} className="mt-6 inline-flex rounded-xl bg-slate-900 px-4 py-2.5 text-sm font-semibold text-white">Volver a mi módulo</Link>}
    </section>
  </main>;
}

export default function RutaModulo({ modulo }: { modulo: ModuloSistema }) {
  const usuario = obtenerSesion()?.usuario;
  return puedeAccederModulo(usuario, modulo) ? <Outlet /> : <AccesoRestringido />;
}
