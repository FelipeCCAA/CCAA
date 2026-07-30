import { useState } from "react";
import axios from "axios";
import {
  ArrowRight,
  Check,
  CheckCircle2,
  Eye,
  EyeOff,
  LoaderCircle,
  LockKeyhole,
} from "lucide-react";
import { Link, useSearchParams } from "react-router-dom";

import { restablecerContrasena } from "../../services/usuario.service";

import AccesoRecuperacion from "./AccesoRecuperacion";


function mensajesDelError(error: unknown): string {
  if (!axios.isAxiosError(error) || !error.response) {
    return "No se pudo conectar con el servidor.";
  }

  const datos = error.response.data;

  if (typeof datos?.error === "string") {
    return datos.error;
  }

  if (Array.isArray(datos?.nueva_contrasena)) {
    return datos.nueva_contrasena.join(" ");
  }

  if (Array.isArray(datos?.confirmar_contrasena)) {
    return datos.confirmar_contrasena.join(" ");
  }

  if (error.response.status === 429) {
    return "Se realizaron demasiados intentos. Solicita un enlace nuevo.";
  }

  return "No se pudo restablecer la contraseña.";
}


function RestablecerContrasena() {
  const [parametros] = useSearchParams();
  const uid = parametros.get("uid") || "";
  const token = parametros.get("token") || "";

  const [nuevaContrasena, setNuevaContrasena] = useState("");
  const [confirmarContrasena, setConfirmarContrasena] = useState("");
  const [mostrar, setMostrar] = useState(false);
  const [cargando, setCargando] = useState(false);
  const [completado, setCompletado] = useState(false);
  const [error, setError] = useState("");

  const enlaceIncompleto = !uid || !token;
  const criterios = [
    { texto: "8 caracteres o más", cumple: nuevaContrasena.length >= 8 },
    {
      texto: "Mayúscula y minúscula",
      cumple: /[A-Z]/.test(nuevaContrasena) && /[a-z]/.test(nuevaContrasena),
    },
    { texto: "Al menos un número", cumple: /\d/.test(nuevaContrasena) },
    {
      texto: "Ambas contraseñas coinciden",
      cumple:
        nuevaContrasena.length > 0 &&
        nuevaContrasena === confirmarContrasena,
    },
  ];
  const fortaleza = criterios.filter((criterio) => criterio.cumple).length;
  const colorFortaleza =
    fortaleza <= 1
      ? "bg-red-400"
      : fortaleza <= 3
        ? "bg-amber-400"
        : "bg-green-600";

  const enviar = async (evento: React.FormEvent<HTMLFormElement>) => {
    evento.preventDefault();
    setError("");

    if (nuevaContrasena !== confirmarContrasena) {
      setError("Las contraseñas no coinciden.");
      return;
    }

    setCargando(true);

    try {
      await restablecerContrasena({
        uid,
        token,
        nueva_contrasena: nuevaContrasena,
        confirmar_contrasena: confirmarContrasena,
      });
      setCompletado(true);
    } catch (error) {
      setError(mensajesDelError(error));
    } finally {
      setCargando(false);
    }
  };

  return (
    <AccesoRecuperacion
      paso="Paso 2 de 2"
      titulo="Crea una contraseña nueva"
      descripcion="Elige una contraseña que no utilices en otros servicios. El enlace quedará invalidado después del cambio."
    >
      {enlaceIncompleto ? (
        <div className="rounded-2xl border border-amber-200 bg-amber-50 p-6">
          <p className="text-lg font-bold text-amber-950">Enlace incompleto</p>
          <p className="mt-2 text-sm leading-6 text-amber-900/75">
            Este enlace no contiene los datos necesarios. Solicita uno nuevo
            desde la pantalla de recuperación.
          </p>

          <Link
            to="/recuperar-contrasena"
            className="mt-5 inline-flex min-h-11 items-center rounded-xl bg-amber-900 px-4 py-2 text-sm font-semibold text-white transition hover:bg-amber-950"
          >
            Solicitar otro enlace
          </Link>
        </div>
      ) : completado ? (
        <div
          className="rounded-2xl border border-green-200 bg-gradient-to-br from-green-50 to-emerald-50 p-6"
          role="status"
          aria-live="polite"
        >
          <div className="flex gap-3">
            <CheckCircle2
              className="mt-0.5 h-6 w-6 shrink-0 text-green-700"
              aria-hidden="true"
            />
            <div>
              <p className="text-lg font-bold text-green-950">
                Contraseña actualizada
              </p>
              <p className="mt-2 text-sm leading-6 text-green-900/75">
                Tu acceso quedó protegido. Ya puedes ingresar con la
                contraseña que acabas de crear.
              </p>
            </div>
          </div>

          <Link
            to="/login"
            className="group mt-6 flex min-h-12 items-center justify-center gap-2 rounded-xl bg-green-700 px-5 py-3 text-center text-sm font-semibold text-white shadow-lg shadow-green-700/15 transition hover:bg-green-800"
          >
            Ir al inicio de sesión
            <ArrowRight
              className="h-4 w-4 transition-transform group-hover:translate-x-0.5"
              aria-hidden="true"
            />
          </Link>
        </div>
      ) : (
        <form onSubmit={enviar} className="space-y-5">
          <div>
            <label
              htmlFor="nueva-contrasena"
              className="mb-2 block text-sm font-semibold text-slate-700"
            >
              Nueva contraseña
            </label>
            <div className="flex items-center rounded-xl border border-slate-300 bg-white px-4 shadow-sm transition focus-within:border-green-600 focus-within:ring-4 focus-within:ring-green-100">
              <LockKeyhole
                className="h-5 w-5 text-slate-400"
                aria-hidden="true"
              />
              <input
                id="nueva-contrasena"
                type={mostrar ? "text" : "password"}
                value={nuevaContrasena}
                onChange={(evento) => setNuevaContrasena(evento.target.value)}
                autoComplete="new-password"
                className="w-full bg-transparent px-3 py-3.5 text-slate-900 outline-none"
                required
                autoFocus
              />
              <button
                type="button"
                onClick={() => setMostrar((valor) => !valor)}
                className="grid h-10 w-10 place-items-center rounded-lg text-slate-400 transition hover:bg-slate-50 hover:text-slate-600 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-green-600"
                aria-label={mostrar ? "Ocultar contraseñas" : "Mostrar contraseñas"}
              >
                {mostrar ? (
                  <EyeOff className="h-5 w-5" />
                ) : (
                  <Eye className="h-5 w-5" />
                )}
              </button>
            </div>
          </div>

          <div>
            <label
              htmlFor="confirmar-contrasena"
              className="mb-2 block text-sm font-semibold text-slate-700"
            >
              Repetir contraseña
            </label>
            <input
              id="confirmar-contrasena"
              type={mostrar ? "text" : "password"}
              value={confirmarContrasena}
              onChange={(evento) => setConfirmarContrasena(evento.target.value)}
              autoComplete="new-password"
              className="w-full rounded-xl border border-slate-300 bg-white px-4 py-3.5 text-slate-900 shadow-sm outline-none transition focus:border-green-600 focus:ring-4 focus:ring-green-100"
              required
            />
          </div>

          <div className="rounded-2xl border border-slate-200 bg-slate-50/80 p-4">
            <div
              className="grid grid-cols-4 gap-1.5"
              aria-label={`Fortaleza de contraseña: ${fortaleza} de 4`}
            >
              {[1, 2, 3, 4].map((nivel) => (
                <span
                  key={nivel}
                  className={`h-1.5 rounded-full transition-colors ${
                    fortaleza >= nivel ? colorFortaleza : "bg-slate-200"
                  }`}
                />
              ))}
            </div>

            <ul className="mt-4 grid gap-2 sm:grid-cols-2">
              {criterios.map((criterio) => (
                <li
                  key={criterio.texto}
                  className={`flex items-center gap-2 text-xs ${
                    criterio.cumple ? "text-green-700" : "text-slate-500"
                  }`}
                >
                  <span
                    className={`grid h-4 w-4 place-items-center rounded-full ${
                      criterio.cumple
                        ? "bg-green-100 text-green-700"
                        : "bg-slate-200 text-transparent"
                    }`}
                  >
                    <Check className="h-3 w-3" aria-hidden="true" />
                  </span>
                  {criterio.texto}
                </li>
              ))}
            </ul>
          </div>

          {error && (
            <div
              className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm leading-6 text-red-700"
              role="alert"
            >
              {error}
            </div>
          )}

          <button
            type="submit"
            disabled={cargando}
            className="inline-flex min-h-13 w-full items-center justify-center gap-2 rounded-xl bg-green-700 px-5 py-3.5 font-semibold text-white shadow-lg shadow-green-700/15 transition hover:bg-green-800 hover:shadow-xl focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-green-600 focus-visible:ring-offset-4 disabled:cursor-not-allowed disabled:opacity-60"
          >
            {cargando ? (
              <>
                <LoaderCircle
                  className="h-5 w-5 animate-spin"
                  aria-hidden="true"
                />
                Actualizando…
              </>
            ) : (
              "Guardar nueva contraseña"
            )}
          </button>
        </form>
      )}
    </AccesoRecuperacion>
  );
}


export default RestablecerContrasena;
