
import { useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { User, Lock, Eye, EyeOff } from "lucide-react";
import axios from "axios";

import { iniciarSesion } from "../../services/usuario.service";
import { guardarSesion } from "../../services/sesion";

import fondo from "../../assets/images/CCAA.png";
import logo from "../../assets/logos/logo-campos-australes-normal.png";

function Login() {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [mostrarPassword, setMostrarPassword] = useState(false);
  const [error, setError] = useState("");
  const [cargando, setCargando] = useState(false);

  const navegar = useNavigate();
  const ubicacion = useLocation();

  // Si RutaProtegida desvió al usuario hasta aquí, vuelve a donde iba.
  const destino =
    (ubicacion.state as { desde?: string } | null)?.desde || "/dashboard";

  const handleLogin = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();

    setError("");
    setCargando(true);

    try {
      const datos = await iniciarSesion(username, password);

      guardarSesion({
        usuario: datos.usuario,
        nombre: datos.nombre,
        apellido: datos.apellido,
      });

      navegar(destino, { replace: true });
    } catch (error) {
      // El backend responde 400 si falta un campo y 401 si las credenciales
      // no son válidas; en ambos casos manda su propio mensaje.
      if (axios.isAxiosError(error) && error.response) {
        setError(
          error.response.data?.error || "Usuario o contraseña incorrectos"
        );
      } else {
        console.error("Error conectando con Django:", error);
        setError("No se pudo conectar con el servidor.");
      }
    } finally {
      setCargando(false);
    }
  };

  return (
    <div className="min-h-screen flex bg-slate-100">

      {/* Imagen */}
      <div className="hidden lg:flex w-3/5 relative">

        <img
          src={fondo}
          className="absolute inset-0 h-full w-full object-cover"
          alt="Campos Australes"
        />

        <div className="absolute inset-0 bg-gradient-to-br"></div>

        <div className="relative z-10 flex flex-col justify-end p-16 text-white">

          <h1 className="text-5xl font-bold mb-4">
            Sistema de Producción
          </h1>

          <h2 className="text-3xl text-green-200 mb-6">
            Campos Australes
          </h2>

          <p className="max-w-xl text-lg leading-8 text-green-50">
            Plataforma para la gestión integral de la producción,
            trazabilidad, calidad e inventario.
          </p>

        </div>

      </div>

      {/* Login */}
      <div className="flex flex-1 items-center justify-center bg-white">

        <div className="w-full max-w-md px-10">

          {/* Logo */}
          <img
            src={logo}
            className="w-48 mb-10"
            alt="Campos Australes"
          />

          <h2 className="text-4xl font-bold text-slate-800">
            Bienvenido
          </h2>

          <p className="mt-2 mb-10 text-slate-500">
            Inicia sesión para acceder al sistema.
          </p>

          <form onSubmit={handleLogin} className="space-y-6">

            {/* Usuario */}
            <div>

              <label className="mb-2 block text-sm font-medium text-slate-700">
                Usuario
              </label>

              <div className="flex items-center rounded-xl border border-slate-300 bg-white px-4">

                <User className="h-5 w-5 text-slate-400" />

                <input
                  type="text"
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  placeholder="sjuan"
                  className="w-full bg-transparent px-3 py-4 outline-none"
                  autoComplete="username"
                  required
                />

              </div>

            </div>

            {/* Contraseña */}
            <div>

              <label className="mb-2 block text-sm font-medium text-slate-700">
                Contraseña
              </label>

              <div className="flex items-center rounded-xl border border-slate-300 bg-white px-4">

                <Lock className="h-5 w-5 text-slate-400" />

                <input
                  type={mostrarPassword ? "text" : "password"}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="••••••••••••"
                  className="w-full bg-transparent px-3 py-4 outline-none"
                  autoComplete="current-password"
                  required
                />

                <button
                  type="button"
                  onClick={() => setMostrarPassword(!mostrarPassword)}
                  className="text-slate-400"
                  aria-label={
                    mostrarPassword
                      ? "Ocultar contraseña"
                      : "Mostrar contraseña"
                  }
                >
                  {mostrarPassword ? (
                    <EyeOff className="h-5 w-5" />
                  ) : (
                    <Eye className="h-5 w-5" />
                  )}
                </button>

              </div>

            </div>

            {/* Error */}
            {error && (
              <div className="rounded-xl bg-red-50 px-4 py-3 text-sm text-red-700">
                {error}
              </div>
            )}

            {/* Recordarme / recuperar */}
            <div className="flex items-center justify-between">

              <label className="flex items-center gap-2 text-sm">

                <input type="checkbox" />

                Recordarme

              </label>

              <button
                type="button"
                className="text-sm text-green-700 hover:underline"
              >
                ¿Olvidaste tu contraseña?
              </button>

            </div>

            {/* Botón */}
            <button
              type="submit"
              disabled={cargando}
              className="
                w-full
                rounded-xl
                bg-green-700
                py-4
                font-semibold
                text-white
                transition-all
                duration-300
                hover:bg-green-800
                hover:shadow-xl
                disabled:cursor-not-allowed
                disabled:opacity-60
              "
            >
              {cargando ? "Ingresando..." : "Iniciar sesión"}
            </button>

          </form>

          <div className="mt-12 text-center text-sm text-slate-400">

            Factory System

            <br />

            Versión 1.0

          </div>

        </div>

      </div>

    </div>
  );
}

export default Login;

