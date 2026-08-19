import type { ReactNode } from "react";
import { Link } from "react-router-dom";
import {
  ArrowLeft,
  BadgeCheck,
  KeyRound,
  ShieldCheck,
  TimerReset,
} from "lucide-react";

import logo from "../../assets/logos/logo-campos-australes-normal.png";


interface AccesoRecuperacionProps {
  paso: string;
  titulo: string;
  descripcion: string;
  children: ReactNode;
}


/**
 * Marco visual compartido por las pantallas públicas de recuperación.
 * Mantiene el formulario enfocado y permite volver siempre al inicio.
 */
function AccesoRecuperacion({
  paso,
  titulo,
  descripcion,
  children,
}: AccesoRecuperacionProps) {
  return (
    <main className="relative flex min-h-dvh items-center justify-center overflow-hidden bg-[#f3f7f4] px-4 py-6 sm:px-6 lg:px-8">
      <div className="pointer-events-none absolute -left-32 top-0 h-96 w-96 rounded-full bg-emerald-200/30 blur-3xl" />
      <div className="pointer-events-none absolute -bottom-48 right-0 h-[30rem] w-[30rem] rounded-full bg-green-200/30 blur-3xl" />

      <section className="relative grid w-full max-w-6xl overflow-hidden rounded-[2rem] border border-white/80 bg-white shadow-[0_30px_90px_-35px_rgba(15,23,42,0.35)] lg:min-h-[690px] lg:grid-cols-[0.92fr_1.08fr]">
        <aside className="relative hidden overflow-hidden bg-gradient-to-br from-green-950 via-green-900 to-emerald-800 p-12 text-white lg:flex lg:flex-col">
          <div className="absolute -right-28 -top-28 h-80 w-80 rounded-full border border-white/10" />
          <div className="absolute -right-12 -top-12 h-48 w-48 rounded-full border border-white/10" />
          <div className="absolute bottom-12 left-10 h-28 w-28 rounded-full bg-emerald-400/10 blur-2xl" />

          <div className="relative">
            <span className="inline-flex rounded-2xl bg-white px-5 py-3 shadow-lg shadow-black/10">
              <img
                src={logo}
                className="w-44"
                alt="Campos Australes"
              />
            </span>
          </div>

          <div className="relative my-auto py-12">
            <span className="inline-flex items-center gap-2 rounded-full border border-emerald-300/20 bg-emerald-300/10 px-3 py-1.5 text-xs font-semibold uppercase tracking-[0.18em] text-emerald-100">
              <ShieldCheck className="h-4 w-4" aria-hidden="true" />
              Acceso protegido
            </span>

            <h2 className="mt-7 max-w-md text-4xl font-bold leading-tight tracking-tight">
              Recupera el acceso de forma segura.
            </h2>
            <p className="mt-5 max-w-md text-base leading-7 text-emerald-50/75">
              El sistema valida tu identidad mediante un enlace privado,
              temporal y válido una sola vez.
            </p>

            <ul className="mt-10 space-y-5 text-sm text-emerald-50/90">
              <li className="flex items-center gap-4">
                <span className="rounded-xl bg-white/10 p-2.5">
                  <KeyRound className="h-5 w-5" aria-hidden="true" />
                </span>
                Tu contraseña nunca se envía por correo.
              </li>
              <li className="flex items-center gap-4">
                <span className="rounded-xl bg-white/10 p-2.5">
                  <TimerReset className="h-5 w-5" aria-hidden="true" />
                </span>
                El enlace expira automáticamente en una hora.
              </li>
              <li className="flex items-center gap-4">
                <span className="rounded-xl bg-white/10 p-2.5">
                  <BadgeCheck className="h-5 w-5" aria-hidden="true" />
                </span>
                Las sesiones anteriores quedan invalidadas.
              </li>
            </ul>
          </div>

          <p className="relative text-xs text-emerald-100/50">
            Gestión Productiva · CCAA
          </p>
        </aside>

        <div className="flex flex-col px-6 py-7 sm:px-10 sm:py-10 lg:px-16 lg:py-12">
          <div className="flex items-center justify-between">
            <Link
              to="/login"
              className="inline-flex min-h-10 items-center gap-2 rounded-lg text-sm font-medium text-slate-600 transition hover:text-green-800 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-green-600 focus-visible:ring-offset-4"
            >
              <ArrowLeft className="h-4 w-4" aria-hidden="true" />
              Volver
            </Link>

            <img
              src={logo}
              className="w-36 lg:hidden"
              alt="Campos Australes"
            />
          </div>

          <div className="my-auto py-10">
            <div className="flex items-center gap-3">
              <span className="grid h-11 w-11 place-items-center rounded-2xl bg-green-50 text-green-700 ring-1 ring-green-100">
                <ShieldCheck className="h-5 w-5" aria-hidden="true" />
              </span>
              <span className="text-xs font-bold uppercase tracking-[0.18em] text-green-700">
                {paso}
              </span>
            </div>

            <h1 className="mt-6 text-3xl font-bold tracking-tight text-slate-950 sm:text-4xl">
              {titulo}
            </h1>
            <p className="mt-4 max-w-xl text-[15px] leading-7 text-slate-600">
              {descripcion}
            </p>

            <div className="mt-9">{children}</div>
          </div>

          <p className="text-center text-xs text-slate-600 lg:text-left">
            ¿Necesitas ayuda? Contacta al administrador del sistema.
          </p>
        </div>
      </section>
    </main>
  );
}


export default AccesoRecuperacion;
