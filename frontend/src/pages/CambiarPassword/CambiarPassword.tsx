import { useState } from "react";
import axios from "axios";
import { useNavigate } from "react-router-dom";

import { cambiarPassword } from "../../services/usuario.service";
import { cerrarSesion, guardarMotivoCierre } from "../../services/sesion";


export default function CambiarPassword() {
  const [actual, setActual] = useState("");
  const [nueva, setNueva] = useState("");
  const [confirmacion, setConfirmacion] = useState("");
  const [error, setError] = useState("");
  const [guardando, setGuardando] = useState(false);
  const navegar = useNavigate();

  const guardar = async (evento: React.FormEvent) => {
    evento.preventDefault();
    setGuardando(true);
    setError("");
    try {
      const respuesta = await cambiarPassword({
        password_actual: actual,
        nueva_contrasena: nueva,
        confirmar_contrasena: confirmacion,
      });
      cerrarSesion();
      guardarMotivoCierre(respuesta.mensaje);
      navegar("/login", { replace: true });
    } catch (fallo) {
      if (axios.isAxiosError(fallo) && fallo.response?.data) {
        const datos = fallo.response.data as Record<string, string | string[]>;
        const primero = Object.values(datos)[0];
        setError(Array.isArray(primero) ? primero[0] : primero || "No se pudo cambiar la contraseña.");
      } else {
        setError("No se pudo conectar con el servidor.");
      }
    } finally {
      setGuardando(false);
    }
  };

  return (
    <main className="flex min-h-screen items-center justify-center bg-slate-100 p-6">
      <section className="w-full max-w-md rounded-2xl bg-white p-8 shadow-sm">
        <h1 className="text-2xl font-bold text-slate-900">Cambiar contraseña</h1>
        <p className="mt-2 text-sm text-slate-500">Debes completar este paso antes de continuar.</p>
        <form onSubmit={guardar} className="mt-7 space-y-4">
          <input type="password" required autoComplete="current-password" value={actual} onChange={(e) => setActual(e.target.value)} placeholder="Contraseña actual" className="w-full rounded-xl border border-slate-300 px-4 py-3" />
          <input type="password" required autoComplete="new-password" value={nueva} onChange={(e) => setNueva(e.target.value)} placeholder="Nueva contraseña" className="w-full rounded-xl border border-slate-300 px-4 py-3" />
          <input type="password" required autoComplete="new-password" value={confirmacion} onChange={(e) => setConfirmacion(e.target.value)} placeholder="Confirmar nueva contraseña" className="w-full rounded-xl border border-slate-300 px-4 py-3" />
          {error && <p className="rounded-xl bg-red-50 px-4 py-3 text-sm text-red-700">{error}</p>}
          <button disabled={guardando} className="w-full rounded-xl bg-green-700 py-3 font-semibold text-white disabled:opacity-50">{guardando ? "Guardando…" : "Cambiar contraseña"}</button>
        </form>
      </section>
    </main>
  );
}
