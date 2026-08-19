import { useState } from "react";
import axios from "axios";
import { ArrowRight, CheckCircle2, LoaderCircle, Mail } from "lucide-react";

import { solicitarRecuperacion } from "../../services/usuario.service";

import AccesoRecuperacion from "./AccesoRecuperacion";


function mensajeDelError(error: unknown): string {
  if (!axios.isAxiosError(error) || !error.response) {
    return "No se pudo conectar con el servidor.";
  }

  const datos = error.response.data;

  if (typeof datos?.error === "string") {
    return datos.error;
  }

  if (Array.isArray(datos?.email)) {
    return datos.email.join(" ");
  }

  if (error.response.status === 429) {
    return "Se realizaron demasiadas solicitudes. Intenta nuevamente más tarde.";
  }

  return "No se pudo procesar la solicitud.";
}


function RecuperarContrasena() {
  const [email, setEmail] = useState("");
  const [cargando, setCargando] = useState(false);
  const [mensaje, setMensaje] = useState("");
  const [error, setError] = useState("");

  const enviar = async (evento: React.FormEvent<HTMLFormElement>) => {
    evento.preventDefault();
    setCargando(true);
    setError("");

    try {
      const respuesta = await solicitarRecuperacion(email.trim());
      setMensaje(respuesta.mensaje);
    } catch (error) {
      setError(mensajeDelError(error));
    } finally {
      setCargando(false);
    }
  };

  return (
    <AccesoRecuperacion
      paso="Paso 1 de 2"
      titulo="Recupera tu contraseña"
      descripcion="Ingresa el correo asociado a tu cuenta. Te enviaremos las instrucciones para crear una contraseña nueva."
    >
      {mensaje ? (
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
                Revisa tu bandeja de entrada
              </p>
              <p className="mt-2 text-sm leading-6 text-green-900/75">
                {mensaje}
              </p>
              <p className="mt-4 border-t border-green-200/70 pt-4 text-xs leading-5 text-green-800">
                La entrega puede tardar unos minutos. Revisa también las
                carpetas de correo no deseado y otros.
              </p>
            </div>
          </div>
        </div>
      ) : (
        <form onSubmit={enviar} className="space-y-5">
          <div>
            <label
              htmlFor="email-recuperacion"
              className="mb-2 block text-sm font-semibold text-slate-700"
            >
              Correo electrónico
            </label>

            <div className="flex items-center rounded-xl border border-slate-300 bg-white px-4 shadow-sm transition focus-within:border-green-600 focus-within:ring-4 focus-within:ring-green-100">
              <Mail className="h-5 w-5 text-slate-600" aria-hidden="true" />
              <input
                id="email-recuperacion"
                type="email"
                value={email}
                onChange={(evento) => setEmail(evento.target.value)}
                placeholder="nombre@camposaustrales.cl"
                autoComplete="email"
                className="w-full bg-transparent px-3 py-3.5 text-slate-900 outline-none placeholder:text-slate-400"
                required
                autoFocus
              />
            </div>
            <p className="mt-2 text-xs leading-5 text-slate-600">
              Usa el mismo correo registrado por el administrador.
            </p>
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
            className="group inline-flex min-h-13 w-full items-center justify-center gap-2 rounded-xl bg-green-700 px-5 py-3.5 font-semibold text-white shadow-lg shadow-green-700/15 transition hover:bg-green-800 hover:shadow-xl focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-green-600 focus-visible:ring-offset-4 disabled:cursor-not-allowed disabled:opacity-60"
          >
            {cargando ? (
              <>
                <LoaderCircle
                  className="h-5 w-5 animate-spin"
                  aria-hidden="true"
                />
                Enviando…
              </>
            ) : (
              <>
                Enviar enlace seguro
                <ArrowRight
                  className="h-4 w-4 transition-transform group-hover:translate-x-0.5"
                  aria-hidden="true"
                />
              </>
            )}
          </button>
        </form>
      )}
    </AccesoRecuperacion>
  );
}


export default RecuperarContrasena;
