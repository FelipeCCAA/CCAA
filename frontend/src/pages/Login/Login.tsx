
import { useState } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { User, Lock, Eye, EyeOff } from "lucide-react";
import axios from "axios";

import { iniciarSesion } from "../../services/usuario.service";
import { guardarSesion } from "../../services/sesion";

import fondo from "../../assets/images/CCAA.jpg";
import logo from "../../assets/logos/logo-campos-australes-normal.png";

function Login() {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [mostrarPassword, setMostrarPassword] = useState(false);
  const [recordar, setRecordar] = useState(false);
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
      const sesion = await iniciarSesion(username, password);

      guardarSesion(sesion, recordar);

      // Administración tiene una portada propia. Los demás roles conservan
      // el destino solicitado o entran al panel operativo general.
      const area = sesion.usuario.perfil?.area;
      const porArea: Record<string, string> = {
        recepcion: "/recepcion",
        condensacion: "/produccion",
        secado: "/produccion",
        envase: "/produccion",
        calidad: "/liberacion",
        bodega: "/abastecimiento",
        compras: "/abastecimiento",
        despacho: "/abastecimiento",
      };
      navegar(
        sesion.usuario.perfil?.nivel === "admin" || sesion.usuario.rol === "admin"
          ? "/administracion"
          : (area && porArea[area]) || destino,
        {
        replace: true,
        },
      );
    } catch (error) {
      // El backend responde 400 si falta un campo, 401 si las credenciales no
      // son válidas y 403 si la cuenta está desactivada; en los tres casos
      // manda su propio mensaje.
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

        {/* Velo sobre la foto.

            Los colores no son decorativos: sin ellos, `bg-gradient-to-*` no
            pinta nada —declara la dirección pero no de qué a qué— y el texto
            blanco queda directamente sobre la imagen. Se oscurece abajo, que
            es donde va el texto, y se deja limpia la parte de arriba. */}
        <div className="absolute inset-0 bg-gradient-to-t from-slate-900/80 via-slate-900/30 to-transparent"></div>

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

              <label
                htmlFor="usuario"
                className="mb-2 block text-sm font-medium text-slate-700"
              >
                Usuario
              </label>

              <div className="flex items-center rounded-xl border border-slate-300 bg-white px-4">

                <User className="h-5 w-5 text-slate-400" />

                <input
                  id="usuario"
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

              <label
                htmlFor="password"
                className="mb-2 block text-sm font-medium text-slate-700"
              >
                Contraseña
              </label>

              <div className="flex items-center rounded-xl border border-slate-300 bg-white px-4">

                <Lock className="h-5 w-5 text-slate-400" />

                <input
                  id="password"
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

              {/* Sin marcar, la sesión vive en sessionStorage y muere al
                  cerrar la pestaña. En una operación con turnos A/B/C sobre los
                  mismos terminales, eso evita que el turno siguiente herede la
                  sesión del anterior (ver services/sesion.ts). */}
              <label
                htmlFor="recordarme"
                className="flex items-center gap-2 text-sm text-slate-700"
              >

                <input
                  id="recordarme"
                  type="checkbox"
                  checked={recordar}
                  onChange={(e) => setRecordar(e.target.checked)}
                  className="h-4 w-4 rounded border-slate-300 text-green-700 focus:ring-green-600"
                />

                Mantener la sesión iniciada

              </label>

              <Link
                to="/recuperar-contrasena"
                className="text-sm text-green-700 hover:underline"
              >
                ¿Olvidaste tu contraseña?
              </Link>

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

            Gestión Productiva · CCAA

            <br />

            Versión 1.0

          </div>

        </div>

      </div>

    </div>
  );
}

export default Login;

